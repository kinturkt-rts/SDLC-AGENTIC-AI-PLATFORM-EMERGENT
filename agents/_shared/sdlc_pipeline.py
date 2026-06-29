"""Deterministic SDLC pipeline runner — mirrors scripts/run-sdlc.ps1.

Used by orchestrator-agent as the master coordinator for local CLI and AgentCore A2A.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .a2a_invoke import invoke_agent, response_text
from .artifact_store import (
    artifact_paths_for_agent,
    is_s3_store,
    new_run_id,
    put_context,
    register_pipeline_run,
    repo_root,
    resolve_run_id,
    sync_repo_paths_to_run,
    update_pipeline_run,
)
from .env import load_repo_env
from .pipeline_context import enrich_handoff_context, prd_rel_path_for_app, slugify

logger = logging.getLogger(__name__)

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
    "Implement data model from designDocPath §3/§6: numbered sql/ migrations, "
    "dev seed with __BCRYPT_PLACEHOLDER__ for password_hash columns, documented password "
    "in SQL comment, ### seedCredentials table in HANDOFF.md, stable UUIDs."
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
    if _should_run_gitlab(options):
        steps.append("gitlab-agent")
    if _should_run_qa(options):
        steps.append("qa-agent")
    return steps


def _should_run_gitlab(options: PipelineOptions) -> bool:
    if options.skip_gitlab or options.skip_developer:
        return False
    token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITLAB_TOKEN")
    if not token:
        return False
    if options.gitlab_project:
        return True
    return bool(os.getenv("GITLAB_PROJECT_PATH") or os.getenv("GITLAB_PROJECT_ID"))


def _should_run_qa(options: PipelineOptions) -> bool:
    return options.with_qa and not options.skip_qa and not options.skip_developer


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
        self.context_file = options.context_file or f"agents/pipeline/{self.feature}.context.json"
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
                self._update_context({"prdPath": prd_rel_path_for_app(self.feature)})

            if self.options.input_file:
                self._sync_delivery_profile(self.options.input_file)
            elif self.ctx_path.is_file():
                self._sync_delivery_profile()

            if not self.options.skip_architect:
                self._step_architect()
            else:
                self._update_context(
                    {"diagramPaths": [f"docs/diagrams/generated-diagrams/{self.feature}.png"]}
                )

            if self.options.with_web_crawler and not self.options.skip_web_crawler:
                self._step_web_crawler()

            if not self.options.skip_db:
                self._step_database()
                if not self.options.skip_postgres:
                    self._step_rds_apply()

            if not self.options.skip_developer:
                self._step_developer()

            if not self.options.skip_verify and not self.options.skip_developer:
                self._step_verify()

            if _should_run_gitlab(self.options):
                self._step_gitlab()

            if _should_run_qa(self.options):
                self._step_qa()

            if self.run_id and is_s3_store():
                update_pipeline_run(self.run_id, status="completed", last_agent="orchestrator-agent")
            self._write_telemetry()
        except PipelineStepError as exc:
            self.errors.append(str(exc))
            if self.run_id and is_s3_store():
                update_pipeline_run(self.run_id, status="failed")
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

    def _begin_run(self) -> None:
        """Orchestrator: allocate runId, register DynamoDB index, export env for specialists."""
        if is_s3_store() and not self.run_id:
            self.run_id = new_run_id()
        if self.run_id:
            os.environ["PIPELINE_RUN_ID"] = self.run_id
            if is_s3_store():
                register_pipeline_run(self.run_id, self.feature)

    def _after_agent_step(self, agent_name: str) -> None:
        """Specialists -> S3; orchestrator -> DynamoDB run index."""
        if not self.run_id:
            return
        put_context(self.run_id, self.context)
        if is_s3_store():
            paths = artifact_paths_for_agent(agent_name, self.feature, self.context)
            sync_repo_paths_to_run(self.run_id, paths)
            update_pipeline_run(self.run_id, last_agent=agent_name)

    def _load_context(self) -> None:
        if self.ctx_path.is_file():
            self.context = json.loads(self.ctx_path.read_text(encoding="utf-8-sig"))
        self.context.setdefault("targetApp", self.feature)
        if self.run_id:
            self.context["runId"] = self.run_id

    def _save_context(self) -> None:
        self.ctx_path.parent.mkdir(parents=True, exist_ok=True)
        self.ctx_path.write_text(json.dumps(self.context, indent=2) + "\n", encoding="utf-8")

    def _update_context(self, fields: dict[str, Any]) -> None:
        self.context.update(fields)
        self.context.setdefault("targetApp", self.feature)
        if not self.context.get("designDocPath"):
            self.context["designDocPath"] = f"docs/design/{self.feature}.md"
        self._save_context()

    def _context_for_agent(self) -> dict[str, Any]:
        ctx = enrich_handoff_context(dict(self.context))
        if self.run_id:
            ctx["runId"] = self.run_id
        return ctx

    def _run_python(self, args: list[str], *, step: str) -> None:
        cmd = [sys.executable, *args]
        logger.info("[%s] %s", step, " ".join(args))
        proc = subprocess.run(
            cmd,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        if proc.returncode != 0:
            raise PipelineStepError(f"{step} failed (exit {proc.returncode})")

    def _invoke_a2a(self, agent_name: str, task: str, *, step: str) -> None:
        result = invoke_agent(agent_name, task, context=self._context_for_agent())
        text = response_text(result)
        print(f"[{step}] {text}")
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
            task = f"Create PRD from staged input for {self.feature}."
            if self.options.with_jira:
                task += f" Create Jira epic and stories in project {self.options.jira_project}."
            self._invoke_a2a("product-agent", task, step="product-agent")

        prd_rel = prd_rel_path_for_app(self.feature)
        if self.transport == "a2a" and self.run_id and is_s3_store():
            from .artifact_store import get_artifact

            try:
                get_artifact(self.run_id, prd_rel)
            except Exception as exc:
                raise PipelineStepError(
                    f"PRD not found in S3 after product-agent: runs/{self.run_id}/{prd_rel} ({exc})"
                ) from exc
        else:
            prd_path = self.root / prd_rel.replace("/", os.sep)
            if not prd_path.is_file() and self.transport == "local":
                raise PipelineStepError(f"PRD not found: {prd_rel}")

        fields: dict[str, Any] = {
            "prdPath": prd_rel,
            "productAgentOutput": f"See prdPath for {self.feature} MVP requirements.",
        }
        if self.options.with_jira:
            fields["jiraProjectKey"] = self.options.jira_project
            fields["jiraBacklogCreated"] = True
        self._update_context(fields)
        self.agents_run.append("product-agent")
        self.artifacts["PRD"] = prd_rel
        self._after_agent_step("product-agent")

    def _step_architect(self) -> None:
        if self.transport == "local":
            self._run_python(
                [
                    "agents/architect-agent/architect_agent.py",
                    "--diagram-name",
                    self.feature,
                    "--context-file",
                    self.context_file,
                    "--task",
                    f"{self.feature} MVP",
                ],
                step="architect-agent",
            )
        else:
            self._invoke_a2a(
                "architect-agent",
                f"Produce architecture diagram and design doc for {self.feature} MVP.",
                step="architect-agent",
            )

        design_rel = f"docs/design/{self.feature}.md"
        png_rel = f"docs/diagrams/generated-diagrams/{self.feature}.png"
        self._update_context({"diagramPaths": [png_rel], "designDocPath": design_rel})
        self._delivery_check("design")
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
        if self.transport == "local":
            args = [
                "agents/database-agent/database_agent.py",
                "--target-app",
                self.feature,
                "--context-file",
                self.context_file,
                "--task",
                DB_AGENT_TASK,
            ]
            if not self.options.skip_postgres:
                args.append("--with-postgres")
            self._run_python(args, step="database-agent")
        else:
            task = DB_AGENT_TASK
            self._invoke_a2a("database-agent", task, step="database-agent")

        self.agents_run.append("database-agent")
        self.artifacts["DB"] = f"target-apps/{self.feature}/db/"
        self._after_agent_step("database-agent")

    def _step_rds_apply(self) -> None:
        sql_dir = self.root / "target-apps" / self.feature / "db" / "sql"
        if not sql_dir.is_dir():
            logger.warning("No db/sql/ — skip RDS apply")
            return
        self._run_python(
            ["scripts/apply_sql_to_rds.py", "--target-app", self.feature],
            step="rds-apply",
        )
        self._run_python(
            [
                "agents/_shared/materialize_seed_passwords.py",
                "--target-app",
                self.feature,
                "--repo-root",
                str(self.root),
            ],
            step="seed-materialize",
        )
        for flag in ("", "--check-rds"):
            args = [
                "agents/_shared/verify_seed_bcrypt.py",
                "--target-app",
                self.feature,
                "--repo-root",
                str(self.root),
                "--quiet",
            ]
            if flag:
                args.append(flag)
            self._run_python(args, step="verify-seed-bcrypt")

    def _step_developer(self) -> None:
        task = DEV_TASK_NO_DB if self.options.skip_db else DEV_TASK_DB
        if self.transport == "local":
            self._run_python(
                [
                    "agents/developer-agent/developer_agent.py",
                    "--target-app",
                    self.feature,
                    "--context-file",
                    self.context_file,
                    "--task",
                    task,
                ],
                step="developer-agent",
            )
        else:
            self._invoke_a2a("developer-agent", task, step="developer-agent")

        self.agents_run.append("developer-agent")
        self.artifacts["App"] = f"target-apps/{self.feature}/"
        self._after_agent_step("developer-agent")

    def _step_verify(self) -> None:
        app_dir = self.root / "target-apps" / self.feature
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
        proc = subprocess.run(pytest_cmd, cwd=app_dir, env=env, capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout)
        if proc.returncode != 0:
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
            raise PipelineStepError("pytest failed during verify")

        self._delivery_check("app")

    def _step_gitlab(self) -> None:
        if self.transport == "local":
            args = [
                "agents/gitlab-agent/gitlab_agent.py",
                "--target-app",
                self.feature,
                "--context-file",
                self.context_file,
            ]
            if self.options.gitlab_project:
                args.extend(["--gitlab-project", self.options.gitlab_project])
            if self.options.gitlab_base:
                args.extend(["--gitlab-base", self.options.gitlab_base])
            self._run_python(args, step="gitlab-agent")
        else:
            self._invoke_a2a(
                "gitlab-agent",
                f"Publish SDLC artifacts for {self.feature} to GitLab branch sdlc/{self.feature}.",
                step="gitlab-agent",
            )

        handoff_path = self.root / "agents" / "pipeline" / f"{self.feature}.gitlab-handoff.json"
        if handoff_path.is_file():
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            self._update_context(
                {
                    "mergeRequestIid": handoff.get("mergeRequestIid"),
                    "mergeRequestUrl": handoff.get("mergeRequestUrl"),
                    "gitlabProject": handoff.get("gitlabProject"),
                    "featureBranch": handoff.get("branch"),
                }
            )
            self.artifacts["GitLab"] = f"agents/pipeline/{self.feature}.gitlab-handoff.json"
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
        self.artifacts["QA"] = f"agents/pipeline/{self.feature}.qa-handoff.json"
        self._after_agent_step("qa-agent")

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


def options_from_dict(data: dict[str, Any]) -> PipelineOptions:
    """Build PipelineOptions from a plain dict (tool / API payloads)."""
    known = {f.name for f in PipelineOptions.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: v for k, v in data.items() if k in known}
    if "target_app" not in filtered and "targetApp" in data:
        filtered["target_app"] = data["targetApp"]
    if "input_file" not in filtered and "inputFile" in data:
        filtered["input_file"] = data["inputFile"]
    return PipelineOptions(**filtered)
