# Deploy a target-app to AWS (ECS Fargate + shared ALB) via Terraform.

param(
    [Parameter(Mandatory = $true)] [string] $Feature,
    [switch] $SkipBuild,
    [switch] $PlanOnly,
    [switch] $Destroy,
    [string] $Region = "us-east-2",
    [string] $ImageTag = "latest",
    # Absorbs unquoted name fragments: -Feature prior auth workbench -> prior-auth-workbench
    [Parameter(ValueFromRemainingArguments = $true)] [string[]] $FeatureTail
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

# Cache Terraform providers across runs (~600MB AWS provider) - faster init and
# resilient to transient registry/DNS failures.
if (-not $env:TF_PLUGIN_CACHE_DIR) {
    $tfCache = Join-Path $env:LOCALAPPDATA "terraform-plugin-cache"
    New-Item -ItemType Directory -Force -Path $tfCache | Out-Null
    $env:TF_PLUGIN_CACHE_DIR = $tfCache
}

# Normalize feature slug: spaces -> dashes, lowercase.
# Handles both -Feature prior-auth-workbench and -Feature prior auth workbench.
$FeatureParts = @($Feature) + @($FeatureTail | Where-Object { $_ -and $_ -notmatch '^-' })
$Feature = (($FeatureParts -join '-') -replace '_', '-' -replace '\s+', '-').ToLowerInvariant().Trim('-')
if (-not $Feature) { throw "Feature/app slug is required." }

$AppDir = Join-Path $RepoRoot "target-apps\$Feature"
$TfRoot = Join-Path $RepoRoot "infrastructure\environments\dev\$Feature"
$TfMain = Join-Path $TfRoot "main.tf"

function Invoke-Native {
    param([string] $Exe, [string[]] $Arguments, [string] $Label)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)." }
}

function Test-TfRootComplete {
    if (-not (Test-Path $TfMain)) { return $false }
    $text = Get-Content -Raw -Path $TfMain
    return [bool]($text -match 'module\s+"app"')
}

function Test-TfRootAutoScaffolded {
    # Only roots written by ensure-target-app-tf-root.py. Never delete devops-agent
    # / hand-authored roots (e.g. expense-tracker) or shared/control-plane trees.
    if (-not (Test-Path $TfMain)) { return $false }
    $head = Get-Content -Path $TfMain -TotalCount 8 -ErrorAction SilentlyContinue
    return [bool]($head -match 'Auto-scaffolded by scripts/ensure-target-app-tf-root\.py')
}

function Ensure-TfRoot {
    if (Test-TfRootComplete) { return }

    $ensurePy = Join-Path $PSScriptRoot "ensure-target-app-tf-root.py"
    if (-not (Test-Path $ensurePy)) {
        throw "Missing $ensurePy (needed to scaffold TF root from remote state)."
    }

    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) { throw "python not found on PATH (needed to scaffold missing TF root)." }

    Write-Host "Local TF root missing/incomplete for '$Feature' - scaffolding from S3 state..." -ForegroundColor Cyan
    & $py.Source $ensurePy --app $Feature --region $Region
    if ($LASTEXITCODE -ne 0) {
        throw "Could not scaffold Terraform root for '$Feature'. If this app was never deployed, there is nothing to destroy."
    }
    if (-not (Test-TfRootComplete)) {
        throw "Scaffolded TF root still incomplete at $TfMain"
    }
}

# -- Resolve tools --------------------------------------------------------------
$tf = Get-Command terraform -ErrorAction SilentlyContinue
if (-not $tf) {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path', 'User')
    $tf = Get-Command terraform -ErrorAction SilentlyContinue
}
if (-not $tf) {
    # winget install often leaves terraform off PATH until a new shell
    $wingetTf = Get-ChildItem "${env:LOCALAPPDATA}\Microsoft\WinGet\Packages" -Recurse -Filter terraform.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if ($wingetTf) {
        $env:Path = (Split-Path -Parent $wingetTf) + [IO.Path]::PathSeparator + $env:Path
        $tf = Get-Command terraform -ErrorAction SilentlyContinue
    }
}
if (-not $tf) { throw "terraform not found on PATH. Install with: winget install HashiCorp.Terraform" }
$Terraform = $tf.Source

