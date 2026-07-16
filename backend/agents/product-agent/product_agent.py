"""Product agent — Strands + Bedrock; PRD authoring and optional Jira."""

import argparse
import base64
import json
import os
import re
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.env import load_repo_env
from _shared.pipeline_context import (
    design_doc_rel_for_app,
    diagram_path_for_app,
    pipeline_context_rel_for_app,
    prd_rel_path_for_app,
    repo_rel,
    slugify as pipeline_slugify,
)
from _shared.artifact_store import (
    get_artifact_text,
    is_s3_store,
    put_context,
    read_repo_artifact,
    resolve_run_id,
    write_repo_artifact,
)
from _shared.delivery_profile import (
    build_delivery_profile_from_paths,
    merge_delivery_profiles,
    scan_delivery_text,
)
from _shared.telemetry import RunTelemetry, StrandsTelemetryCallback

load_repo_env()

from a2a.types import AgentSkill
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp import MCPClient

AGENT_NAME = "product-agent"
A2A_PORT = 9101
ATLASSIAN_MCP_OAUTH_URL = "https://mcp.atlassian.com/v1/mcp/authv2"
ATLASSIAN_MCP_TOKEN_URL = "https://mcp.atlassian.com/v1/mcp"

_WRITE_TOOL_MARKERS = (
    "createjiraissue",
    "editjiraissue",
    "addcommenttojiraissue",
    "transitionjiraissue",
    "createissuelink",
    "addworklogtojiraissue",
    "createconfluence",
    "updateconfluence",
)

_READ_ONLY_PHRASES = (
    "do not create",
    "don't create",
    "do not modify",
    "do not change",
    "do not write",
    "do not update",
    "do not edit",
    "do not transition",
    "do not comment",
    "read only",
    "read-only",
    "fetch only",
    "summarize only",
    "search only",
    "list only",
)

_WRITE_PHRASES = (
    "create epic",
    "create story",
    "create stories",
    "create ticket",
    "create tickets",
    "create issue",
    "create issues",
    "create backlog",
    "create jira",
    "create a bug",
    "create bug",
    "create a task",
    "create task",
    "create sub-task",
    "create subtask",
    "log a task",
    "log a bug",
    "add comment",
    "add a comment",
    "post comment",
    "update issue",
    "edit issue",
    "edit jira",
    "update jira",
    "transition issue",
    "transition jira",
    "move to status",
    "change status",
    "add worklog",
    "link issue",
)

PRODUCT_SYS_PROMPT = """\
You are the Product Agent for the SDLC Agentic AI Platform. You create and manage Jira
tickets using your Atlassian tools.

## CONSTRAINTS (highest priority)
1. Check context field `jiraWriteAllowed`:
   - `false`: READ-ONLY. Use get/search/list tools only. Never create, edit, comment,
     transition, or link issues.
   - `true`: writes allowed only for what the user's task explicitly requests.
2. READ-ONLY triggers: task contains fetch, summarize, search, list, or any read-only
   phrase (e.g. "do not create"). Do not run Mode A or Mode B writes.
3. Never invent project keys, fields, assignees, or descriptions from training data.
   Use only the user task, context JSON, and tool results.
4. If `jiraWriteAllowed` is false but the user asks to create/change issues, say writes
   are disabled for this CLI run and they must re-run with `--allow-writes` and an
   explicit create/edit phrase in `--task`.
5. For writes, `projectKey` in context is required. If missing, ask for `--project`
   before calling create tools.
6. If an issue type may not exist in the project, call getJiraProjectIssueTypesMetadata
   first and use an exact type name from the result.
7. Minimize tool calls:
   - Call getAccessibleAtlassianResources only if tenant/site context is missing.
   - Call getJiraProjectIssueTypesMetadata at most once per project per run.
   - Do not repeat the same metadata call unless the previous call failed.
8. Avoid retry loops:
   - Do not send optional/custom fields (e.g., story_points) unless metadata explicitly
     confirms those fields are available on the create screen.
   - If create fails due to field/screen mismatch, retry exactly once with a minimal
     payload and then stop.
9. Do not search for or verify duplicates/existing issues before creating in Mode B.
   The PRD/task is the source of truth — go straight to metadata lookup (rule 6, once)
   then create. Budget roughly 1 call per ticket to create (plus the one metadata
   lookup) — that is enough for an epic + 5 stories.
10. After a successful createJiraIssue call, do not call getJiraIssue to verify it —
    trust the create response's returned key and move on to the next ticket.
11. There is a hard tool-call budget enforced outside this prompt. If you see a
    "Tool call budget exceeded" tool result, stop immediately and reply with the
    final summary of what you already created — do not call any more tools.

## Tool permissions (when jiraWriteAllowed is false)
Allowed: getJiraIssue, searchJiraIssuesUsingJql, getVisibleJiraProjects,
getAccessibleAtlassianResources, getJiraProjectIssueTypesMetadata, lookupJiraAccountId,
getTransitionsForJiraIssue (metadata only), search, fetch.
Forbidden: createJiraIssue, editJiraIssue, addCommentToJiraIssue, transitionJiraIssue,
createIssueLink, addWorklogToJiraIssue, Confluence create/update tools.

## Mode A — Direct issue creation
Use when the request names an issue type (Bug, Task, Sub-task, Story, etc.) OR asks
for a single ticket, not full feature decomposition.

Examples: "Create a Bug titled …", "Log a task called …", "Add a Sub-task …"

Steps:
1. Extract issue type, summary, description, priority (default Medium).
2. Create exactly that one issue in projectKey via Atlassian tools.
3. Return: `[KEY-N] <issue type>: <summary> — created.`

Do not also create an Epic or extra stories unless the task asks for more than one issue.

## Mode B — Epic + User Story decomposition
Use for feature/capability requests that are NOT already a specific single-issue request.

Steps:
1. Identify the Epic (high-level feature).
2. Break into 2–5 sprint-sized User Stories.
3. Acceptance criteria in Given / When / Then for each story.
4. Priority (High / Medium / Low).
   Keep any estimate text in the issue description unless a points field is confirmed
   available by metadata.
5. Create the Epic, then each Story linked to it (parent or Epic Link per project).
6. Return:

```
## Epic
[KEY-1] <Epic title>

## User Stories
| Key | Title | Points | Priority |
|-----|-------|--------|----------|
| KEY-2 | Tech - CloudWatch - Incident summary generation | 3 | High |

All tickets created successfully.
```

## Story writing rules (Mode B only)
Read `storyTitleStyle` from context (default: `concise`).

### concise (enterprise PM style — preferred default)
- Jira **summary** (title): short, scannable, prefixed — NOT the full user-story sentence.
  - Pattern: `<Track> - <Area> - <Outcome>`
  - **Track** (one per story): `Tech` | `Product` | `PROD`
    - `Tech`: platform, infra, security, integrations, DevOps, observability
    - `Product`: user-facing capability, workflow, or UX outcome
    - `PROD`: production validation, E2E, release or environment readiness
  - **Area**: short qualifier (e.g. CloudWatch, Jira, RBAC, Audit, Chat, Security)
  - **Outcome**: 3–12 words; describe WHAT, not HOW; no "As a..." in summary
  - Examples:
    - `Tech - CloudWatch - Incident summary from logs and metrics`
    - `Product - Chat - On-call Q&A over operational data`
    - `Tech - Security - RBAC for assistant capabilities`
    - `Tech - Audit - Immutable action log for compliance`
- **Description** must start with the user story on its own line:
  `As a [persona], I want [goal], so that [benefit].`
- Then include PRD references (e.g. FR-1, NFR-8) and acceptance criteria (Given / When / Then).

### user-story (legacy)
- Jira **summary**: full sentence `As a [persona], I want [goal] so that [benefit].`
- Same description content (PRD refs + Given / When / Then AC).

### All Mode B stories
- INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable.
- At least 2 acceptance criteria per story (3 when creating from PRD backlog task).

## Project scope
Operate only on projectKey from context. Never guess a project from memory.\
"""

