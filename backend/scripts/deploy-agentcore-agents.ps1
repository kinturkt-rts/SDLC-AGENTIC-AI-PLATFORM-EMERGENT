# Deploy all SDLC agents to Amazon Bedrock AgentCore Runtime.
# Prereqs: pip install bedrock-agentcore-starter-toolkit, AWS credentials, Bedrock model access.

param(
    [string] $Region = "us-east-2",
    [string[]] $Agents = @(),
    [switch] $Configure,
    [switch] $ConfigureOnly,
    [switch] $SkipConfigure,
    [switch] $Demo
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$DotenvForwardedKeys = @(
    "ARTIFACT_S3_BUCKET",
    "ARTIFACT_DYNAMODB_ENABLED",
    "ARTIFACT_DYNAMODB_TABLE",
    "AWS_PROFILE",
    "BEDROCK_READ_TIMEOUT",
    "CODING_MODEL_ID",
    "DEVELOPER_AGENT_AUTO_VALIDATE",
    "DEVELOPER_AGENT_AUTO_VALIDATE_PYTEST",
    "MODEL_ID",
    "SDLC_AGENT_TIMEOUT_SEC",
    "SDLC_DEVELOPER_AGENT_TIMEOUT_SEC",
    "SDLC_DEVELOPER_RETRY_ATTEMPTS",
    "DEVELOPER_AGENT_FALLBACK_MODEL_ID",
    "ATLASSIAN_MCP_TOKEN",
    "ATLASSIAN_MCP_EMAIL",
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
if (-not $env:FIRECRAWL_API_KEY -and $env:Firecrawl_API_Key) {
    [Environment]::SetEnvironmentVariable("FIRECRAWL_API_KEY", $env:Firecrawl_API_Key, "Process")
}

function Set-MinNumericEnv {
    param(
        [string] $Name,
        [int] $Minimum
    )
    $raw = [Environment]::GetEnvironmentVariable($Name)
    $value = 0
    if (-not [int]::TryParse($raw, [ref] $value) -or $value -lt $Minimum) {
        [Environment]::SetEnvironmentVariable($Name, "$Minimum", "Process")
    }
}

Set-MinNumericEnv -Name "BEDROCK_READ_TIMEOUT" -Minimum 1200
Set-MinNumericEnv -Name "SDLC_DEVELOPER_AGENT_TIMEOUT_SEC" -Minimum 1200
if (-not $env:DEVELOPER_AGENT_AUTO_VALIDATE) {
    [Environment]::SetEnvironmentVariable("DEVELOPER_AGENT_AUTO_VALIDATE", "true", "Process")
}
if (-not $env:DEVELOPER_AGENT_AUTO_VALIDATE_PYTEST) {
    [Environment]::SetEnvironmentVariable("DEVELOPER_AGENT_AUTO_VALIDATE_PYTEST", "true", "Process")
}

function Import-GitLabMcpEndpointsFromConfig {
    $configPath = Join-Path $RepoRoot "config\agentcore\gitlab-mcp-endpoints.json"
    if (-not (Test-Path $configPath)) {
        Write-Warning "GitLab MCP endpoints config not found: $configPath"
        return
    }
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    if ($config.cloudFront.mcpUrl) {
        if (-not [Environment]::GetEnvironmentVariable("GITLAB_MCP_URL")) {
            [Environment]::SetEnvironmentVariable("GITLAB_MCP_URL", $config.cloudFront.mcpUrl.Trim(), "Process")
            Write-Host "Using GITLAB_MCP_URL (CloudFront) from config/agentcore/gitlab-mcp-endpoints.json" -ForegroundColor DarkGray
        }
    }
    if ($config.directMcpUrl) {
        if (-not [Environment]::GetEnvironmentVariable("GITLAB_MCP_HTTP_DIRECT_URL")) {
            [Environment]::SetEnvironmentVariable("GITLAB_MCP_HTTP_DIRECT_URL", $config.directMcpUrl.Trim(), "Process")
        }
    }
    if (-not $env:GITLAB_MCP_HTTP_BATCH_SIZE) {
        [Environment]::SetEnvironmentVariable("GITLAB_MCP_HTTP_BATCH_SIZE", "1", "Process")
    }
}

Import-GitLabMcpEndpointsFromConfig

function Get-GitLabAgentMcpEnv {
    $configPath = Join-Path $RepoRoot "config\agentcore\gitlab-mcp-endpoints.json"
    if (-not (Test-Path $configPath)) { return @() }
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    if (-not $config.directMcpUrl) { return @() }
    $direct = $config.directMcpUrl.Trim()
    # Publish must hit ALB (not CloudFront) and use one Git commit per app —
    # per-file CloudFront publishes flood GitLab Sidekiq PostReceive org-wide.
    return @(
        "GITLAB_MCP_URL=$direct",
        "GITLAB_MCP_HTTP_DIRECT_URL=$direct",
        "GITLAB_MCP_HTTP_BATCH_SIZE=20",
        "GITLAB_PUBLISH_SINGLE_COMMIT=true",
        "GITLAB_MCP_PUBLISH_ALLOW_CLOUDFRONT=false"
    )
}

$GitLabAgentMcpEnv = Get-GitLabAgentMcpEnv

function Test-AgentRegisteredInYaml {
    param([string] $AwsName)
    $yamlPath = Join-Path $RepoRoot ".bedrock_agentcore.yaml"
    if (-not (Test-Path $yamlPath)) { return $false }
    return (Select-String -Path $yamlPath -Pattern "^\s{2}${AwsName}:" -Quiet)
}

# Default SDLC pipeline runtimes (batch deploy without -Agents).
# Set AGENTCORE_PRODUCT_JIRA=true before deploy to allow opt-in Jira backlog on product-agent.
$ProductJiraEnabled = ($env:AGENTCORE_PRODUCT_JIRA -eq "true")
$ProductAgentExtra = if ($ProductJiraEnabled) {
    @("AGENTCORE_PRODUCT_SKIP_JIRA=false")
} else {
    @("AGENTCORE_PRODUCT_SKIP_JIRA=true")
}

$PipelineAgents = @(
    @{ awsName = "product_agent"; bundle = "product-agent"; node = $true; extra = $ProductAgentExtra },
    @{ awsName = "architect_agent"; bundle = "architect-agent"; node = $false; extra = @() },
    @{ awsName = "database_agent"; bundle = "database-agent"; node = $false; extra = @("AGENTCORE_DATABASE_USE_POSTGRES=true") },
    @{ awsName = "developer_agent"; bundle = "developer-agent"; node = $false; extra = @("SDLC_TEMPLATE_VERSION=v1.0.0") },
    @{ awsName = "frontend_agent"; bundle = "frontend-agent"; node = $true; extra = @() },
    @{ awsName = "gitlab_agent"; bundle = "gitlab-agent"; node = $false; extra = $GitLabAgentMcpEnv },
    @{ awsName = "orchestrator_agent"; bundle = "orchestrator-agent"; node = $false; extra = @() }
)

# Isolated demo runtimes - same bundles (AGENTCORE_DEMO_AGENTS), new AWS names + ECR repos.
$DemoAgents = @(
    @{ awsName = "product_agent_demo"; bundle = "product-agent"; node = $true; extra = $ProductAgentExtra },
    @{ awsName = "architect_agent_demo"; bundle = "architect-agent"; node = $false; extra = @() },
    @{ awsName = "database_agent_demo"; bundle = "database-agent"; node = $false; extra = @("AGENTCORE_DATABASE_USE_POSTGRES=true") },
    @{ awsName = "developer_agent_demo"; bundle = "developer-agent"; node = $false; extra = @("SDLC_TEMPLATE_VERSION=v1.0.0") },
    @{ awsName = "gitlab_agent_demo"; bundle = "gitlab-agent"; node = $false; extra = $GitLabAgentMcpEnv },
    @{ awsName = "orchestrator_agent_demo"; bundle = "orchestrator-agent"; node = $false; extra = @("AGENTCORE_RUNTIMES_CONFIG=config/agentcore/runtimes.demo.json") }
)

# Deploy on demand via -Agents (not part of default pipeline batch).
$OptionalAgents = @(
    @{ awsName = "qa_agent"; bundle = "qa-agent"; node = $false; extra = @() },
    @{ awsName = "orchestrator_agent_vpc"; bundle = "orchestrator-agent"; node = $false; extra = @(); vpc = @{
        subnets = "subnet-0c0e7c749de659e32,subnet-07651619f77b51d7f,subnet-044c04012037ca457"
        securityGroups = "sg-077b416683295dd42"
    } },
    @{ awsName = "security_agent"; bundle = "security-agent"; node = $false; extra = @() },
    @{ awsName = "devops_agent"; bundle = "devops-agent"; node = $true; extra = @() },
    @{ awsName = "web_crawler_agent"; bundle = "web-crawler-agent"; node = $true; extra = @(
        "AGENTCORE_WEBCRAWLER_WITH_POSTGRES=false",
        "FIRECRAWL_MCP_COMMAND=firecrawl-mcp",
        "FIRECRAWL_MCP_ARGS="
    ) }
)

$AllAgents = $PipelineAgents + $DemoAgents + $OptionalAgents

$TargetAgents = if ($Agents.Count -gt 0) {
    $byAwsName = @($AllAgents | Where-Object { $Agents -contains $_.awsName })
    if ($byAwsName.Count -gt 0) {
        $byAwsName
    } else {
        $byBundle = @($AllAgents | Where-Object { $Agents -contains $_.bundle })
        if ($Demo) {
            @($byBundle | Where-Object { $_.awsName -like "*_demo" })
        } else {
            @($byBundle | Where-Object { $_.awsName -notlike "*_demo" })
        }
    }
} elseif ($Demo) {
    $DemoAgents
} else {
    $PipelineAgents
}

if ($TargetAgents.Count -eq 0) {
    Write-Error "No matching agents for selection. Use awsName (product_agent_demo) or -Demo with bundle names."
}

$CommonEnv = @(
    "AWS_REGION=$Region",
    "ARTIFACT_STORE=s3"
)

if ($env:MODEL_ID) { $CommonEnv += "MODEL_ID=$($env:MODEL_ID)" }
else { $CommonEnv += "MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0" }

# Demo uses a separate artifact bucket so client demos never mix with teammate runs.
if ($Demo -or ($TargetAgents | Where-Object { $_.awsName -like "*_demo" })) {
    $demoBucket = if ($env:ARTIFACT_S3_BUCKET_DEMO) { $env:ARTIFACT_S3_BUCKET_DEMO } else { "sdlc-agentic-ai-app-artifacts-demo" }
    [Environment]::SetEnvironmentVariable("ARTIFACT_S3_BUCKET", $demoBucket, "Process")
    Write-Host "Demo deploy: ARTIFACT_S3_BUCKET=$demoBucket" -ForegroundColor DarkGray
}

if ($env:ARTIFACT_S3_BUCKET) { $CommonEnv += "ARTIFACT_S3_BUCKET=$($env:ARTIFACT_S3_BUCKET)" }
if ($env:ARTIFACT_DYNAMODB_ENABLED) { $CommonEnv += "ARTIFACT_DYNAMODB_ENABLED=$($env:ARTIFACT_DYNAMODB_ENABLED)" }
if ($env:ARTIFACT_DYNAMODB_TABLE) { $CommonEnv += "ARTIFACT_DYNAMODB_TABLE=$($env:ARTIFACT_DYNAMODB_TABLE)" }

if (-not $env:ARTIFACT_S3_BUCKET) {
    Write-Error "ARTIFACT_S3_BUCKET is not set. Add it to .env.local or export it before deploy."
}

if ($env:CODING_MODEL_ID) { $CommonEnv += "CODING_MODEL_ID=$($env:CODING_MODEL_ID)" }
if ($env:BEDROCK_READ_TIMEOUT) { $CommonEnv += "BEDROCK_READ_TIMEOUT=$($env:BEDROCK_READ_TIMEOUT)" }
if ($env:SDLC_AGENT_TIMEOUT_SEC) { $CommonEnv += "SDLC_AGENT_TIMEOUT_SEC=$($env:SDLC_AGENT_TIMEOUT_SEC)" }
if ($env:SDLC_DEVELOPER_AGENT_TIMEOUT_SEC) { $CommonEnv += "SDLC_DEVELOPER_AGENT_TIMEOUT_SEC=$($env:SDLC_DEVELOPER_AGENT_TIMEOUT_SEC)" }
if ($env:SDLC_DEVELOPER_RETRY_ATTEMPTS) { $CommonEnv += "SDLC_DEVELOPER_RETRY_ATTEMPTS=$($env:SDLC_DEVELOPER_RETRY_ATTEMPTS)" }
if ($env:DEVELOPER_AGENT_FALLBACK_MODEL_ID) {
    $CommonEnv += "DEVELOPER_AGENT_FALLBACK_MODEL_ID=$($env:DEVELOPER_AGENT_FALLBACK_MODEL_ID)"
} else {
    $fallbackModel = if ($env:MODEL_ID) { $env:MODEL_ID } else { "us.anthropic.claude-sonnet-4-6" }
    $CommonEnv += "DEVELOPER_AGENT_FALLBACK_MODEL_ID=$fallbackModel"
}
if ($env:DEVELOPER_AGENT_AUTO_VALIDATE) { $CommonEnv += "DEVELOPER_AGENT_AUTO_VALIDATE=$($env:DEVELOPER_AGENT_AUTO_VALIDATE)" }
if ($env:DEVELOPER_AGENT_AUTO_VALIDATE_PYTEST) { $CommonEnv += "DEVELOPER_AGENT_AUTO_VALIDATE_PYTEST=$($env:DEVELOPER_AGENT_AUTO_VALIDATE_PYTEST)" }

# Per-agent secrets forwarded from .env.local (never commit these values).
$AgentSecretKeys = @{
    product_agent          = @("ATLASSIAN_MCP_TOKEN", "ATLASSIAN_MCP_EMAIL", "ATLASSIAN_MCP_BASIC_AUTH", "ATLASSIAN_MCP_URL")
    product_agent_demo     = @("ATLASSIAN_MCP_TOKEN", "ATLASSIAN_MCP_EMAIL", "ATLASSIAN_MCP_BASIC_AUTH", "ATLASSIAN_MCP_URL")
    architect_agent        = @()
    architect_agent_demo   = @()
    database_agent         = @()
    database_agent_demo    = @()
    developer_agent        = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH")
    developer_agent_demo   = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH")
    gitlab_agent           = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH", "GITLAB_MCP_URL", "GITLAB_MCP_HTTP_URL", "GITLAB_MCP_HTTP_DIRECT_URL", "GITLAB_MCP_HTTP_BATCH_SIZE", "GITLAB_APPS_REPO")
    gitlab_agent_demo      = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH", "GITLAB_MCP_URL", "GITLAB_MCP_HTTP_URL", "GITLAB_MCP_HTTP_DIRECT_URL", "GITLAB_MCP_HTTP_BATCH_SIZE", "GITLAB_APPS_REPO")
    orchestrator_agent     = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH")
    orchestrator_agent_demo = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH")
    orchestrator_agent_vpc = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_PROJECT_PATH")
    security_agent         = @()
    devops_agent           = @()
    qa_agent               = @("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_API_URL", "GITLAB_MCP_URL", "GITLAB_MCP_HTTP_URL", "GITLAB_MCP_HTTP_DIRECT_URL", "GITLAB_MCP_HTTP_BATCH_SIZE")
    web_crawler_agent      = @("FIRECRAWL_API_KEY")
}

# RDS creds: orchestrator applies SQL; developer schema_parity introspects the same DB.

$RdsEnvKeys = @(
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
$AgentsNeedingRdsEnv = @(
    "orchestrator_agent",
    "orchestrator_agent_vpc",
    "orchestrator_agent_demo",
    "developer_agent",
    "developer_agent_demo"
)

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

    if ($agent.node) {
        & (Join-Path $PSScriptRoot "sync-agentcore-dockerfiles.ps1") | Out-Null
        $agentDockerfile = Join-Path $RepoRoot ".bedrock_agentcore\$awsName\Dockerfile"
        $rootDockerfile = Join-Path $RepoRoot "Dockerfile"
        if (Test-Path $agentDockerfile) {
            Copy-Item -Path $agentDockerfile -Destination $rootDockerfile -Force
            Write-Host "Using agent Dockerfile for CodeBuild: $agentDockerfile" -ForegroundColor DarkGray
        }
    }

    if ($SkipConfigure -and -not (Test-AgentRegisteredInYaml -AwsName $awsName)) {
        Write-Warning "Skipping $awsName - not registered in .bedrock_agentcore.yaml. First-time setup:`n  .\scripts\deploy-agentcore-agents.ps1 -Agents $awsName -Configure`nThen verify source_path is 'backend' (not deploy/agentcore) before redeploying with -SkipConfigure."
        $DeploySkipped += $awsName
        if ($agent.node) { & (Join-Path $PSScriptRoot "sync-agentcore-dockerfiles.ps1") | Out-Null }
        continue
    }

    if ($awsName -eq "developer_agent" -or $awsName -eq "developer_agent_demo") {
        Write-Host "Publishing target-apps/_template to S3 (AgentCore has no local _template copy)..." -ForegroundColor DarkGray
        $publishScript = Join-Path $PSScriptRoot "publish-template-to-s3.py"
        python $publishScript
        if ($LASTEXITCODE -ne 0) {
            $DeployFailures += $awsName
            Write-Warning "Template publish failed for $awsName - skipping agent deploy."
            continue
        }
    }

    # Pin specialist ARNs for orchestrators from runtimes*.json so sdlcPipeline peers
    if (($awsName -eq "orchestrator_agent" -or $awsName -eq "orchestrator_agent_vpc") -and -not $ConfigureOnly) {
        $devRuntimes = Join-Path $RepoRoot "config\agentcore\runtimes.json"
        if (Test-Path $devRuntimes) {
            $peerMap = python -c @"
            
import json
from pathlib import Path
data = json.loads(Path(r'$devRuntimes').read_text(encoding='utf-8'))
agents = data.get('agents') or {}
peers = {}
for name in (data.get('sdlcPipeline') or data.get('mvpPipeline') or []):
    if name == 'orchestrator-agent':
        continue
    arn = (agents.get(name) or {}).get('runtimeArn') or ''
    if arn:
        peers[name] = arn
print(json.dumps(peers, separators=(',', ':')))
"@
            if ($peerMap -and $peerMap -ne "{}") {
                $agent.extra = @($agent.extra) + @("AGENTCORE_PEER_RUNTIME_ARNS=$peerMap")
                Write-Host "Orchestrator sdlcPipeline peers: $peerMap" -ForegroundColor DarkGray
            } else {
                Write-Warning "runtimes.json sdlcPipeline has no specialist ARNs - deploy specialists first, then re-run orchestrator_agent."
            }
        }
    }

    # Demo orchestrator
    if ($awsName -eq "orchestrator_agent_demo" -and -not $ConfigureOnly) {
        $syncDemo = Join-Path $PSScriptRoot "sync-runtimes-demo.py"
        if (Test-Path $syncDemo) {
            Write-Host "Refreshing config/agentcore/runtimes.demo.json from AWS..." -ForegroundColor DarkGray
            python $syncDemo --region $Region
        }
        $demoRuntimes = Join-Path $RepoRoot "config\agentcore\runtimes.demo.json"
        if (Test-Path $demoRuntimes) {
            $peerMap = python -c @"

import json, sys
from pathlib import Path
data = json.loads(Path(r'$demoRuntimes').read_text(encoding='utf-8'))
peers = {}
for name, entry in (data.get('agents') or {}).items():
    arn = (entry or {}).get('runtimeArn') or ''
    if arn and name != 'orchestrator-agent':
        peers[name] = arn
print(json.dumps(peers, separators=(',', ':')))
"@
            if ($peerMap -and $peerMap -ne "{}") {
                $agent.extra = @($agent.extra) + @("AGENTCORE_PEER_RUNTIME_ARNS=$peerMap")
                Write-Host "Demo orchestrator peers: $peerMap" -ForegroundColor DarkGray
            } else {
                Write-Warning "runtimes.demo.json has no specialist ARNs yet - deploy specialists first, then re-run orchestrator_agent_demo."
            }
        }
    }

    $deployArgs = @("deploy", "--agent", $awsName, "--env", "AGENTCORE_AGENT=$bundle")
    $envBlock = $CommonEnv + $agent.extra
    if ($AgentSecretKeys.ContainsKey($awsName)) {
        $envBlock += Get-EnvPairsForKeys -Keys $AgentSecretKeys[$awsName]
    }
    if ($AgentsNeedingRdsEnv -contains $awsName) {
        $envBlock += Get-EnvPairsForKeys -Keys $RdsEnvKeys
    }
    if (($awsName -eq "gitlab_agent" -or $awsName -eq "gitlab_agent_demo") -and $GitLabAgentMcpEnv.Count -gt 0) {
        $envBlock = @($envBlock | Where-Object {
            $_ -notlike "GITLAB_MCP_URL=*" -and
            $_ -notlike "GITLAB_MCP_HTTP_DIRECT_URL=*" -and
            $_ -notlike "GITLAB_MCP_HTTP_BATCH_SIZE=*"
        }) + $GitLabAgentMcpEnv
    }
    foreach ($item in $envBlock) {
        if (($awsName -eq "gitlab_agent" -or $awsName -eq "gitlab_agent_demo") -and $item -like "MODEL_ID=*") {
            continue
        }
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
    } else {
        $ecrRepo = "bedrock-agentcore-$awsName"
        if (-not $env:AWS_PROFILE) {
            $env:AWS_PROFILE = "eks-admin-user"
        }

        python -c @"
import os, boto3, sys
profile = os.environ.get('AWS_PROFILE') or 'eks-admin-user'
ecr = boto3.Session(profile_name=profile, region_name='$Region').client('ecr')
imgs = ecr.describe_images(repositoryName='$ecrRepo')['imageDetails']
tagged = [i for i in imgs if i.get('imageTags') and 'latest' not in i['imageTags']]
tagged.sort(key=lambda i: i['imagePushedAt'], reverse=True)
if not tagged:
    sys.exit(0)
vtag = tagged[0]['imageTags'][0]
resp = ecr.batch_get_image(repositoryName='$ecrRepo', imageIds=[{'imageTag': vtag}])
m = resp['images'][0]['imageManifest']
try:
    ecr.put_image(repositoryName='$ecrRepo', imageTag='latest', imageManifest=m)
    print('  Tagged ' + vtag + ' as :latest in $ecrRepo')
except ecr.exceptions.ImageAlreadyExistsException:
    print('  :latest already current in $ecrRepo')
"@

        python -c @"
import json, os, boto3, sys
from pathlib import Path
profile = os.environ.get('AWS_PROFILE') or 'eks-admin-user'
cc = boto3.Session(profile_name=profile, region_name='$Region').client('bedrock-agentcore-control')
rts = cc.list_agent_runtimes(maxResults=100)['agentRuntimes']
rt = next((r for r in rts if r['agentRuntimeName'] == '$awsName'), None)
if rt is None:
    print('  WARNING: runtime $awsName not found; lifecycle not updated')
    sys.exit(0)
full = cc.get_agent_runtime(agentRuntimeId=rt['agentRuntimeId'])
env = dict(full.get('environmentVariables') or {})


if '$awsName' in ('orchestrator_agent', 'orchestrator_agent_vpc'):
    cfg = Path(r'$RepoRoot') / 'config' / 'agentcore' / 'runtimes.json'
    if cfg.is_file():
        data = json.loads(cfg.read_text(encoding='utf-8'))
        agents = data.get('agents') or {}
        peers = {}
        for name in (data.get('sdlcPipeline') or data.get('mvpPipeline') or []):
            if name == 'orchestrator-agent':
                continue
            arn = (agents.get(name) or {}).get('runtimeArn') or ''
            if arn:
                peers[name] = arn
        if peers:
            env['AGENTCORE_PEER_RUNTIME_ARNS'] = json.dumps(peers, separators=(',', ':'))
            print('  Peer ARNs re-applied from runtimes.json sdlcPipeline (' + str(len(peers)) + ' peers)')

if '$awsName' == 'orchestrator_agent_demo':
    demo_cfg = Path(r'$RepoRoot') / 'config' / 'agentcore' / 'runtimes.demo.json'
    if demo_cfg.is_file():
        data = json.loads(demo_cfg.read_text(encoding='utf-8'))
        peers = {}
        for name, entry in (data.get('agents') or {}).items():
            arn = (entry or {}).get('runtimeArn') or ''
            if arn and name != 'orchestrator-agent':
                peers[name] = arn
        if peers:
            env['AGENTCORE_PEER_RUNTIME_ARNS'] = json.dumps(peers, separators=(',', ':'))
            env['AGENTCORE_RUNTIMES_CONFIG'] = 'config/agentcore/runtimes.demo.json'
            print('  Peer ARNs re-applied from runtimes.demo.json (' + str(len(peers)) + ' peers)')
kwargs = dict(
    agentRuntimeId=rt['agentRuntimeId'],
    agentRuntimeArtifact=full['agentRuntimeArtifact'],
    roleArn=full['roleArn'],
    networkConfiguration=full['networkConfiguration'],
    lifecycleConfiguration={'idleRuntimeSessionTimeout': 3600, 'maxLifetime': 28800},
    environmentVariables=env,
)
if full.get('protocolConfiguration'):
    kwargs['protocolConfiguration'] = full['protocolConfiguration']
cc.update_agent_runtime(**kwargs)
print('  Lifecycle re-applied: idle=3600s maxLifetime=28800s for $awsName')
"@
    }

    if ($agent.node) {
        & (Join-Path $PSScriptRoot "sync-agentcore-dockerfiles.ps1") | Out-Null
    }
}

if ($DeploySkipped.Count -gt 0) {
    Write-Host "`nSkipped (not configured): $($DeploySkipped -join ', ')" -ForegroundColor Yellow
}
if ($DeployFailures.Count -gt 0) {
    Write-Error "Deploy failed for: $($DeployFailures -join ', ')"
}

if ($Demo -or ($TargetAgents | Where-Object { $_.awsName -like "*_demo" })) {
    $syncDemo = Join-Path $PSScriptRoot "sync-runtimes-demo.py"
    if (Test-Path $syncDemo) {
        python $syncDemo --region $Region
    }
    Write-Host "`nDemo: update/check config/agentcore/runtimes.demo.json (dev runtimes.json unchanged)." -ForegroundColor Green
} else {
    Write-Host "`nUpdate config/agentcore/runtimes.json with runtime ARNs and invoke URLs." -ForegroundColor Green
}