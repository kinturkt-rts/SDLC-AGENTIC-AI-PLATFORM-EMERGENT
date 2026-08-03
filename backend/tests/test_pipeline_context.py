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
    slugify_feature,
)


def test_slugify_rejects_empty() -> None:
    with pytest.raises(ValueError, match="cannot derive app slug"):
        slugify("   ")


def test_slugify_feature_matches_slugify() -> None:
    assert slugify_feature("Bug Deduper") == slugify("Bug Deduper") == "bug-deduper"


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


def test_consolidated_artifact_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORE", "local")
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
        f"{base}/docs/generated-diagrams/{slug}.png"
    )
    assert pipeline_context_rel_for_app(slug) == (
        f"{base}/agents/pipeline/{slug}.context.json"
    )


def test_db_handoff_rel_for_app_follows_pipeline_convention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database handoff moved from <app>/db/HANDOFF.md to the same agents/pipeline/
    convention as the developer/gitlab/qa/devops handoffs."""
    from _shared.pipeline_context import db_handoff_rel_for_app

    monkeypatch.delenv("ARTIFACT_STORE", raising=False)
    monkeypatch.setenv("PRODUCT_ARTIFACT_LAYOUT", "docs")
    assert db_handoff_rel_for_app("inventory-app") == "agents/pipeline/inventory-app.database-handoff.md"

    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    assert db_handoff_rel_for_app("inventory-app") == "inventory-app/handoffs/database-handoff.md"


def test_artifact_layout_honors_product_prd_layout_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _shared.pipeline_context import artifact_layout, prd_rel_path_for_app

    monkeypatch.delenv("PRODUCT_ARTIFACT_LAYOUT", raising=False)
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("PRODUCT_PRD_LAYOUT", "docs")
    assert artifact_layout() == "docs"
    assert prd_rel_path_for_app("expense-tracker") == "docs/PRD/expense-tracker.md"


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


def test_merge_run_handoff_context_loads_run_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from _shared.artifact_store import put_context
    from _shared.pipeline_context import merge_run_handoff_context

    monkeypatch.setenv("ARTIFACT_STORE", "local")
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("PRODUCT_ARTIFACT_LAYOUT", "docs")

    run_id = "merge-handoff"
    put_context(
        run_id,
        {
            "targetApp": "expense-tracker",
            "prdPath": "docs/PRD/expense-tracker.md",
            "designDocPath": "docs/design/expense-tracker.md",
        },
    )
    merged = merge_run_handoff_context({"runId": run_id, "inputFile": "inputs/expense-tracker.txt"})
    assert merged["prdPath"] == "docs/PRD/expense-tracker.md"
    assert merged["designDocPath"] == "docs/design/expense-tracker.md"
    assert merged["inputFile"] == "inputs/expense-tracker.txt"
    assert merged["diagramPaths"] == ["docs/generated-diagrams/expense-tracker.png"]


def test_normalize_handoff_paths_cloud_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    from _shared.pipeline_context import normalize_handoff_paths

    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")

    ctx = normalize_handoff_paths(
        {
            "targetApp": "agent-ops-assistant",
            "runId": "smoke-007",
            "prdPath": "target-apps/agent-ops-assistant/docs/PRD/agent-ops-assistant.md",
            "designDocPath": "target-apps/agent-ops-assistant/docs/design/agent-ops-assistant.md",
            "dbOutputDir": "target-apps/agent-ops-assistant/db",
            "preferredSqlPath": "target-apps/agent-ops-assistant/db/sql",
        }
    )
    assert ctx["targetAppDir"] == "agent-ops-assistant"
    assert ctx["prdPath"] == "agent-ops-assistant/docs/PRD/agent-ops-assistant.md"
    assert ctx["dbOutputDir"] == "agent-ops-assistant/db"
    assert ctx["preferredSqlPath"] == "agent-ops-assistant/db/sql"


def test_sanitize_context_for_persist_strips_runtime_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    from _shared.pipeline_context import sanitize_context_for_persist

    monkeypatch.setenv("ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ARTIFACT_S3_BUCKET", "test-bucket")

    raw = {
        "runId": "smoke-006",
        "targetApp": "field-service-dispatch",
        "targetAppDir": "target-apps/field-service-dispatch",
        "inputPath": "inputs/field-service-dispatch.txt",
        "prdPath": "target-apps/field-service-dispatch/docs/PRD/field-service-dispatch.md",
        "designDocPath": "target-apps/field-service-dispatch/docs/design/field-service-dispatch.md",
        "diagramPaths": [
            "field-service-dispatch/docs/diagrams/generated-diagrams/field-service-dispatch.png",
            "/tmp/generated-diagrams/field-service-dispatch.png",
        ],
        "diagramOutputDir": "/tmp/generated-diagrams",
        "diagramOutputFile": "/tmp/generated-diagrams/field-service-dispatch",
        "productBrief": "Feature: Field Service Dispatch\nSchedule HVAC technicians.",
        "productAgentOutput": "See prdPath for field-service-dispatch MVP requirements.",
        "architectSummary": "Streamlit UI + FastAPI...",
        "postgresMcpParams": {"db_endpoint": "", "database": ""},
        "postgresMcpWarning": "POSTGRES_MCP_DB_ENDPOINT is not set.",
        "seedMinRows": 5,
        "deliveryProfile": {"uiRequired": False},
        "applyToRdsAfterWrite": True,
        "postgresAppSchema": "field_service_dispatch",
    }
    cleaned = sanitize_context_for_persist(raw)

    assert cleaned["runId"] == "smoke-006"
    assert cleaned["targetAppDir"] == "field-service-dispatch"
    assert cleaned["inputFile"] == "inputs/field-service-dispatch.txt"
    assert "inputPath" not in cleaned
    assert "diagramOutputDir" not in cleaned
    assert "architectSummary" not in cleaned
    assert "productAgentOutput" not in cleaned
    assert cleaned["productBrief"] == "Feature: Field Service Dispatch\nSchedule HVAC technicians."
    assert "postgresMcpParams" not in cleaned
    assert cleaned["prdPath"] == "field-service-dispatch/docs/PRD/field-service-dispatch.md"
    assert len(cleaned["diagramPaths"]) == 1
    assert cleaned["diagramPaths"][0].startswith("field-service-dispatch/")
    assert cleaned["applyToRdsAfterWrite"] is True