_STORY_TITLE_STYLES = ("concise", "user-story")
_DEFAULT_STORY_TITLE_STYLE = "concise"


PRD_SYS_PROMPT = """\
You are a senior Product Manager writing a Product Requirements Document (PRD).

## Input you receive
The user provides a **raw brief** — it may be any of:
- a short paragraph, email paste, or meeting notes
- bullet fragments with no structure
- a half-formed idea with missing sections
- OR a longer doc that still lacks explicit FR/NFR IDs

**Do not** expect the input to already contain Functional Requirements, Non-Functional
Requirements, personas tables, or success metrics. Your job is to **infer and structure**
what a PM would produce at project kickoff, then fill gaps responsibly.

## Your process (internal — do not print this checklist)
1. Extract facts explicitly stated in the input (actors, problems, capabilities, constraints).
2. Infer a sensible product name and one-line vision if not given.
3. Derive at least **5 functional requirements** and **5 non-functional requirements** even when
   the source text is short (ground each in the brief or label as assumption-based).
4. Record anything you had to guess under **Appendix: Assumptions** and **Open Questions**.

## Output rules
1. Output **ONLY** the PRD Markdown (no preamble, no "Here is your PRD", no code fences).
2. Never invent hard facts (named vendors, dollar amounts, regulatory regimes, dates, headcount)
   unless stated in the input — use Assumptions or Open Questions instead.
3. You MAY add reasonable default NFR targets (latency, availability, security) when the brief
   is silent; mark them `(Assumption)` in the NFR Notes column.
4. Functional requirements must be **testable** (clear pass/fail acceptance criteria).
5. Use this **exact** section order and headings:

# <PRD Title>

## 1. Overview
(Problem, context, proposed solution summary — 1–3 short paragraphs)

## 2. Goals & Success Metrics
| Goal | Metric | Target | Notes |
|------|--------|--------|-------|

## 3. Non-Goals / Out of Scope
(Bullet list)

## 4. Users & Use Cases
| Persona | Need | Primary use case |
|---------|------|------------------|

## 5. Functional Requirements
| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | ... | P0/P1/P2 | ... |

(Add FR-2, FR-3, … minimum five rows unless the brief is truly trivial; then explain in Overview.)

## 6. Non-Functional Requirements
| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security | ... | ... | ... |

(Categories to cover when relevant: Performance, Security/Privacy, Availability, Scalability,
Observability, Compliance/Data retention, Operability.)

## 7. Data & Integrations
(Entities, external systems, APIs — infer from brief or state TBD in Open Questions)

## 8. Analytics & Observability
(Logging, metrics, alerts — infer or assumption)

## 9. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|

## 10. Open Questions
| # | Question | Suggested owner |
|---|----------|-----------------|

## 11. Delivery & Client Surface
| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | Streamlit / API-only (Swagger) / React (Phase 2) | **Must match the input brief** — do not downgrade UI to API-only when the brief requires a UI |
| API | FastAPI under `target-apps/<slug>/` | REST + OpenAPI |
| UI location | `ui/streamlit_app.py` when Streamlit | HTTP client to API only — never import `app/` from Streamlit |
| Auth for UI | Same as API (JWT Bearer or API key per brief) | Streamlit stores token in session state |

When the input brief mentions **Streamlit**, set Client UI to **Streamlit** and add an FR that the Streamlit app
implements the primary user journeys (login, role-based views, error display).

## Appendix: Assumptions
(Bullet list of everything not explicitly in the source brief)
"""


