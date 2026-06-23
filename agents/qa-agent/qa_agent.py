"""QA agent — Strands + Bedrock + pytest + Playwright/Postman MCP + A2A.

Runs developer baseline pytest suites, Postman collection runs, optional Playwright
system checks, edge-case tests, and emits a structured handoff for security-agent /
developer-agent. GitHub publish/review is handled by github-agent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TARGET_APPS = _REPO_ROOT / "target-apps"

sys.path.insert(0, str(_REPO_ROOT / "agents"))
from _shared.context_cli import load_context_extra, parse_context_args
from _shared.env import load_repo_env
from _shared.mcp_clients import MCP_FACTORIES, postman_api_key
from _shared.pipeline_context import (
    TargetAppRequiredError,
    enrich_handoff_context,
    resolve_cli_context,
    resolve_design_doc_path,
    resolve_target_app,
    slugify,
)

load_repo_env()
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")

import botocore.config
from a2a.types import AgentSkill
from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig
from strands.multiagent.a2a import A2AServer
from strands.tools.decorator import tool

AGENT_NAME = "qa-agent"
A2A_PORT = 9104

DEFAULT_PIPELINE_TASK = """\
Run SDLC-style quality assurance on targetApp using developer handoff artifacts in Context.

**Phase 1 — test planning (requirements → test strategy)**
1a. qa_list_tree(targetApp) — inventory app/, tests/, OpenAPI/spec files.
1b. qa_read_file(prdPath) when set — extract acceptance criteria and NFRs.
1c. qa_read_file(designDocPath) — §4 API surface (every route), §5 auth/error rules.
1d. qa_read_file(developerHandoffPath) when set — testCommand, runCommand, writtenFiles.
1e. Write TEST_PLAN.md mapping criteria → test types (unit, API integration, system/E2E).
    Prioritize: P0 smoke routes, P1 auth/validation edges, P2 pagination/bounds.

**Phase 2 — unit & component tests (pytest)**
2a. qa_run_pytest(targetApp) — developer baseline (default: pytest tests/ -q).
2b. On failure: classify each as app_bug | test_bug | env_issue; fix test_bug only under tests/.
2c. Re-run until pass or only app_bug remain (document app_bug — do not edit app/).

**Phase 3 — API integration (Postman MCP, when available)**
3a. If Postman MCP tools are loaded and apiBaseUrl is reachable:
    - searchPostmanElements or getCollections for an existing collection for targetApp.
    - If none: createCollection from design §4 routes (or sync from OpenAPI if present).
    - runCollection against apiBaseUrl with test API keys from conftest (never real secrets).
3b. If Postman MCP unavailable or apiBaseUrl not running: note skipped in report.

**Phase 4 — system / E2E (Playwright MCP, when UI exists)**
4a. If design/README mentions Streamlit, frontend URL, or uiBaseUrl in Context:
    - Use Playwright MCP (browser_navigate, browser_snapshot, browser_click, etc.).
    - Walk critical user journeys from PRD acceptance criteria.
4b. API-only services: skip Playwright with explicit "API-only — E2E N/A".

**Phase 5 — gap closure & coverage**
5a. Compare PRD + design §4/§5 against all executed tests.
5b. Add minimal edge-case pytest in tests/test_qa_<domain>.py (auth 401/403, 404, 422).
5c. qa_run_coverage(targetApp) when pytest-cov is installed; note untested routes.

