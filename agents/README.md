# Agents (AWS Strands + A2A)

| Agent | Code layout | MCP |
|-------|-------------|-----|
| **product-agent** | `product-agent/product_agent.py` | Atlassian (`mcp-remote`) — PRD + Jira |
| **architect-agent** | `architect-agent/architect_agent.py` | AWS Diagram MCP |
| **web-crawler-agent** | `web-crawler/web_crawler_agent.py` | Firecrawl MCP + Postgres MCP (optional) |
| **database-agent** | `database-agent/database_agent.py` | Postgres MCP + MongoDB MCP |
| **developer-agent** | `developer-agent/developer_agent.py` | Scoped file tools (writes under `target-apps/`) |
| **orchestrator-agent** | `orchestrator-agent/orchestrator_agent.py` | A2A peers via `_shared/runner.py` |
| **qa-agent** | `qa-agent/qa_agent.py` | SDLC QA: pytest + Postman + Playwright MCP (optional) |
| **devops-agent** | `devops-agent/devops_agent.py` | GitLab via `_shared/runner.py` |
| **security-agent** | `security-agent/security_agent.py` | A2A peers via `_shared/runner.py` |

| Agent | A2A port |
|-------|----------|
| orchestrator-agent | 9100 |
| product-agent | 9101 |
| architect-agent | 9102 |
| developer-agent | 9103 |
| qa-agent | 9104 |
| devops-agent | 9105 |
| security-agent | 9106 |
| database-agent | 9108 |
| web-crawler-agent | 9109 |

**Jira** is owned by **product-agent** (not a separate agent). Port 9107 is reserved for a future `jira-agent` if split out later.

## System prompts

Each agent defines its prompt in its module as a string constant (e.g. `DEVELOPER_SYS_PROMPT`, `QA_SYS_PROMPT`).
Agents that use `_shared/runner.py` pass `system_prompt=` to `entrypoint()`.

## Adding a new agent

1. Create `agents/<name>/<name>_agent.py` with `AGENT_NAME`, `<NAME>_SYS_PROMPT`, and either:
   - a custom `Agent` + tools (see `developer_agent.py`), or
   - `entrypoint(AGENT_NAME, system_prompt=..., mcp_names=..., default_port=...)` from `_shared/runner.py`
2. Register the A2A port in `a2a/agent-registry.json` and add an agent card under `a2a/agent-cards/`
3. Add a Cursor skill under `.cursor/skills/<name>/SKILL.md` if needed

## Run (CLI)

```bash
pip install -r requirements.txt
# .env: AWS_*, MODEL_ID, ATLASSIAN_MCP_TOKEN (product-agent), GITLAB_* (qa/devops),
#       MongoDB MCP credentials (MDB_MCP_*) when using database-agent

python agents/product-agent/product_agent.py --task "Checkout flow" --project PAY
```

## Run (A2A server)

```bash
python agents/product-agent/product_agent.py --serve-a2a
```

## Shared code

- `_shared/runner.py` — CLI + A2A for thin agents (requires inline `system_prompt`)
- `_shared/mcp_clients.py` — GitLab stdio; Atlassian for **product-agent**
- `_shared/schemas.py` — BullMQ envelopes
- `a2a/` — registry + agent cards

```bash
python agents/architect-agent/architect_agent.py --context-file agents/pipeline/finops-web-app.context.json --task "..."
python agents/web-crawler/web_crawler_agent.py --target-app finops-web-app --with-postgres --task "Scrape https://example.com/pricing"
python agents/database-agent/database_agent.py --context-file agents/pipeline/finops-web-app.context.json
# optional: --with-postgres to apply SQL to RDS
python agents/developer-agent/developer_agent.py --target-app finops-web-app --context-file agents/pipeline/finops-web-app.context.json
python agents/qa-agent/qa_agent.py --target-app test-medium-app --context-file agents/pipeline/test-medium-app.context.json
```
