"""Load and enrich JSON handoff context between SDLC agents."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = _REPO_ROOT / "agents" / "pipeline"
LEGACY_DESIGN_REL = "docs/design/design.md"
LEGACY_DIAGRAM_REL_DIR = "docs/diagrams/generated-diagrams"


class TargetAppRequiredError(ValueError):
    """Raised when no target app can be resolved from CLI, context, or env."""


def _is_cloud_store() -> bool:
    """True when S3 artifact store is configured (cloud pipeline runs)."""
    store = os.getenv("ARTIFACT_STORE", "").strip().lower()
    if store == "s3":
        return True
    return bool(
        os.getenv("ARTIFACT_S3_BUCKET", "").strip()
        or os.getenv("ARTIFACT_STORE_S3_BUCKET", "").strip()
    )


def artifact_layout() -> str:
    """Artifact path layout: always target-app-root for cloud; configurable for local."""
    if _is_cloud_store():
        return "target-app-root"
    explicit = os.getenv("PRODUCT_ARTIFACT_LAYOUT", "").strip().lower()
    legacy_prd = os.getenv("PRODUCT_PRD_LAYOUT", "").strip().lower()
    if explicit:
        return explicit
    if legacy_prd:
        return legacy_prd
    return "target-app-root"


def target_app_root_rel(target_app: str) -> str:
    """Root dir for app artifacts: ``<slug>/`` in cloud, ``target-apps/<slug>/`` locally."""
    slug = slugify(target_app)
    if _is_cloud_store():
        return slug
    return f"target-apps/{slug}"


def prd_rel_path_for_app(target_app: str) -> str:
    """PRD markdown path for a target app."""
    slug = slugify(target_app)
    layout = artifact_layout()
    if layout == "docs":
        return f"docs/PRD/{slug}.md"
    if layout == "target-app":
        return f"target-apps/{slug}/prd/{slug}.md"
    return f"{target_app_root_rel(slug)}/docs/PRD/{slug}.md"


def design_doc_rel_for_app(target_app: str) -> str:
    """Per-feature design doc so parallel SDLC runs do not overwrite each other."""
    slug = slugify(target_app)
    layout = artifact_layout()
    if layout == "docs":
        return f"docs/design/{slug}.md"
    if layout == "target-app":
        return f"target-apps/{slug}/design/{slug}.md"
    return f"{target_app_root_rel(slug)}/docs/design/{slug}.md"


def diagram_path_for_app(target_app: str) -> str:
    """Default PNG path for architect-agent output."""
    slug = slugify(target_app)
    layout = artifact_layout()
    if layout in {"docs", "target-app"}:
        return f"{LEGACY_DIAGRAM_REL_DIR}/{slug}.png"
    if _is_cloud_store():
        return f"{target_app_root_rel(slug)}/docs/diagrams/{slug}.png"
    return f"{target_app_root_rel(slug)}/docs/diagrams/generated-diagrams/{slug}.png"


def diagram_dir_rel_for_app(target_app: str) -> str:
    """Directory for architecture PNG exports."""
    return str(Path(diagram_path_for_app(target_app)).parent)


def input_rel_for_app(target_app: str) -> str:
    """Input brief path for a target app."""
    slug = slugify(target_app)
    if _is_cloud_store():
        return f"{slug}/inputs/{slug}.txt"
    return f"inputs/{slug}.txt"


# Essential keys accumulated in runs/<runId>/context.json across the SDLC cycle.
PIPELINE_CONTEXT_FIELDS = (
    "runId",
    "targetApp",
    "targetAppDir",
    "inputFile",
    "inputPath",
    "prdPath",
    "productAgentOutput",
    "designDocPath",
    "diagramPaths",
    "architectSummary",
    "deliveryProfile",
    "dbOutputDir",
    "preferredSqlPath",
    "preferredNoSqlPath",
    "databaseHandoffPath",
    "dbBackend",
    "developerHandoffPath",
    "jiraProjectKey",
    "jiraKey",
)


CANONICAL_RUN_CONTEXT_REL = "context.json"


def is_pipeline_context_rel(rel_path: str) -> bool:
    """True for per-app handoff JSON (local repo, legacy run copy, or cloud <slug>/context.json)."""
    rel = rel_path.replace("\\", "/").lstrip("/")
    if rel.endswith(".context.json") and "agents/pipeline/" in rel:
        return True
    parts = rel.split("/")
    if len(parts) == 2 and parts[1] == "context.json":
        return True
    return False


def pipeline_context_rel_for_app(target_app: str) -> str:
    """Handoff JSON path shared across the SDLC chain."""
    slug = slugify(target_app)
    if _is_cloud_store():
        return f"{slug}/context.json"
    if artifact_layout() == "target-app-root":
        return f"{target_app_root_rel(slug)}/agents/pipeline/{slug}.context.json"
    return f"agents/pipeline/{slug}.context.json"


def gitlab_handoff_rel_for_app(target_app: str) -> str:
    slug = slugify(target_app)
    if _is_cloud_store():
        return f"{slug}/handoffs/gitlab-handoff.json"
    if artifact_layout() == "target-app-root":
        return f"{target_app_root_rel(slug)}/agents/pipeline/{slug}.gitlab-handoff.json"
    return f"agents/pipeline/{slug}.gitlab-handoff.json"


def qa_handoff_rel_for_app(target_app: str) -> str:
    slug = slugify(target_app)
    if _is_cloud_store():
        return f"{slug}/handoffs/qa-handoff.json"
    if artifact_layout() == "target-app-root":
        return f"{target_app_root_rel(slug)}/agents/pipeline/{slug}.qa-handoff.json"
    return f"agents/pipeline/{slug}.qa-handoff.json"


def slugify(text: str) -> str:
    """Convert text to a kebab-case app slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug[:60].rstrip("-")
    if not slug:
        raise ValueError(f"cannot derive app slug from: {text!r}")
    return slug


