"""Apply pr-diff-summarizer SQL migrations against the team RDS Postgres."""

from __future__ import annotations

from pathlib import Path

import psycopg

SCHEMA = "pr_diff_summarizer"


def load_root_env(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        raise FileNotFoundError(f"Expected .env at {env_path}")

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_conninfo(env: dict[str, str]) -> str:
    required = [
        "POSTGRES_MCP_DB_ENDPOINT",
        "POSTGRES_MCP_DATABASE",
        "POSTGRES_MCP_DB_USER",
        "POSTGRES_MCP_DB_PASSWORD",
    ]
    missing = [k for k in required if not env.get(k) or env[k].startswith("your")]
    if missing:
        raise RuntimeError(
            f"Missing or placeholder values in .env: {', '.join(missing)}"
        )

    return (
        f"host={env['POSTGRES_MCP_DB_ENDPOINT']} "
        f"port={env.get('POSTGRES_MCP_PORT', '5432')} "
        f"dbname={env['POSTGRES_MCP_DATABASE']} "
        f"user={env['POSTGRES_MCP_DB_USER']} "
        f"password={env['POSTGRES_MCP_DB_PASSWORD']} "
        f"sslmode=require"
    )


def apply_migrations() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    sql_dir = Path(__file__).resolve().parent.parent / "db" / "sql"
    env = load_root_env(repo_root / ".env")
    conninfo = build_conninfo(env)

    sql_files = sorted(sql_dir.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(f"No .sql files found in {sql_dir}")

    print(f"Connecting to {env['POSTGRES_MCP_DB_ENDPOINT']}/{env['POSTGRES_MCP_DATABASE']} ...")
    with psycopg.connect(conninfo, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
            cur.execute(f'SET search_path TO "{SCHEMA}", public')
            print(f"Schema '{SCHEMA}' ready, search_path set.\n")

            for sql_file in sql_files:
                print(f"-> {sql_file.name}", end=" ... ", flush=True)
                cur.execute(sql_file.read_text(encoding="utf-8"))
                print("ok")

    print("\nAll migrations applied successfully.")


if __name__ == "__main__":
    apply_migrations()
