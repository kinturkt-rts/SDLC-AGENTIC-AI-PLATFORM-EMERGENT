from __future__ import annotations

import json
import os
from typing import Any

from .paths import A2A_REGISTRY_PATH


def load_registry() -> dict[str, Any]:
    with A2A_REGISTRY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_peer_url_overrides(raw: str | None = None) -> dict[str, str]:
    """Parse AGENTCORE_A2A_PEER_URLS into agent-name -> base URL.

    Supported formats (comma-separated):
      - ``product-agent=https://runtime.example/``
      - ``https://runtime.example/`` (name resolved from local registry port order — avoid)
    """
    text = (raw if raw is not None else os.getenv("AGENTCORE_A2A_PEER_URLS", "")).strip()
    if not text:
        return {}

    overrides: dict[str, str] = {}
    for chunk in text.split(","):
        item = chunk.strip()
        if not item:
            continue
        if "=" in item:
            name, url = item.split("=", 1)
            overrides[name.strip()] = url.strip().rstrip("/")
        else:
            overrides[item] = item.rstrip("/")
    return overrides


def agent_url_map(exclude: str | None = None) -> dict[str, str]:
    """Merge local registry URLs with AgentCore peer overrides."""
    registry = load_registry()
    mapping: dict[str, str] = {}
    for name, entry in registry.get("agents", {}).items():
        if exclude and name == exclude:
            continue
        mapping[name] = str(entry["url"]).rstrip("/")

    for key, url in parse_peer_url_overrides().items():
        if key in mapping:
            mapping[key] = url.rstrip("/")
        elif key.startswith("http://") or key.startswith("https://"):
            # Bare URL without agent name — keep for peer discovery lists only.
            mapping[url] = url.rstrip("/")
    return mapping


def agent_entry(agent_name: str) -> dict[str, Any]:
    registry = load_registry()
    entry = registry.get("agents", {}).get(agent_name)
    if not entry:
        raise KeyError(f"No A2A registry entry for {agent_name}")
    return entry


def agent_base_url(agent_name: str) -> str:
    overrides = parse_peer_url_overrides()
    if agent_name in overrides:
        return overrides[agent_name].rstrip("/") + "/"
    return agent_entry(agent_name)["url"].rstrip("/") + "/"


def agent_port(agent_name: str) -> int:
    return int(agent_entry(agent_name)["port"])


def known_agent_urls(exclude: str | None = None) -> list[str]:
    """Peer base URLs for A2A client tools (registry + AgentCore overrides)."""
    urls: list[str] = []
    seen: set[str] = set()
    for name, url in agent_url_map(exclude=exclude).items():
        if name.startswith("http://") or name.startswith("https://"):
            normalized = name.rstrip("/")
        else:
            normalized = url.rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
    return urls
