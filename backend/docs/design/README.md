# Solution design (per feature)

**Path pattern:** `docs/design/<target-app>.md` (e.g. `docs/design/rag-pdf-system.md`, `docs/design/finops-web-app.md`).

Each architect run for a feature writes its **own** file so FinOps, RAG, and other briefs do not overwrite each other.

Legacy single file `docs/design/design.md` may still exist from older runs; new pipeline uses per-feature paths only.

## Who reads what

| Agent | Reads via | Uses from design.md | Also uses |
|-------|-----------|---------------------|-----------|
| **database-agent** | `db_read_file(designDocPath)` | **§3 Data model**, **§6 DB delivery** | `targetApp` → writes `target-apps/<app>/db/sql/` |
| **developer-agent** | `dev_read_file(designDocPath)` | **§4 API surface**, **§5 Rules** | `targetApp` → writes `target-apps/<app>/` |
| Humans | Editor | §1–2 overview | PNG in `docs/generated-diagrams/`, PRD in `docs/PRD/` |

The **PNG diagram** is not fed into the model as image bytes — only the file path appears in context. Agents rely on **design.md tables** for schemas and APIs.

## Section layout (compact)

1. Summary  
2. Stack (≤6 rows)  
3. **Data model** → database-agent  
4. **API surface** → developer-agent  
5. **Rules** (auth, audit) → developer-agent  
6. **DB delivery** (migration order, seeds) → database-agent  

Target size: **~90 lines**. Details belong in the PRD; design.md is the implementation contract.

## Chain (one command)

```powershell
.\scripts\run-sdlc-local.ps1 -Feature rag-pdf-system -InputFile inputs\rag-pdf-system.txt
```

Handoff JSON: `agents/pipeline/<feature>.context.json` includes `designDocPath`: `docs/design/<feature>.md`.

## Env

| Variable | Effect |
|----------|--------|
| `ARCHITECT_DESIGN_OUTPUT_PATH` | Override design path for all runs (optional) |
| `ARCHITECT_SKIP_DESIGN` | Skip design generation |
