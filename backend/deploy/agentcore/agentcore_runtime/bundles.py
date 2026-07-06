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
    jira_enabled = env_flag("AGENTCORE_PRODUCT_SKIP_JIRA", default=True) is False

    skills = [
        AgentSkill(
            id="prd_creation",
            name="prd_creation",
            description="Create PRD markdown from business requirements (Jira optional when enabled)",
            tags=["prd", "product"],
        )
    ]
    if jira_enabled:
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
        # PRD pipeline always; post-PRD Jira is opt-in per run via context (createJiraBacklog).
        agent = mod.build_prd_pipeline_agent()  # noqa: SLF001
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
    use_postgres = env_flag("AGENTCORE_WEBCRAWLER_WITH_POSTGRES", default=False)

    skills = [
        AgentSkill(
            id="web_scrape_and_persist",
            name="web_scrape_and_persist",
            description="Scrape URLs via Firecrawl MCP and persist markdown (S3 or local). Postgres optional.",
            tags=["web", "scrape", "firecrawl", "ingestion"],
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
    mod = import_agent_module("gitlab-agent")

    skills = [
        AgentSkill(
            id="publish_feature",
            name="publish_feature",
            description="Publish SDLC artifacts to GitLab branch sdlc/<app> via MCP.",
            tags=["gitlab", "publish", "mcp"],
        )
    ]

    @contextmanager
    def factory() -> Iterator[AgentBundle]:
        import logging

        from strands import tool

        from _shared.runner import build_agent

        logger = logging.getLogger("agentcore.gitlab_agent")

        @tool
        def gitlab_publish_feature(target_app: str, run_id: str = "") -> str:
            """Publish SDLC artifacts for a target app to GitLab.

            Materializes S3 run artifacts (if configured) and publishes them
            to a GitLab branch via MCP.  Returns a markdown summary.

            Args:
                target_app: Feature / service slug (e.g. "pr-diff-summarizer").
                run_id: Pipeline run UUID for S3 artifact retrieval.
            """
            logger.info("gitlab_publish_feature called: app=%s run_id=%s", target_app, run_id)
            summary, handoff = mod.run_publish_for_agentcore(target_app, run_id)
            logger.info("publish result: status=%s paths=%d", handoff.get("status"), len(handoff.get("pathsPublished", [])))
            return summary

        agent = build_agent(
            "gitlab-agent",
            system_prompt=(
                "You are the GitLab publish agent. "
                "When asked to publish, call gitlab_publish_feature with the "
                "targetApp and runId from the user message. "
                "Return the tool output verbatim."
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
