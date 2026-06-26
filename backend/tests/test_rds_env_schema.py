"""Tests for agents/_shared/rds_env.schema_for_app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.rds_env import schema_for_app  # noqa: E402


def test_schema_derived_from_target_app_slug(monkeypatch) -> None:
    monkeypatch.delenv("POSTGRES_APP_SCHEMA", raising=False)
    monkeypatch.setenv("POSTGRES_SCHEMA", "support_knowledge_hub")
    assert schema_for_app("facility-work-order-hub") == "facility_work_order_hub"


def test_postgres_app_schema_overrides_stale_postgres_schema(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_APP_SCHEMA", "facility_work_order_hub")
    monkeypatch.setenv("POSTGRES_SCHEMA", "support_knowledge_hub")
    assert schema_for_app("facility-work-order-hub") == "facility_work_order_hub"
