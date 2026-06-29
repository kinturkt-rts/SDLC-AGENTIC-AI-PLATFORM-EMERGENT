"""Orchestrator — master SDLC coordinator (Strands + A2A peers + pipeline runner)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env
from _shared.runner import build_agent
from _shared.sdlc_pipeline import (
    PIPELINE_STEPS,
    PipelineOptions,
    planned_steps,
    run_sdlc_pipeline,
)
from strands.tools.decorator import tool

load_repo_env()

AGENT_NAME = "orchestrator-agent"
A2A_PORT = 9100

ORCHESTRATOR_SYS_PROMPT = """\
You are the **Orchestrator Agent** — the single master coordinator for the SDLC Agentic AI Platform.

## Architecture (your role in the flow)
```
Frontend/CLI -> orchestrator-agent (you, master)
orchestrator -> product-agent -> architect-agent -> database-agent -> developer-agent -> gitlab-agent
gitlab-agent -.-> qa-agent (optional)
product, architect, database, developer, gitlab each write artifacts -> S3
orchestrator writes run index -> DynamoDB
```

## Your role
- **Only entry point** for end-to-end feature delivery.
- **Do not** implement PRDs, designs, SQL, or application code yourself.
- **Sequence** specialists in order: product -> architect -> database -> developer -> gitlab -> (optional qa).
- **Register** each run in DynamoDB; after each specialist completes, their outputs sync to S3.

## Canonical pipeline
1. **product-agent** — requirements -> PRD + context
2. **architect-agent** — PRD -> diagram PNG + design doc
3. **database-agent** — design §3/§6 -> SQL migrations
4. **developer-agent** — design §4/§5 -> FastAPI app (local verify gate before gitlab)
5. **gitlab-agent** — publish branch `sdlc/<app>`
6. **qa-agent** (optional, after gitlab) — extended pytest + coverage

Optional side branch (not in default chain): web-crawler-agent. Roadmap: security -> UAT -> devops -> AWS.

## How to run
- Full feature: call `run_sdlc_pipeline` with `target_app`, `input_file`, and skip flags.
- Ad-hoc: `a2a_send_message` to one specialist with task + context JSON.

## AgentCore cloud
- Peers via `AGENTCORE_A2A_PEER_URLS`; `ARTIFACT_STORE=s3`; you own DynamoDB run index.

