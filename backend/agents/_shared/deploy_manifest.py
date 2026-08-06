"""Deploy manifest — deterministic derivation of an app's deploy shape.

devops-agent maps this manifest onto infrastructure/modules/target-app-ecs inputs
(enable_ui, db_secret_arn, ...). Everything here is inspected from disk, the
pipeline context, and prior handoffs — never guessed by the LLM.
"""

from __future__ import annotations

import json
import os
import re
import secrets
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


def db_instance_identifier_from_env() -> str | None:
    """POSTGRES_MCP_INSTANCE_IDENTIFIER, else derived from the RDS endpoint's first
    label (<instance-id>.<hash>.<region>.rds.amazonaws.com)."""
    explicit = os.getenv("POSTGRES_MCP_INSTANCE_IDENTIFIER", "").strip()
    if explicit:
        return explicit
    endpoint = os.getenv("POSTGRES_MCP_DB_ENDPOINT", "").strip()
    if endpoint.endswith(".rds.amazonaws.com") and "." in endpoint:
        return endpoint.split(".", 1)[0]
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
    # postgresql+psycopg: target apps use SQLAlchemy 2 + psycopg3 (see _template).
    return f"postgresql+psycopg://{user}:{password}@{endpoint}:{port}/{database}?sslmode=require"


_PLACEHOLDER_HINTS = ("change-me", "change_me", "change-this", "change_this", "your_", "your-", "example", "placeholder", "strong-secret")
_SECRET_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|API_KEY)", re.IGNORECASE)


def derive_extra_env(app: str) -> dict[str, str]:
    """Secret-ish env vars from the app's .env.example that still hold placeholders.

    Generates real values (persisted in <app>.devops-handoff.json so redeploys do
    not rotate them). Non-placeholder keys are skipped — apps ship working defaults
    in config.py; DATABASE_URL is always excluded (injected via Secrets Manager).
    """
    env_example = _TARGET_APPS / app / ".env.example"
    if not env_example.is_file():
        return {}

    previous: dict[str, str] = {}
    handoff = _read_json(_PIPELINE_DIR / f"{app}.devops-handoff.json") or {}
    if isinstance(handoff.get("extraEnv"), dict):
        previous = {str(k): str(v) for k, v in handoff["extraEnv"].items()}

    result: dict[str, str] = {}
    for line in env_example.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key == "DATABASE_URL" or not _SECRET_KEY_RE.search(key):
            continue
        if not any(hint in value.lower() for hint in _PLACEHOLDER_HINTS):
            continue  # looks like a real/workable value; leave app defaults alone
        result[key] = previous.get(key) or secrets.token_urlsafe(24)
    return result


def _detect_ui_framework(app_dir: Path, context: dict[str, Any] | None = None) -> str:
    """Return ``streamlit``, ``react``, or ``none`` from on-disk UI artifacts.

    Streamlit wins if both are present (legacy Pattern C). React is detected via
    ``ui/package.json`` (GitLab CI remaps apps-repo ``frontend/`` → ``ui/``) or
    ``frontend/package.json`` (local / S3 layout before remap).
    """
    if (app_dir / "ui" / "streamlit_app.py").is_file():
        return "streamlit"
    if (app_dir / "ui" / "package.json").is_file() or (
        app_dir / "frontend" / "package.json"
    ).is_file():
        return "react"
    return "none"


def ensure_deploy_dockerfiles(app: str) -> list[str]:
    """Copy template Dockerfiles and serve_api.py into target-apps/<app>/ when missing."""
    app_dir = _TARGET_APPS / app
    deploy_dir = app_dir / "deploy"
    copied: list[str] = []
    if not app_dir.is_dir() or not _TEMPLATE_DEPLOY.is_dir():
        return copied
    deploy_dir.mkdir(exist_ok=True)
    names = (
        "Dockerfile.api",
        "Dockerfile.ui",
        "Dockerfile.ui.react",
        "nginx.react.conf.template",
        "react-ui-entrypoint.sh",
    )
    for name in names:
        src = _TEMPLATE_DEPLOY / name
        dst = deploy_dir / name
        if src.is_file() and not dst.is_file():
            shutil.copyfile(src, dst)
            copied.append(f"target-apps/{app}/deploy/{name}")
            if name.endswith(".sh"):
                try:
                    dst.chmod(dst.stat().st_mode | 0o111)
                except OSError:
                    pass
    # serve_api.py lives at the app root (same level as app/) so uvicorn can import it.
    # It reads API_PATH_PREFIX at runtime and strips the ALB path prefix from requests.
    serve_src = _TARGET_APPS / "_template" / "serve_api.py"
    serve_dst = app_dir / "serve_api.py"
    if serve_src.is_file() and not serve_dst.is_file():
        shutil.copyfile(serve_src, serve_dst)
        copied.append(f"target-apps/{app}/serve_api.py")
    return copied