def infer_target_app_from_context(context: dict[str, Any] | None) -> str | None:
    """Derive targetApp from context fields written by product-agent or pipeline JSON."""
    if not context:
        return None

    for key in ("targetApp", "target_app", "serviceName"):
        value = context.get(key)
        if value and str(value).strip():
            return slugify(str(value).strip())

    prd = context.get("prdPath") or context.get("prd_path")
    if prd and str(prd).strip():
        stem = Path(str(prd).strip()).stem
        if stem:
            return slugify(stem)

    ctx_file = context.get("_contextFile")
    if ctx_file and str(ctx_file).strip():
        name = Path(str(ctx_file).strip()).name
        if name.endswith(".context.json"):
            return slugify(name[: -len(".context.json")])

    design = context.get("designDocPath") or context.get("design_doc_path")
    if design and str(design).strip():
        stem = Path(str(design).strip()).stem
        if stem:
            return slugify(stem)

    return None


def resolve_target_app(
    cli_name: str | None,
    context: dict[str, Any] | None,
    *,
    env_var: str = "PIPELINE_TARGET_APP",
) -> str:
    """Resolve target app from CLI flag, context JSON, or env — never a hardcoded default."""
    if cli_name and cli_name.strip():
        return slugify(cli_name.strip())

    inferred = infer_target_app_from_context(context)
    if inferred:
        return inferred

    env_name = os.getenv(env_var, "").strip()
    if env_name:
        return slugify(env_name)

    raise TargetAppRequiredError(
        "targetApp is required. Pass --target-app <name>, include targetApp in context "
        "(product-agent writes agents/pipeline/<feature>.context.json), pass "
        "--context-file agents/pipeline/<feature>.context.json, or set "
        f"{env_var} / PIPELINE_TARGET_APP."
    )


def resolve_design_doc_path(context: dict[str, Any] | None) -> str:
    """Resolve designDocPath from context, targetApp, or env override."""
    if context:
        explicit = context.get("designDocPath") or context.get("design_doc_path")
        if explicit and str(explicit).strip():
            return str(explicit).strip()
        app = infer_target_app_from_context(context)
        if app:
            return design_doc_rel_for_app(app)
    env = os.getenv("ARCHITECT_DESIGN_OUTPUT_PATH", "").strip()
    if env:
        return env
    raise TargetAppRequiredError(
        "designDocPath requires targetApp in context, or set ARCHITECT_DESIGN_OUTPUT_PATH."
    )


