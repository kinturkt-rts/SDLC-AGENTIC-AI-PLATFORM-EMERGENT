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
import os
import sys
import time
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


# ---------------------------------------------------------------------------
# 5. Dialog layout gate (narrow detail dialog clips table columns + actions)
# ---------------------------------------------------------------------------


def _write_screen(frontend_dir: Path, name: str, body: str) -> None:
    screens = frontend_dir / "src" / "components"
    screens.mkdir(parents=True, exist_ok=True)
    (screens / name).write_text(body, encoding="utf-8")


def test_dialog_layout_gate_rejects_table_in_default_width_dialog(tmp_path: Path) -> None:
    """Regression for multi-tenant-pay-platform: Payment Details rendered a
    transactions table with Review/Refund/Dispute buttons inside a bare
    <DialogContent>, so the Actions column was clipped off the dialog."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    _write_screen(
        frontend_dir,
        "Payments.tsx",
        "<Dialog>\n"
        "  <DialogContent>\n"
        "    <Table><TableBody /></Table>\n"
        "  </DialogContent>\n"
        "</Dialog>\n",
    )

    passed, report = fa._validate_dialog_layout_gate(frontend_dir)

    assert passed is False
    assert "dialog-layout-gate" in report
    assert "components/Payments.tsx" in report


def test_dialog_layout_gate_accepts_widened_dialog(tmp_path: Path) -> None:
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    _write_screen(
        frontend_dir,
        "Payments.tsx",
        '<DialogContent className="sm:max-w-2xl">\n'
        '  <div className="overflow-x-auto"><Table><TableBody /></Table></div>\n'
        "</DialogContent>\n",
    )

    passed, report = fa._validate_dialog_layout_gate(frontend_dir)

    assert passed is True
    assert report == "[dialog-layout-gate] PASSED"


def test_dialog_layout_gate_allows_narrow_confirm_dialog(tmp_path: Path) -> None:
    """Delete/confirm prompts have no table — default max-w-sm is correct there."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    _write_screen(
        frontend_dir,
        "Customers.tsx",
        "<DialogContent>\n"
        "  <DialogHeader><DialogTitle>Delete customer?</DialogTitle></DialogHeader>\n"
        "  <DialogFooter><Button>Delete</Button></DialogFooter>\n"
        "</DialogContent>\n",
    )

    passed, _report = fa._validate_dialog_layout_gate(frontend_dir)

    assert passed is True


def test_dialog_layout_gate_ignores_template_ui_components(tmp_path: Path) -> None:
    """src/components/ui/dialog.tsx defines the default width itself — the gate
    must not flag the primitive it is asserting against."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    ui = frontend_dir / "src" / "components" / "ui"
    ui.mkdir(parents=True)
    (ui / "dialog.tsx").write_text(
        "<DialogContent>\n  <Table />\n</DialogContent>\n", encoding="utf-8"
    )

    passed, _report = fa._validate_dialog_layout_gate(frontend_dir)

    assert passed is True


def test_dialog_layout_rules_are_in_system_prompt() -> None:
    fa = _load_agent_module()
    prompt = fa._build_frontend_system_prompt({})

    assert "sm:max-w-2xl" in prompt
    assert "overflow-x-auto" in prompt
    assert "flex flex-wrap gap-1" in prompt


# ---------------------------------------------------------------------------
# 6. Action payload + method-mismatch gates (409/422/405 regressions)
# ---------------------------------------------------------------------------


def test_action_payload_gate_rejects_shortened_decision_literals(tmp_path: Path) -> None:
    """Regression: PaymentList sent decision: 'approve' while API wanted 'approved'."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    _write_screen(
        frontend_dir,
        "Payments.tsx",
        "await apiPost(`/api/v1/transactions/${id}/review`, { decision: 'approve' });\n"
        '<SelectItem value="reject">Reject</SelectItem>\n',
    )

    passed, report = fa._validate_action_payload_gate(frontend_dir)

    assert passed is False
    assert "action-payload-gate" in report
    assert "components/Payments.tsx" in report


def test_action_payload_gate_accepts_approved_rejected(tmp_path: Path) -> None:
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    _write_screen(
        frontend_dir,
        "Payments.tsx",
        "await apiPost(`/api/v1/transactions/${id}/review`, { decision: 'approved' });\n"
        '<SelectItem value="rejected">Reject</SelectItem>\n'
        "{tx.status === 'under_review' && <Button>Review</Button>}\n",
    )

    passed, report = fa._validate_action_payload_gate(frontend_dir)

    assert passed is True
    assert report == "[action-payload-gate] PASSED"


def test_action_payload_gate_ignores_files_without_review_path(tmp_path: Path) -> None:
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    _write_screen(
        frontend_dir,
        "Customers.tsx",
        "const form = { decision: 'approve' };\n",
    )

    passed, _report = fa._validate_action_payload_gate(frontend_dir)

    assert passed is True


def test_method_mismatch_gate_rejects_wrong_http_method(tmp_path: Path) -> None:
    """Regression: GET /api/v1/organisations when OpenAPI only declares POST → 405."""
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"
    _write_openapi(
        openapi_path,
        {"/api/v1/organisations": {"post": {"summary": "create"}}},
    )
    _write_screen(
        frontend_dir,
        "Orgs.tsx",
        "apiGet<unknown>('/api/v1/organisations');\n",
    )

    passed, report = fa._validate_method_mismatch_gate(frontend_dir, openapi_path)

    assert passed is False
    assert "method-mismatch-gate" in report
    assert "GET" in report
    assert "organisations" in report


