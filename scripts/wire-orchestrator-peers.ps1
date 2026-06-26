# Wire orchestrator-agent peer URLs from config/agentcore/runtimes.json.
param(
    [string] $ConfigPath = "config/agentcore/runtimes.json"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Test-Path $ConfigPath)) {
    throw "Missing $ConfigPath — populate invokeUrl after agentcore deploy."
}

$config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
$peerUrls = @()
foreach ($prop in $config.agents.PSObject.Properties) {
    if ($prop.Name -eq "orchestrator-agent") { continue }
    $url = $prop.Value.invokeUrl
    if ($url) { $peerUrls += $url.TrimEnd("/") }
}

if ($peerUrls.Count -eq 0) {
    Write-Warning "No invokeUrl values in $ConfigPath"
    exit 1
}

$joined = ($peerUrls -join ",")
Write-Host "AGENTCORE_A2A_PEER_URLS=$joined"
Write-Host ""
Write-Host "Deploy orchestrator with:"
Write-Host "  agentcore deploy --agent orchestrator-agent --env AGENTCORE_A2A_PEER_URLS=$joined"
