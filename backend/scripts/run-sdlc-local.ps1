# Full SDLC chain (default): brief -> PRD -> design -> db -> apply RDS -> developer -> verify -> gitlab publish
# Default publish: gitlab-agent -> branch sdlc/<app> on GitLab origin (code.junodev.net).
# Use -SkipGitlab to skip publish after developer.
#
# DEFAULT (Postgres app, full chain + GitLab publish when .env has GITLAB_*):
#   .\scripts\run-sdlc-local.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt
#
# GitLab overrides:
#   -GitlabProject / -GitlabBase         # override GITLAB_PROJECT_PATH / GITLAB_BASE_BRANCH
#   -SkipGitlab                          # skip gitlab-agent publish step
#
#   -WithWebCrawler                      # scrape URLs into Postgres (optional step 2b)
#
# AWS deploy (opt-in step 7, after gitlab publish):
#   -WithDeploy                          # devops-agent: Terraform root + ECS Fargate deploy -> live ALB URL
#   -DeployPlanOnly                      # with -WithDeploy: terraform plan only, no AWS changes
#   Needs: Docker Desktop running, terraform on PATH, AWS SSO session (see infrastructure/README.md)
#
# Opt-out (skip steps):
#   -SkipDb -SkipPostgres                 # no database-agent, no RDS apply
#   -SkipGitlab                           # skip gitlab-agent publish (default is ON after developer)
#   -SkipQa                               # skip qa-agent
#   -SkipVerify                           # skip local import + pytest at end
#   -SkipProduct -SkipArchitect           # resume from DB or developer only
#
# Legacy aliases (still work): -WithPostgres -WithQa force those steps on if you used older scripts.
#
# See scripts/PIPELINE.md for a full command cheat sheet.

param(
    [Parameter(Mandatory = $true)]
    [string] $Feature,
    [string] $InputFile = "",
    [string] $ContextFile = "agents/pipeline/$Feature.context.json",
    [switch] $SkipProduct,
    [switch] $SkipArchitect,
    [switch] $SkipWebCrawler,
    [switch] $WithWebCrawler,
    [switch] $SkipDb,
    [switch] $SkipDeveloper,
    [switch] $SkipPostgres,
    [switch] $SkipQa,
    [switch] $SkipVerify,
    [switch] $SkipGitlab,
    [switch] $SkipFrontend,
    [switch] $WithJira,
    [string] $GitlabProject = "",
    [string] $GitlabBase = "",
    [string] $JiraProject = "",
    [int] $JiraSprint = 0,
    [ValidateSet("", "concise", "user-story")]
    [string] $JiraStoryTitleStyle = "",
    [switch] $WithPostgres,
    [switch] $WithQa,
    [switch] $WithDeploy,
    [switch] $SkipDeploy,
    [switch] $DeployPlanOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$MonorepoRoot = Split-Path -Parent $RepoRoot
Set-Location $RepoRoot

function Import-RepoEnv {
    foreach ($path in @(
        (Join-Path $MonorepoRoot ".env"),
        (Join-Path $MonorepoRoot ".env.local"),
        (Join-Path $RepoRoot ".env"),
        (Join-Path $RepoRoot ".env.local")
    )) {
        if (-not (Test-Path $path)) { continue }
        Get-Content $path | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#")) { return }
            $idx = $line.IndexOf("=")
            if ($idx -lt 1) { return }
            $name = $line.Substring(0, $idx).Trim()
            $value = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
            if ($name -and -not (Test-Path "env:$name")) {
                Set-Item -Path "env:$name" -Value $value
            }
        }
    }
}
Import-RepoEnv

# This script is the LOCAL orchestrator: every agent it spawns must resolve
# PRD/design/context paths against the local filesystem convention
# (docs/PRD/<feature>.md), never the S3/cloud-run convention (<slug>/docs/PRD/...).
# .env/.env.local may default ARTIFACT_STORE=s3 for AgentCore deploys or the
# frontend's S3 reads — that default is correct for those, but must never leak
# into a local pipeline run, so force it here regardless of what was loaded above.
$env:ARTIFACT_STORE = "local"
# artifact_layout() defaults to the nested "target-app-root" layout (target-apps/<slug>/docs/PRD/...)
# even outside cloud mode unless told otherwise. Every path check in this script — the
# PRD existence check below, ContextFile's default agents/pipeline/<feature>.context.json,
# design doc, scraped-docs dir — assumes the flat legacy "docs" layout. Force it so product-agent
# (and anything else consulting artifact_layout()) matches what this script actually reads.
$env:PRODUCT_ARTIFACT_LAYOUT = "docs"

