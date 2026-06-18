---
name: qa-agent
description: Test plans, pytest coverage, and GitLab MR test feedback. Use when working on qa-agent, tests/, or coverage goals.
---

# QA Agent

## What this agent does

Designs test plans and pytest cases; posts results on GitHub pull requests (or GitLab MR when configured).

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/qa-agent/qa_agent.py` (Strands + scoped tools + A2A) |
| System prompt | `QA_SYS_PROMPT` in `qa_agent.py` |
| Tools | `qa_list_tree`, `qa_read_file`, `qa_write_file`, `qa_run_pytest`, `qa_run_coverage` |
| A2A port | 9104 |
| Test queries | `agents/qa-agent/test_queries.txt` |

## MCP tools (optional)

- **GitHub**: PR review comment when `-WithGithub` pipeline ran devops-agent first
- **GitLab**: legacy MR comment when `mergeRequestIid` in context

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
| `env_issue` | Report missing install/cwd steps |

## Cursor workflow

- Prefer `pytest` under `target-apps/<service>/tests/`.
- Tie tests to Jira keys from task context when present.