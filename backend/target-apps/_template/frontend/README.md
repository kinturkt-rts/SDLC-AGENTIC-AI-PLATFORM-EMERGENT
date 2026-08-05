# Frontend

Vite + React UI for this target app.

## Run locally (platform monorepo)

```bash
cd target-apps/<app>/frontend
cp .env.example .env   # if present; set VITE_API_URL
npm install
npm run dev
```

## Apps-repo layout

On the published apps branch the same tree is:

```text
<app>/frontend/   ← this package
<app>/backend/    ← FastAPI API (sibling)
```

```bash
cd <app>/frontend
npm install
npm run dev
```

Start the API from `<app>/backend` (see that README) so `VITE_API_URL` points at it.
