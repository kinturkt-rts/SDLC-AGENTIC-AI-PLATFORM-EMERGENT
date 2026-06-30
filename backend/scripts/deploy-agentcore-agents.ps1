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

# agentcore CLI prints unicode glyphs (checkmarks); Windows console codepage (cp1252) can't
# encode them and the process crashes mid-command even after the action already succeeded.
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$DotenvForwardedKeys = @(
    "ARTIFACT_S3_BUCKET",
    "ARTIFACT_DYNAMODB_TABLE",
    "POSTGRES_MCP_DB_ENDPOINT",
    "POSTGRES_MCP_DATABASE",
    "POSTGRES_MCP_DB_USER",
    "POSTGRES_MCP_DB_PASSWORD",
    "POSTGRES_MCP_PORT",
    "POSTGRES_MCP_REGION",
    "POSTGRES_MCP_SSLMODE"
)

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

$AllAgents = @(
    @{ awsName = "architect_agent"; bundle = "architect-agent"; node = $false; extra = @("PRODUCT_ARTIFACT_LAYOUT=docs") },
    @{ awsName = "product_agent"; bundle = "product-agent"; node = $false; extra = @("AGENTCORE_PRODUCT_SKIP_JIRA=true", "PRODUCT_ARTIFACT_LAYOUT=docs") },
    @{ awsName = "database_agent"; bundle = "database-agent"; node = $false; extra = @("AGENTCORE_DATABASE_USE_POSTGRES=true") },
    @{ awsName = "developer_agent"; bundle = "developer-agent"; node = $false; extra = @() },
    @{ awsName = "gitlab_agent"; bundle = "gitlab-agent"; node = $false; extra = @() },
    @{ awsName = "qa_agent"; bundle = "qa-agent"; node = $false; extra = @() },
    @{ awsName = "orchestrator_agent"; bundle = "orchestrator-agent"; node = $false; extra = @() },
    # VPC-mode orchestrator runtime: AgentCore network mode is immutable after creation, so RDS
    # access (needs to reach RDS in vpc-036155f359e2e940c) requires a separate runtime, not a
    # reconfigure of orchestrator_agent. Cut config/agentcore/runtimes.json over once verified.
    @{ awsName = "orchestrator_agent_vpc"; bundle = "orchestrator-agent"; node = $false; extra = @(); vpc = @{
        subnets = "subnet-0c0e7c749de659e32,subnet-07651619f77b51d7f,subnet-044c04012037ca457"
        securityGroups = "sg-077b416683295dd42"
    } },
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

if (-not $env:ARTIFACT_S3_BUCKET) {
    Write-Error "ARTIFACT_S3_BUCKET is not set. Add it to .env.local or export it before deploy."
}

if ($env:CODING_MODEL_ID) { $CommonEnv += "CODING_MODEL_ID=$($env:CODING_MODEL_ID)" }

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

    $deployArgs = @("deploy", "--agent", $awsName, "--env", "AGENTCORE_AGENT=$bundle")
    $envBlock = $CommonEnv + $agent.extra
    if ($awsName -eq "orchestrator_agent" -or $awsName -eq "orchestrator_agent_vpc") {
        $envBlock += $OrchestratorExtra
    }
    foreach ($item in $envBlock) {
        $deployArgs += @("--env", $item)
    }
    & agentcore @deployArgs
}

Write-Host "`nUpdate config/agentcore/runtimes.json with runtime ARNs and invoke URLs." -ForegroundColor Green
