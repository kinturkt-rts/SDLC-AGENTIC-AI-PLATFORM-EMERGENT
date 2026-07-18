"""ASGI startup shim — strips API_PATH_PREFIX before routing to FastAPI.

The shared ALB routes /<app-name>/* to this container but does NOT strip the
prefix before forwarding, so FastAPI receives /expense-tracker/health instead
of /health.  This wrapper intercepts the path, strips the prefix, and adjusts
root_path so Swagger UI generates correct URLs.

Usage (set automatically by Dockerfile.api CMD):
    python serve_api.py
"""
from __future__ import annotations

import os

import uvicorn

_PREFIX = os.getenv("API_PATH_PREFIX", "").rstrip("/")


def _make_app():
    from app.main import app as _fastapi_app  # import here so env is loaded first

    if not _PREFIX:
        return _fastapi_app

    from starlette.types import ASGIApp, Receive, Scope, Send

    class _StripPrefixMiddleware:
        def __init__(self, inner: ASGIApp, prefix: str) -> None:
            self.inner = inner
            self.prefix = prefix

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] in ("http", "websocket"):
                path: str = scope.get("path", "")
                if path.startswith(self.prefix):
                    scope = dict(scope)
                    scope["path"] = path[len(self.prefix) :] or "/"
                    scope["root_path"] = self.prefix
            await self.inner(scope, receive, send)

    return _StripPrefixMiddleware(_fastapi_app, _PREFIX)


app = _make_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "serve_api:app",
        host="0.0.0.0",
        port=port,
        root_path=_PREFIX,
    )
