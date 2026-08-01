"""Guards for product-agent (AgentCore PRD path + local CLI safety)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "product-agent" / "product_agent.py"


def _load_agent_module():
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec = importlib.util.spec_from_file_location("product_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pa = _load_agent_module()


def test_infer_target_app_requires_hyphenated_slug() -> None:
    assert pa._infer_target_app_from_text("Create PRD for inventory-app") == "inventory-app"
    assert pa._infer_target_app_from_text('targetApp: "sales-dashboard"') == "sales-dashboard"
    # Bare "for users" must not invent a slug
    assert pa._infer_target_app_from_text("Create a PRD for users with roles") is None


def test_jira_backlog_outcome_classifies_keys() -> None:
    created, keys = pa._jira_backlog_outcome(
        "## Epic\n[SAAP-1] Feature\n## User Stories\n| SAAP-2 | Story | 3 | High |"
    )
    assert created == "created"
    assert keys == ["SAAP-1", "SAAP-2"]

    partial, pkeys = pa._jira_backlog_outcome(
        "Created SAAP-9 then tool call budget exceeded; rest not created."
    )
    assert partial == "partial"
    assert pkeys == ["SAAP-9"]

    failed, fkeys = pa._jira_backlog_outcome("No tickets created — writes are disabled.")
    assert failed == "failed"
    assert fkeys == []


def test_read_text_file_rejects_path_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_REPO_ROOT", tmp_path)
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError, match="escapes repository root"):
        pa._read_text_file(str(Path("..") / outside.name))


def test_a2a_write_tools_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRODUCT_A2A_ALLOW_WRITES", raising=False)
    assert pa._a2a_write_tools_allowed() is False
    monkeypatch.setenv("PRODUCT_A2A_ALLOW_WRITES", "true")
    assert pa._a2a_write_tools_allowed() is True
