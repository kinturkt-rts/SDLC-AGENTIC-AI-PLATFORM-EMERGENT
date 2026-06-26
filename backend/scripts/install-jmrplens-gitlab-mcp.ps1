# Download jmrplens/gitlab-mcp-server release binary into repo bin/ (GitLab Free MCP).
$ErrorActionPreference = "Stop"

$Version = "v2.2.1"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$BinDir = Join-Path $RepoRoot "bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$Asset = if ([Environment]::Is64BitOperatingSystem) {
    "gitlab-mcp-server-windows-amd64.exe"
} else {
    throw "Unsupported Windows architecture for gitlab-mcp-server."
}

$Dest = Join-Path $BinDir "gitlab-mcp-server.exe"
$Url = "https://github.com/jmrplens/gitlab-mcp-server/releases/download/$Version/$Asset"

Write-Host "Downloading $Url"
Write-Host "  -> $Dest"
Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
Write-Host "Done. Reload GitLab MCP in Cursor (Settings -> Tools & MCP)."
