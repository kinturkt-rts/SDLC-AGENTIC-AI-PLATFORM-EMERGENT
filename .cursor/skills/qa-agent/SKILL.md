---
name: qa-agent
description: SDLC QA — test plans, pytest, Postman API runs, Playwright E2E, coverage. Use when working on qa-agent, tests/, or QA reports.
---

# QA Agent

## What this agent does

Runs SDLC-style QA after developer-agent:

1. **Test planning** — map PRD/design to `TEST_PLAN.md`
2. **Unit/component** — pytest baseline + edge cases
3. **API integration** — Postman MCP (`runCollection`, create/sync collections)
4. **System/E2E** — Playwright MCP when UI exists
5. **Report** — `QA_REPORT.md` + `handoff_json` for security-agent / orchestrator

GitHub publish and PR review are **not** handled here — use **github-agent**.

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/qa-agent/qa_agent.py` (Strands + scoped tools + optional MCP + A2A) |
| System prompt | `QA_SYS_PROMPT` in `qa_agent.py` |
| Built-in tools | `qa_list_tree`, `qa_read_file`, `qa_write_file`, `qa_run_pytest`, `qa_run_coverage` |
| Optional MCP | Playwright (`@playwright/mcp`), Postman (`https://mcp.postman.com/mcp`) |
| A2A port | 9104 |

## MCP prerequisites

| MCP | Env | When loaded |
|-----|-----|-------------|
| Playwright | `QA_ENABLE_PLAYWRIGHT_MCP=1` (default) | Always attempted; skipped if npx/Node unavailable |
| Postman | `POSTMAN_API_KEY` | When key is set and `QA_ENABLE_POSTMAN_MCP=1` |

Optional: `POSTMAN_WORKSPACE_ID`, `QA_API_BASE_URL` (default `http://localhost:8000`).

## Run standalone

```bash
python agents/qa-agent/qa_agent.py --target-app test-medium-app
python agents/qa-agent/qa_agent.py --serve-a2a
```

## Failure handling

| Classification | QA action |
|----------------|-----------|
| `app_bug` | Report + recommend developer-agent; do not edit `app/` |
| `test_bug` | Fix under `tests/` only, re-run pytest |
| `env_issue` | Report missing install/cwd/server steps |

## Writable paths

- `target-apps/<service>/tests/**`
- `target-apps/<service>/TEST_PLAN.md`
- `target-apps/<service>/QA_REPORT.md`

## Cursor workflow

- Prefer `pytest` under `target-apps/<service>/tests/`.
- Start API with `runCommand` from context before Postman live runs.
- Tie tests to Jira keys from task context when present.
