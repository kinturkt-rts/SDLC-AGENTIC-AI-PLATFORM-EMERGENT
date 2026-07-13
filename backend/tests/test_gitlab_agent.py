"""Tests for gitlab-agent handoff helpers and publish branch naming."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

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


def test_parse_publish_request_from_context_block() -> None:
    mod = _load_gitlab_agent_module()
    message = (
        "Publish SDLC artifacts for pr-diff-summarizer to GitLab.\n\n"
        'Context:\n{"targetApp": "pr-diff-summarizer", "runId": "92099e5f-be02-4894-9276-67f2e5a72343"}'
    )
    parsed = mod.parse_publish_request(message)
    assert parsed is not None
    app, run_id, ctx = parsed
    assert app == "pr-diff-summarizer"
    assert run_id == "92099e5f-be02-4894-9276-67f2e5a72343"
    assert ctx["targetApp"] == "pr-diff-summarizer"


def test_agentcore_publish_is_blocked_when_developer_failed(monkeypatch) -> None:
    mod = _load_gitlab_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")

    with (
        patch(
            "_shared.artifact_store.classify_developer_readiness",
            return_value=("failed", {"status": "failed", "error": "developer model timeout"}),
        ),
        patch("_shared.artifact_store.put_handoff") as put_handoff,
        patch("_shared.artifact_store.materialize_run") as materialize,
    ):
        summary, handoff = mod.run_publish_for_agentcore(
            "contacts-api",
            "run-developer-failed",
            {"targetApp": "contacts-api"},
        )

    assert handoff["status"] == "failed"
    assert "developer-agent failed" in handoff["error"]
    assert "developer model timeout" in handoff["error"]
    assert "failed" in summary
    put_handoff.assert_called_once()
    materialize.assert_not_called()


def test_agentcore_publish_is_blocked_when_no_artifacts(monkeypatch) -> None:
    mod = _load_gitlab_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")

    with (
        patch(
            "_shared.artifact_store.classify_developer_readiness",
            return_value=("missing", {"status": "in_progress"}),
        ),
        patch("_shared.artifact_store.put_handoff") as put_handoff,
        patch("_shared.artifact_store.materialize_run") as materialize,
    ):
        summary, handoff = mod.run_publish_for_agentcore(
            "contacts-api",
            "run-empty",
            {"targetApp": "contacts-api"},
        )

    assert handoff["status"] == "failed"
    assert "no publishable" in handoff["error"]
    put_handoff.assert_called_once()
    materialize.assert_not_called()


def test_agentcore_publish_proceeds_on_partial_developer_delivery(monkeypatch) -> None:
    """Developer runtime died before finalizing, but app artifacts exist — publish."""
    mod = _load_gitlab_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")

    published = {"status": "published", "branch": "sdlc/contacts-api", "pathsPublished": ["a.py"]}
    with (
        patch(
            "_shared.artifact_store.classify_developer_readiness",
            return_value=("partial", {"status": "in_progress"}),
        ),
        patch(
            "_shared.artifact_store.list_run_artifact_keys",
            return_value=["contacts-api/app/main.py"],
        ),
        patch("_shared.artifact_store.materialize_run", return_value=None) as materialize,
        patch("_shared.artifact_store.put_handoff") as put_handoff,
        patch.object(mod, "run_publish", return_value=("## status\npublished\n", published)) as run_publish,
    ):
        summary, handoff = mod.run_publish_for_agentcore(
            "contacts-api",
            "run-partial",
            {"targetApp": "contacts-api"},
        )

    assert handoff["status"] == "published"
    materialize.assert_called_once()
    run_publish.assert_called_once()
    put_handoff.assert_called_once()
