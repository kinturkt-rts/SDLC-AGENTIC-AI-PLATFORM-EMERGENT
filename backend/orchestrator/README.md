# Orchestrator (TypeScript) — planned

Central router on **BullMQ** + Redis. Will consume task envelopes from `agents/_shared/schemas.py` (Python agents publish compatible JSON).

**Not scaffolded yet.** Intended layout:

- `src/router/` — route incoming tasks to specialist agent queues
- `src/queue/` — queue definitions and workers (`product`, `developer`, `qa`, `devops`, `results`, …)

Today, run agents individually via CLI or A2A (`python agents/<name>/*_agent.py --serve-a2a`). See `docs/SDLC_PIPELINE_FLOW.md` and `scripts/run-sdlc-local.ps1` for manual pipeline chaining.
