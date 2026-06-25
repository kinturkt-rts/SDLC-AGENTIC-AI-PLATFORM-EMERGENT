"""Tests for agents/_shared/validate_ui_parity.py and api_surface.py."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.api_surface import (  # noqa: E402
    is_streamlit_ui_route,
    parse_design_api_surface,
    requires_streamlit,
)
from _shared.validate_ui_parity import (  # noqa: E402
    check_post_create_has_list_get,
    check_streamlit_list_coverage,
    validate_ui_parity_blocking,
)


def test_parse_facility_design_surface() -> None:
    design = _REPO_ROOT / "docs" / "design" / "facility-work-order-hub.md"
    routes = parse_design_api_surface(design)
    methods_paths = {(m, p) for m, p in routes}
    assert ("GET", "/api/v1/work-orders") in methods_paths
    assert ("POST", "/api/v1/sites") in methods_paths


def test_streamlit_ui_route_heuristic() -> None:
    assert is_streamlit_ui_route("GET", "/api/v1/work-orders")
    assert not is_streamlit_ui_route("GET", "/api/v1/work-orders/{id}")
    assert not is_streamlit_ui_route("POST", "/api/v1/sites")


def test_requires_streamlit_from_context() -> None:
    app_dir = _REPO_ROOT / "target-apps" / "facility-work-order-hub"
    assert requires_streamlit("facility-work-order-hub", app_dir, _REPO_ROOT)


def test_post_without_list_get_detected(tmp_path: Path) -> None:
    app = tmp_path / "mini-app"
    routers = app / "app" / "routers"
    routers.mkdir(parents=True)
    (app / "app").mkdir(exist_ok=True)
    (app / "app" / "main.py").write_text(
        'from app.routers import sites\n'
        'application.include_router(sites.router, prefix="/api/v1/sites")\n',
        encoding="utf-8",
    )
    (routers / "sites.py").write_text(
        '@router.post("")\ndef create(): ...\n',
        encoding="utf-8",
    )
    # inject router import hack - collect_implemented_routes needs @router in file
    (routers / "sites.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
        '@router.post("")\ndef create():\n    pass\n',
        encoding="utf-8",
    )
    errors = check_post_create_has_list_get(app, streamlit_required=True)
    assert any("GET /api/v1/sites" in e for e in errors)


def test_facility_work_order_hub_fails_ui_parity() -> None:
    """Documents known UI gaps on the stress-test app (optional fixture)."""
    app = _REPO_ROOT / "target-apps" / "facility-work-order-hub"
    if not app.is_dir():
        pytest.skip("target-apps/facility-work-order-hub not present")
    errors = validate_ui_parity_blocking(app, _REPO_ROOT)
    assert errors  # sites list, streamlit gaps, etc.


def test_desk_booking_api_only_skips_streamlit_checks() -> None:
    app = _REPO_ROOT / "target-apps" / "desk-booking"
    if not app.is_dir():
        return
    assert requires_streamlit("desk-booking", app, _REPO_ROOT) is False
    errors = [
        e for e in validate_ui_parity_blocking(app, _REPO_ROOT) if e.startswith("UI_PARITY:")
    ]
    assert errors == []
