"""FastAPI + uvicorn entry for Amazon Bedrock AgentCore Runtime (A2A protocol)."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence

import uvicorn
from a2a.types import AgentSkill
from fastapi import FastAPI
from strands import Agent
from strands.multiagent.a2a import A2AServer

logger = logging.getLogger(__name__)

AGENTCORE_A2A_HOST = "0.0.0.0"
AGENTCORE_A2A_PORT = 9000


def agentcore_runtime_url() -> str:
    """Public runtime URL for agent-card generation (set by AgentCore after deploy)."""
    port = int(os.getenv("AGENTCORE_A2A_PORT", str(AGENTCORE_A2A_PORT)))
    return os.environ.get("AGENTCORE_RUNTIME_URL", f"http://127.0.0.1:{port}/")


def build_agentcore_fastapi_app(agent: Agent, skills: Sequence[AgentSkill]) -> FastAPI:
    """Wrap a Strands agent as a FastAPI app on `/` with health check at `/ping`."""
    runtime_url = agentcore_runtime_url()
    a2a_server = A2AServer(
        agent=agent,
        http_url=runtime_url,
        serve_at_root=True,
        skills=list(skills),
    )

    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "healthy"}

    app.mount("/", a2a_server.to_fastapi_app())
    return app


def run_agentcore_a2a(
    agent: Agent,
    skills: Sequence[AgentSkill],
    *,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Block and serve the agent on AgentCore's expected A2A port (9000)."""
    bind_host = host or os.getenv("AGENTCORE_A2A_HOST", AGENTCORE_A2A_HOST)
    bind_port = port or int(os.getenv("AGENTCORE_A2A_PORT", str(AGENTCORE_A2A_PORT)))

    logging.basicConfig(level=logging.INFO)
    logger.info(
        "Starting AgentCore A2A server host=%s port=%s runtime_url=%s",
        bind_host,
        bind_port,
        agentcore_runtime_url(),
    )

    app = build_agentcore_fastapi_app(agent, skills)
    uvicorn.run(app, host=bind_host, port=bind_port)
