"""Extract and verify client delivery requirements (UI surface, patterns) across the SDLC chain."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_STREAMLIT_MARKERS = (
    "streamlit",
    "ui/streamlit_app.py",
    "streamlit_app.py",
)
_REACT_MARKERS = ("react", "next.js", "nextjs", "vite", "frontend/")

_STREAMLIT_NEGATED = re.compile(
    r"\b(?:no|without|not|omit)\s+(?:\w+\s+){0,2}streamlit\b|"
    r"\bapi[- ]only\b|"
    r"\bno\s+ui\s+folder\b|"
    r"streamlit/react\s+ui",
    re.IGNORECASE,
)
_REACT_NEGATED = re.compile(
    r"\b(?:no|without|not|omit)\s+(?:\w+\s+){0,2}react\b|"
    r"streamlit/react\s+ui",
    re.IGNORECASE,
)


def _feature_required(text_lower: str, markers: tuple[str, ...], negated: re.Pattern[str]) -> bool:
    if negated.search(text_lower):
        return False
    return any(marker in text_lower for marker in markers)


def scan_delivery_text(text: str) -> dict[str, Any]:
    """Infer delivery profile flags from PRD, input brief, or design markdown."""
    lower = text.lower()
    requires_streamlit = _feature_required(lower, _STREAMLIT_MARKERS, _STREAMLIT_NEGATED)
    requires_react = _feature_required(lower, _REACT_MARKERS, _REACT_NEGATED)
    ui_required = (
        requires_streamlit
        or requires_react
        or "web ui" in lower
        or "browser ui" in lower
        or "client-facing portal" in lower and "api only" not in lower
    )
    ui_pattern: str | None = None
    if requires_streamlit:
        ui_pattern = "streamlit"
    elif requires_react:
        ui_pattern = "react"

    return {
        "uiRequired": ui_required,
        "requiresStreamlit": requires_streamlit,
        "requiresReact": requires_react,
        "uiPattern": ui_pattern,
        "streamlitPath": "ui/streamlit_app.py",
        "streamlitRequirementsPath": "ui/requirements.txt",
    }


def merge_delivery_profiles(*profiles: dict[str, Any]) -> dict[str, Any]:
    """Combine profiles from input brief and PRD (logical OR on requirement flags)."""
    merged: dict[str, Any] = {
        "uiRequired": False,
        "requiresStreamlit": False,
        "requiresReact": False,
        "uiPattern": None,
        "streamlitPath": "ui/streamlit_app.py",
        "streamlitRequirementsPath": "ui/requirements.txt",
    }
    for profile in profiles:
        if not profile:
            continue
        merged["uiRequired"] = bool(merged["uiRequired"] or profile.get("uiRequired"))
        merged["requiresStreamlit"] = bool(
            merged["requiresStreamlit"] or profile.get("requiresStreamlit")
        )
        merged["requiresReact"] = bool(merged["requiresReact"] or profile.get("requiresReact"))
        if profile.get("uiPattern"):
            merged["uiPattern"] = profile["uiPattern"]
    if merged["requiresStreamlit"]:
        merged["uiPattern"] = "streamlit"
    elif merged["requiresReact"] and not merged["uiPattern"]:
        merged["uiPattern"] = "react"
    merged["uiRequired"] = bool(
        merged["uiRequired"] or merged["requiresStreamlit"] or merged["requiresReact"]
    )
    return merged


def _read_optional(repo_root: Path, rel_or_abs: str | None, *, run_id: str | None = None) -> str:
    if not rel_or_abs or not str(rel_or_abs).strip():
        return ""
    rel = str(rel_or_abs).strip().lstrip("/").replace("\\", "/")

    # S3-aware read when run_id is available (cloud containers don't have local artifacts)
    if run_id:
        try:
            from .artifact_store import get_artifact
            return get_artifact(run_id, rel).decode("utf-8", errors="replace")
        except Exception:
            pass

    # Local filesystem fallback
    path = Path(rel_or_abs.strip())
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def build_delivery_profile_from_paths(
    repo_root: Path,
    *,
    prd_path: str | None = None,
    input_path: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build delivery profile from input brief and/or PRD file paths."""
    profiles: list[dict[str, Any]] = []
    input_text = _read_optional(repo_root, input_path, run_id=run_id)
    prd_text = _read_optional(repo_root, prd_path, run_id=run_id)
    if input_text:
        profiles.append(scan_delivery_text(input_text))
    if prd_text:
        profiles.append(scan_delivery_text(prd_text))
    if not profiles:
        return merge_delivery_profiles()
    return merge_delivery_profiles(*profiles)


