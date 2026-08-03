"""Pydantic schemas for inter-agent handoff JSON files.

Each agent reads upstream handoff(s) and writes a downstream one. Without typed
schemas, drift between producer and consumer silently turns into `dict.get()`
returning None deep in the consumer — bugs that only surface at runtime as
mysterious downstream failures.

Every schema sets `model_config = ConfigDict(extra="allow")` so producers can
add fields without breaking older consumers. Required fields are still enforced.

Use `load_handoff(path, ModelClass)` to read + validate + raise loudly with a
clear ValueError on schema mismatch.
"""

import json
from pathlib import Path
from typing import Any, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_DIR = _REPO_ROOT / "agents" / "pipeline"

T = TypeVar("T", bound=BaseModel)


class _BaseHandoff(BaseModel):
    """Shared base: allow extra fields, populate by name OR alias."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ── 1. PipelineContext ───────────────────────────────────────────────────────
# Written by product-agent on PRD save; auto-loaded by downstream agents.

class PipelineContext(_BaseHandoff):
    targetApp: str
    prdPath: str | None = None
    designDocPath: str | None = None
    diagramPaths: list[str] = Field(default_factory=list)
    productBrief: str | None = None
    productAgentOutput: str | None = None
    architectSummary: str | None = None
    dbOutputDir: str | None = None
    preferredSqlPath: str | None = None
    databaseHandoffPath: str | None = None
    dbSchemaHandoffPath: str | None = None
    dbBackend: Literal["postgres", "mongodb", "postgres+mongodb"] | None = None
    storyTitleStyle: Literal["concise", "user-story"] | None = None
    jiraKey: str | None = None
    projectKey: str | None = None


# ── 2. DeveloperHandoff ──────────────────────────────────────────────────────
# Written by developer-agent after generating target-apps/<app>/.

class DeploymentHandoff(_BaseHandoff):
    targetEnvironment: str = "aws-dev"
    port: int = 8000
    healthCheckPath: str = "/health"
    containerEntrypoint: str | None = None
    envVarNames: list[str] = Field(default_factory=list)
    secretsSource: str | None = None
    dockerReady: bool = False
    notes: str | None = None


class DeveloperHandoff(_BaseHandoff):
    targetApp: str
    writtenFiles: list[str] = Field(default_factory=list)
    dbBackend: str | None = None
    designDocPath: str | None = None
    prdPath: str | None = None
    databaseHandoffPath: str | None = None
    runCommand: str | None = None
    runCommandLocal: str | None = None
    testCommand: str | None = None
    userSetupCommand: str | None = None
    envVarsRequired: list[str] = Field(default_factory=list)
    deploymentHandoff: DeploymentHandoff | None = None
    jiraKey: str | None = None


# ── 3. QaHandoff ─────────────────────────────────────────────────────────────
# Written by qa-agent after running pytest + adding edge cases.

class FailedTest(_BaseHandoff):
    id: str
    classification: Literal["app_bug", "test_bug", "env_issue"] | None = None
    reason: str | None = None


class QaHandoff(_BaseHandoff):
    targetApp: str
    status: Literal["pass", "fail", "error"]
    testsRun: int = 0
    testsPassed: int = 0
    testsFailed: int = 0
    failedTests: list[FailedTest] = Field(default_factory=list)
    newTestsWritten: list[str] = Field(default_factory=list)
    testCommand: str | None = None
    coverageCommand: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    jiraKey: str | None = None


# ── 4. SecurityHandoff ───────────────────────────────────────────────────────
# Written by security-agent after bandit + pip-audit + secrets + PII scans.

SeverityCounts = dict[Literal["critical", "high", "medium", "low", "info"], int]


class SecurityFinding(_BaseHandoff):
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: str | None = None
    title: str | None = None
    location: str | None = None
    file: str | None = None
    line: int | None = None
    description: str | None = None
    remediation: str | None = None
    surface: str | None = None
    tool: str | None = None


class SecurityHandoff(_BaseHandoff):
    targetApp: str
    status: Literal["pass", "fail", "error"]
    severityCounts: dict[str, int] = Field(default_factory=dict)
    criticalCount: int = 0
    highCount: int = 0
    mediumCount: int = 0
    lowCount: int = 0
    findings: list[SecurityFinding] = Field(default_factory=list)
    toolingStatus: dict[str, str] = Field(default_factory=dict)
    reportPath: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    jiraKey: str | None = None


# ── 5. DatabaseHandoff ───────────────────────────────────────────────────────
# Written by architect-agent alongside solution_design.md; validated and read by
# database-agent before it writes DDL. Prescriptive (what to build), unlike the
# other handoffs above which are retrospective (what was built) — the first of
# its kind in this file, matching the redesign discussed for architect->database.

class ColumnSpec(_BaseHandoff):
    name: str
    type: str
    primaryKey: bool = False
    foreignKey: str | None = None  # e.g. "categories.id"
    nullable: bool = True
    unique: bool = False
    default: str | None = None


class IndexSpec(_BaseHandoff):
    columns: list[str]
    unique: bool = False
    condition: str | None = None  # partial index WHERE clause, if any


class RelationshipSpec(_BaseHandoff):
    fromEntity: str
    toEntity: str
    cardinality: Literal["one-to-one", "one-to-many", "many-to-many"]
    via: str | None = None  # FK column or join table


class StatusEnumSpec(_BaseHandoff):
    name: str
    values: list[str]
    transitions: list[str] = Field(default_factory=list)  # e.g. "available->assigned"


class EntitySpec(_BaseHandoff):
    name: str
    tableName: str
    columns: list[ColumnSpec]
    indexes: list[IndexSpec] = Field(default_factory=list)
    softDelete: bool = False
    auditLogged: bool = False


class DatabaseHandoff(_BaseHandoff):
    targetApp: str
    designDocPath: str | None = None
    entities: list[EntitySpec]
    relationships: list[RelationshipSpec] = Field(default_factory=list)
    statusEnums: list[StatusEnumSpec] = Field(default_factory=list)
    transactionBoundaries: list[str] = Field(default_factory=list)
    seedExpectations: str | None = None
    assumptions: list[str] = Field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────────────

class HandoffValidationError(ValueError):
    """Raised when a handoff JSON does not match its expected schema."""

    def __init__(self, path: Path, model_name: str, validation_error: ValidationError):
        rel = path.relative_to(_REPO_ROOT).as_posix() if path.is_absolute() else str(path)
        super().__init__(
            f"Handoff at {rel} does not match {model_name}:\n{validation_error}"
        )
        self.path = path
        self.model_name = model_name
        self.validation_error = validation_error


def load_handoff(path: str | Path, model: type[T]) -> T:
    """Read JSON at `path` and validate against `model`. Raises with a clear error on drift.

    Returns the parsed, typed model instance. Use `.model_dump()` for plain dict back.
    """
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = (_REPO_ROOT / file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"handoff file not found: {file_path}")
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"handoff at {file_path} is not valid JSON: {exc}") from exc
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise HandoffValidationError(file_path, model.__name__, exc) from exc


def write_handoff(model_instance: BaseModel, target_app: str, suffix: str) -> Path:
    """Write a handoff JSON for `(target_app, suffix)`. Returns the absolute path.

    suffix examples: 'developer-handoff', 'qa-handoff', 'security-handoff'.
    """
    _PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    out = _PIPELINE_DIR / f"{target_app}.{suffix}.json"
    out.write_text(
        model_instance.model_dump_json(indent=2, exclude_none=False) + "\n",
        encoding="utf-8",
    )
    return out


def validate_dict(payload: dict[str, Any], model: type[T]) -> T:
    """Validate an in-memory dict against `model`. Same loud-error semantics as load_handoff."""
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"payload does not match {model.__name__}:\n{exc}") from exc


def handoff_rel_path(target_app: str, suffix: str) -> str:
    """Repo-relative path for a handoff JSON — same convention as write_handoff's local path."""
    return f"agents/pipeline/{target_app}.{suffix}.json"


