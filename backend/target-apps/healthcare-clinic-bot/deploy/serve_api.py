"""Deploy-time API entrypoint — path-prefix-aware uvicorn launcher.

Behind the shared ALB, apps are routed by path (http://<alb>/<app>/...). Streamlit
handles this via baseUrlPath; FastAPI needs the prefix stripped. This wrapper does
that WITHOUT touching generated app code:

- API_PATH_PREFIX set (api-only apps): strips the prefix from incoming paths and
  sets root_path so /docs and openapi.json render correct URLs.
- API_PATH_PREFIX unset (local dev / UI apps where the API stays internal): plain
  passthrough, identical to running uvicorn directly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Running "python deploy/serve_api.py" puts deploy/ on sys.path, not the app root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn

from app.main import app as fastapi_app

PREFIX = os.getenv("API_PATH_PREFIX", "").rstrip("/")


class PrefixStripMiddleware:
    """Pure-ASGI: /<prefix>/x -> /x with root_path=<prefix> (docs-safe)."""

    def __init__(self, app, prefix: str) -> None:
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket"):
            path = scope.get("path", "")
            if path == self.prefix or path.startswith(self.prefix + "/"):
                scope = dict(scope)
                stripped = path[len(self.prefix):] or "/"
                scope["path"] = stripped
                scope["raw_path"] = stripped.encode("utf-8")
                scope["root_path"] = self.prefix
        await self.app(scope, receive, send)


app = PrefixStripMiddleware(fastapi_app, PREFIX) if PREFIX else fastapi_app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
