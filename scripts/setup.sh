#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Python deps for target-app template..."
pip install -r target-apps/_template/requirements.txt 2>/dev/null || true

echo "==> Copying .env.example -> .env (if missing)..."
[ -f .env ] || cp .env.example .env

echo "==> Configure Cursor MCP: see .cursor/mcp.json and config/mcp/servers.json"
echo "==> Setup complete. Install agent runtime: pip install -r requirements.txt"
echo "==> Run pipeline: see scripts/run-sdlc.ps1 or agents/README.md"
