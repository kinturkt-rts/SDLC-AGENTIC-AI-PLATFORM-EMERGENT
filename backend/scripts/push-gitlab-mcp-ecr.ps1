# Push jmrplens/gitlab-mcp-server to ECR for shared HTTP MCP on ECS.
# This is NOT the gitlab-agent AgentCore image (bedrock-agentcore-gitlab_agent).
#
# Prereqs: Docker Desktop, AWS CLI, `aws sso login --profile "Juno Developers"`
#
# Usage (from backend/):
#   .\scripts\push-gitlab-mcp-ecr.ps1
#   .\scripts\push-gitlab-mcp-ecr.ps1 -SkipCreateRepo
#   .\scripts\push-gitlab-mcp-ecr.ps1 -Repository gitlab-mcp-server -Tag latest
#   .\scripts\push-gitlab-mcp-ecr.ps1 -BuildFromDockerfile
param(
    [string] $Region = "us-east-2",
    [string] $AccountId = "061836593297",
    [string] $Repository = "gitlab-mcp-server",
    [string] $Tag = "latest",
    [string] $SourceImage = "ghcr.io/jmrplens/gitlab-mcp-server:latest",
    [string] $Profile = "Juno Developers",
    [switch] $SkipCreateRepo,
    [switch] $SkipPull,
    [switch] $BuildFromDockerfile
)

$ErrorActionPreference = "Stop"
$env:AWS_PROFILE = $Profile
$BackendRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker Desktop, then re-run."
}

if ($Repository -eq "bedrock-agentcore-gitlab_agent") {
    Write-Warning "bedrock-agentcore-gitlab_agent is the gitlab-agent Python runtime repo, not the MCP server."
    Write-Warning "Use -Repository gitlab-mcp-server (default) for the shared MCP HTTP service."
}

Write-Host "Checking AWS identity..." -ForegroundColor Cyan
aws sts get-caller-identity --region $Region | Out-Null

$EcrUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/${Repository}:$Tag"

if (-not $SkipCreateRepo) {
    Write-Host "Creating ECR repository $Repository (ignored if exists)..." -ForegroundColor Cyan
    aws ecr create-repository `
        --repository-name $Repository `
        --region $Region `
        2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Repository may already exist - continuing.' -ForegroundColor Yellow
    }
}

$LocalImage = "gitlab-mcp-server:local"
if ($BuildFromDockerfile) {
    $dockerfileDir = Join-Path $BackendRoot "deploy\gitlab-mcp-server"
    Write-Host "Building from $dockerfileDir/Dockerfile ..." -ForegroundColor Cyan
    docker build -t $LocalImage $dockerfileDir
    $SourceImage = $LocalImage
} elseif (-not $SkipPull) {
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
Write-Host "Done. MCP service image URI:" -ForegroundColor Green
Write-Host "  $EcrUri"
Write-Host ""
Write-Host "ECS task command (if not using deploy/gitlab-mcp-server/Dockerfile CMD):" -ForegroundColor Cyan
Write-Host "  --http --http-addr=0.0.0.0:8080 --gitlab-url=https://code.junodev.net"
Write-Host ""
Write-Host "gitlab-agent AgentCore runtime env:" -ForegroundColor Cyan
Write-Host '  GITLAB_MCP_HTTP_URL=http://<internal-service-dns>:8080/mcp'
Write-Host '  GITLAB_PERSONAL_ACCESS_TOKEN=glpat_...'
