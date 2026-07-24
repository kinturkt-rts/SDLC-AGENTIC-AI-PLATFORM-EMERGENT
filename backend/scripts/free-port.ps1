# Kill whatever process (if any) is bound to a local TCP port, so a fresh
# `npm run dev` lands on the expected port (5173) instead of bouncing to 5174+
# because a forgotten dev server from a previous test session is still holding it.
#
# Safe to run even when the port is already free - it's a no-op in that case.
#
# Usage (from backend/, or anywhere):
#   .\scripts\free-port.ps1                # defaults to 5173 (Vite default)
#   .\scripts\free-port.ps1 -Port 8000

param(
    [int] $Port = 5173
)

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host "Port $Port is already free." -ForegroundColor DarkGray
    return
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $pids) {
    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    $label = if ($proc) { "$($proc.ProcessName) (PID $processId)" } else { "PID $processId" }
    Write-Host "Port $Port is in use by $label - stopping it ..." -ForegroundColor Yellow
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}

Write-Host "Port $Port freed." -ForegroundColor Green
