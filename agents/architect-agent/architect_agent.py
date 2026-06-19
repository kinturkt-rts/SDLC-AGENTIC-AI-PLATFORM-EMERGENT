"""Architect agent - Strands + Bedrock + AWS Diagram MCP"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.mcp_clients import aws_diagram_mcp_client
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    repo_rel,
    resolve_cli_context,
    resolve_design_doc_path,
)

load_repo_env()

from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.mcp import MCPClient
from strands.types.exceptions import MCPClientInitializationError

AGENT_NAME = "architect-agent"
A2A_PORT = 9102
DEFAULT_DIAGRAM_DIR = _REPO_ROOT / "docs" / "diagrams" / "generated-diagrams"
DEFAULT_DIAGRAM_BASE_NAME = "architecture-diagram"

DEFAULT_PIPELINE_TASK = """\
Use handoff in Context (prdPath, productAgentOutput, targetApp).
1. Read the PRD scope from context; produce one AWS architecture PNG via generate_diagram.
2. Write design doc at context `designDocPath` (default `docs/design/<targetApp>.md`) per design-writer rules unless --skip-design.
3. Save PNG under diagramOutputDir using diagramBaseName (default: targetApp slug).
4. Return saved diagram path, brief ADR bullets, and do not paste diagram Python source.\
"""

ARCHITECT_SYS_PROMPT = """\
You are the Architect Agent for the Autonomous SDLC platform. You produce a **single**
AWS architecture PNG using the AWS Diagram MCP tools.

## Tool budget (minimize latency)
1. Call `awsdiagram_get_diagram_examples` once (`diagram_type`: `aws`).
2. Optionally call `awsdiagram_list_icons` once only if you need an uncommon icon.
3. Call `awsdiagram_generate_diagram` **exactly once** with simple code (see below).
4. **Do not retry** generate_diagram on failure. Report the error briefly and stop.

## Keep diagrams simple (required)
- Target **8–14 nodes** total across all clusters.
- At most **3 clusters** (e.g. Users/API, Data, Integrations).
- **ASCII-only** labels: letters, numbers, spaces, hyphen. No em-dash, arrows, or Unicode.
- Diagram title: short ASCII (e.g. `FinOps Web App MVP`).
- Prefer left-to-right (`direction="LR"`). Avoid fan-out edges to lists of nodes.
- Use only icons you saw in examples or list_icons. Do not invent class names.

## generate_diagram parameters
- `code`: Python DSL only (no import lines — runtime pre-imports classes).
- `filename`: context `diagramOutputFile` (absolute POSIX path, no `.png` suffix).
- `workspace_dir`: context `diagramOutputDir`.

## Diagram code rules
- Start with `with Diagram(` — no imports, no other top-level code.
- `show=False` always.
- Map PRD components only; do not add Redshift/SageMaker/Kinesis unless the task or PRD requires them.

Example skeleton:
```python
with Diagram("FinOps MVP", filename="/abs/path/finops-web-app", show=False, direction="LR"):
    with Cluster("App"):
        user = Users("Users")
        api = APIGateway("API")
    with Cluster("Data"):
        s3 = S3("CUR S3")
        ath = Athena("Athena")
    user >> api >> ath
```

## Your text response (keep short)
Return **only**:
1. **Saved diagram**: path from generate_diagram (or one-line failure reason).
2. **ADR** (optional, max 6 bullets): Context / Key decisions / Trade-offs — no tables, no open questions unless asked.
3. **Do not** paste the diagram Python source code in your reply.
4. **Do not** duplicate content or repeat the same summary twice.

## General
- Align with `prdPath` / `productAgentOutput` in context when present.
- Do not invent Jira keys. Jira is not required for architecture.
- FastAPI services under `target-apps/` when the PRD implies an app tier.
- A follow-up step writes the per-feature design doc (`designDocPath` in context) for database-agent and developer-agent; keep ADR bullets aligned with that doc.
"""

DESIGN_SYS_PROMPT = """\
You are a solution architect writing a **compact** Markdown handoff for database-agent
and developer-agent. The AWS diagram PNG is separate; do not repeat long narratives here.

## Brevity (required)
- Target **≤ 90 lines** total.
- **database-agent** uses sections **3** and **6** only for DDL/seeds.
- **developer-agent** uses sections **4** and **5** for FastAPI routes and guards.
- Reference PRD as `FR-x` / `NFR-x` instead of copying PRD text.
- No open-questions table (unknowns → one line under Summary as "TBD: ...").
- No CI/CD or CDK sections.
- **Do not omit client UI** when PRD section 11 or `deliveryProfile.requiresStreamlit` is true.

