"""Lightweight per-run telemetry — token usage, cache hits, tool calls, wall-clock.

Each agent's callback handler appends usage events captured from Strands' streaming
metadata events. At end of run, `print_summary()` writes a one-screen telemetry block
to stderr and persists the snapshot so the next run can show a delta.

The file lives at `agents/pipeline/<app>.<agent>-telemetry.json`. Persist failures are
silent — telemetry must never break a real agent run.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_DIR = _REPO_ROOT / "agents" / "pipeline"


class RunTelemetry:
    """Accumulates per-run metrics. Hooked from each agent's callback handler."""

    def __init__(self, agent_name: str, target_app: str | None = None) -> None:
        self.agent_name = agent_name
        self.target_app = target_app
        self.tool_count: int = 0
        self.tool_names: list[str] = []
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cache_read_input_tokens: int = 0
        self.cache_write_input_tokens: int = 0
        self.total_tokens: int = 0
        self.started_at: float = time.monotonic()
        self.extra: dict[str, Any] = {}

    # ── ingestion ────────────────────────────────────────────────────────────

    def record_tool(self, name: str) -> None:
        self.tool_count += 1
        self.tool_names.append(name)

    def record_usage(self, usage: dict[str, Any] | None) -> None:
        """Add a Bedrock usage dict (one per converse turn). Strands emits one per turn."""
        if not isinstance(usage, dict):
            return
        # Bedrock keys: inputTokens, outputTokens, totalTokens,
        # cacheReadInputTokens, cacheWriteInputTokens (when caching is on).
        self.input_tokens += int(usage.get("inputTokens", 0) or 0)
        self.output_tokens += int(usage.get("outputTokens", 0) or 0)
        self.total_tokens += int(usage.get("totalTokens", 0) or 0)
        self.cache_read_input_tokens += int(usage.get("cacheReadInputTokens", 0) or 0)
        self.cache_write_input_tokens += int(usage.get("cacheWriteInputTokens", 0) or 0)

    # ── helpers ──────────────────────────────────────────────────────────────

    @property
    def elapsed_sec(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def cache_hit_ratio(self) -> float:
        """Fraction of input tokens served from cache (0.0–1.0)."""
        total_input = self.input_tokens + self.cache_read_input_tokens
        if total_input <= 0:
            return 0.0
        return self.cache_read_input_tokens / total_input

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent_name,
            "targetApp": self.target_app,
            "toolCount": self.tool_count,
            "toolNames": list(self.tool_names),
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheReadInputTokens": self.cache_read_input_tokens,
            "cacheWriteInputTokens": self.cache_write_input_tokens,
            "totalTokens": self.total_tokens,
            "cacheHitRatio": round(self.cache_hit_ratio, 4),
            "elapsedSec": round(self.elapsed_sec, 2),
        }

    # ── persistence + summary ────────────────────────────────────────────────

    def _path(self) -> Path | None:
        if not self.target_app:
            return None
        _PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
        return _PIPELINE_DIR / f"{self.target_app}.{self.agent_name}-telemetry.json"

    def load_previous(self) -> dict[str, Any] | None:
        """Read the last persisted snapshot for this (agent, app) pair, or None."""
        path = self._path()
        if not path or not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def persist(self) -> None:
        """Write current snapshot for the next run to compare against. Silent on failure."""
        path = self._path()
        if not path:
            return
        try:
            path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

    def print_summary(self, *, stream=sys.stderr) -> None:
        """Print a one-screen telemetry block + delta vs the prior run."""
        previous = self.load_previous()
        cur = self.to_dict()
        prefix = f"[{self.agent_name}]"

        def _delta(curv: int | float, prev: int | float | None, unit: str = "") -> str:
            if prev is None:
                return ""
            d = curv - prev
            if d == 0:
                return f"  (= prev)"
            sign = "+" if d > 0 else ""
            return f"  ({sign}{d}{unit} vs prev)"

        prev = previous or {}
        cache_pct = self.cache_hit_ratio * 100
        prev_cache_pct = (prev.get("cacheHitRatio") or 0) * 100

        lines = [
            "",
            "=" * 64,
            f"{prefix} Telemetry — {self.agent_name} on {self.target_app or '(no app)'}",
            "-" * 64,
            f"  wall clock        : {cur['elapsedSec']:>8.2f}s{_delta(cur['elapsedSec'], prev.get('elapsedSec'), 's')}",
            f"  tool calls        : {cur['toolCount']:>8d}{_delta(cur['toolCount'], prev.get('toolCount'))}",
            f"  input tokens      : {cur['inputTokens']:>8d}{_delta(cur['inputTokens'], prev.get('inputTokens'))}",
            f"  cache-read tokens : {cur['cacheReadInputTokens']:>8d}{_delta(cur['cacheReadInputTokens'], prev.get('cacheReadInputTokens'))}",
            f"  cache-write tokens: {cur['cacheWriteInputTokens']:>8d}{_delta(cur['cacheWriteInputTokens'], prev.get('cacheWriteInputTokens'))}",
            f"  output tokens     : {cur['outputTokens']:>8d}{_delta(cur['outputTokens'], prev.get('outputTokens'))}",
            f"  total tokens      : {cur['totalTokens']:>8d}{_delta(cur['totalTokens'], prev.get('totalTokens'))}",
            f"  cache hit ratio   : {cache_pct:>7.1f}%{_delta(round(cache_pct,1), round(prev_cache_pct,1), '%')}",
        ]
        if self.extra:
            lines.append(f"  extra             : {json.dumps(self.extra, default=str)}")
        lines.append("=" * 64)
        print("\n".join(lines), file=stream)

        if previous is None:
            print(
                f"{prefix} (no previous run on file — next invocation will show deltas)",
                file=stream,
            )


def usage_from_event(event: Any) -> dict[str, Any] | None:
    """Best-effort extraction of Bedrock usage from a Strands callback event.

    Strands surfaces converse_stream's `metadata` chunk as `event["metadata"]["usage"]`.
    Different SDK versions sometimes nest it under `event["event"]["metadata"]["usage"]`.
    Both paths are tried; returns None if neither is present.
    """
    if not isinstance(event, dict):
        return None
    candidates = (
        event.get("metadata"),
        (event.get("event") or {}).get("metadata") if isinstance(event.get("event"), dict) else None,
    )
    for meta in candidates:
        if isinstance(meta, dict) and isinstance(meta.get("usage"), dict):
            return meta["usage"]
    return None
