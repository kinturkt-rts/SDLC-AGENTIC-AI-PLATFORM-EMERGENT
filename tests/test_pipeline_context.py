"""Tests for shared pipeline context resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.pipeline_context import (  # noqa: E402
    TargetAppRequiredError,
    infer_target_app_from_context,
    resolve_cli_context,
    resolve_target_app,
    slugify,
)


def test_slugify_rejects_empty() -> None:
    with pytest.raises(ValueError, match="cannot derive app slug"):
        slugify("   ")


def test_infer_target_app_from_context_target_app() -> None:
    assert infer_target_app_from_context({"targetApp": "inventory-app"}) == "inventory-app"


def test_infer_target_app_from_context_prd_path() -> None:
    assert (
        infer_target_app_from_context({"prdPath": "docs/PRD/rag-app-streamlit.md"})
        == "rag-app-streamlit"
    )


def test_infer_target_app_from_context_file_stem() -> None:
    assert (
        infer_target_app_from_context(
            {"_contextFile": "agents/pipeline/contacts-api.context.json"}
        )
        == "contacts-api"
    )


def test_resolve_target_app_cli_wins() -> None:
    assert resolve_target_app("my-app", {"targetApp": "other-app"}) == "my-app"


def test_resolve_target_app_from_context() -> None:
    assert resolve_target_app(None, {"targetApp": "lunch-learn-app"}) == "lunch-learn-app"


def test_resolve_target_app_requires_explicit_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PIPELINE_TARGET_APP", raising=False)
    with pytest.raises(TargetAppRequiredError):
        resolve_target_app(None, None)


def test_consolidated_artifact_paths() -> None:
    from _shared.pipeline_context import (
        design_doc_rel_for_app,
        diagram_path_for_app,
        gitlab_handoff_rel_for_app,
        pipeline_context_rel_for_app,
        prd_rel_path_for_app,
        qa_handoff_rel_for_app,
    )

    slug = "inventory-app"
    base = f"target-apps/{slug}"
    assert prd_rel_path_for_app(slug) == f"{base}/docs/PRD/{slug}.md"
    assert design_doc_rel_for_app(slug) == f"{base}/docs/design/{slug}.md"
    assert diagram_path_for_app(slug) == (
        f"{base}/docs/diagrams/generated-diagrams/{slug}.png"
    )
    assert pipeline_context_rel_for_app(slug) == (
        f"{base}/agents/pipeline/{slug}.context.json"
    )
    assert gitlab_handoff_rel_for_app(slug) == (
        f"{base}/agents/pipeline/{slug}.gitlab-handoff.json"
    )
    assert qa_handoff_rel_for_app(slug) == f"{base}/agents/pipeline/{slug}.qa-handoff.json"


def test_resolve_cli_context_loads_pipeline_json() -> None:
    extra, app = resolve_cli_context(
        "inventory-app",
        None,
        no_auto_context=False,
    )
    assert app == "inventory-app"
    assert extra.get("targetApp") == "inventory-app"
    assert extra.get("prdPath")


def test_resolve_cli_context_loads_legacy_pipeline_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCT_ARTIFACT_LAYOUT", "docs")
    extra, app = resolve_cli_context(
        "inventory-app",
        None,
        no_auto_context=False,
    )
    assert app == "inventory-app"
    assert extra.get("prdPath")