def test_method_mismatch_gate_accepts_matching_methods(tmp_path: Path) -> None:
    fa = _load_agent_module()
    frontend_dir = tmp_path / "frontend"
    openapi_path = tmp_path / "openapi.json"
    _write_openapi(
        openapi_path,
        {"/api/v1/organisations": {"post": {"summary": "create"}}},
    )
    _write_screen(
        frontend_dir,
        "Orgs.tsx",
        "apiPost<unknown>('/api/v1/organisations', body);\n",
    )

    passed, report = fa._validate_method_mismatch_gate(frontend_dir, openapi_path)

    assert passed is True
    assert report == "[method-mismatch-gate] PASSED"


def test_status_gate_and_payload_rules_are_in_system_prompt() -> None:
    fa = _load_agent_module()
    prompt = fa._build_frontend_system_prompt({})

    assert "under_review" in prompt
    assert "approved" in prompt
    assert "Status-gated actions" in prompt or "status-gated" in prompt.lower()
    assert "EXACTLY" in prompt


def test_index_css_is_protected_from_llm_writes() -> None:
    fa = _load_agent_module()

    assert fa._is_protected_path("src/index.css") is True
    assert fa._is_protected_path("src/components/Login.tsx") is False


def test_package_json_and_vite_config_are_protected() -> None:
    """LLM must not strip deps or rewrite the Tailwind Vite plugin import."""
    fa = _load_agent_module()

    for path in (
        "package.json",
        "vite.config.ts",
        "src/main.tsx",
        "tsconfig.json",
        "tsconfig.app.json",
        "tsconfig.node.json",
    ):
        assert fa._is_protected_path(path) is True, path
    assert fa._is_protected_path("src/App.tsx") is False


def test_npm_install_needed_when_node_modules_missing(tmp_path) -> None:
    fa = _load_agent_module()

    needed, reason = fa._npm_install_needed(tmp_path)
    assert needed is True
    assert reason == "first time"


def test_npm_install_needed_when_critical_dep_missing(tmp_path) -> None:
    fa = _load_agent_module()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    needed, reason = fa._npm_install_needed(tmp_path)
    assert needed is True
    assert reason.startswith("missing deps:")


def test_scrape_resolves_path_assigned_to_variable(tmp_path) -> None:
    """apiGet(url) must count when url was assigned an /api/v1/... literal."""
    fa = _load_agent_module()
    src = tmp_path / "src"
    src.mkdir()
    (src / "Audit.tsx").write_text(
        "import { apiGet } from '../api';\n"
        "const url = `/api/v1/audit-log${qs}`;\n"
        "apiGet<unknown>(url);\n",
        encoding="utf-8",
    )
    calls = fa._scrape_frontend_api_calls(tmp_path)
    assert ("GET", "/api/v1/audit-log${qs}") in calls


def test_parse_frontend_file_map_json_extracts_object_from_prose() -> None:
    fa = _load_agent_module()
    raw = 'Looking at OpenAPI...\n{"src/App.tsx": "export default function App() { return null }"}'
    parsed = fa._parse_frontend_file_map_json(raw)
    assert parsed is not None
    assert "src/App.tsx" in parsed


def test_parse_frontend_file_map_json_returns_none_for_pure_prose() -> None:
    fa = _load_agent_module()
    assert fa._parse_frontend_file_map_json("Looking at the OpenAPI spec, I need to cover:") is None


def test_max_output_tokens_default_raised_above_32000(monkeypatch) -> None:
    """Regression: _generate_and_write() returns the whole app as one JSON blob in a
    single completion (zero tool calls) - multisite-construction-ops hard-failed with
    MaxTokensReachedException at 32000/32000 tokens before a single file was parsed."""
    fa = _load_agent_module()
    monkeypatch.delenv("FRONTEND_AGENT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("BEDROCK_MAX_OUTPUT_TOKENS", raising=False)
    assert fa._max_output_tokens() > 32000


def test_max_output_tokens_honors_env_override(monkeypatch) -> None:
    fa = _load_agent_module()
    monkeypatch.setenv("FRONTEND_AGENT_MAX_TOKENS", "48000")
    assert fa._max_output_tokens() == 48000


def test_resolve_app_dir_uses_repo_root_in_local_mode(monkeypatch) -> None:
    fa = _load_agent_module()
    monkeypatch.delenv("ARTIFACT_STORE", raising=False)
    app_dir = fa._resolve_app_dir("demo-app")
    assert app_dir == fa._REPO_ROOT / "target-apps" / "demo-app"


def test_resolve_app_dir_uses_writable_tmp_dir_in_s3_mode(monkeypatch) -> None:
    """Regression: _REPO_ROOT/target-apps/... is baked into the AgentCore image and
    read-only there - run_task() used to write generated frontend files straight into
    it, which crashed with OSError: [Errno 30] Read-only file system the first time a
    run actually reached the write step (feedback-systenm, run a912dda4). s3 mode must
    resolve to a genuinely writable /tmp dir instead, shaped like target-apps/<slug>
    so relative-path reporting stays identical to local mode."""
    fa = _load_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    app_dir = fa._resolve_app_dir("demo-app")
    assert app_dir != fa._REPO_ROOT / "target-apps" / "demo-app"
    assert app_dir.parts[-2:] == ("target-apps", "demo-app")
    assert app_dir.is_dir()  # _resolve_app_dir must create it, not just compute the path