def pipeline_context_candidates(target_app: str) -> list[Path]:
    slug = slugify(target_app)
    env_path = os.getenv("PIPELINE_CONTEXT_FILE", os.getenv("DATABASE_CONTEXT_FILE", "")).strip()
    paths: list[Path] = []
    if env_path:
        paths.append(Path(env_path))
    paths.extend(
        [
            _REPO_ROOT / pipeline_context_rel_for_app(slug),
            PIPELINE_DIR / f"{slug}.context.json",
        ]
    )
    seen: set[str] = set()
    unique: list[Path] = []
    for item in paths:
        key = str(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def load_pipeline_context(target_app: str) -> dict[str, Any] | None:
    for candidate in pipeline_context_candidates(target_app):
        path = candidate if candidate.is_absolute() else (_REPO_ROOT / candidate).resolve()
        if not path.is_file():
            continue
        try:
            parsed = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(parsed, dict):
            parsed.setdefault("_contextFile", repo_rel(path))
            return parsed
    return None


def architect_summary_from_design(
    design_rel: str,
    context: dict[str, Any] | None = None,
) -> str:
    path = (_REPO_ROOT / design_rel).resolve()
    text = ""
    if path.is_file():
        text = path.read_text(encoding="utf-8")
    elif context:
        from _shared.artifact_store import read_repo_artifact, resolve_run_id

        run_id = resolve_run_id(context)
        if run_id:
            try:
                text = read_repo_artifact(design_rel, context=context).decode("utf-8")
            except FileNotFoundError:
                return ""
    else:
        return ""

    lines = text.splitlines()
    summary_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if summary_lines:
                break
            if stripped.startswith("#"):
                summary_lines.append(stripped.lstrip("#").strip())
            continue
        summary_lines.append(stripped)
        if len(summary_lines) >= 4:
            break
    return " ".join(summary_lines)[:500]


def discover_diagram_paths(target_app: str) -> list[str]:
    slug = slugify(target_app)
    candidates = [
        diagram_path_for_app(slug),
        f"{LEGACY_DIAGRAM_REL_DIR}/{slug}.png",
        f"target-apps/{slug}/docs/diagrams/generated-diagrams/{slug}.png",
        f"target-apps/{slug}/docs/diagrams/{slug}.png",
    ]
    seen: set[str] = set()
    found: list[str] = []
    for rel in candidates:
        if rel in seen:
            continue
        seen.add(rel)
        path = _REPO_ROOT / rel
        if path.is_file():
            found.append(repo_rel(path))
    return found


def enrich_handoff_context(ctx: dict[str, Any], *, include_db_paths: bool = False) -> dict[str, Any]:
    """Fill standard paths; optional db/sql paths when present on disk."""
    app = infer_target_app_from_context(ctx)
    if not app:
        raise TargetAppRequiredError(
            "enrich_handoff_context requires targetApp (or prdPath) in context."
        )
    slug = slugify(app)
    ctx.setdefault("targetApp", slug)

    desired_design = design_doc_rel_for_app(slug)
    current = ctx.get("designDocPath") or ctx.get("design_doc_path")
    if not current or str(current).strip() in (LEGACY_DESIGN_REL, ""):
        ctx["designDocPath"] = desired_design
    else:
        ctx.setdefault("designDocPath", desired_design)

    if not ctx.get("prdPath") and not ctx.get("prd_path"):
        for rel in (
            prd_rel_path_for_app(slug),
            f"docs/PRD/{slug}.md",
            f"target-apps/{slug}/prd/{slug}.md",
        ):
            prd = _REPO_ROOT / rel
            if prd.is_file():
                ctx["prdPath"] = repo_rel(prd)
                break

    if not ctx.get("diagramPaths"):
        discovered = discover_diagram_paths(slug)
        ctx["diagramPaths"] = discovered or [diagram_path_for_app(slug)]

    if not ctx.get("architectSummary"):
        summary = architect_summary_from_design(str(ctx["designDocPath"]), ctx)
        if summary:
            ctx["architectSummary"] = summary

    if include_db_paths:
        service_dir = _REPO_ROOT / "target-apps" / slug
        db_dir = service_dir / "db"
        sql_dir = db_dir / "sql"
        if db_dir.is_dir():
            ctx.setdefault("dbOutputDir", repo_rel(db_dir))
        if sql_dir.is_dir():
            ctx.setdefault("preferredSqlPath", repo_rel(sql_dir))
        handoff = db_dir / "HANDOFF.md"
        if handoff.is_file():
            ctx.setdefault("databaseHandoffPath", repo_rel(handoff))

        from _shared.artifact_store import enrich_db_paths_from_run, resolve_run_id

        if resolve_run_id(ctx):
            enrich_db_paths_from_run(ctx)

    return ctx


def merge_run_handoff_context(
    context: dict[str, Any] | None,
    *,
    include_db_paths: bool = False,
) -> dict[str, Any]:
    """Merge runs/<runId>/context.json with incoming Context; fill standard handoff paths."""
    from _shared.artifact_store import get_context, resolve_run_id

    ctx = dict(context or {})
    run_id = resolve_run_id(ctx) or os.getenv("PIPELINE_RUN_ID", "").strip() or None
    if run_id:
        app_hint = infer_target_app_from_context(ctx)
        stored = get_context(run_id, target_app=app_hint)
        if stored:
            merged = dict(stored)
            for key, value in ctx.items():
                if value is not None and value != "":
                    merged[key] = value
            ctx = merged
        ctx.setdefault("runId", run_id)

    enrich_handoff_context(ctx, include_db_paths=include_db_paths)
    return ctx


def resolve_cli_context(
    cli_target_app: str | None,
    parsed_extra: dict[str, Any] | None,
    *,
    no_auto_context: bool,
    env_var: str = "PIPELINE_TARGET_APP",
) -> tuple[dict[str, Any], str]:
    """Merge --context-file/json with auto-loaded pipeline JSON; return (extra, target_app)."""
    extra: dict[str, Any] = dict(parsed_extra) if parsed_extra else {}

    prelim_hint: str | None = None
    if cli_target_app and cli_target_app.strip():
        prelim_hint = slugify(cli_target_app.strip())
    else:
        prelim_hint = infer_target_app_from_context(extra)

    if not extra and not no_auto_context and prelim_hint:
        auto = load_pipeline_context(prelim_hint)
        if auto:
            extra = auto

    app = resolve_target_app(cli_target_app, extra or None, env_var=env_var)
    extra.setdefault("targetApp", app)
    return extra, app


def repo_rel(path: Path) -> str:
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()