def design_doc_includes_streamlit(design_text: str) -> bool:
    """Return True when design Stack/doc mentions Streamlit delivery."""
    lower = design_text.lower()
    return "streamlit" in lower or "ui/streamlit_app.py" in lower


def verify_design_doc(repo_root: Path, context: dict[str, Any]) -> list[str]:
    """Fail architect handoff when PRD/input require Streamlit but design omits it."""
    profile = context.get("deliveryProfile") or {}
    if not profile.get("requiresStreamlit"):
        return []

    design_rel = context.get("designDocPath") or context.get("design_doc_path")
    if not design_rel:
        return ["deliveryProfile requires Streamlit but designDocPath is missing from context"]

    run_id = context.get("runId") or context.get("run_id") or None
    design_text = _read_optional(repo_root, str(design_rel), run_id=run_id)
    if not design_text:
        return [f"deliveryProfile requires Streamlit but design doc not found: {design_rel}"]

    if design_doc_includes_streamlit(design_text):
        return []
    return [
        f"deliveryProfile.requiresStreamlit is true but {design_rel} does not include "
        "Streamlit in section 2 Stack (add: UI | Streamlit | ui/streamlit_app.py HTTP client to FastAPI)"
    ]


def verify_app_artifacts(repo_root: Path, target_app: str, context: dict[str, Any]) -> list[str]:
    """Fail developer handoff when required UI files are missing."""
    profile = context.get("deliveryProfile") or {}
    errors: list[str] = []
    if profile.get("requiresStreamlit"):
        ui_path = repo_root / "target-apps" / target_app / "ui" / "streamlit_app.py"
        if not ui_path.is_file():
            errors.append(
                f"deliveryProfile.requiresStreamlit is true but missing {ui_path.relative_to(repo_root).as_posix()}"
            )
        req_path = repo_root / "target-apps" / target_app / "ui" / "requirements.txt"
        if not req_path.is_file():
            errors.append(
                "deliveryProfile.requiresStreamlit is true but missing "
                f"{req_path.relative_to(repo_root).as_posix()}"
            )
    return errors


def load_context(context_path: Path) -> dict[str, Any]:
    """Load pipeline context JSON."""
    return json.loads(context_path.read_text(encoding="utf-8-sig"))


def sync_context_delivery_profile(
    repo_root: Path,
    context_path: Path,
    *,
    input_path: str | None = None,
) -> dict[str, Any]:
    """Merge deliveryProfile into pipeline context from PRD + input brief."""
    context = load_context(context_path)
    run_id = context.get("runId") or context.get("run_id") or None
    profile = build_delivery_profile_from_paths(
        repo_root,
        prd_path=context.get("prdPath") or context.get("prd_path"),
        input_path=input_path or context.get("inputPath") or context.get("input_path"),
        run_id=run_id,
    )
    context["deliveryProfile"] = profile
    if input_path:
        context["inputPath"] = input_path
    context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    return profile


def main() -> None:
    """CLI: verify design/app artifacts or sync deliveryProfile into context."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Verify SDLC delivery profile handoff")
    parser.add_argument("--context-file", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--input-file", default="", help="Re-scan input brief when syncing profile")
    parser.add_argument("--sync", action="store_true", help="Write deliveryProfile into context JSON")
    parser.add_argument(
        "--check",
        choices=("design", "app"),
        default="design",
        help="design: after architect; app: after developer",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print on failure",
    )
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    ctx_path = Path(args.context_file)
    if not ctx_path.is_absolute():
        ctx_path = (repo_root / ctx_path).resolve()

    if args.sync:
        input_rel = args.input_file.replace("\\", "/") if args.input_file else None
        profile = sync_context_delivery_profile(repo_root, ctx_path, input_path=input_rel)
        print(json.dumps(profile, indent=2))
        return

    context = load_context(ctx_path)
    target_app = str(context.get("targetApp") or "").strip()
    if args.check == "design":
        errors = verify_design_doc(repo_root, context)
    else:
        if not target_app:
            print("ERROR: targetApp missing from context", file=sys.stderr)
            raise SystemExit(1)
        errors = verify_app_artifacts(repo_root, target_app, context)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(1)
    if not args.quiet:
        print(f"delivery profile OK ({args.check})")


if __name__ == "__main__":
    main()
