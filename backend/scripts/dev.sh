#!/usr/bin/env bash
# Planned: start BullMQ orchestrator + A2A agent servers.
# The TypeScript orchestrator is not scaffolded yet — see orchestrator/README.md.

set -euo pipefail

echo "The BullMQ orchestrator is not implemented yet."
echo "Run agents manually, for example:"
echo "  python agents/product-agent/product_agent.py --serve-a2a --port 9101"
echo "  python agents/architect-agent/architect_agent.py --serve-a2a --port 9102"
echo ""
echo "Or chain the pipeline:"
echo "  pwsh ./scripts/run-sdlc.ps1 -Feature finops-web-app -InputFile inputs/finops-web-app.txt"
exit 1
