"""Tests for delivery profile extraction and verification."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.delivery_profile import (  # noqa: E402
    build_delivery_profile_from_paths,
    design_doc_includes_streamlit,
    frontend_required_from_delivery_profile,
    merge_delivery_profiles,
    scan_delivery_text,
    sync_context_delivery_profile,
    verify_app_artifacts,
    verify_design_doc,
)


def test_scan_streamlit_mention_resolves_to_react() -> None:
    """Streamlit is retired as a deliverable — a mention still means "UI required"
    but the classifier must always route it to React, never requiresStreamlit=True."""
    profile = scan_delivery_text("MVP with Streamlit UI on port 8501")
    assert profile["requiresStreamlit"] is False
    assert profile["requiresReact"] is True
    assert profile["uiPattern"] == "react"


def test_scan_backend_only_via_is_not_no_frontend() -> None:
    """Regression: "the Streamlit app talks to the FastAPI backend only via HTTP
    REST calls" describes a communication constraint, not a no-frontend
    declaration - it previously matched \\bbackend[- ]only\\b and set
    noFrontendExplicit=True, silently dropping a UI the brief explicitly required."""
    profile = scan_delivery_text(
        "The Streamlit application communicates with the FastAPI backend only via "
        "HTTP REST calls; it does not share Python modules or a database session."
    )
    assert profile["noFrontendExplicit"] is False
    assert profile["requiresReact"] is True


def test_scan_http_client_calls_fastapi_backend_only_not_no_frontend() -> None:
    """Regression (vehicle-scheduling / sales-performance): product-agent writes
    'HTTP client calls FastAPI backend only' in architecture sections meaning
    client→API isolation. Bare 'backend only' must not suppress a React SPA."""
    profile = scan_delivery_text(
        "## 11. Client UI\n"
        "Primary UI: **React SPA** under `frontend/`.\n\n"
        "## Architecture notes\n"
        "The browser HTTP client calls FastAPI backend only; no direct DB access "
        "from the UI layer.\n"
    )
    assert profile["noFrontendExplicit"] is False
    assert profile["requiresReact"] is True
    assert profile["uiRequired"] is True


def test_scan_full_prd_react_spa_with_backend_only_architecture_phrase() -> None:
    """Full-PRD fixture: React SPA required, architecture uses 'backend only' for
    call isolation. Short-string tests missed this because they never included both."""
    prd = """
# Vehicle Scheduling — Product Requirements

## 1. Summary
Internal fleet booking for employees and fleet managers.

## 2. Users
- Fleet Manager, Employee, Admin

## 11. Client UI
| Surface | Choice | Notes |
| --- | --- | --- |
| Primary UI | **React SPA** | Vite + TypeScript under `frontend/` |
| UI location | `frontend/` (React) | HTTP client calls FastAPI backend only — never import `app/` from the UI |

## Out of scope
Mobile native apps, SSO federation.
"""
    profile = scan_delivery_text(prd)
    assert profile["noFrontendExplicit"] is False
    assert profile["requiresReact"] is True
    assert profile["uiRequired"] is True
    assert frontend_required_from_delivery_profile(profile) is True


def test_scan_full_prd_sales_dashboard_backend_only_phrase() -> None:
    """Second full-PRD shape (sales-performance style dashboard + backend only)."""
    prd = """
# Sales Performance Dashboard PRD

Operators need a web dashboard of pipeline and win-rate metrics.

Stack expectation: React frontend, FastAPI API, Postgres.

