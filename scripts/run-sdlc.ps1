# Full SDLC chain (default): brief -> PRD -> design -> db -> apply RDS -> developer -> verify
# Optional GitHub mirror: -WithGithub publishes branch + PR, then qa-agent tests and comments on PR.
# QA step disabled by default unless -WithQa or -WithGithub.
#
# DEFAULT (Postgres app, full chain):
#   .\scripts\run-sdlc.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt
#
# Opt-in extras:
#   -WithGithub                          # devops-agent: git push + PR; then qa-agent + PR review
#   -GithubOwner / -GithubRepo           # override GITHUB_OWNER / GITHUB_REPO from .env
#
#   -WithWebCrawler                      # scrape URLs into Postgres (optional step 2b)
#
# Opt-out (skip steps):
#   -SkipDb -SkipPostgres                 # no database-agent, no RDS apply
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
    [switch] $WithJira,
    [switch] $WithGithub,
    [string] $GithubOwner = "",
    [string] $GithubRepo = "",
    [string] $GithubBase = "",
    [string] $JiraProject = "",
    [int] $JiraSprint = 0,
    [ValidateSet("", "concise", "user-story")]
    [string] $JiraStoryTitleStyle = "",
    [switch] $WithPostgres,
    [switch] $WithQa
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$ctxPath = Join-Path $RepoRoot ($ContextFile -replace "/", "\")
$ctxDir = Split-Path $ctxPath -Parent
if (-not (Test-Path $ctxDir)) { New-Item -ItemType Directory -Path $ctxDir -Force | Out-Null }

# Full chain defaults: RDS apply when DB runs; QA when -WithQa or -WithGithub
$applyPostgres = (-not $SkipDb) -and (-not $SkipPostgres)
$runQa = $false
if ($WithQa -or $WithGithub) { $runQa = (-not $SkipDeveloper) -and (-not $SkipQa) }
$runDevops = $WithGithub -and (-not $SkipDeveloper)
if ($WithPostgres) { $applyPostgres = $true }
if ($WithQa) { $runQa = $true }

if ($WithJira -and $SkipProduct) {
    throw "-WithJira requires the product step (do not use -SkipProduct). Re-run product-agent manually with --create-jira-tickets if PRD already exists."
}
if ($WithGithub -and (-not $GithubOwner) -and (-not $env:GITHUB_OWNER)) {
    throw "-WithGithub requires -GithubOwner or GITHUB_OWNER in .env"
}
if ($WithGithub -and (-not $GithubRepo) -and (-not $env:GITHUB_REPO)) {
    throw "-WithGithub requires -GithubRepo or GITHUB_REPO in .env"
}

if ($WithJira -and -not $JiraProject) {
    throw "-WithJira requires -JiraProject <KEY> (e.g. SAAP). Example: -WithJira -JiraProject SAAP"
}

$appDir = Join-Path $RepoRoot "target-apps\$Feature"
$sqlDir = Join-Path $appDir "db\sql"

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
    $obj | ConvertTo-Json -Depth 5 | Set-Content $ctxPath -Encoding utf8
    Write-Host "[pipeline] Context -> $ctxPath" -ForegroundColor Cyan
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
    python @syncArgs
    if ($LASTEXITCODE -ne 0) { throw "deliveryProfile sync failed" }
}

function Invoke-DeliveryVerify {
    param([ValidateSet("design", "app")][string]$Stage)
    if (-not (Test-Path $ctxPath)) { return }
    Write-Host "`n=== Delivery profile verify ($Stage) ===" -ForegroundColor Green
    python agents/_shared/delivery_profile.py --context-file $ContextFile --repo-root $RepoRoot --check $Stage
    if ($LASTEXITCODE -ne 0) {
        throw "deliveryProfile check failed ($Stage). UI required by brief/PRD was dropped — fix design or developer output."
    }
}

function Invoke-RdsApply {
    if (-not (Test-Path $sqlDir)) {
        Write-Warning "No db/sql/ under target-apps/$Feature  - skip RDS apply."
        return
    }
    Write-Host "`n=== Apply SQL to RDS (apply_sql_to_rds.py) ===" -ForegroundColor Green
    python scripts/apply_sql_to_rds.py --target-app $Feature
    if ($LASTEXITCODE -ne 0) {
        throw "RDS apply failed. Fix network/credentials (.env.local POSTGRES_MCP_*) then re-run: python scripts/apply_sql_to_rds.py --target-app $Feature"
    }
}

