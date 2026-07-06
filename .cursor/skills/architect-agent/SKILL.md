---
name: architect-agent
description: Produces architecture diagrams (AWS Diagram MCP), per-feature docs/design/<app>.md, and ADR notes. Use when working on architect-agent, system design, or docs/diagrams.
---

# Architect Agent

## What this agent does

Designs system architecture:

1. **PNG diagram** via AWS Diagram MCP → `docs/generated-diagrams/`
2. **Solution design** → `docs/design/<target-app>.md` (handoff for database-agent + developer-agent)
3. Short **ADR** bullets in the terminal response

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/architect-agent/architect_agent.py` |
| System prompt | `ARCHITECT_SYS_PROMPT` + `DESIGN_SYS_PROMPT` in same file |
| A2A port | 9102 |

## Context handoff (downstream agents)

```json
{
  "prdPath": "docs/PRD/my-feature.md",
  "productAgentOutput": "...",
  "designDocPath": "docs/design/finops-web-app.md",
  "architectSummary": "<section 1 excerpt>",
  "diagramPaths": ["docs/generated-diagrams/my-feature.png"],
  "targetApp": "my-service"
}
```

## MCP tools

Configured in `.cursor/mcp.json` → `awslabs.aws-diagram-mcp-server`. Key flow:

1. `awsdiagram_get_diagram_examples`
2. `awsdiagram_list_icons`
3. `awsdiagram_generate_diagram` — use **absolute** `filename` from context

See `config/mcp/servers.json` → `aws-diagram`. Requires Graphviz on PATH.

## Env vars

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHITECT_DIAGRAM_OUTPUT_DIR` | `docs/diagrams` | PNG output folder |
| `ARCHITECT_DESIGN_OUTPUT_PATH` | `docs/design/<targetApp>.md` | Override design markdown path |
| `ARCHITECT_SKIP_DESIGN` | — | Set `1` to skip design doc generation |

## Run standalone

```bash
python agents/architect-agent/architect_agent.py \
  --target-app finops-web-app \
  --context-file agents/pipeline/finops-web-app.context.json

# Diagram only (faster)
python agents/architect-agent/architect_agent.py --task "..." --skip-design
```

## Cursor workflow

- Use only icons returned by `list_icons`.
- Prefer absolute diagram paths; avoid relative filenames (creates `generated-diagrams/`).
- Pass `prdPath` in context so `docs/design/<targetApp>.md` references FR/NFR IDs.