Architecture: dashboard charts load via the HTTP client; the client calls the
FastAPI backend only (no embedding of SQL in the browser).
"""
    profile = scan_delivery_text(prd)
    assert profile["noFrontendExplicit"] is False
    assert profile["requiresReact"] is True
    assert frontend_required_from_delivery_profile(profile) is True


def test_scan_genuine_backend_only_still_detected() -> None:
    profile = scan_delivery_text("This is a backend-only service, no UI needed.")
    assert profile["noFrontendExplicit"] is True


def test_scan_backend_only_service_noun_still_detected() -> None:
    """Strong form (parallel to api-only app|service) — still no frontend."""
    profile = scan_delivery_text(
        "Deliver a backend-only service exposing REST endpoints for partner systems."
    )
    assert profile["noFrontendExplicit"] is True
    assert profile["uiRequired"] is False


def test_scan_bare_backend_only_without_ui_markers_is_not_explicit() -> None:
    """Bare 'backend only' alone is insufficient (same policy as bare 'api only').
    Silent / ambiguous briefs stay noFrontendExplicit=False so the platform
    default React gate still runs frontend-agent."""
    profile = scan_delivery_text(
        "Expose vehicle availability through the FastAPI backend only."
    )
    assert profile["noFrontendExplicit"] is False


def test_scan_ignores_negated_streamlit() -> None:
    profile = scan_delivery_text(
        "Pattern B: FastAPI + Postgres. No Streamlit, no JWT. Out of scope: Streamlit/React UI."
    )
    assert profile["requiresStreamlit"] is False
    assert profile["uiRequired"] is False


def test_scan_ignores_negated_streamlit_in_comma_list() -> None:
    """Regression: 'no <list of 3+ items>, Streamlit, <more items>' must negate.

    lab-equipment-booking.txt used this phrasing ("No customer-facing web UI,
    Streamlit, chatbots, or SSO for this version - API only.") and the old
    0-2-word gap couldn't reach past "customer-facing web UI," to "Streamlit",
    so requiresStreamlit came back True for an API-only brief.
    """
    profile = scan_delivery_text(
        "Must have for v1:\n"
        "- No customer-facing web UI, Streamlit, chatbots, or SSO for this "
        "version - API only.\n"
    )
    assert profile["requiresStreamlit"] is False
    assert profile["uiRequired"] is False


def test_scan_streamlit_not_killed_by_http_client_to_api_only() -> None:
    """PRD architecture rows often say 'HTTP client to API only' while requiring a UI —
    that must still resolve to React now that Streamlit is retired as a deliverable."""
    profile = scan_delivery_text(
        "| UI location | `ui/streamlit_app.py` | http client to api only — "
        "never import `app/` from streamlit; enforced by ci lint check |"
    )
    assert profile["requiresStreamlit"] is False
    assert profile["requiresReact"] is True
    assert profile["uiPattern"] == "react"


def test_scan_api_only_app_still_false() -> None:
    profile = scan_delivery_text(
        "Deliver as API-only app. FastAPI + Postgres. No Streamlit UI folder."
    )
    assert profile["requiresStreamlit"] is False


def test_merge_profiles_or_flags() -> None:
    merged = merge_delivery_profiles(
        {"uiRequired": False, "requiresStreamlit": False, "requiresReact": False, "uiPattern": None},
        scan_delivery_text("needs streamlit dashboard"),
    )
    assert merged["requiresStreamlit"] is False
    assert merged["requiresReact"] is True
    assert merged["uiPattern"] == "react"


def test_verify_design_doc_fails_when_streamlit_omitted(tmp_path: Path) -> None:
    design = tmp_path / "design.md"
    design.write_text(
        "# App\n\n## 2. Stack\n| Layer | Technology |\n| API | FastAPI |\n",
        encoding="utf-8",
    )
    context = {
        "deliveryProfile": {"requiresStreamlit": True},
        "designDocPath": str(design),
    }
    errors = verify_design_doc(tmp_path, context)
    assert len(errors) == 1
    assert "Streamlit" in errors[0]


def test_verify_design_doc_passes_with_streamlit_stack(tmp_path: Path) -> None:
    design = tmp_path / "design.md"
    design.write_text(
        "# App\n\n## 2. Stack\n| UI | Streamlit ui/streamlit_app.py |\n",
        encoding="utf-8",
    )
    context = {
        "deliveryProfile": {"requiresStreamlit": True},
        "designDocPath": str(design),
    }
    assert verify_design_doc(tmp_path, context) == []


def test_verify_app_artifacts_requires_streamlit_file(tmp_path: Path) -> None:
    app_dir = tmp_path / "target-apps" / "demo" / "ui"
    app_dir.mkdir(parents=True)
    context = {"deliveryProfile": {"requiresStreamlit": True}}
    errors = verify_app_artifacts(tmp_path, "demo", context)
    assert any("streamlit_app.py" in err for err in errors)


def test_build_delivery_profile_from_input_file(tmp_path: Path) -> None:
    brief = tmp_path / "inputs" / "app.txt"
    brief.parent.mkdir(parents=True)
    brief.write_text("Stack: FastAPI + Streamlit UI for client portal\n", encoding="utf-8")
    profile = build_delivery_profile_from_paths(tmp_path, input_path=str(brief))
    assert profile["requiresStreamlit"] is False
    assert profile["requiresReact"] is True


def test_sync_reads_input_file_when_input_path_missing(tmp_path: Path) -> None:
    brief = tmp_path / "inputs" / "prior-auth.txt"
    brief.parent.mkdir(parents=True)
    brief.write_text("Must ship Streamlit UI at ui/streamlit_app.py\n", encoding="utf-8")
    prd = tmp_path / "docs" / "PRD" / "app.md"
    prd.parent.mkdir(parents=True)
    prd.write_text(
        "| UI | Streamlit | http client to api only — never import app/ from streamlit |\n",
        encoding="utf-8",
    )
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(
        '{"prdPath": "docs/PRD/app.md", "inputFile": "inputs/prior-auth.txt"}\n',
        encoding="utf-8",
    )
    profile = sync_context_delivery_profile(tmp_path, ctx_path)
    assert profile["requiresStreamlit"] is False
    assert profile["requiresReact"] is True
    synced = __import__("json").loads(ctx_path.read_text(encoding="utf-8"))
    assert synced["inputPath"] == "inputs/prior-auth.txt"


def test_design_doc_includes_streamlit() -> None:
    assert design_doc_includes_streamlit("| UI | Streamlit |")
    assert not design_doc_includes_streamlit("| API | FastAPI |")


def test_prd_only_streamlit_downgraded_when_brief_silent(tmp_path: Path) -> None:
    """Regression: product-agent's PRD picked Streamlit for a brief that names no
    frontend tech at all (violating its own "never default to Streamlit" rule). The
    brief is the source of truth for tech CHOICE - an unconfirmed PRD claim must not
    silently override the platform's React default."""
    brief = tmp_path / "inputs" / "visitor-managemtn.txt"
    brief.parent.mkdir(parents=True)
    brief.write_text(
        "Organizations need a better way to manage visitors entering their offices.\n"
        "Register visitors, schedule visits, record check-in/check-out.\n",
        encoding="utf-8",
    )
    prd = tmp_path / "docs" / "PRD" / "app.md"
    prd.parent.mkdir(parents=True)
    prd.write_text("| Client UI | **Streamlit** | Primary UI for reception staff |\n", encoding="utf-8")

    profile = build_delivery_profile_from_paths(tmp_path, prd_path=str(prd), input_path=str(brief))
    assert profile["requiresStreamlit"] is False
    assert profile["requiresReact"] is True
    assert profile["uiPattern"] == "react"


def test_sync_falls_back_to_input_rel_for_app_when_context_missing_inputpath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: AgentCore/orchestrator-driven cloud runs don't always propagate
    inputPath into context.json even though the brief exists at the conventional
    <slug>/inputs/<slug>.txt path - without a fallback there, the brief-vs-PRD guard
    has nothing to check and a wrong PRD Streamlit choice goes uncaught."""
    monkeypatch.setenv("ARTIFACT_STORE", "s3")  # cloud layout: <slug>/inputs/<slug>.txt
    slug = "visitor-managemtn"
    brief = tmp_path / slug / "inputs" / f"{slug}.txt"
    brief.parent.mkdir(parents=True)
    brief.write_text("Organizations need a better way to manage visitors.\n", encoding="utf-8")
    prd = tmp_path / slug / "docs" / "PRD" / f"{slug}.md"
    prd.parent.mkdir(parents=True)
    prd.write_text("| Client UI | **Streamlit** |\n", encoding="utf-8")

    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(
        __import__("json").dumps({"targetApp": slug, "prdPath": f"{slug}/docs/PRD/{slug}.md"}),
        encoding="utf-8",
    )

    profile = sync_context_delivery_profile(tmp_path, ctx_path)
    assert profile["requiresStreamlit"] is False
    assert profile["requiresReact"] is True
    synced = __import__("json").loads(ctx_path.read_text(encoding="utf-8"))
    assert synced["inputPath"] == f"{slug}/inputs/{slug}.txt"


def test_frontend_required_from_delivery_profile_silent_brief_defaults_react() -> None:
    """Silent brief scans to requiresReact=False — still require React frontend."""
    assert (
        frontend_required_from_delivery_profile(
            {
                "uiRequired": False,
                "requiresReact": False,
                "requiresStreamlit": False,
                "noFrontendExplicit": False,
            }
        )
        is True
    )


def test_frontend_required_from_delivery_profile_explicit_no_frontend_skips() -> None:
    assert (
        frontend_required_from_delivery_profile(
            {"requiresReact": False, "noFrontendExplicit": True}
        )
        is False
    )


# --- Fix C: non-literal backend-only self-description (Kintur-authorized, not a
# Streamlit change) ---------------------------------------------------------------


def test_scan_just_a_backend_service_suppresses_frontend() -> None:
    profile = scan_delivery_text(
        "This project needs just a backend service exposing REST endpoints."
    )
    assert profile["noFrontendExplicit"] is True
    assert profile["uiRequired"] is False
    assert profile["requiresReact"] is False


def test_scan_backend_api_nothing_else_needed_suppresses_frontend() -> None:
    profile = scan_delivery_text("We need a backend API, nothing else needed for v1.")
    assert profile["noFrontendExplicit"] is True
    assert profile["uiRequired"] is False


def test_scan_rest_api_only_suppresses_frontend() -> None:
    profile = scan_delivery_text("Deliver a REST API only.")
    assert profile["noFrontendExplicit"] is True
    assert profile["uiRequired"] is False


def test_scan_silent_brief_does_not_set_no_frontend_explicit() -> None:
    """A brief that says nothing about UI at all must NOT be treated as an explicit
    no-frontend signal — the frontend-required gate (outside this module) is what
    defaults silent briefs to React, and it only skips frontend-agent when
    noFrontendExplicit is true."""
    profile = scan_delivery_text(
        "Manage inventory counts across three warehouses with reorder alerts."
    )
    assert profile["noFrontendExplicit"] is False
    assert profile["uiRequired"] is False


def test_scan_backend_feeding_frontend_dashboard_not_suppressed() -> None:
    """False positive #1: mentions 'backend service' but clearly has a UI — must
    not be caught by the broadened backend-only detection."""
    profile = scan_delivery_text("The backend service feeds the frontend dashboard.")
    assert profile["noFrontendExplicit"] is False


def test_scan_just_backend_today_react_next_sprint_not_suppressed() -> None:
    """False positive #2: 'just backend' phrasing in one clause, but a React
    frontend is named later in the same document — the document-wide UI-marker
    gate must catch this even though the two mentions are in different clauses."""
    profile = scan_delivery_text(
        "It's just backend work today; the React frontend ships next sprint."
    )
    assert profile["noFrontendExplicit"] is False


def test_scan_api_only_when_offline_web_dashboard_not_suppressed() -> None:
    """False positive #3: 'API only' immediately followed by a conditional clause
    (blocked by the continuation-word lookahead) AND the same document separately
    mentions a web dashboard (now a tracked _GENERIC_UI_MARKERS entry, giving this
    case a second line of defense independent of the continuation-word list)."""
    profile = scan_delivery_text(
        "Users interact with the backend API only when offline; otherwise they "
        "use the web dashboard."
    )
    assert profile["noFrontendExplicit"] is False