**Phase 6 — report and handoff (LAST)**
Reply with exactly these sections in order:
1. **status** — pass | fail
2. **test_plan** — path to TEST_PLAN.md and priority summary
3. **baseline_summary** — pytest: run, passed, failed, exit code
4. **postman_summary** — collection run result or skipped reason
5. **playwright_summary** — E2E result or skipped reason
6. **failed_tests** — list with classification and one-line reason each
7. **coverage_gaps** — acceptance criteria or routes still untested
8. **new_tests_written** — paths under tests/ or QA artifacts
9. **recommendations** — ordered fixes for developer-agent
10. **commands** — reproduce: pytest, coverage, runCommand, Postman/Playwright notes
11. **handoff_json** — fenced ```json with keys:
    targetApp, status, testsRun, testsPassed, testsFailed, failedTests, newTestsWritten,
    testCommand, coverageCommand, postmanSummary, playwrightSummary, recommendations,
    jiraKey (or null).

Do not write outside target-apps/<service>/tests/, TEST_PLAN.md, or QA_REPORT.md.
Do not modify app/ unless the user task explicitly says to fix app bugs.
GitHub/GitLab PR actions are owned by github-agent — do not post PR reviews.
"""

_READ_PREFIXES = (
    _TARGET_APPS,
    _REPO_ROOT / "docs",
    _REPO_ROOT / "agents",
    _REPO_ROOT / "inputs",
)

_written_files: list[str] = []
_last_pytest_result: dict[str, Any] | None = None

QA_SYS_PROMPT = """\
You are the QA Agent for the Autonomous SDLC platform. You run **after developer-agent**
as the sixth pipeline step: product → architect → web-crawler → database → developer → **YOU**
→ security-agent.

You behave like a human QA engineer across SDLC test phases: plan from requirements,
execute unit/API/system tests, analyze coverage gaps, and produce actionable reports.
You do NOT publish to GitHub or post PR reviews (github-agent owns that).

## Test phases (execute in order)

| Phase | Activity | Primary tools |
|-------|----------|---------------|
| 1 Planning | Map PRD/design to test cases; write TEST_PLAN.md | qa_read_file, qa_write_file |
| 2 Unit/component | Developer baseline + edge pytest | qa_run_pytest, qa_run_coverage |
| 3 API integration | Postman collection create/run | Postman MCP (runCollection, createCollection*) |
| 4 System/E2E | Browser journeys when UI exists | Playwright MCP (browser_*) |
| 5 Report | QA_REPORT.md + handoff_json | qa_write_file |

## Scope

- **In scope:** pytest (FastAPI TestClient), Postman collection runs, Playwright UI smoke,
  TEST_PLAN.md, QA_REPORT.md, structured handoff.
- **Keep developer baseline:** conftest.py, test_health.py, route smoke tests — never delete.
- **Out of scope:** GitHub/GitLab PR actions, load/perf testing, live AWS integration in CI.

## Inputs — read ALL that are present before testing

| Context key | Read how | What it contains |
|-------------|----------|-----------------|
| `targetApp` | Context JSON | Service folder under target-apps/ |
| `testCommand` | Context / developer handoff | pytest command |
| `runCommand` | Context | uvicorn/streamlit start (for live API/UI checks) |
| `apiBaseUrl` | Context (default http://localhost:8000) | Postman collection target |
| `uiBaseUrl` | Context when set | Playwright navigation base |
| `prdPath` | qa_read_file | Acceptance criteria, NFRs |
| `designDocPath` | qa_read_file | §4 routes, §5 auth/error rules |
| `developerHandoffPath` | qa_read_file | Developer handoff JSON |
| `postmanWorkspaceId` | Context when set | Prefer this workspace for collections |

## Built-in tools

| Tool | Purpose |
|------|---------|
| qa_list_tree | Inventory target-apps/<service>/ |
| qa_read_file | Read PRD, design, tests, app code |
| qa_run_pytest | Execute pytest suite |
| qa_run_coverage | Coverage when pytest-cov installed |
| qa_write_file | Write tests/, TEST_PLAN.md, QA_REPORT.md only |

## Postman MCP (when loaded)

Use for API integration testing beyond in-process TestClient:
- `searchPostmanElements` / `getCollections` — find existing collection
- `createCollection` + `createCollectionRequest` — build from design §4 if missing
- `createEnvironment` — variables: baseUrl, apiKey (use test-key, never real secrets)
- `runCollection` — execute against apiBaseUrl; capture pass/fail per request

Skip Postman phase gracefully when MCP unavailable or API not reachable.

## Playwright MCP (when loaded)

Use for system/E2E when PRD/design mentions UI, Streamlit, or uiBaseUrl is set:
- `browser_navigate` → `browser_snapshot` → interact (click, type, fill_form)
- Verify acceptance-criteria journeys; capture console errors via browser_console_messages
- Close browser when done (browser_close)

Skip Playwright for API-only FastAPI services.

## Failure handling (pytest)

Classify: app_bug | test_bug | env_issue.
- test_bug → fix under tests/ only, re-run
- app_bug → document + recommend to developer-agent; never edit app/
- env_issue → document setup steps; status fail

## Developer vs QA ownership

| Owner | Responsibility |
|-------|----------------|
| developer-agent | Baseline tests/ per §4 routes |
| You (qa-agent) | Plan, run all test phases, edge cases, reports, handoff |
| github-agent | Publish branch/PR — not your job |
| security-agent | SAST/secrets scan — runs after you |

## Security guardrails

- Never hardcode real API keys in tests or Postman env — use test-key / conftest fixtures.
- Never create or modify `.env`.
- Write ONLY under tests/, TEST_PLAN.md, QA_REPORT.md.

## Response format

Always end with **handoff_json** (fenced ```json) for orchestrator and downstream agents.
"""


def _resolve_repo_path(relative_path: str, *, write: bool) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path is required")
    candidate = (
        (_REPO_ROOT / raw).resolve()
        if not Path(raw).is_absolute()
        else Path(raw).resolve()
    )
    if not str(candidate).startswith(str(_REPO_ROOT.resolve())):
        raise ValueError(f"path must stay inside repo: {relative_path}")
    if write:
        if not str(candidate).startswith(str(_TARGET_APPS.resolve())):
            raise ValueError("writes only allowed under target-apps/")
        return candidate
    allowed = (
        any(str(candidate).startswith(str(p.resolve())) for p in _READ_PREFIXES)
        or candidate == _REPO_ROOT.resolve()
    )
    if not allowed:
        raise ValueError(f"read not allowed for path: {relative_path}")
    return candidate


def _service_dir(service: str) -> Path:
    return _TARGET_APPS / slugify(service)


def _ensure_service_exists(service: str) -> Path:
    dest = _service_dir(service)
    if not dest.is_dir():
        raise ValueError(f"service not found: target-apps/{slugify(service)}/")
    return dest


def _allowed_write_path(file_path: Path, service: str) -> bool:
    """Writes limited to tests/ and QA_REPORT.md under the service directory."""
    root = _service_dir(service).resolve()
    rel = file_path.resolve()
    if not str(rel).startswith(str(root)):
        return False
    rel_to_service = rel.relative_to(root)
    parts = rel_to_service.parts
    if rel_to_service.as_posix() in ("QA_REPORT.md", "TEST_PLAN.md"):
        return True
    if parts and parts[0] == "tests":
        return True
    return False


def _parse_pytest_output(output: str) -> dict[str, Any]:
    """Extract summary counts and FAILED lines from pytest stdout/stderr."""
    failed_tests: list[dict[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED "):
            test_id = stripped.removeprefix("FAILED ").split(" - ")[0]
            failed_tests.append({"id": test_id, "raw": stripped})
        elif " FAILED" in stripped and "::" in stripped:
            test_id = stripped.split(" FAILED")[0].strip()
            failed_tests.append({"id": test_id, "raw": stripped})

    summary_match = re.search(
        r"(?P<failed>\d+) failed(?:, (?P<passed>\d+) passed)?|"
        r"(?P<passed_only>\d+) passed",
        output,
    )
    passed = 0
    failed = 0
    if summary_match:
        if summary_match.group("passed_only"):
            passed = int(summary_match.group("passed_only"))
        if summary_match.group("passed"):
            passed = int(summary_match.group("passed"))
        if summary_match.group("failed"):
            failed = int(summary_match.group("failed"))

    errors_match = re.search(r"(?P<errors>\d+) error", output)
    errors = int(errors_match.group("errors")) if errors_match else 0

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "failedTests": failed_tests,
        "rawTail": output[-4000:] if len(output) > 4000 else output,
    }


def _default_test_command(service: str) -> str:
    return f"cd target-apps/{slugify(service)} && pytest tests/ -q"


def _default_coverage_command(service: str) -> str:
    return (
        f"cd target-apps/{slugify(service)} && "
        "pytest tests/ --cov=app --cov-report=term-missing -q"
    )


def _pytest_python(service_dir: Path) -> str:
    """Prefer the service venv interpreter when present."""
    if os.name == "nt":
        venv_py = service_dir / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = service_dir / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


@tool
def qa_list_tree(service: str, subpath: str = "") -> str:
    """List files under target-apps/<service>/ (optionally under subpath)."""
    try:
        root = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"
    base = (root / subpath).resolve()
    if not str(base).startswith(str(root.resolve())):
        return "Error: subpath escapes service directory"
    if not base.exists():
        return f"Error: not found: {base.relative_to(_REPO_ROOT).as_posix()}"
    lines: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and ".venv" not in path.parts:
            lines.append(path.relative_to(_REPO_ROOT).as_posix())
    return "\n".join(lines) if lines else "(no files)"


@tool
def qa_read_file(path: str) -> str:
    """Read a repo file. Allowed: target-apps/, docs/, agents/, inputs/."""
    try:
        file_path = _resolve_repo_path(path, write=False)
    except ValueError as exc:
        return f"Error: {exc}"
    if not file_path.is_file():
        return f"Error: not a file: {path}"
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: binary or non-utf8 file: {path}"
    if len(text) > 120_000:
        return text[:120_000] + "\n\n... (truncated)"
    return text


@tool
def qa_write_file(path: str, content: str) -> str:
    """Write a file under target-apps/<service>/tests/, TEST_PLAN.md, or QA_REPORT.md only."""
    try:
        file_path = _resolve_repo_path(path, write=True)
    except ValueError as exc:
        return f"Error: {exc}"

    service = None
    try:
        rel = file_path.relative_to(_TARGET_APPS.resolve())
        service = rel.parts[0] if rel.parts else None
    except ValueError:
        return "Error: path must be under target-apps/<service>/"

    if not service or not _allowed_write_path(file_path, service):
        return (
            "Error: writes only allowed under target-apps/<service>/tests/, "
            "TEST_PLAN.md, or QA_REPORT.md"
        )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8", newline="\n")
    rel_path = file_path.relative_to(_REPO_ROOT).as_posix()
    _written_files.append(rel_path)
    return f"Wrote {rel_path} ({len(content)} bytes)"


def _run_pytest_impl(service: str, pytest_args: str) -> str:
    """Execute pytest and format results (shared by qa_run_pytest and qa_run_coverage)."""
    global _last_pytest_result
    try:
        service_dir = _ensure_service_exists(service)
    except ValueError as exc:
        return f"Error: {exc}"

    tests_dir = service_dir / "tests"
    if not tests_dir.is_dir():
        return f"Error: no tests/ directory under target-apps/{slugify(service)}/"

    cmd = [_pytest_python(service_dir), "-m", "pytest", *pytest_args.split()]
    try:
        completed = subprocess.run(
            cmd,
            cwd=service_dir,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("QA_PYTEST_TIMEOUT", "300")),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "Error: pytest timed out (QA_PYTEST_TIMEOUT seconds)"

    combined = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    parsed = _parse_pytest_output(combined)
    parsed["exitCode"] = completed.returncode
    parsed["command"] = " ".join(cmd)
    parsed["cwd"] = service_dir.relative_to(_REPO_ROOT).as_posix()
    _last_pytest_result = parsed

    status = "PASS" if completed.returncode == 0 else "FAIL"
    failed_lines = "\n".join(f["raw"] for f in parsed["failedTests"][:20])
    body = (
        f"status={status}\n"
        f"exit_code={completed.returncode}\n"
        f"passed={parsed['passed']} failed={parsed['failed']} errors={parsed['errors']}\n"
        f"command: {' '.join(cmd)}\n"
        f"cwd: {parsed['cwd']}\n"
    )
    if failed_lines:
        body += f"\nfailed_tests:\n{failed_lines}\n"
    body += f"\n--- output (tail) ---\n{parsed['rawTail']}"
    return body


@tool
def qa_run_pytest(service: str, pytest_args: str = "tests/ -q") -> str:
    """Run pytest in target-apps/<service>/ and return exit code plus parsed results.

    pytest_args: arguments after pytest (default: tests/ -q).
    """
    return _run_pytest_impl(service, pytest_args)


@tool
def qa_run_coverage(service: str, pytest_args: str = "tests/ --cov=app --cov-report=term-missing -q") -> str:
    """Run pytest with coverage in target-apps/<service>/ (requires pytest-cov)."""
    return _run_pytest_impl(service, pytest_args)


def _max_output_tokens() -> int:
    return int(os.getenv("QA_AGENT_MAX_TOKENS", "16384"))


class _QACallbackHandler:
    """Stream tool progress to stderr."""

    def __init__(self) -> None:
        self.tool_count = 0

    def __call__(self, **kwargs: Any) -> None:
        tool_use = (
            kwargs.get("event", {})
            .get("contentBlockStart", {})
            .get("start", {})
            .get("toolUse")
        )
        if tool_use:
            self.tool_count += 1
            print(
                f"\n[qa-agent] Tool #{self.tool_count}: {tool_use['name']}",
                file=sys.stderr,
            )


def _qa_model() -> BedrockModel:
    model_id = os.getenv(
        "QA_MODEL_ID",
        os.getenv("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
    )
    read_timeout = int(os.getenv("BEDROCK_READ_TIMEOUT", "600"))
    return BedrockModel(
        model_id=model_id,
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        max_tokens=_max_output_tokens(),
        streaming=True,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
        boto_client_config=botocore.config.Config(
            read_timeout=read_timeout,
            connect_timeout=10,
            retries={"mode": "standard", "max_attempts": 2},
        ),
    )


def _qa_mcp_enabled(name: str) -> bool:
    """Return True when an optional QA MCP server should be loaded."""
    env_key = f"QA_ENABLE_{name.upper()}_MCP"
    if os.getenv(env_key, "1").strip().lower() in {"0", "false", "no"}:
        return False
    if name == "postman":
        try:
            postman_api_key()
        except ValueError:
            return False
    return name in MCP_FACTORIES


def _qa_mcp_servers() -> list[str]:
    """Resolve optional MCP servers for QA (Playwright, Postman)."""
    return [name for name in ("playwright", "postman") if _qa_mcp_enabled(name)]


def _load_optional_mcp_tools(mcp_names: list[str]) -> tuple[list[Any], ExitStack]:
    """Load MCP tools; skip servers that fail to start (fail-open)."""
    stack: ExitStack = ExitStack()
    tools: list[Any] = []
    for name in mcp_names:
        if name not in MCP_FACTORIES:
            print(f"[qa-agent] Unknown MCP: {name}", file=sys.stderr)
            continue
        try:
            client = MCP_FACTORIES[name]()
            stack.enter_context(client)
            loaded = client.list_tools_sync()
            tools.extend(loaded)
            print(f"[qa-agent] Loaded MCP: {name} ({len(loaded)} tools)", file=sys.stderr)
        except Exception as exc:
            print(f"[qa-agent] MCP {name} unavailable: {exc}", file=sys.stderr)
    return tools, stack


def _build_agent(*, extra_tools: list[Any] | None = None) -> Agent:
    tools: list[Any] = [
        qa_list_tree,
        qa_read_file,
        qa_write_file,
        qa_run_pytest,
        qa_run_coverage,
    ]
    if extra_tools:
        tools.extend(extra_tools)
    return Agent(
        agent_id=AGENT_NAME,
        name=AGENT_NAME,
        description=(
            "SDLC QA: test planning, pytest, Postman API runs, Playwright E2E, "
            "coverage gaps, and structured handoff."
        ),
        model=_qa_model(),
        system_prompt=QA_SYS_PROMPT,
        tools=tools,
        callback_handler=_QACallbackHandler(),
    )


def _user_message(task: str, context: dict[str, Any] | None) -> str:
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


def _enrich_qa_context(ctx: dict[str, Any]) -> None:
    """Add QA-specific paths and default commands."""
    app = slugify(str(ctx["targetApp"]))
    service_dir = _REPO_ROOT / "target-apps" / app

    ctx.setdefault("targetAppDir", service_dir.relative_to(_REPO_ROOT).as_posix())
    ctx.setdefault("testCommand", _default_test_command(app))
    ctx.setdefault("coverageCommand", _default_coverage_command(app))
    ctx.setdefault("apiBaseUrl", os.getenv("QA_API_BASE_URL", "http://localhost:8000"))
    ctx.setdefault(
        "runCommand",
        f"cd target-apps/{app} && uvicorn app.main:app --reload --port 8000",
    )
    if os.getenv("POSTMAN_WORKSPACE_ID", "").strip():
        ctx.setdefault("postmanWorkspaceId", os.getenv("POSTMAN_WORKSPACE_ID", "").strip())

    if not ctx.get("developerHandoffPath"):
        for candidate in (
            service_dir / "DEVELOPER_HANDOFF.json",
            _REPO_ROOT / "agents" / "pipeline" / f"{app}.developer-handoff.json",
        ):
            if candidate.is_file():
                ctx["developerHandoffPath"] = candidate.relative_to(_REPO_ROOT).as_posix()
                break

    handoff_path = ctx.get("developerHandoffPath")
    if handoff_path and not ctx.get("writtenFiles"):
        try:
            handoff_file = _resolve_repo_path(str(handoff_path), write=False)
            if handoff_file.is_file():
                handoff_data = json.loads(handoff_file.read_text(encoding="utf-8"))
                if isinstance(handoff_data, dict):
                    ctx.setdefault("writtenFiles", handoff_data.get("writtenFiles"))
                    ctx.setdefault("testCommand", handoff_data.get("testCommand", ctx["testCommand"]))
                    ctx.setdefault("runCommand", handoff_data.get("runCommand", ctx["runCommand"]))
        except (json.JSONDecodeError, ValueError, OSError):
            pass


def _build_context(
    *,
    target_app: str,
    jira_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    service_path = _ensure_service_exists(target_app)
    ctx: dict[str, Any] = {
        "targetApp": target_app,
        "targetAppDir": service_path.relative_to(_REPO_ROOT).as_posix(),
    }
    if jira_key:
        ctx["jiraKey"] = jira_key
    if extra:
        ctx.update(extra)
    enrich_handoff_context(ctx, include_db_paths=False)
    _enrich_qa_context(ctx)
    return ctx


def run_task(
    task: str,
    context: dict[str, Any] | None = None,
    *,
    target_app: str | None = None,
    jira_key: str | None = None,
) -> tuple[str, list[str]]:
    global _written_files, _last_pytest_result
    _written_files = []
    _last_pytest_result = None

    app = resolve_target_app(target_app, context, env_var="QA_TARGET_APP")
    ctx = context if context is not None else _build_context(target_app=app, jira_key=jira_key)
    ctx.setdefault("targetApp", app)
    enrich_handoff_context(ctx, include_db_paths=False)
    _enrich_qa_context(ctx)
    if jira_key:
        ctx.setdefault("jiraKey", jira_key)

    mcp_names = _qa_mcp_servers()
    if mcp_names:
        mcp_tools, stack = _load_optional_mcp_tools(mcp_names)
        agent = _build_agent(extra_tools=mcp_tools)
        with stack:
            summary = str(agent(_user_message(task, ctx)))
    else:
        agent = _build_agent()
        summary = str(agent(_user_message(task, ctx)))

    if _written_files:
        files_block = "\n".join(f"- `{p}`" for p in _written_files)
        summary += f"\n\n## Files written\n{files_block}\n"

    pytest_snapshot = _last_pytest_result or {}
    handoff = {
        "targetApp": app,
        "status": "pass" if pytest_snapshot.get("exitCode") == 0 else "fail",
        "testsRun": pytest_snapshot.get("passed", 0) + pytest_snapshot.get("failed", 0),
        "testsPassed": pytest_snapshot.get("passed", 0),
        "testsFailed": pytest_snapshot.get("failed", 0),
        "failedTests": pytest_snapshot.get("failedTests", []),
        "newTestsWritten": list(_written_files),
        "testCommand": ctx.get("testCommand", _default_test_command(app)),
        "coverageCommand": ctx.get("coverageCommand", _default_coverage_command(app)),
        "jiraKey": ctx.get("jiraKey"),
        "designDocPath": ctx.get("designDocPath"),
        "prdPath": ctx.get("prdPath"),
    }
    handoff_path = _REPO_ROOT / "agents" / "pipeline" / f"{slugify(app)}.qa-handoff.json"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    summary += f"\n\n## QA handoff\nSaved: `{handoff_path.relative_to(_REPO_ROOT).as_posix()}`\n```json\n{json.dumps(handoff, indent=2)}\n```\n"

    return summary, list(_written_files)


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
    skills = [
        AgentSkill(
            id="run_qa_suite",
            name="run_qa_suite",
            description=(
                "SDLC QA: test plan, pytest, Postman API integration, Playwright E2E, "
                "and structured handoff."
            ),
            tags=["qa", "pytest", "testing", "api", "postman", "playwright"],
        )
    ]
    agent = _build_agent()
    A2AServer(agent, host=host, port=port, skills=skills).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="QA agent — Strands + pytest tools + A2A")
    parser.add_argument(
        "--task",
        help="Optional task override. Default: full pipeline QA task.",
    )
    parser.add_argument(
        "--target-app",
        help="Service folder under target-apps/ (from --target-app, context targetApp, or PIPELINE_TARGET_APP)",
    )
    parser.add_argument(
        "--no-auto-context",
        action="store_true",
        help="Do not load agents/pipeline/<target-app>.context.json automatically.",
    )
    parser.add_argument("--jira-key", help="Jira issue key for traceability")
    load_context_extra(parser)
    parser.add_argument(
        "--serve-a2a",
        action="store_true",
        help=f"Start A2A server on :{A2A_PORT}",
    )
    parser.add_argument("--port", type=int, default=A2A_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if args.serve_a2a:
        serve_a2a(host=args.host, port=args.port)
        return

    if not args.task:
        args.task = DEFAULT_PIPELINE_TASK

    try:
        extra, target = resolve_cli_context(
            args.target_app,
            parse_context_args(args),
            no_auto_context=args.no_auto_context,
            env_var="QA_TARGET_APP",
        )
    except TargetAppRequiredError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if extra.get("_contextFile"):
        print(f"[qa-agent] Context (auto): {extra['_contextFile']}", file=sys.stderr)

    enrich_handoff_context(extra, include_db_paths=False)
    _enrich_qa_context(extra)

    ctx = _build_context(target_app=target, jira_key=args.jira_key, extra=extra or None)

    print(f"[qa-agent] Target app  : {ctx['targetAppDir']}", file=sys.stderr)
    print(f"[qa-agent] Design doc  : {resolve_design_doc_path(ctx)}", file=sys.stderr)
    print(f"[qa-agent] Test command: {ctx.get('testCommand')}", file=sys.stderr)
    mcp_servers = _qa_mcp_servers()
    print(
        f"[qa-agent] MCP servers : {', '.join(mcp_servers) if mcp_servers else '(none — pytest only)'}",
        file=sys.stderr,
    )
    print("[qa-agent] Running...", file=sys.stderr)

    result, written = run_task(
        args.task,
        ctx,
        target_app=target,
        jira_key=args.jira_key,
    )
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(result)
    if written:
        print(f"\n[qa-agent] Wrote {len(written)} file(s):", file=sys.stderr)
        for path in written:
            print(f"  {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
