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

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$DotenvForwardedKeys = @(
    "ARTIFACT_S3_BUCKET",
    "ARTIFACT_DYNAMODB_TABLE",
    "AWS_PROFILE",
    "CODING_MODEL_ID",
    "MODEL_ID",
    "ATLASSIAN_MCP_TOKEN",
    "ATLASSIAN_MCP_URL",
    "GITLAB_PERSONAL_ACCESS_TOKEN",
    "GITLAB_TOKEN",
    "GITLAB_URL",
    "GITLAB_API_URL",
    "GITLAB_PROJECT_PATH",
    "GITLAB_MCP_URL",
    "GITLAB_MCP_HTTP_URL",
    "GITLAB_MCP_HTTP_DIRECT_URL",
    "GITLAB_MCP_HTTP_BATCH_SIZE",
    "POSTGRES_MCP_DEPLOYMENT",
    "POSTGRES_MCP_CONNECTION_METHOD",
    "POSTGRES_MCP_INSTANCE_IDENTIFIER",
    "POSTGRES_MCP_DB_ENDPOINT",
    "POSTGRES_MCP_DATABASE",
    "POSTGRES_MCP_REGION",
    "POSTGRES_MCP_PORT",
    "POSTGRES_MCP_ALLOW_WRITE",
    "POSTGRES_MCP_DB_USER",
    "POSTGRES_MCP_DB_PASSWORD",
    "POSTGRES_MCP_SSLMODE",
    "FIRECRAWL_API_KEY"
)

function Get-EnvPairsForKeys {
    param([string[]] $Keys)
    $pairs = @()
    foreach ($name in $Keys) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if ($value) { $pairs += "$name=$value" }
    }
    return $pairs
}

function Import-ArtifactEnvFromDotenv {
    foreach ($path in @(
        (Join-Path (Split-Path -Parent $RepoRoot) ".env.local"),
        (Join-Path $RepoRoot ".env.local"),
        (Join-Path (Split-Path -Parent $RepoRoot) ".env"),
        (Join-Path $RepoRoot ".env")
    )) {
        if (-not (Test-Path $path)) { continue }
        Get-Content $path | ForEach-Object {
            $line = $_.Trim()
            if ($line -match '^\s*#' -or -not $line) { return }
            if ($line -match '^\s*([^=]+)=(.*)$') {
                $key = $matches[1].Trim()
                $val = $matches[2].Trim().Trim('"').Trim("'")
                if ($val -and ($DotenvForwardedKeys -contains $key) -and -not [Environment]::GetEnvironmentVariable($key)) {
                    [Environment]::SetEnvironmentVariable($key, $val, "Process")
                }
            }
        }
    }
}

Import-ArtifactEnvFromDotenv

function Import-GitLabMcpEndpointsFromConfig {
    $configPath = Join-Path $RepoRoot "config\agentcore\gitlab-mcp-endpoints.json"
    if (-not (Test-Path $configPath)) {
        Write-Warning "GitLab MCP endpoints config not found: $configPath"
        return
    }
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    if ($config.cloudFront.mcpUrl) {
        [Environment]::SetEnvironmentVariable("GITLAB_MCP_URL", $config.cloudFront.mcpUrl.Trim(), "Process")
        Write-Host "Using GITLAB_MCP_URL (CloudFront) from config/agentcore/gitlab-mcp-endpoints.json" -ForegroundColor DarkGray
    }
    if ($config.directMcpUrl) {
        [Environment]::SetEnvironmentVariable("GITLAB_MCP_HTTP_DIRECT_URL", $config.directMcpUrl.Trim(), "Process")
    }
    if (-not $env:GITLAB_MCP_HTTP_BATCH_SIZE) {
        [Environment]::SetEnvironmentVariable("GITLAB_MCP_HTTP_BATCH_SIZE", "1", "Process")
    }
}

Import-GitLabMcpEndpointsFromConfig

