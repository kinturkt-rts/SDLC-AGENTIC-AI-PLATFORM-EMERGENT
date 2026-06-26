from __future__ import annotations

import json
from typing import Any

from .paths import A2A_REGISTRY_PATH


def load_registry() -> dict[str, Any]:
    with A2A_REGISTRY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def agent_entry(agent_name: str) -> dict[str, Any]:
    registry = load_registry()
    entry = registry.get("agents", {}).get(agent_name)
    if not entry:
        raise KeyError(f"No A2A registry entry for {agent_name}")
    return entry


def agent_base_url(agent_name: str) -> str:
    return agent_entry(agent_name)["url"].rstrip("/") + "/"


def agent_port(agent_name: str) -> int:
    return int(agent_entry(agent_name)["port"])


def known_agent_urls(exclude: str | None = None) -> list[str]:
    registry = load_registry()
    urls = [entry["url"] for name, entry in registry.get("agents", {}).items() if name != exclude]
    return urls
