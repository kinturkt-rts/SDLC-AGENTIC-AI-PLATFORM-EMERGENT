"""Shared Pydantic coercion helpers — required when DDL uses TIMESTAMPTZ on RDS."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def coerce_iso_datetime(v: Any) -> str | None:
    """RDS TIMESTAMPTZ → datetime; SQLite tests may use ISO str. API responses use str."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)
