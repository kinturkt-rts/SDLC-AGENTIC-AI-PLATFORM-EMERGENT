"""Tests for the frontend-agent route-coverage gate and the shared spec-route
loader (_load_spec_routes) it was extracted alongside.

frontend_agent.py lives under a hyphenated directory (agents/frontend-agent/),
so it's loaded by file path via importlib, same pattern test_developer_agent.py
uses for developer_agent.py. No network, no pipeline, no AWS calls — every gate
function under test only reads files under tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "frontend-agent" / "frontend_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("frontend_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def _write_openapi(path: Path, paths_obj: dict[str, Any]) -> None:
    path.write_text(json.dumps({"paths": paths_obj}), encoding="utf-8")


def _write_frontend_call_file(frontend_dir: Path, filename: str, body: str) -> None:
    src = frontend_dir / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / filename).write_text(body, encoding="utf-8")


def _padding_routes(count: int) -> dict[str, Any]:
    """`count` distinct, single-route, always-covered entities (/api/v1/padN)
    so a test's real gap stays a small fraction of the total — the 15%
    percentage-block threshold is a real app concern (a handful of missed
    routes out of ~20-30), not something a 1-or-2-route toy spec should trip
    by accident. Pair with _padding_calls() for the matching scraped calls."""
    return {f"/api/v1/pad{i}": {"get": {}} for i in range(count)}


def _padding_calls(count: int) -> str:
    return "\n".join(
        f"apiGet<unknown>('/api/v1/pad{i}');" for i in range(count)
    ) + "\n"


# ---------------------------------------------------------------------------
# 1. _load_spec_routes
# ---------------------------------------------------------------------------


def test_load_spec_routes_returns_normalized_method_path_set(tmp_path: Path) -> None:
    fa = _load_agent_module()
    openapi_path = tmp_path / "openapi.json"
    _write_openapi(
        openapi_path,
        {
            "/api/v1/widgets": {
                "get": {"summary": "list"},
                "post": {"summary": "create"},
                # non-HTTP key sitting alongside real methods on the same path —
                # a common OpenAPI shape (shared path-level parameters) that must
                # be skipped, not misread as a 6th "method".
                "parameters": [{"name": "foo"}],
            },
            "/api/v1/widgets/{widget_id}": {
                "get": {"summary": "retrieve"},
            },
            # non-dict path value — must be skipped entirely, not raise.
            "/api/v1/broken": "not-a-methods-object",
        },
    )

    routes = fa._load_spec_routes(openapi_path)

    assert routes == {
        ("GET", "/api/v1/widgets"),
        ("POST", "/api/v1/widgets"),
        ("GET", "/api/v1/widgets/{*}"),
    }


def test_load_spec_routes_none_for_missing_file(tmp_path: Path) -> None:
    fa = _load_agent_module()
    assert fa._load_spec_routes(tmp_path / "does_not_exist.json") is None


def test_load_spec_routes_none_for_paths_less_or_empty_spec(tmp_path: Path) -> None:
    fa = _load_agent_module()

    no_paths_key = tmp_path / "no_paths.json"
    no_paths_key.write_text(json.dumps({"openapi": "3.0.0"}), encoding="utf-8")
    assert fa._load_spec_routes(no_paths_key) is None

    empty_paths = tmp_path / "empty_paths.json"
    empty_paths.write_text(json.dumps({"paths": {}}), encoding="utf-8")
    assert fa._load_spec_routes(empty_paths) is None


# ---------------------------------------------------------------------------
# 2. _validate_route_coverage_gate
# ---------------------------------------------------------------------------


def test_route_coverage_gate_blocks_multirroute_gap_warns_subpath_no_gap_when_covered(
    tmp_path: Path,
) -> None:
    """One openapi/frontend pair exercising three of the four required shapes:
    - "leases" (2 routes, 0 covered) -> multi-route fully-uncovered -> BLOCKS.
    - "widgets" (1 route, a GET sub-path action, 0 covered) -> fully uncovered
      but single-route + not-entity-root -> warns, does NOT block.
    - "owners" (2 routes, both covered) -> no gap at all.
    """
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"

    _write_openapi(
        openapi_path,
        {
            "/api/v1/owners": {"get": {}, "post": {}},
            "/api/v1/leases": {"get": {}, "post": {}},
            "/api/v1/widgets/{widget_id}/summary": {"get": {}},
        },
    )
    _write_frontend_call_file(
        frontend_dir,
        "Owners.tsx",
        "import { apiGet, apiPost } from '../api';\n"
        "apiGet<Owner[]>('/api/v1/owners');\n"
        "apiPost<Owner>('/api/v1/owners', {});\n",
    )

    passed, report = fa._validate_route_coverage_gate(frontend_dir, openapi_path, "jwt")

    assert passed is False
    assert "FAILED: entity with no UI at all: leases" in report
    assert "leases: 0/2 covered" in report
    assert "FULLY UNCOVERED (BLOCKING" in report
    # widgets is reported (WARN-always) but never named in the FAILED line.
    assert "widgets: 0/1 covered" in report
    assert "widgets" not in report.split("FAILED:")[1]
    # owners is fully covered — no gap tag of any kind.
    assert "owners: 2/2 covered\n" in report or report.strip().endswith("owners: 2/2 covered")


def test_route_coverage_gate_single_subpath_gap_alone_does_not_block(tmp_path: Path) -> None:
    """Isolates the single-route/sub-path carve-out: an entity with exactly one
    route, that route uncovered, and nothing else wrong, must PASS (warn only).
    Padded with 10 covered routes so the one real gap is ~9% of the total,
    under the 15% pct-block threshold — isolates the entity-level carve-out
    from the separate percentage-block behavior (see its own tests below)."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"

    _write_openapi(
        openapi_path,
        {
            "/api/v1/maintenance-requests/{request_id}/assign": {"put": {}},
            **_padding_routes(10),
        },
    )
    _write_frontend_call_file(frontend_dir, "Padding.tsx", _padding_calls(10))

    passed, report = fa._validate_route_coverage_gate(frontend_dir, openapi_path, "jwt")

    assert passed is True
    assert "FAILED" not in report
    assert "maintenance-requests: 0/1 covered" in report


