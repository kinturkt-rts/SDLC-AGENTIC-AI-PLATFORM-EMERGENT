from __future__ import annotations

import base64

import pytest

from _shared.gitlab_mcp_actions import (
    _build_publish_file,
    assert_publish_python_syntax,
)


def test_assert_publish_python_syntax_accepts_valid() -> None:
    assert_publish_python_syntax(
        [{"path": "ui/streamlit_app.py", "content": "x = 1\n"}]
    )


def test_assert_publish_python_syntax_rejects_unterminated_fstring() -> None:
    bad = 'x = f"oops\n'
    with pytest.raises(ValueError, match="SyntaxError"):
        assert_publish_python_syntax([{"path": "ui/bad.py", "content": bad}])


def test_assert_publish_python_syntax_accepts_base64_py_with_escaped_newlines() -> None:
    """Regression: golden startup_checks uses \\n inside quotes; must survive publish."""
    source = (
        'raise RuntimeError(\n'
        '    "DATABASE_URL is not set. Copy .env.example to .env and add a line like:\\n"\n'
        '    "  DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db"\n'
        ")\n"
    )
    payload = _build_publish_file("app/startup_checks.py", source.encode("utf-8"))
    assert payload["binary"] is True
    decoded = base64.b64decode(payload["content"]).decode("utf-8")
    assert "\\n" in decoded
    assert_publish_python_syntax([payload])


def test_assert_publish_python_syntax_rejects_expanded_backslash_n_corruption() -> None:
    """The exact corruption GitLab text publish produced across apps (3484→3475)."""
    good = (
        'raise RuntimeError(\n'
        '    "DATABASE_URL is not set. Copy .env.example to .env and add a line like:\\n"\n'
        '    "  DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db"\n'
        ")\n"
    )
    corrupted = good.replace("\\n", "\n")
    with pytest.raises(ValueError, match="SyntaxError"):
        assert_publish_python_syntax(
            [{"path": "app/startup_checks.py", "content": corrupted, "binary": False}]
        )


def test_build_publish_file_py_is_base64_roundtrip() -> None:
    raw = b'msg = "line one\\nline two"\n'
    item = _build_publish_file("app/startup_checks.py", raw)
    assert item["binary"] is True
    assert base64.b64decode(item["content"]) == raw


def test_build_publish_file_markdown_stays_text() -> None:
    raw = b"# Hello\n"
    item = _build_publish_file("docs/PRD/demo.md", raw)
    assert item["binary"] is False
    assert item["content"] == "# Hello\n"
