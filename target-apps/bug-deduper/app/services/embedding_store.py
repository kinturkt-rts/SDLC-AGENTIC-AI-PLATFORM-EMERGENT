"""Bind/read embedding values across Postgres pgvector and SQLite text tests."""
from __future__ import annotations

from typing import Any


def embedding_bind_value(values: list[float], *, dialect: str) -> list[float] | str:
    if dialect == "sqlite":
        return "[" + ",".join(str(f) for f in values) + "]"
    return values


def embedding_as_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return [float(x) for x in text.strip("[]").split(",")]
        except ValueError:
            return None
    return None