function Test-AgentRegisteredInYaml {
    param([string] $AwsName)
    $yamlPath = Join-Path $RepoRoot ".bedrock_agentcore.yaml"
    if (-not (Test-Path $yamlPath)) { return $false }
    return (Select-String -Path $yamlPath -Pattern "^\s{2}${AwsName}:" -Quiet)
}

# Default SDLC pipeline runtimes (batch deploy without -Agents).
$PipelineAgents = @(
    @{ awsName = "product_agent"; bundle = "product-agent"; node = $false; extra = @("AGENTCORE_PRODUCT_SKIP_JIRA=true") },
    @{ awsName = "architect_agent"; bundle = "architect-agent"; node = $false; extra = @() },
    @{ awsName = "database_agent"; bundle = "database-agent"; node = $false; extra = @() },
    @{ awsName = "developer_agent"; bundle = "developer-agent"; node = $false; extra = @() },
    @{ awsName = "gitlab_agent"; bundle = "gitlab-agent"; node = $false; extra = @() },
    @{ awsName = "orchestrator_agent"; bundle = "orchestrator-agent"; node = $false; extra = @() }
)

# Deploy on demand via -Agents (not part of default pipeline batch).
$OptionalAgents = @(
    @{ awsName = "qa_agent"; bundle = "qa-agent"; node = $false; extra = @() },
    # VPC-mode orchestrator: network mode is immutable after creation; use when orchestrator
    # must reach RDS in vpc-036155f359e2e940c. Example:
    #   .\scripts\deploy-agentcore-agents.ps1 -Agents orchestrator_agent_vpc -SkipConfigure
    @{ awsName = "orchestrator_agent_vpc"; bundle = "orchestrator-agent"; node = $false; extra = @(); vpc = @{
        subnets = "subnet-0c0e7c749de659e32,subnet-07651619f77b51d7f,subnet-044c04012037ca457"
        securityGroups = "sg-077b416683295dd42"
    } },
    @{ awsName = "security_agent"; bundle = "security-agent"; node = $false; extra = @() }
)

$AllAgents = $PipelineAgents + $OptionalAgents

$TargetAgents = if ($Agents.Count -gt 0) {
    $AllAgents | Where-Object {
        ($Agents -contains $_.awsName) -or ($Agents -contains $_.bundle)
    }
} else {
    $PipelineAgents
}

$CommonEnv = @(
    "AWS_REGION=$Region",
    "ARTIFACT_STORE=s3"
)

if ($env:MODEL_ID) { $CommonEnv += "MODEL_ID=$($env:MODEL_ID)" }
else { $CommonEnv += "MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0" }

if ($env:ARTIFACT_S3_BUCKET) { $CommonEnv += "ARTIFACT_S3_BUCKET=$($env:ARTIFACT_S3_BUCKET)" }
if ($env:ARTIFACT_DYNAMODB_TABLE) { $CommonEnv += "ARTIFACT_DYNAMODB_TABLE=$($env:ARTIFACT_DYNAMODB_TABLE)" }

if (-not $env:ARTIFACT_S3_BUCKET) {
    Write-Error "ARTIFACT_S3_BUCKET is not set. Add it to .env.local or export it before deploy."
}

if ($env:CODING_MODEL_ID) { $CommonEnv += "CODING_MODEL_ID=$($env:CODING_MODEL_ID)" }

# Per-agent secrets forwarded from .env.local (never commit these values).
$AgentSecretKeys = @{
    product_agent          = @("ATLASSIAN_MCP_TOKEN", "ATLASSIAN_MCP_URL")
    architect_agent        = @()
    database_agent         = @()
    developer_agent        = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH")
    gitlab_agent           = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH", "GITLAB_MCP_URL", "GITLAB_MCP_HTTP_URL", "GITLAB_MCP_HTTP_DIRECT_URL", "GITLAB_MCP_HTTP_BATCH_SIZE")
    orchestrator_agent     = @()
    orchestrator_agent_vpc = @()
    security_agent         = @()
    qa_agent               = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_MCP_URL", "GITLAB_MCP_HTTP_URL", "GITLAB_MCP_HTTP_DIRECT_URL", "GITLAB_MCP_HTTP_BATCH_SIZE")
}

