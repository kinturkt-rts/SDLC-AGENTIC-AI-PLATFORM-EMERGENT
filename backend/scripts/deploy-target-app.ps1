# Deploy a target-app to AWS (ECS Fargate + shared ALB) via Terraform.

param(
    [Parameter(Mandatory = $true)] [string] $Feature,
    [switch] $SkipBuild,
    [switch] $PlanOnly,
    [switch] $Destroy,
    [string] $Region = "us-east-2",
    [string] $ImageTag = "latest"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$MonorepoRoot = Split-Path -Parent $RepoRoot

# Load .env/.env.local so standalone runs get POSTGRES_MCP_* / AWS_PROFILE
# (process env always wins; same semantics as run-sdlc-local.ps1).
foreach ($envPath in @(
    (Join-Path $MonorepoRoot ".env"),
    (Join-Path $MonorepoRoot ".env.local"),
    (Join-Path $RepoRoot ".env"),
    (Join-Path $RepoRoot ".env.local")
)) {
    if (-not (Test-Path $envPath)) { continue }
    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        if ($name -and -not (Test-Path "env:$name")) { Set-Item -Path "env:$name" -Value $value }
    }
}

# Cache Terraform providers across runs (~600MB AWS provider) — faster init and
# resilient to transient registry/DNS failures.
if (-not $env:TF_PLUGIN_CACHE_DIR) {
    $tfCache = Join-Path $env:LOCALAPPDATA "terraform-plugin-cache"
    New-Item -ItemType Directory -Force -Path $tfCache | Out-Null
    $env:TF_PLUGIN_CACHE_DIR = $tfCache
}
$AppDir = Join-Path $RepoRoot "target-apps\$Feature"
$TfRoot = Join-Path $RepoRoot "infrastructure\environments\dev\$Feature"

function Invoke-Native {
    param([string] $Exe, [string[]] $Arguments, [string] $Label)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)." }
}

# ── Resolve tools ──────────────────────────────────────────────────────────────
$tf = Get-Command terraform -ErrorAction SilentlyContinue
if (-not $tf) {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $tf = Get-Command terraform -ErrorAction SilentlyContinue
}
if (-not $tf) { throw "terraform not found on PATH. Install with: winget install HashiCorp.Terraform" }
$Terraform = $tf.Source

if (-not (Test-Path $TfRoot)) {
    throw "No Terraform root for '$Feature' at infrastructure/environments/dev/$Feature. Create it (see hello-fastapi example)."
}

Write-Host "`n=== deploy-target-app: $Feature (dev, $Region) ===" -ForegroundColor Green

if (-not $env:TF_VAR_database_url -and $env:POSTGRES_MCP_DB_PASSWORD -and $env:POSTGRES_MCP_DB_ENDPOINT -and $env:POSTGRES_MCP_DATABASE -and $env:POSTGRES_MCP_DB_USER) {
    $dbPort = if ($env:POSTGRES_MCP_PORT) { $env:POSTGRES_MCP_PORT } else { "5432" }
    # postgresql+psycopg + sslmode: matches target-app SQLAlchemy/psycopg3 expectations
    $env:TF_VAR_database_url = "postgresql+psycopg://$($env:POSTGRES_MCP_DB_USER):$($env:POSTGRES_MCP_DB_PASSWORD)@$($env:POSTGRES_MCP_DB_ENDPOINT):${dbPort}/$($env:POSTGRES_MCP_DATABASE)?sslmode=require"
    Write-Host "TF_VAR_database_url derived from POSTGRES_MCP_* env." -ForegroundColor DarkGray
}

# ── AWS identity ───────────────────────────────────────────────────────────────
$identityJson = aws sts get-caller-identity --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw "AWS credentials unavailable. Run: aws sso login --profile $env:AWS_PROFILE" }
$Account = (ConvertFrom-Json ($identityJson -join "`n")).Account
$Registry = "$Account.dkr.ecr.$Region.amazonaws.com"
Write-Host "AWS account: $Account" -ForegroundColor DarkGray

