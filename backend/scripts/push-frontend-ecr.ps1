# Build and push control-plane frontend image to ECR (redeploy only).
#
# Existing repo: 061836593297.dkr.ecr.us-east-2.amazonaws.com/sdlc-control-plane
#
# Usage (from backend/):
#   aws sso login --profile eks-admin-user
#   .\scripts\push-frontend-ecr.ps1
#   .\scripts\push-frontend-ecr.ps1 -SkipBuild
#
# Then roll out:
#   aws ecs update-service --cluster sdlc-agentic-ai --service sdlc-control-plane `
#     --force-new-deployment --region us-east-2 --profile eks-admin-user

param(
    [string] $Region = "us-east-2",
    [string] $Profile = "eks-admin-user",
    [string] $AccountId = "061836593297",
    [string] $Repository = "sdlc-control-plane",
    [string] $Tag = "latest",
    [switch] $SkipBuild
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile
$BackendRoot = Split-Path $PSScriptRoot -Parent
$MonorepoRoot = Split-Path $BackendRoot -Parent
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$ImageUri = "$Registry/${Repository}:$Tag"

Write-Host "Verifying ECR repository $Repository ..." -ForegroundColor Cyan
$repo = aws ecr describe-repositories `
    --repository-names $Repository `
    --region $Region `
    --profile $Profile `
    --query "repositories[0].repositoryUri" `
    --output text
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repo)) {
    throw "ECR repository '$Repository' not found in $Region (profile: $Profile). Create it once via deploy-frontend-ecs.ps1 or the AWS console."
}
Write-Host "Using $repo" -ForegroundColor DarkGray

if ($IsLinux -or $IsMacOS) {
    aws ecr get-login-password --region $Region --profile $Profile |
        docker login --username AWS --password-stdin $Registry
} else {
    cmd /c "aws ecr get-login-password --region $Region --profile $Profile | docker login --username AWS --password-stdin $Registry"
}
if ($LASTEXITCODE -ne 0) { throw "docker login to ECR failed" }

if (-not $SkipBuild) {
    $frontendNext = Join-Path $MonorepoRoot "frontend\.next"
    if (Test-Path $frontendNext) {
        Write-Host "Removing local frontend/.next (rebuilt inside Docker) ..." -ForegroundColor DarkGray
        Remove-Item -Recurse -Force $frontendNext -ErrorAction SilentlyContinue
    }
    Write-Host "Building $ImageUri ..." -ForegroundColor Cyan
    docker build -f (Join-Path $MonorepoRoot "frontend\Dockerfile") -t $ImageUri (Join-Path $MonorepoRoot ".")
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
}

Write-Host "Pushing $ImageUri ..." -ForegroundColor Cyan
docker push $ImageUri
if ($LASTEXITCODE -ne 0) { throw "docker push failed" }

Write-Host "Done: $ImageUri" -ForegroundColor Green
Write-Host "Next: aws ecs update-service --cluster sdlc-agentic-ai --service sdlc-control-plane --force-new-deployment --region $Region --profile $Profile" -ForegroundColor DarkGray