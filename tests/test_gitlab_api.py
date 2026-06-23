"""Unit tests for GitLab API helpers (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from _shared.gitlab_api import _commit_actions_for_files, encode_project_id


def test_encode_project_id_numeric() -> None:
    assert encode_project_id("12345") == "12345"


def test_encode_project_id_path() -> None:
    encoded = encode_project_id("junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform")
    assert "%2F" in encoded
    assert "/" not in encoded


def test_commit_actions_text_content() -> None:
    actions = _commit_actions_for_files(
        [{"path": "README.md", "content": "# Hello"}],
        actions={"README.md": "create"},
    )
    assert actions[0]["action"] == "create"
    assert actions[0]["content"] == "# Hello"
    assert "encoding" not in actions[0]
