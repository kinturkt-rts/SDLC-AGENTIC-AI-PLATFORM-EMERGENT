# SDLC pipeline commands

Run everything from the **repo root** after AWS SSO login:

```powershell
aws sso login --profile eks-admin-user
```

Ensure `.env` has `AWS_PROFILE=eks-admin-user` (no active `AWS_ACCESS_KEY_ID` / session token lines).
One-time CLI profile setup: `aws configure sso --profile eks-admin-user` (writes `~/.aws/config`, not the repo).

## Default command (full chain)

For a Postgres-backed app like **Inventory Desk**, this is the standard one-liner:

```powershell
.\scripts\run-sdlc.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt
```

Equivalent test wrapper:

```powershell
.\scripts\run-pipeline-test.ps1 -Level inventory
```

### What runs by default (no extra flags)

| Step | Agent / script | What it does |
|------|----------------|--------------|
| 1 | **product-agent** | Brief → `docs/PRD/<feature>.md` + `agents/pipeline/<feature>.context.json` |
| 2 | architect-agent | `docs/design/<feature>.md` + diagram PNG |
| 3 | database-agent | SQL under `target-apps/<feature>/db/sql/` |
| 3b | apply_sql_to_rds.py | **Applies SQL to RDS Postgres** (when DB step runs) |
| 4 | developer-agent | FastAPI app under `target-apps/<feature>/` |
| 5 | local verify | Import smoke + `pytest` in app folder |
| 6 | **gitlab-agent** | MCP push to `sdlc/<feature>` on GitLab (when `GITLAB_*` in `.env`) |
| 7 | qa-agent | Extended tests — **only with `-WithQa`** |

GitLab publish runs **by default** after developer when `.env` has `GITLAB_PERSONAL_ACCESS_TOKEN` and `GITLAB_PROJECT_PATH`. Use **`-SkipGitlab`** to skip. **devops-agent** and **security-agent** are not in `run-sdlc.ps1` yet — run manually after QA when needed.

---

## Two ways to run

| Script | When to use |
|--------|-------------|
| `run-sdlc.ps1` | Any feature — you pass `-Feature` and `-InputFile` |
| `run-pipeline-test.ps1` | Preset levels: `easy`, `medium`, `db`, `inventory`, `release-notes` |

---

## Opt-in flags (`-With*`)

| Flag | Requires | Effect |
|------|----------|--------|
| **`-WithJira`** | **`-JiraProject SAAP`** | After PRD: creates Jira **Epic + 5 user stories** via Atlassian MCP |
| `-JiraSprint 42` | optional | Add stories to a sprint |
| `-JiraStoryTitleStyle concise` | optional | `concise` (default) or `user-story` |
| `-WithWebCrawler` | — | Optional scrape step (Firecrawl + Postgres) between architect and DB |
| `-WithPostgres` | — | Legacy: force RDS apply (already default when DB runs) |
| `-WithQa` | — | Run qa-agent after GitLab publish |

**Jira example:**

```powershell
.\scripts\run-sdlc.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt -WithJira -JiraProject SAAP
```

```powershell
.\scripts\run-pipeline-test.ps1 -Level inventory -WithJira -JiraProject SAAP
```

Jira is **never** created unless you pass `-WithJira`. Atlassian MCP must be configured in Cursor.

---

## Opt-out flags (`-Skip*`)

| Flag | Effect |
|------|--------|
| `-SkipProduct` | Skip PRD (PRD must already exist) |
| `-SkipArchitect` | Skip design + diagram |
| `-SkipDb` | Skip database-agent entirely |
| `-SkipPostgres` | Run database-agent (SQL files) but **do not** apply to RDS |
| `-SkipDeveloper` | Skip FastAPI implementation |
| `-SkipGitlab` | Skip gitlab-agent publish (default is ON after developer when GitLab env is set) |
| `-SkipQa` | Skip qa-agent |
| `-SkipVerify` | Skip end-of-pipeline import + pytest |

**No database (API-only apps):**

```powershell
.\scripts\run-sdlc.ps1 -Feature test-medium-app -InputFile inputs\test_medium_app.txt -SkipDb -SkipPostgres
```

**SQL files only — no RDS:**

```powershell
.\scripts\run-sdlc.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt -SkipPostgres
```

---

## Postgres: files vs RDS

| Mode | Command | SQL on disk | RDS updated |
|------|---------|-------------|-------------|
| **Default (DB app)** | no `-SkipPostgres` | Yes | **Yes** |
| SQL only | `-SkipPostgres` | Yes | No |
| No DB | `-SkipDb` | — | — |

RDS needs `POSTGRES_MCP_*` (or equivalent) in root `.env` / `.env.local`. Retry apply alone:

```powershell
python scripts/apply_sql_to_rds.py --target-app inventory-app
```

---

## Preset levels (`run-pipeline-test.ps1`)

| Level | Input | DB + RDS | QA |
|-------|-------|----------|-----|
| `easy` | test_dev.txt | No | Yes (default) |
| `medium` | test_medium_app.txt | No | Yes |
| `db` | test_db.txt | Yes | Yes |
| `inventory` | inventory-app.txt | Yes | Yes |
| `release-notes` | release-notes-bot.txt | Yes | Yes |

```powershell
.\scripts\run-pipeline-test.ps1 -Level medium
.\scripts\run-pipeline-test.ps1 -Level db
.\scripts\run-pipeline-test.ps1 -Level inventory
.\scripts\run-pipeline-test.ps1 -Level release-notes
```

---

## Resume a failed run

```powershell
# PRD done — continue from architect
.\scripts\run-sdlc.ps1 -Feature inventory-app -InputFile inputs\inventory-app.txt -SkipProduct

# Design done — DB + dev + QA only
.\scripts\run-sdlc.ps1 -Feature inventory-app -SkipProduct -SkipArchitect

# Dev + QA only
.\scripts\run-sdlc.ps1 -Feature inventory-app -SkipProduct -SkipArchitect -SkipDb -SkipPostgres
```

---

## Manual Jira (without pipeline)

```powershell
python agents/product-agent/product_agent.py `
  --input-file inputs\inventory-app.txt `
  --prd-name inventory-app `
  --project SAAP `
  --allow-writes `
  --create-jira-tickets
```
