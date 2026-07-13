"""Deploy manifest — deterministic derivation of an app's deploy shape.

devops-agent maps this manifest onto infrastructure/modules/target-app-ecs inputs
(enable_ui, db_secret_arn, ...). Everything here is inspected from disk, the
pipeline context, and prior handoffs — never guessed by the LLM.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGET_APPS = _REPO_ROOT / "target-apps"
_TEMPLATE_DEPLOY = _TARGET_APPS / "_template" / "deploy"
_PIPELINE_DIR = _REPO_ROOT / "agents" / "pipeline"
INFRA_DEV_DIR = _REPO_ROOT / "infrastructure" / "environments" / "dev"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        # utf-8-sig tolerates the BOM that PS 5.1 Out-File adds to handoff JSONs
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def database_url_from_env() -> str | None:
    """Build a SQLAlchemy Postgres DSN from POSTGRES_MCP_* (same vars the RDS apply uses)."""
    endpoint = os.getenv("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    database = os.getenv("POSTGRES_MCP_DATABASE", "").strip()
    user = os.getenv("POSTGRES_MCP_DB_USER", "").strip()
    password = os.getenv("POSTGRES_MCP_DB_PASSWORD", "").strip()
    port = os.getenv("POSTGRES_MCP_PORT", "5432").strip() or "5432"
    if not (endpoint and database and user and password):
        return None
    return f"postgresql://{user}:{password}@{endpoint}:{port}/{database}"


def ensure_deploy_dockerfiles(app: str) -> list[str]:
    """Copy template Dockerfiles into target-apps/<app>/deploy/ when missing."""
    app_dir = _TARGET_APPS / app
    deploy_dir = app_dir / "deploy"
    copied: list[str] = []
    if not app_dir.is_dir() or not _TEMPLATE_DEPLOY.is_dir():
        return copied
    deploy_dir.mkdir(exist_ok=True)
    for name in ("Dockerfile.api", "Dockerfile.ui"):
        src = _TEMPLATE_DEPLOY / name
        dst = deploy_dir / name
        if src.is_file() and not dst.is_file():
            shutil.copyfile(src, dst)
            copied.append(f"target-apps/{app}/deploy/{name}")
    return copied


def build_deploy_manifest(app: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inspect target-apps/<app>/ + pipeline context/handoffs -> deploy manifest."""
    ctx = context or {}
    app_dir = _TARGET_APPS / app

    has_ui = (app_dir / "ui" / "streamlit_app.py").is_file()
    sql_dir = app_dir / "db" / "sql"
    has_db = sql_dir.is_dir() and any(sql_dir.glob("*.sql"))

    # deliveryProfile from product/developer context can force the UI flag on.
    profile = ctx.get("deliveryProfile") or {}
    if isinstance(profile, dict) and profile.get("requiresStreamlit"):
        has_ui = has_ui or (app_dir / "ui").is_dir()

    gitlab_handoff = _read_json(_PIPELINE_DIR / f"{app}.gitlab-handoff.json") or {}
    developer_handoff = _read_json(_PIPELINE_DIR / f"{app}.developer-handoff.json") or {}

    manifest: dict[str, Any] = {
        "targetApp": app,
        "environment": "dev",
        "awsRegion": os.getenv("AWS_REGION", "us-east-2"),
        "appDir": f"target-apps/{app}",
        "tfRoot": f"infrastructure/environments/dev/{app}",
        "enableUi": has_ui,
        "hasDatabase": has_db,
        "dbInstanceIdentifier": (
            os.getenv("POSTGRES_MCP_INSTANCE_IDENTIFIER", "").strip() or None
        )
        if has_db
        else None,
        "databaseUrlAvailable": bool(database_url_from_env()) if has_db else False,
        "dockerfiles": {
            "api": (app_dir / "deploy" / "Dockerfile.api").is_file(),
            "ui": (app_dir / "deploy" / "Dockerfile.ui").is_file(),
        },
        "gitlab": {
            "branch": gitlab_handoff.get("branch"),
            "project": gitlab_handoff.get("gitlabProject"),
            "mergeRequestUrl": gitlab_handoff.get("mergeRequestUrl"),
        }
        if gitlab_handoff
        else None,
        "extraEnvVars": developer_handoff.get("envVarNames") or [],
        "tfRootExists": (INFRA_DEV_DIR / app / "main.tf").is_file(),
    }
    return manifest
