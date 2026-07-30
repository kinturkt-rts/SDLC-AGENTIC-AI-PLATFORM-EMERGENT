"""Throwaway Postgres test-schema helpers — build a schema from an app's
db/sql/*.sql for pytest to run against, with guaranteed teardown.

Shared by developer_agent.py's run_service_validation gate and
scripts/run_app_tests_pg.py (the PowerShell pipeline's end-of-run pytest step)
so both callers build/tear down throwaway schemas identically — never two
copies of this logic drifting apart.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.rds_env import connection_url  # noqa: E402


def teardown_temp_pg_schema(schema: str) -> None:
    """DROP SCHEMA <schema> CASCADE — guaranteed cleanup so a crashed or failed
    validation run never leaves an orphan throwaway schema behind on shared RDS.
    Callers must invoke this from a `finally`, never conditionally.

    Retries up to 3 times (2s, 4s between attempts) so a transient
    psycopg.OperationalError (DNS/network blip, e.g. getaddrinfo failed) doesn't
    abandon the schema on the first failure. Still never raises — teardown must
    never mask the real validation result — but only gives up (and prints the
    WARN) after all attempts are exhausted."""
    import time

    import psycopg
    from psycopg import sql as psql

    url = connection_url().replace("postgresql+psycopg://", "postgresql://")
    attempts = 3
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with psycopg.connect(url, autocommit=True, connect_timeout=15) as conn, conn.cursor() as cur:
                cur.execute(psql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(psql.Identifier(schema)))
            return
        except Exception as exc:  # never let cleanup failure mask the real validation result
            last_exc = exc
            if attempt < attempts:
                time.sleep(2 * attempt)

    print(
        f"[dev-validate] WARN: failed to drop throwaway test schema {schema!r} — "
        f"drop it manually: DROP SCHEMA {schema} CASCADE; ({last_exc!r})",
        file=sys.stderr,
    )


def _sweep_orphan_test_schemas(app: str) -> None:
    """Drop leftover throwaway test schemas for THIS app from prior failed/killed
    runs, so orphans self-heal instead of accumulating on shared RDS. Scoped to
    this app's own test_<app>_* pattern ONLY — never touches other apps' schemas,
    so it can't disrupt a concurrent pipeline run on the same RDS. Best-effort:
    never raises, never blocks setup."""
    try:
        import psycopg
        from psycopg import sql as psql

        url = connection_url().replace("postgresql+psycopg://", "postgresql://")
        pattern = f"test_{app.strip().replace('-', '_')}_%"
        with psycopg.connect(url, autocommit=True, connect_timeout=15) as conn, conn.cursor() as cur:
            cur.execute("SELECT nspname FROM pg_namespace WHERE nspname LIKE %s", (pattern,))
            orphans = [row[0] for row in cur.fetchall()]
            for name in orphans:
                cur.execute(psql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(psql.Identifier(name)))
    except Exception as exc:
        print(f"[dev-validate] WARN: orphan test-schema sweep failed for {app!r} ({exc!r})", file=sys.stderr)


def setup_temp_pg_test_schema(service_dir: Path, app: str) -> tuple[str | None, str, list[str]]:
    """Build a throwaway Postgres schema from db/sql/*.sql so the import/health/pytest
    validation steps run against the TRUE applied schema (native enums included), not
    an ORM-derived SQLite copy that can never disagree with the ORM it was built from.

    Returns (schema_name, sqlalchemy_url, errors):
      - No db/sql/ (DB-less or non-Postgres app pattern): (None, "", []) — caller keeps
        the SQLite baseline; this fix is scoped to the Postgres RDS pattern.
      - Success: (temp_schema_name, sqlalchemy_url, []) — sqlalchemy_url carries the
        "+psycopg" dialect suffix (see below) so it's ready to hand the generated
        app as DATABASE_URL.
      - Failure: (None, "", [blocking error]) — caller must fail the whole validation
        run. Never falls back to SQLite on a connection or apply failure.
    """
    import secrets

    sql_dir = service_dir / "db" / "sql"
    if not sql_dir.is_dir() or not any(sql_dir.glob("*.sql")):
        return None, "", []

    try:
        import psycopg
    except ImportError as exc:
        return None, "", [f"schema_test_setup: psycopg not installed ({exc!r})"]

    try:
        raw_url = connection_url()
    except ValueError as exc:
        return None, "", [f"schema_test_setup: {exc}"]

    # connection_url() returns a bare "postgresql://" DSN for direct psycopg use
    # (matches validate_schema_parity / apply_sql_to_rds.py). SQLAlchemy's
    # create_engine (used by the generated app's app/database.py) needs the
    # "+psycopg" dialect suffix, or it silently falls back to the (uninstalled)
    # psycopg2 driver and every subprocess step below fails at import.
    if raw_url.startswith("postgresql://"):
        sqlalchemy_url = "postgresql+psycopg://" + raw_url[len("postgresql://") :]
    else:
        sqlalchemy_url = raw_url
    probe_url = sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")
    try:
        with psycopg.connect(probe_url, autocommit=True, connect_timeout=15):
            pass
    except psycopg.OperationalError as exc:
        return None, "", [
            f"schema_test_setup: could NOT CONNECT to Postgres to build the throwaway "
            f"test schema ({exc!r}) — this usually means the AWS SSO session expired or "
            f"RDS is unreachable, NOT a code bug. Run `aws sso login --profile aryan-sdlc` "
            f"and retry. Tests must run against the real Postgres schema and cannot fall "
            f"back to SQLite."
        ]

    # DB is confirmed reachable at this point — safe to sweep this app's own
    # leftover orphan schemas from prior failed/killed runs before creating a
    # new one, so orphans self-heal instead of accumulating on shared RDS.
    _sweep_orphan_test_schemas(app)

    schema = f"test_{app.strip().replace('-', '_')}_{secrets.token_hex(3)}"

    scripts_dir = _REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from apply_sql_to_rds import apply_sql_files  # reuse the exact, already-hardened apply path

    os.environ["POSTGRES_APP_SCHEMA"] = schema
    try:
        # skip_seed=True: only the DDL files build the schema (enums included, per
        # the whole point of this function). Seed rows are deliberately excluded —
        # generated test fixtures commonly insert rows with hardcoded primary keys
        # assuming empty tables (e.g. this app's own seeded_users/sample_ticket
        # fixtures use id=1, id=100, ...); applying seed data too would collide on
        # those ids and fail tests for an unrelated reason, muddying whatever this
        # gate is actually trying to prove.
        rc = apply_sql_files(sql_dir, target_app=None, quiet=True, reset_schema=True, skip_seed=True)
    finally:
        os.environ.pop("POSTGRES_APP_SCHEMA", None)

    if rc != 0:
        teardown_temp_pg_schema(schema)
        return None, "", [
            f"schema_test_setup: failed to build throwaway schema {schema!r} from "
            f"db/sql/*.sql — rerun with APPLY_SQL_VERBOSE=1 to see the failing statement"
        ]

    return schema, sqlalchemy_url, []
