"""Product agent - Strands + Bedrock + Atlassian MCP (Jira)"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.env import load_repo_env
from _shared.pipeline_context import diagram_path_for_app

load_repo_env()

from a2a.types import AgentSkill
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp import MCPClient

AGENT_NAME = "product-agent"
A2A_PORT = 9101
ATLASSIAN_MCP_URL = os.getenv(
    "ATLASSIAN_MCP_URL",
    "https://mcp.atlassian.com/v1/mcp/authv2",
)

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
You are the Product Agent for the Autonomous SDLC platform. You create and manage Jira
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


def _atlassian_mcp() -> MCPClient:
    """Same transport as Cursor `.cursor/mcp.json` — npx mcp-remote + OAuth (not raw SSE)."""

    def transport() -> object:
        return stdio_client(
            StdioServerParameters(
                command="npx",
                args=["-y", "mcp-remote@latest", ATLASSIAN_MCP_URL],
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


def _build_agent(tools: list[Any]) -> Agent:
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Jira product agent: epics, stories, bugs, tasks via Atlassian MCP.",
        model=_bedrock_model(),
        system_prompt=PRODUCT_SYS_PROMPT,
        tools=tools,
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


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


def _generate_prd_from_text(*, input_text: str, task_hint: str | None = None) -> str:
    prd_agent = Agent(
        agent_id=f"{AGENT_NAME}-prd-writer",
        name=f"{AGENT_NAME}-prd-writer",
        description="Writes Product Requirements Documents (PRD) in Markdown",
        model=_bedrock_model(),
        system_prompt=PRD_SYS_PROMPT,
        tools=[],
    )
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

def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    write_allowed: bool = False,
) -> str:
    ctx = dict(context or {})
    ctx["jiraWriteAllowed"] = write_allowed
    with _atlassian_mcp() as mcp:
        tools = _filter_tools(mcp.list_tools_sync(), write_allowed=write_allowed)
        agent = _build_agent(tools)
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

def _write_pipeline_context(*, prd_base: str, prd_path: Path) -> None:
    """Write agents/pipeline/<slug>.context.json so downstream agents auto-discover this product."""
    pipeline_dir = _REPO_ROOT / "agents" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(prd_base)
    ctx = {
        "targetApp": slug,
        "prdPath": str(prd_path.relative_to(_REPO_ROOT).as_posix()),
        "designDocPath": f"docs/design/{slug}.md",
        "diagramPaths": [diagram_path_for_app(slug)],
    }
    ctx_path = pipeline_dir / f"{slug}.context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2) + "\n", encoding="utf-8")
    print(f"[product-agent] Pipeline context: {ctx_path.relative_to(_REPO_ROOT)}", file=sys.stderr)


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
            input_path = _REPO_ROOT / input_path
        input_path = input_path.resolve()
        if not input_path.is_file():
            raise SystemExit(f"Input file not found: {args.input_file}")

        input_text = input_path.read_text(encoding="utf-8")
        prd_dir = _prd_output_dir()
        prd_base = args.prd_name or input_path.stem
        prd_path = (prd_dir / f"{_slugify(prd_base)}.md").resolve()

        print(f"[product-agent] Generating PRD -> {prd_path}", file=sys.stderr)
        prd_markdown = _generate_prd_from_text(input_text=input_text, task_hint=args.task)
        prd_path.write_text(prd_markdown, encoding="utf-8", newline="\n")
        print(f"[product-agent] Saved PRD: {prd_path}", file=sys.stderr)

        _write_pipeline_context(prd_base=prd_base, prd_path=prd_path)

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

            jira_context = dict(context)
            jira_context["prdMarkdown"] = prd_markdown
            jira_context["prdPath"] = str(prd_path)

            jira_task = _minimal_jira_task_from_prd(story_title_style=story_title_style)
            print(
                f"[product-agent] Creating Jira backlog (Epic + 5 Stories, title style: {story_title_style})...",
                file=sys.stderr,
            )
            print(run_task(jira_task, jira_context, write_allowed=True))
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

    print("[product-agent] Connecting to Atlassian MCP via mcp-remote", file=sys.stderr)
    print("[product-agent] Running...")
    print(run_task(args.task, context or None, write_allowed=write_allowed))

if __name__ == "__main__":
    main()