# ── Terraform init ─────────────────────────────────────────────────────────────
Push-Location $TfRoot
try {
    Invoke-Native $Terraform @("init", "-input=false", "-upgrade=false") "terraform init"

    if ($Destroy) {
        Invoke-Native $Terraform @("destroy", "-input=false", "-auto-approve") "terraform destroy"
        Write-Host "`n[$Feature] destroyed. (ECR repos had force_delete, images are gone too.)" -ForegroundColor Yellow
        return
    }

    if ($PlanOnly) {
        Invoke-Native $Terraform @("plan", "-input=false") "terraform plan"
        return
    }

    # ── 1) Ensure ECR repos exist before pushing images ────────────────────────
    Write-Host "`n--- [1/4] Terraform: ECR repositories ---" -ForegroundColor Cyan
    Invoke-Native $Terraform @(
        "apply", "-input=false", "-auto-approve",
        "-target=module.app.aws_ecr_repository.api",
        "-target=module.app.aws_ecr_repository.ui"
    ) "terraform apply (ECR)"

    # ── 2) Build + push images ──────────────────────────────────────────────────
    if (-not $SkipBuild) {
        if (-not (Test-Path $AppDir)) { throw "App directory not found: $AppDir" }
        docker version --format '{{.Server.Version}}' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Docker daemon not running. Start Docker Desktop and retry." }

        Write-Host "`n--- [2/4] Build + push images to ECR ---" -ForegroundColor Cyan
        if ($IsLinux -or $IsMacOS) {
            # pwsh on Linux/macOS pipes stdin natively without the CRLF issue
            # below - no cmd wrapper available there anyway (cmd.exe is
            # Windows-only), so use a direct pipe.
            aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry
        } else {
            # cmd /c keeps the pipe out of PowerShell 5.1, which appends CRLF to piped
            # stdin and breaks --password-stdin with a 400 from the registry.
            cmd /c "aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry"
        }
        if ($LASTEXITCODE -ne 0) { throw "docker login to ECR failed." }

        $apiImage = "${Registry}/sdlc/$Feature/api:$ImageTag"
        Invoke-Native "docker" @("build", "-f", (Join-Path $AppDir "deploy\Dockerfile.api"), "-t", $apiImage, $AppDir) "docker build api"
        Invoke-Native "docker" @("push", $apiImage) "docker push api"

        $uiDockerfile = Join-Path $AppDir "deploy\Dockerfile.ui"
        if ((Test-Path $uiDockerfile) -and (Test-Path (Join-Path $AppDir "ui\streamlit_app.py"))) {
            $uiImage = "${Registry}/sdlc/$Feature/ui:$ImageTag"
            Invoke-Native "docker" @("build", "-f", $uiDockerfile, "-t", $uiImage, $AppDir) "docker build ui"
            Invoke-Native "docker" @("push", $uiImage) "docker push ui"
        } else {
            Write-Host "No UI Dockerfile/streamlit app - api-only deploy." -ForegroundColor DarkGray
        }
    }

    # ── 3) Full apply ───────────────────────────────────────────────────────────
    Write-Host "`n--- [3/4] Terraform: full apply ---" -ForegroundColor Cyan
    Invoke-Native $Terraform @("apply", "-input=false", "-auto-approve") "terraform apply"

    $AppUrl = (& $Terraform output -raw app_url)
    $Service = (& $Terraform output -raw service_name)
    $Cluster = (& $Terraform output -raw cluster_name)

    # ── 4) Roll service (":latest" re-push needs a forced deployment) + wait ────
    Write-Host "`n--- [4/4] Roll ECS service + wait for stable ---" -ForegroundColor Cyan
    if (-not $SkipBuild) {
        aws ecs update-service --cluster $Cluster --service $Service --force-new-deployment --region $Region --output text --query 'service.serviceName' | Out-Null
    }
    Write-Host "Waiting for ECS service to stabilize (can take a few minutes)..." -ForegroundColor DarkGray
    aws ecs wait services-stable --cluster $Cluster --services $Service --region $Region
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Service did not stabilize in time. Check: CloudWatch /ecs/sdlc/dev/$Feature and target group health."
    }

    # Smoke test through the ALB (Streamlit health first, /health for api-only apps)
    $healthy = $false
    $healthUrl = ""
    foreach ($attempt in 1..10) {
        foreach ($suffix in @("_stcore/health", "health")) {
            $candidate = "$($AppUrl.TrimEnd('/'))/$suffix"
            try {
                $resp = Invoke-WebRequest -Uri $candidate -UseBasicParsing -TimeoutSec 10
                if ($resp.StatusCode -eq 200) { $healthy = $true; $healthUrl = $candidate; break }
            } catch {}
        }
        if ($healthy) { break }
        Start-Sleep -Seconds 15
    }
    if (-not $healthUrl) { $healthUrl = "$($AppUrl.TrimEnd('/'))/_stcore/health" }

    Write-Host "`n=== $Feature deployed ===" -ForegroundColor Green
    if ($healthy) {
        Write-Host "Health check OK through ALB." -ForegroundColor Green
        Write-Host "Live UI: $AppUrl" -ForegroundColor Yellow
    } else {
        Write-Warning "Health endpoint not answering ($healthUrl) after all retries - NOT reporting this as live."
    }

    $handoffDir = Join-Path $RepoRoot "agents\pipeline"
    if (Test-Path $handoffDir) {
        $handoffPath = Join-Path $handoffDir "$Feature.devops-handoff.json"
        $handoff = @{}
        if (Test-Path $handoffPath) {
            try {
                $existing = Get-Content $handoffPath -Raw | ConvertFrom-Json
                foreach ($prop in $existing.PSObject.Properties) { $handoff[$prop.Name] = $prop.Value }
            } catch {}
        }
        $handoff["targetApp"] = $Feature
        $handoff["environment"] = "dev"
        $handoff["region"] = $Region
        # Only record appUrl when the health check actually passed - an unhealthy
        # deployment must not be reported as "live" to downstream consumers
        # (devops_agent.py's CLI output, S3 handoff sync, the frontend).
        if ($healthy) { $handoff["appUrl"] = $AppUrl } else { $handoff.Remove("appUrl") | Out-Null }
        $handoff["ecsCluster"] = $Cluster
        $handoff["ecsService"] = $Service
        $handoff["imageTag"] = $ImageTag
        $handoff["healthy"] = $healthy
        $handoff["deployedAt"] = (Get-Date).ToUniversalTime().ToString("o")
        $handoff | ConvertTo-Json -Depth 10 | Out-File -FilePath $handoffPath -Encoding utf8
        Write-Host "Handoff: agents/pipeline/$Feature.devops-handoff.json" -ForegroundColor DarkGray
    }

    if (-not $healthy) {
        # Infra apply succeeded but the app never came up healthy - fail loudly
        # so the caller (devops_agent.py, GitLab CI) doesn't treat this as success.
        exit 2
    }
}
finally {
    Pop-Location
}
