"""Tests for GitLab MCP actions (no network)."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

from _shared.gitlab_mcp_actions import (  # noqa: E402
    _collect_apps_repo_publish_files,
    _collect_input_brief_entries,
    _is_branch_not_found,
    _mcp_error_message,
    _publish_commit_message,
    _publish_error,
    apps_branch_name,
    cloud_workspace_to_gitlab_dest,
    collect_feature_artifact_entries,
    collect_feature_artifact_paths,
    create_mr_note,
    default_branch_name,
    dest_path_for_apps_repo,
    gitlab_api_url,
    gitlab_base_branch,
    gitlab_personal_access_token,
    gitlab_project_path,
    is_cloud_materialized_workspace,
    pipeline_run_marker_repo_rel,
    sanitize_publish_content_for_waf,
    should_include_file,
    write_pipeline_run_marker,
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


def test_default_branch_name() -> None:
    assert default_branch_name("customer-feedback-hub") == "sdlc/customer-feedback-hub"


def test_apps_branch_name() -> None:
    assert apps_branch_name("notice-board-ui") == "notice-board-ui"


def test_dest_path_for_apps_repo() -> None:
    assert dest_path_for_apps_repo("target-apps/notice-board-ui/app/main.py", "notice-board-ui") == "app/main.py"
    assert dest_path_for_apps_repo("docs/PRD/notice-board-ui.md", "notice-board-ui") is None
    assert dest_path_for_apps_repo("inputs/notice-board-ui.txt", "notice-board-ui") == "inputs/notice-board-ui.txt"


def test_cloud_workspace_maps_input_brief_for_apps_repo() -> None:
    dest = cloud_workspace_to_gitlab_dest("demo-app", "demo-app/inputs/demo-app.txt")
    assert dest == "inputs/demo-app.txt"
    assert cloud_workspace_to_gitlab_dest("demo-app", "demo-app/telemetry/demo-app.json") is None


def test_cloud_materialized_includes_input_brief(tmp_path: Path) -> None:
    feature = "demo-app"
    cloud_root = tmp_path / feature
    (cloud_root / "inputs").mkdir(parents=True)
    (cloud_root / "inputs" / f"{feature}.txt").write_text("# brief\n", encoding="utf-8")
    (cloud_root / "app").mkdir(parents=True)
    (cloud_root / "app" / "main.py").write_text("# main", encoding="utf-8")

    entries = collect_feature_artifact_entries(feature, root=tmp_path)
    dests = {dest for _, dest in entries}
    assert f"inputs/{feature}.txt" in dests
    assert f"target-apps/{feature}/app/main.py" in dests


def test_monorepo_publish_includes_input_brief(tmp_path: Path) -> None:
    feature = "demo-app"
    cloud_root = tmp_path / feature
    (cloud_root / "inputs").mkdir(parents=True)
    (cloud_root / "inputs" / f"{feature}.txt").write_text("# brief\n", encoding="utf-8")
    (cloud_root / "app").mkdir(parents=True)
    (cloud_root / "app" / "main.py").write_text("# main", encoding="utf-8")

    from _shared.gitlab_mcp_actions import _collect_monorepo_publish_files

    files = _collect_monorepo_publish_files(feature, root=tmp_path)
    by_path = {item["path"]: item for item in files}
    assert f"inputs/{feature}.txt" in by_path
    py_item = by_path[f"target-apps/{feature}/app/main.py"]
    assert py_item["binary"] is True
    assert base64.b64decode(py_item["content"]).decode("utf-8") == "# main"


def test_apps_repo_publish_includes_local_input_brief(tmp_path: Path) -> None:
    feature = "demo-app"
    (tmp_path / "target-apps" / feature / "app").mkdir(parents=True)
    (tmp_path / "target-apps" / feature / "app" / "main.py").write_text("# main", encoding="utf-8")
    (tmp_path / "inputs").mkdir(parents=True)
    (tmp_path / "inputs" / f"{feature}.txt").write_text("# requirements brief\n", encoding="utf-8")

    files = _collect_apps_repo_publish_files(feature, root=tmp_path)
    paths = {item["path"] for item in files}
    assert "app/main.py" in paths
    assert f"inputs/{feature}.txt" in paths


def test_apps_repo_publish_includes_ci_yml_from_backend_scripts(tmp_path: Path) -> None:
    """Cloud publish roots omit scripts/; CI must still resolve from packaged backend."""
    feature = "demo-app"
    (tmp_path / "target-apps" / feature / "app").mkdir(parents=True)
    (tmp_path / "target-apps" / feature / "app" / "main.py").write_text("# main", encoding="utf-8")

    files = _collect_apps_repo_publish_files(feature, root=tmp_path)
    by_path = {item["path"]: item for item in files}
    assert ".gitlab-ci.yml" in by_path
    content = by_path[".gitlab-ci.yml"]["content"]
    if by_path[".gitlab-ci.yml"].get("binary") or str(
        by_path[".gitlab-ci.yml"].get("encoding") or ""
    ).lower() == "base64":
        content = base64.b64decode(content).decode("utf-8")
    assert "mcr.microsoft.com/powershell:7.4-debian-12" in content
    assert "target-app:deploy" in content


def test_collect_input_brief_from_context_path(tmp_path: Path) -> None:
    feature = "office-equipment-checkout"
    (tmp_path / "inputs").mkdir(parents=True)
    brief = tmp_path / "inputs" / "office-equipment-checkout.txt"
    brief.write_text("# brief\n", encoding="utf-8")
    ctx = tmp_path / "agents" / "pipeline"
    ctx.mkdir(parents=True)
    (ctx / f"{feature}.context.json").write_text(
        '{"inputFile": "inputs/office-equipment-checkout.txt"}',
        encoding="utf-8",
    )

    entries = _collect_input_brief_entries(feature, root=tmp_path)
    assert ("inputs/office-equipment-checkout.txt", "inputs/office-equipment-checkout.txt") in entries


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
    assert dest == "docs/generated-diagrams/demo-app.png"

    dest_new = cloud_workspace_to_gitlab_dest("demo-app", "demo-app/docs/generated-diagrams/demo-app.png")
    assert dest_new == "docs/generated-diagrams/demo-app.png"


def test_cloud_handoff_merge_includes_env_example_and_readme(tmp_path: Path) -> None:
    feature = "demo-app"
    cloud_root = tmp_path / feature
    (cloud_root / "app").mkdir(parents=True)
    (cloud_root / "app" / "main.py").write_text("# main", encoding="utf-8")
    (cloud_root / ".env.example").write_text("APP_ENV=test\n", encoding="utf-8")
    (cloud_root / "README.md").write_text("# Demo\n", encoding="utf-8")
    handoff = {
        "writtenFiles": [
            f"target-apps/{feature}/app/main.py",
            f"target-apps/{feature}/.env.example",
            f"target-apps/{feature}/README.md",
        ]
    }
    (cloud_root / "handoffs").mkdir()
    (cloud_root / "handoffs" / "developer-handoff.json").write_text(
        __import__("json").dumps(handoff),
        encoding="utf-8",
    )

    dests = {dest for _, dest in collect_feature_artifact_entries(feature, root=tmp_path)}
    assert f"target-apps/{feature}/.env.example" in dests
    assert f"target-apps/{feature}/README.md" in dests


def test_sanitize_publish_content_for_waf_only_on_cloudfront(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "curl http://localhost:8000/health"
    monkeypatch.setenv("GITLAB_MCP_URL", "https://d123.cloudfront.net/mcp")
    monkeypatch.delenv("GITLAB_MCP_HTTP_DIRECT_URL", raising=False)
    assert sanitize_publish_content_for_waf(text) == "curl http://127.0.0.1:8000/health"

    monkeypatch.setenv(
        "GITLAB_MCP_HTTP_DIRECT_URL",
        "http://gitlab-mcp-alb-123.us-east-2.elb.amazonaws.com/mcp",
    )
    assert sanitize_publish_content_for_waf(text) == "curl http://127.0.0.1:8000/health"


def test_write_pipeline_run_marker_monorepo(tmp_path: Path) -> None:
    feature = "expense-tracker"
    (tmp_path / "target-apps" / feature / "app").mkdir(parents=True)
    (tmp_path / "target-apps" / feature / "app" / "main.py").write_text("# x", encoding="utf-8")

    rel = write_pipeline_run_marker(feature, "run-abc-123", root=tmp_path)
    assert rel == pipeline_run_marker_repo_rel(feature)
    marker = tmp_path / rel
    assert marker.is_file()
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["runId"] == "run-abc-123"
    assert data["targetApp"] == feature

    paths = collect_feature_artifact_paths(feature, root=tmp_path)
    assert rel in paths

    apps_files = _collect_apps_repo_publish_files(feature, root=tmp_path)
    apps_paths = {item["path"] for item in apps_files}
    assert ".sdlc/pipeline-run.json" in apps_paths


def test_write_pipeline_run_marker_cloud_workspace(tmp_path: Path) -> None:
    feature = "demo-app"
    cloud_root = tmp_path / feature
    (cloud_root / "app").mkdir(parents=True)
    (cloud_root / "app" / "main.py").write_text("# main", encoding="utf-8")

    rel = write_pipeline_run_marker(feature, "run-cloud-1", root=tmp_path)
    assert rel == f"target-apps/{feature}/.sdlc/pipeline-run.json"
    assert (cloud_root / ".sdlc" / "pipeline-run.json").is_file()

    dests = {dest for _, dest in collect_feature_artifact_entries(feature, root=tmp_path)}
    assert rel in dests


def test_write_pipeline_run_marker_skips_without_run_id(tmp_path: Path) -> None:
    feature = "demo-app"
    (tmp_path / "target-apps" / feature).mkdir(parents=True)
    assert write_pipeline_run_marker(feature, "  ", root=tmp_path) is None
    assert write_pipeline_run_marker(feature, "", root=tmp_path) is None
