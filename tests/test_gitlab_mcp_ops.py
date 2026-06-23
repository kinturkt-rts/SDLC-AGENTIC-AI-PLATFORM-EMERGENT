"""Tests for GitLab MCP ops helpers (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from _shared.gitlab_mcp_ops import create_mr_note  # noqa: E402


def test_create_mr_note_requires_body() -> None:
    result = create_mr_note(mr_iid=1, body="   ")
    assert result["ok"] is False
    assert "body" in result["error"].lower()
