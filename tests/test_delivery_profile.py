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


def test_design_doc_includes_streamlit() -> None:
    assert design_doc_includes_streamlit("| UI | Streamlit |")
    assert not design_doc_includes_streamlit("| API | FastAPI |")
