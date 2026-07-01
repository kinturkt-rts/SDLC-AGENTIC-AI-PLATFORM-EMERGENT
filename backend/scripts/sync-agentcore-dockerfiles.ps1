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

function Set-DockerfileAgentArg {
    param(
        [string] $DockerfilePath,
        [string] $Bundle
    )
    $content = Get-Content -Path $DockerfilePath -Raw -Encoding UTF8
    $content = $content -replace 'ARG AGENTCORE_AGENT=orchestrator-agent', "ARG AGENTCORE_AGENT=$Bundle"
    Set-Content -Path $DockerfilePath -Value $content -Encoding UTF8 -NoNewline
}

$targets = @(
    @{ Path = (Join-Path $BackendRoot "Dockerfile"); Bundle = "orchestrator-agent" }
)
$agentcoreDir = Join-Path $BackendRoot ".bedrock_agentcore"
if (Test-Path $agentcoreDir) {
    Get-ChildItem -Path $agentcoreDir -Directory | ForEach-Object {
        $targets += @{
            Path = Join-Path $_.FullName "Dockerfile"
            Bundle = Get-AgentCoreBundleFromFolder $_.Name
        }
    }
}

foreach ($target in $targets) {
    Copy-Item -Path $Canonical -Destination $target.Path -Force
    Set-DockerfileAgentArg -DockerfilePath $target.Path -Bundle $target.Bundle
    Write-Host "Synced $($target.Path) (AGENTCORE_AGENT=$($target.Bundle))"
}

Write-Host "Done. Agent images: no gitlab-mcp binary unless INSTALL_GITLAB_MCP_BINARY=true."
Write-Host "ECS MCP service: deploy/gitlab-mcp-server/Dockerfile -> scripts/push-gitlab-mcp-ecr.ps1"
