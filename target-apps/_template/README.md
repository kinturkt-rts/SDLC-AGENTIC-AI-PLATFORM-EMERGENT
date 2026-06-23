# Service Template

> Replace this README when the developer-agent scaffolds a real service.

## Layout

```
app/
  main.py           — FastAPI app + lifespan, CORS, router registration
  config.py         — pydantic-settings (reads .env)
  database.py       — SQLAlchemy engine, SessionLocal, Base, get_db()
  dependencies.py   — get_current_user(), DbSession, AuthUser typedefs
  models/           — SQLAlchemy ORM models (one file per domain entity)
  routers/          — FastAPI routers (one file per API domain from design §4)
  services/
    bedrock_client.py — Bedrock Converse wrapper (when design §2 uses LLM)
    prompts.py        — system prompt templates from design §5
schemas/            — Pydantic request/response models
tests/
  conftest.py       — TestClient + SQLite override fixtures
  test_health.py
requirements.txt
.env.example        — copy to .env and fill in secrets
```

## Local setup

Run from **repository root** (the folder that contains `target-apps/`):

```bash
cd target-apps/<your-service>
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
# edit .env — set DATABASE_URL, JWT_SECRET_KEY, etc.
```

## Run

**Terminal 1 — API** (from repo root):

```bash
cd target-apps/<your-service>
# activate venv (see above)
uvicorn app.main:app --reload --port 8000 --reload-dir app --reload-dir schemas
```

Use `--reload-dir` so pytest/package installs under `.venv` do not trigger reload storms (Streamlit health checks time out).

If the app includes Streamlit (`ui/streamlit_app.py`), add **Terminal 2** from repo root:

```bash
cd target-apps/<your-service>
# activate venv
cd ui
streamlit run streamlit_app.py --server.port 8501
```

API docs: http://localhost:8000/docs

## Test

```bash
pytest tests/ -q
```

## Environment variables

See `.env.example` for the full list. **Never commit `.env`.**
