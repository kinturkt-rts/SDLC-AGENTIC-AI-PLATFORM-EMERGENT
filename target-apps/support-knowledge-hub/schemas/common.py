"""Shared Pydantic coercion helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def coerce_iso_datetime(v: Any) -> str | None:
    """RDS TIMESTAMPTZ → datetime; SQLite tests → ISO str. API always returns str."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)