def test_route_coverage_gate_auth_mode_gates_users_me_exclusion(tmp_path: Path) -> None:
    """jwt excludes GET /api/v1/users/me entirely (identity decoded client-side);
    api-key does not exclude it (login() genuinely calls it) — so an app that
    never calls it shows no gap under jwt, but a real (non-blocking, single
    sub-path route) gap under api-key. Padded with 10 covered routes so the
    api-key case's one real gap is ~8% of the total, under the 15% pct-block
    threshold — isolates the exclusion/carve-out behavior from the separate
    percentage-block behavior (see its own tests below)."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"

    _write_openapi(
        openapi_path,
        {
            "/api/v1/users/me": {"get": {}},
            "/api/v1/owners": {"get": {}},
            **_padding_routes(10),
        },
    )
    _write_frontend_call_file(
        frontend_dir,
        "Owners.tsx",
        "import { apiGet } from '../api';\napiGet<Owner[]>('/api/v1/owners');\n" + _padding_calls(10),
    )

    jwt_data = fa._route_coverage_report(frontend_dir, openapi_path, "jwt")
    api_key_data = fa._route_coverage_report(frontend_dir, openapi_path, "api-key")

    assert jwt_data["total"] == 11
    assert "users" not in jwt_data["entities"]

    assert api_key_data["total"] == 12
    assert "users" in api_key_data["entities"]
    assert api_key_data["entities"]["users"]["fully_uncovered"] is True
    assert api_key_data["entities"]["users"]["blocking"] is False

    jwt_passed, _ = fa._validate_route_coverage_gate(frontend_dir, openapi_path, "jwt")
    api_key_passed, _ = fa._validate_route_coverage_gate(frontend_dir, openapi_path, "api-key")
    assert jwt_passed is True
    assert api_key_passed is True  # warns only — single sub-path route, never blocks


def test_route_coverage_gate_20_8_pct_uncovered_blocks_and_feeds_retry(tmp_path: Path) -> None:
    """The exact real property-manage number: 5/24 = 20.8% uncovered, all
    detail routes ({id} routes with no reachable UI), none of the 5 affected
    entities ever fully uncovered (each has its list route covered) — so
    blocking_entities stays empty and the entity-level rule alone would PASS
    this. The percentage rule is the backstop that catches it.

    Also proves this is wired into the SAME retry loop as the entity block,
    not just a printed warning: run_task() sets coverage_gap_data from
    _route_coverage_report() whenever _validate_route_coverage_gate returns
    False (frontend_agent.py, the `else: passed, report = coverage_passed,
    coverage_report; coverage_gap_data = _route_coverage_report(...)` branch —
    unconditional on WHY coverage_passed is False), then feeds it to
    _route_coverage_retry_message() to build the next attempt's prompt instead
    of giving up. We call that exact same pair of functions here and assert
    the retry message is non-empty and names every uncovered route — a
    printed-warning-only implementation would have nothing to put there.
    """
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"

    # 5 entities: list route covered, {id} detail route uncovered (10 routes,
    # 5 uncovered) + 14 fully-covered padding routes = 24 total, 5 uncovered.
    detail_entities = ["owners", "properties", "units", "leases", "tenants"]
    _write_openapi(
        openapi_path,
        {
            **{f"/api/v1/{e}": {"get": {}} for e in detail_entities},
            **{f"/api/v1/{e}/{{id}}": {"get": {}} for e in detail_entities},
            **_padding_routes(14),
        },
    )
    _write_frontend_call_file(
        frontend_dir,
        "Lists.tsx",
        "\n".join(f"apiGet<unknown>('/api/v1/{e}');" for e in detail_entities) + "\n" + _padding_calls(14),
    )

    data = fa._route_coverage_report(frontend_dir, openapi_path, "jwt")
    assert data["total"] == 24
    assert data["uncovered"] == 5
    assert data["uncovered_pct"] == 20.8  # round((5/24)*100, 1)
    assert data["blocking_entities"] == []  # confirms the PCT rule is catching this, not the entity rule

    passed, report = fa._validate_route_coverage_gate(frontend_dir, openapi_path, "jwt")
    assert passed is False
    assert "exceeds the 15.0% threshold" in report

    # This is the exact call run_task() makes on a coverage failure before
    # looping back for another attempt — proves the block feeds a real retry,
    # not a dead end.
    message = fa._route_coverage_retry_message(report, data)
    assert message.strip() != ""
    for entity in detail_entities:
        assert f"entity '{entity}'" in message
        assert f"GET /api/v1/{entity}/{{*}}" in message
    assert "Return only the JSON file map" in message  # same contract every other retry message uses


def test_route_coverage_gate_4_pct_uncovered_does_not_block(tmp_path: Path) -> None:
    """A single stray uncovered route in an otherwise well-covered app: 1/25 =
    4.0% uncovered, comfortably under the 15% threshold — must PASS. This is
    exactly the scraper-blind-spot false-positive rate (see module docstring:
    the scraper can only ever over-report gaps, never under-report) the
    threshold is designed to tolerate."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"

    _write_openapi(
        openapi_path,
        {
            "/api/v1/widgets/{widget_id}/archive": {"put": {}},  # single sub-path route, uncovered
            **_padding_routes(24),
        },
    )
    _write_frontend_call_file(frontend_dir, "Padding.tsx", _padding_calls(24))

    data = fa._route_coverage_report(frontend_dir, openapi_path, "jwt")
    assert data["total"] == 25
    assert data["uncovered"] == 1
    assert data["uncovered_pct"] == 4.0
    assert data["blocking_entities"] == []

    passed, report = fa._validate_route_coverage_gate(frontend_dir, openapi_path, "jwt")
    assert passed is True
    assert "FAILED" not in report