def _tool_identifier(tool: Any) -> str:
    for attr in ("tool_name", "name", "__name__"):
        val = getattr(tool, attr, None)
        if isinstance(val, str):
            return val.lower()
    return str(tool).lower()


def _is_write_tool(tool: Any) -> bool:
    name = _tool_identifier(tool)
    return any(marker in name for marker in _WRITE_TOOL_MARKERS)


def _filter_tools(tools: list[Any], *, write_allowed: bool) -> list[Any]:
    if write_allowed:
        return tools
    return [t for t in tools if not _is_write_tool(t)]


def _task_allows_jira_writes(task: str, *, allow_writes_flag: bool) -> bool:
    if not allow_writes_flag:
        return False
    lower = task.lower()
    if any(phrase in lower for phrase in _READ_ONLY_PHRASES):
        return False
    return any(phrase in lower for phrase in _WRITE_PHRASES)


def _atlassian_mcp_basic_auth_value() -> str | None:
    """Base64(email:api_token) for headless AgentCore / CI (Atlassian Rovo MCP API token auth)."""
    preencoded = os.getenv("ATLASSIAN_MCP_BASIC_AUTH", "").strip()
    if preencoded:
        return preencoded
    email = os.getenv("ATLASSIAN_MCP_EMAIL", "").strip()
    token = os.getenv("ATLASSIAN_MCP_TOKEN", "").strip()
    if email and token:
        return base64.b64encode(f"{email}:{token}".encode()).decode("ascii")
    return None


def _atlassian_mcp_url() -> str:
    explicit = os.getenv("ATLASSIAN_MCP_URL", "").strip()
    if explicit:
        return explicit
    if _atlassian_mcp_basic_auth_value():
        return ATLASSIAN_MCP_TOKEN_URL
    return ATLASSIAN_MCP_OAUTH_URL


def _atlassian_mcp_remote_args() -> list[str]:
    args = ["-y", "mcp-remote@latest", _atlassian_mcp_url()]
    basic = _atlassian_mcp_basic_auth_value()
    if basic:
        args.extend(["--header", f"Authorization: Basic {basic}"])
    return args


def _agentcore_jira_runtime_enabled() -> bool:
    """AgentCore kill-switch; default skips Jira unless runtime sets AGENTCORE_PRODUCT_SKIP_JIRA=false."""
    if not os.getenv("AGENTCORE_AGENT", "").strip():
        return True
    flag = os.getenv("AGENTCORE_PRODUCT_SKIP_JIRA", "true").strip().lower()
    return flag not in ("1", "true", "yes", "on")


def _resolve_jira_project(ctx: dict[str, Any], *, task: str = "") -> str:
    for key in ("jiraProjectKey", "projectKey", "jira_project", "jiraProject"):
        raw = ctx.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().upper()
    match = re.search(r"\bproject\s+([A-Z][A-Z0-9_-]{0,19})\b", task, re.I)
    if match:
        return match.group(1).upper()
    return ""


def _jira_backlog_requested(ctx: dict[str, Any], *, task: str = "") -> tuple[bool, str]:
    if not _agentcore_jira_runtime_enabled():
        return False, ""
    project = _resolve_jira_project(ctx, task=task)
    create_flag = ctx.get("createJiraBacklog")
    if create_flag is None:
        create_flag = ctx.get("withJira")
    if create_flag is None:
        create_flag = ctx.get("with_jira")
    if create_flag in (True, "true", "yes", "1", 1):
        return bool(project), project
    lower = task.lower()
    if project and any(
        phrase in lower
        for phrase in ("create jira", "jira epic", "jira backlog", "user stories in jira")
    ):
        return True, project
    return False, project


def _atlassian_mcp() -> MCPClient:
    """Cursor OAuth or headless Basic auth via mcp-remote → Atlassian hosted MCP."""

    remote_args = _atlassian_mcp_remote_args()

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command="npx",
                args=remote_args,
            )
        )

    return MCPClient(transport, prefix="atlassian", startup_timeout=120)


def _bedrock_model() -> BedrockModel:
    import botocore.config

    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    return BedrockModel(
        model_id=os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        streaming=True,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


def _model_id() -> str:
    return os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0").strip()


def _build_prd_agent(*, telemetry: RunTelemetry | None = None) -> Agent:
    callback = (
        StrandsTelemetryCallback(f"{AGENT_NAME}-prd-writer", telemetry, log_tools=False)
        if telemetry is not None
        else None
    )
    return Agent(
        agent_id=f"{AGENT_NAME}-prd-writer",
        name=f"{AGENT_NAME}-prd-writer",
        description="Writes Product Requirements Documents (PRD) in Markdown",
        model=_bedrock_model(),
        system_prompt=PRD_SYS_PROMPT,
        tools=[],
        callback_handler=callback,
    )


_JIRA_AGENT_MAX_TOOL_CALLS_DEFAULT = 30


class _ToolCallBudgetHook(HookProvider):
    """Circuit breaker for the Jira agent: some models loop on read tools (re-checking
    for duplicates, re-fetching metadata) instead of stopping per the system prompt's
    own "minimize tool calls" / "retry once then stop" rules. Past the budget, cancel
    further tool calls with an instructive message so the model is forced to emit a
    final text response (which becomes a normal "jiraBacklog: failed" — not a stall
    that only ends when AgentCore's connection is killed).
    """

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.count = 0

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool_call)

    def _on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        self.count += 1
        if self.count > self.max_calls:
            event.cancel_tool = (
                f"Tool call budget exceeded ({self.max_calls} calls). Stop calling tools now "
                "and reply with a final summary: list any issues you already created "
                "successfully (with keys), and report the rest as not created."
            )


