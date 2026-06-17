# Infrastructure (Terraform)

- `modules/` — reusable Terraform modules
- `environments/dev|staging|prod` — per-environment roots

State backend and MCP-driven Terraform workflows: see `config/mcp/servers.json` → `terraform`.