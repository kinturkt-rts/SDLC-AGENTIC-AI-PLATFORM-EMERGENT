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
DEFAULT_DIAGRAM_REL_DIR = "docs/diagrams/generated-diagrams"


class TargetAppRequiredError(ValueError):
    """Raised when no target app can be resolved from CLI, context, or env."""


def diagram_path_for_app(target_app: str) -> str:
    """Default PNG path for architect-agent output (AWS Diagram MCP workspace)."""
    return f"{DEFAULT_DIAGRAM_REL_DIR}/{slugify(target_app)}.png"


def design_doc_rel_for_app(target_app: str) -> str:
    """Per-feature design doc so parallel SDLC runs do not overwrite each other."""
    return f"docs/design/{slugify(target_app)}.md"


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
    paths.extend([PIPELINE_DIR / f"{slug}.context.json"])
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


def architect_summary_from_design(design_rel: str) -> str:
    path = (_REPO_ROOT / design_rel).resolve()
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
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
    path = _REPO_ROOT / DEFAULT_DIAGRAM_REL_DIR / f"{slug}.png"
    if path.is_file():
        return [repo_rel(path)]
    return []


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
        prd = _REPO_ROOT / "docs" / "PRD" / f"{slug}.md"
        if prd.is_file():
            ctx["prdPath"] = repo_rel(prd)

    if not ctx.get("diagramPaths"):
        discovered = discover_diagram_paths(slug)
        if discovered:
            ctx["diagramPaths"] = discovered

    if not ctx.get("architectSummary"):
        summary = architect_summary_from_design(str(ctx["designDocPath"]))
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