$venvScripts = Join-Path $RepoRoot ".venv\Scripts"
if (Test-Path $venvScripts) {
    $env:PATH = "$venvScripts;$env:PATH"
}

if (-not $env:GITLAB_PROJECT_PATH -and $env:GITLAB_PROJECT) {
    $env:GITLAB_PROJECT_PATH = $env:GITLAB_PROJECT
}

$ctxPath = Join-Path $RepoRoot ($ContextFile -replace "/", "\")
$ctxDir = Split-Path $ctxPath -Parent
if (-not (Test-Path $ctxDir)) { New-Item -ItemType Directory -Path $ctxDir -Force | Out-Null }

function Invoke-PipelinePython {
    param([Parameter(Mandatory = $true)][string[]]$ArgumentList)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $prevNative = $null
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
        $prevNative = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    & python @ArgumentList 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            # Python agents log progress to stderr; PS wraps each line as ErrorRecord.
            $line = [string]$_
            if ([string]::IsNullOrWhiteSpace($line)) { return }
            if ($line -eq "System.Management.Automation.RemoteException") { return }
            Write-Host $line
        } else {
            Write-Host $_
        }
    }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($null -ne $prevNative) {
        $PSNativeCommandUseErrorActionPreference = $prevNative
    }
    return $code
}

# Full chain defaults: RDS apply when DB runs; QA only when -WithQa (Phase 3)
$applyPostgres = (-not $SkipDb) -and (-not $SkipPostgres)
$runQa = $false
if ($WithQa) { $runQa = (-not $SkipDeveloper) -and (-not $SkipQa) }
# GitLab publish runs after verify unless skipped (-SkipGitlab).
# May still run when -SkipDeveloper if target-apps/<app> already exists (resume).
$runGitlab = (-not $SkipGitlab)
# Frontend-agent runs by default after developer, before GitLab (matches sdlc_pipeline _step_frontend).
# -SkipFrontend to disable. Allowed with -SkipDeveloper for frontend-only resume when OpenAPI exists.
$runFrontend = (-not $SkipFrontend)
if ($WithPostgres) { $applyPostgres = $true }
if ($WithQa) { $runQa = $true }

if ($WithJira -and $SkipProduct) {
    throw "-WithJira requires the product step (do not use -SkipProduct). Re-run product-agent manually with --create-jira-tickets if PRD already exists."
}
if ($runGitlab) {
    if (-not $env:GITLAB_PERSONAL_ACCESS_TOKEN) {
        Write-Warning "Skipping gitlab-agent: GITLAB_PERSONAL_ACCESS_TOKEN not set in .env (use -SkipGitlab to silence)."
        $runGitlab = $false
    } elseif (-not $GitlabProject -and -not $env:GITLAB_PROJECT_PATH -and -not $env:GITLAB_PROJECT_ID) {
        Write-Warning "Skipping gitlab-agent: set GITLAB_PROJECT_PATH in .env or pass -GitlabProject."
        $runGitlab = $false
    }
}

# AWS deploy is opt-in (-WithDeploy) and never blocks the rest of the pipeline.
# Works in resume runs too (-SkipDeveloper): it deploys whatever is in target-apps/<app>/.
$runDeploy = $WithDeploy -and (-not $SkipDeploy)
if ($runDeploy) {
    $dockerOk = $false
    try {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        docker version --format '{{.Server.Version}}' 2>$null | Out-Null
        $dockerOk = ($LASTEXITCODE -eq 0)
    } catch {
        $dockerOk = $false
    } finally {
        $ErrorActionPreference = $prevEap
    }
    if (-not $dockerOk) {
        Write-Warning "Skipping deploy: Docker daemon not running (start Docker Desktop, then re-run with -SkipProduct ... -WithDeploy)."
        $runDeploy = $false
    } else {
        $tfCmd = Get-Command terraform -ErrorAction SilentlyContinue
        if (-not $tfCmd) {
            $wingetTf = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe"
            if (Test-Path (Join-Path $wingetTf "terraform.exe")) {
                $env:PATH = "$env:PATH;$wingetTf"
            } else {
                Write-Warning "Skipping deploy: terraform not found (winget install HashiCorp.Terraform)."
                $runDeploy = $false
            }
        }
    }
}

if ($WithJira -and -not $JiraProject) {
    throw "-WithJira requires -JiraProject <KEY> (e.g. SAAP). Example: -WithJira -JiraProject SAAP"
}

$appDir = Join-Path $RepoRoot "target-apps\$Feature"
$sqlDir = Join-Path $appDir "db\sql"
$pipelineAgentsRun = @()

