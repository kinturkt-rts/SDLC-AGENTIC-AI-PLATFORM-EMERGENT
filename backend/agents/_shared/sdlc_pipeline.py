"""Deterministic SDLC pipeline runner — mirrors scripts/run-sdlc-local.ps1.

Used by orchestrator-agent as the master coordinator for local CLI and AgentCore A2A.
"""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .a2a_invoke import a2a_invoke_error, invoke_agent, response_text
from .artifact_store import (
    artifact_paths_for_agent,
    is_s3_store,
    materialize_run,
    new_run_id,
    put_artifact,
    put_context,
    register_pipeline_run,
    repo_root,
    resolve_run_id,
    run_sql_artifact_keys,
    sync_repo_paths_to_run,
    update_pipeline_run,
)
from .db_handoff import write_db_handoff
from .mcp_clients import postgres_mcp_tool_params
from .env import load_repo_env
from .pipeline_context import (
    design_doc_rel_for_app,
    diagram_path_for_app,
    gitlab_handoff_rel_for_app,
    openapi_rel_for_app,
    pipeline_context_rel_for_app,
    prd_rel_path_for_app,
    qa_handoff_rel_for_app,
    read_context_json,
    slugify,
    target_app_root_rel,
)

logger = logging.getLogger(__name__)

# Specialists that write artifacts directly to S3 (runId in context) — no local sync.
_S3_DIRECT_WRITE_AGENTS = frozenset({"product-agent", "database-agent", "developer-agent"})


def _safe_print(text: str, *, file: Any = None) -> None:
    """Print text replacing chars the console cannot encode (Windows cp1252)."""
    target = file or sys.stdout
    try:
        target.write(text)
        if not text.endswith("\n"):
            target.write("\n")
        target.flush()
    except UnicodeEncodeError:
        safe = text.encode(target.encoding or "utf-8", errors="replace").decode(
            target.encoding or "utf-8", errors="replace"
        )
        target.write(safe)
        if not safe.endswith("\n"):
            target.write("\n")
        target.flush()

TransportMode = Literal["local", "a2a", "auto"]

DEV_TASK_DB = """
Implement API surface from designDocPath as FastAPI routes. dev_read_file db/HANDOFF.md and every db/sql/*.sql before models.
Postgres parity (mandatory): psycopg[binary] + postgresql+psycopg:// in .env.example with ?sslmode=require; dialect-guarded database.py;
ENUM columns use sqlalchemy.Enum(create_type=False, native_enum=True) with sqlite String variant;
uuid columns use PG_UUID(as_uuid=False).with_variant(String(36), sqlite); Pydantic response schemas coerce UUID to str.
Auth per design Rules only (API-key and/or JWT+bcrypt  - not both unless design requires).
If deliveryProfile.requiresStreamlit is true: Pattern C mandatory - ui/streamlit_app.py + ui/requirements.txt;
login via API; JWT in st.session_state or API_KEY header per auth mode; role-based tabs per PRD; README Terminal 1+2.
tests/conftest.py: SQLite with schema ATTACH when models use POSTGRES_SCHEMA.
When db/sql/*seed*.sql has JWT users: add tests/test_seed_bcrypt.py (from _template/tests/test_seed_bcrypt_reference.py); conftest password must match seed SQL comment.
README: Windows+bash setup, .env copy, uvicorn, Swagger auth header, seed UUIDs, RDS smoke-test steps (GET /health + one DB list route).
When multiple roles or /portal vs /internal: README must include Role & endpoint quick reference (example seed username per route).
Baseline pytest must pass.
""".strip()

DEV_TASK_NO_DB = (
    "Implement API surface and rules from designDocPath as FastAPI routes, "
    "Pydantic schemas, and baseline pytest. README with how to run uvicorn and open /docs."
)

DB_AGENT_TASK = (
    "Implement data model from designDocPath §3/§6: numbered sql/ migrations, stable UUIDs. "
    "Whenever any table seeds __BCRYPT_PLACEHOLDER__ in a password_hash/hashed_password column, "
    "that same table should also have a username or email column as the login identifier, even "
    "if designDocPath omitted it — a hash with no way to look up which row it belongs to means "
    "nobody can actually log in and test the app, even though the pipeline itself will still "
    "seed and hash it correctly. Document the password in a SQL comment, and write a "
    "'### seedCredentials' table in HANDOFF.md listing every seeded user's login value, "
    "password, and hash column."
)

WEB_CRAWLER_TASK = (
    "Scrape URLs from context scrapeUrls or requirements; persist markdown and Postgres rows."
)

# Canonical chain (orchestrator diagram): FE -> ORCH -> PROD -> ARCH -> DB -> DEV -> GL -.-> QA
PIPELINE_STEPS: tuple[str, ...] = (
    "product-agent",
    "architect-agent",
    "database-agent",
    "developer-agent",
    "gitlab-agent",
    "qa-agent",
)

DEFAULT_A2A_TIMEOUT_SEC = 600
DEFAULT_DEVELOPER_A2A_TIMEOUT_SEC = 2400
# Re-attempts after the first developer-agent failure (SDLC_DEVELOPER_RETRY_ATTEMPTS).
DEFAULT_DEVELOPER_RETRY_ATTEMPTS = 1
# Fallback model for developer retries (DEVELOPER_AGENT_FALLBACK_MODEL_ID).
# Same Sonnet 4.6 ID as product/architect agents (MODEL_ID) — lighter than CODING_MODEL_ID.
DEFAULT_DEVELOPER_FALLBACK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"


@dataclass
class PipelineOptions:
    """Configuration for a full SDLC pipeline run."""

    target_app: str
    input_file: str = ""
    context_file: str = ""
    run_id: str | None = None
    transport: TransportMode = "auto"
    skip_product: bool = False
    skip_architect: bool = False
    with_web_crawler: bool = False
    skip_web_crawler: bool = False
    skip_db: bool = False
    skip_postgres: bool = False
    skip_developer: bool = False
    skip_verify: bool = False
    skip_gitlab: bool = False
    with_qa: bool = False
    skip_qa: bool = False
    with_frontend: bool = False
    skip_frontend: bool = False
    with_jira: bool = False
    jira_project: str = ""
    jira_sprint: int = 0
    jira_story_title_style: str = ""
    gitlab_project: str = ""
    gitlab_base: str = ""


@dataclass
class PipelineResult:
    """Outcome of a pipeline run."""

    target_app: str
    run_id: str | None
    agents_run: list[str] = field(default_factory=list)
    success: bool = True
    errors: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"SDLC pipeline {'completed' if self.success else 'failed'} for {self.target_app}",
        ]
        if self.run_id:
            lines.append(f"runId: {self.run_id}")
        if self.agents_run:
            lines.append(f"agents: {', '.join(self.agents_run)}")
        for label, path in self.artifacts.items():
            lines.append(f"{label}: {path}")
        for err in self.errors:
            lines.append(f"error: {err}")
        return "\n".join(lines)


