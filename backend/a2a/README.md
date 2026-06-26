# Agent-to-agent (A2A)

Specialist agents expose an **A2A HTTP server** (Strands `A2AServer`) so peers can discover and message each other.

| Path | Purpose |
|------|---------|
| `agent-registry.json` | Base URLs and ports for all agents |
| `agent-cards/*.json` | Static capability cards (one per registered agent) |

Registered agents: orchestrator, product, architect, developer, qa, devops, security, database, web-crawler. Jira is handled by product-agent (no separate card).

## Run an agent as A2A server

```bash
python agents/product-agent/product_agent.py --serve-a2a --port 9101
```

Live card: `http://127.0.0.1:9101/.well-known/agent-card.json`

## Cross-agent calls

When multiple agents are running, each Strands agent also loads **A2A client tools** (`a2a_send_message`, `a2a_list_discovered_agents`) pointed at peers in `agent-registry.json`.

## BullMQ

Queue envelopes remain `agents/_shared/schemas.py` (`AgentMessage`, `TaskPayload`). The TypeScript orchestrator can publish tasks; agents consume via CLI or future queue workers.