function Convert-JsonObjectToHashtable {
    param($Node)
    $ht = @{}
    if ($null -eq $Node) { return $ht }
    if ($Node -is [hashtable]) { return $Node }
    if ($Node -is [PSCustomObject]) {
        $Node.PSObject.Properties | ForEach-Object {
            $value = $_.Value
            if ($value -is [PSCustomObject]) {
                $ht[$_.Name] = Convert-JsonObjectToHashtable $value
            }
            elseif ($value -is [System.Array]) {
                $ht[$_.Name] = @(
                    $value | ForEach-Object {
                        if ($_ -is [PSCustomObject]) { Convert-JsonObjectToHashtable $_ } else { $_ }
                    }
                )
            }
            else {
                $ht[$_.Name] = $value
            }
        }
    }
    return $ht
}

function Update-Context {
    param([hashtable] $Fields)
    $obj = @{}
    if (Test-Path $ctxPath) {
        $parsed = Get-Content $ctxPath -Raw | ConvertFrom-Json
        $obj = Convert-JsonObjectToHashtable $parsed
    }
    foreach ($k in $Fields.Keys) { $obj[$k] = $Fields[$k] }
    if (-not $obj["targetApp"]) { $obj["targetApp"] = $Feature }
    if (-not $obj["designDocPath"]) { $obj["designDocPath"] = "docs/design/$Feature.md" }
    # PS 5.1's Set-Content/Out-File -Encoding utf8 always emits a UTF-8 BOM (no
    # plain-utf8-no-BOM option exists on that encoding parameter in 5.1). A BOM
    # broke Python readers that parse this file with plain "utf-8" + json.loads
    # (json.JSONDecodeError on the BOM). $ctxPath is already absolute (built
    # from $RepoRoot via Join-Path at the top of this script), which
    # [System.IO.File]::WriteAllText requires.
    $json = $obj | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($ctxPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "[pipeline] Context -> agents/pipeline/$Feature.context.json" -ForegroundColor Cyan
}

function Sync-DeliveryProfile {
    param([string]$InputFileRel = "")
    $syncArgs = @(
        "agents/_shared/delivery_profile.py",
        "--context-file", $ContextFile,
        "--repo-root", $RepoRoot,
        "--sync"
    )
    if ($InputFileRel) {
        $syncArgs += @("--input-file", $InputFileRel)
    }
    if ((Invoke-PipelinePython -ArgumentList $syncArgs) -ne 0) { throw "deliveryProfile sync failed" }
}

function Invoke-DeliveryVerify {
    param([ValidateSet("design", "app")][string]$Stage)
    if (-not (Test-Path $ctxPath)) { return }
    if ((Invoke-PipelinePython -ArgumentList @(
        "agents/_shared/delivery_profile.py", "--context-file", $ContextFile, "--repo-root", $RepoRoot, "--check", $Stage, "--quiet"
    )) -ne 0) {
        throw "deliveryProfile check failed ($Stage). UI required by brief/PRD was dropped - fix design or developer output."
    }
}

function Sync-AuthMode {
    # Deterministic (not LLM) — derives authMode from designDocPath's Auth line(s) and
    # logs it so the value is visible on every run, regardless of entry point. Nothing
    # consumes authMode yet.
    if (-not (Test-Path $ctxPath)) { return }
    Invoke-PipelinePython -ArgumentList @(
        "agents/_shared/auth_profile.py", "--context-file", $ContextFile, "--repo-root", $RepoRoot, "--sync"
    ) | Out-Null
}

function Get-DeveloperStepLabel {
    param([string]$ContextPath = $ctxPath)
    $stack = @("FastAPI")
    if (Test-Path $ContextPath) {
        try {
            $dp = (Get-Content $ContextPath -Raw | ConvertFrom-Json).deliveryProfile
            if ($dp.requiresStreamlit) { $stack += "Streamlit" }
            if ($dp.requiresReact) { $stack += "React" }
        }
        catch { }
    }
    return "4/6 developer-agent ($($stack -join ' + '))"
}

function Invoke-RdsApply {
    if (-not (Test-Path $sqlDir)) {
        Write-Warning "No db/sql/ under target-apps/$Feature  - skip RDS apply."
        return
    }
    Write-Host "`n=== Apply SQL to RDS (apply_sql_to_rds.py) ===" -ForegroundColor Green
    if ((Invoke-PipelinePython -ArgumentList @("scripts/apply_sql_to_rds.py", "--target-app", $Feature, "--reset-schema")) -ne 0) {
        throw "RDS apply failed. Fix network/credentials (.env.local POSTGRES_MCP_*) then re-run: python scripts/apply_sql_to_rds.py --target-app $Feature"
    }
}

function Invoke-SeedMaterialize {
    param([string]$TargetFeature)
    Write-Host "`n=== Materialize seed passwords on RDS (materialize_seed_passwords.py) ===" -ForegroundColor Green
    if ((Invoke-PipelinePython -ArgumentList @(
        "agents/_shared/materialize_seed_passwords.py", "--target-app", $TargetFeature, "--repo-root", $RepoRoot
    )) -ne 0) {
        throw "Seed password materialization failed - check HANDOFF seedCredentials or seed SQL password comment."
    }
}

function Invoke-GenerateEnv {
    param([string]$TargetFeature)
    $targetDir = Join-Path $RepoRoot "target-apps\$TargetFeature"
    if (-not (Test-Path (Join-Path $targetDir ".env.example"))) { return }
    Write-Host "`n=== Generate .env from .env.example + .env.local (generate_target_app_env.py) ===" -ForegroundColor Green
    if ((Invoke-PipelinePython -ArgumentList @(
        "agents/_shared/generate_target_app_env.py", "--target-app", $TargetFeature
    )) -ne 0) {
        Write-Warning ".env generation failed - copy target-apps/$TargetFeature/.env.example to .env by hand."
    }
}

function Invoke-LocalVerify {
    param([string]$TargetFeature)
    $targetDir = Join-Path $RepoRoot "target-apps\$TargetFeature"
    if (-not (Test-Path $targetDir)) { return }

    $testsDir = Join-Path $targetDir "tests"
    if (-not (Test-Path $testsDir)) {
        Write-Host "  Local verify skipped (no tests/)" -ForegroundColor DarkGray
        Invoke-DeliveryVerify -Stage app
        return
    }

    $venvPython = Join-Path $targetDir ".venv\Scripts\python.exe"
    $python = if (Test-Path $venvPython) { $venvPython } else { "python" }
    # verify_seed_bcrypt.py is a SHARED repo tool (needs bcrypt from the repo venv),
    # never the app venv above - the app venv doesn't install repo-level deps.
    $repoVenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $repoPython = if (Test-Path $repoVenvPython) { $repoVenvPython } else { "python" }

    Push-Location $targetDir
    $prevDbUrl = $env:DATABASE_URL
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $prevNative = $null
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
        $prevNative = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    try {
        $env:DATABASE_URL = "sqlite://"
        $env:SKIP_STARTUP_CHECKS = "1"

        & $python -c "from app.main import app" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "app import failed - developer-agent must fix startup errors before pipeline continues."
        }

        # Pytest runs against a throwaway Postgres schema built from this app's
        # db/sql/*.sql (agents/_shared/pg_test_schema.py) - NOT SQLite. The app's
        # tests/conftest.py now requires a real Postgres DATABASE_URL and refuses
        # to fall back to SQLite (see target-apps/_template/tests/conftest_reference.py),
        # since SQLite silently accepted values a real Postgres native enum would
        # reject, hiding ORM-vs-DDL drift. run_app_tests_pg.py runs on the REPO venv
        # (it imports _shared/apply_sql_to_rds), unlike $python above; it guarantees
        # the temp schema is dropped even if pytest fails or crashes.
        # Absolute path required here: this try block runs inside a Push-Location
        # $targetDir (see above), so the relative "scripts/..." path Invoke-RdsApply
        # uses (called at $RepoRoot scope, before any Push-Location) would resolve
        # against target-apps/<app>/ instead of backend/ and silently fail to find
        # the script — same reason the verify_seed_bcrypt.py calls above use
        # Join-Path $RepoRoot rather than a bare relative path.
        $runTestsScript = Join-Path $RepoRoot "scripts\run_app_tests_pg.py"
        if ((Invoke-PipelinePython -ArgumentList @($runTestsScript, "--target-app", $TargetFeature)) -ne 0) {
            throw "pytest failed - developer-agent must fix tests before pipeline continues."
        }

        & $repoPython (Join-Path $RepoRoot "agents\_shared\verify_seed_bcrypt.py") --target-app $TargetFeature --repo-root $RepoRoot --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Seed bcrypt verification failed - README login will fail on RDS even if pytest passes."
        }
        & $repoPython (Join-Path $RepoRoot "agents\_shared\verify_seed_bcrypt.py") --target-app $TargetFeature --repo-root $RepoRoot --check-rds --quiet
        if ($LASTEXITCODE -ne 0) {
            throw "RDS seed password mismatch - re-run apply_sql_to_rds.py (auto-materializes passwords)."
        }

        Write-Host "  Local verify passed (import smoke, pytest vs. Postgres temp schema, seed bcrypt, delivery profile)." -ForegroundColor Green
    }
    finally {
        $ErrorActionPreference = $prevEap
        if ($null -ne $prevNative) {
            $PSNativeCommandUseErrorActionPreference = $prevNative
        }
        if ($null -eq $prevDbUrl) {
            Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
        } else {
            $env:DATABASE_URL = $prevDbUrl
        }
        Remove-Item Env:SKIP_STARTUP_CHECKS -ErrorAction SilentlyContinue
        Pop-Location
    }

    Invoke-DeliveryVerify -Stage app
}

