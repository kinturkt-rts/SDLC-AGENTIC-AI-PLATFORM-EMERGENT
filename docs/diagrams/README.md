# Architecture diagrams

PNG files produced by **architect-agent** (AWS Diagram MCP).

The architect also writes **`docs/design/<target-app>.md`** (per-feature solution design for database-agent and developer-agent). ADR bullets in the terminal are optional; pipeline handoff uses the **PNG**, **design doc**, and the PRD in `docs/PRD/`.

| Setting | Default |
|---------|---------|
| `ARCHITECT_DIAGRAM_OUTPUT_DIR` | `docs/diagrams/generated-diagrams` |
| CLI | `--diagram-name <basename>` → `<basename>.png` |

**Canonical layout:** all PNG files live in `generated-diagrams/`, e.g. `docs/diagrams/generated-diagrams/rag-app-streamlit.png`. Do not store diagrams in the parent `docs/diagrams/` folder.

The AWS Diagram MCP server writes into this subdirectory of the workspace; architect-agent, `run-sdlc.ps1`, and pipeline context JSON all use this path. The architect normalizes any nested fallback paths after each run.