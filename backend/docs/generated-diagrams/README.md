# Architecture diagrams

PNG files produced by **architect-agent** (AWS Diagram MCP) and platform documentation.

The architect also writes **`docs/design/<target-app>.md`** (per-feature solution design for database-agent and developer-agent). Pipeline handoff uses the **PNG**, **design doc**, and the PRD in `docs/PRD/`.

| Setting | Default |
|---------|---------|
| `ARCHITECT_DIAGRAM_OUTPUT_DIR` | `docs/generated-diagrams` |
| CLI | `--diagram-name <basename>` → `<basename>.png` |

**Canonical layout:** all PNG files live here, e.g. `docs/generated-diagrams/rag-app-streamlit.png`.

Legacy runs may still reference `docs/diagrams/generated-diagrams/` in context JSON; `pipeline_context.py` normalizes those paths on load.

The AWS Diagram MCP server writes into this folder; architect-agent, `run-sdlc-local.ps1`, and pipeline context JSON all use this path.
