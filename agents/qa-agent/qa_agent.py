"""QA agent — Strands + Bedrock + scoped test tools + A2A.

Runs developer baseline pytest suites under target-apps/<service>/, reports failures,
adds edge-case tests, and emits a structured handoff for devops-agent / developer-agent.
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
from _shared.mcp_clients import MCP_FACTORIES, github_personal_access_token
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
Run quality assurance on targetApp using developer handoff artifacts in Context.

**Step 1 — orient (read before running tests)**
1a. qa_list_tree(targetApp) — inventory app/ and tests/; note existing developer baseline files
    (conftest.py, test_health.py, test_*.py). **Never delete** developer baseline tests.
1b. qa_read_file(prdPath) when set — acceptance criteria and NFRs to map coverage gaps.
1c. qa_read_file(designDocPath) — §4 API surface (every route), §5 auth/error rules.
1d. If developerHandoffPath or handoff_json fields are in Context, use testCommand from there.

**Step 2 — run developer baseline suite**
2a. qa_run_pytest(targetApp) — runs the baseline command (default: pytest tests/ -q).
2b. If exit code ≠ 0, proceed to Step 3 (failure handling). If all pass, proceed to Step 4.

**Step 3 — failure handling (when tests fail)**
3a. Parse failed test names and assertion messages from qa_run_pytest output.
3b. Classify each failure:
    - **app_bug** — implementation wrong vs design §4/§5 or PRD acceptance criteria.
    - **test_bug** — test expectation wrong, fixture issue, or stale test after intentional API change.
    - **env_issue** — missing dependency, wrong Python path, import error before tests run.
3c. For **test_bug** only: fix tests under tests/ via qa_write_file (never change app/ for app_bug).
3d. For **app_bug**: document in the report with route, expected vs actual, and file hint for developer-agent.
    Do NOT rewrite application code — hand off to developer-agent.
3e. Re-run qa_run_pytest after any test fixes you made.

**Step 4 — gap analysis and new tests (only when baseline passes or after test_bug fixes)**
4a. Compare PRD acceptance criteria + design §4/§5 against existing tests.
4b. Add **minimal** edge-case tests the developer skipped (auth 401/403, 404, 422, pagination bounds).
4c. Prefer new file tests/test_qa_<domain>.py — do not bloat or duplicate developer baseline files.
4d. Re-run qa_run_pytest; optionally qa_run_coverage(targetApp) when pytest-cov is installed.

**Step 5 — report and handoff (LAST)**
Reply with exactly these sections in order:
1. **status** — pass | fail
2. **baseline_summary** — tests run, passed, failed, exit code
3. **failed_tests** — list with classification (app_bug | test_bug | env_issue) and one-line reason each
4. **coverage_gaps** — acceptance criteria or routes still untested (bullets)
5. **new_tests_written** — paths added or modified under tests/
6. **recommendations** — ordered fixes for developer-agent if app_bug failures remain
7. **commands** — exact shell commands to reproduce (test, verbose, stop-on-first, coverage)
8. **handoff_json** — fenced ```json block with keys:
   targetApp, status, testsRun, testsPassed, testsFailed, failedTests, newTestsWritten,
   testCommand, coverageCommand, recommendations, jiraKey (or null).
   This block is consumed by devops-agent and orchestrator-agent.

Do not write outside target-apps/<service>/tests/ or QA_REPORT.md.
Do not modify app/ source unless the user task explicitly says to fix app bugs.
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
as the sixth pipeline step: product → architect → web-crawler → database → developer → **YOU**.

Your job is to **verify** working backend APIs under `target-apps/<service>/` by running pytest,
reporting failures clearly, and adding **minimal** edge-case tests the developer did not cover.
You do NOT redesign architecture or rewrite application code unless fixing a test-only bug.

## MVP scope (current platform default)

- **In scope:** API pytest via FastAPI `TestClient` under `target-apps/<service>/tests/`.
- **Keep developer baseline:** `conftest.py`, `test_health.py`, `test_projects.py`, `test_tasks.py`
  (or equivalent) are **required** — run them, extend them only when fixing test_bug, never delete.
- **Out of scope (Phase 2):** browser/UI tests, load testing, live AWS/Bedrock integration in CI.

## Inputs — read ALL that are present before running tests

| Context key | Read how | What it contains |
|-------------|----------|-----------------|
| `targetApp` | Context JSON | Service folder name under target-apps/ |
| `testCommand` | Context JSON / developer handoff | e.g. `pytest tests/ -q` from service dir |
| `runCommand` | Context JSON | uvicorn start command (smoke reference only) |
| `prdPath` | `qa_read_file` | Acceptance criteria, NFRs |
| `designDocPath` | `qa_read_file` | §4 routes, §5 auth/error rules |
| `developerHandoffPath` | `qa_read_file` | Developer handoff JSON or summary |
| `writtenFiles` | Context JSON | Files developer created — orient coverage |

## Tools — use in this order

| Tool | Purpose |
|------|---------|
| `qa_list_tree` | List files under target-apps/<service>/ |
| `qa_read_file` | Read PRD, design, tests, app code (read-only) |
| `qa_run_pytest` | Execute baseline suite; returns exit code + failure details |
| `qa_run_coverage` | Optional coverage report when pytest-cov installed |
| `qa_write_file` | Write **only** under `tests/` or `QA_REPORT.md` |

## Test commands (document these in every report)

From repo root (PowerShell or bash):

```bash
cd target-apps/<service>
pytest tests/ -q                    # baseline (developer handoff default)
pytest tests/ -v                    # verbose — see each test name
pytest tests/ --tb=short            # short tracebacks on failure
pytest tests/ -x                    # stop on first failure (debug)
pytest tests/ -k "auth"             # run tests matching keyword
pytest tests/ --cov=app --cov-report=term-missing   # coverage (if pytest-cov installed)
```

Windows one-liner from repo root:
`cd target-apps\\<service>; pytest tests/ -q`

## When tests fail — mandatory workflow

1. **Run** `qa_run_pytest` and capture full output.
2. **Classify** each failure:
   - `app_bug` — handler returns wrong status/body vs design §4; auth missing; validation wrong.
   - `test_bug` — wrong header in test, stale assertion, fixture not resetting store.
   - `env_issue` — ModuleNotFoundError, missing requirements.txt install, wrong cwd.
3. **Act by classification:**
   - `test_bug` → fix via `qa_write_file` under `tests/` only, then re-run.
   - `app_bug` → document route, expected, actual; add `recommendations` for developer-agent; **do not edit app/**.
   - `env_issue` → document missing step (e.g. `pip install -r requirements.txt`); set status `fail`.
4. **Re-run** baseline after any test file changes until pass or only app_bug remain.
5. If only `app_bug` remain: status = `fail`, hand off to developer-agent with actionable list.

## When tests pass — gap analysis

- Map every design §4 route to at least one test (developer may have done this — verify).
- Add edge cases developer skipped: empty name 422, wrong API key 403, pagination limit max, 404 paths.
- Prefer `tests/test_qa_<area>.py` for **your** additions — keep developer files stable.
- One behavior per test; AAA pattern; no conditional asserts.

## Developer vs QA ownership

| Owner | Responsibility |
|-------|----------------|
| **developer-agent** | Baseline `tests/` — smoke per §4 route; suite must pass at handoff |
| **You (qa-agent)** | Run suite, report failures, add edge cases, optional coverage, QA_REPORT.md |

## Security guardrails

- Never hardcode real API keys, passwords, or tokens in tests — use `test-key` / fixtures like conftest.
- Never create or modify `.env` — tests set env via conftest or monkeypatch.
- Write ONLY under `target-apps/<service>/tests/` and `QA_REPORT.md` via `qa_write_file`.
- Read `app/` via `qa_read_file` to diagnose failures — do not modify app/ unless task overrides.

## GitHub PR review (when devops-agent opened a PR)

When `pullRequestNumber`, `githubOwner`, and `githubRepo` are in Context (from devops-handoff):
1. Complete Steps 1–5 (local pytest on the same checkout — mirrors QA testing a dev branch).
2. Post results on the PR using GitHub MCP `pull_request_review_write`:
   - method: `create`
   - event: `COMMENT` if all tests pass; `REQUEST_CHANGES` if app_bug failures remain
   - body: markdown summary with baseline_summary, failed_tests, new_tests_written, commands
3. If GitHub MCP is unavailable, skip silently and keep handoff_json only.

Legacy GitLab: when `mergeRequestIid` and `gitlabProject` are in Context (from gitlab-handoff),
the agent posts a QA summary comment on the MR automatically after pytest (gitlab_mr_note_create).
You do not need to call GitLab MCP tools manually for that case.

## Response format

Always end with **handoff_json** (fenced ```json) for orchestrator and devops-agent.
Keep prose concise; put failure details in structured `failedTests` array.
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
    if rel_to_service.as_posix() == "QA_REPORT.md":
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
    """Write a file under target-apps/<service>/tests/ or QA_REPORT.md only."""
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
            "Error: writes only allowed under target-apps/<service>/tests/ "
            "or target-apps/<service>/QA_REPORT.md"
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


def _load_mcp_tools(mcp_names: list[str]) -> tuple[list[Any], ExitStack]:
    stack: ExitStack = ExitStack()
    tools: list[Any] = []
    for name in mcp_names:
        client = MCP_FACTORIES[name]()
        stack.enter_context(client)
        tools.extend(client.list_tools_sync())
    return tools, stack


def _github_mcp_enabled() -> bool:
    try:
        github_personal_access_token()
        return True
    except ValueError:
        return False


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
            "Runs pytest on target-apps services, reports failures, adds edge-case API tests, "
            "and produces structured QA handoff for the SDLC pipeline."
        ),
        model=_qa_model(),
        system_prompt=QA_SYS_PROMPT,
        tools=tools,
        callback_handler=_QACallbackHandler(),
    )


def _enrich_devops_handoff(ctx: dict[str, Any]) -> None:
    """Merge devops-handoff.json into context for GitHub PR review."""
    app = slugify(str(ctx["targetApp"]))
    handoff_path = _REPO_ROOT / "agents" / "pipeline" / f"{app}.devops-handoff.json"
    if not handoff_path.is_file():
        return
    try:
        data = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(data, dict):
        return
    for key in (
        "pullRequestNumber",
        "pullRequestUrl",
        "githubOwner",
        "githubRepo",
        "githubBaseBranch",
        "featureBranch",
        "branch",
    ):
        if data.get(key) is not None:
            ctx.setdefault(key, data[key])
    if data.get("branch") and not ctx.get("featureBranch"):
        ctx["featureBranch"] = data["branch"]


def _enrich_gitlab_handoff(ctx: dict[str, Any]) -> None:
    """Merge gitlab-handoff.json into context for MR QA comments."""
    app = slugify(str(ctx["targetApp"]))
    handoff_path = _REPO_ROOT / "agents" / "pipeline" / f"{app}.gitlab-handoff.json"
    if not handoff_path.is_file():
        return
    try:
        data = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(data, dict):
        return
    for key in (
        "mergeRequestIid",
        "mergeRequestUrl",
        "gitlabProject",
        "gitlabBaseBranch",
        "featureBranch",
        "branch",
    ):
        if data.get(key) is not None:
            ctx.setdefault(key, data[key])
    if data.get("branch") and not ctx.get("featureBranch"):
        ctx["featureBranch"] = data["branch"]


def _format_gitlab_qa_mr_comment(
    pytest_snapshot: dict[str, Any],
    *,
    app: str,
    qa_handoff: dict[str, Any],
) -> str:
    status = "pass" if pytest_snapshot.get("exitCode") == 0 else "fail"
    lines = [
        f"## QA results — `{app}`",
        "",
        f"**Status:** {status}",
        f"**Tests run:** {qa_handoff.get('testsRun', 0)}",
        f"**Passed:** {qa_handoff.get('testsPassed', 0)}",
        f"**Failed:** {qa_handoff.get('testsFailed', 0)}",
        f"**Command:** `{qa_handoff.get('testCommand', '')}`",
    ]
    failed = pytest_snapshot.get("failedTests") or []
    if failed:
        lines.extend(["", "**Failed tests:**"])
        lines.extend(f"- `{name}`" for name in failed[:25])
        if len(failed) > 25:
            lines.append(f"- … and {len(failed) - 25} more")
    new_tests = qa_handoff.get("newTestsWritten") or []
    if new_tests:
        lines.extend(["", "**New QA tests:**"])
        lines.extend(f"- `{path}`" for path in new_tests[:15])
    return "\n".join(lines)


def _post_gitlab_mr_qa_comment(
    ctx: dict[str, Any],
    pytest_snapshot: dict[str, Any],
    qa_handoff: dict[str, Any],
) -> str | None:
    """Post QA summary on GitLab MR when gitlab-handoff provides mergeRequestIid."""
    iid = ctx.get("mergeRequestIid")
    project = ctx.get("gitlabProject")
    if iid is None or not project:
        return None
    try:
        from _shared.gitlab_mcp_ops import create_mr_note

        body = _format_gitlab_qa_mr_comment(
            pytest_snapshot,
            app=str(ctx["targetApp"]),
            qa_handoff=qa_handoff,
        )
        result = create_mr_note(
            mr_iid=int(iid),
            body=body,
            project_id=str(project),
        )
    except (ImportError, TypeError, ValueError):
        return None
    if not result.get("ok"):
        return None
    note = result.get("note") or {}
    return str(note.get("web_url") or note.get("id") or "")


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
    ctx.setdefault(
        "runCommand",
        f"cd target-apps/{app} && uvicorn app.main:app --reload --port 8000",
    )

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
    _enrich_devops_handoff(ctx)
    _enrich_gitlab_handoff(ctx)
    if jira_key:
        ctx.setdefault("jiraKey", jira_key)

    use_github = _github_mcp_enabled() and ctx.get("pullRequestNumber") and ctx.get("githubOwner")
    if use_github:
        mcp_tools, stack = _load_mcp_tools(["github"])
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
    mr_note_ref = _post_gitlab_mr_qa_comment(ctx, pytest_snapshot, handoff)
    if mr_note_ref:
        summary += f"\n\n## GitLab MR comment\nPosted QA summary: {mr_note_ref}\n"
    summary += f"\n\n## QA handoff\nSaved: `{handoff_path.relative_to(_REPO_ROOT).as_posix()}`\n```json\n{json.dumps(handoff, indent=2)}\n```\n"

    return summary, list(_written_files)


def serve_a2a(host: str = "127.0.0.1", port: int = A2A_PORT) -> None:
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
