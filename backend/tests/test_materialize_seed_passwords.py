"""Tests for materialize_seed_passwords: schema-agnostic RDS placeholder scan/repair.

Regression context: four separate pipeline failures (fitness-tracker integer-PK,
support-knowledge-hub no-login-column, legal-doc-qa UNIQUE api_keys.key_hash, and
others) all traced back to the same design flaw — this module used to require
parsing seed SQL for a users-table login column before it would materialize
anything, and hard-failed whenever database-agent produced a schema shape that
parser didn't anticipate. It has been rewritten to check/repair live RDS directly
(any table, any text/varchar column) instead of predicting table shape from SQL text.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared import materialize_seed_passwords as mod  # noqa: E402


def _fake_conn(cur: MagicMock) -> MagicMock:
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur
    return conn


def test_find_remaining_placeholder_columns_checks_every_table_not_just_users(
    monkeypatch,
) -> None:
    """The scan must not be scoped to a 'users' table — that scoping is exactly what
    caused api_keys.key_hash placeholders to go undetected in the legal-doc-qa run."""
    monkeypatch.setattr(mod, "schema_for_app", lambda app: "myapp")
    monkeypatch.setattr(mod, "connection_url", lambda: "postgresql://fake")

    cur = MagicMock()
    cur.fetchall.return_value = [
        ("users", "password_hash"),
        ("api_keys", "key_hash"),
        ("users", "email"),
    ]
    cur.fetchone.side_effect = [(False,), (True,), (False,)]
    monkeypatch.setattr(mod, "_connect", lambda url: _fake_conn(cur))

    result = mod.find_remaining_placeholder_columns("myapp")
    assert result == [("api_keys", "key_hash")]


def test_materialize_columns_in_place_gives_each_row_a_distinct_hash(monkeypatch) -> None:
    """UNIQUE-constrained columns (e.g. api_keys.key_hash) need a fresh hash per row,
    not one shared digest reused for every row — a shared digest previously collided
    on the UNIQUE constraint and failed the whole apply."""
    import bcrypt

    monkeypatch.setattr(mod, "schema_for_app", lambda app: "myapp")
    monkeypatch.setattr(mod, "connection_url", lambda: "postgresql://fake")

    cur = MagicMock()
    cur.fetchall.return_value = [("ctid-1",), ("ctid-2",), ("ctid-3",)]
    monkeypatch.setattr(mod, "_connect", lambda url: _fake_conn(cur))

    mod._materialize_columns_in_place("myapp", [("api_keys", "key_hash")], "SharedPass123!")

    # call 0 = SELECT ctid; calls 1-3 = one UPDATE per row
    update_calls = cur.execute.call_args_list[1:]
    assert len(update_calls) == 3
    digests = [call.args[1][0] for call in update_calls]
    assert len(set(digests)) == 3, "each row must get its own freshly-salted hash"
    for digest in digests:
        assert bcrypt.checkpw(b"SharedPass123!", digest.encode("utf-8"))


def test_materialize_skips_rds_repair_when_preprocessing_already_succeeded(
    monkeypatch, tmp_path: Path
) -> None:
    """Common case: apply_sql_to_rds.py's pre-apply preprocessing already replaced
    every occurrence before the INSERT ran, so materialize() must not touch RDS again
    to repair anything — the live scan finding nothing is success by itself."""
    monkeypatch.setattr(mod, "load_target_app_env", lambda *a, **k: None)
    monkeypatch.setattr(mod, "find_remaining_placeholder_columns", lambda app: [])

    repaired = []
    monkeypatch.setattr(
        mod, "_materialize_columns_in_place", lambda *a, **k: repaired.append(a)
    )

    errors = mod.materialize("myapp", tmp_path)
    assert errors == []
    assert repaired == [], "no RDS repair call needed when nothing is left to fix"


def test_materialize_repairs_and_reverifies_when_placeholder_still_present(
    monkeypatch, tmp_path: Path
) -> None:
    """Fallback path: preprocessing did not run (e.g. bcrypt missing at apply time).
    materialize() must repair in place and then re-check, without ever needing to
    parse seed SQL for a login column."""
    monkeypatch.setattr(mod, "load_target_app_env", lambda *a, **k: None)

    calls = {"n": 0}

    def fake_find(app: str) -> list[tuple[str, str]]:
        calls["n"] += 1
        return [("api_keys", "key_hash")] if calls["n"] == 1 else []

    monkeypatch.setattr(mod, "find_remaining_placeholder_columns", fake_find)
    repaired = []
    monkeypatch.setattr(
        mod, "_materialize_columns_in_place", lambda *a, **k: repaired.append(a)
    )

    errors = mod.materialize("myapp", tmp_path)
    assert errors == []
    assert len(repaired) == 1
    assert calls["n"] == 2


def test_materialize_fails_strict_when_placeholder_survives_repair(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(mod, "load_target_app_env", lambda *a, **k: None)
    monkeypatch.setattr(
        mod, "find_remaining_placeholder_columns", lambda app: [("api_keys", "key_hash")]
    )
    monkeypatch.setattr(mod, "_materialize_columns_in_place", lambda *a, **k: None)

    errors = mod.materialize("myapp", tmp_path, strict=True)
    assert len(errors) == 1
    assert "api_keys.key_hash" in errors[0]