# Orchestrator runs apply_sql_to_rds after database-agent - pass RDS creds on orchestrator runtime only.
$OrchestratorRdsKeys = @(
    "POSTGRES_MCP_DEPLOYMENT",
    "POSTGRES_MCP_CONNECTION_METHOD",
    "POSTGRES_MCP_INSTANCE_IDENTIFIER",
    "POSTGRES_MCP_DB_ENDPOINT",
    "POSTGRES_MCP_DATABASE",
    "POSTGRES_MCP_DB_USER",
    "POSTGRES_MCP_DB_PASSWORD",
    "POSTGRES_MCP_PORT",
    "POSTGRES_MCP_REGION",
    "POSTGRES_MCP_ALLOW_WRITE",
    "POSTGRES_MCP_SSLMODE"
)

# Default: skip configure on redeploy (configure shrinks source_path to deploy/agentcore only).
$RunConfigure = ($Configure -or $ConfigureOnly) -and -not $SkipConfigure

$DeployFailures = @()
$DeploySkipped = @()

foreach ($agent in $TargetAgents) {
    $awsName = $agent.awsName
    $bundle = $agent.bundle
    Write-Host "`n=== $awsName (bundle=$bundle) ===" -ForegroundColor Cyan

    if ($RunConfigure) {
        $configureArgs = @(
            "configure",
            "--entrypoint", "deploy/agentcore/a2a_server.py",
            "--requirements-file", "deploy/agentcore/requirements.txt",
            "--protocol", "A2A",
            "--deployment-type", "container",
            "--name", $awsName,
            "--region", $Region,
            "--disable-memory",
            "--non-interactive"
        )
        if ($agent.vpc) {
            $configureArgs += @(
                "--vpc",
                "--subnets", $agent.vpc.subnets,
                "--security-groups", $agent.vpc.securityGroups
            )
        }
        & agentcore @configureArgs
        Write-Warning "After configure, verify source_path is 'backend' (not deploy/agentcore) in .bedrock_agentcore.yaml"
    }

    if ($ConfigureOnly) { continue }

    if ($SkipConfigure -and -not (Test-AgentRegisteredInYaml -AwsName $awsName)) {
        Write-Warning "Skipping $awsName - not registered in .bedrock_agentcore.yaml. First-time setup:`n  .\scripts\deploy-agentcore-agents.ps1 -Agents $awsName -Configure`nThen verify source_path is 'backend' (not deploy/agentcore) before redeploying with -SkipConfigure."
        $DeploySkipped += $awsName
        continue
    }

    $deployArgs = @("deploy", "--agent", $awsName, "--env", "AGENTCORE_AGENT=$bundle")
    $envBlock = $CommonEnv + $agent.extra
    if ($AgentSecretKeys.ContainsKey($awsName)) {
        $envBlock += Get-EnvPairsForKeys -Keys $AgentSecretKeys[$awsName]
    }
    if ($awsName -eq "orchestrator_agent" -or $awsName -eq "orchestrator_agent_vpc") {
        $envBlock += Get-EnvPairsForKeys -Keys $OrchestratorRdsKeys
    }
    foreach ($item in $envBlock) {
        $deployArgs += @("--env", $item)
    }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & agentcore @deployArgs 2>&1 | ForEach-Object { Write-Host $_ }
    $agentcoreExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($agentcoreExit -ne 0) {
        $DeployFailures += $awsName
        Write-Warning "Deploy failed for $awsName (exit $agentcoreExit)."
    }
}

if ($DeploySkipped.Count -gt 0) {
    Write-Host "`nSkipped (not configured): $($DeploySkipped -join ', ')" -ForegroundColor Yellow
}
if ($DeployFailures.Count -gt 0) {
    Write-Error "Deploy failed for: $($DeployFailures -join ', ')"
}

Write-Host "`nUpdate config/agentcore/runtimes.json with runtime ARNs and invoke URLs." -ForegroundColor Green
