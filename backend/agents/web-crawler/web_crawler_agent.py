"""Web crawler agent — Strands + Bedrock; Firecrawl scrape and optional Postgres persist."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_DIR = _REPO_ROOT / "agents" / "pipeline"
_DEFAULT_SCRAPED_REL = "docs/PRD/scraped"

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.mcp_clients import firecrawl_mcp_client, postgres_mcp_client, postgres_mcp_tool_params
from _shared.artifact_store import is_s3_store, put_artifact, resolve_run_id
from _shared.pipeline_context import (
    TargetAppRequiredError,
    design_doc_rel_for_app,
    enrich_handoff_context,
    read_context_json,
    resolve_design_doc_path,
    resolve_target_app,
    slugify,
    target_app_root_rel,
)

load_repo_env()

from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool
from strands.types.exceptions import MCPClientInitializationError

AGENT_NAME = "web-crawler-agent"
A2A_PORT = 9109

_SCRAPE_KEYWORDS = (
    "web scrap",
    "web-scrap",
    "scrape",
    "scraping",
    "crawl",
    "crawling",
    "fetch url",
    "fetch the url",
    "extract from website",
    "extract from web",
    "pull data from",
    "ingest url",
    "ingest website",
    "competitor page",
    "external spec",
    "api docs url",
    "documentation url",
    "search the web",
    "web search",
    "find online",
    "look up online",
    "research online",
    "discover pages",
    "find documentation",
)

_QUERY_CONTEXT_KEYS = (
    "scrapeQuery",
    "scrape_query",
    "webSearchQuery",
    "web_search_query",
    "searchQuery",
    "search_query",
)

_URL_PATTERN = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

_READ_PREFIXES = (
    _REPO_ROOT / "docs",
    _REPO_ROOT / "agents",
    _REPO_ROOT / "inputs",
)

_WRITE_PREFIXES = (
    _REPO_ROOT / "docs" / "scraped",
    _REPO_ROOT / "docs" / "PRD" / "scraped",
    _REPO_ROOT / "inputs" / "scraped",
)

_written_files: list[str] = []
_run_context: dict[str, Any] | None = None

SCRAPED_CONTENT_DDL = """\
CREATE TABLE IF NOT EXISTS scraped_web_content (
    id BIGSERIAL PRIMARY KEY,
    target_app TEXT,
    source_url TEXT NOT NULL,
    title TEXT,
    content_markdown TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    scrape_method TEXT NOT NULL DEFAULT 'firecrawl',
    correlation_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_url, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_scraped_web_content_target_app
    ON scraped_web_content (target_app);
CREATE INDEX IF NOT EXISTS idx_scraped_web_content_correlation
    ON scraped_web_content (correlation_id);
"""

DEFAULT_PIPELINE_TASK = """\
Run after architect-agent when requirements mention web scraping or external research.

1. Read handoff: prdPath, designDocPath (wc_read_file), architectSummary, productAgentOutput.
2. Derive work from context (any may apply):
   - scrapeUrls / URLs in task → scrape directly
   - scrapeQuery / searchQuery → firecrawl_search first, then scrape top relevant hits
   - requirements text only → read PRD/design, extract URLs and search queries, then search + scrape
3. Discovery workflow (when URL unknown):
   - firecrawl_search with scrapeQuery (limit 5; includeDomains if set)
   - Pick 1–3 best result URLs; firecrawl_scrape each with markdown format
   - Optional: firecrawl_map on a known domain + search term, then scrape
4. Known URL: firecrawl_scrape only. Multi-page section: firecrawl_crawl limit <= 10.
5. Persist via wc_write_markdown and optional Postgres INSERT (see system prompt).
6. Return scraped_urls, search_queries_used, markdown_paths, brief summary for product-agent.

Respect robots/terms; do not scrape authenticated pages unless credentials are in context.\
"""

WEB_CRAWLER_SYS_PROMPT = f"""\
You are the Web Crawler Agent for the SDLC Agentic AI Platform. You run **after architect-agent**
when requirements mention web scraping, URL ingestion, or external documentation extraction.

## Handoff inputs (context JSON)
| Field | Use |
|-------|-----|
| `targetApp` | Slug for output paths and Postgres rows |
| `prdPath` | Read via wc_read_file — **primary source** for scrape/search intent in requirements |
| `designDocPath` | Read via wc_read_file for scrape hints (default `docs/design/<targetApp>.md`) |
| `requirementsPath` | Optional inputs/*.txt or similar — read when PRD lacks URL details |
| `architectSummary` / `productAgentOutput` | Orientation; may contain scrape/search phrases |
| `scrapeUrls` / `scrape_urls` | Explicit URLs — scrape directly (optional) |
| `scrapeQuery` / `searchQuery` | Natural-language web search when URL is unknown |
| `includeDomains` / `excludeDomains` | Pass to firecrawl_search to restrict results |
| `correlationId` | Store on Postgres rows when present |
| `scrapedOutputDir` | Markdown output folder (default `{_DEFAULT_SCRAPED_REL}/<targetApp>`) |
| `postgresMcpParams` | From wc_get_postgres_params — pass to every postgres run_query |

**scrapeUrls is not required.** When requirements say "find competitor pricing" or "research API docs"
without a URL, read prdPath/designDocPath, build a search query, then discover and scrape.

## Firecrawl MCP (required for scraping)
Workflow — pick the first that applies:
1. **Known URL(s)** in task or scrapeUrls → `firecrawl_scrape` (markdown, onlyMainContent).
2. **Known site, unknown page** → `firecrawl_map` with `search`, then scrape best URL.
3. **No URL — open research** → `firecrawl_search` using scrapeQuery or text from PRD/requirements;
   scrape 1–3 top relevant results (do not re-scrape URLs already returned with full content).
4. **Multi-page section explicitly required** → `firecrawl_crawl` with `limit` <= 10; poll status.
- Do not use browser/interact tools unless scrape returns empty JS-rendered content.

## Postgres persistence (when postgres tools are available)
1. Call `wc_get_postgres_params` once; reuse the JSON for all `postgres_run_query` calls.
2. Run this DDL once per session (idempotent):

```sql
{SCRAPED_CONTENT_DDL.strip()}
```

3. INSERT each scraped page:

```sql
INSERT INTO scraped_web_content
  (target_app, source_url, title, content_markdown, content_hash, scrape_method, correlation_id, metadata)
VALUES
  ('<targetApp>', '<url>', '<title>', '<markdown>', '<sha256>', 'firecrawl', '<correlationId>', '{{}}'::jsonb)
ON CONFLICT (source_url, content_hash) DO NOTHING
RETURNING id;
```

Escape single quotes in SQL strings by doubling them (`'` → `''`).
Truncate content_markdown to 500000 chars if needed.

## File output
- When the user message includes Context JSON, call `wc_set_handoff_context` once with that JSON before writing (required for S3 artifact store / runId).
- Write normalized markdown via `wc_write_markdown` under `scrapedOutputDir`.
- Filename pattern: `<slug-from-url>.md` with YAML front matter (url, title, scraped_at).

## Response format (keep concise)
1. **URLs scraped** — list with status (success/skipped/failed)
2. **Markdown files** — repo-relative paths from wc_write_markdown
3. **Postgres** — row ids or "skipped (--with-postgres not enabled / MCP unavailable)"
4. **Handoff** — 3–5 bullet summary for product-agent (facts only; do not create Jira tickets)

## Guardrails
- Never store API keys or credentials in markdown or Postgres metadata.
- Do not scrape pages that require login unless context provides explicit approved credentials.
- Minimize Firecrawl calls: scrape each URL once; prefer map+scrape over crawl.
- Do not modify design docs under docs/design/ or target-apps/ application code.
"""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60].rstrip("-") or "scraped"


def _repo_rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def extract_scrape_queries(context: dict[str, Any] | None) -> list[str]:
    """Collect explicit web-search queries from context for firecrawl_search"""
    ctx = context or {}
    queries: list[str] = []
    for key in _QUERY_CONTEXT_KEYS:
        raw = ctx.get(key)
        if isinstance(raw, str) and raw.strip():
            queries.append(raw.strip())
        elif isinstance(raw, list):
            queries.extend(str(item).strip() for item in raw if str(item).strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(query)
    return deduped


def task_requires_web_scraping(task: str, context: dict[str, Any] | None = None) -> bool:
    """Return True when the task or context indicates web scraping is needed."""
    ctx = context or {}
    if ctx.get("webScrapeRequired") is True or ctx.get("requiresWebScraping") is True:
        return True
    if extract_scrape_queries(ctx):
        return True
    urls = extract_scrape_urls(task, ctx)
    if urls:
        return True
    combined = task.lower()
    for key in (
        "architectSummary",
        "productAgentOutput",
        "designDocPath",
        "prdPath",
        "requirementsPath",
    ):
        value = ctx.get(key)
        if value:
            combined += " " + str(value).lower()
    return any(keyword in combined for keyword in _SCRAPE_KEYWORDS)


def extract_scrape_urls(task: str, context: dict[str, Any] | None = None) -> list[str]:
    """Collect explicit URLs from context and task text."""
    ctx = context or {}
    found: list[str] = []
    for key in ("scrapeUrls", "scrape_urls", "urls", "sourceUrls", "source_urls"):
        raw = ctx.get(key)
        if isinstance(raw, str) and raw.strip():
            found.append(raw.strip())
        elif isinstance(raw, list):
            found.extend(str(item).strip() for item in raw if str(item).strip())
    found.extend(_URL_PATTERN.findall(task))
    deduped: list[str] = []
    seen: set[str] = set()
    for url in found:
        normalized = url.rstrip(".,;)")
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def url_to_filename(url: str) -> str:
    """Derive a safe markdown basename from a URL."""
    parsed = urlparse(url)
    host = _slugify(parsed.netloc or "page")
    path_part = _slugify(parsed.path.strip("/").replace("/", "-") or "index")
    return f"{host}-{path_part}.md"


def content_hash(markdown: str) -> str:
    """SHA-256 hex digest of scraped markdown."""
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def _resolve_repo_path(relative_path: str, *, write: bool) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = (_REPO_ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if not str(candidate).startswith(str(_REPO_ROOT.resolve())):
        raise ValueError(f"path must stay inside repo: {relative_path}")
    if write:
        allowed = any(str(candidate).startswith(str(prefix.resolve())) for prefix in _WRITE_PREFIXES)
        if not allowed:
            raise ValueError("writes only allowed under docs/scraped/, docs/PRD/scraped/, or inputs/scraped/")
        return candidate
    allowed = any(str(candidate).startswith(str(prefix.resolve())) for prefix in _READ_PREFIXES)
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


def _pipeline_context_candidates(target_app: str) -> list[Path]:
    slug = _slugify(target_app)
    env_path = os.getenv("WEB_CRAWLER_CONTEXT_FILE", "").strip()
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    paths.extend([_PIPELINE_DIR / f"{slug}.context.json"])
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _load_pipeline_context(target_app: str) -> dict[str, Any] | None:
    for candidate in _pipeline_context_candidates(target_app):
        path = candidate if candidate.is_absolute() else (_REPO_ROOT / candidate).resolve()
        if not path.is_file():
            continue
        try:
            parsed = read_context_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(parsed, dict):
            parsed.setdefault("_contextFile", _repo_rel(path))
            return parsed
    return None


def _resolve_target_app(name: str | None, context: dict[str, Any] | None) -> str:
    return resolve_target_app(name, context, env_var="WEB_CRAWLER_TARGET_APP")


def _scraped_output_rel(target_app: str, context: dict[str, Any] | None) -> str:
    """Repo-relative scraped output directory (local or S3 artifact prefix)."""
    ctx = context or {}
    raw = str(ctx.get("scrapedOutputDir") or os.getenv("WEB_CRAWLER_OUTPUT_DIR", "")).strip()
    if raw:
        return raw.replace("\\", "/").lstrip("/")
    slug = slugify(target_app)
    if is_s3_store():
        return f"{target_app_root_rel(slug)}/{_DEFAULT_SCRAPED_REL}"
    return f"{_DEFAULT_SCRAPED_REL}/{slug}"


def _artifact_rel_path(path: str, target_app: str) -> str:
    """Map repo-relative write path to run-scoped artifact key suffix."""
    raw = path.strip().replace("\\", "/").lstrip("/")
    slug = slugify(target_app)
    root = target_app_root_rel(slug)
    if raw.startswith(f"{root}/"):
        return raw
    if raw.startswith("docs/") or raw.startswith("inputs/"):
        return f"{root}/{raw}"
    return f"{root}/{raw}"


def _scraped_output_dir(target_app: str, context: dict[str, Any] | None) -> Path:
    rel = _scraped_output_rel(target_app, context)
    if is_s3_store():
        return Path(rel)
    path = (_REPO_ROOT / rel).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_context(
    *,
    target_app: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out_dir = _scraped_output_dir(target_app, extra)
    scraped_rel = _scraped_output_rel(target_app, extra)
    ctx: dict[str, Any] = {
        "targetApp": target_app,
        "designDocPath": design_doc_rel_for_app(target_app),
        "scrapedOutputDir": scraped_rel if is_s3_store() else _repo_rel(out_dir),
        "postgresMcpParams": postgres_mcp_tool_params(),
        "webScrapeRequired": True,
    }
    if extra:
        ctx.update(extra)
    enrich_handoff_context(ctx)
    urls = extract_scrape_urls("", ctx)
    if urls:
        ctx["scrapeUrls"] = urls
    queries = extract_scrape_queries(ctx)
    if queries:
        ctx["scrapeQuery"] = queries[0]
        if len(queries) > 1:
            ctx["scrapeQueries"] = queries
    return ctx


@tool
def wc_read_file(path: str) -> str:
    """Read a file from docs/, agents/, or inputs/."""
    try:
        file_path = _resolve_repo_path(path, write=False)
    except ValueError as exc:
        return f"Error: {exc}"
    if not file_path.is_file():
        return f"Error: not a file: {path}"
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: binary or non-utf8 file: {path}"


@tool
def wc_set_handoff_context(context_json: str) -> str:
    """Bind runId/targetApp from handoff JSON for S3 artifact writes (call once per request)."""
    global _run_context
    try:
        parsed = json.loads(context_json)
    except json.JSONDecodeError as exc:
        return f"Error: invalid JSON: {exc}"
    if not isinstance(parsed, dict):
        return "Error: context must be a JSON object"
    _run_context = parsed
    run_id = resolve_run_id(parsed) or "missing"
    target = parsed.get("targetApp", "n/a")
    return f"Bound handoff context (runId={run_id}, targetApp={target})"


@tool
def wc_write_markdown(path: str, content: str) -> str:
    """Write scraped markdown under docs/PRD/scraped/ (or S3 artifact store when configured)."""
    ctx = _run_context or {}
    target_app = str(ctx.get("targetApp") or os.getenv("WEB_CRAWLER_TARGET_APP", "scraped"))
    run_id = resolve_run_id(ctx)

    if is_s3_store():
        if not run_id:
            return "Error: runId or PIPELINE_RUN_ID required when ARTIFACT_STORE=s3"
        raw = path.strip().replace("\\", "/").lstrip("/")
        if not raw.endswith(".md"):
            return "Error: path must end with .md"
        rel = _artifact_rel_path(raw, target_app)
        stored = put_artifact(run_id, rel, content, content_type="text/markdown; charset=utf-8")
        _written_files.append(stored)
        return f"Wrote s3://{os.getenv('ARTIFACT_S3_BUCKET', '')}/runs/{run_id}/{stored} ({len(content)} bytes)"

    try:
        file_path = _resolve_repo_path(path, write=True)
    except ValueError as exc:
        return f"Error: {exc}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")
    rel = _repo_rel(file_path)
    _written_files.append(rel)
    return f"Wrote {rel} ({len(content)} bytes)"


@tool
def wc_get_postgres_params() -> str:
    """Return JSON connection params for postgres run_query (from POSTGRES_MCP_* env)."""
    return json.dumps(postgres_mcp_tool_params(), indent=2)


@tool
def wc_scraped_content_ddl() -> str:
    """Return idempotent DDL for scraped_web_content table."""
    return SCRAPED_CONTENT_DDL


def _coding_model() -> BedrockModel:
    model_id = os.getenv(
        "CODING_MODEL_ID",
        os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
    )
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        streaming=True,
        max_tokens=8192,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _build_agent(tools: list[Any]) -> Agent:
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description="Scrapes web content via Firecrawl MCP and stores results in Postgres and markdown files.",
        model=_coding_model(),
        system_prompt=WEB_CRAWLER_SYS_PROMPT,
        tools=tools,
    )


def _file_tools() -> list[Any]:
    return [
        wc_read_file,
        wc_set_handoff_context,
        wc_write_markdown,
        wc_get_postgres_params,
        wc_scraped_content_ddl,
    ]


def _firecrawl_mcp_tools(stack: ExitStack) -> list[Any]:
    client = stack.enter_context(firecrawl_mcp_client(cwd=_REPO_ROOT))
    return client.list_tools_sync()


def _postgres_mcp_tools(stack: ExitStack) -> list[Any]:
    client = stack.enter_context(postgres_mcp_client(cwd=_REPO_ROOT))
    return client.list_tools_sync()


def _build_toolset(
    stack: ExitStack,
    *,
    use_firecrawl: bool = True,
    use_postgres: bool = False,
) -> list[Any]:
    tools = _file_tools()
    if use_firecrawl:
        tools.extend(_firecrawl_mcp_tools(stack))
    if use_postgres:
        tools.extend(_postgres_mcp_tools(stack))
    return tools


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    use_firecrawl: bool = True,
    use_postgres: bool = False,
) -> tuple[str, list[str]]:
    global _written_files, _run_context
    _written_files = []

    app = _resolve_target_app(target_app, context)
    ctx = context if context is not None else _build_context(target_app=app)
    _run_context = ctx
    ctx.setdefault("targetApp", app)
    ctx.setdefault("designDocPath", resolve_design_doc_path(ctx))
    ctx.setdefault("postgresMcpParams", postgres_mcp_tool_params())
    out_dir = _scraped_output_dir(app, ctx)
    ctx.setdefault(
        "scrapedOutputDir",
        _scraped_output_rel(app, ctx) if is_s3_store() else _repo_rel(out_dir),
    )
    if is_s3_store() and not resolve_run_id(ctx):
        ctx.setdefault("runId", os.getenv("PIPELINE_RUN_ID", "").strip() or None)
    urls = extract_scrape_urls(task, ctx)
    if urls:
        ctx["scrapeUrls"] = urls
    queries = extract_scrape_queries(ctx)
    if queries and "scrapeQuery" not in ctx:
        ctx["scrapeQuery"] = queries[0]

    if not task_requires_web_scraping(task, ctx):
        return (
            "No web scraping required for this task (no URLs, search queries, or scrape keywords detected). "
            "Set context.webScrapeRequired=true, scrapeQuery, or scrapeUrls to force a run.",
            [],
        )

    try:
        with ExitStack() as stack:
            toolset = _build_toolset(stack, use_firecrawl=use_firecrawl, use_postgres=use_postgres)
            agent = _build_agent(toolset)
            summary = str(agent(_user_message(task, ctx)))
    except MCPClientInitializationError as exc:
        backends: list[str] = []
        if use_firecrawl:
            backends.append("Firecrawl")
        if use_postgres:
            backends.append("Postgres")
        label = " + ".join(backends) if backends else "MCP"
        raise SystemExit(
            f"{label} MCP failed to start.\n"
            "Check FIRECRAWL_API_KEY and POSTGRES_MCP_* env vars.\n"
            f"Details: {exc}"
        ) from exc

    if _written_files:
        written = "\n".join(f"- `{path}`" for path in _written_files)
        summary += f"\n\n## Markdown files written\n{written}\n"
    ctx_handoff = {
        "scrapedMarkdownPaths": list(_written_files),
        "scrapeUrls": ctx.get("scrapeUrls", []),
        "scrapeQuery": ctx.get("scrapeQuery"),
    }
    summary += f"\n\n## Context handoff\n```json\n{json.dumps(ctx_handoff, indent=2)}\n```\n"
    return summary, list(_written_files)


def serve_a2a(
    host: str = "127.0.0.1",
    port: int = A2A_PORT,
    *,
    use_postgres: bool = True,
) -> None:
    skills = [
        AgentSkill(
            id="web_scrape_and_persist",
            name="web_scrape_and_persist",
            description="Scrape URLs via Firecrawl, store markdown and Postgres rows for downstream agents.",
            tags=["web", "scrape", "firecrawl", "postgres", "ingestion"],
        )
    ]
    with ExitStack() as stack:
        tools = _build_toolset(stack, use_firecrawl=True, use_postgres=use_postgres)
        agent = _build_agent(tools)
        A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Web crawler agent - Strands + Firecrawl + Postgres MCP")
    parser.add_argument(
        "--task",
        help="Scrape task or URL list. Default: pipeline task when context provides URLs or scrape intent.",
    )
    parser.add_argument(
        "--target-app",
        help="Target app slug for output paths and Postgres target_app column",
    )
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Do not load agents/pipeline/<target-app>.context.json when --context-file/json omitted",
    )
    parser.add_argument(
        "--no-firecrawl",
        action="store_true",
        help="Skip Firecrawl MCP (file tools only — for testing)",
    )
    parser.add_argument(
        "--with-postgres",
        action="store_true",
        help="Attach AWS Postgres MCP to persist scraped content",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Print whether the task requires scraping and exit (no LLM/MCP run)",
    )
    load_context_extra(parser)
    parser.add_argument("--serve-a2a", action="store_true", help=f"Start A2A server on :{A2A_PORT}")
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port, use_postgres=args.with_postgres)
        return

    extra = parse_context_args(args) or {}
    prelim_app = _resolve_target_app(args.target_app, extra if extra else None)
    if not extra and not args.no_auto_context:
        auto = _load_pipeline_context(prelim_app)
        if auto:
            extra = auto
            print(
                f"[web-crawler-agent] Context (auto): {extra.get('_contextFile', 'pipeline')}",
                file=sys.stderr,
            )

    app = _resolve_target_app(args.target_app, extra if extra else None)
    context = _build_context(target_app=app, extra=extra if extra else None)
    task = args.task or DEFAULT_PIPELINE_TASK

    if args.check_only:
        required = task_requires_web_scraping(task, context)
        urls = extract_scrape_urls(task, context)
        queries = extract_scrape_queries(context)
        print(
            json.dumps(
                {
                    "requiresWebScraping": required,
                    "scrapeUrls": urls,
                    "scrapeQueries": queries,
                    "prdPath": context.get("prdPath"),
                },
                indent=2,
            )
        )
        return

    print(f"[web-crawler-agent] Target app     : {context['targetApp']}", file=sys.stderr)
    print(f"[web-crawler-agent] Output dir     : {context['scrapedOutputDir']}", file=sys.stderr)
    print(f"[web-crawler-agent] Firecrawl MCP  : {not args.no_firecrawl}", file=sys.stderr)
    print(f"[web-crawler-agent] Postgres MCP   : {args.with_postgres}", file=sys.stderr)
    if context.get("scrapeUrls"):
        print(f"[web-crawler-agent] URLs           : {', '.join(context['scrapeUrls'])}", file=sys.stderr)
    print("[web-crawler-agent] Running...", file=sys.stderr)

    result, written = run_task(
        task,
        context,
        target_app=app,
        use_firecrawl=not args.no_firecrawl,
        use_postgres=args.with_postgres,
    )
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(result)
    if written:
        print(f"\n[web-crawler-agent] Wrote {len(written)} markdown file(s):", file=sys.stderr)
        for path in written:
            print(f"  {path}", file=sys.stderr)


if __name__ == "__main__":
    main()