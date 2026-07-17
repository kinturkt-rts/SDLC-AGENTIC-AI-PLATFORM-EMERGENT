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
    """Wrap a Strands agent as a FastAPI app on `/` with health check at `/ping`.

    `enable_a2a_compliant_streaming=True` is REQUIRED on AgentCore Runtime. Without
    it, Strands returns each A2A response as a single buffered blob. AgentCore's
    invocation transport expects incremental streaming chunks and will terminate
    invocations that go quiet for too long (~15 min) even though `/ping` health
    checks still pass. That silent kill is what caused developer runs to write
    all 46 app files, then die at the LLM turn after their last tool call —
    the `finally` block that flips developer-handoff to `status=completed` and
    writes telemetry never runs, and the pipeline finishes with the app in S3
    but nothing published to GitLab.
    """
    runtime_url = agentcore_runtime_url()
    a2a_server = A2AServer(
        agent=agent,
        http_url=runtime_url,
        serve_at_root=True,
        skills=list(skills),
        enable_a2a_compliant_streaming=True,
    )

    app = FastAPI()

    # AgentCore keeps a session alive only while /ping reports "HealthyBusy";
    # a session reporting "Healthy" is idle-eligible and gets terminated once
    # idleRuntimeSessionTimeout elapses — even if the agent is mid-invocation
    # (docs: bedrock-agentcore runtime-troubleshooting "long-running tool gets
    # interrupted after 15 minutes"). Track in-flight A2A requests so long
    # developer/orchestrator invocations are reported busy instead of idle.
    # Fire-and-forget entrypoints return before their work finishes, so /ping
    # must also count registered background tasks (see _shared/background_tasks).
    from _shared.background_tasks import active_background_tasks

    active_invocations = {"count": 0}

    @app.middleware("http")
    async def _track_active_invocations(request, call_next):  # type: ignore[no-untyped-def]
        is_ping = request.url.path == "/ping"
        if not is_ping:
            active_invocations["count"] += 1
        try:
            return await call_next(request)
        finally:
            if not is_ping:
                active_invocations["count"] -= 1

    @app.get("/ping")
    def ping() -> dict[str, str]:
        busy = active_invocations["count"] > 0 or active_background_tasks() > 0
        return {"status": "HealthyBusy" if busy else "Healthy"}

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
