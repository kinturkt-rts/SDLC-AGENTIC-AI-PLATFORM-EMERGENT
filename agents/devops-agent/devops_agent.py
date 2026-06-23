"""DevOps agent — Phase 2: Terraform, CI/CD, ECS (not GitHub publish).

GitHub publish is handled by github-agent after developer-agent (Phase 1 MVP).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_target_app,
)

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.multiagent.a2a import A2AServer

AGENT_NAME = "devops-agent"
A2A_PORT = 9105

DEVOPS_SYS_PROMPT = """\
You are the DevOps Agent for the Autonomous SDLC platform (Phase 2).

## Phase 1 (implemented elsewhere)
- **github-agent** publishes generated apps to GitHub via MCP after developer-agent.
- Do not push code or open pull requests — delegate to github-agent.

## Phase 2 scope (your future job)
- Terraform modules under infrastructure/
- CI/CD pipelines (GitHub Actions or Harness)
- ECS / container deploy for target-apps
- Secrets via AWS Secrets Manager
- Slack/email notifications on deploy events

## Today
If asked to publish to GitHub, tell the user to run:
`python agents/github-agent/github_agent.py --target-app <app>`
"""


def _bedrock_model() -> BedrockModel:
    model_id = os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        max_tokens=int(os.getenv("DEVOPS_AGENT_MAX_TOKENS", "4096")),
        streaming=True,
        boto_client_config=botocore.config.Config(
            read_timeout=int(os.getenv("BEDROCK_READ_TIMEOUT", "600")),
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


def run_task(task: str, context: dict[str, Any] | None = None, *, target_app: str | None = None) -> str:
    app = resolve_target_app(target_app, context, env_var="DEVOPS_TARGET_APP")
    ctx = context if context is not None else {"targetApp": app}
    ctx.setdefault("targetApp", app)
    enrich_handoff_context(ctx, include_db_paths=False)
    message = task
    if context:
        message = f"{task}\n\nContext:\n{json.dumps(ctx, indent=2)}"
    agent = Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Phase 2 infra and CI/CD (Terraform, ECS).",
        model=_bedrock_model(),
        system_prompt=DEVOPS_SYS_PROMPT,
        tools=[],
    )
    return str(agent(message))


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    agent = Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Phase 2 infra and CI/CD.",
        model=_bedrock_model(),
        system_prompt=DEVOPS_SYS_PROMPT,
        tools=[],
    )
    skills = [
        AgentSkill(
            id="delivery",
            name="delivery",
            description="Terraform and CI/CD (Phase 2).",
            tags=["devops", "terraform", "cicd"],
        )
    ]
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="DevOps agent — Phase 2 infra (not GitHub publish)")
    parser.add_argument("--task", default="Summarize Phase 2 DevOps scope for this target app.")
    parser.add_argument("--target-app", help="Feature slug")
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Do not auto-load agents/pipeline/<app>.context.json",
    )
    load_context_extra(parser)
    parser.add_argument("--serve-a2a", action="store_true")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    try:
        ctx, target = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="DEVOPS_TARGET_APP",
        )
    except TargetAppRequiredError as exc:
        parser.error(str(exc))

    print(f"[{AGENT_NAME}] Phase 2 — use github-agent for publish.")
    summary = run_task(args.task, ctx, target_app=target)
    print("\n" + "=" * 60)
    print(summary)


if __name__ == "__main__":
    main()
