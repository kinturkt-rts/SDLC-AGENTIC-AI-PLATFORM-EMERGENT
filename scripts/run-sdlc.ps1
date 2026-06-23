# Full SDLC chain (default): brief -> PRD -> design -> db -> apply RDS -> developer -> verify
# Optional publish: -WithGitlab (GitLab MR) or -WithGithub (GitHub showcase PR). No QA in Phase 1 MVP.
#
# DEFAULT (Postgres app, full chain):
#   .\scripts\run-sdlc.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt
#
# Opt-in extras:
#   -WithGitlab                          # gitlab-agent: MCP push + MR to GitLab origin
#   -GitlabProject / -GitlabBase         # override GITLAB_PROJECT_PATH / GITLAB_BASE_BRANCH
#   -WithGithub                          # github-agent: MCP push + PR to showcase repo
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
    [switch] $WithGitlab,
    [string] $GithubOwner = "",
    [string] $GithubRepo = "",
    [string] $GithubBase = "",
    [string] $GitlabProject = "",
    [string] $GitlabBase = "",
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

function Resolve-GithubConfigFromEnv {
    param(
        [string] $OwnerArg,
        [string] $RepoArg,
        [string] $BaseArg
    )
    $ownerPy = if ($OwnerArg) { "'$($OwnerArg.Replace("'", "''"))'" } else { "None" }
    $repoPy = if ($RepoArg) { "'$($RepoArg.Replace("'", "''"))'" } else { "None" }
    $basePy = if ($BaseArg) { "'$($BaseArg.Replace("'", "''"))'" } else { "None" }
    $agentsPath = Join-Path $RepoRoot "agents"
    $pyScript = @"
import json, sys
sys.path.insert(0, r'$agentsPath')
from _shared.env import load_repo_env
from _shared.github_mcp_publish import github_repo_config
load_repo_env()
cfg = github_repo_config(owner=$ownerPy, repo=$repoPy, base_branch=$basePy)
token = ''
for key in ('GITHUB_PERSONAL_ACCESS_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN'):
    token = (__import__('os').environ.get(key) or '').strip()
    if token:
        break
print(json.dumps({'owner': cfg['owner'], 'repo': cfg['repo'], 'base': cfg['base'], 'hasToken': bool(token)}))
"@
    $json = python -c $pyScript
    if ($LASTEXITCODE -ne 0) { throw "Failed to resolve GitHub config from .env" }
    return ($json | ConvertFrom-Json)
}

$ctxPath = Join-Path $RepoRoot ($ContextFile -replace "/", "\")
$ctxDir = Split-Path $ctxPath -Parent
if (-not (Test-Path $ctxDir)) { New-Item -ItemType Directory -Path $ctxDir -Force | Out-Null }

# Full chain defaults: RDS apply when DB runs; QA only when -WithQa (Phase 3)
$applyPostgres = (-not $SkipDb) -and (-not $SkipPostgres)
$runQa = $false
if ($WithQa) { $runQa = (-not $SkipDeveloper) -and (-not $SkipQa) }
$runGithub = $WithGithub -and (-not $SkipDeveloper)
$runGitlab = $WithGitlab -and (-not $SkipDeveloper)
if ($WithPostgres) { $applyPostgres = $true }
if ($WithQa) { $runQa = $true }

if ($WithJira -and $SkipProduct) {
    throw "-WithJira requires the product step (do not use -SkipProduct). Re-run product-agent manually with --create-jira-tickets if PRD already exists."
}
if ($WithGithub) {
    $githubCfg = Resolve-GithubConfigFromEnv -OwnerArg $GithubOwner -RepoArg $GithubRepo -BaseArg $GithubBase
    if (-not $GithubOwner) { $GithubOwner = $githubCfg.owner }
    if (-not $GithubRepo) { $GithubRepo = $githubCfg.repo }
    if (-not $GithubBase) { $GithubBase = $githubCfg.base }
    if (-not $githubCfg.hasToken) {
        throw "-WithGithub requires GITHUB_PERSONAL_ACCESS_TOKEN in .env (or GITHUB_TOKEN / GH_TOKEN)"
    }
    Write-Host "[pipeline] GitHub target: $GithubOwner/$GithubRepo (base: $GithubBase)" -ForegroundColor Cyan
}
if ($WithGitlab -and (-not $env:GITLAB_PERSONAL_ACCESS_TOKEN)) {
    throw "-WithGitlab requires GITLAB_PERSONAL_ACCESS_TOKEN in .env"
}
if ($WithGitlab -and (-not $GitlabProject) -and (-not $env:GITLAB_PROJECT_PATH)) {
    throw "-WithGitlab requires -GitlabProject or GITLAB_PROJECT_PATH in .env"
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
        throw "deliveryProfile check failed ($Stage). UI required by brief/PRD was dropped - fix design or developer output."
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

function Invoke-SeedMaterialize {
    param([string]$TargetFeature)
    Write-Host "`n=== Materialize seed passwords on RDS (materialize_seed_passwords.py) ===" -ForegroundColor Green
    python agents/_shared/materialize_seed_passwords.py --target-app $TargetFeature --repo-root $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Seed password materialization failed - check HANDOFF seedCredentials or seed SQL password comment."
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
                throw "app import failed - developer-agent must fix startup errors before pipeline continues."
            }

            Write-Host "  pytest tests/ -q" -ForegroundColor DarkGray
            & $python -m pytest tests/ -q --tb=line
            if ($LASTEXITCODE -ne 0) {
                throw "pytest failed - developer-agent must fix tests before pipeline continues."
            }

            Write-Host "  seed bcrypt verify (SQL files)" -ForegroundColor DarkGray
            & $python (Join-Path $RepoRoot "agents\_shared\verify_seed_bcrypt.py") --target-app $TargetFeature --repo-root $RepoRoot
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Seed bcrypt verification failed - README login will fail on RDS even if pytest passes."
            }
            Write-Host "  seed bcrypt verify (RDS stored hash)" -ForegroundColor DarkGray
            & $python (Join-Path $RepoRoot "agents\_shared\verify_seed_bcrypt.py") --target-app $TargetFeature --repo-root $RepoRoot --check-rds
            if ($LASTEXITCODE -ne 0) {
                throw "RDS seed password mismatch - re-run apply_sql_to_rds.py (auto-materializes passwords)."
            }

            Write-Host "  RDS + UI parity (TIMESTAMPTZ, seed parse, Streamlit list GETs)" -ForegroundColor DarkGray
            & $python (Join-Path $RepoRoot "scripts\verify_app_parity.py") --target-app $TargetFeature --repo-root $RepoRoot
            if ($LASTEXITCODE -ne 0) {
                throw "parity check failed - fix RDS_PARITY / UI_PARITY (see dev_validate_app hints) before pipeline continues."
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
        "--task", "Implement data model from designDocPath §3/§6: numbered sql/ migrations, dev seed with __BCRYPT_PLACEHOLDER__ for password_hash columns, documented password in SQL comment, ### seedCredentials table in HANDOFF.md, stable UUIDs."
    )
    if ($applyPostgres) { $dbArgs += "--with-postgres" }
    python @dbArgs
    if ($LASTEXITCODE -ne 0) { throw "database-agent failed" }

    # Explicit RDS apply (idempotent)  - ensures schema exists even if agent apply was skipped
    if ($applyPostgres) {
        Invoke-RdsApply
        Invoke-SeedMaterialize -TargetFeature $Feature
        Write-Host "`n=== Verify seed bcrypt hashes (SQL files) ===" -ForegroundColor Green
        python agents/_shared/verify_seed_bcrypt.py --target-app $Feature --repo-root $RepoRoot
        if ($LASTEXITCODE -ne 0) {
            throw "Seed bcrypt verification failed - placeholder password hashes will break RDS login."
        }
        Write-Host "`n=== Verify seed bcrypt on RDS ===" -ForegroundColor Green
        python agents/_shared/verify_seed_bcrypt.py --target-app $Feature --repo-root $RepoRoot --check-rds
        if ($LASTEXITCODE -ne 0) {
            throw "RDS seed password verification failed - Swagger/Streamlit login will 401."
        }
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

# 5) Local verify (before publish - do not push broken code)
if (-not $SkipVerify -and -not $SkipDeveloper) {
    Invoke-LocalVerify -TargetFeature $Feature
}

# 6) GitHub-agent -> MCP push + PR (showcase repo, one branch per app)
if ($runGithub) {
    Write-Host "`n=== 6/6 github-agent (MCP publish + PR) ===" -ForegroundColor Green
    $githubArgs = @(
        "agents/github-agent/github_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile
    )
    if ($GithubOwner) { $githubArgs += @("--github-owner", $GithubOwner) }
    if ($GithubRepo) { $githubArgs += @("--github-repo", $GithubRepo) }
    if ($GithubBase) { $githubArgs += @("--github-base", $GithubBase) }
    python @githubArgs
    if ($LASTEXITCODE -ne 0) { Write-Warning "github-agent reported issues - review before merge." }
    $githubHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.github-handoff.json"
    if (Test-Path $githubHandoff) {
        $githubJson = Get-Content $githubHandoff -Raw | ConvertFrom-Json
        Update-Context @{
            pullRequestNumber = $githubJson.pullRequestNumber
            pullRequestUrl    = $githubJson.pullRequestUrl
            githubOwner       = $githubJson.githubOwner
            githubRepo        = $githubJson.githubRepo
            featureBranch     = $githubJson.branch
        }
    }
}

# 6b) GitLab-agent -> MCP push to sdlc/<app> branch (MR opt-in via --open-mr)
if ($runGitlab) {
    Write-Host "`n=== gitlab-agent (MCP publish to sdlc/<app> branch) ===" -ForegroundColor Green
    $gitlabArgs = @(
        "agents/gitlab-agent/gitlab_agent.py",
        "--target-app", $Feature,
        "--context-file", $ContextFile
    )
    if ($GitlabProject) { $gitlabArgs += @("--gitlab-project", $GitlabProject) }
    if ($GitlabBase) { $gitlabArgs += @("--gitlab-base", $GitlabBase) }
    python @gitlabArgs
    if ($LASTEXITCODE -ne 0) { Write-Warning "gitlab-agent reported issues - review before merge." }
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

# 7) QA -> pytest (Phase 3 — opt-in via -WithQa)
if ($runQa) {
    Write-Host "`n=== qa-agent (pytest) ===" -ForegroundColor Green
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
if ($runGithub) {
    $githubHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.github-handoff.json"
    if (Test-Path $githubHandoff) {
        Write-Host "  GitHub:  agents/pipeline/$Feature.github-handoff.json"
    } else {
        Write-Host "  GitHub:  publish failed (no handoff file — retry github-agent when online)" -ForegroundColor Yellow
    }
}
if ($runGitlab) {
    $gitlabHandoff = Join-Path $RepoRoot "agents\pipeline\$Feature.gitlab-handoff.json"
    if (Test-Path $gitlabHandoff) {
        Write-Host "  GitLab:  agents/pipeline/$Feature.gitlab-handoff.json"
    } else {
        Write-Host "  GitLab:  publish failed (no handoff file — retry gitlab-agent when online)" -ForegroundColor Yellow
    }
}
if ($runQa) { Write-Host "  QA:      agents/pipeline/$Feature.qa-handoff.json" }

Write-RunInstructions -TargetFeature $Feature -UsesDb:(-not $SkipDb)
