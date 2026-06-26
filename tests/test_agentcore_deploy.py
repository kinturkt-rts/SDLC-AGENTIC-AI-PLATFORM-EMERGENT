"""Tests for AgentCore deployment helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_bootstrap_inserts_paths_and_resolves_repo_root(repo_root: Path) -> None:
    deploy_dir = repo_root / "deploy" / "agentcore"
    sys.path.insert(0, str(deploy_dir))
    try:
        from agentcore_runtime.bootstrap import AGENT_MODULE_MAP, bootstrap, repo_root as rr

        root = bootstrap()
        assert root == repo_root
        assert rr() == repo_root
        assert str(root) in sys.path
        assert str(root / "agents") in sys.path
        assert "architect-agent" in AGENT_MODULE_MAP
    finally:
        if str(deploy_dir) in sys.path:
            sys.path.remove(str(deploy_dir))


def test_agentcore_runtime_url_default() -> None:
    from agents._shared.agentcore_serve import agentcore_runtime_url

    assert agentcore_runtime_url().startswith("http://127.0.0.1:9000")


def test_a2a_server_resolves_agent_name(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deploy_dir = repo_root / "deploy" / "agentcore"
    sys.path.insert(0, str(deploy_dir))
    monkeypatch.delenv("AGENTCORE_AGENT", raising=False)
    try:
        from a2a_server import _resolve_agent_name
        from agentcore_runtime.bundles import BUNDLE_FACTORIES

        assert _resolve_agent_name("architect-agent") == "architect-agent"
        monkeypatch.setenv("AGENTCORE_AGENT", "qa-agent")
        assert _resolve_agent_name(None) == "qa-agent"
        assert "gitlab-agent" in BUNDLE_FACTORIES
    finally:
        if str(deploy_dir) in sys.path:
            sys.path.remove(str(deploy_dir))