## UI in Stack (mandatory when PRD/brief requires it)
When the PRD or `deliveryProfile` requires Streamlit, section **2. Stack** MUST include:
`| UI | Streamlit | ui/streamlit_app.py calls FastAPI over HTTP (port 8501) |`
When React/Next is required (Phase 2), note `frontend/` in Stack — developer implements only when explicitly in profile.

## Output rules
1. Output **ONLY** Markdown starting with `# <Feature> — Solution Design`.
2. Use **exact** section headings below (numbers matter).
3. Concrete types, paths, enums — no placeholder "TBD" columns in data/API tables.

# <Feature> — Solution Design

## 1. Summary
(2–3 sentences: app purpose, primary DB, API style. Optional: `Diagram: <path>`.)

## 2. Stack
| Layer | Technology |
|-------|------------|
(Max **6** rows — match the architecture diagram.)

## 3. Data model
| Table / collection | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|--------------------|----------------------------------|------------------------|

(Max **8** Postgres tables for MVP; include `audit_log` if PRD requires. Enough for DDL.)

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|

(Max **10** MVP endpoints; Pydantic field names.)

## 5. Rules
- Auth / RBAC: (roles + which routes)
- Audit: (what to log, immutable rules)
- Idempotency / status enums: (payment or workflow tables if any)
(Max **8** bullets.)

