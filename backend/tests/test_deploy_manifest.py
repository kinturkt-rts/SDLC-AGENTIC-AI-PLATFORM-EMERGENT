"""Tests for deploy_manifest UI framework detection (Streamlit vs React)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared import deploy_manifest as dm  # noqa: E402


@pytest.fixture()
def app_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    apps = tmp_path / "target-apps"
    apps.mkdir()
    app = apps / "demo-app"
    app.mkdir()
    (app / "app").mkdir()
    (app / "app" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    monkeypatch.setattr(dm, "_TARGET_APPS", apps)
    monkeypatch.setattr(dm, "_TEMPLATE_DEPLOY", apps / "_template" / "deploy")
    monkeypatch.setattr(dm, "_PIPELINE_DIR", tmp_path / "pipeline")
    monkeypatch.setattr(dm, "INFRA_DEV_DIR", tmp_path / "infra")
    return app


def test_detect_streamlit(app_dir: Path) -> None:
    ui = app_dir / "ui"
    ui.mkdir()
    (ui / "streamlit_app.py").write_text("import streamlit as st\n", encoding="utf-8")
    assert dm._detect_ui_framework(app_dir) == "streamlit"
    m = dm.build_deploy_manifest("demo-app")
    assert m["enableUi"] is True
    assert m["uiFramework"] == "streamlit"


def test_detect_react_under_ui(app_dir: Path) -> None:
    ui = app_dir / "ui"
    ui.mkdir()
    (ui / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    assert dm._detect_ui_framework(app_dir) == "react"
    m = dm.build_deploy_manifest("demo-app")
    assert m["enableUi"] is True
    assert m["uiFramework"] == "react"


def test_detect_react_under_frontend(app_dir: Path) -> None:
    fe = app_dir / "frontend"
    fe.mkdir()
    (fe / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    assert dm._detect_ui_framework(app_dir) == "react"


def test_streamlit_wins_over_react(app_dir: Path) -> None:
    ui = app_dir / "ui"
    ui.mkdir()
    (ui / "streamlit_app.py").write_text("import streamlit as st\n", encoding="utf-8")
    (ui / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    assert dm._detect_ui_framework(app_dir) == "streamlit"


def test_api_only(app_dir: Path) -> None:
    assert dm._detect_ui_framework(app_dir) == "none"
    m = dm.build_deploy_manifest("demo-app")
    assert m["enableUi"] is False
    assert m["uiFramework"] == "none"


def test_stage_react_ui_from_frontend(app_dir: Path) -> None:
    fe = app_dir / "frontend"
    fe.mkdir()
    (fe / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (fe / "index.html").write_text("<html></html>\n", encoding="utf-8")
    staged = dm.stage_react_ui_for_deploy("demo-app")
    assert staged is not None
    assert (app_dir / "ui" / "package.json").is_file()
    assert (app_dir / "ui" / "index.html").is_file()


def test_devops_tf_template_renders_react_framework() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "agents"
        / "devops-agent"
        / "devops_agent.py"
    )
    spec = importlib.util.spec_from_file_location("devops_agent_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    text = module.render_tf_root(
        {
            "targetApp": "demo-app",
            "enableUi": True,
            "uiFramework": "react",
            "hasDatabase": False,
            "usesBedrock": False,
        }
    )
    assert "enable_ui      = true" in text
    assert 'ui_framework   = "react"' in text


def test_requires_react_alone_does_not_enable_ui(app_dir: Path) -> None:
    # Profile without package.json must not create a UI ECS service with no image.
    assert (
        dm._detect_ui_framework(
            app_dir, {"deliveryProfile": {"requiresReact": True}}
        )
        == "none"
    )
    m = dm.build_deploy_manifest(
        "demo-app", {"deliveryProfile": {"requiresReact": True}}
    )
    assert m["enableUi"] is False
    assert m["uiFramework"] == "none"


def test_ensure_tf_root_infers_react_from_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_path = (
        _REPO_ROOT / "scripts" / "ensure-target-app-tf-root.py"
    )
    spec = importlib.util.spec_from_file_location("ensure_tf_root", ensure_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "BACKEND", tmp_path)
    app = tmp_path / "target-apps" / "demo-app"
    (app / "frontend").mkdir(parents=True)
    (app / "frontend" / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")

    assert module._infer_ui_framework("demo-app", True, None) == "react"
    assert module._infer_ui_framework("demo-app", True, "/demo-app/healthz") == "react"
    assert module._infer_ui_framework("other", True, "/other/_stcore/health") == "streamlit"
    assert module._infer_ui_framework("other", False, None) == "none"

    text = module._render(
        "demo-app",
        "us-east-2",
        True,
        False,
        False,
        "agenticaidbinstance",
        ui_framework="react",
    )
    assert 'ui_framework   = "react"' in text
    assert "enable_ui      = true" in text


def test_derive_extra_env_detects_change_this_placeholder(app_dir: Path) -> None:
    """Regression: developer-agent's ".env.example" phrases the JWT placeholder as
    "change-this-to-a-random-secret", which didn't match any _PLACEHOLDER_HINTS
    substring — no secret got generated, JWT_SECRET_KEY shipped empty, and every
    login 500'd with "HMAC key must not be empty" despite correct credentials."""
    (app_dir / ".env.example").write_text(
        "DATABASE_URL=postgresql://x\nJWT_SECRET_KEY=change-this-to-a-random-secret\n",
        encoding="utf-8",
    )
    extra = dm.derive_extra_env("demo-app")
    assert extra.get("JWT_SECRET_KEY")
    assert extra["JWT_SECRET_KEY"] != "change-this-to-a-random-secret"


