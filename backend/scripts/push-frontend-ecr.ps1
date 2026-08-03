# Build and push control-plane frontend image to ECR (redeploy only).
#
# Existing repo: 061836593297.dkr.ecr.us-east-2.amazonaws.com/sdlc-control-plane
# Demo repo:     .../sdlc-control-plane-demo
#
# Usage (from backend/):
#   aws sso login --profile eks-admin-user
#   .\scripts\push-frontend-ecr.ps1
#   .\scripts\push-frontend-ecr.ps1 -Demo
#   .\scripts\push-frontend-ecr.ps1 -SkipBuild
#
# Then roll out:
#   .\scripts\deploy-frontend-ecs.ps1
#   .\scripts\deploy-frontend-ecs.ps1 -Demo

param(
    [string] $Region = "us-east-2",
    [string] $Profile = "eks-admin-user",
    [string] $AccountId = "061836593297",
    [string] $Repository = "",
    [string] $Tag = "latest",
    [switch] $Demo,
    [switch] $SkipBuild,
    [switch] $CreateRepo
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile
$BackendRoot = Split-Path $PSScriptRoot -Parent
$MonorepoRoot = Split-Path $BackendRoot -Parent
if (-not $Repository) {
    $Repository = if ($Demo) { "sdlc-control-plane-demo" } else { "sdlc-control-plane" }
}
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$ImageUri = "$Registry/${Repository}:$Tag"

Write-Host "Verifying ECR repository $Repository ..." -ForegroundColor Cyan
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$repo = aws ecr describe-repositories `
    --repository-names $Repository `
    --region $Region `
    --profile $Profile `
    --query "repositories[0].repositoryUri" `
    --output text 2>$null
$repoOk = ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($repo) -and $repo -ne "None")
$ErrorActionPreference = $prevEap

if (-not $repoOk) {
    if ($CreateRepo -or $Demo) {
        Write-Host "Creating ECR repository $Repository ..." -ForegroundColor Cyan
        aws ecr create-repository `
            --repository-name $Repository `
            --region $Region `
            --profile $Profile `
            --image-scanning-configuration scanOnPush=true `
            --encryption-configuration encryptionType=AES256 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to create ECR repository $Repository" }
        $repo = "$Registry/$Repository"
    } else {
        throw "ECR repository '$Repository' not found in $Region (profile: $Profile). Create it once via deploy-frontend-ecs.ps1, -CreateRepo, or the AWS console."
    }
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
    # Docker writes progress to stderr; don't treat that as a terminating error.
    $prevEapBuild = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    docker build -f (Join-Path $MonorepoRoot "frontend\Dockerfile") -t $ImageUri (Join-Path $MonorepoRoot ".")
    $buildExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEapBuild
    if ($buildExit -ne 0) { throw "docker build failed (exit $buildExit)" }
}

Write-Host "Pushing $ImageUri ..." -ForegroundColor Cyan
$prevEapPush = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker push $ImageUri
$pushExit = $LASTEXITCODE
$ErrorActionPreference = $prevEapPush
if ($pushExit -ne 0) { throw "docker push failed (exit $pushExit)" }

# Also stamp a versioned tag for promote/rollback (demo + dev).
$versionTag = Get-Date -Format "yyyyMMdd-HHmmss"
$VersionedUri = "$Registry/${Repository}:$versionTag"
$ErrorActionPreference = "Continue"
docker tag $ImageUri $VersionedUri
docker push $VersionedUri | Out-Null
$ErrorActionPreference = "Stop"
Write-Host "Also tagged: $VersionedUri" -ForegroundColor DarkGray

$serviceHint = if ($Demo) { "sdlc-control-plane-demo" } else { "sdlc-control-plane" }
Write-Host "Done: $ImageUri" -ForegroundColor Green
Write-Host "Next: .\scripts\deploy-frontend-ecs.ps1$(if ($Demo) { ' -Demo' } else { '' })" -ForegroundColor DarkGray
Write-Host "Or: aws ecs update-service --cluster sdlc-agentic-ai --service $serviceHint --force-new-deployment --region $Region --profile $Profile" -ForegroundColor DarkGray