function Write-PublishHandoffLinks {
    param(
        [string]$Label,
        [object]$Handoff
    )
    if (-not $Handoff) { return }
    $repoUrl = [string]$Handoff.repoUrl
    $branchUrl = [string]$Handoff.branchUrl
    $prUrl = ""
    if ($Handoff.PSObject.Properties.Name -contains "mergeRequestUrl" -and $Handoff.mergeRequestUrl) {
        $prUrl = [string]$Handoff.mergeRequestUrl
    }
    if ($repoUrl) { Write-Host "  $Label repo:   $repoUrl" -ForegroundColor Green }
    if ($branchUrl) { Write-Host "  $Label branch: $branchUrl" -ForegroundColor Green }
    if ($prUrl) { Write-Host "  $Label PR/MR:  $prUrl" -ForegroundColor Green }
}

function Write-RunInstructions {
    param([string]$TargetFeature, [bool]$UsesDb)
    Write-Host "`n=== Run the app (manual) ===" -ForegroundColor Cyan
    Write-Host "  cd target-apps/$TargetFeature"
    if (-not (Test-Path (Join-Path $appDir ".venv"))) {
        Write-Host "  python -m venv .venv"
        Write-Host "  .\.venv\Scripts\Activate.ps1"
        Write-Host "  pip install -r requirements.txt"
    }
    if ($UsesDb) {
        Write-Host "  .env already generated (target-apps/$TargetFeature/.env) - edit only if you need to override it"
        Write-Host "  RDS smoke: GET /health then one DB list/read route (pytest SQLite != RDS proof)"
    }
    Write-Host "  uvicorn app.main:app --reload --port 8000"
    Write-Host "  Open http://127.0.0.1:8000/docs  - auth per README (JWT Bearer or API key per app)"
    if (Test-Path $ctxPath) {
        try {
            $ctxObj = Get-Content $ctxPath -Raw | ConvertFrom-Json
            if ($ctxObj.deliveryProfile.requiresStreamlit) {
                Write-Host "  pip install -r ui/requirements.txt"
                Write-Host "  streamlit run ui/streamlit_app.py --server.port 8501   # Terminal 2"
            }
        } catch { }
    }
}

