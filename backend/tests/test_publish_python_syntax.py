from __future__ import annotations

import pytest

from _shared.gitlab_mcp_actions import assert_publish_python_syntax


def test_assert_publish_python_syntax_accepts_valid() -> None:
    assert_publish_python_syntax(
        [{"path": "ui/streamlit_app.py", "content": "x = 1\n"}]
    )


def test_assert_publish_python_syntax_rejects_unterminated_fstring() -> None:
    bad = 'x = f"oops\n'
    with pytest.raises(ValueError, match="SyntaxError"):
        assert_publish_python_syntax([{"path": "ui/bad.py", "content": bad}])
