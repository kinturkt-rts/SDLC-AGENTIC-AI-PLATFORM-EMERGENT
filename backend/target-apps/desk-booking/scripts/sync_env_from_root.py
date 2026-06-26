"""Populate target-apps/desk-booking/.env from values already set in the project root .env.

Reads POSTGRES_MCP_* vars from the project root .env, builds a properly
URL-encoded DATABASE_URL, and writes it (plus a random ADMIN_KEY when the
placeholder is still present) into target-apps/desk-booking/.env.

The script never prints any credential — it only reports which lines were
updated.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import quote


PLACEHOLDER_DSN_MARKERS = ("user:password", "your-rds-host", "your_db_name")
PLACEHOLDER_ADMIN_KEY = "your-admin-key-here"


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE pairs from a .env file (ignoring comments and blanks)."""
    if not path.exists():
        raise FileNotFoundError(f"Expected .env at {path}")
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def build_database_url(env: dict[str, str]) -> str:
    """Build a postgresql+psycopg DSN with URL-encoded user/password."""
    required = (
        "POSTGRES_MCP_DB_ENDPOINT",
        "POSTGRES_MCP_DATABASE",
        "POSTGRES_MCP_DB_USER",
        "POSTGRES_MCP_DB_PASSWORD",
    )
    missing = [k for k in required if not env.get(k) or env[k].startswith("your")]
    if missing:
        raise RuntimeError(
            "Root .env is missing real values for: " + ", ".join(missing)
        )

    user = quote(env["POSTGRES_MCP_DB_USER"], safe="")
    password = quote(env["POSTGRES_MCP_DB_PASSWORD"], safe="")
    host = env["POSTGRES_MCP_DB_ENDPOINT"]
    port = env.get("POSTGRES_MCP_PORT", "5432")
    db = env["POSTGRES_MCP_DATABASE"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}?sslmode=require"


def update_app_env(app_env_path: Path, database_url: str) -> list[str]:
    """Rewrite DATABASE_URL and (if still placeholder) ADMIN_KEY in app .env.

    Returns the list of variable names that were updated for reporting.
    """
    if not app_env_path.exists():
        raise FileNotFoundError(f"Expected app .env at {app_env_path}")

    lines = app_env_path.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("DATABASE_URL=") and any(
            marker in stripped for marker in PLACEHOLDER_DSN_MARKERS
        ):
            new_lines.append(f"DATABASE_URL={database_url}")
            updated.append("DATABASE_URL")
            continue

        if stripped.startswith("ADMIN_KEY=") and PLACEHOLDER_ADMIN_KEY in stripped:
            new_lines.append(f"ADMIN_KEY=desk-admin-{secrets.token_hex(12)}")
            updated.append("ADMIN_KEY")
            continue

        new_lines.append(line)

    app_env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def main() -> None:
    """Sync credentials from root .env into the desk-booking .env."""
    repo_root = Path(__file__).resolve().parents[3]
    app_env = Path(__file__).resolve().parent.parent / ".env"

    root_env_values = parse_env_file(repo_root / ".env")
    database_url = build_database_url(root_env_values)
    updated = update_app_env(app_env, database_url)

    if not updated:
        print("No placeholder values found in app .env — nothing to update.")
        return

    print(f"Updated {len(updated)} variable(s) in {app_env}: {', '.join(updated)}")


if __name__ == "__main__":
    main()
