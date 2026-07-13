"""hello-fastapi — lightweight demo target-app for the Phase A AWS deploy dry run.

No database: greetings live in memory. Mirrors the template layout
(app/main.py FastAPI backend + ui/streamlit_app.py Streamlit frontend).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="hello-fastapi", version="0.1.0")

_GREETINGS: list[dict] = [
    {
        "id": 1,
        "name": "SDLC Platform",
        "message": "Deployed to ECS Fargate by the devops pipeline 🎉",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
]


class GreetingIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=280)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "hello-fastapi"}


@app.get("/api/greetings")
def list_greetings() -> list[dict]:
    return _GREETINGS


@app.post("/api/greetings", status_code=201)
def create_greeting(payload: GreetingIn) -> dict:
    greeting = {
        "id": max((g["id"] for g in _GREETINGS), default=0) + 1,
        "name": payload.name,
        "message": payload.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _GREETINGS.append(greeting)
    return greeting


@app.get("/api/greetings/{greeting_id}")
def get_greeting(greeting_id: int) -> dict:
    for greeting in _GREETINGS:
        if greeting["id"] == greeting_id:
            return greeting
    raise HTTPException(status_code=404, detail="Greeting not found")


@app.get("/api/stats")
def stats() -> dict:
    return {"total_greetings": len(_GREETINGS)}
