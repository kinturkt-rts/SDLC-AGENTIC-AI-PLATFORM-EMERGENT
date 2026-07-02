"""Tests for shared publish path helpers."""

from __future__ import annotations

from pathlib import Path

from agents._shared.gitlab_mcp_actions import (
    apps_branch_name,
    cloud_workspace_to_gitlab_dest,
    collect_feature_artifact_entries,
    collect_feature_artifact_paths,
    default_branch_name,
    dest_path_for_apps_repo,
    is_cloud_materialized_workspace,
    should_include_file,
)


def test_default_branch_name() -> None:
    assert default_branch_name("customer-feedback-hub") == "sdlc/customer-feedback-hub"


def test_apps_branch_name() -> None:
    assert apps_branch_name("notice-board-ui") == "notice-board-ui"


def test_dest_path_for_apps_repo() -> None:
    assert dest_path_for_apps_repo("target-apps/notice-board-ui/app/main.py", "notice-board-ui") == "app/main.py"
    assert dest_path_for_apps_repo("docs/PRD/notice-board-ui.md", "notice-board-ui") is None


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


def test_cloud_materialized_workspace_maps_to_monorepo_paths(tmp_path: Path) -> None:
    feature = "demo-app"
    cloud_root = tmp_path / feature
    (cloud_root / "app").mkdir(parents=True)
    (cloud_root / "app" / "main.py").write_text("# main", encoding="utf-8")
    (cloud_root / "db" / "sql").mkdir(parents=True)
    (cloud_root / "db" / "sql" / "001.sql").write_text("SELECT 1;", encoding="utf-8")
    (cloud_root / "docs" / "PRD").mkdir(parents=True)
    (cloud_root / "docs" / "PRD" / f"{feature}.md").write_text("# PRD", encoding="utf-8")
    (cloud_root / "handoffs").mkdir()
    (cloud_root / "handoffs" / "developer-handoff.json").write_text("{}", encoding="utf-8")
    cloud_root.joinpath("context.json").write_text("{}", encoding="utf-8")

    assert is_cloud_materialized_workspace(tmp_path, feature)

    entries = collect_feature_artifact_entries(feature, root=tmp_path)
    dests = {dest for _, dest in entries}
    assert f"target-apps/{feature}/app/main.py" in dests
    assert f"target-apps/{feature}/db/sql/001.sql" in dests
    assert f"docs/PRD/{feature}.md" in dests
    assert f"agents/pipeline/{feature}.developer-handoff.json" in dests
    assert f"agents/pipeline/{feature}.context.json" in dests


def test_cloud_workspace_to_gitlab_dest_diagram() -> None:
    dest = cloud_workspace_to_gitlab_dest("demo-app", "demo-app/docs/diagrams/demo-app.png")
    assert dest == "docs/diagrams/generated-diagrams/demo-app.png"
