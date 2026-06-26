"""Agent transport configuration for the SDLC pipeline orchestrator.

Loads ``config/orchestrator/agents.json`` and applies environment-variable
overrides so a single AWS-deploy can flip an agent from ``cli`` to
``a2a-http`` without touching the file.

Recognised env vars (per agent name, uppercased + dashes -> underscores):

- ``AGENT_MODE_<NAME>``  -- ``cli`` | ``a2a-http`` | ``dry-run``
- ``AGENT_URL_<NAME>``   -- AgentCore runtime URL (used when mode is a2a-http)

Example::

    AGENT_MODE_PRODUCT_AGENT=a2a-http
    AGENT_URL_PRODUCT_AGENT=https://abc.bedrock-agentcore.us-east-2.amazonaws.com/
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


TransportMode = Literal["cli", "a2a-http", "dry-run"]
VALID_MODES: tuple[TransportMode, ...] = ("cli", "a2a-http", "dry-run")

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "orchestrator" / "agents.json"


@dataclass
class AgentConfig:
    name: str
    mode: TransportMode = "cli"
    url: str | None = None
    cli_module: str | None = None
    timeout_sec: int = 1800


@dataclass
class OrchestratorConfig:
    repo_root: Path = REPO_ROOT
    python_executable: str = field(default_factory=lambda: os.getenv("ORCHESTRATOR_PYTHON", "python"))
    agents: dict[str, AgentConfig] = field(default_factory=dict)

    def agent(self, name: str) -> AgentConfig:
        if name not in self.agents:
            raise KeyError(f"No orchestrator config for agent {name!r}")
        return self.agents[name]


def _env_key(agent_name: str, suffix: str) -> str:
    sanitized = agent_name.replace("-", "_").upper()
    return f"AGENT_{suffix}_{sanitized}"


def _apply_env_overrides(cfg: AgentConfig) -> AgentConfig:
    mode_env = os.getenv(_env_key(cfg.name, "MODE"), "").strip().lower()
    if mode_env:
        if mode_env not in VALID_MODES:
            raise ValueError(
                f"Invalid {_env_key(cfg.name, 'MODE')}={mode_env!r}. Use one of: {VALID_MODES}"
            )
        cfg.mode = mode_env  # type: ignore[assignment]
    url_env = os.getenv(_env_key(cfg.name, "URL"), "").strip()
    if url_env:
        cfg.url = url_env
    return cfg


def load_config(path: Path = CONFIG_PATH) -> OrchestratorConfig:
    cfg = OrchestratorConfig()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("agents", []):
            name = entry["name"]
            ac = AgentConfig(
                name=name,
                mode=entry.get("mode", "cli"),
                url=entry.get("url"),
                cli_module=entry.get("cliModule"),
                timeout_sec=int(entry.get("timeoutSec", 1800)),
            )
            cfg.agents[name] = ac
    cfg.agents = {name: _apply_env_overrides(ac) for name, ac in cfg.agents.items()}
    return cfg
