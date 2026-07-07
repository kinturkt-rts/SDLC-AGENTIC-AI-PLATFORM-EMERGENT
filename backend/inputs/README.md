# Project input (entry point)

Drop **plain-text requirement briefs** here — notes, email, meeting dump, half-page idea. No need for FR/NFR sections.

The product agent reads a file and expands it into a full PRD under `docs/PRD/`.

## Naming convention

Use **`inputs/<feature-slug>.txt`** where `<feature-slug>` matches `targetApp` / `--prd-name` (e.g. `finops-web-app.txt`, `rag-pdf-system.txt`, `checkout.txt`).

## Sample briefs

| File | Feature |
|------|---------|
| `checkout.txt` | Store checkout / payments |
| `aws-bedrock-agent-ops-assistant.txt` | Bedrock ops assistant |
| `finops-web-app.txt` | FinOps web app |
| `rag-pdf-system.txt` | RAG PDF system (original brief — OpenSearch/S3 TBD) |
| `rag-app-streamlit.txt` | RAG PDF + **pgvector local MVP** + **Streamlit UI** (full pipeline test) |
| `meeting-assistant.txt` | AI meeting scheduler + reminders (demo pipeline) |
| `incident-triage-bot.txt` | On-call log triage bot (minimal, read-only) |
| `release-notes-bot.txt` | Release notes drafter (Bedrock + Postgres + **Streamlit** — medium E2E test) |
| `standup-tracker.txt` | Sprint standup tracker (Bedrock + Postgres + **Streamlit** -- medium E2E test) |
| `team-faq-bot.txt` | Lightweight FAQ chatbot (single text file) |
| `contacts-api.txt` | Contact Directory Postgres CRUD + API-key auth-no JWT) |

## Hard apps — pipeline stress tests (Tier 9–11)

