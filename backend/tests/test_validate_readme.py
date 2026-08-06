"""Tests for README demo-account guardrail (scaffold stub / missing credentials)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.validate_readme import validate_readme_demo_accounts  # noqa: E402


def test_missing_readme_fails() -> None:
    # empty tmp-like dir via Path that has no README — use a fresh subpath under repo tmp
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        service = Path(td) / "conference-speaker"
        service.mkdir()
        errors = validate_readme_demo_accounts(service)
        assert any("missing" in e.lower() for e in errors)


def test_template_stub_readme_fails(tmp_path: Path) -> None:
    service = tmp_path / "conference-speaker"
    service.mkdir()
    (service / "README.md").write_text(
        "# Service Template\n\n"
        "> Replace this README when the developer-agent scaffolds a real service.\n",
        encoding="utf-8",
    )
    errors = validate_readme_demo_accounts(service)
    assert any("scaffold" in e.lower() or "service template" in e.lower() for e in errors)


def test_bcrypt_seed_requires_password_and_username_in_readme(tmp_path: Path) -> None:
    service = tmp_path / "conference-speaker"
    sql = service / "db" / "sql"
    sql.mkdir(parents=True)
    (sql / "007_seed.sql").write_text(
        '-- Password for all seed users: "ConferencePass2024!"\n'
        "INSERT INTO users (id, username, email, password_hash, role, is_active) VALUES\n"
        "    ('a1b2c3d4-0001-4000-a000-000000000001', 'admin', 'admin@example.com', "
        "'__BCRYPT_PLACEHOLDER__', 'admin', TRUE);\n",
        encoding="utf-8",
    )
    (service / "README.md").write_text(
        "# Conference Speaker\n\nSetup uvicorn and open /docs.\n",
        encoding="utf-8",
    )
    errors = validate_readme_demo_accounts(service)
    assert any("ConferencePass2024!" in e for e in errors)
    assert any("admin" in e for e in errors)


def test_readme_with_demo_accounts_passes(tmp_path: Path) -> None:
    service = tmp_path / "conference-speaker"
    sql = service / "db" / "sql"
    sql.mkdir(parents=True)
    (sql / "007_seed.sql").write_text(
        '-- Password for all seed users: "ConferencePass2024!"\n'
        "INSERT INTO users (id, username, email, password_hash, role, is_active) VALUES\n"
        "    ('a1b2c3d4-0001-4000-a000-000000000001', 'admin', 'admin@example.com', "
        "'__BCRYPT_PLACEHOLDER__', 'admin', TRUE);\n",
        encoding="utf-8",
    )
    (service / "README.md").write_text(
        "# Conference Speaker\n\n"
        "## Demo accounts\n\n"
        "| Username | Password | Role |\n"
        "| --- | --- | --- |\n"
        "| admin | ConferencePass2024! | admin |\n",
        encoding="utf-8",
    )
    assert validate_readme_demo_accounts(service) == []
