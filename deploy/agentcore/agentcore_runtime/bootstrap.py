"""Repo path setup for AgentCore container entrypoints."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

# deploy/agentcore/agentcore_runtime/bootstrap.py -> repo root is parents[3]
_DEPLOY_AGENTCORE = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]

# agent registry name -> (folder under agents/, python module stem)
AGENT_MODULE_MAP: dict[str, tuple[str, str]] = {
    "orchestrator-agent": ("orchestrator-agent", "orchestrator_agent"),
    "product-agent": ("product-agent", "product_agent"),
    "architect-agent": ("architect-agent", "architect_agent"),
    "developer-agent": ("developer-agent", "developer_agent"),
    "qa-agent": ("qa-agent", "qa_agent"),
    "devops-agent": ("devops-agent", "devops_agent"),
    "security-agent": ("security-agent", "security_agent"),
    "database-agent": ("database-agent", "database_agent"),
    "web-crawler-agent": ("web-crawler", "web_crawler_agent"),
    "gitlab-agent": ("gitlab-agent", "gitlab_agent"),
}


def repo_root() -> Path:
    """Return repository root (overridable via REPO_ROOT env in containers)."""
    env_root = os.getenv("REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return _REPO_ROOT


def deploy_agentcore_dir() -> Path:
    return _DEPLOY_AGENTCORE


def _load_repo_env(root: Path) -> None:
    env_path = root / "agents" / "_shared" / "env.py"
    spec = importlib.util.spec_from_file_location("agent_repo_env", env_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load env module from {env_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.load_repo_env()


def bootstrap() -> Path:
    """Insert repo paths and load .env; return repo root."""
    root = repo_root()
    agents_dir = root / "agents"
    deploy_dir = root / "deploy" / "agentcore"

    for path in (str(deploy_dir), str(agents_dir), str(root)):
        if path not in sys.path:
            sys.path.insert(0, path)

    os.environ.setdefault("REPO_ROOT", str(root))
    _load_repo_env(root)
    return root


def import_agent_module(agent_name: str) -> ModuleType:
    """Load agents/<folder>/<module>.py for the given registry agent name."""
    if agent_name not in AGENT_MODULE_MAP:
        known = ", ".join(sorted(AGENT_MODULE_MAP))
        raise KeyError(f"Unknown agent {agent_name!r}. Known: {known}")

    folder, module_stem = AGENT_MODULE_MAP[agent_name]
    module_path = repo_root() / "agents" / folder / f"{module_stem}.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"Agent module not found: {module_path}")

    spec = importlib.util.spec_from_file_location(module_stem, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_stem] = module
    spec.loader.exec_module(module)
    return module


def env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}
