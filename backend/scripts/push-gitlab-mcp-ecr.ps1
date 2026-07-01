# Push jmrplens/gitlab-mcp-server to ECR for shared HTTP MCP on ECS.
# Prereqs: Docker Desktop, AWS CLI, `aws sso login --profile "Juno Developers"`
#
# Usage (from backend/):
#   .\scripts\push-gitlab-mcp-ecr.ps1
#   .\scripts\push-gitlab-mcp-ecr.ps1 -SkipCreateRepo
param(
    [string] $Region = "us-east-2",
    [string] $AccountId = "061836593297",
    [string] $Repository = "gitlab-mcp-server",
    [string] $SourceImage = "ghcr.io/jmrplens/gitlab-mcp-server:latest",
    [string] $Profile = "Juno Developers",
    [switch] $SkipCreateRepo,
    [switch] $SkipPull
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker Desktop, then re-run."
}

Write-Host "Checking AWS identity..." -ForegroundColor Cyan
aws sts get-caller-identity --region $Region | Out-Null

$EcrUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/$Repository`:latest"

if (-not $SkipCreateRepo) {
    Write-Host "Creating ECR repository $Repository (ignored if exists)..." -ForegroundColor Cyan
    aws ecr create-repository `
        --repository-name $Repository `
        --region $Region `
        2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Repository may already exist — continuing." -ForegroundColor Yellow
    }
}

if (-not $SkipPull) {
    Write-Host "Pulling $SourceImage ..." -ForegroundColor Cyan
    docker pull $SourceImage
}

Write-Host "Logging in to ECR..." -ForegroundColor Cyan
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

Write-Host "Tagging image -> $EcrUri" -ForegroundColor Cyan
docker tag $SourceImage $EcrUri

Write-Host "Pushing to ECR..." -ForegroundColor Cyan
docker push $EcrUri

Write-Host ""
Write-Host "Done. Image URI:" -ForegroundColor Green
Write-Host "  $EcrUri"
Write-Host ""
Write-Host "ECS container command (Juno GitLab):" -ForegroundColor Cyan
Write-Host "  --http --http-addr=0.0.0.0:8080 --gitlab-url=https://code.junodev.net"
Write-Host ""
Write-Host "gitlab-agent AgentCore env after ECS is reachable:" -ForegroundColor Cyan
Write-Host "  GITLAB_MCP_HTTP_URL=http://<internal-service-dns>:8080/mcp"
