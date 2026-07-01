"""AgentCore Dockerfiles must COPY the full agents/ tree (includes agents/_shared/)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_CANONICAL = _BACKEND / "deploy" / "agentcore" / "Dockerfile"
_REQUIRED_COPY_LINES = (
    "COPY agents /app/agents",
    "COPY a2a /app/a2a",
    "COPY scripts /app/scripts",
    "COPY config /app/config",
)
_SHARED_MODULES = (
    "artifact_store.py",
    "pipeline_context.py",
    "sdlc_pipeline.py",
    "env.py",
    "runner.py",
    "a2a_invoke.py",
)


def _dockerfile_paths() -> list[Path]:
    paths = [_BACKEND / "Dockerfile", _CANONICAL]
    agentcore = _BACKEND / ".bedrock_agentcore"
    if agentcore.is_dir():
        for child in sorted(agentcore.iterdir()):
            dockerfile = child / "Dockerfile"
            if dockerfile.is_file():
                paths.append(dockerfile)
    return paths


def _dockerignore_blocks(path: Path) -> bool:
    """Approximate backend/.dockerignore — path relative to backend root."""
    rel = path.relative_to(_BACKEND).as_posix()
    blocked_prefixes = (
        ".git/",
        ".cursor/",
        ".bedrock_agentcore/",
        ".orchestrator/",
        "target-apps/",
        "infrastructure/",
        "inputs/",
        "docs/",
    )
    blocked_suffixes = ("/__pycache__/", "/.pytest_cache/", "/.venv/", "/node_modules/")
    if rel.endswith(".md") and rel != "deploy/agentcore/README.md":
        return True
    if rel.startswith(".env"):
        return True
    for prefix in blocked_prefixes:
        if rel.startswith(prefix):
            return True
    for suffix in blocked_suffixes:
        if suffix.strip("/") in rel:
            return True
    return False


def test_agentcore_dockerfile_gitlab_mcp_binary_optional() -> None:
    text = _CANONICAL.read_text(encoding="utf-8")
    assert "INSTALL_GITLAB_MCP_BINARY" in text
    assert "gitlab-mcp-server-linux-arm64" in text
    assert 'if [ "$INSTALL_GITLAB_MCP_BINARY" = "true" ]; then' in text


def test_gitlab_mcp_service_dockerfile_exists() -> None:
    mcp_dockerfile = _BACKEND / "deploy" / "gitlab-mcp-server" / "Dockerfile"
    assert mcp_dockerfile.is_file()
    text = mcp_dockerfile.read_text(encoding="utf-8")
    assert "jmrplens/gitlab-mcp-server" in text
    assert "--gitlab-url=https://code.junodev.net" in text


@pytest.mark.parametrize("dockerfile", _dockerfile_paths(), ids=lambda p: p.relative_to(_BACKEND).as_posix())
def test_agentcore_dockerfile_sets_agent_bundle(dockerfile: Path) -> None:
    rel = dockerfile.relative_to(_BACKEND).as_posix()
    if rel == "deploy/agentcore/Dockerfile" or rel == "Dockerfile":
        expected = "orchestrator-agent"
    elif rel.startswith(".bedrock_agentcore/"):
        folder = rel.split("/")[1]
        if folder == "orchestrator_agent_vpc":
            expected = "orchestrator-agent"
        else:
            expected = folder.replace("_", "-")
    else:
        return
    text = dockerfile.read_text(encoding="utf-8")
    assert f"ARG AGENTCORE_AGENT={expected}" in text, f"{rel} should default AGENTCORE_AGENT to {expected}"


@pytest.mark.parametrize("dockerfile", _dockerfile_paths(), ids=lambda p: p.relative_to(_BACKEND).as_posix())
def test_agentcore_dockerfile_copies_agents_tree(dockerfile: Path) -> None:
    text = dockerfile.read_text(encoding="utf-8")
    for line in _REQUIRED_COPY_LINES:
        assert line in text, f"{dockerfile.name} missing {line!r} (agents/_shared lives under agents/)"
    assert "COPY . ." not in text, f"{dockerfile} must not use COPY . . — use explicit agents/ COPY"
    assert 'CMD ["python", "a2a_server.py"]' in text


def test_sync_script_exists() -> None:
    script = _BACKEND / "scripts" / "sync-agentcore-dockerfiles.ps1"
    assert script.is_file()


def test_dockerignore_allows_agents_shared() -> None:
    shared_dir = _BACKEND / "agents" / "_shared"
    assert shared_dir.is_dir()
    for name in _SHARED_MODULES:
        path = shared_dir / name
        assert path.is_file(), f"missing {name}"
        assert not _dockerignore_blocks(path), f".dockerignore would block {path.relative_to(_BACKEND)}"


def test_simulated_container_imports_shared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mimic COPY agents /app/agents — specialists must import _shared in-container."""
    app_root = tmp_path / "app"
    shutil.copytree(_BACKEND / "agents", app_root / "agents")
    shutil.copytree(_BACKEND / "a2a", app_root / "a2a")
    shutil.copytree(_BACKEND / "config", app_root / "config")
    scripts_dest = app_root / "scripts"
    scripts_dest.mkdir()
    for name in ("apply_sql_to_rds.py",):
        src = _BACKEND / "scripts" / name
        if src.is_file():
            shutil.copy2(src, scripts_dest / name)

    monkeypatch.setenv("REPO_ROOT", str(app_root))
    deploy_dest = app_root / "deploy" / "agentcore"
    deploy_dest.mkdir(parents=True)
    shutil.copytree(_BACKEND / "deploy" / "agentcore", deploy_dest, dirs_exist_ok=True)
    monkeypatch.chdir(deploy_dest)
    sys.path.insert(0, str(app_root / "agents"))
    sys.path.insert(0, str(deploy_dest))

    from _shared import artifact_store, pipeline_context, sdlc_pipeline  # noqa: PLC0415

    assert artifact_store.repo_root() == app_root.resolve()
    assert callable(pipeline_context.slugify)
    assert callable(sdlc_pipeline.run_sdlc_pipeline)

    from agentcore_runtime.bootstrap import repo_root  # noqa: PLC0415

    assert repo_root() == app_root.resolve()
