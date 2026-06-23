"""Unit tests for GitLab env helpers (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from _shared.gitlab_api import (  # noqa: E402
    gitlab_api_url,
    gitlab_base_branch,
    gitlab_personal_access_token,
    gitlab_project_path,
)


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
