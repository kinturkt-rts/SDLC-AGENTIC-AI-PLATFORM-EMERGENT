"""Populate target-apps/bug-deduper/.env from the project root .env."""

from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import quote

PLACEHOLDER_DSN_MARKERS = ("username:password", "your-rds-host", "database_name")
PLACEHOLDER_API_KEY = "your-secret-api-key-here"
PLACEHOLDER_ADMIN_KEY = "your-admin-key-here"


def parse_env_file(path: Path) -> dict[str, str]:
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


def upsert_env_vars(app_env_path: Path, updates: dict[str, str]) -> list[str]:
    lines = app_env_path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    new_lines: list[str] = []
    updated: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                new_lines.append(f"{key}={remaining.pop(key)}")
                updated.append(key)
                continue
        new_lines.append(line)

    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")
        updated.append(key)

    app_env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def update_app_env(app_env_path: Path, database_url: str, root_env: dict[str, str]) -> list[str]:
    if not app_env_path.exists():
        raise FileNotFoundError(f"Expected app .env at {app_env_path}")

    updated: list[str] = []
    new_lines: list[str] = []

    for line in app_env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped.startswith("DATABASE_URL=") and any(
            marker in stripped for marker in PLACEHOLDER_DSN_MARKERS
        ):
            new_lines.append(f"DATABASE_URL={database_url}")
            updated.append("DATABASE_URL")
            continue

        if stripped.startswith("API_KEY=") and PLACEHOLDER_API_KEY in stripped:
            new_lines.append(f"API_KEY=bug-dedup-{secrets.token_hex(16)}")
            updated.append("API_KEY")
            continue

        if stripped.startswith("ADMIN_KEY=") and PLACEHOLDER_ADMIN_KEY in stripped:
            new_lines.append(f"ADMIN_KEY=bug-dedup-admin-{secrets.token_hex(12)}")
            updated.append("ADMIN_KEY")
            continue

        new_lines.append(line)

    app_env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    aws_updates: dict[str, str] = {}
    for key in (
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ):
        value = root_env.get(key, "").strip()
        if value and not value.startswith("your"):
            aws_updates[key] = value

    if aws_updates:
        updated.extend(upsert_env_vars(app_env_path, aws_updates))

    return updated


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    app_env = Path(__file__).resolve().parent.parent / ".env"
    example = Path(__file__).resolve().parent.parent / ".env.example"
    if not app_env.exists() and example.exists():
        app_env.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    root_env_values = parse_env_file(repo_root / ".env")
    database_url = build_database_url(root_env_values)
    updated = update_app_env(app_env, database_url, root_env_values)

    if not updated:
        print("No values to update in app .env.")
        return

    print(f"Updated {len(updated)} variable(s) in {app_env}: {', '.join(updated)}")


if __name__ == "__main__":
    main()
