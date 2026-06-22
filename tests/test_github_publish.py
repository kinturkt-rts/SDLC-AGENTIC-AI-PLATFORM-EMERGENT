"""Tests for GitHub publish helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents._shared.github_publish import (
    collect_feature_artifact_paths,
    default_branch_name,
    should_include_file,
)


def test_default_branch_name() -> None:
    assert default_branch_name("customer-feedback-hub") == "sdlc/customer-feedback-hub"


def test_should_exclude_env_and_venv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=x", encoding="utf-8")
    venv_file = tmp_path / ".venv" / "pyvenv.cfg"
    venv_file.parent.mkdir()
    venv_file.write_text("home = /usr/bin", encoding="utf-8")
    ok_file = tmp_path / "app.py"
    ok_file.write_text("print('ok')", encoding="utf-8")

    assert not should_include_file(env_file)
    assert not should_include_file(venv_file)
    assert should_include_file(ok_file)


def test_collect_feature_artifact_paths_includes_prd_and_app(tmp_path: Path) -> None:
    feature = "demo-app"
    (tmp_path / "target-apps" / feature / "app").mkdir(parents=True)
    (tmp_path / "target-apps" / feature / "app" / "main.py").write_text("# main", encoding="utf-8")
    (tmp_path / "docs" / "PRD").mkdir(parents=True)
    (tmp_path / "docs" / "PRD" / f"{feature}.md").write_text("# PRD", encoding="utf-8")

    paths = collect_feature_artifact_paths(feature, root=tmp_path)
    assert f"target-apps/{feature}/app/main.py" in paths
    assert f"docs/PRD/{feature}.md" in paths
    assert not any(p.endswith(".env") for p in paths)


def test_github_feature_branch_uses_app_slug() -> None:
    from agents._shared.github_publish import github_feature_branch

    assert github_feature_branch("training-compliance") == "training-compliance"


def test_dest_path_for_showcase_repo() -> None:
    from agents._shared.github_publish import dest_path_for_showcase_repo

    assert dest_path_for_showcase_repo(
        "target-apps/training-compliance/app/main.py",
        "training-compliance",
    ) == "training-compliance/app/main.py"
    assert dest_path_for_showcase_repo(
        "docs/PRD/training-compliance.md",
        "training-compliance",
    ) == "docs/PRD/training-compliance.md"


def test_collect_showcase_publish_files_removes_target_apps_prefix(tmp_path: Path) -> None:
    from agents._shared.github_publish import collect_showcase_publish_files

    feature = "demo-app"
    app_dir = tmp_path / "target-apps" / feature / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "docs" / "PRD").mkdir(parents=True)
    (tmp_path / "docs" / "PRD" / f"{feature}.md").write_text("# PRD", encoding="utf-8")

    files = collect_showcase_publish_files(feature, root=tmp_path)
    paths = {f["path"] for f in files}
    assert f"{feature}/app/main.py" in paths
    assert f"docs/PRD/{feature}.md" in paths
    assert not any(p.startswith("target-apps/") for p in paths)


def test_github_repo_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    from agents._shared.github_mcp_publish import github_repo_config

    monkeypatch.delenv("GITHUB_OWNER", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    monkeypatch.delenv("GITHUB_BASE_BRANCH", raising=False)
    cfg = github_repo_config()
    assert cfg["owner"] == "kinturkt-rts"
    assert cfg["repo"] == "SDLC-Agentic-AI-Platform"
    assert cfg["base"] == "main"
