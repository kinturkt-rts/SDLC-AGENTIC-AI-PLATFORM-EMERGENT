# Copy deploy/agentcore/Dockerfile to backend/Dockerfile and every .bedrock_agentcore/*/Dockerfile.
# Patches AGENTCORE_AGENT per agent folder. Run from backend/ after editing the canonical Dockerfile.
$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
$Canonical = Join-Path $BackendRoot "deploy\agentcore\Dockerfile"

if (-not (Test-Path $Canonical)) {
    Write-Error "Missing canonical Dockerfile: $Canonical"
}

function Get-AgentCoreBundleFromFolder {
    param([string] $FolderName)
    if ($FolderName -eq "orchestrator_agent_vpc") {
        return "orchestrator-agent"
    }
    return ($FolderName -replace '_', '-')
}

# Agents that need Node.js/npx at runtime (Atlassian mcp-remote, Firecrawl MCP, etc.)
$NodeInstallAgents = @("product_agent", "web_crawler_agent")

function Set-DockerfileAgentArg {
    param(
        [string] $DockerfilePath,
        [string] $Bundle
    )
    $content = Get-Content -Path $DockerfilePath -Raw -Encoding UTF8
    $content = $content -replace 'ARG AGENTCORE_AGENT=orchestrator-agent', "ARG AGENTCORE_AGENT=$Bundle"
    Set-Content -Path $DockerfilePath -Value $content -Encoding UTF8 -NoNewline
}

function Set-DockerfileInstallNode {
    param(
        [string] $DockerfilePath,
        [bool] $InstallNode
    )
    $content = Get-Content -Path $DockerfilePath -Raw -Encoding UTF8
    $conditionalBlock = @'
RUN if [ "$INSTALL_NODE" = "true" ]; then \
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
      && apt-get install -y --no-install-recommends nodejs \
      && rm -rf /var/lib/apt/lists/*; \
    fi
'@
    $unconditionalBlock = @'
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g firecrawl-mcp \
    && rm -rf /var/lib/apt/lists/*
'@
    if ($InstallNode) {
        $content = $content -replace [regex]::Escape($conditionalBlock), $unconditionalBlock
        $content = $content -replace 'ARG INSTALL_NODE=false', 'ARG INSTALL_NODE=true'
    } else {
        $content = $content -replace [regex]::Escape($unconditionalBlock), $conditionalBlock
        $content = $content -replace 'ARG INSTALL_NODE=true', 'ARG INSTALL_NODE=false'
    }
    Set-Content -Path $DockerfilePath -Value $content -Encoding UTF8 -NoNewline
}

$targets = @(
    @{ Path = (Join-Path $BackendRoot "Dockerfile"); Bundle = "orchestrator-agent"; InstallNode = $false }
)
$agentcoreDir = Join-Path $BackendRoot ".bedrock_agentcore"
if (Test-Path $agentcoreDir) {
    Get-ChildItem -Path $agentcoreDir -Directory | ForEach-Object {
        $folderName = $_.Name
        $targets += @{
            Path = Join-Path $_.FullName "Dockerfile"
            Bundle = Get-AgentCoreBundleFromFolder $folderName
            InstallNode = ($NodeInstallAgents -contains $folderName)
        }
    }
}

foreach ($target in $targets) {
    Copy-Item -Path $Canonical -Destination $target.Path -Force
    Set-DockerfileAgentArg -DockerfilePath $target.Path -Bundle $target.Bundle
    if ($null -ne $target.InstallNode) {
        Set-DockerfileInstallNode -DockerfilePath $target.Path -InstallNode ([bool]$target.InstallNode)
    }
    $nodeLabel = if ($target.InstallNode) { ", INSTALL_NODE=true" } else { "" }
    Write-Host "Synced $($target.Path) (AGENTCORE_AGENT=$($target.Bundle)$nodeLabel)"
}

Write-Host "Done. Agent images: no gitlab-mcp binary unless INSTALL_GITLAB_MCP_BINARY=true."
Write-Host "ECS MCP service: deploy/gitlab-mcp-server/Dockerfile -> bedrock-agentcore-gitlab_agent:gitlab_mcp"