## 6. DB delivery
1. Migration order: `001_....sql`, `002_....sql`, ...
2. Seed data: (minimal rows for local dev / tests)
3. Athena or NoSQL: (only if used — else omit)
"""


def _design_output_path(*, design_rel: str | None = None) -> Path:
    """Absolute path for design markdown (per-feature when design_rel is set)."""
    raw = (design_rel or resolve_design_doc_path(None)).strip()
    path = Path(raw)
    if not path.is_absolute():
        path = (_REPO_ROOT / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_repo_text(relative_or_abs: str) -> str:
    p = Path(relative_or_abs.strip())
    if not p.is_absolute():
        p = (_REPO_ROOT / p).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"not found: {p}")
    return p.read_text(encoding="utf-8")


def _normalize_design_markdown(text: str) -> str:
    body = text.strip()
    if body.startswith("```"):
        lines = body.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        body = "\n".join(lines).strip()
    for prefix in ("Here is the design:", "Here's the design:", "Below is the design:"):
        if body.lower().startswith(prefix.lower()):
            body = body[len(prefix) :].strip()
    if not body.startswith("#"):
        idx = body.find("\n# ")
        if idx >= 0:
            body = body[idx + 1 :].lstrip()
    return body + "\n"


def _architect_summary_from_design(design_md: str, *, max_chars: int = 1200) -> str:
    """Short handoff string for context.architectSummary."""
    match = re.search(
        r"(?ms)^##\s*1\.\s*Summary\s*\n(.*?)(?=^##\s|\Z)",
        design_md,
    )
    block = match.group(1).strip() if match else design_md.strip().split("\n\n", 1)[0]
    if len(block) > max_chars:
        return block[: max_chars - 3].rstrip() + "..."
    return block


def _generate_design_markdown(
    *,
    task: str,
    context: dict[str, Any],
    diagram_summary: str,
    diagram_paths: list[Path],
) -> str:
    prd_text = ""
    prd_path = context.get("prdPath") or context.get("prd_path")
    if prd_path:
        try:
            prd_text = _read_repo_text(str(prd_path))
        except OSError:
            prd_text = f"(PRD file not readable: {prd_path})"
    product_out = context.get("productAgentOutput") or context.get("product_agent_output") or ""
    paths_block = "\n".join(f"- {p.as_posix()}" for p in diagram_paths) or "(no diagram PNG)"

    design_agent = Agent(
        agent_id=f"{AGENT_NAME}-design-writer",
        name=f"{AGENT_NAME}-design-writer",
        description="Writes solution design Markdown for developer and database agents",
        model=_bedrock_model(),
        system_prompt=DESIGN_SYS_PROMPT,
        tools=[],
    )
    user_message = (
        "Produce a **compact** solution design (≤ 90 lines). "
        "Sections 3+6 are for database-agent; 4+5 for developer-agent.\n"
        "Do not ask clarifying questions.\n\n"
        f"## Architecture task\n{task.strip()}\n\n"
        f"## Diagram agent notes\n{diagram_summary.strip() or '(none)'}\n\n"
        f"## Diagram files\n{paths_block}\n\n"
    )
    if product_out:
        user_message += f"## Product / backlog summary\n{str(product_out).strip()}\n\n"
    if prd_text:
        user_message += (
            "## PRD (source of truth for FR/NFR)\n"
            "--- BEGIN PRD ---\n"
            f"{prd_text.strip()}\n"
            "--- END PRD ---\n\n"
        )
    delivery_profile = context.get("deliveryProfile")
    if delivery_profile:
        user_message += (
            "## Delivery profile (MANDATORY — do not drop UI)\n"
            f"{json.dumps(delivery_profile, indent=2)}\n\n"
        )
        if delivery_profile.get("requiresStreamlit"):
            user_message += (
                "When requiresStreamlit is true, section 2 Stack MUST list Streamlit and "
                "`ui/streamlit_app.py`. Do not specify API-only.\n\n"
            )
    target = context.get("targetApp") or context.get("target_app")
    if target:
        user_message += f"## Target FastAPI service folder\n`target-apps/{target}/`\n\n"
    user_message += "Return only the Markdown starting with `# `."
    return _normalize_design_markdown(str(design_agent(user_message)))


def _write_design_doc(markdown: str, *, design_rel: str) -> Path:
    path = _design_output_path(design_rel=design_rel)
    path.write_text(markdown, encoding="utf-8", newline="\n")
    return path


def _skip_design_generation() -> bool:
    flag = os.getenv("ARCHITECT_SKIP_DESIGN", "").strip().lower()
    return flag in ("1", "true", "yes")


def _diagram_output_dir(override: str | None = None) -> Path:
    raw = override or os.getenv("ARCHITECT_DIAGRAM_OUTPUT_DIR", "")
    path = Path(raw) if raw else DEFAULT_DIAGRAM_DIR
    if not path.is_absolute():
        path = _REPO_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _bedrock_model() -> BedrockModel:
    return BedrockModel(
        model_id=os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        streaming=True,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
    )


def _build_agent(tools: list[Any]) -> Agent:
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Creates AWS architecture PNG diagrams and per-feature docs/design/<app>.md.",
        model=_bedrock_model(),
        system_prompt=ARCHITECT_SYS_PROMPT,
        tools=tools,
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _slugify(text: str, *, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") if slug else "diagram"


def _resolve_diagram_base_name(
    explicit: str | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """Short file basename — never derived from the full --task prompt."""
    if explicit and explicit.strip():
        return _slugify(explicit.strip())
    if context:
        for key in ("diagramBaseName", "diagramName", "diagram_name"):
            value = context.get(key)
            if value and str(value).strip():
                return _slugify(str(value).strip())
    env_name = os.getenv("ARCHITECT_DIAGRAM_NAME", "").strip()
    if env_name:
        return _slugify(env_name)
    if context:
        app = context.get("targetApp") or context.get("target_app")
        if app and str(app).strip():
            return _slugify(str(app).strip())
        epic = context.get("epicKey") or context.get("epic_key")
        if epic and str(epic).strip():
            return _slugify(f"{epic}-architecture")
    return DEFAULT_DIAGRAM_BASE_NAME


def _diagram_output_file(output_dir: Path, base_name: str) -> str:
    """Absolute POSIX path for Diagram() / generate_diagram (no .png suffix)."""
    return (output_dir / base_name).resolve().as_posix()


def _normalize_diagram_outputs(output_dir: Path, base_name: str, since: float) -> list[Path]:
    """Move MCP fallback PNGs from generated-diagrams/ into output_dir root."""
    nested = output_dir / "generated-diagrams"
    if nested.is_dir():
        target = output_dir / f"{base_name}.png"
        for src in nested.glob("*.png"):
            if src.stat().st_mtime < since:
                continue
            dest = target if src.stem == base_name or not target.exists() else output_dir / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dest.resolve():
                src.replace(dest)
    return _collect_saved_pngs(output_dir, since)


def _collect_saved_pngs(output_dir: Path, since: float) -> list[Path]:
    """Return PNG files under output_dir (incl. generated-diagrams/) written at or after `since`."""
    if not output_dir.is_dir():
        return []
    return sorted(
        p
        for p in output_dir.rglob("*.png")
        if p.is_file() and p.stat().st_mtime >= since
    )

def _build_diagram_context(
    output_dir: Path,
    *,
    diagram_base_name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _resolve_diagram_base_name(diagram_base_name, extra)
    ctx: dict[str, Any] = {
        "diagramOutputDir": output_dir.as_posix(),
        "diagramBaseName": base,
        "diagramOutputFile": _diagram_output_file(output_dir, base),
    }
    if extra:
        ctx.update(extra)
    ctx["designDocPath"] = resolve_design_doc_path(ctx)
    return ctx


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    output_dir: Path | None = None,
    diagram_base_name: str | None = None,
    skip_design: bool | None = None,
) -> tuple[str, list[Path], Path | None]:
    out_dir = output_dir or _diagram_output_dir()
    if context is None:
        context = _build_diagram_context(out_dir, diagram_base_name=diagram_base_name)
    else:
        base = _resolve_diagram_base_name(diagram_base_name, context)
        context.setdefault("diagramOutputDir", out_dir.as_posix())
        context.setdefault("diagramBaseName", base)
        context.setdefault("diagramOutputFile", _diagram_output_file(out_dir, base))
    context["designDocPath"] = resolve_design_doc_path(context)
    scan_start = time.time()
    design_path: Path | None = None
    try:
        with aws_diagram_mcp_client(cwd=_REPO_ROOT) as mcp:
            agent = _build_agent(mcp.list_tools_sync())
            summary = str(agent(_user_message(task, context)))
        base = context.get("diagramBaseName", DEFAULT_DIAGRAM_BASE_NAME)
        saved = _normalize_diagram_outputs(out_dir, str(base), scan_start)

        do_design = not (skip_design if skip_design is not None else _skip_design_generation())
        if do_design:
            design_md = _generate_design_markdown(
                task=task,
                context=context,
                diagram_summary=summary,
                diagram_paths=saved,
            )
            design_rel = str(context["designDocPath"])
            design_path = _write_design_doc(design_md, design_rel=design_rel)
            context["architectSummary"] = _architect_summary_from_design(design_md)
        return summary, saved, design_path
    except MCPClientInitializationError as exc:
        raise SystemExit(
            "AWS Diagram MCP failed to start.\n"
            "Ensure `uv` is installed and on PATH.\n"
            f"Details: {exc}"
        ) from exc


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    skills = [
        AgentSkill(
            id="architecture_diagrams",
            name="architecture_diagrams",
            description="AWS architecture PNG diagrams, per-feature design docs, and ADR summaries",
            tags=["architecture", "aws-diagram", "design"],
        )
    ]
    with aws_diagram_mcp_client(cwd=_REPO_ROOT) as mcp:
        agent = _build_agent(mcp.list_tools_sync())
        A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Architect agent - Strands + AWS Diagram MCP")
    parser.add_argument(
        "--task",
        help="Optional override. Default: pipeline task (reads PRD from Context).",
    )
    parser.add_argument(
        "--target-app",
        help="Target app slug for pipeline context (default: finops-web-app or context JSON)",
    )
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Do not load agents/pipeline/<target-app>.context.json when --context-file/json omitted",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for PNG diagrams (default: docs/diagrams/generated-diagrams)",
    )
    parser.add_argument(
        "--diagram-name",
        help=(
            "Short basename for exported files (e.g. checkout-flow). "
            f"Default: targetApp from context, or {DEFAULT_DIAGRAM_BASE_NAME}"
        ),
    )
    load_context_extra(parser)
    parser.add_argument(
        "--skip-design",
        action="store_true",
        help="Skip writing the per-feature design doc (diagram only)",
    )
    parser.add_argument("--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    if not args.task:
        args.task = DEFAULT_PIPELINE_TASK

    out_dir = _diagram_output_dir(args.output_dir)
    try:
        extra, _app = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="ARCHITECT_TARGET_APP",
        )
    except TargetAppRequiredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    enrich_handoff_context(extra)

    context = _build_diagram_context(
        out_dir,
        diagram_base_name=args.diagram_name,
        extra=extra or None,
    )
    diagram_base = context["diagramBaseName"]
    design_rel = context.get("designDocPath", resolve_design_doc_path(context))

    print("[architect-agent] Starting AWS Diagram MCP Server", file=sys.stderr)
    print(f"[architect-agent] Diagram: {repo_rel(out_dir)}/{diagram_base}.png", file=sys.stderr)
    if args.skip_design:
        print("[architect-agent] Design doc: skipped (--skip-design)", file=sys.stderr)
    else:
        print(f"[architect-agent] Design doc: {design_rel}", file=sys.stderr)
    print("[architect-agent] Running...", file=sys.stderr)

    result, saved, design_path = run_task(
        args.task,
        context,
        output_dir=out_dir,
        diagram_base_name=args.diagram_name,
        skip_design=args.skip_design,
    )
    # Bedrock may emit emoji; Windows cp1252 console cannot print them by default.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(result)
    if saved:
        for path in sorted(saved):
            print(f"[architect-agent] Diagram: {repo_rel(path)}", file=sys.stderr)
    else:
        print(
            f"[architect-agent] WARNING: no PNG diagrams in {repo_rel(out_dir)}.",
            file=sys.stderr,
        )
    if design_path:
        print(f"[architect-agent] Design doc: {repo_rel(design_path)}", file=sys.stderr)
    elif not args.skip_design:
        print("[architect-agent] WARNING: design document was not written.", file=sys.stderr)

if __name__ == "__main__":
    main()