# Deploy all SDLC agents to Amazon Bedrock AgentCore Runtime.
# Prereqs: pip install bedrock-agentcore-starter-toolkit, AWS credentials, Bedrock model access.
#
# AgentCore registry names use underscores (database_agent). AGENTCORE_AGENT uses hyphenated
# bundle keys (database-agent) matching agents/<name>/ and BUNDLE_FACTORIES in a2a_server.py.
#
# IMPORTANT: agentcore configure --entrypoint deploy/agentcore/a2a_server.py narrows source_path
# to deploy/agentcore (~11 KB zip) and CodeBuild fails (COPY agents/ not found). Redeploys should
# use -SkipConfigure (default for existing agents in .bedrock_agentcore.yaml). First-time setup: -Configure.
param(
    [string] $Region = "us-east-2",
    [string[]] $Agents = @(),
    [switch] $Configure,
    [switch] $ConfigureOnly,
    [switch] $SkipConfigure
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$AllAgents = @(
    @{ awsName = "architect_agent"; bundle = "architect-agent"; node = $false; extra = @("PRODUCT_ARTIFACT_LAYOUT=docs") },
    @{ awsName = "product_agent"; bundle = "product-agent"; node = $false; extra = @("AGENTCORE_PRODUCT_SKIP_JIRA=true", "PRODUCT_ARTIFACT_LAYOUT=docs") },
    @{ awsName = "database_agent"; bundle = "database-agent"; node = $false; extra = @("AGENTCORE_DATABASE_USE_POSTGRES=true") },
    @{ awsName = "developer_agent"; bundle = "developer-agent"; node = $false; extra = @() },
    @{ awsName = "gitlab_agent"; bundle = "gitlab-agent"; node = $false; extra = @() },
    @{ awsName = "qa_agent"; bundle = "qa-agent"; node = $false; extra = @() },
    @{ awsName = "orchestrator_agent"; bundle = "orchestrator-agent"; node = $false; extra = @() },
    @{ awsName = "web_crawler_agent"; bundle = "web-crawler-agent"; node = $true; extra = @() },
    @{ awsName = "security_agent"; bundle = "security-agent"; node = $false; extra = @() },
    @{ awsName = "devops_agent"; bundle = "devops-agent"; node = $false; extra = @() }
)

$TargetAgents = if ($Agents.Count -gt 0) {
    $AllAgents | Where-Object {
        ($Agents -contains $_.awsName) -or ($Agents -contains $_.bundle)
    }
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
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($value) { $OrchestratorExtra += "$name=$value" }
}

# Default: skip configure on redeploy (configure shrinks source_path to deploy/agentcore only).
$RunConfigure = ($Configure -or $ConfigureOnly) -and -not $SkipConfigure

foreach ($agent in $TargetAgents) {
    $awsName = $agent.awsName
    $bundle = $agent.bundle
    Write-Host "`n=== $awsName (bundle=$bundle) ===" -ForegroundColor Cyan

    if ($RunConfigure) {
        agentcore configure `
            --entrypoint deploy/agentcore `
            --requirements-file deploy/agentcore/requirements.txt `
            --protocol A2A `
            --deployment-type container `
            --name $awsName `
            --region $Region `
            --disable-memory `
            --non-interactive
        Write-Warning "After configure, verify source_path is 'backend' (not deploy/agentcore) in .bedrock_agentcore.yaml"
    }

    if ($ConfigureOnly) { continue }

    $deployArgs = @("deploy", "--agent", $awsName, "--env", "AGENTCORE_AGENT=$bundle")
    $envBlock = $CommonEnv + $agent.extra
    if ($awsName -eq "orchestrator_agent") {
        $envBlock += $OrchestratorExtra
    }
    foreach ($item in $envBlock) {
        $deployArgs += @("--env", $item)
    }
    & agentcore @deployArgs
}

Write-Host "`nUpdate config/agentcore/runtimes.json with runtime ARNs and invoke URLs." -ForegroundColor Green