def _build_agent(tools: list[Any], *, telemetry: RunTelemetry | None = None) -> Agent:
    callback = (
        StrandsTelemetryCallback(AGENT_NAME, telemetry)
        if telemetry is not None
        else None
    )
    max_calls = int(
        os.getenv("JIRA_AGENT_MAX_TOOL_CALLS", str(_JIRA_AGENT_MAX_TOOL_CALLS_DEFAULT))
    )
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Jira product agent: epics, stories, bugs, tasks via Atlassian MCP.",
        model=_bedrock_model(),
        system_prompt=PRODUCT_SYS_PROMPT,
        tools=tools,
        callback_handler=callback,
        hooks=[_ToolCallBudgetHook(max_calls)],
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def parse_task_and_context(message: str) -> tuple[str, dict[str, Any]]:
    """Split orchestrator/A2A messages into task text and context JSON."""
    marker = "\n\nContext:\n"
    if marker in message:
        task, rest = message.rsplit(marker, 1)
        try:
            parsed = json.loads(rest)
            if isinstance(parsed, dict):
                return task.strip(), parsed
        except json.JSONDecodeError:
            pass
    return message.strip(), {}


def _extract_brief_from_task(task: str) -> str | None:
    for marker in ("## Product brief\n", "## Product brief\r\n"):
        if marker in task:
            body = task.split(marker, 1)[1]
            body = body.split("\n\nContext:", 1)[0].strip()
            if body:
                return body
    return None


