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

