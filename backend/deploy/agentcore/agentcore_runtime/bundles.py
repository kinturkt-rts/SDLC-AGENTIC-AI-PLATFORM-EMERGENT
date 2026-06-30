"""Per-agent factories for AgentCore A2A deployment."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

from a2a.types import AgentSkill

from agentcore_runtime.bootstrap import env_flag, import_agent_module, repo_root
from agentcore_runtime.serve import AgentBundle, BundleFactory


def _runner_bundle(
    agent_name: str,
    *,
    system_prompt: str,
    mcp_names: tuple[str, ...] = (),
    enable_a2a_peers: bool = True,
) -> BundleFactory:
    from _shared.runner import AGENT_DESCRIPTIONS, _load_mcp_tools, build_agent

    skills = [
        AgentSkill(
            id=f"{agent_name}-run",
            name=f"{agent_name}-run",
            description=AGENT_DESCRIPTIONS.get(agent_name, agent_name),
            tags=["sdlc", agent_name],
        )
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        if mcp_names:
            tools, stack = _load_mcp_tools(mcp_names)
            with stack:
                agent = build_agent(
                    agent_name,
                    system_prompt=system_prompt,
                    tools=tools,
                    enable_a2a_peers=enable_a2a_peers,
                )
                yield agent, skills
        else:
            agent = build_agent(
                agent_name,
                system_prompt=system_prompt,
                enable_a2a_peers=enable_a2a_peers,
            )
            yield agent, skills

    return factory


def orchestrator_agent_bundle() -> BundleFactory:
    mod = import_agent_module("orchestrator-agent")
    peer_urls = os.getenv("AGENTCORE_A2A_PEER_URLS", "").strip()
    enable_peers = bool(peer_urls) or env_flag("AGENTCORE_ENABLE_A2A_PEERS", default=True)

    skills = [
        AgentSkill(
            id="run_sdlc_pipeline",
            name="run_sdlc_pipeline",
            description="End-to-end SDLC: PRD → design → DB → app → GitLab publish",
            tags=["sdlc", "pipeline", "orchestration"],
        ),
        AgentSkill(
            id="delegate_specialists",
            name="delegate_specialists",
            description="Delegate ad-hoc work to specialist agents via A2A",
            tags=["a2a", "delegation"],
        ),
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        # Deterministic pipeline avoids LLM round-trip + 424 timeouts on long runs.
        if env_flag("AGENTCORE_ORCHESTRATOR_DETERMINISTIC", default=True):
            agent = mod.build_orchestrator_pipeline_agent()  # noqa: SLF001
        else:
            agent = mod.build_orchestrator_agent(enable_a2a_peers=enable_peers)
        yield agent, skills

    return factory


def devops_agent_bundle() -> BundleFactory:
    mod = import_agent_module("devops-agent")
    return _runner_bundle(
        "devops-agent",
        system_prompt=mod.DEVOPS_SYS_PROMPT,
        mcp_names=(),
    )


def security_agent_bundle() -> BundleFactory:
    mod = import_agent_module("security-agent")
    return _runner_bundle(
        "security-agent",
        system_prompt=mod.SECURITY_SYS_PROMPT,
        mcp_names=(),
    )


def product_agent_bundle() -> BundleFactory:
    mod = import_agent_module("product-agent")
    skip_jira = env_flag("AGENTCORE_PRODUCT_SKIP_JIRA", default=True)

    skills = [
        AgentSkill(
            id="prd_creation",
            name="prd_creation",
            description="Create PRD markdown from business requirements (Jira optional when enabled)",
            tags=["prd", "product"],
        )
    ]
    if not skip_jira:
        skills.append(
            AgentSkill(
                id="backlog_creation",
                name="backlog_creation",
                description="Create Jira epics and stories from requirements",
                tags=["jira", "product"],
            )
        )

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        if skip_jira:
            agent = mod.build_prd_pipeline_agent()  # noqa: SLF001 — PRD pipeline + S3 persist
            yield agent, skills
        else:
            with mod._atlassian_mcp() as mcp:  # noqa: SLF001
                tools = mod._filter_tools(mcp.list_tools_sync(), write_allowed=False)  # noqa: SLF001
                agent = mod._build_agent(tools)  # noqa: SLF001
                yield agent, skills

    return factory


def architect_agent_bundle() -> BundleFactory:
    mod = import_agent_module("architect-agent")
    root = repo_root()

    skills = [
        AgentSkill(
            id="architecture_diagrams",
            name="architecture_diagrams",
            description="AWS architecture PNG diagrams, per-feature design docs, and ADR summaries",
            tags=["architecture", "aws-diagram", "design"],
        )
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        from _shared.mcp_clients import aws_diagram_mcp_client

        with aws_diagram_mcp_client(cwd=root) as mcp:
            agent = mod.build_architect_pipeline_agent(mcp.list_tools_sync())  # noqa: SLF001
            yield agent, skills

    return factory


def developer_agent_bundle() -> BundleFactory:
    mod = import_agent_module("developer-agent")

    skills = [
        AgentSkill(
            id="implement_feature",
            name="implement_feature",
            description=(
                "Implement backend API + optional Streamlit UI under target-apps/. "
                "Patterns A/B/B+/B++/C. Stack driven by design doc tech stack section."
            ),
            tags=["development", "fastapi", "python", "streamlit", "rag", "bedrock"],
        )
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        yield mod.build_developer_pipeline_agent(), skills  # noqa: SLF001

    return factory


def qa_agent_bundle() -> BundleFactory:
    mod = import_agent_module("qa-agent")

    skills = [
        AgentSkill(
            id="run_qa_suite",
            name="run_qa_suite",
            description=(
                "Run pytest on a target-apps service, report failures with classification, "
                "add edge-case API tests, and emit structured QA handoff."
            ),
            tags=["qa", "pytest", "testing", "api"],
        )
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        yield mod._build_agent(), skills  # noqa: SLF001

    return factory


def database_agent_bundle() -> BundleFactory:
    mod = import_agent_module("database-agent")
    use_postgres = env_flag("AGENTCORE_DATABASE_USE_POSTGRES")
    use_mongodb = env_flag("AGENTCORE_DATABASE_USE_MONGODB")

    skills = [
        AgentSkill(
            id="database_design_and_scripts",
            name="database_design_and_scripts",
            description="Create SQL/NoSQL schema artifacts, migrations, and DB command playbooks.",
            tags=["database", "postgres", "mongodb", "schema", "migration"],
        )
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        with ExitStack() as stack:
            tools = mod._build_toolset(  # noqa: SLF001
                stack,
                use_mongodb=use_mongodb,
            )
            agent = mod.build_database_pipeline_agent(  # noqa: SLF001
                tools,
                use_postgres=use_postgres,
                use_mongodb=use_mongodb,
            )
            yield agent, skills

    return factory


def web_crawler_agent_bundle() -> BundleFactory:
    mod = import_agent_module("web-crawler-agent")
    use_postgres = env_flag("AGENTCORE_WEBCRAWLER_WITH_POSTGRES", default=True)

    skills = [
        AgentSkill(
            id="web_scrape_and_persist",
            name="web_scrape_and_persist",
            description="Scrape URLs via Firecrawl, store markdown and Postgres rows for downstream agents.",
            tags=["web", "scrape", "firecrawl", "postgres", "ingestion"],
        )
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        with ExitStack() as stack:
            tools = mod._build_toolset(  # noqa: SLF001
                stack,
                use_firecrawl=True,
                use_postgres=use_postgres,
            )
            agent = mod._build_agent(tools)  # noqa: SLF001
            yield agent, skills

    return factory


def gitlab_agent_bundle() -> BundleFactory:
    import tempfile
    from pathlib import Path

    from strands import tool

    from _shared.artifact_store import is_s3_store, materialize_run, put_handoff, resolve_run_id
    from _shared.runner import build_agent

    mod = import_agent_module("gitlab-agent")

    skills = [
        AgentSkill(
            id="publish_feature",
            name="publish_feature",
            description="Publish SDLC artifacts to GitLab branch sdlc/<app> via MCP.",
            tags=["gitlab", "publish", "mcp"],
        )
    ]

    @tool
    def gitlab_publish_feature(target_app: str, run_id: str = "") -> str:
        """Publish SDLC outputs for targetApp to GitLab (branch sdlc/<app>)."""
        ctx: dict[str, object] = {"targetApp": target_app}
        rid = (run_id or resolve_run_id(ctx) or os.getenv("PIPELINE_RUN_ID", "")).strip()
        if rid:
            ctx["runId"] = rid

        root: Path | None = None
        if rid and is_s3_store():
            root = materialize_run(rid, Path(tempfile.mkdtemp(prefix="sdlc-gitlab-")))

        summary, handoff = mod.run_publish(  # noqa: SLF001
            target_app,
            dict(ctx),
            open_mr=env_flag("GITLAB_OPEN_MR"),
            apps_repo=env_flag("GITLAB_APPS_REPO"),
            root=root,
        )
        if rid and is_s3_store():
            put_handoff(rid, "gitlab", handoff)
        return summary

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        agent = build_agent(
            "gitlab-agent",
            system_prompt=(
                "You publish SDLC feature artifacts to GitLab. "
                "When asked to publish, call gitlab_publish_feature with targetApp "
                "and runId from context when present."
            ),
            tools=[gitlab_publish_feature],
            enable_a2a_peers=False,
        )
        yield agent, skills

    return factory


BUNDLE_FACTORIES: dict[str, BundleFactory] = {
    "orchestrator-agent": orchestrator_agent_bundle,
    "product-agent": product_agent_bundle,
    "architect-agent": architect_agent_bundle,
    "developer-agent": developer_agent_bundle,
    "qa-agent": qa_agent_bundle,
    "devops-agent": devops_agent_bundle,
    "security-agent": security_agent_bundle,
    "database-agent": database_agent_bundle,
    "web-crawler-agent": web_crawler_agent_bundle,
    "gitlab-agent": gitlab_agent_bundle,
}
