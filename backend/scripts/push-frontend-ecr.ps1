# Build and push control-plane frontend image to ECR.
#
# Usage (from monorepo root or backend/):
#   .\scripts\push-frontend-ecr.ps1
#   .\scripts\push-frontend-ecr.ps1 -SkipBuild

param(
    [string] $Region = "us-east-2",
    [string] $Profile = "Juno Developers",
    [string] $AccountId = "061836593297",
    [string] $Repository = "sdlc-control-plane",
    [string] $Tag = "latest",
    [switch] $SkipCreateRepo,
    [switch] $SkipBuild
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile
$BackendRoot = Split-Path $PSScriptRoot -Parent
$MonorepoRoot = Split-Path $BackendRoot -Parent
$ImageUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/${Repository}:$Tag"

if (-not $SkipCreateRepo) {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    aws ecr describe-repositories --repository-names $Repository --region $Region --profile $Profile 2>$null | Out-Null
    $repoExists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    if (-not $repoExists) {
        Write-Host "Creating ECR repository $Repository ..." -ForegroundColor Cyan
        aws ecr create-repository --repository-name $Repository --region $Region --profile $Profile | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "ecr create-repository failed" }
    }
}

aws ecr get-login-password --region $Region --profile $Profile |
    docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

if (-not $SkipBuild) {
    Write-Host "Building $ImageUri ..." -ForegroundColor Cyan
    docker build -f (Join-Path $MonorepoRoot "frontend\Dockerfile") -t $ImageUri (Join-Path $MonorepoRoot ".")
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
}

Write-Host "Pushing $ImageUri ..." -ForegroundColor Cyan
docker push $ImageUri
if ($LASTEXITCODE -ne 0) { throw "docker push failed" }

Write-Host "Done: $ImageUri" -ForegroundColor Green
