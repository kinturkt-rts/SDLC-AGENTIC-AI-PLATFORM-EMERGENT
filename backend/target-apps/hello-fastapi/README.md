# hello-fastapi

Lightweight demo target-app used to validate the Phase A AWS deploy path
(ECS Fargate + shared ALB). No database — greetings are stored in memory.

## Layout

- `app/main.py` — FastAPI backend (`/health`, `/api/greetings`, `/api/stats`)
- `ui/streamlit_app.py` — Streamlit UI calling the API over `API_BASE_URL`
- `deploy/Dockerfile.api`, `deploy/Dockerfile.ui` — container builds (from `_template/deploy/`)

## Run locally

```powershell
pip install -r requirements.txt -r ui/requirements.txt
uvicorn app.main:app --port 8000          # terminal 1
streamlit run ui/streamlit_app.py         # terminal 2
```

## Deploy to AWS (dev)

```powershell
cd backend
.\scripts\deploy-target-app.ps1 -Feature hello-fastapi
```

Terraform root: `backend/infrastructure/environments/dev/hello-fastapi/`.
Tear down with `.\scripts\deploy-target-app.ps1 -Feature hello-fastapi -Destroy`.
