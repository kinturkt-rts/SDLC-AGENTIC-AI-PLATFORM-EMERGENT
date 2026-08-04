# Build and push the apps-repo target-app:deploy CI image to ECR.
#
# Image: 061836593297.dkr.ecr.us-east-2.amazonaws.com/sdlc-deploy-ci:<TF_VERSION>
# Consumed by backend/scripts/gitlab-apps-repo-ci.yml (target-app:deploy).
#
# Prereqs: Docker Desktop, AWS CLI, aws sso login
# Runner note: devops-agent-runner must be able to pull this private ECR image
# (credential helper / IAM on the runner host). Image pull happens before
# the job's OIDC role is available.
#
# Usage (from backend/):
#   .\scripts\push-deploy-ci-ecr.ps1
#   .\scripts\push-deploy-ci-ecr.ps1 -SkipBuild
#   .\scripts\push-deploy-ci-ecr.ps1 -SkipCreateRepo

param(
    [string] $Region = "us-east-2",
    [string] $AccountId = "061836593297",
    [string] $Repository = "sdlc-deploy-ci",
    # Tag matches TF_VERSION baked into the image / CI variables.
    [string] $Tag = "1.10.5",
    [string] $Profile = "eks-admin-user",
    [switch] $SkipBuild,
    [switch] $SkipCreateRepo
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile
$BackendRoot = Split-Path $PSScriptRoot -Parent
$DockerfileDir = Join-Path $BackendRoot "deploy\target-app-deploy-ci"
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$ImageUri = "$Registry/${Repository}:$Tag"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not on PATH. Install Docker Desktop, then re-run."
}

Write-Host "Checking AWS identity..." -ForegroundColor Cyan
aws sts get-caller-identity --region $Region | Out-Null
if ($LASTEXITCODE -ne 0) { throw "aws sts get-caller-identity failed (profile: $Profile)." }

if (-not $SkipCreateRepo) {
    Write-Host "Ensuring ECR repository $Repository exists..." -ForegroundColor Cyan
    # Native aws stderr becomes a terminating error under Stop; soften for probe/create.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $existing = aws ecr describe-repositories `
        --repository-names $Repository `
        --region $Region `
        --query "repositories[0].repositoryUri" `
        --output text 2>$null
    $describeOk = ($LASTEXITCODE -eq 0)
    if ($describeOk -and -not [string]::IsNullOrWhiteSpace($existing) -and $existing -ne "None") {
        $ErrorActionPreference = $prevEap
        Write-Host "Using existing $existing" -ForegroundColor DarkGray
    } else {
        aws ecr create-repository `
            --repository-name $Repository `
            --region $Region | Out-Null
        $createCode = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        if ($createCode -ne 0) { throw "Failed to create ECR repository '$Repository'." }
        Write-Host "Created $Registry/$Repository" -ForegroundColor DarkGray
    }
}

# PowerShell pipes append CRLF and ECR returns 400 on --password-stdin.
# Same workaround as deploy-target-app.ps1 / push-frontend-ecr.ps1.
if ($IsLinux -or $IsMacOS) {
    aws ecr get-login-password --region $Region --profile $Profile |
        docker login --username AWS --password-stdin $Registry
} else {
    cmd /c "aws ecr get-login-password --region $Region --profile $Profile | docker login --username AWS --password-stdin $Registry"
}
if ($LASTEXITCODE -ne 0) { throw "docker login to ECR failed." }

if (-not $SkipBuild) {
    if (-not (Test-Path (Join-Path $DockerfileDir "Dockerfile"))) {
        throw "Missing Dockerfile at $DockerfileDir"
    }
    Write-Host "Building $ImageUri (TF_VERSION=$Tag) ..." -ForegroundColor Cyan
    docker build `
        --build-arg "TF_VERSION=$Tag" `
        -t $ImageUri `
        $DockerfileDir
    if ($LASTEXITCODE -ne 0) { throw "docker build failed." }
}

Write-Host "Pushing $ImageUri ..." -ForegroundColor Cyan
docker push $ImageUri
if ($LASTEXITCODE -ne 0) { throw "docker push failed." }

Write-Host "Done: $ImageUri" -ForegroundColor Green
Write-Host "Next: copy gitlab-apps-repo-ci.yml into the apps repo (or sync) so target-app:deploy uses this image." -ForegroundColor DarkGray
