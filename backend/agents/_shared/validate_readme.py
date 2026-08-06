"""Validate generated app README — demo credentials, not scaffold leftovers.

The developer scaffold used to copy ``target-apps/_template/README.md`` ("Service
Template / Replace this README…"). Agents often skipped rewriting it, and
``_ensure_delivery_files`` even re-copied the template at handoff — so live apps
shipped with no Demo accounts while seed SQL had the real password.

This module is the agent-facing guardrail: ``dev_validate_app`` fails → the model
must rewrite README and call validate again (same loop as SEED_SHA256 / RDS_PARITY).
"""

from __future__ import annotations

from pathlib import Path

from _shared.seed_credentials import parse_seed_credentials
from _shared.verify_seed_bcrypt import documented_password

_TEMPLATE_MARKERS = (
    "replace this readme when the developer-agent scaffolds",
    "# service template",
    "> replace this readme",
)

_PLACEHOLDER = "__BCRYPT_PLACEHOLDER__"


def _seed_sql_files(service_dir: Path) -> list[Path]:
    seed_dir = service_dir / "db" / "sql"
    if not seed_dir.is_dir():
        return []
    return [
        p
        for p in seed_dir.glob("*seed*.sql")
        if "test" not in p.name.lower()
    ]


def _seed_has_bcrypt_placeholders(service_dir: Path) -> bool:
    for path in _seed_sql_files(service_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _PLACEHOLDER in text:
            return True
    return False


def _seed_logins(service_dir: Path) -> tuple[list[str], str | None]:
    """Return (lookups, password) — username and/or email from users INSERT."""
    from _shared.seed_credentials import (
        _parse_users_insert_rows,
        _users_insert_columns,
        users_table_layout,
    )

    password: str | None = None
    lookups: list[str] = []
    for path in _seed_sql_files(service_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not password:
            password = documented_password(text)
        for user, pw, _lc, _hc in parse_seed_credentials(path):
            if user and user not in lookups:
                lookups.append(user)
            if not password:
                password = pw
        cols = _users_insert_columns(path) or []
        layout = users_table_layout(path)
        if not layout:
            continue
        _, hash_col = layout
        for col in ("username", "email"):
            if col not in cols:
                continue
            for user in _parse_users_insert_rows(path, lookup_col=col, hash_col=hash_col):
                if user and user not in lookups:
                    lookups.append(user)
    return lookups, password


def validate_readme_demo_accounts(service_dir: Path) -> list[str]:
    """Return blocking errors when README is missing, still a scaffold stub, or
    omits the seed password that users need to log in.
    """
    errors: list[str] = []
    readme = service_dir / "README.md"
    if not readme.is_file():
        errors.append(
            f"{service_dir.name}/README.md is missing — GENERATE it after seed "
            "(scaffold no longer copies the template stub). Include Demo accounts "
            "from the seed SQL password comment."
        )
        return errors

    text = readme.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    for marker in _TEMPLATE_MARKERS:
        if marker in lower:
            errors.append(
                f"{service_dir.name}/README.md is still the scaffold Service Template "
                f"(contains {marker!r}). Overwrite it with a real app README that includes "
                "setup + Demo accounts — do not leave the placeholder."
            )
            break

    if not _seed_has_bcrypt_placeholders(service_dir):
        return errors

    lookups, password = _seed_logins(service_dir)
    if not password:
        return errors

    if password not in text:
        errors.append(
            f"{service_dir.name}/README.md must document the seed password "
            f"{password!r} (exact string from `-- Password for all seed users: \"…\"` "
            "in db/sql/*seed*.sql) under Demo accounts / Seed Users — otherwise "
            "testers cannot log into the live app."
        )

    if lookups and not any(u in text for u in lookups):
        sample = ", ".join(repr(u) for u in lookups[:3])
        errors.append(
            f"{service_dir.name}/README.md must list at least one seed login "
            f"({sample} from db/sql/*seed*.sql) in the Demo accounts table."
        )

    return errors
