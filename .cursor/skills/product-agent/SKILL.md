---
name: product-agent
description: Converts business requirements into Jira epics and user stories via Atlassian MCP. Use when working on product-agent, backlog creation, or Jira ticket workflows.
---

# Product Agent

## What this agent does

Converts plain-language business requirements into Jira epics and user stories, creates tickets via Atlassian MCP, and returns a summary with issue keys.

## Queue contract

| Queue | Direction | Message type |
|-------|-----------|--------------|
| `product` | consume | `task.assign` |
| `results` | publish | `task.result` / `task.error` |

## Input — TaskPayload

```json
{
  "taskId": "uuid",
  "description": "Build a payment checkout flow supporting cards and UPI",
  "context": {
    "projectKey": "PAY",
    "sprintId": 12
  }
}
```

## Output — ResultPayload

```json
{
  "taskId": "uuid",
  "status": "success",
  "output": "## Epic\nPAY-42 Checkout Flow\n\n## User Stories\n..."
}
```

## MCP tools (Atlassian)

Configured in `.cursor/mcp.json` → `atlassian`. Key operations:

- `create_issue` — Epic or Story
- `get_issue` / `update_issue`
- `search_issues` — JQL
- `link_issues` — Story → Epic

## Env vars

| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | Bedrock (Strands) |
| `MODEL_ID` | Bedrock model (e.g. `anthropic.claude-sonnet-4-6`) |
| `ATLASSIAN_MCP_TOKEN` | OAuth token for Atlassian MCP |
| `REDIS_HOST` / `REDIS_PORT` | BullMQ (default `localhost:6379`) |

## Run standalone

```bash
pip install -r requirements.txt
python agents/product-agent/product_agent.py --task "Build checkout flow" --project PAY --sprint 5
```

## Jira story title style

Default: **concise** (matches enterprise PM boards — short prefixed summary).

| Style | Summary example | User story location |
|-------|-----------------|---------------------|
| `concise` (default) | `Tech - CloudWatch - Incident summary from logs` | Issue description |
| `user-story` | `As an SRE, I want ... so that ...` | Summary (may truncate) |

```bash
# PRD + backlog with PM-style titles (default)
python agents/product-agent/product_agent.py \
  --input-file brief.txt --prd-name my-feature --project SAAP \
  --allow-writes --create-jira-tickets

# Legacy full user-story summaries
python agents/product-agent/product_agent.py ... --story-title-style user-story
```

Env override: `JIRA_STORY_TITLE_STYLE=concise|user-story`

## System prompt

`agents/product-agent/product_agent.py` → `PRODUCT_SYS_PROMPT`.