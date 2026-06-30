# Copy deploy/agentcore/Dockerfile to backend/Dockerfile and every .bedrock_agentcore/*/Dockerfile.
# Run from backend/ after editing the canonical Dockerfile.
$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
$Canonical = Join-Path $BackendRoot "deploy\agentcore\Dockerfile"

if (-not (Test-Path $Canonical)) {
    Write-Error "Missing canonical Dockerfile: $Canonical"
}

$targets = @(
    (Join-Path $BackendRoot "Dockerfile")
)
$agentcoreDir = Join-Path $BackendRoot ".bedrock_agentcore"
if (Test-Path $agentcoreDir) {
    Get-ChildItem -Path $agentcoreDir -Directory | ForEach-Object {
        $targets += (Join-Path $_.FullName "Dockerfile")
    }
}

foreach ($dest in $targets) {
    Copy-Item -Path $Canonical -Destination $dest -Force
    Write-Host "Synced $dest"
}

Write-Host "Done. CodeBuild uses backend/Dockerfile; per-agent folders match for local/toolkit builds."