def write_handoff_artifact(
    model_instance: BaseModel,
    target_app: str,
    suffix: str,
    *,
    context: dict[str, Any] | None = None,
) -> str:
    """Write a handoff JSON via the run's artifact store (S3 when runId is set, else local disk).

    Unlike `write_handoff` (local-disk only — fine for same-container use, e.g. security-agent),
    this is for handoffs that must cross an AgentCore step boundary in the cloud pipeline, where
    the producer and consumer are separate invocations with no shared local filesystem.
    """
    from _shared.artifact_store import write_repo_artifact

    rel = handoff_rel_path(target_app, suffix)
    content = model_instance.model_dump_json(indent=2, exclude_none=False) + "\n"
    write_repo_artifact(rel, content, context=context)
    return rel


def load_handoff_artifact(
    rel_path: str,
    model: type[T],
    *,
    context: dict[str, Any] | None = None,
) -> T:
    """Read + validate a handoff JSON via the run's artifact store. Raises loudly on drift."""
    from _shared.artifact_store import read_repo_artifact

    raw_bytes = read_repo_artifact(rel_path, context=context)
    try:
        raw = json.loads(raw_bytes.decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"handoff at {rel_path} is not valid JSON: {exc}") from exc
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise HandoffValidationError(Path(rel_path), model.__name__, exc) from exc
