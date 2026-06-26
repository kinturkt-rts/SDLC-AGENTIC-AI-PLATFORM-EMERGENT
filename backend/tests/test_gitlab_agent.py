"""Tests for gitlab-agent handoff helpers and publish branch naming."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO / "agents" / "gitlab-agent" / "gitlab_agent.py"


def test_publish_branch_name_is_stable_per_app() -> None:
    sys.path.insert(0, str(_REPO / "agents"))
    from _shared.gitlab_mcp_actions import publish_branch_name

    assert publish_branch_name("training-compliance") == "sdlc/training-compliance"
    assert publish_branch_name("jwt-rag-streamlit") == "sdlc/jwt-rag-streamlit"
    assert publish_branch_name("training-compliance") == publish_branch_name("Training_Compliance")


def test_branch_tree_url_encodes_slashes() -> None:
    sys.path.insert(0, str(_REPO / "agents"))
    from _shared.gitlab_mcp_actions import _branch_tree_url

    url = _branch_tree_url(
        "https://code.junodev.net/group/project",
        "sdlc/training-compliance",
    )
    assert url.endswith("/-/tree/sdlc%2Ftraining-compliance")


def test_commit_actions_normalize_empty_content() -> None:
    sys.path.insert(0, str(_REPO / "agents"))
    from _shared.gitlab_mcp_actions import _commit_actions

    batch = [{"path": "pkg/__init__.py", "content": ""}]
    actions = _commit_actions(batch, set())
    assert actions[0]["content"] == "\n"
    assert actions[0]["action"] == "create"

    update_actions = _commit_actions(batch, {"pkg/__init__.py"})
    assert update_actions[0]["action"] == "update"
    assert update_actions[0]["content"] == "\n"


def _load_gitlab_agent_module():
    spec = importlib.util.spec_from_file_location("gitlab_agent_mod", _AGENT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gitlab_agent_mod"] = mod
    sys.path.insert(0, str(_REPO / "agents"))
    spec.loader.exec_module(mod)
    return mod


def test_write_gitlab_handoff_creates_json(tmp_path: Path, monkeypatch) -> None:
    mod = _load_gitlab_agent_module()
    pipeline = tmp_path / "agents" / "pipeline"
    pipeline.mkdir(parents=True)
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)

    rel = mod._write_gitlab_handoff(
        "training-compliance",
        {"status": "published", "branch": "sdlc/training-compliance"},
    )

    handoff_path = tmp_path / Path(rel)
    assert handoff_path.is_file()
    data = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert data["branch"] == "sdlc/training-compliance"
