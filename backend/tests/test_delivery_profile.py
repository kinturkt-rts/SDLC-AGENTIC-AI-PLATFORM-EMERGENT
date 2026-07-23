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
    merge_delivery_profiles,
    scan_delivery_text,
    sync_context_delivery_profile,
    verify_app_artifacts,
    verify_design_doc,
)


def test_scan_detects_streamlit() -> None:
    profile = scan_delivery_text("MVP with Streamlit UI on port 8501")
    assert profile["requiresStreamlit"] is True
    assert profile["uiPattern"] == "streamlit"


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
    """PRD architecture rows often say 'HTTP client to API only' while requiring Streamlit."""
    profile = scan_delivery_text(
        "| UI location | `ui/streamlit_app.py` | http client to api only — "
        "never import `app/` from streamlit; enforced by ci lint check |"
    )
    assert profile["requiresStreamlit"] is True
    assert profile["uiPattern"] == "streamlit"


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
    assert merged["requiresStreamlit"] is True


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
    assert profile["requiresStreamlit"] is True


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
    assert profile["requiresStreamlit"] is True
    synced = __import__("json").loads(ctx_path.read_text(encoding="utf-8"))
    assert synced["inputPath"] == "inputs/prior-auth.txt"


def test_design_doc_includes_streamlit() -> None:
    assert design_doc_includes_streamlit("| UI | Streamlit |")
    assert not design_doc_includes_streamlit("| API | FastAPI |")