$devTaskDb = @"
Implement API surface from designDocPath as FastAPI routes. dev_read_file databaseHandoffPath and every db/sql/*.sql before models.
Postgres parity (mandatory): psycopg[binary] + postgresql+psycopg:// in .env.example with ?sslmode=require; dialect-guarded database.py;
ENUM columns use sqlalchemy.Enum(create_type=False, native_enum=True) with sqlite String variant;
uuid columns use PG_UUID(as_uuid=False).with_variant(String(36), sqlite); Pydantic response schemas coerce UUID to str.
Auth per design Rules only (API-key and/or JWT+bcrypt  - not both unless design requires).
If deliveryProfile.requiresStreamlit is true: Pattern C mandatory - ui/streamlit_app.py + ui/requirements.txt;
login via API; JWT in st.session_state or API_KEY header per auth mode; role-based tabs per PRD; README Terminal 1+2.
tests/conftest.py: SQLite with schema ATTACH when models use POSTGRES_SCHEMA.
When db/sql/*seed*.sql has JWT users: add tests/test_seed_bcrypt.py (from _template/tests/test_seed_bcrypt_reference.py); conftest password must match seed SQL comment.
README: Windows+bash setup, .env copy, uvicorn, Swagger auth header, seed UUIDs, RDS smoke-test steps (GET /health + one DB list route).
When multiple roles or /portal vs /internal: README must include Role & endpoint quick reference (example seed username per route).
Baseline pytest must pass.
"@.Trim()

$devTaskNoDb = @"
Implement API surface and rules from designDocPath as FastAPI routes, Pydantic schemas, and baseline pytest. README with how to run uvicorn and open /docs.
"@.Trim()

# 1) Product -> PRD [+ optional Jira backlog]
if (-not $SkipProduct) {
    if (-not $InputFile) { throw "Pass -InputFile for product-agent, or use -SkipProduct." }
    $stepLabel = if ($WithJira) { "1/6 product-agent (PRD + Jira)" } else { "1/6 product-agent (PRD)" }
    Write-Host "`n=== $stepLabel ===" -ForegroundColor Green
    $productArgs = @(
        "agents/product-agent/product_agent.py",
        "--input-file", $InputFile,
        "--prd-name", $Feature
    )
    if ($WithJira) {
        $productArgs += @("--create-jira-tickets", "--allow-writes", "--project", $JiraProject)
        if ($JiraSprint -gt 0) { $productArgs += @("--sprint", $JiraSprint) }
        if ($JiraStoryTitleStyle) { $productArgs += @("--story-title-style", $JiraStoryTitleStyle) }
        Write-Host "  Jira: Epic + 5 user stories -> project $JiraProject" -ForegroundColor DarkGray
    }
    if ((Invoke-PipelinePython -ArgumentList $productArgs) -ne 0) { throw "product-agent failed" }
    $pipelineAgentsRun += "product-agent"
    if (-not (Test-Path "docs/PRD/$Feature.md")) { throw "PRD not found: docs/PRD/$Feature.md" }
    Write-Host "[pipeline] PRD -> docs/PRD/$Feature.md" -ForegroundColor Cyan
    $ctxFields = @{
        prdPath            = "docs/PRD/$Feature.md"
        productAgentOutput = "See prdPath for $Feature MVP requirements."
    }
    if ($WithJira) {
        $ctxFields.jiraProjectKey = $JiraProject
        $ctxFields.jiraBacklogCreated = $true
    }
    Update-Context $ctxFields
}
else {
    Update-Context @{ prdPath = "docs/PRD/$Feature.md" }
}

if ($InputFile) {
    Sync-DeliveryProfile -InputFileRel ($InputFile -replace '\\', '/')
}
elseif (Test-Path $ctxPath) {
    Sync-DeliveryProfile
}

# 2) Architect -> PNG + design.md
if (-not $SkipArchitect) {
    Write-Host "`n=== 2/6 architect-agent (diagram + design.md) ===" -ForegroundColor Green
    if ((Invoke-PipelinePython -ArgumentList @(
        "agents/architect-agent/architect_agent.py",
        "--diagram-name", $Feature,
        "--context-file", $ContextFile,
        "--task", "$Feature MVP"
    )) -ne 0) { throw "architect-agent failed" }
    $pipelineAgentsRun += "architect-agent"
    $png = "docs/generated-diagrams/$Feature.png"
    if (-not (Test-Path $png)) { Write-Warning "Diagram missing: $png" }
    $designRel = "docs/design/$Feature.md"
    if (-not (Test-Path $designRel)) { throw "design doc not found: $designRel" }
    Update-Context @{ diagramPaths = @($png); designDocPath = $designRel }
    Invoke-DeliveryVerify -Stage design
}
else {
    Update-Context @{ diagramPaths = @("docs/generated-diagrams/$Feature.png") }
}
Sync-AuthMode

# 2b) Web crawler (optional)
$runWebCrawler = $WithWebCrawler -and -not $SkipWebCrawler
if ($runWebCrawler) {
    Write-Host "`n=== 2b/6 web-crawler-agent ===" -ForegroundColor Green
    if ((Invoke-PipelinePython -ArgumentList @(
        "agents/web-crawler/web_crawler_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile,
        "--with-postgres",
        "--task", "Scrape URLs from context scrapeUrls or requirements; persist markdown and Postgres rows."
    )) -ne 0) { throw "web-crawler-agent failed" }
    Update-Context @{
        webScrapeCompleted = $true
        scrapedOutputDir     = "docs/PRD/scraped/$Feature"
    }
}

# 3) Database -> target-apps/<feature>/db/
if (-not $SkipDb) {
    Write-Host "`n=== 3/6 database-agent (SQL migrations + seed) ===" -ForegroundColor Green
    $dbArgs = @(
        "agents/database-agent/database_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile,
        "--task", "Implement data model from designDocPath sections 3/6: numbered sql/ migrations, ### seedCredentials in the database handoff doc, stable UUIDs. JWT apps only: __BCRYPT_PLACEHOLDER__ in hashed_password plus documented password comment. Opaque token/API-key apps: do NOT put __BCRYPT_PLACEHOLDER__ in token_hash/key_hash; use distinct sha256 placeholder strings per row (see database-agent api_keys rule)."
    )
    if ($applyPostgres) { $dbArgs += "--with-postgres" }
    if ((Invoke-PipelinePython -ArgumentList $dbArgs) -ne 0) { throw "database-agent failed" }
    $pipelineAgentsRun += "database-agent"

    # Explicit RDS apply (idempotent)  - ensures schema exists even if agent apply was skipped
    if ($applyPostgres) {
        Invoke-RdsApply
        Invoke-SeedMaterialize -TargetFeature $Feature
        Write-Host "`n=== Verify seed bcrypt (SQL + RDS) ===" -ForegroundColor Green
        if ((Invoke-PipelinePython -ArgumentList @(
            "agents/_shared/verify_seed_bcrypt.py", "--target-app", $Feature, "--repo-root", $RepoRoot, "--quiet"
        )) -ne 0) {
            throw "Seed bcrypt verification failed - placeholder password hashes will break RDS login."
        }
        if ((Invoke-PipelinePython -ArgumentList @(
            "agents/_shared/verify_seed_bcrypt.py", "--target-app", $Feature, "--repo-root", $RepoRoot, "--check-rds", "--quiet"
        )) -ne 0) {
            throw "RDS seed password verification failed - Swagger/Streamlit login will 401."
        }
        Write-Host "  seed bcrypt OK (SQL files + RDS)" -ForegroundColor Green
    }
}

# 4) Developer -> target-apps/<feature>/
if (-not $SkipDeveloper) {
    Write-Host "`n=== $(Get-DeveloperStepLabel) ===" -ForegroundColor Green
    $task = if ($SkipDb) { $devTaskNoDb } else { $devTaskDb }
    if ((Invoke-PipelinePython -ArgumentList @(
        "agents/developer-agent/developer_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile,
        "--task", $task
    )) -ne 0) { throw "developer-agent failed" }
    $pipelineAgentsRun += "developer-agent"
}
Invoke-GenerateEnv -TargetFeature $Feature

# 5) Local verify (before publish - do not push broken code)
if (-not $SkipVerify) {
    Invoke-LocalVerify -TargetFeature $Feature
}

# 5b) Frontend-agent -> React frontend from OpenAPI contract (runs by default; -SkipFrontend to disable).
# Mirrors sdlc_pipeline _step_frontend (local transport): passes --full-regen for a clean from-scratch build.
# Skip when deliveryProfile explicitly chose a non-React UI (e.g. Streamlit) or API-only -
# mirrors sdlc_pipeline._frontend_required(); absent/unknown profile still defaults to required.
$frontendRequired = $true
if (Test-Path $ctxPath) {
    try {
        $dp = (Get-Content $ctxPath -Raw | ConvertFrom-Json).deliveryProfile
        if ($null -ne $dp.requiresReact) { $frontendRequired = [bool]$dp.requiresReact }
    } catch { }
}
if ($runFrontend -and -not $frontendRequired) {
    Write-Host "`n=== 5b/6 frontend-agent skipped - deliveryProfile does not require a React frontend ===" -ForegroundColor Yellow
    $runFrontend = $false
}
if ($runFrontend) {
    Write-Host "`n=== 5b/6 frontend-agent (React from OpenAPI contract) ===" -ForegroundColor Green
    $frontendArgs = @(
        "agents/frontend-agent/frontend_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile,
        "--full-regen"
    )
    if ((Invoke-PipelinePython -ArgumentList $frontendArgs) -ne 0) {
        throw "frontend-agent failed - refusing to publish a broken frontend to GitLab. Fix target-apps/$Feature/frontend or re-run with -SkipFrontend only if intentional."
    }
    $pipelineAgentsRun += "frontend-agent"
}

# 6) GitLab-agent -> MCP push to sdlc/<app> branch (default publish; MR opt-in via gitlab-agent --open-mr)
if ($runGitlab) {
    Write-Host "`n=== 6/6 gitlab-agent (MCP publish to sdlc/<app> branch) ===" -ForegroundColor Green
    $gitlabArgs = @(
        "agents/gitlab-agent/gitlab_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile
    )
    if ($GitlabProject) { $gitlabArgs += @("--gitlab-project", $GitlabProject) }
    if ($GitlabBase) { $gitlabArgs += @("--gitlab-base", $GitlabBase) }
    if ((Invoke-PipelinePython -ArgumentList $gitlabArgs) -ne 0) { Write-Warning "gitlab-agent reported issues - review before merge." }
    $gitlabHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.gitlab-handoff.json"
    if (Test-Path $gitlabHandoff) {
        $gitlabJson = Get-Content $gitlabHandoff -Raw | ConvertFrom-Json
        Update-Context @{
            mergeRequestIid   = $gitlabJson.mergeRequestIid
            mergeRequestUrl   = $gitlabJson.mergeRequestUrl
            gitlabProject     = $gitlabJson.gitlabProject
            featureBranch     = $gitlabJson.branch
        }
    }
}

# 7) DevOps-agent -> Terraform root + ECS Fargate deploy (opt-in via -WithDeploy)
if ($runDeploy) {
    $deployMode = if ($DeployPlanOnly) { "terraform plan only" } else { "build + deploy to ECS" }
    Write-Host "`n=== 7/7 devops-agent ($deployMode) ===" -ForegroundColor Green
    $devopsArgs = @(
        "agents/devops-agent/devops_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile
    )
    if ($DeployPlanOnly) { $devopsArgs += "--plan-only" } else { $devopsArgs += "--deploy" }
    if ((Invoke-PipelinePython -ArgumentList $devopsArgs) -ne 0) {
        Write-Warning "devops-agent reported issues - app may not be live (see agents/pipeline/$Feature.devops-handoff.json)."
    }
    $devopsHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.devops-handoff.json"
    if (Test-Path $devopsHandoff) {
        $devopsJson = Get-Content $devopsHandoff -Raw | ConvertFrom-Json
        if ($devopsJson.appUrl) {
            Update-Context @{
                deployUrl  = $devopsJson.appUrl
                ecsService = $devopsJson.ecsService
            }
        }
    }
}

# QA -> pytest (opt-in via -WithQa)
if ($runQa) {
    Write-Host "`n=== qa-agent (pytest) ===" -ForegroundColor Green
    if ((Invoke-PipelinePython -ArgumentList @(
        "agents/qa-agent/qa_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile
    )) -ne 0) { Write-Warning "qa-agent reported issues - review before shipping." }
}

Write-Host "`n[pipeline] Done. Artifacts:" -ForegroundColor Cyan
Write-Host "  PRD:     docs/PRD/$Feature.md"
if ($WithJira) { Write-Host "  Jira:    Epic + stories in project $JiraProject (see product-agent output for keys)" }
Write-Host "  Design:  docs/design/$Feature.md"
Write-Host "  Diagram: docs/generated-diagrams/$Feature.png"
if (-not $SkipDb) {
    Write-Host "  DB:      target-apps/$Feature/db/"
    if ($applyPostgres) { Write-Host "  RDS:     applied via apply_sql_to_rds.py" }
}
Write-Host "  App:     target-apps/$Feature/"
if ($runGitlab) {
    $gitlabHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.gitlab-handoff.json"
    if (Test-Path $gitlabHandoff) {
        Write-Host "  GitLab:  agents/pipeline/$Feature.gitlab-handoff.json"
        Write-PublishHandoffLinks -Label "GitLab" -Handoff (Get-Content $gitlabHandoff -Raw | ConvertFrom-Json)
    } else {
        Write-Host "  GitLab:  publish failed (no handoff file - retry gitlab-agent when online)" -ForegroundColor Yellow
    }
}
if ($runQa) { Write-Host "  QA:      agents/pipeline/$Feature.qa-handoff.json" }

$deployUrl = $null
if ($runDeploy) {
    $devopsHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.devops-handoff.json"
    if (Test-Path $devopsHandoff) {
        Write-Host "  Deploy:  agents/pipeline/$Feature.devops-handoff.json"
        try { $deployUrl = (Get-Content $devopsHandoff -Raw | ConvertFrom-Json).appUrl } catch {}
    } elseif ($DeployPlanOnly) {
        Write-Host "  Deploy:  terraform plan only (no AWS changes)" -ForegroundColor DarkGray
    } else {
        Write-Host "  Deploy:  no handoff file - deploy may have failed" -ForegroundColor Yellow
    }
}

if ($pipelineAgentsRun.Count -gt 0) {
    Write-Host "`n=== Pipeline token usage ===" -ForegroundColor Cyan
    $telemetryArgs = @(
        "agents/_shared/pipeline_telemetry.py",
        "--target-app", $Feature,
        "--agents-run", ($pipelineAgentsRun -join ",")
    )
    Invoke-PipelinePython -ArgumentList $telemetryArgs | Out-Null
}

Write-RunInstructions -TargetFeature $Feature -UsesDb:(-not $SkipDb)

# Live URL last — primary thing to open when testing devops deploy.
if ($runDeploy) {
    if ($deployUrl) {
        Write-Host "`n=== Live app (devops) ===" -ForegroundColor Green
        Write-Host "  $deployUrl" -ForegroundColor Yellow
        Write-Host "  Open this URL to verify the deployed app." -ForegroundColor DarkGray
    } elseif (-not $DeployPlanOnly) {
        Write-Host "`n=== Live app (devops) ===" -ForegroundColor Yellow
        Write-Host "  No appUrl in devops handoff - deploy may have failed." -ForegroundColor Yellow
        Write-Host "  Check agents/pipeline/$Feature.devops-handoff.json" -ForegroundColor DarkGray
    }
}