These briefs are **hybrid**: a short client story at the top, then **full agent spec** (DDL, API tables,
state machines, RBAC, tests) comparable to `inventory-app.txt` and `meeting-action-tracker.txt`.
They are intentionally harder than medium E2E apps (#5–#8).

| Tier | File | Feature | Complexity drivers |
|------|------|---------|-------------------|
| 9 | `employee-leave-manager.txt` | Leave + approvals + balances | State machine, balance ledger, overlap rules, half-days, manager chain |
| 9 | `vendor-compliance-tracker.txt` | Vendor compliance | Doc versioning/supersede, renewal workflow, gap detection, file ACLs |
| 10 | `field-service-dispatch.txt` | Field dispatch | SLA breach, assignment uniqueness, parts lines, role-scoped status updates |
| 10 | `audit-finding-tracker.txt` | Audit findings | Strict workflow matrix, optimistic locking, append-only history, evidence |
| 11 | `client-project-portal.txt` | Client portal | **Multi-tenant row isolation**, dual JWT personas, deliverable review flow |
| 11 | `it-asset-lifecycle.txt` | IT assets | License seat pools, offboarding alerts, encryption/masking, finance read-only |

**Difficulty scale (this repo):**
| Tier | Examples | Typical scope |
|------|----------|----------------|
| 1–2 | `test_dev.txt`, `test_medium_app.txt` | In-memory API, no DB |
| 3–4 | `contacts-api.txt`, `inventory-app.txt` | Postgres + JWT or API key |
| 5–8 | `release-notes-bot`, `customer-feedback-hub` | Bedrock + Streamlit + Postgres |
| **9–11** | Files above | Multi-entity workflows, file upload, tenant isolation, audit logs |

```powershell
# Hardest first (multi-tenant)
.\scripts\run-sdlc-local.ps1 -Feature client-project-portal -InputFile inputs\client-project-portal.txt

# Workflow + evidence
.\scripts\run-sdlc-local.ps1 -Feature audit-finding-tracker -InputFile inputs\audit-finding-tracker.txt
```

**Note:** The first draft of these files was client-email only (~30 lines) — too thin for agents.
Current versions include explicit API contracts and data models so product/architect/database/developer
agents have the same signal density as golden tests.

### Delivery profile (UI must not be dropped)

When a brief or PRD mentions **Streamlit**, product-agent writes `deliveryProfile.requiresStreamlit: true`
into `agents/pipeline/<feature>.context.json`. The pipeline then:

1. **Architect** — design §2 Stack must include Streamlit (verify step fails if omitted)
2. **Developer** — must ship `ui/streamlit_app.py` (verify step fails if missing)
3. **Developer prompt** — Pattern C is mandatory when `deliveryProfile` requires it, even if design slipped

Re-sync profile after editing inputs:  
`python agents/_shared/delivery_profile.py --context-file agents/pipeline/<feature>.context.json --sync --input-file inputs/<feature>.txt`

### Seed login guardrails (JWT apps)

Pipeline and developer-agent now verify dev seed passwords so **pytest green ≠ RDS 401**:

1. **database-agent** — real `bcrypt` hashes in `*_seed.sql` (single quotes, no dollar-quoting)
2. **`verify_seed_bcrypt.py`** — after RDS apply: SQL file check; optional `--check-rds` when `target-apps/<app>/.env` exists
3. **developer-agent** — `tests/test_seed_bcrypt.py` + `dev_validate_app` SEED_BCRYPT step
4. **Manual after pipeline:** copy `.env.example` → `.env`, then  
   `python agents/_shared/verify_seed_bcrypt.py --target-app <app> --check-rds`

## Progressive pipeline tests (agentic flow)

Use these to validate the SDLC chain in increasing complexity. Backend only (no frontend) in MVP.

| Test | Input | `targetApp` | Agents | Database |
|------|-------|-------------|--------|----------|
| **#1 Easy** | `test_dev.txt` | `test-dev` | product → architect → developer | skip |
| **#2 Medium** | `test_medium_app.txt` | `test-medium-app` | product → architect → developer | skip |
| **#3 Pattern B** | `contacts-api.txt` | `contacts-api` | product → architect → **database** → developer → **qa** | yes (API-key auth, no JWT/Bedrock) |
| **#4 Showcase** | `inventory-app.txt` | `inventory-app` | product → architect → **database** → developer → **qa** | yes (JWT login + roles) |
| **#5 Medium + UI** | `release-notes-bot.txt` | `release-notes-bot` | product → architect → **database** → developer → **qa** | yes (Bedrock + Streamlit) |
| **#6 Golden Test** | `standup-tracker.txt` | `standup-tracker` | product → architect → **database** → developer → **qa** | yes (Bedrock + Streamlit) |

**#5 app idea:** *Release Notes Bot* — paste sprint tickets, Bedrock drafts Markdown release notes, Streamlit UI to edit/publish, history in Postgres (like incident-triage-bot complexity).

```powershell
aws sso login --profile eks-admin-user
$env:AWS_PROFILE="eks-admin-user"

# Test #2 — medium (recommended next)
.\scripts\run-pipeline-test.ps1 -Level medium

# Or step by step:
python agents/product-agent/product_agent.py --input-file inputs/test_medium_app.txt --prd-name test-medium-app
python agents/architect-agent/architect_agent.py --target-app test-medium-app
python agents/developer-agent/developer_agent.py --target-app test-medium-app

# Test #3 — full chain including database-agent
.\scripts\run-pipeline-test.ps1 -Level db

# Test #4 — Inventory Desk (login, Postgres CRUD, stock + QA)
.\scripts\run-pipeline-test.ps1 -Level inventory
# Same as: .\scripts\run-sdlc-local.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt

# Test #5 — Release Notes Bot (Bedrock + Postgres + Streamlit — medium E2E)
.\scripts\run-pipeline-test.ps1 -Level release-notes
# Same as: .\scripts\run-sdlc-local.ps1 -Feature release-notes-bot -InputFile inputs\release-notes-bot.txt

# Test #6 — Standup Tracker (Bedrock + Postgres + Streamlit — golden template test)
.\scripts\run-pipeline-test.ps1 -Level standup
# Same as: .\scripts\run-sdlc-local.ps1 -Feature standup-tracker -InputFile inputs\standup-tracker.txt
```

## Example

```powershell
aws sso login --profile eks-admin-user
$env:AWS_PROFILE="eks-admin-user"

python agents/product-agent/product_agent.py `
  --input-file inputs/finops-web-app.txt `
  --prd-name finops-web-app
```

Optional: Jira Epic + 5 stories in the **same pipeline run**:

```powershell
.\scripts\run-sdlc-local.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt -WithJira -JiraProject SAAP
```

Or manually after PRD:

```powershell
python agents/product-agent/product_agent.py `
  --input-file inputs/finops-web-app.txt `
  --prd-name finops-web-app `
  --project SAAP `
  --allow-writes `
  --create-jira-tickets
```

Full flag reference: [`scripts/PIPELINE.md`](../scripts/PIPELINE.md)

## Pipeline (all agents)

**Default full chain** (`run-sdlc-local.ps1` — no extra flags needed for Postgres apps):

1. product → architect → database → **apply SQL to RDS** → developer → **qa** → **pytest verify**

```powershell
aws sso login --profile eks-admin-user
$env:AWS_PROFILE="eks-admin-user"

# Inventory Desk — DEFAULT full chain (RDS + QA + verify; no Jira unless -WithJira)
.\scripts\run-sdlc-local.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt

# Same + Jira backlog in project SAAP:
.\scripts\run-sdlc-local.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt -WithJira -JiraProject SAAP

# Or use the test wrapper:
.\scripts\run-pipeline-test.ps1 -Level inventory
.\scripts\run-pipeline-test.ps1 -Level inventory -WithJira -JiraProject SAAP

# No-database apps (skip RDS + DB agent):
.\scripts\run-sdlc-local.ps1 -Feature test-medium-app -InputFile inputs\test_medium_app.txt -SkipDb -SkipPostgres

# Opt out of QA or local pytest only:
.\scripts\run-sdlc-local.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt -SkipQa
.\scripts\run-sdlc-local.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt -SkipVerify
```

Legacy flags `-WithPostgres` and `-WithQa` still work; RDS apply and QA are **on by default** when database/developer steps run.

```powershell
.\scripts\run-sdlc-local.ps1 -Feature finops-web-app -InputFile inputs\finops-web-app.txt
.\scripts\run-sdlc-local.ps1 -Feature meeting-assistant -InputFile inputs\meeting-assistant.txt
.\scripts\run-sdlc-local.ps1 -Feature rag-app-streamlit -InputFile inputs\rag-app-streamlit.txt
```

### RAG + Streamlit (step-by-step — recommended for first run)

```powershell
aws sso login --profile eks-admin-user
$env:AWS_PROFILE="eks-admin-user"

# 1) Product → PRD
python agents/product-agent/product_agent.py --input-file inputs/rag-app-streamlit.txt --prd-name rag-app-streamlit

# 2) Architect → design + diagram
python agents/architect-agent/architect_agent.py --target-app rag-app-streamlit --context-file agents/pipeline/rag-app-streamlit.context.json

# 3) Database → SQL + apply to RDS (pgvector + document_chunks)
python agents/database-agent/database_agent.py --target-app rag-app-streamlit --context-file agents/pipeline/rag-app-streamlit.context.json --with-postgres

# 4) Developer → FastAPI + Streamlit + full RAG wiring
python agents/developer-agent/developer_agent.py --target-app rag-app-streamlit --context-file agents/pipeline/rag-app-streamlit.context.json --task "Implement Pattern B++ local RAG with Streamlit UI: persist PDF, pypdf chunk, Titan embed, pgvector retrieval, /chat with citations, ui/streamlit_app.py calling API"

# 5) Run app
cd target-apps/rag-app-streamlit
copy .env.example .env   # set DATABASE_URL from .env.local
pytest tests/ -q
uvicorn app.main:app --reload --port 8000
# second terminal:
streamlit run ui/streamlit_app.py --server.port 8501
```
