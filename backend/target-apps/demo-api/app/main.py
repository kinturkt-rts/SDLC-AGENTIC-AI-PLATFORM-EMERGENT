from fastapi import FastAPI

from app.routers import health, items

app = FastAPI(title="demo-api", version="0.1.0")
app.include_router(health.router)
app.include_router(items.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "demo-api", "status": "ok"}