def resolve_transport(mode: TransportMode) -> Literal["local", "a2a"]:
    """Pick subprocess (local) vs A2A/AgentCore ARN based on env and option."""
    if mode in ("local", "a2a"):
        return mode
    if os.getenv("AGENTCORE_A2A_PEER_URLS", "").strip():
        return "a2a"
    env_mode = os.getenv("SDLC_PIPELINE_TRANSPORT", "").strip().lower()
    if env_mode in ("local", "a2a"):
        return env_mode  # type: ignore[return-value]
    if os.getenv("AGENTCORE_AGENT", "").strip() or is_s3_store():
        return "a2a"
    return "local"


def planned_steps(options: PipelineOptions) -> list[str]:
    """Return ordered agent steps matching the orchestrator diagram."""
    steps: list[str] = []
    if not options.skip_product:
        steps.append("product-agent")
    if not options.skip_architect:
        steps.append("architect-agent")
    if not options.skip_db:
        steps.append("database-agent")
    if not options.skip_developer:
        steps.append("developer-agent")
    if _should_run_frontend(options):
        steps.append("frontend-agent")
    if _should_run_gitlab(options):
        steps.append("gitlab-agent")
    if _should_run_qa(options):
        steps.append("qa-agent")
    return steps


def _should_run_gitlab(options: PipelineOptions) -> bool:
    if options.skip_gitlab:
        return False
    # A2A/AgentCore: gitlab-agent runtime holds GITLAB_* secrets; orchestrator only schedules the step.
    if resolve_transport(options.transport) == "a2a":
        return True
    token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITLAB_TOKEN")
    if not token:
        return False
    if options.gitlab_project:
        return True
    return bool(os.getenv("GITLAB_PROJECT_PATH") or os.getenv("GITLAB_PROJECT_ID"))


def _should_run_qa(options: PipelineOptions) -> bool:
    return options.with_qa and not options.skip_qa and not options.skip_developer

def _should_run_frontend(options: PipelineOptions) -> bool:
    return options.with_frontend and not options.skip_frontend


