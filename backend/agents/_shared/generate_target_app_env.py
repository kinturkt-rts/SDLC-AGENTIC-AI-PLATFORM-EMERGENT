"""Generate target-apps/<app>/.env from .env.example + real RDS creds (no hand-editing).

developer-agent already writes a target-apps/<app>/.env.example per app (endpoint,
database, POSTGRES_SCHEMA, CORS_ORIGINS, ...) — everything except the DB credentials
(placeholder `user:password`) and secrets (`change-me-to-...`). This script fills
those in, using the same canonical sources apply_sql_to_rds.py and
materialize_seed_passwords.py already trust:
  - DATABASE_URL  <- _shared.rds_env.connection_url() (POSTGRES_MCP_* in .env.local),
                     scheme swapped to postgresql+psycopg:// for SQLAlchemy.
  - POSTGRES_SCHEMA <- _shared.rds_env.schema_for_app(target_app)
  - CORS_ORIGINS <- always the local dev frontends, never whatever developer-agent
    guessed into .env.example (it has been wrong before — e.g. a UI port that
    CORS-blocks a React dev server on 5173).
  - Any placeholder-looking secret (value containing "change-me") gets a fresh
    secrets.token_urlsafe(32).
Every other line in .env.example (JWT_ALGORITHM, SERVICE_NAME, Bedrock/RAG vars,
comments, blank lines, ...) is copied through unchanged.

Skip-if-exists by default: an existing target-apps/<app>/.env is never overwritten
unless --force is passed, so hand-edits made after generation are not silently wiped.

Usage:
  python agents/_shared/generate_target_app_env.py --target-app desk-booking
  python agents/_shared/generate_target_app_env.py --target-app desk-booking --force
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.rds_env import connection_url, schema_for_app  # noqa: E402
from _shared.env import load_repo_env  # noqa: E402

_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_PLACEHOLDER_RE = re.compile(r"change-me", re.IGNORECASE)

# Overridden deterministically regardless of what .env.example already has —
# these must match live infra state, not whatever the developer-agent LLM guessed.
_DETERMINISTIC_OVERRIDES = {"DATABASE_URL", "POSTGRES_SCHEMA", "CORS_ORIGINS"}

# Local Vite/React + common Next ports. Include a small 5173–5176 range because
# Vite bumps the port when another app already holds 5173 (movie-vault + property-
# manage side-by-side). Also allow 127.0.0.1 origins — browsers treat those as
# distinct from localhost for CORS.
_LOCAL_CORS_ORIGINS = (
    '["http://localhost:5173","http://localhost:5174","http://localhost:5175",'
    '"http://localhost:5176","http://localhost:3000",'
    '"http://127.0.0.1:5173","http://127.0.0.1:5174",'
    '"http://127.0.0.1:5175","http://127.0.0.1:5176"]'
)


def _app_dir(target_app: str, repo_root: Path) -> Path:
    try:
        from _shared.pipeline_context import target_app_root_rel

        app_dir = repo_root / target_app_root_rel(target_app)
    except ImportError:
        app_dir = repo_root / "target-apps" / target_app
    if not app_dir.is_dir():
        app_dir = repo_root / "target-apps" / target_app
    return app_dir


def _real_database_url() -> str:
    url = connection_url()
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def render_env(example_text: str, target_app: str) -> str:
    """Rewrite .env.example text into real .env text (line-preserving)."""
    overrides = {
        "DATABASE_URL": _real_database_url(),
        "POSTGRES_SCHEMA": schema_for_app(target_app),
        "CORS_ORIGINS": _LOCAL_CORS_ORIGINS,
    }

    out_lines: list[str] = []
    seen_deterministic: set[str] = set()
    for line in example_text.splitlines():
        match = _LINE_RE.match(line)
        if not match:
            out_lines.append(line)
            continue
        key, value = match.group(1), match.group(2)
        if key in _DETERMINISTIC_OVERRIDES:
            out_lines.append(f"{key}={overrides[key]}")
            seen_deterministic.add(key)
        elif _PLACEHOLDER_RE.search(value):
            out_lines.append(f"{key}={secrets.token_urlsafe(32)}")
        else:
            out_lines.append(line)

    # .env.example is expected to declare all of these keys; if any is missing, append it
    # so the generated .env is still runnable without hand-editing.
    for key in _DETERMINISTIC_OVERRIDES - seen_deterministic:
        out_lines.append(f"{key}={overrides[key]}")

    return "\n".join(out_lines) + "\n"


def generate(target_app: str, repo_root: Path, *, force: bool = False, quiet: bool = False) -> int:
    load_repo_env()
    app_dir = _app_dir(target_app, repo_root)
    example_path = app_dir / ".env.example"
    env_path = app_dir / ".env"

    if not example_path.is_file():
        print(f"[gen-env] SKIP: no .env.example at {example_path}", file=sys.stderr)
        return 1

    if env_path.is_file() and not force:
        if not quiet:
            print(f"[gen-env] SKIP: {env_path} already exists (pass --force to overwrite)", file=sys.stderr)
        return 0

    try:
        rendered = render_env(example_path.read_text(encoding="utf-8"), target_app)
    except ValueError as exc:
        print(f"[gen-env] FAILED: {exc}", file=sys.stderr)
        return 1

    env_path.write_text(rendered, encoding="utf-8")
    if not quiet:
        print(f"[gen-env] Wrote {env_path} (DATABASE_URL + POSTGRES_SCHEMA from .env.local; CORS_ORIGINS forced to local dev frontends; secrets regenerated)", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate target-apps/<app>/.env from .env.example + real RDS creds")
    parser.add_argument("--target-app", required=True)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT))
    parser.add_argument("--force", action="store_true", help="Overwrite an existing .env")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    return generate(args.target_app, Path(args.repo_root), force=args.force, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