Return a short plan, steps executed, artifact paths, runId, and errors. Do not invent paths.\
"""


@tool
def run_sdlc_pipeline_tool(
    target_app: str,
    input_file: str = "",
    skip_product: bool = False,
    skip_architect: bool = False,
    skip_db: bool = False,
    skip_developer: bool = False,
    skip_gitlab: bool = False,
    skip_verify: bool = False,
    with_web_crawler: bool = False,
    with_qa: bool = False,
    with_jira: bool = False,
    jira_project: str = "",
    transport: str = "auto",
) -> dict[str, Any]:
    """Run the full SDLC pipeline for a target app (master coordinator).

    Flow: product -> architect -> database -> developer -> gitlab -> (optional qa).
    Specialists sync artifacts to S3; orchestrator owns DynamoDB run index.

    Args:
        target_app: Feature slug (e.g. inventory-app)
        input_file: Path to requirements brief (required unless skip_product)
        skip_product: Resume from existing PRD/context
        skip_architect: Skip diagram + design doc
        skip_db: Skip database-agent and RDS apply
        skip_developer: Skip FastAPI implementation
        skip_gitlab: Skip GitLab publish
        skip_verify: Skip local pytest gate
        with_web_crawler: Run web-crawler-agent after architect
        with_qa: Run qa-agent after gitlab
        with_jira: Create Jira epic/stories (local only; not AgentCore v1)
        jira_project: Jira project key when with_jira is true
        transport: auto | local | a2a

    Returns:
        dict with success, summary, agents_run, artifacts, run_id
    """
    options = PipelineOptions(
        target_app=target_app,
        input_file=input_file,
        skip_product=skip_product,
        skip_architect=skip_architect,
        skip_db=skip_db,
        skip_developer=skip_developer,
        skip_gitlab=skip_gitlab,
        skip_verify=skip_verify,
        with_web_crawler=with_web_crawler,
        with_qa=with_qa,
        with_jira=with_jira,
        jira_project=jira_project,
        transport=transport if transport in ("auto", "local", "a2a") else "auto",  # type: ignore[arg-type]
    )
    result = run_sdlc_pipeline(options)
    return {
        "success": result.success,
        "summary": result.summary(),
        "target_app": result.target_app,
        "run_id": result.run_id,
        "agents_run": result.agents_run,
        "artifacts": result.artifacts,
        "errors": result.errors,
        "planned_steps": planned_steps(options),
    }


def orchestrator_tools() -> list[Any]:
    """Tools for the master orchestrator (pipeline runner + A2A peers from build_agent)."""
    return [run_sdlc_pipeline_tool]


def build_orchestrator_agent(*, enable_a2a_peers: bool = True) -> Any:
    """Construct the Strands agent with pipeline tool and optional A2A peer tools."""
    return build_agent(
        AGENT_NAME,
        system_prompt=ORCHESTRATOR_SYS_PROMPT,
        tools=orchestrator_tools(),
        enable_a2a_peers=enable_a2a_peers,
    )


def _print_pipeline_plan(options: PipelineOptions) -> None:
    steps = planned_steps(options)
    print(f"[orchestrator] Pipeline plan for {options.target_app} ({resolve_transport_label(options)}):")
    print("  flow: ORCH -> PROD -> ARCH -> DB -> DEV -> GL -.-> QA (optional)")
    print("  storage: specialists -> S3 | orchestrator -> DynamoDB")
    for idx, step in enumerate(steps, start=1):
        print(f"  {idx}. {step}")
    if not options.skip_verify and not options.skip_developer:
        print("  (internal: verify pytest after developer, before gitlab)")
    print(f"  context: agents/pipeline/{options.target_app}.context.json")


def resolve_transport_label(options: PipelineOptions) -> str:
    from _shared.sdlc_pipeline import resolve_transport

    return resolve_transport(options.transport)


def _add_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--run-pipeline",
        action="store_true",
        help="Run the full SDLC chain deterministically (master coordinator mode)",
    )
    parser.add_argument("--target-app", "--feature", dest="target_app", help="Feature slug")
    parser.add_argument("--run-id", default="", help="Pipeline run UUID (frontend stages inputs under runs/<runId>/)")
    parser.add_argument("--input-file", help="Requirements brief for product-agent")
    parser.add_argument("--context-file", default="", help="Pipeline context JSON path")
    parser.add_argument(
        "--transport",
        choices=["auto", "local", "a2a"],
        default="auto",
        help="local=subprocess agents; a2a=AgentCore peer URLs; auto=env-based",
    )
    parser.add_argument("--skip-product", action="store_true")
    parser.add_argument("--skip-architect", action="store_true")
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--skip-postgres", action="store_true")
    parser.add_argument("--skip-developer", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-gitlab", action="store_true")
    parser.add_argument("--with-web-crawler", action="store_true")
    parser.add_argument("--skip-web-crawler", action="store_true")
    parser.add_argument("--with-qa", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--with-jira", action="store_true")
    parser.add_argument("--jira-project", default="")
    parser.add_argument("--plan-only", action="store_true", help="Print pipeline plan and exit")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{AGENT_NAME} — master SDLC coordinator (Strands + A2A)",
    )
    parser.add_argument("--task", help="Ad-hoc task for LLM delegation mode")
    _add_pipeline_args(parser)
    parser.add_argument(
        "--serve-a2a",
        action="store_true",
        help="Start A2A HTTP server (port 9100 local, 9000 on AgentCore)",
    )
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        agent = build_orchestrator_agent()
        from a2a.types import AgentSkill
        from strands.multiagent.a2a import A2AServer

        skills = [
            AgentSkill(
                id="run_sdlc_pipeline",
                name="run_sdlc_pipeline",
                description="End-to-end SDLC: PRD → design → DB → app → GitLab",
                tags=["sdlc", "pipeline", "orchestration"],
            ),
            AgentSkill(
                id="delegate_specialists",
                name="delegate_specialists",
                description="Delegate ad-hoc work to specialist agents via A2A",
                tags=["a2a", "delegation"],
            ),
        ]
        A2AServer(agent, host=args.host, port=args.port, skills=skills).serve()
        return

    if args.run_pipeline or args.plan_only:
        if not args.target_app:
            parser.error("--target-app is required with --run-pipeline")
        options = PipelineOptions(
            target_app=args.target_app,
            input_file=args.input_file or "",
            context_file=args.context_file,
            run_id=args.run_id.strip() or None,
            transport=args.transport,
            skip_product=args.skip_product,
            skip_architect=args.skip_architect,
            skip_db=args.skip_db,
            skip_postgres=args.skip_postgres,
            skip_developer=args.skip_developer,
            skip_verify=args.skip_verify,
            skip_gitlab=args.skip_gitlab,
            with_web_crawler=args.with_web_crawler,
            skip_web_crawler=args.skip_web_crawler,
            with_qa=args.with_qa,
            skip_qa=args.skip_qa,
            with_jira=args.with_jira,
            jira_project=args.jira_project,
        )
        _print_pipeline_plan(options)
        if args.plan_only:
            return
        result = run_sdlc_pipeline(options)
        print("\n" + "=" * 60)
        print(result.summary())
        if not result.success:
            sys.exit(1)
        return

    if not args.task:
        parser.error("--task, --run-pipeline, or --serve-a2a is required")

    agent = build_orchestrator_agent()
    context: dict[str, Any] | None = None
    if args.target_app:
        context = {"targetApp": args.target_app}
        if args.input_file:
            context["inputFile"] = args.input_file

    print(f"[{AGENT_NAME}] Delegating task...")
    message = args.task
    if context:
        message = f"{args.task}\n\nContext:\n{json.dumps(context, indent=2)}"
    output = str(agent(message))
    print("\n" + "=" * 60)
    print(output)


if __name__ == "__main__":
    main()
