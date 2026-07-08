"""Tests for materialize_seed_passwords SQL (psycopg placeholder safety)."""

from pathlib import Path

_MODULE = Path(__file__).resolve().parents[1] / "agents" / "_shared" / "materialize_seed_passwords.py"


def test_like_pattern_escapes_percent_for_psycopg() -> None:
    """psycopg3 rejects bare % in query strings; LIKE '$2%%' is required."""
    text = _MODULE.read_text(encoding="utf-8")
    assert text.count("NOT LIKE '$2%%'") >= 2
    stripped = text.replace("NOT LIKE '$2%%'", "")
    assert "NOT LIKE '$2%'" not in stripped
