"""Derive the app's auth model (JWT vs API-key) deterministically from the design doc.

Mirrors delivery_profile.py's approach: a marker-based scan over doc text, never an
LLM judgment call. Unlike delivery_profile (which scans the input brief + PRD before
architect-agent runs), authMode is derived from the **design doc** after architect-agent
writes it — the design doc's Rules/API-surface Auth line is where the concrete auth
decision is finalized (architect-agent resolves brief/PRD ambiguity into one choice).

Consumption (database-agent / developer-agent / frontend-agent branching on authMode)
is intentionally NOT wired yet — this module only derives, stores authMode in pipeline
context, and logs it so the value is visible on every run.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT / "agents") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "agents"))

# Lines that declare the auth scheme, e.g.:
#   | Auth | JWT HS256 + bcrypt >=12 | `app/routers/auth.py`, `app/deps.py` |
#   | Auth | API key headers |
#   - Auth: X-User-Token header for employees, X-Admin-Key for admin routes (/blackouts)
#   - Auth (FR-1, NFR-2): JWT HS256 with 24h expiry; ...
#   - **Auth (NFR-3)**: All routes require valid credential; ... X-Api-Key ...
# \**  handles a **bold**-markdown "Auth" label (the leading ** appears between
# the bullet marker and the word — without it, expense-tracker's actual auth
# line was invisible to this regex and its header names never got extracted).
# Scoped to these lines only (not the whole doc) so an unrelated "API key" mention
# elsewhere (e.g. a third-party integration in an Infra section) can't flip the mode.
_AUTH_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\|\s*)?\**auth(?:entication)?\**\b.*$",
    re.IGNORECASE | re.MULTILINE,
)

_JWT_MARKER_RE = re.compile(
    r"\bjwt\b|json\s+web\s+token|\bpyjwt\b|python-jose",
    re.IGNORECASE,
)

# A JWT marker mentioned only to rule it out — "Custom header dependency (PyJWT
# not used)", "no JWT", "without JWT" — must NOT flip mode to jwt. Real example
# that motivated this: expense-tracker's design doc literally says "PyJWT not
# used" while describing its actual api-key/X-Employee-Token scheme; a bare
# substring match on "pyjwt" alone misread that as a jwt app.
_JWT_NEGATED_RE = re.compile(
    r"\b(?:no|not|without)\s+(?:\w+\s+){0,3}(?:jwt|pyjwt|json\s+web\s+token|python-jose)\b|"
    r"\b(?:jwt|pyjwt|json\s+web\s+token|python-jose)\s+(?:is\s+|are\s+)?not\s+(?:used|needed|required)\b",
    re.IGNORECASE,
)

# api-key / api key / token-header / shared api key, plus custom header names
# shaped like X-<word>-Key or X-<word>-Token (X-API-Key, X-User-Token, X-Admin-Key, ...).
_API_KEY_MARKER_RE = re.compile(
    r"api[- ]key|x-[a-z0-9]+-(?:key|token)|token-header|shared\s+api\s+key",
    re.IGNORECASE,
)


def derive_auth_mode(design_text: str) -> str:
    """Return "jwt" (default) or "api-key", scanning only the doc's Auth line(s).

    Rules (in order):
      1. No Auth line at all                        -> "jwt"
      2. Auth line(s) mention JWT, not negated       -> "jwt"  (JWT wins on conflict — safe default)
      3. Auth line(s) mention API-key/token-header/X-*-Key/X-*-Token -> "api-key"
      4. Auth line(s) present but neither marker matches (or the only JWT
         mention is negated, e.g. "PyJWT not used")  -> "jwt"
    """
    auth_lines = _AUTH_LINE_RE.findall(design_text)
    if not auth_lines:
        return "jwt"
    auth_text = "\n".join(auth_lines)
    if _JWT_MARKER_RE.search(auth_text) and not _JWT_NEGATED_RE.search(auth_text):
        return "jwt"
    if _API_KEY_MARKER_RE.search(auth_text):
        return "api-key"
    return "jwt"


_HEADER_TOKEN_RE = re.compile(r"\bX-[A-Za-z0-9][A-Za-z0-9-]*\b")


def extract_named_headers(design_text: str) -> set[str]:
    """Return every X-<Name> header token named on the design doc's Auth line(s)
    — e.g. {"X-User-Token", "X-Admin-Key"} for desk-booking, {"X-API-Key"} for
    contacts-api. Empty set when the design doesn't name a specific header at all
    (the X-API-Key baseline needs no extra check beyond the existing auth-mode
    gates in that case).

    Same deterministic Auth-line scope as derive_auth_mode() — never an LLM
    guess. Used as the "expected headers" source for developer_agent's
    validate_auth_header_names gate, which catches a generated app silently
    substituting require_api_key's X-API-Key for a differently-named header
    the design actually specifies.
    """
    auth_lines = _AUTH_LINE_RE.findall(design_text)
    if not auth_lines:
        return set()
    auth_text = "\n".join(auth_lines)
    return set(_HEADER_TOKEN_RE.findall(auth_text))


def _read_optional(repo_root: Path, rel_or_abs: str | None, *, run_id: str | None = None) -> str:
    if not rel_or_abs or not str(rel_or_abs).strip():
        return ""
    rel = str(rel_or_abs).strip().lstrip("/").replace("\\", "/")

    if run_id:
        try:
            from _shared.artifact_store import get_artifact

            return get_artifact(run_id, rel).decode("utf-8", errors="replace")
        except Exception:
            pass

    path = Path(rel_or_abs.strip())
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def load_context(context_path: Path) -> dict[str, Any]:
    from _shared.pipeline_context import read_context_json

    return read_context_json(context_path)


def sync_context_auth_mode(repo_root: Path, context_path: Path) -> str:
    """Derive authMode from context's designDocPath and write it into context JSON."""
    context = load_context(context_path)
    run_id = context.get("runId") or context.get("run_id") or None
    design_rel = context.get("designDocPath") or context.get("design_doc_path")
    design_text = _read_optional(repo_root, design_rel, run_id=run_id) if design_rel else ""
    auth_mode = derive_auth_mode(design_text)
    context["authMode"] = auth_mode
    context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    return auth_mode


def main() -> None:
    """CLI: sync authMode into pipeline context JSON."""
    import argparse

    parser = argparse.ArgumentParser(description="Derive and sync authMode into pipeline context")
    parser.add_argument("--context-file", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--sync", action="store_true", help="Write authMode into context JSON")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    ctx_path = Path(args.context_file)
    if not ctx_path.is_absolute():
        ctx_path = (repo_root / ctx_path).resolve()

    if not args.sync:
        parser.error("--sync is required (no other mode implemented yet)")

    auth_mode = sync_context_auth_mode(repo_root, ctx_path)
    print(f"[pipeline] authMode: {auth_mode}")


if __name__ == "__main__":
    main()
