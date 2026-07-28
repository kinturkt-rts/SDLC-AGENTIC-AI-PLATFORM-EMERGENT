"""Tests for Streamlit UI_PARITY guards (width API + double-slash paths)."""

from __future__ import annotations

from pathlib import Path

from _shared.validate_ui_parity import (
    autofix_streamlit_api_path_slashes,
    autofix_streamlit_width_api,
    check_streamlit_no_deprecated_width_api,
    check_streamlit_no_double_slash_paths,
)


def _write_ui(app_dir: Path, body: str) -> None:
    ui_dir = app_dir / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "streamlit_app.py").write_text(body, encoding="utf-8")


def test_check_flags_width_zero(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    _write_ui(app_dir, 'st.dataframe(rows, width=0)\n')
    errors = check_streamlit_no_deprecated_width_api(app_dir)
    assert any("width=0" in e for e in errors)


def test_check_flags_width_false(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    _write_ui(app_dir, 'st.dataframe(rows, width=False)\n')
    errors = check_streamlit_no_deprecated_width_api(app_dir)
    assert any("width=0" in e for e in errors)


def test_check_flags_use_container_width(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    _write_ui(app_dir, 'st.dataframe(rows, use_container_width=True)\n')
    errors = check_streamlit_no_deprecated_width_api(app_dir)
    assert any("use_container_width" in e for e in errors)


def test_check_accepts_stretch_and_content(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    _write_ui(
        app_dir,
        'st.dataframe(rows, width="stretch")\n'
        'st.button("Save", width="content")\n',
    )
    assert check_streamlit_no_deprecated_width_api(app_dir) == []


def test_autofix_rewrites_width_zero_to_stretch(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    _write_ui(
        app_dir,
        'st.dataframe(rows, width=0)\n'
        'st.dataframe(other, width=0)\n',
    )
    fixes = autofix_streamlit_width_api(app_dir)
    assert fixes
    fixed_text = (app_dir / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "width=0" not in fixed_text
    assert fixed_text.count('width="stretch"') == 2
    # Re-running the blocking check against the repaired file must now pass clean.
    assert check_streamlit_no_deprecated_width_api(app_dir) == []


def test_autofix_rewrites_use_container_width(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    _write_ui(
        app_dir,
        'st.dataframe(rows, use_container_width=True)\n'
        'st.image(img, use_container_width=False)\n',
    )
    autofix_streamlit_width_api(app_dir)
    fixed_text = (app_dir / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "use_container_width" not in fixed_text
    assert 'width="stretch"' in fixed_text
    assert 'width="content"' in fixed_text
    assert check_streamlit_no_deprecated_width_api(app_dir) == []


def test_autofix_is_noop_on_clean_file(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    body = 'st.dataframe(rows, width="stretch")\n'
    _write_ui(app_dir, body)
    assert autofix_streamlit_width_api(app_dir) == []
    assert (app_dir / "ui" / "streamlit_app.py").read_text(encoding="utf-8") == body


def test_autofix_noop_when_no_ui_dir(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app-no-ui"
    app_dir.mkdir()
    assert autofix_streamlit_width_api(app_dir) == []


def test_check_flags_double_slash_api_paths(tmp_path: Path) -> None:
    app_dir = tmp_path / "kb-support-tickets"
    _write_ui(
        app_dir,
        'resp = _get("/api/v1/admin//status")\n'
        'resp2 = _get("/api/v1/admin//audit-log")\n',
    )
    errors = check_streamlit_no_double_slash_paths(app_dir)
    assert any("double-slash" in e for e in errors)


def test_check_accepts_single_slash_api_paths(tmp_path: Path) -> None:
    app_dir = tmp_path / "kb-support-tickets"
    _write_ui(
        app_dir,
        'resp = _get("/api/v1/admin/status")\n'
        'resp2 = _post("/api/v1/query", {"query": "x"})\n',
    )
    assert check_streamlit_no_double_slash_paths(app_dir) == []


def test_autofix_collapses_double_slash_api_paths(tmp_path: Path) -> None:
    app_dir = tmp_path / "kb-support-tickets"
    _write_ui(
        app_dir,
        'resp = _get("/api/v1/admin//status")\n'
        'hist = _get("/api/v1//query")\n'
        'login = _post("/api/v1/auth/token", {"email": "a"})\n',
    )
    fixes = autofix_streamlit_api_path_slashes(app_dir)
    assert fixes
    fixed = (app_dir / "ui" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "/api/v1/admin/status" in fixed
    assert "/api/v1/query" in fixed
    assert "//" not in fixed.replace("http://", "")
    assert check_streamlit_no_double_slash_paths(app_dir) == []


def test_autofix_path_slashes_noop_on_clean_file(tmp_path: Path) -> None:
    app_dir = tmp_path / "demo-app"
    body = 'resp = _get("/api/v1/admin/status")\n'
    _write_ui(app_dir, body)
    assert autofix_streamlit_api_path_slashes(app_dir) == []
    assert (app_dir / "ui" / "streamlit_app.py").read_text(encoding="utf-8") == body