if (-not (Test-TfRootComplete)) {
    if ($Destroy) {
        Ensure-TfRoot
    } else {
        throw "No Terraform root for $Feature. Run: python .\scripts\ensure-target-app-tf-root.py --app $Feature"
    }
}

$banner = [string]::Format('=== deploy-target-app: {0} (dev, {1}) ===', $Feature, $Region)
Write-Host $banner -ForegroundColor Green

if (-not $env:TF_VAR_database_url -and $env:POSTGRES_MCP_DB_PASSWORD -and $env:POSTGRES_MCP_DB_ENDPOINT -and $env:POSTGRES_MCP_DATABASE -and $env:POSTGRES_MCP_DB_USER) {
    $dbPort = if ($env:POSTGRES_MCP_PORT) { $env:POSTGRES_MCP_PORT } else { "5432" }
    $env:TF_VAR_database_url = (
        'postgresql+psycopg://' +
        $env:POSTGRES_MCP_DB_USER + ':' +
        $env:POSTGRES_MCP_DB_PASSWORD + '@' +
        $env:POSTGRES_MCP_DB_ENDPOINT + ':' +
        $dbPort + '/' +
        $env:POSTGRES_MCP_DATABASE +
        '?sslmode=require'
    )
    Write-Host "TF_VAR_database_url derived from POSTGRES_MCP_* env." -ForegroundColor DarkGray
}

if ($Destroy -and -not $env:TF_VAR_database_url) {
    $env:TF_VAR_database_url = 'postgresql+psycopg://unused:unused@localhost:5432/unused'
}

# -- AWS identity ---------------------------------------------------------------
$identityJson = aws sts get-caller-identity --region $Region --output json
if ($LASTEXITCODE -ne 0) { throw "AWS credentials unavailable. Run: aws sso login --profile $env:AWS_PROFILE" }
$Account = (ConvertFrom-Json ($identityJson -join "`n")).Account
$Registry = "$Account.dkr.ecr.$Region.amazonaws.com"
Write-Host "AWS account: $Account" -ForegroundColor DarkGray

