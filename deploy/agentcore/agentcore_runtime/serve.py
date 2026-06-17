"""Run an agent bundle on AgentCore A2A (port 9000)."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import TypeAlias

from a2a.types import AgentSkill
from strands import Agent

AgentBundle: TypeAlias = tuple[Agent, list[AgentSkill]]
BundleFactory: TypeAlias = Callable[[], AbstractContextManager[AgentBundle]]


def run_bundle(factory: BundleFactory) -> None:
    """Enter the agent bundle context manager and serve until process exit."""
    from _shared.agentcore_serve import run_agentcore_a2a

    with factory() as (agent, skills):
        run_agentcore_a2a(agent, skills)