def _infer_target_app_from_text(text: str) -> str | None:
    """Best-effort slug from orchestrator task text"""
    patterns = (
        r"targetApp[\"']?\s*[:=]\s*[\"']?([a-z0-9-]+)",
        r"\bstaged input for\s+([a-z][a-z0-9-]{1,58})\b",
        r"\bfor\s+([a-z][a-z0-9-]{1,58})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        try:
            return pipeline_slugify(match.group(1))
        except ValueError:
            continue
    return None


def _default_staged_input_rel(slug: str) -> str:
    return f"inputs/{slug}.txt"


def enrich_prd_context(context: dict[str, Any], *, task: str = "") -> dict[str, Any]:
    """Fill targetApp, runId, and inputFile when orchestrator sends a minimal task."""
    ctx = dict(context)
    if not (ctx.get("targetApp") or ctx.get("target_app")):
        inferred = _infer_target_app_from_text(task)
        if inferred:
            ctx["targetApp"] = inferred

    if not resolve_run_id(ctx):
        for env_key in ("PIPELINE_RUN_ID", "DEFAULT_PIPELINE_RUN_ID"):
            env_run = os.getenv(env_key, "").strip()
            if env_run:
                ctx["runId"] = env_run
                break
    elif not ctx.get("runId") and resolve_run_id(ctx):
        ctx["runId"] = resolve_run_id(ctx)

    slug = ctx.get("targetApp") or ctx.get("target_app")
    has_input = ctx.get("inputFile") or ctx.get("inputPath") or ctx.get("input_file")
    if slug and not has_input:
        ctx.setdefault("inputFile", _default_staged_input_rel(pipeline_slugify(str(slug))))
    return ctx


def _staged_input_candidates(context: dict[str, Any], *, slug: str) -> list[str]:
    """S3/local input paths to try for a staged brief."""
    explicit = (
        context.get("inputFile")
        or context.get("inputPath")
        or context.get("input_file")
    )
    candidates: list[str] = []
    if explicit:
        candidates.append(str(explicit).replace("\\", "/").lstrip("/"))
    for rel in (
        _default_staged_input_rel(slug),
        f"{slug}/inputs/{slug}.txt",
        f"inputs/{slug.replace('-', '_')}.txt",
    ):
        if rel not in candidates:
            candidates.append(rel)
    return candidates


def resolve_input_text(context: dict[str, Any], *, task: str = "") -> str:
    """Load requirements from inline context, S3 run prefix, or local repo path."""
    for key in ("inputText", "requirementsText", "requirements"):
        value = context.get(key)
        if value and str(value).strip():
            return str(value).strip()

    input_file = (
        context.get("inputFile")
        or context.get("inputPath")
        or context.get("input_file")
    )
    run_id = resolve_run_id(context)
    slug = context.get("targetApp") or context.get("target_app")
    slug_norm = pipeline_slugify(str(slug)) if slug else None

    if run_id:
        from botocore.exceptions import ClientError

        if slug_norm:
            rel_candidates = _staged_input_candidates(context, slug=slug_norm)
        elif input_file:
            rel_candidates = [str(input_file).replace("\\", "/").lstrip("/")]
        else:
            rel_candidates = []

        last_error: Exception | None = None
        for rel in rel_candidates:
            try:
                return get_artifact_text(run_id, rel)
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "NoSuchKey":
                    last_error = exc
                    continue
                raise
            except FileNotFoundError as exc:
                last_error = exc
                continue
        if rel_candidates and is_s3_store():
            raise ValueError(
                f"Input not found in S3 for run {run_id}. Tried: {', '.join(rel_candidates)}. "
                "Upload to runs/<runId>/inputs/ before invoking product-agent."
            ) from last_error
        if rel_candidates and last_error is not None:
            raise ValueError(
                f"Input not found for run {run_id}. Tried: {', '.join(rel_candidates)}."
            ) from last_error

    if input_file:
        return _read_text_file(str(input_file))

    brief = _extract_brief_from_task(task)
    if brief:
        return brief

    if len(task.strip()) > 200:
        return task.strip()

    raise ValueError(
        "No requirements text. Provide inputText, inputFile + runId (S3), "
        "a local input file, or embed the brief in the task."
    )


def _build_pipeline_context_dict(
    *,
    slug: str,
    prd_rel: str,
    input_rel: str | None = None,
    prd_markdown: str = "",
    run_id: str | None = None,
) -> dict[str, Any]:
    delivery_profile = build_delivery_profile_from_paths(
        _REPO_ROOT,
        prd_path=prd_rel,
        input_path=input_rel,
        run_id=run_id,
    )
    # Harden against S3/local path lag: always OR in-memory PRD + input text scans.
    extras: list[dict[str, Any]] = [delivery_profile]
    if prd_markdown.strip():
        extras.append(scan_delivery_text(prd_markdown))
    if input_rel and run_id:
        try:
            input_text = get_artifact_text(run_id, input_rel)
            if input_text.strip():
                extras.append(scan_delivery_text(input_text))
        except Exception:
            pass
    delivery_profile = merge_delivery_profiles(*extras)
    ctx: dict[str, Any] = {
        "targetApp": slug,
        "prdPath": prd_rel,
        "designDocPath": design_doc_rel_for_app(slug),
        "diagramPaths": [diagram_path_for_app(slug)],
        "deliveryProfile": delivery_profile,
    }
    product_brief = _build_product_brief(prd_markdown)
    if product_brief:
        ctx["productBrief"] = product_brief
    if input_rel:
        ctx["inputPath"] = input_rel
        ctx["inputFile"] = input_rel
    return ctx


def _build_product_brief(prd_markdown: str, *, max_chars: int = 700) -> str:
    """Return a compact deterministic product summary from the generated PRD."""
    text = prd_markdown.strip()
    if not text:
        return ""

    title = ""
    overview_lines: list[str] = []
    in_overview = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            heading = re.sub(r"^\d+\.\s*", "", line[3:].strip()).lower()
            in_overview = "overview" in heading or "goal" in heading or "summary" in heading
            continue
        if in_overview:
            overview_lines.append(line.lstrip("-* ").strip())
            if len(" ".join(overview_lines)) >= max_chars:
                break

    parts: list[str] = []
    if title:
        parts.append(f"Feature: {title}")
    if overview_lines:
        parts.append(" ".join(overview_lines))
    brief = "\n".join(parts).strip()
    if len(brief) <= max_chars:
        return brief
    return brief[: max_chars - 3].rstrip() + "..."


def run_prd_from_context(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    telemetry: RunTelemetry | None = None,
) -> str:
    """Generate PRD, persist repo/S3 artifacts, and return a short status message."""
    ctx = enrich_prd_context(dict(context or {}), task=task)
    target = ctx.get("targetApp") or ctx.get("target_app")
    if not target:
        raise ValueError(
            "targetApp is required. Pass it in Context JSON or mention it in the task "
            "(e.g. 'Create PRD for inventory-app')."
        )

    slug = pipeline_slugify(str(target))
    prd_rel = prd_rel_path_for_app(slug)
    ctx_path_rel = pipeline_context_rel_for_app(slug)
    input_text = resolve_input_text(ctx, task=task)

    tel = telemetry or RunTelemetry(
        AGENT_NAME,
        target_app=slug,
        model_id=_model_id(),
        run_id=str(ctx.get("runId") or ctx.get("run_id") or "").strip() or None,
    )
    tel.ensure_run_id(ctx)
    print(f"[product-agent] Generating PRD -> {prd_rel}", file=sys.stderr)

    prd_markdown = _generate_prd_from_text(
        input_text=input_text,
        task_hint=task,
        telemetry=tel,
    )
    write_repo_artifact(prd_rel, prd_markdown, context=ctx)

    input_rel = None
    input_file = ctx.get("inputFile") or ctx.get("inputPath") or ctx.get("input_file")
    if input_file:
        input_rel = str(input_file).replace("\\", "/").lstrip("/")

    run_id = resolve_run_id(ctx)
    pipeline_ctx = _build_pipeline_context_dict(
        slug=slug,
        prd_rel=prd_rel,
        input_rel=input_rel,
        prd_markdown=prd_markdown,
        run_id=run_id,
    )
    if run_id:
        pipeline_ctx["runId"] = run_id
    write_repo_artifact(ctx_path_rel, json.dumps(pipeline_ctx, indent=2) + "\n", context=ctx)
    if run_id:
        put_context(run_id, {**ctx, **pipeline_ctx})

    tel.extra = {"prdSaved": True, "prdPath": prd_rel, "pipelineContext": ctx_path_rel}
    if run_id:
        tel.extra["runId"] = run_id
    tel.finalize(context=ctx)

    print(f"[product-agent] PRD: {prd_rel}", file=sys.stderr)
    print(f"[product-agent] Pipeline context: {ctx_path_rel}", file=sys.stderr)

    lines = [
        f"PRD created for {slug}.",
        f"- prdPath: {prd_rel}",
        f"- pipelineContext: {ctx_path_rel}",
    ]
    if run_id:
        lines.append(f"- runId: {run_id}")
        if is_s3_store():
            lines.append(f"- s3Prefix: runs/{run_id}/")

    requested, project_key = _jira_backlog_requested(ctx, task=task)
    if requested:
        try:
            jira_summary = _run_jira_backlog_from_prd(
                slug=slug,
                prd_rel=prd_rel,
                ctx=ctx,
                project_key=project_key,
                parent_telemetry=tel,
            )
            lines.append(f"- jiraProjectKey: {project_key}")
            lines.append(f"- jiraBacklog: created")
            lines.append("")
            lines.append(jira_summary)
            pipeline_ctx["jiraProjectKey"] = project_key
            pipeline_ctx["jiraBacklogCreated"] = True
            write_repo_artifact(
                ctx_path_rel,
                json.dumps(pipeline_ctx, indent=2) + "\n",
                context=ctx,
            )
            if run_id:
                put_context(run_id, {**ctx, **pipeline_ctx})
        except Exception as exc:
            print(f"[product-agent] Jira backlog failed (PRD kept): {exc}", file=sys.stderr)
            lines.append(f"- jiraBacklog: failed ({exc})")
    elif project_key and not _agentcore_jira_runtime_enabled():
        lines.append(
            "- jiraBacklog: skipped (set AGENTCORE_PRODUCT_SKIP_JIRA=false on product-agent runtime)"
        )

    return "\n".join(lines)


def _prompt_to_text(prompt: Any) -> str:
    """Normalize Strands/A2A prompt shapes to plain text for the PRD pipeline."""
    if prompt is None:
        return ""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        parts: list[str] = []
        for block in prompt:
            if isinstance(block, dict):
                if "text" in block:
                    parts.append(str(block["text"]))
                    continue
                for item in block.get("content") or []:
                    if isinstance(item, dict) and "text" in item:
                        parts.append(str(item["text"]))
            elif hasattr(block, "text"):
                parts.append(str(block.text))
        if parts:
            return "\n".join(parts)
    return str(prompt)


def _prd_pipeline_error_message(exc: ValueError, ctx: dict[str, Any]) -> str:
    example = {
        "targetApp": ctx.get("targetApp") or "inventory-app",
        "runId": ctx.get("runId") or "smoke-001",
        "inputFile": ctx.get("inputFile") or "inputs/inventory-app.txt",
    }
    return (
        "PRD pipeline could not start.\n\n"
        f"Reason: {exc}\n\n"
        "Append this block to your message (or set PIPELINE_RUN_ID on the runtime):\n\n"
        f"Context:\n{json.dumps(example, indent=2)}\n\n"
        "Upload the brief first:\n"
        "  s3://<bucket>/runs/<runId>/<inputFile>"
    )


def _execute_prd_pipeline_message(message: Any) -> str:
    """Run PRD generation + artifact persistence from an A2A/CLI message."""
    text = _prompt_to_text(message)
    if text.strip().lower().startswith("control-plane health check"):
        return "OK"
    task, ctx = parse_task_and_context(text)
    ctx = enrich_prd_context(ctx, task=task)
    try:
        return run_prd_from_context(task, ctx)
    except ValueError as exc:
        return _prd_pipeline_error_message(exc, ctx)


def _agent_result_from_text(text: str) -> Any:
    from strands.agent.agent_result import AgentResult
    from strands.telemetry.metrics import EventLoopMetrics

    return AgentResult(
        stop_reason="end_turn",
        message={"role": "assistant", "content": [{"text": text}]},
        metrics=EventLoopMetrics(),
        state={},
    )


def build_prd_pipeline_agent() -> Agent:
    """AgentCore PRD-only mode: deterministic PRD pipeline on each A2A message."""
    agent = _build_prd_agent()

    def prd_invoke(message: Any, **kwargs: Any) -> str:
        return _execute_prd_pipeline_message(message)

    async def prd_stream_async(
        prompt: Any = None,
        *,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """A2A entrypoint — StrandsA2AExecutor calls stream_async, not __call__."""
        from strands.types._events import AgentResultEvent

        del invocation_state, kwargs
        summary = _execute_prd_pipeline_message(prompt)
        yield AgentResultEvent(result=_agent_result_from_text(summary)).as_dict()

    agent.__call__ = prd_invoke  # type: ignore[method-assign]
    agent.stream_async = prd_stream_async  # type: ignore[method-assign]
    return agent


def _slugify(text: str, *, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug[:max_len].rstrip("-")
    return slug or "prd"


def _prd_output_dir() -> Path:
    raw = os.getenv("PRODUCT_PRD_OUTPUT_DIR", "docs/PRD")
    out_dir = Path(raw)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _read_text_file(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = (_REPO_ROOT / p).resolve()
    return p.read_text(encoding="utf-8")


def _normalize_prd_markdown(text: str) -> str:
    """Strip accidental code fences or leading chit-chat from model output."""
    body = text.strip()
    if body.startswith("```"):
        lines = body.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        body = "\n".join(lines).strip()
    for prefix in ("Here is the PRD:", "Here's the PRD:", "Below is the PRD:"):
        if body.lower().startswith(prefix.lower()):
            body = body[len(prefix) :].strip()
    if not body.startswith("#"):
        idx = body.find("\n# ")
        if idx == -1 and body.startswith("# "):
            pass
        elif idx >= 0:
            body = body[idx + 1 :].lstrip()
    return body + "\n"


def _generate_prd_from_text(
    *,
    input_text: str,
    task_hint: str | None = None,
    telemetry: RunTelemetry | None = None,
) -> str:
    prd_agent = _build_prd_agent(telemetry=telemetry)
    task_part = f"\n\nAdditional instructions: {task_hint.strip()}" if task_hint and task_hint.strip() else ""
    user_message = (
        "The following text is the ONLY source of truth. It may be informal and incomplete.\n"
        "Do not ask clarifying questions — produce the full PRD template with FR/NFR tables now.\n\n"
        "--- BEGIN INPUT ---\n"
        f"{input_text.strip()}\n"
        "--- END INPUT ---\n"
        f"{task_part}\n\n"
        "Return only the PRD Markdown starting with `# `."
    )
    return _normalize_prd_markdown(str(prd_agent(user_message)))

def _normalize_story_title_style(style: str | None) -> str:
    if not style:
        return _DEFAULT_STORY_TITLE_STYLE
    normalized = style.strip().lower().replace("_", "-")
    if normalized not in _STORY_TITLE_STYLES:
        allowed = ", ".join(_STORY_TITLE_STYLES)
        raise SystemExit(f"Invalid story title style {style!r}. Use one of: {allowed}")
    return normalized


def _minimal_jira_task_from_prd(*, story_title_style: str) -> str:
    style_note = (
        "Use concise prefixed story summaries (Tech|Product|PROD - Area - Outcome); "
        "put the full user story and acceptance criteria in the description."
        if story_title_style == "concise"
        else "Use full user-story sentences as story summaries."
    )
    return (
        "Create an epic and exactly 5 user stories in Jira based on the PRD in context. "
        "For each user story include at least 3 acceptance criteria using Given / When / Then. "
        f"{style_note} "
        "Follow storyTitleStyle and Story writing rules in your system prompt. "
        "Do not create any additional tickets besides the epic and those stories. "
        "Use a minimal create payload (project, issue type, summary, description, epic link/parent). "
        "Do not use story_points or other custom fields unless metadata explicitly confirms they are available."
    )

def _run_jira_backlog_from_prd(
    *,
    slug: str,
    prd_rel: str,
    ctx: dict[str, Any],
    project_key: str,
    story_title_style: str | None = None,
    parent_telemetry: RunTelemetry | None = None,
) -> str:
    """Create epic + 5 stories after PRD persist; soft-fails so PRD artifacts remain valid."""
    style = _normalize_story_title_style(
        story_title_style
        or str(ctx.get("jiraStoryTitleStyle") or ctx.get("storyTitleStyle") or "").strip()
        or os.getenv("JIRA_STORY_TITLE_STYLE", _DEFAULT_STORY_TITLE_STYLE)
    )
    prd_markdown = read_repo_artifact(prd_rel, context=ctx).decode("utf-8")
    jira_context = dict(ctx)
    jira_context["projectKey"] = project_key
    jira_context["jiraProjectKey"] = project_key
    jira_context["prdMarkdown"] = prd_markdown
    jira_context["prdPath"] = prd_rel
    jira_context["createJiraBacklog"] = True

    jira_task = _minimal_jira_task_from_prd(story_title_style=style)
    if ctx.get("jiraSprintId") or ctx.get("sprintId"):
        sprint_id = ctx.get("jiraSprintId") or ctx.get("sprintId")
        jira_task += f" Add stories to sprint {sprint_id}."

    print(
        f"[product-agent] Creating Jira backlog in {project_key} "
        f"(Epic + 5 Stories, title style: {style})...",
        file=sys.stderr,
    )
    jira_telemetry = RunTelemetry(
        AGENT_NAME,
        target_app=slug,
        model_id=_model_id(),
        run_id=str(ctx.get("runId") or ctx.get("run_id") or "").strip() or None,
    )
    jira_telemetry.ensure_run_id(ctx)
    summary = run_task(jira_task, jira_context, write_allowed=True, telemetry=jira_telemetry)
    jira_telemetry.extra = {"prdSaved": True, "jiraBacklog": True, "jiraProjectKey": project_key}
    jira_telemetry.finalize(context=ctx)
    if parent_telemetry is not None:
        parent_telemetry.extra = {**(parent_telemetry.extra or {}), "jiraBacklog": True}
    return str(summary)


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    write_allowed: bool = False,
    telemetry: RunTelemetry | None = None,
) -> str:
    ctx = dict(context or {})
    ctx["jiraWriteAllowed"] = write_allowed
    with _atlassian_mcp() as mcp:
        tools = _filter_tools(mcp.list_tools_sync(), write_allowed=write_allowed)
        agent = _build_agent(tools, telemetry=telemetry)
        return str(agent(_user_message(task, ctx)))

def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    skills = [
        AgentSkill(
            id="backlog_creation",
            name="backlog_creation",
            description="Create Jira epics and stories from requirements",
            tags=["jira", "product"],
        )
    ]
    with _atlassian_mcp() as mcp:
        agent = _build_agent(mcp.list_tools_sync())
        A2AServer(agent, host=host, port=port, skills=skills).serve()

def _write_pipeline_context(
    *,
    prd_base: str,
    prd_path: Path,
    input_path: Path | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Write agents/pipeline/<slug>.context.json so downstream agents auto-discover this product."""
    slug = _slugify(prd_base)
    prd_rel = str(prd_path.relative_to(_REPO_ROOT).as_posix())
    input_rel = (
        str(input_path.relative_to(_REPO_ROOT).as_posix()) if input_path else None
    )
    pipeline_ctx = _build_pipeline_context_dict(
        slug=slug,
        prd_rel=prd_rel,
        input_rel=input_rel,
        prd_markdown=prd_path.read_text(encoding="utf-8") if prd_path.is_file() else "",
    )
    ctx_path_rel = pipeline_context_rel_for_app(slug)
    write_repo_artifact(
        ctx_path_rel,
        json.dumps(pipeline_ctx, indent=2) + "\n",
        context=context,
    )
    print(f"[product-agent] Pipeline context: {ctx_path_rel}", file=sys.stderr)
    if pipeline_ctx.get("deliveryProfile", {}).get("requiresStreamlit"):
        print(
            "[product-agent] deliveryProfile: requiresStreamlit=true (architect + developer must deliver ui/)",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Product agent - Strands + Atlassian MCP")
    parser.add_argument("--task", help="Business requirement or Jira operation")
    parser.add_argument(
        "--input-file",
        help="Path to a text document containing the initial product brief/requirements.",
    )
    parser.add_argument(
        "--prd-name",
        help="Optional basename for saved PRD markdown (default: input file stem).",
    )
    parser.add_argument(
        "--create-jira-tickets",
        action="store_true",
        help="After saving the PRD, create a Jira backlog (1 Epic + 5 User Stories) via Atlassian MCP.",
    )
    parser.add_argument("--project", help="Jira project key (e.g. SAAP)")
    parser.add_argument("--sprint", type=int, help="Jira sprint id")
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="Enable Jira write tools; --task must include an explicit write phrase. "
        "Default: read-only.",
    )
    parser.add_argument(
        "--story-title-style",
        choices=_STORY_TITLE_STYLES,
        default=os.getenv("JIRA_STORY_TITLE_STYLE", _DEFAULT_STORY_TITLE_STYLE),
        help="Jira story summary format: concise (Tech|Product|PROD - Area - Outcome, default) "
        "or user-story (full As a... sentence).",
    )
    parser.add_argument("--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    story_title_style = _normalize_story_title_style(args.story_title_style)

    context: dict[str, Any] = {"storyTitleStyle": story_title_style}
    if args.project:
        context["projectKey"] = args.project
    if args.sprint is not None:
        context["sprintId"] = args.sprint

    # Windows console sometimes errors on emojis; replace rather than crash.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.input_file:
        input_path = Path(args.input_file)
        if not input_path.is_absolute():
            input_path = (_REPO_ROOT / input_path).resolve()
        if not input_path.is_file():
            raise SystemExit(f"Input file not found: {args.input_file}")

        prd_base = args.prd_name or input_path.stem
        slug = pipeline_slugify(prd_base)
        input_rel = str(input_path.relative_to(_REPO_ROOT).as_posix())
        run_ctx: dict[str, Any] = {
            "targetApp": slug,
            "inputFile": input_rel,
            **context,
        }
        run_id = resolve_run_id(run_ctx)
        if run_id:
            run_ctx["runId"] = run_id

        telemetry = RunTelemetry(
            AGENT_NAME,
            target_app=slug,
            model_id=_model_id(),
            run_id=run_ctx.get("runId"),
        )
        summary = run_prd_from_context(
            task=args.task or f"Create PRD from {input_rel}",
            context=run_ctx,
            telemetry=telemetry,
        )
        print(summary)

        if args.create_jira_tickets:
            if not args.allow_writes:
                print(
                    "[product-agent] --create-jira-tickets requested but --allow-writes is not set; "
                    "PRD saved only (no Jira writes).",
                    file=sys.stderr,
                )
                return
            if "projectKey" not in context:
                raise SystemExit("Jira project key required: pass --project <PROJECT_KEY>.")

            prd_rel = prd_rel_path_for_app(slug)
            prd_markdown = read_repo_artifact(prd_rel, context=run_ctx).decode("utf-8")
            jira_context = dict(run_ctx)
            jira_context["prdMarkdown"] = prd_markdown
            jira_context["prdPath"] = prd_rel

            jira_task = _minimal_jira_task_from_prd(story_title_style=story_title_style)
            print(
                f"[product-agent] Creating Jira backlog (Epic + 5 Stories, title style: {story_title_style})...",
                file=sys.stderr,
            )
            jira_telemetry = RunTelemetry(
                AGENT_NAME,
                target_app=slug,
                model_id=_model_id(),
                run_id=run_ctx.get("runId"),
            )
            print(run_task(jira_task, jira_context, write_allowed=True, telemetry=jira_telemetry))
            jira_telemetry.extra = {"prdSaved": True, "jiraBacklog": True}
            jira_telemetry.finalize()
            return

        print(
            "[product-agent] PRD mode complete. "
            "Rerun with --create-jira-tickets --allow-writes --project <PROJECT_KEY> to create Jira tickets.",
            file=sys.stderr,
        )
        return

    if not args.task:
        parser.error("--task is required unless --input-file or --serve-a2a is set")

    write_allowed = _task_allows_jira_writes(args.task, allow_writes_flag=args.allow_writes)
    mode = "WRITE" if write_allowed else "READ-ONLY"
    print(f"[product-agent] Mode: {mode}", file=sys.stderr)
    if args.allow_writes and not write_allowed:
        print(
            "[product-agent] --allow-writes set but task has no write phrase or has "
            "read-only phrase. Running read-only.",
            file=sys.stderr,
        )

    telemetry = RunTelemetry(AGENT_NAME, target_app=None, model_id=_model_id())
    print("[product-agent] Connecting to Atlassian MCP via mcp-remote", file=sys.stderr)
    print("[product-agent] Running...")
    print(run_task(args.task, context or None, write_allowed=write_allowed, telemetry=telemetry))
    telemetry.finalize()

if __name__ == "__main__":
    main()