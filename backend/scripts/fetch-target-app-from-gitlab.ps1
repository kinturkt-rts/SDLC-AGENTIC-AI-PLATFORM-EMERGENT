# Fetch a target-app published on GitLab (branch sdlc/<app>) into backend/target-apps/<app>,
# so devops-agent can deploy apps produced by CLOUD pipeline runs (nothing on local disk).
#
#   .\scripts\fetch-target-app-from-gitlab.ps1 -Feature team-faq-bot
#   .\scripts\fetch-target-app-from-gitlab.ps1 -Feature team-faq-bot -Branch sdlc/team-faq-bot -Force
#
# Also copies agents/pipeline/<app>.* handoff/context JSONs from the branch when present.
# Requires GITLAB_URL + GITLAB_PROJECT_PATH + GITLAB_PERSONAL_ACCESS_TOKEN (from .env/.env.local).

param(
    [Parameter(Mandatory = $true)] [string] $Feature,
    [string] $Branch = "",
    [switch] $Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$MonorepoRoot = Split-Path -Parent $RepoRoot

# Load GITLAB_* from .env/.env.local (process env wins)
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
        if ($name -and -not (Test-Path "env:$name")) { Set-Item -Path "env:$name" -Value $value }
    }
}

if (-not $Branch) { $Branch = "sdlc/$Feature" }
$gitlabUrl = if ($env:GITLAB_URL) { $env:GITLAB_URL.TrimEnd('/') } else { "https://code.junodev.net" }
$projectPath = $env:GITLAB_PROJECT_PATH
$token = $env:GITLAB_PERSONAL_ACCESS_TOKEN
if (-not $token) { $token = $env:GITLAB_TOKEN }
if (-not $projectPath) { throw "GITLAB_PROJECT_PATH is not set." }
if (-not $token) { throw "GITLAB_PERSONAL_ACCESS_TOKEN is not set." }

$targetDir = Join-Path $RepoRoot "target-apps\$Feature"
if ((Test-Path $targetDir) -and -not $Force) {
    throw "target-apps/$Feature already exists locally. Use -Force to overwrite from GitLab."
}

$host_ = ([Uri]$gitlabUrl).Host
$cloneUrl = "https://oauth2:$token@$host_/$projectPath.git"
$tempDir = Join-Path $env:TEMP "sdlc-fetch-$Feature-$(Get-Random)"

Write-Host "Fetching $projectPath@$Branch -> target-apps/$Feature" -ForegroundColor Cyan
try {
    git clone --depth 1 --branch $Branch --quiet $cloneUrl $tempDir
    if ($LASTEXITCODE -ne 0) { throw "git clone of branch '$Branch' failed (does the branch exist?)." }

    $srcApp = Join-Path $tempDir "target-apps\$Feature"
    if (-not (Test-Path $srcApp)) {
        throw "Branch '$Branch' has no target-apps/$Feature directory."
    }

    if (Test-Path $targetDir) { Remove-Item $targetDir -Recurse -Force }
    Copy-Item $srcApp -Destination $targetDir -Recurse
    $fileCount = (Get-ChildItem $targetDir -Recurse -File).Count
    Write-Host "  Copied target-apps/$Feature ($fileCount files)" -ForegroundColor Green

    # Pipeline context/handoffs (cloud runs publish these alongside the app)
    $srcPipeline = Join-Path $tempDir "agents\pipeline"
    $dstPipeline = Join-Path $RepoRoot "agents\pipeline"
    if (Test-Path $srcPipeline) {
        Get-ChildItem $srcPipeline -File -Filter "$Feature.*" | ForEach-Object {
            Copy-Item $_.FullName -Destination (Join-Path $dstPipeline $_.Name) -Force
            Write-Host "  Copied agents/pipeline/$($_.Name)" -ForegroundColor Green
        }
    }

    # Docs (PRD/design) are optional but useful for context enrichment
    foreach ($docRel in @("docs\PRD\$Feature.md", "docs\design\$Feature.md")) {
        $srcDoc = Join-Path $tempDir $docRel
        if (Test-Path $srcDoc) {
            $dstDoc = Join-Path $RepoRoot $docRel
            New-Item -ItemType Directory -Force -Path (Split-Path $dstDoc -Parent) | Out-Null
            Copy-Item $srcDoc -Destination $dstDoc -Force
            Write-Host "  Copied $docRel" -ForegroundColor Green
        }
    }
}
finally {
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host "`nFetched. Next:" -ForegroundColor Yellow
Write-Host "  python scripts/apply_sql_to_rds.py --target-app $Feature   # if the app has db/sql/"
Write-Host "  .\scripts\deploy-target-app.ps1 -Feature $Feature          # needs infrastructure/environments/dev/$Feature (devops-agent generates it)"
Write-Host "  python agents/devops-agent/devops_agent.py --target-app $Feature --deploy"
