# Deploy all SDLC agents to Amazon Bedrock AgentCore Runtime.
# Prereqs: pip install bedrock-agentcore-starter-toolkit, AWS credentials, Bedrock model access.
param(
    [string] $Region = "us-east-2",
    [string[]] $Agents = @(),
    [switch] $ConfigureOnly,
    [switch] $SkipConfigure
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$AllAgents = @(
    @{ name = "architect-agent"; node = $false; extra = @("PRODUCT_ARTIFACT_LAYOUT=docs") },
    @{ name = "product-agent"; node = $false; extra = @("AGENTCORE_PRODUCT_SKIP_JIRA=true", "PRODUCT_ARTIFACT_LAYOUT=docs") },
    @{ name = "database-agent"; node = $false; extra = @("AGENTCORE_DATABASE_USE_POSTGRES=true") },
    @{ name = "developer-agent"; node = $false; extra = @() },
    @{ name = "gitlab-agent"; node = $false; extra = @() },
    @{ name = "qa-agent"; node = $false; extra = @() },
    @{ name = "orchestrator-agent"; node = $false; extra = @() },
    @{ name = "web-crawler-agent"; node = $true; extra = @() },
    @{ name = "security-agent"; node = $false; extra = @() },
    @{ name = "devops-agent"; node = $false; extra = @() }
)

$TargetAgents = if ($Agents.Count -gt 0) {
    $AllAgents | Where-Object { $Agents -contains $_.name }
} else {
    $AllAgents
}

$CommonEnv = @(
    "AWS_REGION=$Region",
    "MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0",
    "ARTIFACT_STORE=s3"
)

if ($env:ARTIFACT_S3_BUCKET) { $CommonEnv += "ARTIFACT_S3_BUCKET=$($env:ARTIFACT_S3_BUCKET)" }
if ($env:ARTIFACT_DYNAMODB_TABLE) { $CommonEnv += "ARTIFACT_DYNAMODB_TABLE=$($env:ARTIFACT_DYNAMODB_TABLE)" }

# Orchestrator runs apply_sql_to_rds after database-agent — pass RDS creds on orchestrator runtime only.
$OrchestratorExtra = @()
foreach ($name in @(
    "POSTGRES_MCP_DB_ENDPOINT",
    "POSTGRES_MCP_DATABASE",
    "POSTGRES_MCP_DB_USER",
    "POSTGRES_MCP_DB_PASSWORD",
    "POSTGRES_MCP_PORT",
    "POSTGRES_MCP_REGION",
    "POSTGRES_MCP_SSLMODE"
)) {
    if ($env:$name) { $OrchestratorExtra += "$name=$($env:$name)" }
}

foreach ($agent in $TargetAgents) {
    $name = $agent.name
    Write-Host "`n=== $name ===" -ForegroundColor Cyan

    if (-not $SkipConfigure) {
        agentcore configure `
            --entrypoint deploy/agentcore/a2a_server.py `
            --requirements-file deploy/agentcore/requirements.txt `
            --protocol A2A `
            --deployment-type container `
            --name $name `
            --region $Region `
            --disable-memory `
            --non-interactive
    }

    if ($ConfigureOnly) { continue }

    $deployArgs = @("deploy", "--agent", $name, "--env", "AGENTCORE_AGENT=$name")
    $envBlock = $CommonEnv + $agent.extra
    if ($name -eq "orchestrator-agent") {
        $envBlock += $OrchestratorExtra
    }
    foreach ($item in $envBlock) {
        $deployArgs += @("--env", $item)
    }
    & agentcore @deployArgs
}

Write-Host "`nUpdate config/agentcore/runtimes.json with runtime ARNs and invoke URLs." -ForegroundColor Green
