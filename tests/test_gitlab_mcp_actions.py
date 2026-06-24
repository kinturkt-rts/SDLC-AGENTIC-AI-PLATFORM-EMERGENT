"""Tests for GitLab MCP actions (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from _shared.gitlab_mcp_actions import (  # noqa: E402
    _is_branch_not_found,
    _mcp_error_message,
    _publish_commit_message,
    _publish_error,
    create_mr_note,
    gitlab_api_url,
    gitlab_base_branch,
    gitlab_personal_access_token,
    gitlab_project_path,
)
from _shared.gitlab_mcp_client import GitLabMcpError  # noqa: E402


def test_create_mr_note_requires_body() -> None:
    result = create_mr_note(mr_iid=1, body="   ")
    assert result["ok"] is False
    assert "body" in result["error"].lower()


def test_gitlab_project_path_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_PROJECT_PATH", "group/my-project")
    assert gitlab_project_path() == "group/my-project"


def test_gitlab_base_branch_defaults_to_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_BASE_BRANCH", raising=False)
    assert gitlab_base_branch() == "main"


def test_gitlab_api_url_strips_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_API_URL", "https://gitlab.example.com/api/v4/")
    assert gitlab_api_url() == "https://gitlab.example.com/api/v4"


def test_gitlab_personal_access_token_prefers_pat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITLAB_PERSONAL_ACCESS_TOKEN", "glpat-test")
    monkeypatch.setenv("GITLAB_TOKEN", "other")
    assert gitlab_personal_access_token() == "glpat-test"


def test_gitlab_personal_access_token_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GL_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="GITLAB_PERSONAL_ACCESS_TOKEN"):
        gitlab_personal_access_token()


def test_mcp_error_message_unwraps_nested_exception_group() -> None:
    inner = GitLabMcpError("Token is expired")
    wrapped = BaseExceptionGroup("task group", [BaseExceptionGroup("inner", [inner])])
    assert _mcp_error_message(wrapped) == "Token is expired"


def test_is_branch_not_found_detects_gitlab_message() -> None:
    exc = GitLabMcpError("Branch Not Found: notice-board-ui")
    assert _is_branch_not_found(exc) is True
    assert _is_branch_not_found(GitLabMcpError("commit failed")) is False


def test_publish_commit_message_generic_and_batched() -> None:
    assert _publish_commit_message("notice-board-ui") == "feat(notice-board-ui): SDLC pipeline output"
    assert (
        _publish_commit_message("notice-board-ui", batch=2, total=3)
        == "feat(notice-board-ui): SDLC pipeline output (batch 2/3)"
    )


def test_publish_error_includes_project_and_unwraps_group() -> None:
    inner = GitLabMcpError("file already exists")
    wrapped = BaseExceptionGroup("task group", [inner])
    cfg = {"project": "group/apps", "base": "main"}
    result = _publish_error("notice-board-ui", "notice-board-ui", cfg, wrapped)
    assert result["ok"] is False
    assert result["error"] == "file already exists"
    assert result["gitlabProject"] == "group/apps"
    assert result["gitlabBaseBranch"] == "main"