def test_route_coverage_gate_fully_uncovered_entity_blocks_regardless_of_low_pct(
    tmp_path: Path,
) -> None:
    """A fully-uncovered multi-route entity must block even when the OVERALL
    percentage is well under the 15% threshold — the entity rule and the
    percentage rule are two independent block conditions (OR'd together), not
    a single combined threshold. 2/30 = 6.7% uncovered (comfortably under
    15%), but "leases" (2 routes, 0 covered) is a real, unambiguous multi-route
    gap that must block on its own regardless of how low the percentage is."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"

    _write_openapi(
        openapi_path,
        {
            "/api/v1/leases": {"get": {}, "post": {}},  # fully uncovered, multi-route
            **_padding_routes(28),
        },
    )
    _write_frontend_call_file(frontend_dir, "Padding.tsx", _padding_calls(28))

    data = fa._route_coverage_report(frontend_dir, openapi_path, "jwt")
    assert data["total"] == 30
    assert data["uncovered"] == 2
    assert data["uncovered_pct"] == 6.7  # well under the 15% threshold
    assert data["blocking_entities"] == ["leases"]  # blocks via the entity rule, not the pct rule

    passed, report = fa._validate_route_coverage_gate(frontend_dir, openapi_path, "jwt")
    assert passed is False
    assert "entity with no UI at all: leases" in report
    assert "exceeds the" not in report  # confirms THIS block came from the entity rule, not the pct rule


# ---------------------------------------------------------------------------
# 3. _check_backend_integration — extraction regression check
# ---------------------------------------------------------------------------


def test_check_backend_integration_still_validates_after_extraction(tmp_path: Path) -> None:
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"

    _write_openapi(openapi_path, {"/api/v1/items": {"get": {}, "post": {}}})
    _write_frontend_call_file(
        frontend_dir,
        "Items.tsx",
        "import { apiGet, apiPost } from '../api';\n"
        "apiGet<Item[]>('/api/v1/items');\n"
        "apiPost<Item>('/api/v1/items', {});\n",
    )

    assert fa._check_backend_integration(frontend_dir, openapi_path) == ("validated", [])


# ---------------------------------------------------------------------------
# 4. Tailwind @theme spacing collision gate (max-w-sm collapse / vertical bar)
# ---------------------------------------------------------------------------


def test_tailwind_theme_gate_rejects_named_spacing_sm(tmp_path: Path) -> None:
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    css_dir = frontend_dir / "src"
    css_dir.mkdir(parents=True)
    (css_dir / "index.css").write_text(
        "@theme {\n  --color-primary: #2dd4bf;\n  --spacing-sm: 12px;\n}\n",
        encoding="utf-8",
    )

    passed, report = fa._validate_tailwind_theme_gate(frontend_dir)

    assert passed is False
    assert "tailwind-theme-gate" in report
    assert "--spacing-sm" in report


def test_tailwind_theme_gate_accepts_template_without_named_spacing(tmp_path: Path) -> None:
    fa = _load_agent_module()
    template_css = (
        _REPO_ROOT / "target-apps" / "_template" / "frontend" / "src" / "index.css"
    )
    frontend_dir = tmp_path / "frontend"
    css_dir = frontend_dir / "src"
    css_dir.mkdir(parents=True)
    (css_dir / "index.css").write_text(
        template_css.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    passed, report = fa._validate_tailwind_theme_gate(frontend_dir)

    assert passed is True
    assert report == "[tailwind-theme-gate] PASSED"


def test_index_css_is_protected_from_llm_writes() -> None:
    fa = _load_agent_module()

    assert fa._is_protected_path("src/index.css") is True
    assert fa._is_protected_path("src/components/Login.tsx") is False
