"""Tests for devops-agent's status-write ordering guard (stale-pipeline race)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "devops-agent" / "devops_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("devops_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_not_superseded_when_no_pipeline_id() -> None:
    """Local/non-CI runs (no $CI_PIPELINE_ID) have no ordering info — never skip."""
    mod = _load_agent_module()
    assert mod._is_status_write_superseded(None, {"gitlabPipelineId": 99, "appUrl": "x"}) is False


def test_not_superseded_when_no_remote_handoff_yet() -> None:
    mod = _load_agent_module()
    assert mod._is_status_write_superseded(5, None) is False


def test_not_superseded_when_remote_has_no_live_url() -> None:
    """A remote handoff that recorded a failure (no appUrl) must not block this
    job's write, even if it's for a newer pipeline — only a genuine success is
    protected from being overwritten."""
    mod = _load_agent_module()
    remote = {"gitlabPipelineId": 99}
    assert mod._is_status_write_superseded(5, remote) is False


def test_superseded_when_remote_pipeline_is_newer_and_live() -> None:
    """The core stale-write bug from run 582cf1e8: an older/slower pipeline (id=5)
    finishing after a newer one (id=42) already recorded a live handoff must not
    clobber it."""
    mod = _load_agent_module()
    remote = {"gitlabPipelineId": 42, "appUrl": "http://example.com/app"}
    assert mod._is_status_write_superseded(5, remote) is True


def test_superseded_when_remote_pipeline_is_equal_and_live() -> None:
    mod = _load_agent_module()
    remote = {"gitlabPipelineId": 42, "appUrl": "http://example.com/app"}
    assert mod._is_status_write_superseded(42, remote) is True


def test_not_superseded_when_this_pipeline_is_newer() -> None:
    """This job represents the true latest deploy — its write (success or failure)
    must always be recorded, overriding an older remote record."""
    mod = _load_agent_module()
    remote = {"gitlabPipelineId": 5, "appUrl": "http://example.com/app"}
    assert mod._is_status_write_superseded(42, remote) is False


def test_main_skips_put_handoff_and_update_pipeline_run_when_superseded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: main() must not call put_handoff/update_pipeline_run at all when
    a newer pipeline already recorded a live handoff for this run."""
    mod = _load_agent_module()

    target = "demo-app"
    pipeline_dir = tmp_path / "agents" / "pipeline"
    pipeline_dir.mkdir(parents=True)
    handoff_path = pipeline_dir / f"{target}.devops-handoff.json"
    handoff_path.write_text(
        '{"targetApp": "demo-app", "appUrl": null, "gitlabPipelineId": 5, '
        '"gitlabCommitSha": "aaa111"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_PIPELINE_DIR", pipeline_dir)
    monkeypatch.setattr(mod, "is_s3_store", lambda: True)
    monkeypatch.setattr(mod, "resolve_run_id", lambda ctx: "run-582cf1e8")
    monkeypatch.setattr(
        mod,
        "get_handoff",
        lambda run_id, name: {"gitlabPipelineId": 42, "appUrl": "http://example.com/app"},
    )
    monkeypatch.setattr(mod, "run_deploy", lambda target, plan_only=False: 0)

    called = {"put_handoff": False, "update_pipeline_run": False}
    monkeypatch.setattr(
        mod, "put_handoff", lambda *a, **k: called.__setitem__("put_handoff", True)
    )
    monkeypatch.setattr(
        mod,
        "update_pipeline_run",
        lambda *a, **k: called.__setitem__("update_pipeline_run", True),
    )
    monkeypatch.setattr(
        mod, "resolve_cli_context", lambda *a, **k: ({"targetApp": target}, target)
    )
    monkeypatch.setattr(mod, "_ensure_pipeline_run_id_from_marker", lambda *a, **k: None)
    monkeypatch.setattr(mod, "run_task", lambda *a, **k: "ok")

    monkeypatch.setattr(sys, "argv", ["devops_agent.py", "--target-app", target, "--deploy"])
    mod.main()

    assert called == {"put_handoff": False, "update_pipeline_run": False}


def test_main_writes_status_when_this_pipeline_is_newest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirror case: this job IS the newest/true-final pipeline — its success must
    always be written, even though an older remote record exists."""
    mod = _load_agent_module()

    target = "demo-app"
    pipeline_dir = tmp_path / "agents" / "pipeline"
    pipeline_dir.mkdir(parents=True)
    handoff_path = pipeline_dir / f"{target}.devops-handoff.json"
    handoff_path.write_text(
        '{"targetApp": "demo-app", "appUrl": "http://example.com/app", '
        '"gitlabPipelineId": 42, "gitlabCommitSha": "bbb222"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_PIPELINE_DIR", pipeline_dir)
    monkeypatch.setattr(mod, "is_s3_store", lambda: True)
    monkeypatch.setattr(mod, "resolve_run_id", lambda ctx: "run-582cf1e8")
    monkeypatch.setattr(
        mod,
        "get_handoff",
        lambda run_id, name: {"gitlabPipelineId": 5, "appUrl": None},
    )
    monkeypatch.setattr(mod, "run_deploy", lambda target, plan_only=False: 0)

    called = {"put_handoff": False, "update_pipeline_run": False}
    monkeypatch.setattr(
        mod, "put_handoff", lambda *a, **k: called.__setitem__("put_handoff", True)
    )
    monkeypatch.setattr(
        mod,
        "update_pipeline_run",
        lambda *a, **k: called.__setitem__("update_pipeline_run", True) or True,
    )
    monkeypatch.setattr(
        mod, "resolve_cli_context", lambda *a, **k: ({"targetApp": target}, target)
    )
    monkeypatch.setattr(mod, "_ensure_pipeline_run_id_from_marker", lambda *a, **k: None)
    monkeypatch.setattr(mod, "run_task", lambda *a, **k: "ok")

    monkeypatch.setattr(sys, "argv", ["devops_agent.py", "--target-app", target, "--deploy"])
    mod.main()

    assert called == {"put_handoff": True, "update_pipeline_run": True}
