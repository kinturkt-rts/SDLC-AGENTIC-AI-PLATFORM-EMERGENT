---
name: orchestrator-agent
description: Routes work to specialist agents via A2A. Use when working on orchestrator-agent, delegation, or multi-agent flows.
---

# Orchestrator Agent

## What this agent does

Receives work items, plans delegation, and coordinates hand-offs to product- (incl. Jira), architect-, database-, web-crawler-, developer-, qa-, devops-, and security-agents via A2A tools.

## Runtime

| Item | Location |
|------|----------|
| Code | `agents/orchestrator-agent/orchestrator_agent.py` |
| System prompt | `ORCHESTRATOR_SYS_PROMPT` in `orchestrator_agent.py` |
| A2A port | 9100 |

## A2A tools

- `a2a_send_message`
- `a2a_list_discovered_agents`

Registry: `agents/_shared/a2a_registry.py`, cards under `a2a/`.

## Run standalone

```bash
python agents/orchestrator-agent/orchestrator_agent.py --task "End-to-end checkout feature"
```

## Cursor workflow

Return a short plan plus delegation results; prefer smallest set of specialist agents needed.