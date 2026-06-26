from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from contextlib import ExitStack
from typing import Any

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp import MCPClient

from .a2a_registry import agent_port, known_agent_urls
from .mcp_clients import MCP_FACTORIES

# Optional A2A client tools for calling peer agents
try:
    from strands_tools.a2a_client import A2AClientToolProvider
except ImportError:  # pragma: no cover
    A2AClientToolProvider = None  # type: ignore[misc, assignment]


AGENT_DESCRIPTIONS: dict[str, str] = {
    "orchestrator-agent": "Master SDLC coordinator — runs full pipeline or delegates to specialists via A2A.",
    "product-agent": "Converts business requirements into Jira epics and user stories.",
    "architect-agent": "Produces architecture decisions, ADRs, and API contracts.",
    "developer-agent": "Implements features in target-apps/ (local files; use gitlab-agent for GitLab publish).",
    "qa-agent": "Authors and runs tests; reports coverage and defects.",
    "devops-agent": "Manages Terraform, CI/CD pipelines, and deployments.",
    "security-agent": "Runs static analysis, dependency audits, and compliance checks.",
}


def coding_model_id() -> str:
    """Bedrock model for code/SQL agents; prefers CODING_MODEL_ID over MODEL_ID."""
    explicit = os.getenv("CODING_MODEL_ID", "").strip()
    if explicit:
        return explicit
    return os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-6").strip()


def _bedrock_model() -> BedrockModel:
    region = os.getenv("AWS_REGION", "us-east-2")
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    return BedrockModel(
        model_id=model_id,
        region_name=region,
        streaming=True,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


def build_agent(
    agent_name: str,
    *,
    system_prompt: str,
    tools: Sequence[Any] | None = None,
    enable_a2a_peers: bool = True,
) -> Agent:
    tool_list: list[Any] = list(tools or [])
    if enable_a2a_peers and A2AClientToolProvider is not None:
        peer_urls = known_agent_urls(exclude=agent_name)
        if peer_urls:
            provider = A2AClientToolProvider(known_agent_urls=peer_urls)
            tool_list.extend(provider.tools)

    return Agent(
        agent_id=agent_name,
        name=agent_name,
        description=AGENT_DESCRIPTIONS.get(agent_name, agent_name),
        model=_bedrock_model(),
        system_prompt=system_prompt.strip(),
        tools=tool_list,
    )


def _task_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _load_mcp_tools(mcp_names: Sequence[str]) -> tuple[list[Any], ExitStack]:
    """Enter MCP client contexts; caller must close the returned ExitStack."""
    stack: ExitStack = ExitStack()
    tools: list[Any] = []
    for name in mcp_names:
        client = MCP_FACTORIES[name]()
        stack.enter_context(client)
        tools.extend(client.list_tools_sync())
    return tools, stack


def run_task(
    agent_name: str,
    task: str,
    *,
    system_prompt: str,
    mcp_names: Sequence[str] | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Run one task with optional MCP tool providers."""
    mcp_names = list(mcp_names or [])
    if not mcp_names:
        agent = build_agent(agent_name, system_prompt=system_prompt)
        return str(agent(_task_message(task, context)))

    tools, stack = _load_mcp_tools(mcp_names)
    with stack:
        agent = build_agent(agent_name, system_prompt=system_prompt, tools=tools)
        return str(agent(_task_message(task, context)))


def serve_a2a(
    agent_name: str,
    *,
    system_prompt: str,
    mcp_names: Sequence[str] | None = None,
    port: int | None = None,
    host: str = "127.0.0.1",
) -> None:
    """Expose this Strands agent as an A2A HTTP server."""
    mcp_names = list(mcp_names or [])
    bind_port = port or agent_port(agent_name)

    skills = [
        AgentSkill(
            id=f"{agent_name}-run",
            name=f"{agent_name}-run",
            description=AGENT_DESCRIPTIONS.get(agent_name, agent_name),
            tags=["sdlc", agent_name],
        )
    ]

    if not mcp_names:
        agent = build_agent(agent_name, system_prompt=system_prompt)
        A2AServer(agent, host=host, port=bind_port, skills=skills).serve()
        return

    tools, stack = _load_mcp_tools(mcp_names)
    with stack:
        agent = build_agent(agent_name, system_prompt=system_prompt, tools=tools)
        A2AServer(agent, host=host, port=bind_port, skills=skills).serve()


def main(
    agent_name: str,
    *,
    system_prompt: str,
    mcp_names: Sequence[str] | None = None,
    default_port: int,
) -> None:
    parser = argparse.ArgumentParser(description=f"{agent_name} — Strands + A2A")
    parser.add_argument("--task", help="Task description (CLI mode)")
    parser.add_argument("--project", help="Jira project key (product/jira agents)")
    parser.add_argument("--sprint", type=int, help="Jira sprint id")
    parser.add_argument(
        "--serve-a2a",
        action="store_true",
        help="Start A2A HTTP server (see a2a/agent-registry.json)",
    )
    parser.add_argument("--port", type=int, default=default_port, help="A2A server port")
    parser.add_argument("--host", default="127.0.0.1", help="A2A bind host")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(
            agent_name,
            system_prompt=system_prompt,
            mcp_names=mcp_names,
            port=args.port,
            host=args.host,
        )
        return

    if not args.task:
        parser.error("--task is required unless --serve-a2a is set")

    if mcp_names and "atlassian" in mcp_names and not os.getenv("ATLASSIAN_MCP_TOKEN"):
        print(
            "WARNING: ATLASSIAN_MCP_TOKEN is not set; Jira MCP tools may fail.",
            file=sys.stderr,
        )

    context: dict[str, Any] = {}
    if args.project:
        context["projectKey"] = args.project
    if args.sprint is not None:
        context["sprintId"] = args.sprint

    print(f"[{agent_name}] Running task...")
    output = run_task(
        agent_name,
        args.task,
        system_prompt=system_prompt,
        mcp_names=mcp_names,
        context=context or None,
    )
    print("\n" + "=" * 60)
    print(output)


def entrypoint(
    agent_name: str,
    *,
    system_prompt: str,
    mcp_names: Sequence[str] | None = None,
    default_port: int,
) -> None:
    main(
        agent_name,
        system_prompt=system_prompt,
        mcp_names=mcp_names,
        default_port=default_port,
    )
