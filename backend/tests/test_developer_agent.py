"""Tests for developer-agent context enrichment and path guards."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "developer-agent" / "developer_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("developer_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_resolve_repo_path_rejects_template_escape_with_stray_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a stray space in an LLM-authored path ("_template /x.json") let a
    write escape the golden-template guard and land as a bogus top-level S3 key
    (runs/<runId>/_template /scaffold-manifest.json) instead of being blocked. In
    cloud mode _resolve_repo_path permits writes anywhere under repo root, so the
    golden-template guard depends entirely on _validate_dev_write_path's part check —
    which the un-stripped space defeated (this reproduces the cloud codepath)."""
    mod = _load_agent_module()
    monkeypatch.setattr(mod, "_is_cloud_store", lambda: True)
    file_path = mod._resolve_repo_path("_template /scaffold-manifest.json", write=True)
    assert "_template" in file_path.parts
    blocked = mod._validate_dev_write_path(file_path)
    assert blocked is not None
    assert "read-only" in blocked


def test_resolve_repo_path_still_blocks_clean_template_path() -> None:
    mod = _load_agent_module()
    with pytest.raises(ValueError, match="read-only"):
        mod._resolve_repo_path("target-apps/_template/app/database.py", write=True)


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


def test_enrich_developer_context_discovers_handoff_md(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    handoff_dir = tmp_path / "target-apps" / "meeting-assistant" / "db"
    handoff_dir.mkdir(parents=True)
    (handoff_dir / "HANDOFF.md").write_text("# DB handoff\n", encoding="utf-8")
    template = tmp_path / "target-apps" / "_template"
    template.mkdir(parents=True)
    (template / "README.md").write_text("template\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", template)

    ctx: dict[str, Any] = {"targetApp": "meeting-assistant"}
    mod._enrich_developer_context(ctx)
    assert ctx.get("databaseHandoffPath") == "target-apps/meeting-assistant/db/HANDOFF.md"


def test_enrich_developer_context_discovers_scraped_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    scraped = tmp_path / "docs" / "PRD" / "scraped" / "demo-api"
    scraped.mkdir(parents=True)
    (scraped / "competitor.md").write_text("# Competitor API\n", encoding="utf-8")

    template = tmp_path / "target-apps" / "_template"
    template.mkdir(parents=True)
    (template / "README.md").write_text("template\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", template)

    ctx: dict[str, Any] = {"targetApp": "demo-api"}
    mod._enrich_developer_context(ctx)
    assert ctx["scrapedMarkdownPaths"] == ["docs/PRD/scraped/demo-api/competitor.md"]


def test_resolve_repo_path_allows_inputs_read() -> None:
    mod = _load_agent_module()
    path = mod._resolve_repo_path("inputs/team-faq-bot.txt", write=False)
    assert path.name == "team-faq-bot.txt"


def test_resolve_repo_path_blocks_writes_outside_target_apps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    with pytest.raises(ValueError, match="writes only allowed"):
        mod._resolve_repo_path("docs/design/foo.md", write=True)


def test_resolve_repo_path_blocks_template_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "s3")

    with pytest.raises(ValueError, match="read-only"):
        mod._resolve_repo_path("target-apps/_template/golden/generated.py", write=True)


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


def test_failed_developer_handoff_is_written_without_files(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    captured: dict[str, Any] = {}

    def _capture(_app: str, handoff: dict[str, Any], *, context=None) -> str:
        captured.update(handoff)
        return "demo/handoffs/developer-handoff.json"

    monkeypatch.setattr(mod, "_write_developer_handoff", _capture)
    rel = mod._persist_developer_handoff(
        "demo",
        {"targetApp": "demo"},
        [],
        status="failed",
        error="model timeout",
    )

    assert rel is not None
    assert captured["status"] == "failed"
    assert captured["writtenFiles"] == []
    assert captured["error"] == "model timeout"


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


def test_validate_dev_write_path_blocks_verbatim_scaffold_files(tmp_path: Path) -> None:
    """Golden template files must come from dev_scaffold, not hand-written content —
    regression for a hand-rewritten app/startup_checks.py that shipped a syntax error."""
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-svc"
    (service / "app" / "routers").mkdir(parents=True)
    (service / "app" / "models").mkdir(parents=True)

    assert mod._validate_dev_write_path(service / "app" / "database.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "startup_checks.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "routers" / "health.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "models" / "pg_types.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "routers" / "items.py") is None


def test_validate_dev_write_path_blocks_all_template_files(tmp_path: Path) -> None:
    mod = _load_agent_module()
    template_file = tmp_path / "target-apps" / "_template" / "golden" / "database_golden.py"

    assert "read-only" in str(mod._validate_dev_write_path(template_file))
    assert "read-only" in mod.dev_scaffold("_template", "B")


def test_python_for_service_prefers_repo_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    repo_venv = tmp_path / ".venv" / "Scripts"
    repo_venv.mkdir(parents=True)
    repo_python = repo_venv / "python.exe"
    repo_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)

    assert mod._python_for_service(service) == str(repo_python)


def test_ensure_service_requirements_installed_runs_pip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    (service / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    import subprocess

    monkeypatch.setattr(subprocess, "run", _fake_run)
    ok, msg = mod._ensure_service_requirements_installed(service, "python")
    assert ok is True
    assert msg == ""
    assert calls[0][:4] == ["python", "-m", "pip", "install"]


def test_ensure_delivery_files_copies_template_seed_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    template = tmp_path / "target-apps" / "_template"
    template.mkdir(parents=True)
    (template / ".env.example").write_text("APP_ENV=test\n", encoding="utf-8")
    (template / "README.md").write_text("# Demo API\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", template)
    monkeypatch.setattr(mod, "_is_cloud_store", lambda: False)

    written = mod._ensure_delivery_files(
        "demo-api",
        ["target-apps/demo-api/app/main.py"],
        context=None,
    )
    assert "target-apps/demo-api/.env.example" in written
    assert "target-apps/demo-api/README.md" in written
    assert (service / ".env.example").read_text(encoding="utf-8") == "APP_ENV=test\n"
    assert (service / "README.md").read_text(encoding="utf-8") == "# Demo API\n"