# -- Terraform init -------------------------------------------------------------
$cleanupScaffoldedTfRoot = $false
Push-Location $TfRoot
try {
    Invoke-Native $Terraform @("init", "-input=false", "-upgrade=false") "terraform init"

    if ($Destroy) {
        $wasAutoScaffolded = Test-TfRootAutoScaffolded
        Invoke-Native $Terraform @("destroy", "-input=false", "-auto-approve") "terraform destroy"
        Write-Host "`n[$Feature] destroyed. (ECR repos had force_delete, images are gone too.)" -ForegroundColor Yellow
        # Only after success — failed destroy must leave the local root for retry.
        $cleanupScaffoldedTfRoot = $wasAutoScaffolded
        return
    }

    if ($PlanOnly) {
        Invoke-Native $Terraform @("plan", "-input=false") "terraform plan"
        return
    }

    # -- 1) Ensure ECR repos exist before pushing images ------------------------
    Write-Host "`n--- [1/4] Terraform: ECR repositories ---" -ForegroundColor Cyan
    Invoke-Native $Terraform @(
        "apply", "-input=false", "-auto-approve",
        "-target=module.app.aws_ecr_repository.api",
        "-target=module.app.aws_ecr_repository.ui"
    ) "terraform apply (ECR)"

    # -- 2) Build + push images --------------------------------------------------
    if (-not $SkipBuild) {
        if (-not (Test-Path $AppDir)) { throw "App directory not found: $AppDir" }
        docker version --format '{{.Server.Version}}' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Docker daemon not running. Start Docker Desktop and retry." }

        Write-Host "`n--- [2/4] Build + push images to ECR ---" -ForegroundColor Cyan
        if ($IsLinux -or $IsMacOS) {
            aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry
        } else {
            cmd /c "aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry"
        }
        if ($LASTEXITCODE -ne 0) { throw "docker login to ECR failed." }

        $apiImage = "${Registry}/sdlc/$Feature/api:$ImageTag"
        Invoke-Native "docker" @("build", "-f", (Join-Path $AppDir "deploy\Dockerfile.api"), "-t", $apiImage, $AppDir) "docker build api"
        Invoke-Native "docker" @("push", $apiImage) "docker push api"

        $uiDockerfile = Join-Path $AppDir "deploy\Dockerfile.ui"
        $streamlitApp = Join-Path (Join-Path $AppDir "ui") "streamlit_app.py"
        if ((Test-Path $uiDockerfile) -and (Test-Path $streamlitApp)) {
            $uiImage = "${Registry}/sdlc/$Feature/ui:$ImageTag"
            Invoke-Native "docker" @("build", "-f", $uiDockerfile, "-t", $uiImage, $AppDir) "docker build ui"
            Invoke-Native "docker" @("push", $uiImage) "docker push ui"
        } else {
            Write-Host "No UI Dockerfile/streamlit app - api-only deploy." -ForegroundColor DarkGray
        }
    }

    # -- 3) Full apply -----------------------------------------------------------
    Write-Host "`n--- [3/4] Terraform: full apply ---" -ForegroundColor Cyan
    Invoke-Native $Terraform @("apply", "-input=false", "-auto-approve") "terraform apply"

    $AppUrl = (& $Terraform output -raw app_url)
    $Service = (& $Terraform output -raw service_name)
    $Cluster = (& $Terraform output -raw cluster_name)

    $hasStreamlitUi = Test-Path (Join-Path (Join-Path $AppDir "ui") "streamlit_app.py")
    $LiveUrl = if ($hasStreamlitUi) {
        $AppUrl.TrimEnd('/')
    } else {
        "$($AppUrl.TrimEnd('/'))/docs"
    }

    # -- 4) Roll service (":latest" re-push needs a forced deployment) + wait ----
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
        Write-Host "Live UI: $LiveUrl" -ForegroundColor Yellow
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
        if ($healthy) { $handoff["appUrl"] = $LiveUrl } else { $handoff.Remove("appUrl") | Out-Null }
        $handoff["ecsCluster"] = $Cluster
        $handoff["ecsService"] = $Service
        $handoff["imageTag"] = $ImageTag
        $handoff["healthy"] = $healthy
        $handoff["deployedAt"] = (Get-Date).ToUniversalTime().ToString("o")
        $handoff | ConvertTo-Json -Depth 10 | Out-File -FilePath $handoffPath -Encoding utf8
        Write-Host "Handoff: agents/pipeline/$Feature.devops-handoff.json" -ForegroundColor DarkGray
    }

    if (-not $healthy) {
        exit 2
    }
}
finally {
    Pop-Location
    # After successful destroy only: drop temporary ensure-*-scaffolded TF roots so
    # infrastructure/environments/dev/ does not accumulate orphans. Hand-authored
    # devops roots (no Auto-scaffolded marker) are left alone.
    if ($cleanupScaffoldedTfRoot -and (Test-TfRootAutoScaffolded)) {
        $devParent = Join-Path $RepoRoot "infrastructure\environments\dev"
        $resolvedRoot = [System.IO.Path]::GetFullPath($TfRoot)
        $resolvedParent = [System.IO.Path]::GetFullPath($devParent)
        $expected = [System.IO.Path]::GetFullPath((Join-Path $devParent $Feature))
        if (
            $resolvedRoot -eq $expected -and
            $resolvedRoot.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase) -and
            $Feature -notin @('_shared', 'control-plane-auth')
        ) {
            Remove-Item -LiteralPath $resolvedRoot -Recurse -Force -ErrorAction Stop
            Write-Host "Removed auto-scaffolded TF root: infrastructure/environments/dev/$Feature" -ForegroundColor DarkGray
        }
    }
}