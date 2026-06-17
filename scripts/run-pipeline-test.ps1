# Progressive SDLC pipeline tests (product → architect → [db] → apply RDS → developer → [qa] → verify)
# Usage from repo root:
#   .\scripts\run-pipeline-test.ps1 -Level easy       # test-dev, no DB
#   .\scripts\run-pipeline-test.ps1 -Level medium     # test-medium-app, no DB
#   .\scripts\run-pipeline-test.ps1 -Level db         # test-db, full DB chain
#   .\scripts\run-pipeline-test.ps1 -Level release-notes  # release-notes-bot, Streamlit + Bedrock + Postgres
#   .\scripts\run-pipeline-test.ps1 -Level standup        # standup-tracker, Streamlit + Bedrock + Postgres

param(
    [ValidateSet("easy", "medium", "db", "inventory", "release-notes", "standup")]
    [string] $Level = "medium",
    [switch] $SkipProduct,
    [switch] $SkipArchitect,
    [switch] $SkipDeveloper,
    [switch] $SkipQa,
    [switch] $SkipVerify,
    [switch] $WithJira,
    [string] $JiraProject = "",
    [int] $JiraSprint = 0,
    [ValidateSet("", "concise", "user-story")]
    [string] $JiraStoryTitleStyle = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$config = switch ($Level) {
    "easy"       { @{ Feature = "test-dev";        Input = "inputs/test_dev.txt";        SkipDb = $true } }
    "medium"     { @{ Feature = "test-medium-app"; Input = "inputs/test_medium_app.txt"; SkipDb = $true } }
    "db"         { @{ Feature = "test-db";         Input = "inputs/test_db.txt";         SkipDb = $false } }
    "inventory"      { @{ Feature = "inventory-app";      Input = "inputs/inventory-app.txt";      SkipDb = $false } }
    "release-notes"  { @{ Feature = "release-notes-bot"; Input = "inputs/release-notes-bot.txt"; SkipDb = $false } }
    "standup"        { @{ Feature = "standup-tracker";   Input = "inputs/standup-tracker.txt";   SkipDb = $false } }
}

$Feature = $config.Feature
$InputFile = $config.Input
$ContextFile = "agents/pipeline/$Feature.context.json"

Write-Host "`n=== Pipeline test: $Level ($Feature) ===" -ForegroundColor Magenta
Write-Host "Full chain defaults: RDS apply + QA + pytest when DB is included." -ForegroundColor DarkGray

$sdlcParams = @{
    Feature     = $Feature
    InputFile   = $InputFile
    ContextFile = $ContextFile
}
if ($SkipProduct)   { $sdlcParams.SkipProduct = $true }
if ($SkipArchitect) { $sdlcParams.SkipArchitect = $true }
if ($config.SkipDb) {
    $sdlcParams.SkipDb = $true
    $sdlcParams.SkipPostgres = $true
}
if ($SkipDeveloper) { $sdlcParams.SkipDeveloper = $true }
if ($SkipQa)        { $sdlcParams.SkipQa = $true }
if ($SkipVerify)    { $sdlcParams.SkipVerify = $true }
if ($WithJira) {
    if (-not $JiraProject) {
        throw "-WithJira requires -JiraProject <KEY> (e.g. SAAP). Example: .\scripts\run-pipeline-test.ps1 -Level inventory -WithJira -JiraProject SAAP"
    }
    $sdlcParams.WithJira = $true
    $sdlcParams.JiraProject = $JiraProject
    if ($JiraSprint -gt 0) { $sdlcParams.JiraSprint = $JiraSprint }
    if ($JiraStoryTitleStyle) { $sdlcParams.JiraStoryTitleStyle = $JiraStoryTitleStyle }
}

& "$PSScriptRoot\run-sdlc.ps1" @sdlcParams