def stage_react_ui_for_deploy(app: str) -> str | None:
    """Ensure ``ui/`` holds the Vite app for ``Dockerfile.ui.react`` (COPY ui/...).

    GitLab CI already remaps ``<slug>/frontend/`` → ``target-apps/<slug>/ui/``.
    Local / S3 trees may still have ``frontend/`` only — copy once when needed.
    """
    app_dir = _TARGET_APPS / app
    ui_pkg = app_dir / "ui" / "package.json"
    fe_dir = app_dir / "frontend"
    if ui_pkg.is_file():
        return None
    if not (fe_dir / "package.json").is_file():
        return None
    ui_dir = app_dir / "ui"
    if ui_dir.exists():
        # Avoid clobbering a Streamlit ui/ tree.
        if (ui_dir / "streamlit_app.py").is_file():
            return None
        shutil.rmtree(ui_dir)
    shutil.copytree(fe_dir, ui_dir)
    return f"target-apps/{app}/ui (staged from frontend/)"


def _uses_bedrock(app_dir: Path) -> bool:
    """App code references Bedrock (RAG/LLM apps) -> task role needs InvokeModel."""
    app_pkg = app_dir / "app"
    if not app_pkg.is_dir():
        return False
    for py in app_pkg.rglob("*.py"):
        try:
            if "bedrock" in py.read_text(encoding="utf-8", errors="ignore").lower():
                return True
        except OSError:
            continue
    return False


def build_deploy_manifest(app: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inspect target-apps/<app>/ + pipeline context/handoffs -> deploy manifest."""
    ctx = context or {}
    app_dir = _TARGET_APPS / app

    ui_framework = _detect_ui_framework(app_dir, ctx)
    has_ui = ui_framework in ("streamlit", "react")
    sql_dir = app_dir / "db" / "sql"
    has_db = sql_dir.is_dir() and any(sql_dir.glob("*.sql"))

    gitlab_handoff = _read_json(_PIPELINE_DIR / f"{app}.gitlab-handoff.json") or {}
    developer_handoff = _read_json(_PIPELINE_DIR / f"{app}.developer-handoff.json") or {}

    deploy_dir = app_dir / "deploy"
    has_ui_dockerfile = (deploy_dir / "Dockerfile.ui").is_file() or (
        deploy_dir / "Dockerfile.ui.react"
    ).is_file()

    manifest: dict[str, Any] = {
        "targetApp": app,
        "environment": "dev",
        "awsRegion": os.getenv("AWS_REGION", "us-east-2"),
        "appDir": f"target-apps/{app}",
        "tfRoot": f"infrastructure/environments/dev/{app}",
        "enableUi": has_ui,
        "uiFramework": ui_framework,
        "hasDatabase": has_db,
        "usesBedrock": _uses_bedrock(app_dir),
        "dbInstanceIdentifier": db_instance_identifier_from_env() if has_db else None,
        "databaseUrlAvailable": bool(database_url_from_env()) if has_db else False,
        "dockerfiles": {
            "api": (deploy_dir / "Dockerfile.api").is_file(),
            "ui": has_ui_dockerfile,
        },
        "gitlab": {
            "branch": gitlab_handoff.get("branch"),
            "project": gitlab_handoff.get("gitlabProject"),
            "mergeRequestUrl": gitlab_handoff.get("mergeRequestUrl"),
        }
        if gitlab_handoff
        else None,
        "extraEnvVars": developer_handoff.get("envVarNames") or [],
        "extraEnv": derive_extra_env(app),
        "tfRootExists": (INFRA_DEV_DIR / app / "main.tf").is_file(),
    }
    return manifest