class SdlcPipelineRunner:
    """Execute the SDLC chain with local subprocess or A2A transport."""

    def __init__(self, options: PipelineOptions) -> None:
        load_repo_env()
        self.options = options
        self.root = repo_root()
        self.feature = slugify(options.target_app)
        self.transport = resolve_transport(options.transport)
        self.run_id = options.run_id or resolve_run_id() or (
            new_run_id() if is_s3_store() else None
        )
        self.context_file = options.context_file or pipeline_context_rel_for_app(self.feature)
        self.ctx_path = self.root / self.context_file.replace("/", os.sep)
        self.context: dict[str, Any] = {}
        self.agents_run: list[str] = []
        self.errors: list[str] = []
        self.artifacts: dict[str, str] = {}

    def run(self) -> PipelineResult:
        """Run all planned steps; stop on first hard failure."""
        self._begin_run()
        self._load_context()
        try:
            if not self.options.skip_product:
                self._step_product()
            else:
                self._hydrate_run_context()

            if self.options.input_file:
                input_rel = self.options.input_file.replace("\\", "/").lstrip("/")
                self.context.setdefault("inputFile", input_rel)
                self.context.setdefault("inputPath", input_rel)
                self._save_context()
                self._sync_delivery_profile(self.options.input_file)
            elif self.ctx_path.is_file():
                self._sync_delivery_profile()

            if not self.options.skip_architect:
                self._step_architect()
            else:
                self._update_context(
                    {"diagramPaths": [diagram_path_for_app(self.feature)]}
                )

            if self.options.with_web_crawler and not self.options.skip_web_crawler:
                self._step_web_crawler()

            if not self.options.skip_db:
                self._step_database()
                if not self.options.skip_postgres:
                    self._step_rds_apply()

            if not self.options.skip_developer:
                self._step_developer()

            self._step_generate_env()

            if not self.options.skip_verify and not self.options.skip_developer:
                self._step_verify()
            
            if _should_run_frontend(self.options):
                self._step_frontend()

            gitlab_ran = False
            if _should_run_gitlab(self.options):
                self._step_gitlab()
                gitlab_ran = True

            if _should_run_qa(self.options):
                self._step_qa()

            # Publish succeeded → wait for async GitLab CI / devops before "completed".
            # Skip-gitlab runs have no CI deploy, so they finish as completed.
            final_status = "awaiting_deploy" if gitlab_ran else "completed"
            if self.run_id and is_s3_store():
                update_pipeline_run(
                    self.run_id, status=final_status, last_agent="orchestrator-agent"
                )
            self._update_run_json(status=final_status, finished=True)
            self._write_telemetry()
        except PipelineStepError as exc:
            self.errors.append(str(exc))
            if self.run_id and is_s3_store():
                update_pipeline_run(self.run_id, status="failed")
            self._update_run_json(status="failed", error=str(exc), finished=True)
            return self._result(success=False)

        return self._result(success=True)

    def _result(self, *, success: bool) -> PipelineResult:
        return PipelineResult(
            target_app=self.feature,
            run_id=self.run_id,
            agents_run=list(self.agents_run),
            success=success,
            errors=list(self.errors),
            artifacts=dict(self.artifacts),
        )

    # ── run.json persistence ───────────────────────────────────

    def _run_json_path(self) -> Path | None:
        if not self.run_id:
            return None
        return self.root / "agents" / "pipeline" / "runs" / self.run_id / "run.json"

    def _default_steps(self) -> list[dict[str, str]]:
        """Frontend-compatible step skeleton (matches pipeline-run.ts run.json seed)."""
        opts = self.options
        return [
            {
                "name": "product-agent",
                "label": "1/6 Product (PRD)",
                "status": "skipped" if opts.skip_product else "queued",
            },
            {
                "name": "architect-agent",
                "label": "2/6 Architect (design + diagram)",
                "status": "skipped" if opts.skip_architect else "queued",
            },
            {
                "name": "database-agent",
                "label": "3/6 Database (SQL migrations)",
                "status": "skipped" if opts.skip_db else "queued",
            },
            {
                "name": "developer-agent",
                "label": "4/6 Developer (FastAPI)",
                "status": "skipped" if opts.skip_developer else "queued",
            },
            {
                "name": "gitlab-agent",
                "label": "5/6 GitLab publish",
                "status": "queued" if _should_run_gitlab(opts) else "skipped",
            },
            {
                "name": "qa-agent",
                "label": "6/6 QA (optional)",
                "status": "queued" if _should_run_qa(opts) else "skipped",
            },
        ]

    def _mirror_run_json_to_s3(self, data: dict[str, Any]) -> None:
        """Publish run.json to runs/<runId>/ so the frontend can poll run state.

        This is the async-pipeline status channel: the frontend gets an
        immediate ack from the orchestrator and then reads this artifact until
        status turns terminal (awaiting_deploy → completed after CI deploy, or failed).
        """
        if not self.run_id or not is_s3_store():
            return
        try:
            put_artifact(
                self.run_id,
                "run.json",
                json.dumps(data, indent=2) + "\n",
                content_type="application/json",
            )
        except Exception:
            logger.warning("Could not mirror run.json to S3", exc_info=True)

    def _update_run_json(
        self,
        *,
        status: str | None = None,
        current_step: str | None = None,
        error: str | None = None,
        finished: bool = False,
    ) -> None:
        """Update local run.json (and its S3 mirror) so the frontend can track progress."""
        rj = self._run_json_path()
        if not rj:
            return
        try:
            data: dict[str, Any] = {}
            if rj.is_file():
                data = json.loads(rj.read_text(encoding="utf-8-sig"))
            data.setdefault("runId", self.run_id)
            data.setdefault("feature", self.feature)
            data.setdefault("targetApp", self.feature)
            data.setdefault("startedAt", datetime.now(timezone.utc).isoformat())
            data.setdefault("status", "running")
            if not data.get("steps"):
                data["steps"] = self._default_steps()
            if status:
                data["status"] = status
            if error is not None:
                data["error"] = error
            if finished:
                data["finishedAt"] = datetime.now(timezone.utc).isoformat()
            if data.get("steps"):
                agent_order = [s["name"] for s in data["steps"]]
                # current_step can be an internal-only pseudo-step (e.g. "rds-apply",
                # "seed-materialize") that runs between database-agent and developer-agent
                # but isn't one of the 6 UI-facing steps. Only advance the displayed
                # currentStep/index for a name that's actually in the steps array — an
                # unrecognized name would otherwise resolve to index -1, and on failure
                # "i > current_idx" is then true for every step, wiping the whole array
                # to "queued" even though earlier steps genuinely completed.
                if current_step is not None and current_step in agent_order:
                    data["currentStep"] = current_step
                current = data.get("currentStep")
                current_idx = agent_order.index(current) if current and current in agent_order else -1
                for i, step in enumerate(data["steps"]):
                    if step.get("status") == "skipped":
                        continue
                    if finished and status == "completed":
                        step["status"] = "completed"
                    elif finished and status == "failed":
                        if i == current_idx:
                            step["status"] = "failed"
                        elif i > current_idx:
                            step["status"] = "queued"
                    elif current_idx >= 0:
                        if i < current_idx:
                            step["status"] = "completed"
                        elif i == current_idx:
                            step["status"] = "running"
            rj.parent.mkdir(parents=True, exist_ok=True)
            rj.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            self._mirror_run_json_to_s3(data)
        except Exception as exc:
            logger.warning("Could not update run.json: %s", exc)

    # ── pipeline lifecycle ───────────────────────────────────

    def _begin_run(self) -> None:
        """Orchestrator: allocate runId, register DynamoDB index, export env for specialists."""
        if is_s3_store() and not self.run_id:
            self.run_id = new_run_id()
        if self.run_id:
            os.environ["PIPELINE_RUN_ID"] = self.run_id
            if is_s3_store():
                register_pipeline_run(self.run_id, self.feature)
        # Seed run.json (local + S3 mirror) so frontend polling sees "running"
        # immediately after the async ack instead of a missing artifact.
        self._update_run_json(status="running")

    def _after_agent_step(self, agent_name: str) -> None:
        """Specialists -> S3; orchestrator -> DynamoDB run index."""
        if not self.run_id:
            return
        self._merge_run_context_from_s3()
        merged = put_context(self.run_id, self.context)
        self.context.update(merged)
        if is_s3_store():
            if self.transport == "a2a" and agent_name in _S3_DIRECT_WRITE_AGENTS:
                update_pipeline_run(self.run_id, last_agent=agent_name)
            else:
                paths = artifact_paths_for_agent(agent_name, self.feature, self.context)
                sync_repo_paths_to_run(self.run_id, paths)
                update_pipeline_run(self.run_id, last_agent=agent_name)

    def _load_context(self) -> None:
        if self.ctx_path.is_file():
            self.context = read_context_json(self.ctx_path)
        self.context.setdefault("targetApp", self.feature)
        if self.run_id:
            self.context["runId"] = self.run_id
            self._hydrate_run_context()

    def _hydrate_run_context(self) -> None:
        """Load run-scoped paths from context.json (S3/local) — authoritative for resume."""
        if not self.run_id:
            return
        self._merge_run_context_from_s3()
        from .pipeline_context import normalize_handoff_paths

        normalize_handoff_paths(self.context)
        self._normalize_docs_layout_paths()
        if not self.context.get("prdPath"):
            self.context["prdPath"] = prd_rel_path_for_app(self.feature)
        self._save_context()

    def _normalize_docs_layout_paths(self) -> None:
        """Align design/diagram paths when PRD uses docs/ layout (cloud v1)."""
        prd = str(self.context.get("prdPath") or "")
        slug = self.feature
        if not prd.startswith("docs/PRD/"):
            return
        self.context["designDocPath"] = f"docs/design/{slug}.md"
        self.context["diagramPaths"] = [f"docs/generated-diagrams/{slug}.png"]

    def _save_context(self) -> None:
        self.ctx_path.parent.mkdir(parents=True, exist_ok=True)
        self.ctx_path.write_text(json.dumps(self.context, indent=2) + "\n", encoding="utf-8")

    def _update_context(self, fields: dict[str, Any]) -> None:
        self.context.update(fields)
        self.context.setdefault("targetApp", self.feature)
        if not self.context.get("designDocPath"):
            self.context["designDocPath"] = design_doc_rel_for_app(self.feature)
        self._save_context()

    def _context_for_agent(self, *, include_db_paths: bool = False) -> dict[str, Any]:
        from .pipeline_context import merge_run_handoff_context

        ctx = merge_run_handoff_context(dict(self.context), include_db_paths=include_db_paths)
        if self.run_id:
            ctx["runId"] = self.run_id
        return ctx

    def _merge_run_context_from_s3(self) -> None:
        """After A2A specialist steps, merge paths the remote agent wrote to the run store."""
        if not self.run_id:
            return
        from .artifact_store import get_context

        remote = get_context(self.run_id, target_app=self.feature)
        if remote:
            self.context.update(remote)
        from .pipeline_context import normalize_handoff_paths

        normalize_handoff_paths(self.context)

    def _run_python(
        self,
        args: list[str],
        *,
        step: str,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        self._update_run_json(current_step=step)
        cmd = [sys.executable, *args]
        logger.info("[%s] %s", step, " ".join(args))
        env = {**os.environ, **env_overrides} if env_overrides else None
        proc = subprocess.run(
            cmd,
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=env,
        )
        if proc.stdout:
            _safe_print(proc.stdout)
        if proc.stderr:
            _safe_print(proc.stderr, file=sys.stderr)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()
            if len(tail) > 800:
                tail = "\u2026" + tail[-800:]
            detail = f"{step} failed (exit {proc.returncode})"
            if tail:
                detail = f"{detail}: {tail}"
            raise PipelineStepError(detail)

    def _soft_fail_seed_materialize(self) -> bool:
        """When True, seed bcrypt failures warn but do not abort after SQL apply."""
        flag = os.getenv("SDLC_SOFT_FAIL_SEED_MATERIALIZE", "").strip().lower()
        if flag in ("1", "true", "yes", "on"):
            return True
        return False

    def _app_dir_for_rds(self, workspace_root: Path) -> Path:
        app_dir = workspace_root / target_app_root_rel(self.feature).replace("/", os.sep)
        if not (app_dir / "db").is_dir():
            legacy = workspace_root / "target-apps" / self.feature
            if (legacy / "db").is_dir():
                return legacy
        return app_dir

    def _invoke_a2a(
        self,
        agent_name: str,
        task: str,
        *,
        step: str,
        include_db_paths: bool = False,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        self._update_run_json(current_step=step)
        timeout = (
            DEFAULT_DEVELOPER_A2A_TIMEOUT_SEC
            if agent_name == "developer-agent"
            else DEFAULT_A2A_TIMEOUT_SEC
        )
        env_key = (
            "SDLC_DEVELOPER_AGENT_TIMEOUT_SEC"
            if agent_name == "developer-agent"
            else "SDLC_AGENT_TIMEOUT_SEC"
        )
        timeout = int(os.getenv(env_key, str(timeout)))
        context = self._context_for_agent(include_db_paths=include_db_paths)
        if extra_context:
            context.update(extra_context)
        result = invoke_agent(
            agent_name,
            task,
            context=context,
            timeout=timeout,
        )
        text = response_text(result)
        _safe_print(f"[{step}] {text}")
        invoke_error = a2a_invoke_error(result)
        if invoke_error:
            raise PipelineStepError(f"{step} A2A failed: {invoke_error}")
        if result.get("status") != "success":
            raise PipelineStepError(f"{step} A2A failed: {result.get('error')}")

    def _step_product(self) -> None:
        if not self.options.input_file:
            raise PipelineStepError("input_file is required when product-agent runs")
        input_rel = self.options.input_file.replace("\\", "/").lstrip("/")
        self._update_context(
            {
                "inputFile": input_rel,
                "inputPath": input_rel,
            }
        )
        if self.transport == "local":
            args = [
                "agents/product-agent/product_agent.py",
                "--input-file",
                input_rel,
                "--prd-name",
                self.feature,
            ]
            if self.options.with_jira:
                if not self.options.jira_project:
                    raise PipelineStepError("with_jira requires jira_project")
                args.extend(
                    [
                        "--create-jira-tickets",
                        "--allow-writes",
                        "--project",
                        self.options.jira_project,
                    ]
                )
                if self.options.jira_sprint > 0:
                    args.extend(["--sprint", str(self.options.jira_sprint)])
                if self.options.jira_story_title_style:
                    args.extend(["--story-title-style", self.options.jira_story_title_style])
            self._run_python(args, step="product-agent")
        else:
            if self.options.with_jira:
                if not self.options.jira_project:
                    raise PipelineStepError("with_jira requires jira_project")
                self._update_context(
                    {
                        "createJiraBacklog": True,
                        "withJira": True,
                        "jiraProjectKey": self.options.jira_project,
                        "projectKey": self.options.jira_project,
                    }
                )
                if self.options.jira_sprint > 0:
                    self._update_context({"jiraSprintId": self.options.jira_sprint})
                if self.options.jira_story_title_style:
                    self._update_context(
                        {"jiraStoryTitleStyle": self.options.jira_story_title_style}
                    )
            task = f"Create PRD from staged input for {self.feature}."
            if self.options.with_jira:
                task += f" Create Jira epic and stories in project {self.options.jira_project}."
            self._invoke_a2a("product-agent", task, step="product-agent")

        if self.transport == "a2a" and self.run_id:
            self._merge_run_context_from_s3()

        if self.transport == "a2a" and self.run_id:
            from .artifact_store import resolve_prd_artifact_rel

            try:
                prd_rel = resolve_prd_artifact_rel(self.run_id, self.feature, self.context)
            except FileNotFoundError as exc:
                raise PipelineStepError(
                    f"PRD not found in S3 after product-agent: runs/{self.run_id}/ ({exc})"
                ) from exc
        else:
            prd_rel = str(self.context.get("prdPath") or prd_rel_path_for_app(self.feature))
            if self.transport == "local":
                prd_path = self.root / prd_rel.replace("/", os.sep)
                if not prd_path.is_file():
                    raise PipelineStepError(f"PRD not found: {prd_rel}")

        fields: dict[str, Any] = {
            "prdPath": prd_rel,
        }
        product_brief = self._product_brief_from_prd(prd_rel)
        if product_brief:
            fields["productBrief"] = product_brief
        if self.options.with_jira:
            fields["jiraProjectKey"] = self.options.jira_project
            fields["jiraBacklogCreated"] = True
        self._update_context(fields)
        self.agents_run.append("product-agent")
        self.artifacts["PRD"] = prd_rel
        self._after_agent_step("product-agent")

    def _product_brief_from_prd(self, prd_rel: str, *, max_chars: int = 700) -> str:
        """Build a compact product brief from the PRD artifact."""
        try:
            if self.run_id and is_s3_store():
                from .artifact_store import get_artifact_text

                text = get_artifact_text(self.run_id, prd_rel)
            else:
                text = (self.root / prd_rel.replace("/", os.sep)).read_text(encoding="utf-8")
        except OSError:
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
                heading = line[3:].strip().lower()
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

    def _step_architect(self) -> None:
        if self.run_id:
            self._hydrate_run_context()
        if self.transport == "local":
            self._run_python(
                [
                    "agents/architect-agent/architect_agent.py",
                    "--diagram-name",
                    self.feature,
                    "--context-file",
                    self.context_file,
                    "--task",
                    self.feature,
                ],
                step="architect-agent",
            )
        else:
            self._invoke_a2a(
                "architect-agent",
                f"Produce architecture diagram and design doc for {self.feature}.",
                step="architect-agent",
            )

        if self.transport == "a2a" and self.run_id:
            self._merge_run_context_from_s3()

        design_rel = str(self.context.get("designDocPath") or design_doc_rel_for_app(self.feature))
        diagram_paths = [str(p) for p in (self.context.get("diagramPaths") or []) if p]
        if not diagram_paths:
            diagram_paths = [diagram_path_for_app(self.feature)]
        png_rel = diagram_paths[0]
        self._update_context({"diagramPaths": diagram_paths, "designDocPath": design_rel})
        self._delivery_check("design")
        self._sync_auth_mode()
        self.agents_run.append("architect-agent")
        self.artifacts["Design"] = design_rel
        self.artifacts["Diagram"] = png_rel
        self._after_agent_step("architect-agent")

    def _step_web_crawler(self) -> None:
        if self.transport == "local":
            self._run_python(
                [
                    "agents/web-crawler/web_crawler_agent.py",
                    "--target-app",
                    self.feature,
                    "--context-file",
                    self.context_file,
                    "--with-postgres",
                    "--task",
                    WEB_CRAWLER_TASK,
                ],
                step="web-crawler-agent",
            )
        else:
            self._invoke_a2a("web-crawler-agent", WEB_CRAWLER_TASK, step="web-crawler-agent")

        self._update_context(
            {
                "webScrapeCompleted": True,
                "scrapedOutputDir": f"docs/PRD/scraped/{self.feature}",
            }
        )
        self.agents_run.append("web-crawler-agent")

    def _step_database(self) -> None:
        if self.run_id:
            self._hydrate_run_context()
        if self.transport == "local":
            args = [
                "agents/database-agent/database_agent.py",
                "--target-app",
                self.feature,
                "--context-file",
                self.context_file,
                "--task",
                DB_AGENT_TASK,
                "--full-regen",
            ]
            if not self.options.skip_postgres:
                args.append("--with-postgres")
            self._run_python(args, step="database-agent")
        else:
            task = DB_AGENT_TASK
            self._invoke_a2a(
                "database-agent",
                task,
                step="database-agent",
                extra_context={"fullRegen": True},
            )

        if self.transport == "a2a" and self.run_id:
            self._merge_run_context_from_s3()

        self.agents_run.append("database-agent")
        self.artifacts["DB"] = f"{target_app_root_rel(self.feature)}/db/"
        self._after_agent_step("database-agent")

    def _resolve_rds_workspace(self) -> tuple[Path, Path]:
        """Return (repo_root for seed scripts, sql_dir) for RDS apply."""
        local_sql_dir = self.root / "target-apps" / self.feature / "db" / "sql"
        if self.transport == "a2a" and self.run_id:
            sql_keys = run_sql_artifact_keys(self.run_id, self.feature)
            if not sql_keys:
                app_root = target_app_root_rel(self.feature)
                raise PipelineStepError(
                    f"No SQL artifacts in S3 for run {self.run_id} "
                    f"(expected runs/{self.run_id}/{app_root}/db/sql/*.sql). "
                    "Ensure database-agent received runId in Context and ARTIFACT_STORE=s3 on its runtime."
                )
            workspace = materialize_run(self.run_id)
            app_root = target_app_root_rel(self.feature)
            sql_dir = workspace / app_root.replace("/", os.sep) / "db" / "sql"
            if not sql_dir.is_dir():
                legacy = workspace / "target-apps" / self.feature / "db" / "sql"
                if legacy.is_dir():
                    sql_dir = legacy
                else:
                    raise PipelineStepError(f"Materialized workspace missing sql dir: {sql_dir}")
            return workspace, sql_dir

        if not local_sql_dir.is_dir() or not any(local_sql_dir.glob("*.sql")):
            raise PipelineStepError(
                f"No db/sql/*.sql under target-apps/{self.feature}/ for RDS apply"
            )
        return self.root, local_sql_dir

    def _handoff_context_for_rds(self) -> dict[str, Any]:
        from .pipeline_context import merge_run_handoff_context

        ctx = merge_run_handoff_context(dict(self.context), include_db_paths=True)
        if self.run_id:
            ctx["runId"] = self.run_id
        ctx.setdefault("postgresAppSchema", self.feature.replace("-", "_"))
        if not ctx.get("postgresMcpParams"):
            ctx["postgresMcpParams"] = postgres_mcp_tool_params()
        return ctx

    def _step_rds_apply(self) -> None:
        from .seed_credentials import seed_sql_has_placeholders

        workspace_root, sql_dir = self._resolve_rds_workspace()
        self._run_python(
            [
                "scripts/apply_sql_to_rds.py",
                "--sql-dir",
                str(sql_dir),
                "--target-app",
                self.feature,
                "--skip-seed-materialize",
                "--reset-schema",
            ],
            step="rds-apply",
        )

        app_dir = self._app_dir_for_rds(workspace_root)
        seed_warnings: list[str] = []
        if seed_sql_has_placeholders(app_dir):
            try:
                self._run_python(
                    [
                        "agents/_shared/materialize_seed_passwords.py",
                        "--target-app",
                        self.feature,
                        "--repo-root",
                        str(workspace_root),
                    ],
                    step="seed-materialize",
                )
                for flag in ("", "--check-rds"):
                    verify_args = [
                        "agents/_shared/verify_seed_bcrypt.py",
                        "--target-app",
                        self.feature,
                        "--repo-root",
                        str(workspace_root),
                        "--quiet",
                    ]
                    if flag:
                        verify_args.append(flag)
                    self._run_python(verify_args, step="verify-seed-bcrypt")
            except PipelineStepError as exc:
                if self._soft_fail_seed_materialize():
                    seed_warnings.append(str(exc))
                    logger.warning("[rds-apply] seed materialize soft-fail: %s", exc)
                else:
                    raise
        else:
            logger.info(
                "[rds-apply] No seed hash placeholders — skipping seed materialize"
            )

        handoff_ctx = self._handoff_context_for_rds()
        if seed_warnings:
            handoff_ctx["seedMaterializeWarning"] = "; ".join(seed_warnings)
        handoff_rel = write_db_handoff(
            self.feature,
            handoff_ctx,
            rds_applied=True,
            repo_root=workspace_root,
        )
        self.context["databaseHandoffPath"] = handoff_rel
        if seed_warnings:
            self.context["seedMaterializeWarning"] = handoff_ctx["seedMaterializeWarning"]
        self._save_context()
        if self.run_id and is_s3_store():
            put_context(self.run_id, self.context)
        logger.info("[rds-apply] HANDOFF.md -> %s", handoff_rel)

    @staticmethod
    def _developer_retry_attempts() -> int:
        raw = os.getenv("SDLC_DEVELOPER_RETRY_ATTEMPTS", "").strip()
        try:
            return max(0, int(raw)) if raw else DEFAULT_DEVELOPER_RETRY_ATTEMPTS
        except ValueError:
            return DEFAULT_DEVELOPER_RETRY_ATTEMPTS

    @staticmethod
    def _developer_fallback_model() -> str:
        """Sonnet fallback on developer retries; empty string disables the model switch."""
        raw = os.getenv("DEVELOPER_AGENT_FALLBACK_MODEL_ID")
        if raw is None:
            return DEFAULT_DEVELOPER_FALLBACK_MODEL_ID
        return raw.strip()

    def _step_developer(self) -> None:
        if self.run_id:
            self._hydrate_run_context()
        task = DEV_TASK_NO_DB if self.options.skip_db else DEV_TASK_DB

        total_attempts = self._developer_retry_attempts() + 1
        fallback_model = self._developer_fallback_model()
        last_error: PipelineStepError | None = None

        for attempt in range(total_attempts):
            attempt_task = task
            use_fallback = attempt > 0 and bool(fallback_model)
            if attempt > 0:
                logger.warning(
                    "[developer-agent] retry %d/%d%s after failure: %s",
                    attempt,
                    total_attempts - 1,
                    f" with fallback model {fallback_model}" if use_fallback else "",
                    last_error,
                )
                attempt_task = (
                    f"{task}\n\nRETRY NOTE: the previous developer-agent attempt failed "
                    f"({last_error}). Re-implement the app completely, keep the code minimal, "
                    "and ensure the developer handoff is written before finishing."
                )
            try:
                if self.transport == "local":
                    self._run_python(
                        [
                            "agents/developer-agent/developer_agent.py",
                            "--target-app",
                            self.feature,
                            "--context-file",
                            self.context_file,
                            "--task",
                            attempt_task,
                            "--full-regen",
                        ],
                        step="developer-agent",
                        env_overrides=(
                            {"CODING_MODEL_ID": fallback_model} if use_fallback else None
                        ),
                    )
                else:
                    extra_context: dict[str, Any] = {"fullRegen": True}
                    if use_fallback:
                        extra_context["codingModelOverride"] = fallback_model
                    self._invoke_a2a(
                        "developer-agent",
                        attempt_task,
                        step="developer-agent",
                        include_db_paths=not self.options.skip_db,
                        extra_context=extra_context,
                    )
                    # AgentCore may return before developer-agent finishes writing S3 artifacts.
                    self._wait_for_developer_handoff()
                last_error = None
                break
            except PipelineStepError as exc:
                last_error = exc
                logger.warning(
                    "[developer-agent] attempt %d/%d failed: %s",
                    attempt + 1,
                    total_attempts,
                    exc,
                )

        if last_error is not None:
            raise PipelineStepError(
                f"developer-agent failed after {total_attempts} attempt(s): {last_error}"
            )

        if self.transport == "a2a" and self.run_id:
            self._merge_run_context_from_s3()

        # Local subprocess transport never writes ctx["openApiPath"] back into this
        # orchestrator's context.json (developer_agent.py's own put_context() call
        # only fires when it resolves a runId, i.e. the S3/A2A path) — so mirror
        # prdPath/designDocPath's own pattern here: derive the pointer path and set
        # it at the orchestrator level too. Skip if the A2A merge above already
        # pulled a value from S3 (do not overwrite a value developer-agent set).
        if not self.context.get("openApiPath"):
            openapi_local_path = (
                self.root / target_app_root_rel(self.feature).replace("/", os.sep) / "openapi.json"
            )
            if openapi_local_path.is_file():
                self._update_context({"openApiPath": openapi_rel_for_app(self.feature)})

        self.agents_run.append("developer-agent")
        self.artifacts["App"] = f"{target_app_root_rel(self.feature)}/"
        self._after_agent_step("developer-agent")
        self._ensure_developer_telemetry()

    def _ensure_developer_telemetry(self) -> None:
        """Verify developer-agent telemetry exists in S3; mirror from local if missing."""
        if not self.run_id or not is_s3_store():
            return
        from .artifact_store import run_artifact_exists, get_artifact_text, put_artifact
        from .telemetry import load_agent_telemetry, RunTelemetry

        tel_rel = f"{self.feature}/telemetry/developer-agent-telemetry.json"
        if run_artifact_exists(self.run_id, tel_rel):
            logger.info("[pipeline] developer-agent telemetry verified in S3")
            return

        logger.warning(
            "[pipeline] developer-agent telemetry missing from S3 (run=%s), "
            "attempting local fallback",
            self.run_id,
        )
        local_snap = load_agent_telemetry(self.feature, "developer-agent")
        if local_snap:
            local_snap["runId"] = self.run_id
            payload = json.dumps(local_snap, indent=2) + "\n"
            try:
                put_artifact(self.run_id, tel_rel, payload, content_type="application/json")
                logger.info("[pipeline] developer-agent telemetry mirrored from local to S3")
                return
            except Exception:
                logger.exception("[pipeline] failed to mirror developer-agent telemetry from local")

        try:
            handoff_rel = f"{self.feature}/handoffs/developer-handoff.json"
            raw = get_artifact_text(self.run_id, handoff_rel)
            handoff = json.loads(raw)
            files_written = len(handoff.get("writtenFiles", []))
            status = handoff.get("status", "unknown")
        except Exception:
            files_written = 0
            status = "completed"

        fallback = RunTelemetry(
            "developer-agent",
            target_app=self.feature,
            model_id=os.getenv("CODING_MODEL_ID", "us.anthropic.claude-opus-4-20250514-v1:0"),
            run_id=self.run_id,
        )
        fallback.extra = {
            "filesWritten": files_written,
            "status": status,
            "fallback": True,
        }
        payload = json.dumps(fallback.to_dict(), indent=2) + "\n"
        try:
            put_artifact(self.run_id, tel_rel, payload, content_type="application/json")
            logger.warning(
                "[pipeline] developer-agent fallback telemetry written to S3 "
                "(no token data — agent did not report)"
            )
        except Exception:
            logger.exception("[pipeline] failed to write developer-agent fallback telemetry")

    def _wait_for_developer_handoff(self) -> None:
        """Gate GitLab publish on developer readiness (AgentCore can return early).

        Publish proceeds when the developer either finished cleanly (``completed``)
        or delivered app artifacts but its runtime ended before finalizing
        (``partial``). It is blocked only when the developer explicitly failed or
        produced nothing publishable — preserving "publish whatever is generated"
        while still surfacing real developer failures.
        """
        if not self.run_id or not is_s3_store() or self.options.skip_developer:
            return
        from .artifact_store import (
            DEV_READY_COMPLETED,
            DEV_READY_FAILED,
            DEV_READY_MISSING,
            DEV_READY_PARTIAL,
            classify_developer_readiness,
        )
        from .pipeline_context import developer_handoff_rel_for_app

        rel = developer_handoff_rel_for_app(self.feature)
        # Async developer runs return an ack in seconds and stream work to S3
        # for as long as the implementation takes, so this poll — not the A2A
        # response — is the primary completion signal. The stall window must be
        # generous: LLM turns between file writes (and the final summary turn)
        # can legitimately go many minutes with no new writtenFiles.
        timeout = float(os.getenv("SDLC_DEVELOPER_HANDOFF_WAIT_SEC", "5400"))
        poll_interval = float(os.getenv("SDLC_DEVELOPER_HANDOFF_POLL_SEC", "15"))
        stall_polls = int(os.getenv("SDLC_DEVELOPER_STALL_POLLS", "40"))
        logger.info(
            "[pipeline] waiting for developer handoff: runs/%s/%s "
            "(timeout=%ss, poll=%ss, stall_polls=%s)",
            self.run_id,
            rel,
            timeout,
            poll_interval,
            stall_polls,
        )
        decision, handoff = classify_developer_readiness(
            self.run_id,
            self.feature,
            timeout_sec=timeout,
            poll_interval_sec=poll_interval,
            stall_polls=stall_polls,
        )
        if decision == DEV_READY_COMPLETED:
            logger.info("[pipeline] developer handoff ready: runs/%s/%s", self.run_id, rel)
            return
        if decision == DEV_READY_PARTIAL:
            logger.warning(
                "[pipeline] developer handoff not finalized for runs/%s/%s "
                "(status=%s); publishing delivered artifacts best-effort",
                self.run_id,
                rel,
                (handoff or {}).get("status", "in_progress"),
            )
            self.context["developerHandoffPartial"] = True
            return
        if decision == DEV_READY_FAILED:
            detail = str((handoff or {}).get("error") or "developer-agent reported failure")
            raise PipelineStepError(f"developer-agent failed before GitLab publish: {detail}")
        raise PipelineStepError(
            "developer-agent produced no publishable app artifacts before GitLab publish "
            f"(runs/{self.run_id}/{rel})"
        )

    def _step_generate_env(self) -> None:
        """Generate target-apps/<app>/.env from .env.example (skip-if-exists).

        Runs unconditionally after the developer step — even when developer-agent
        itself was skipped (resume runs) — because this must fire no matter how the
        pipeline is launched (run-sdlc-local.ps1, orchestrator-agent, A2A), not just
        from the PowerShell wrapper. No-op if there's no local .env.example (e.g.
        pure S3/AgentCore runs with no materialized workspace).
        """
        app_root = target_app_root_rel(self.feature)
        app_dir = self.root / app_root.replace("/", os.sep)
        if not (app_dir / ".env.example").is_file():
            legacy = self.root / "target-apps" / self.feature
            if (legacy / ".env.example").is_file():
                app_dir = legacy
            else:
                return

        self._update_run_json(current_step="generate-env")
        proc = subprocess.run(
            [
                sys.executable,
                "agents/_shared/generate_target_app_env.py",
                "--target-app",
                self.feature,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.stdout:
            _safe_print(proc.stdout)
        if proc.stderr:
            _safe_print(proc.stderr, file=sys.stderr)
        if proc.returncode != 0:
            logger.warning(
                "[generate-env] .env generation failed (exit %s) - copy %s/.env.example "
                "to .env by hand.",
                proc.returncode,
                app_root,
            )

    def _step_verify(self) -> None:
        app_root = target_app_root_rel(self.feature)
        app_dir = self.root / app_root.replace("/", os.sep)
        if not app_dir.is_dir():
            legacy = self.root / "target-apps" / self.feature
            app_dir = legacy if legacy.is_dir() else app_dir
        tests_dir = app_dir / "tests"
        if not tests_dir.is_dir():
            self._delivery_check("app")
            return

        venv_python = app_dir / ".venv" / "Scripts" / "python.exe"
        python = str(venv_python) if venv_python.is_file() else sys.executable
        env = os.environ.copy()
        env["DATABASE_URL"] = "sqlite://"
        env["SKIP_STARTUP_CHECKS"] = "1"

        import_cmd = [python, "-c", "from app.main import app"]
        if subprocess.run(import_cmd, cwd=app_dir, env=env, check=False).returncode != 0:
            raise PipelineStepError("app import failed during verify")

        pytest_cmd = [python, "-m", "pytest", "tests/", "-q", "--tb=line"]
        proc = subprocess.run(
            pytest_cmd, cwd=app_dir, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if proc.stdout:
            _safe_print(proc.stdout)
        if proc.returncode != 0:
            if proc.stderr:
                _safe_print(proc.stderr, file=sys.stderr)
            raise PipelineStepError("pytest failed during verify")

        self._delivery_check("app")

    def _read_gitlab_handoff(self) -> dict[str, Any] | None:
        """Load gitlab handoff from S3 run store or local repo path."""
        if self.run_id and is_s3_store():
            from .artifact_store import get_handoff

            return get_handoff(self.run_id, "gitlab")

        handoff_path = self.root / gitlab_handoff_rel_for_app(self.feature).replace("/", os.sep)
        if handoff_path.is_file():
            return json.loads(handoff_path.read_text(encoding="utf-8"))

        from .pipeline_context import slugify

        legacy = self.root / "agents" / "pipeline" / f"{slugify(self.feature)}.gitlab-handoff.json"
        if legacy.is_file():
            return json.loads(legacy.read_text(encoding="utf-8"))
        return None

    def _step_gitlab(self) -> None:
        self._wait_for_developer_handoff()
        apps_repo = os.getenv("GITLAB_APPS_REPO", "").strip().lower() in {"1", "true", "yes", "on"}
        if self.transport == "local":
            args = [
                "agents/gitlab-agent/gitlab_agent.py",
                "--target-app",
                self.feature,
                "--context-file",
                self.context_file,
            ]
            if apps_repo:
                args.append("--apps-repo")
            if self.options.gitlab_project:
                args.extend(["--gitlab-project", self.options.gitlab_project])
            if self.options.gitlab_base:
                args.extend(["--gitlab-base", self.options.gitlab_base])
            self._run_python(args, step="gitlab-agent")
        else:
            # Apps-repo and monorepo both use sdlc/<app> so GitLab CI deploy rules match.
            branch_hint = f"sdlc/{self.feature}"
            task = f"Publish SDLC artifacts for {self.feature} to GitLab branch {branch_hint}."
            self._invoke_a2a("gitlab-agent", task, step="gitlab-agent")

        handoff = self._read_gitlab_handoff()
        if handoff:
            self._update_context(
                {
                    "mergeRequestIid": handoff.get("mergeRequestIid"),
                    "mergeRequestUrl": handoff.get("mergeRequestUrl"),
                    "gitlabProject": handoff.get("gitlabProject"),
                    "featureBranch": handoff.get("branch"),
                }
            )
            self.artifacts["GitLab"] = (
                f"handoffs/gitlab.json"
                if self.run_id and is_s3_store()
                else gitlab_handoff_rel_for_app(self.feature)
            )
        # Deduped republish returns already-published (ok:true) — treat as success.
        publish_status = str((handoff or {}).get("status") or "").strip().lower()
        if not handoff or publish_status not in {"published", "already-published"}:
            detail = (handoff or {}).get("error") or "no gitlab handoff produced"
            raise PipelineStepError(f"gitlab-agent publish failed: {detail}")

        self.agents_run.append("gitlab-agent")
        self._after_agent_step("gitlab-agent")

    def _step_qa(self) -> None:
        if self.transport == "local":
            self._run_python(
                [
                    "agents/qa-agent/qa_agent.py",
                    "--target-app",
                    self.feature,
                    "--context-file",
                    self.context_file,
                ],
                step="qa-agent",
            )
        else:
            self._invoke_a2a(
                "qa-agent",
                f"Run extended pytest and coverage analysis for {self.feature}.",
                step="qa-agent",
            )
        self.agents_run.append("qa-agent")
        self.artifacts["QA"] = qa_handoff_rel_for_app(self.feature)
        self._after_agent_step("qa-agent")
    
    def _step_frontend(self) -> None:
        if self.transport == "local":
            self._run_python(
                [
                    "agents/frontend-agent/frontend_agent.py",
                    "--target-app",
                    self.feature,
                    "--context-file",
                    self.context_file,
                    "--full-regen",
                ],
                step="frontend-agent",
            )
        else:
            # frontend-agent has no A2A/AgentCore handler today (not in
            # config/agentcore/runtimes.json) — nothing to thread fullRegen into yet.
            self._invoke_a2a(
                "frontend-agent",
                f"Generate the React frontend for {self.feature} from the OpenAPI spec.",
                step="frontend-agent",
            )
        self.agents_run.append("frontend-agent")
        self.artifacts["Frontend"] = f"{target_app_root_rel(self.feature)}/frontend/"
        self._after_agent_step("frontend-agent")

    def _sync_delivery_profile(self, input_file: str = "") -> None:
        args = [
            "agents/_shared/delivery_profile.py",
            "--context-file",
            self.context_file,
            "--repo-root",
            str(self.root),
            "--sync",
        ]
        if input_file:
            args.extend(["--input-file", input_file.replace("\\", "/")])
        self._run_python(args, step="delivery-profile-sync")
        # The sync above writes deliveryProfile only to the on-disk context file
        # (via a subprocess). Pull it into the in-memory context immediately so a
        # later _hydrate_run_context() (which merges S3 context and re-saves) does
        # not silently drop it before it reaches architect/developer over A2A.
        if self.ctx_path.is_file():
            on_disk = read_context_json(self.ctx_path)
            if on_disk.get("deliveryProfile"):
                self.context["deliveryProfile"] = on_disk["deliveryProfile"]

    def _sync_auth_mode(self) -> None:
        """Derive authMode ("jwt"/"api-key") from the design doc and log it.

        Not consumed anywhere yet — this only makes the value visible in context.json
        and the run log on every pipeline run, regardless of entry point (orchestrator
        or run-sdlc-local.ps1), so database/developer/frontend-agent can read it once
        something is wired to branch on it.
        """
        if not self.ctx_path.is_file():
            return
        self._run_python(
            [
                "agents/_shared/auth_profile.py",
                "--context-file",
                self.context_file,
                "--repo-root",
                str(self.root),
                "--sync",
            ],
            step="auth-mode-sync",
        )
        if self.ctx_path.is_file():
            on_disk = read_context_json(self.ctx_path)
            if on_disk.get("authMode"):
                self.context["authMode"] = on_disk["authMode"]
        _safe_print(f"[pipeline] authMode: {self.context.get('authMode', 'jwt')}")

    def _delivery_check(self, stage: str) -> None:
        if not self.ctx_path.is_file():
            return
        self._run_python(
            [
                "agents/_shared/delivery_profile.py",
                "--context-file",
                self.context_file,
                "--repo-root",
                str(self.root),
                "--check",
                stage,
                "--quiet",
            ],
            step=f"delivery-profile-check-{stage}",
        )

    def _write_telemetry(self) -> None:
        if not self.agents_run:
            return
        args = [
            "agents/_shared/pipeline_telemetry.py",
            "--target-app",
            self.feature,
            "--agents-run",
            ",".join(self.agents_run),
        ]
        subprocess.run([sys.executable, *args], cwd=self.root, check=False)


class PipelineStepError(RuntimeError):
    """Raised when a pipeline step fails."""


def run_sdlc_pipeline(options: PipelineOptions) -> PipelineResult:
    """Public entry: run the full SDLC chain."""
    return SdlcPipelineRunner(options).run()


def mark_run_failed(run_id: str, target_app: str, error: str) -> None:
    """Force run.json (S3 + local) to a terminal failed state.

    Used by the orchestrator's fire-and-forget wrapper when the background
    pipeline dies with an unexpected exception — without this the frontend
    would poll a permanently "running" run.json until its own timeout.
    """
    now = datetime.now(timezone.utc).isoformat()
    feature = slugify(target_app)
    data: dict[str, Any] = {
        "runId": run_id,
        "feature": feature,
        "targetApp": feature,
        "status": "failed",
        "error": error,
        "finishedAt": now,
    }
    rj = repo_root() / "agents" / "pipeline" / "runs" / run_id / "run.json"
    try:
        if rj.is_file():
            existing = json.loads(rj.read_text(encoding="utf-8-sig"))
            existing.update(data)
            data = existing
        rj.parent.mkdir(parents=True, exist_ok=True)
        rj.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        logger.warning("mark_run_failed: could not update local run.json", exc_info=True)
    if is_s3_store():
        try:
            from .artifact_store import get_artifact_text

            try:
                remote = json.loads(get_artifact_text(run_id, "run.json"))
                remote.update({k: v for k, v in data.items() if k != "steps"})
                data = remote
            except FileNotFoundError:
                pass
            put_artifact(
                run_id,
                "run.json",
                json.dumps(data, indent=2) + "\n",
                content_type="application/json",
            )
        except Exception:
            logger.warning("mark_run_failed: could not update S3 run.json", exc_info=True)


def options_from_dict(data: dict[str, Any]) -> PipelineOptions:
    """Build PipelineOptions from a plain dict (tool / API payloads)."""
    known = {f.name for f in PipelineOptions.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: v for k, v in data.items() if k in known}
    if "target_app" not in filtered and "targetApp" in data:
        filtered["target_app"] = data["targetApp"]
    if "input_file" not in filtered and "inputFile" in data:
        filtered["input_file"] = data["inputFile"]
    if "run_id" not in filtered:
        for key in ("runId", "run_id", "pipelineRunId"):
            value = data.get(key)
            if value and str(value).strip():
                filtered["run_id"] = str(value).strip()
                break
    if "with_jira" not in filtered and data.get("withJira") is not None:
        filtered["with_jira"] = bool(data.get("withJira"))
    if "jira_project" not in filtered:
        for key in ("jiraProject", "jira_project", "jiraProjectKey"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                filtered["jira_project"] = value.strip()
                break
    if "jira_sprint" not in filtered and data.get("jiraSprint") is not None:
        try:
            filtered["jira_sprint"] = int(data["jiraSprint"])
        except (TypeError, ValueError):
            pass
    if "jira_story_title_style" not in filtered and data.get("jiraStoryTitleStyle"):
        filtered["jira_story_title_style"] = str(data["jiraStoryTitleStyle"]).strip()
    return PipelineOptions(**filtered)


def parse_pipeline_request(message: str) -> PipelineOptions | None:
    """Extract PipelineOptions from an A2A message containing a JSON payload."""
    text = message.strip()
    if not text:
        return None

    chunks: list[str] = []
    lower = text.lower()
    if "with:" in lower:
        idx = lower.rfind("with:")
        chunks.append(text[idx + len("with:") :].strip())
    if "context:" in lower:
        idx = lower.rfind("context:")
        chunks.append(text[idx + len("context:") :].strip())
    chunks.append(text)

    seen: set[str] = set()
    for chunk in chunks:
        if chunk in seen:
            continue
        seen.add(chunk)
        start = chunk.find("{")
        if start < 0:
            continue
        try:
            parsed = json.loads(chunk[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if not (parsed.get("target_app") or parsed.get("targetApp")):
            continue
        return options_from_dict(parsed)
    return None
