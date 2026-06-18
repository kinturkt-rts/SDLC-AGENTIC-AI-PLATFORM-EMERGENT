"""Tests for developer-agent context enrichment and path guards."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "developer-agent" / "developer_agent.py"
_SCAFFOLD_PATH = _REPO_ROOT / "agents" / "developer-agent"


def _import_scaffold():
    sys.path.insert(0, str(_SCAFFOLD_PATH))
    from scaffold import load_manifest, resolve_pattern_spec, scaffold_service

    return load_manifest, resolve_pattern_spec, scaffold_service


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("developer_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_max_output_tokens_defaults_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("DEVELOPER_AGENT_MAX_TOKENS", raising=False)
    assert mod._max_output_tokens() == 32768
    monkeypatch.setenv("DEVELOPER_AGENT_MAX_TOKENS", "16384")
    assert mod._max_output_tokens() == 16384


def test_thinking_enabled_and_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("DEVELOPER_AGENT_THINKING", raising=False)
    monkeypatch.delenv("DEVELOPER_AGENT_THINKING_BUDGET", raising=False)
    assert mod._thinking_enabled() is False
    assert mod._thinking_budget_tokens() == 8192
    monkeypatch.setenv("DEVELOPER_AGENT_THINKING", "1")
    monkeypatch.setenv("DEVELOPER_AGENT_THINKING_BUDGET", "4096")
    assert mod._thinking_enabled() is True
    assert mod._thinking_budget_tokens() == 4096


def test_enrich_developer_context_sets_db_backend_postgres() -> None:
    mod = _load_agent_module()
    ctx: dict[str, Any] = {
        "targetApp": "meeting-assistant",
        "preferredSqlPath": "target-apps/meeting-assistant/db/sql",
    }
    mod._enrich_developer_context(ctx)
    assert ctx["dbBackend"] == "postgres"


def test_enrich_developer_context_discovers_handoff_md() -> None:
    mod = _load_agent_module()
    ctx: dict[str, Any] = {"targetApp": "meeting-assistant"}
    mod._enrich_developer_context(ctx)
    assert ctx.get("databaseHandoffPath") == "target-apps/meeting-assistant/db/HANDOFF.md"


def test_enrich_developer_context_discovers_scraped_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    scraped = tmp_path / "docs" / "PRD" / "scraped" / "demo-api"
    scraped.mkdir(parents=True)
    (scraped / "competitor.md").write_text("# Competitor API\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")

    ctx: dict[str, Any] = {"targetApp": "demo-api"}
    mod._enrich_developer_context(ctx)
    assert ctx["scrapedMarkdownPaths"] == ["docs/PRD/scraped/demo-api/competitor.md"]


def test_resolve_repo_path_allows_inputs_read() -> None:
    mod = _load_agent_module()
    path = mod._resolve_repo_path("inputs/team-faq-bot.txt", write=False)
    assert path.name == "team-faq-bot.txt"


def test_resolve_repo_path_blocks_writes_outside_target_apps() -> None:
    mod = _load_agent_module()
    with pytest.raises(ValueError, match="writes only allowed"):
        mod._resolve_repo_path("docs/design/foo.md", write=True)


def test_deployment_handoff_includes_port_and_env_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    env_example = service / ".env.example"
    env_example.write_text("API_KEY=placeholder\nDATABASE_URL=\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)

    written = ["target-apps/demo-api/.env.example"]
    handoff = mod._deployment_handoff("demo-api", written)
    assert handoff["targetEnvironment"] == "aws-dev"
    assert handoff["port"] == 8000
    assert handoff["healthCheckPath"] == "/health"
    assert "0.0.0.0" in handoff["containerEntrypoint"]
    assert "API_KEY" in handoff["envVarNames"]
    assert "PORT" in handoff["envVarNames"]


def test_strip_duplicate_handoff_sections() -> None:
    mod = _load_agent_module()
    text = (
        "Stack summary here.\n\n"
        "### 2. Files Written\n```\ntarget-apps/demo/app/main.py\n```\n\n"
        "### 6. Handoff JSON\n```json\n{\"writtenFiles\": [\"a.py\"]}\n```\n\n"
        "## Files written\n- `a.py`\n\n"
        "## Context handoff\n```json\n{\"writtenFiles\": [\"a.py\"]}\n```"
    )
    stripped = mod._strip_duplicate_handoff_sections(text)
    assert stripped == "Stack summary here."
    assert "writtenFiles" not in stripped


def test_dedupe_preserve_order() -> None:
    mod = _load_agent_module()
    assert mod._dedupe_preserve_order(["a.py", "b.py", "a.py"]) == ["a.py", "b.py"]


def test_scaffold_pattern_copies_streamlit_and_base(tmp_path: Path) -> None:
    _, _, scaffold_service = _import_scaffold()

    template = _REPO_ROOT / "target-apps" / "_template"
    service = tmp_path / "target-apps" / "scaffold-test-app"
    result = scaffold_service(
        template_dir=template,
        service_dir=service,
        pattern="C",
        force=True,
    )
    assert result["pattern"] == "C"
    assert not result["missing"]
    assert (service / "app" / "database.py").is_file()
    assert (service / "app" / "startup_checks.py").is_file()
    assert (service / "app" / "services" / "bedrock_client.py").is_file()
    assert (service / "ui" / "streamlit_app.py").is_file()
    assert (service / "tests" / "conftest.py").is_file()


def test_scaffold_skips_existing_unless_force(tmp_path: Path) -> None:
    _, _, scaffold_service = _import_scaffold()

    template = _REPO_ROOT / "target-apps" / "_template"
    service = tmp_path / "target-apps" / "scaffold-skip-app"
    service.mkdir(parents=True)
    db = service / "app" / "database.py"
    db.parent.mkdir(parents=True)
    db.write_text("# custom\n", encoding="utf-8")

    result = scaffold_service(
        template_dir=template,
        service_dir=service,
        pattern="B",
        force=False,
    )
    assert "app/database.py" in result["skipped"]
    assert db.read_text(encoding="utf-8") == "# custom\n"

    scaffold_service(
        template_dir=template,
        service_dir=service,
        pattern="B",
        force=True,
    )
    assert "SQLAlchemy" in db.read_text(encoding="utf-8")


def test_dev_scaffold_tool_tracks_written_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", _REPO_ROOT / "target-apps" / "_template")
    mod._written_files.clear()

    report = mod.dev_scaffold("tool-test-app", "B")
    assert report.startswith("SCAFFOLD OK")
    assert any("tool-test-app/app/database.py" in p for p in mod._written_files)


def test_resolve_pattern_spec_rejects_unknown() -> None:
    load_manifest, resolve_pattern_spec, _ = _import_scaffold()

    manifest = load_manifest(_REPO_ROOT / "target-apps" / "_template" / "scaffold-manifest.json")
    with pytest.raises(ValueError, match="unsupported pattern"):
        resolve_pattern_spec(manifest, "Z")


def test_validate_dev_write_path_blocks_env_and_qa_artifacts(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-svc"
    (service / "tests").mkdir(parents=True)

    assert mod._validate_dev_write_path(service / ".env") is not None
    assert mod._validate_dev_write_path(service / ".env.local") is not None
    assert mod._validate_dev_write_path(service / ".env.example") is None
    assert mod._validate_dev_write_path(service / "QA_REPORT.md") is not None
    assert mod._validate_dev_write_path(service / "tests" / "test_qa_edge_cases.py") is not None
    assert mod._validate_dev_write_path(service / "tests" / "test_api.py") is None
    assert mod._validate_dev_write_path(service / ".venv" / "pyvenv.cfg") is not None