function Invoke-LocalVerify {
    param([string]$TargetFeature)
    $targetDir = Join-Path $RepoRoot "target-apps\$TargetFeature"
    if (-not (Test-Path $targetDir)) { return }

    Write-Host "`n=== Local verify (env + pytest) ===" -ForegroundColor Green

    $envFile = Join-Path $targetDir ".env"
    $envExample = Join-Path $targetDir ".env.example"
    if (-not (Test-Path $envFile)) {
        if (Test-Path $envExample) {
            Write-Warning "Missing target-apps/$TargetFeature/.env  - copy .env.example and set DATABASE_URL, POSTGRES_SCHEMA, and auth secret (API_KEY or JWT_SECRET_KEY per design Rules)."
        }
    }

    $testsDir = Join-Path $targetDir "tests"
    if (-not (Test-Path $testsDir)) {
        Write-Host "  (no tests/  - skip pytest)" -ForegroundColor DarkGray
    }
    else {
        $venvPython = Join-Path $targetDir ".venv\Scripts\python.exe"
        $python = if (Test-Path $venvPython) { $venvPython } else { "python" }

        Push-Location $targetDir
        $prevDbUrl = $env:DATABASE_URL
        try {
            $env:DATABASE_URL = "sqlite://"
            $env:SKIP_STARTUP_CHECKS = "1"
            Write-Host "  import smoke: from app.main import app" -ForegroundColor DarkGray
            & $python -c "from app.main import app; print('  import OK')"
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "app import failed  - fix startup errors before pytest."
                return
            }

            Write-Host "  pytest tests/ -q" -ForegroundColor DarkGray
            & $python -m pytest tests/ -q --tb=line
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "pytest failed  - fix tests before manual Swagger testing."
            }
            else {
                Write-Host "  pytest OK" -ForegroundColor Green
            }
        }
        finally {
            # Restore previous DATABASE_URL to avoid polluting the shell session
            if ($null -eq $prevDbUrl) {
                Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
            } else {
                $env:DATABASE_URL = $prevDbUrl
            }
            Remove-Item Env:SKIP_STARTUP_CHECKS -ErrorAction SilentlyContinue
            Pop-Location
        }
    }

    Invoke-DeliveryVerify -Stage app
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
        Write-Host "  copy .env.example .env   # DATABASE_URL (?sslmode=require), POSTGRES_SCHEMA, auth secret"
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
Implement API surface from designDocPath as FastAPI routes. dev_read_file db/HANDOFF.md and every db/sql/*.sql before models.
Postgres parity (mandatory): psycopg[binary] + postgresql+psycopg:// in .env.example with ?sslmode=require; dialect-guarded database.py;
ENUM columns use sqlalchemy.Enum(create_type=False, native_enum=True) with sqlite String variant;
uuid columns use PG_UUID(as_uuid=False).with_variant(String(36), sqlite); Pydantic response schemas coerce UUID to str.
Auth per design Rules only (API-key and/or JWT+bcrypt  - not both unless design requires).
If deliveryProfile.requiresStreamlit is true: Pattern C mandatory — ui/streamlit_app.py + ui/requirements.txt;
login via API; JWT in st.session_state or API_KEY header per auth mode; role-based tabs per PRD; README Terminal 1+2.
tests/conftest.py: SQLite with schema ATTACH when models use POSTGRES_SCHEMA.
README: Windows+bash setup, .env copy, uvicorn, Swagger auth header, seed UUIDs, RDS smoke-test steps (GET /health + one DB list route).
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
    python @productArgs
    if (-not (Test-Path "docs/PRD/$Feature.md")) { throw "PRD not found: docs/PRD/$Feature.md" }
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
    python agents/architect-agent/architect_agent.py `
        --diagram-name $Feature `
        --context-file $ContextFile `
        --task "$Feature MVP"
    $png = "docs/diagrams/generated-diagrams/$Feature.png"
    if (-not (Test-Path $png)) { Write-Warning "Diagram missing: $png" }
    $designRel = "docs/design/$Feature.md"
    if (-not (Test-Path $designRel)) { throw "design doc not found: $designRel" }
    Update-Context @{ diagramPaths = @($png); designDocPath = $designRel }
    Invoke-DeliveryVerify -Stage design
}
else {
    Update-Context @{ diagramPaths = @("docs/diagrams/generated-diagrams/$Feature.png") }
}

# 2b) Web crawler (optional)
$runWebCrawler = $WithWebCrawler -and -not $SkipWebCrawler
if ($runWebCrawler) {
    Write-Host "`n=== 2b/6 web-crawler-agent ===" -ForegroundColor Green
    python agents/web-crawler/web_crawler_agent.py `
        --target-app $Feature `
        --context-file $ContextFile `
        --with-postgres `
        --task "Scrape URLs from context scrapeUrls or requirements; persist markdown and Postgres rows."
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
        "--task", "Implement data model from designDocPath §3/§6: numbered sql/ migrations, dev seed with real bcrypt hashes for any password columns (bcrypt library, cost 12), stable UUIDs, HANDOFF notes."
    )
    if ($applyPostgres) { $dbArgs += "--with-postgres" }
    python @dbArgs
    if ($LASTEXITCODE -ne 0) { throw "database-agent failed" }

    # Explicit RDS apply (idempotent)  - ensures schema exists even if agent apply was skipped
    if ($applyPostgres) {
        Invoke-RdsApply
    }
}

# 4) Developer -> target-apps/<feature>/
if (-not $SkipDeveloper) {
    Write-Host "`n=== 4/6 developer-agent (FastAPI) ===" -ForegroundColor Green
    $task = if ($SkipDb) { $devTaskNoDb } else { $devTaskDb }
    python agents/developer-agent/developer_agent.py `
        --target-app $Feature `
        --context-file $ContextFile `
        --task $task
    if ($LASTEXITCODE -ne 0) { throw "developer-agent failed" }
}

# 5) Local verify (before publish — do not push broken code)
if (-not $SkipVerify -and -not $SkipDeveloper) {
    Invoke-LocalVerify -TargetFeature $Feature
}

# 6) DevOps -> GitHub branch + PR (mirrors developer git push)
if ($runDevops) {
    Write-Host "`n=== 6/7 devops-agent (GitHub publish + PR) ===" -ForegroundColor Green
    $devopsArgs = @(
        "agents/devops-agent/devops_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile
    )
    if ($GithubOwner) { $devopsArgs += @("--github-owner", $GithubOwner) }
    if ($GithubRepo) { $devopsArgs += @("--github-repo", $GithubRepo) }
    if ($GithubBase) { $devopsArgs += @("--github-base", $GithubBase) }
    python @devopsArgs
    if ($LASTEXITCODE -ne 0) { Write-Warning "devops-agent reported issues - review before merge." }
    $devopsHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.devops-handoff.json"
    if (Test-Path $devopsHandoff) {
        $devopsJson = Get-Content $devopsHandoff -Raw | ConvertFrom-Json
        Update-Context @{
            pullRequestNumber = $devopsJson.pullRequestNumber
            pullRequestUrl    = $devopsJson.pullRequestUrl
            githubOwner         = $devopsJson.githubOwner
            githubRepo          = $devopsJson.githubRepo
            featureBranch       = $devopsJson.branch
        }
    }
}

# 7) QA -> pytest + edge-case tests + GitHub PR review
if ($runQa) {
    Write-Host "`n=== 7/7 qa-agent (pytest + PR review) ===" -ForegroundColor Green
    python agents/qa-agent/qa_agent.py `
        --target-app $Feature `
        --context-file $ContextFile
    if ($LASTEXITCODE -ne 0) { Write-Warning "qa-agent reported issues - review before shipping." }
}

Write-Host "`n[pipeline] Done. Artifacts:" -ForegroundColor Cyan
Write-Host "  PRD:     docs/PRD/$Feature.md"
if ($WithJira) { Write-Host "  Jira:    Epic + stories in project $JiraProject (see product-agent output for keys)" }
Write-Host "  Design:  docs/design/$Feature.md"
Write-Host "  Diagram: docs/diagrams/generated-diagrams/$Feature.png"
if (-not $SkipDb) {
    Write-Host "  DB:      target-apps/$Feature/db/"
    if ($applyPostgres) { Write-Host "  RDS:     applied via apply_sql_to_rds.py" }
}
Write-Host "  App:     target-apps/$Feature/"
if ($runDevops) { Write-Host "  DevOps:  agents/pipeline/$Feature.devops-handoff.json" }
if ($runQa) { Write-Host "  QA:      agents/pipeline/$Feature.qa-handoff.json" }

Write-RunInstructions -TargetFeature $Feature -UsesDb:(-not $SkipDb)
