"""Run a target-app's pytest suite against a throwaway Postgres schema.

Used by the local PowerShell pipeline (run-sdlc-local.ps1's Invoke-LocalVerify)
in place of running pytest directly on SQLite. SQLite silently accepts values a
real Postgres native enum would reject, which made ORM-vs-DDL drift (a column
the SQL declares as a native ENUM but the ORM types as a plain String) invisible
to pytest. See agents/_shared/pg_test_schema.py for the setup/teardown mechanics
(the same ones developer_agent.py's own validation gate uses) and
target-apps/_template/tests/conftest_reference.py for why generated apps'
conftest.py now requires a real Postgres DATABASE_URL.

Usage (from backend/, REPO venv — this script imports _shared and scripts/
apply_sql_to_rds, neither of which is installed in a target-app's own venv):
  python scripts/run_app_tests_pg.py --target-app support-sla-desk
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env

load_repo_env()

from _shared.pg_test_schema import setup_temp_pg_test_schema, teardown_temp_pg_schema


def _python_for_app(app_dir: Path) -> str:
    """App's own venv if present, else the repo venv, else bare "python" on PATH.

    Unlike this script itself (which must run on the repo venv to import
    _shared/scripts), the pytest subprocess needs the APP's own installed
    dependencies (fastapi, sqlalchemy, psycopg, the app's requirements.txt) —
    mirrors developer_agent.py's _python_for_service.
    """
    if platform.system() == "Windows":
        venv_python = app_dir / ".venv" / "Scripts" / "python.exe"
        repo_python = _REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = app_dir / ".venv" / "bin" / "python"
        repo_python = _REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)
    if repo_python.is_file():
        return str(repo_python)
    return "python"


def run_app_tests_pg(target_app: str) -> int:
    app_dir = _REPO_ROOT / "target-apps" / target_app
    if not app_dir.is_dir():
        print(f"[run_app_tests_pg] target-apps/{target_app}/ does not exist", file=sys.stderr)
        return 1

    schema, database_url, errors = setup_temp_pg_test_schema(app_dir, target_app)
    if errors:
        for err in errors:
            print(f"[run_app_tests_pg] {err}", file=sys.stderr)
        return 1

    try:
        env = {**os.environ}
        env["APP_ENV"] = "test"
        env["SKIP_STARTUP_CHECKS"] = "1"
        if database_url:
            env["DATABASE_URL"] = database_url
            if schema:
                env["POSTGRES_SCHEMA"] = schema
        else:
            # No db/sql/ (DB-less or non-Postgres app pattern) — nothing to build a
            # throwaway schema from; same harmless fallback developer_agent.py's
            # _validation_env uses for this case.
            env["DATABASE_URL"] = "sqlite:///:memory:"

        python_cmd = _python_for_app(app_dir)
        result = subprocess.run(
            [python_cmd, "-m", "pytest", "tests/", "-q", "--tb=line"],
            cwd=str(app_dir),
            env=env,
        )
        return result.returncode
    finally:
        # Guaranteed teardown even if pytest fails, times out (no timeout is set
        # here — the PowerShell caller has no timeout on this step either), or
        # the subprocess itself crashes: this finally is host-side Python, never
        # skipped by anything happening inside the pytest child process.
        if schema:
            teardown_temp_pg_schema(schema)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a target-app's pytest suite against a throwaway Postgres schema."
    )
    parser.add_argument("--target-app", required=True, help="Folder under target-apps/")
    args = parser.parse_args()
    return run_app_tests_pg(args.target_app)


if __name__ == "__main__":
    raise SystemExit(main())