def test_nginx_react_proxies_docs_assets() -> None:
    nginx = (
        _REPO_ROOT
        / "target-apps"
        / "_template"
        / "deploy"
        / "nginx.react.conf.template"
    ).read_text(encoding="utf-8")
    assert "location /${APP_NAME}/docs {" in nginx
    assert "location /${APP_NAME}/redoc {" in nginx
    assert "location = /${APP_NAME}/docs {" not in nginx


def test_nginx_react_redirects_stay_relative_to_alb_port() -> None:
    """Regression: nginx listens on UI_PORT (internal-only) behind the ALB's public port.
    Without absolute_redirect off, its automatic redirects (e.g. the trailing-slash one for
    `= /${APP_NAME}`) build a Location header from nginx's own host:port, sending the browser
    to <alb-dns>:<UI_PORT> directly - a port the ALB never exposes - and it times out."""
    nginx = (
        _REPO_ROOT
        / "target-apps"
        / "_template"
        / "deploy"
        / "nginx.react.conf.template"
    ).read_text(encoding="utf-8")
    assert "absolute_redirect off;" in nginx
    # Must appear before any location block so it applies to every redirect the server emits.
    assert nginx.index("absolute_redirect off;") < nginx.index("location")


def test_api_ts_token_key_is_namespaced_per_app() -> None:
    """Regression: all target apps share one ALB origin (path-routed per app),
    and localStorage is scoped by origin, not path. A bare TOKEN_KEY = "token"
    let one app's leftover session get picked up by a different app on the
    same origin, skipping its login screen and then 401ing every API call
    against a token signed with the wrong app's JWT_SECRET_KEY."""
    api_ts = (
        _REPO_ROOT / "target-apps" / "_template" / "frontend" / "src" / "api.ts"
    ).read_text(encoding="utf-8")
    assert 'const TOKEN_KEY = "token"' not in api_ts
    assert "API_BASE_URL" in api_ts.split("TOKEN_KEY =", 1)[1].splitlines()[0]
    assert "localStorage.removeItem(TOKEN_KEY)" in api_ts.split("async function handle")[1]


def test_api_apikey_ts_storage_keys_are_namespaced_per_app() -> None:
    """Same origin-collision regression as api.ts, for all four keys the
    api-key auth variant stores (token, role, userId, userRole)."""
    api_ts = (
        _REPO_ROOT / "target-apps" / "_template" / "frontend" / "src" / "api_apikey.ts"
    ).read_text(encoding="utf-8")
    for literal in ('"token"', '"authRole"', '"userId"', '"userRole"'):
        assert f"= {literal}" not in api_ts, f"{literal} must be namespaced by API_BASE_URL"


def test_frontend_agent_prompt_uses_token_key_not_literal() -> None:
    """Regression: the JWT auth-screen prompt told the LLM to hardcode
    localStorage.setItem("token", ...) directly, bypassing the TOKEN_KEY
    constant api.ts actually reads from (which is namespaced per app) —
    new apps would write to "token" and read from "token:/app-name" and
    break authentication immediately after generation."""
    frontend_agent_src = (
        _REPO_ROOT / "agents" / "frontend-agent" / "frontend_agent.py"
    ).read_text(encoding="utf-8")
    assert 'localStorage.setItem("token"' not in frontend_agent_src
    assert 'localStorage.removeItem("token")' not in frontend_agent_src
    assert "import { TOKEN_KEY }" in frontend_agent_src


def test_react_template_keeps_router_under_alb_app_path() -> None:
    template = (
        _REPO_ROOT / "target-apps" / "_template" / "frontend" / "src" / "main.tsx"
    ).read_text(encoding="utf-8")
    dockerfile = (
        _REPO_ROOT / "target-apps" / "_template" / "deploy" / "Dockerfile.ui.react"
    ).read_text(encoding="utf-8")

    assert "BrowserRouter basename={import.meta.env.BASE_URL}" in template
    # Backward compatibility for generated apps made by an older AgentCore runtime.
    assert "main.tsx must configure BrowserRouter basename" in dockerfile

