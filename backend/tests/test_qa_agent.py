"""Tests for qa-agent path guards, pytest parsing, and context enrichment."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "qa-agent" / "qa_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("qa_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_parse_pytest_output_extracts_failed_and_passed() -> None:
    mod = _load_agent_module()
    output = """
tests/test_projects.py::test_create_project_returns_201 PASSED
tests/test_tasks.py::test_delete_task_returns_204 FAILED - assert 500 == 204
2 failed, 10 passed in 0.42s
"""
    parsed = mod._parse_pytest_output(output)
    assert parsed["failed"] == 2
    assert parsed["passed"] == 10
    assert len(parsed["failedTests"]) >= 1
    assert any("test_delete_task_returns_204" in f["id"] for f in parsed["failedTests"])


def test_allowed_write_path_tests_and_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    service = "demo-qa"
    root = tmp_path / "target-apps" / service
    (root / "tests").mkdir(parents=True)
    root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")

    assert mod._allowed_write_path(root / "tests" / "test_new.py", service)
    assert mod._allowed_write_path(root / "QA_REPORT.md", service)
    assert not mod._allowed_write_path(root / "app" / "main.py", service)


def test_resolve_repo_path_blocks_writes_outside_target_apps() -> None:
    mod = _load_agent_module()
    with pytest.raises(ValueError, match="writes only allowed"):
        mod._resolve_repo_path("docs/design/foo.md", write=True)


def test_enrich_qa_context_sets_default_commands() -> None:
    mod = _load_agent_module()
    ctx: dict[str, Any] = {"targetApp": "test-medium-app"}
    mod._enrich_qa_context(ctx)
    assert "testCommand" in ctx
    assert "coverageCommand" in ctx
    assert "test-medium-app" in ctx["testCommand"]
    assert ctx["targetAppDir"] == "target-apps/test-medium-app"


def test_default_test_command_format() -> None:
    mod = _load_agent_module()
    cmd = mod._default_test_command("test-dev")
    assert cmd == "cd target-apps/test-dev && pytest tests/ -q"
