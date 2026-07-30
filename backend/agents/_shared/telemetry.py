"""Lightweight per-run telemetry — token usage, cache hits, tool calls, wall-clock.

Each agent's callback handler appends usage events captured from Strands' streaming
metadata events. At end of run, `print_summary()` writes a one-screen telemetry block
to stderr and persists the snapshot so the next run can show a delta.

Per-agent files: `agents/pipeline/<app>.<agent>-telemetry.json`
Pipeline rollup:  `agents/pipeline/<app>.pipeline-telemetry.json`

Persist failures are silent — telemetry must never break a real agent run.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_DIR = _REPO_ROOT / "agents" / "pipeline"

# Bedrock LLM agents in the default SDLC chain (gitlab/qa are deterministic or optional).
DEFAULT_PIPELINE_AGENTS: tuple[str, ...] = (
    "product-agent",
    "architect-agent",
    "database-agent",
    "developer-agent",
    "frontend-agent",
)


def short_model_label(model_id: str) -> str:
    """Human label e.g. sonnet-4.6, opus-4.6."""
    mid = (model_id or "").lower()
    if "opus" in mid:
        family = "opus"
    elif "sonnet" in mid:
        family = "sonnet"
    elif "haiku" in mid:
        family = "haiku"
    else:
        tail = model_id.rsplit(".", 1)[-1] if model_id else "unknown"
        return tail[:24]
    ver_match = re.search(r"claude-(?:[\w-]+-)?(\d+-\d+)", mid)
    if not ver_match:
        ver_match = re.search(r"(\d+-\d+)", mid)
    ver = ver_match.group(1) if ver_match else ""
    return f"{family}-{ver}" if ver else family


class RunTelemetry:
    """Accumulates per-run metrics. Hooked from each agent's callback handler."""

    def __init__(
        self,
        agent_name: str,
        target_app: str | None = None,
        *,
        model_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.target_app = target_app
        self.run_id = (run_id or "").strip() or None
        self.model_id = (
            model_id
            or os.getenv("CODING_MODEL_ID", "").strip()
            or os.getenv("MODEL_ID", "").strip()
        )
        self.tool_count: int = 0
        self.tool_names: list[str] = []
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cache_read_input_tokens: int = 0
        self.cache_write_input_tokens: int = 0
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
        self.cache_read_input_tokens += int(usage.get("cacheReadInputTokens", 0) or 0)
        self.cache_write_input_tokens += int(usage.get("cacheWriteInputTokens", 0) or 0)

    def merge_from(self, other: RunTelemetry) -> None:
        """Combine metrics from a sub-run (e.g. architect design-writer after diagram agent)."""
        self.tool_count += other.tool_count
        self.tool_names.extend(other.tool_names)
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens
        self.cache_write_input_tokens += other.cache_write_input_tokens

    @property
    def billed_tokens(self) -> int:
        """New input + output tokens (excludes cache-read; matches Bedrock billing)."""
        return self.input_tokens + self.output_tokens

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
            "runId": self._run_id(),
            "modelId": self.model_id,
            "modelLabel": short_model_label(self.model_id),
            "toolCount": self.tool_count,
            "toolNames": list(self.tool_names),
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheReadInputTokens": self.cache_read_input_tokens,
            "cacheWriteInputTokens": self.cache_write_input_tokens,
            "totalTokens": self.billed_tokens,
            "cacheHitRatio": round(self.cache_hit_ratio, 4),
            "elapsedSec": round(self.elapsed_sec, 2),
        }

    # ── persistence + summary ────────────────────────────────────────────────

    def _path(self) -> Path | None:
        if not self.target_app:
            return None
        _PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
        return _PIPELINE_DIR / f"{self.target_app}.{self.agent_name}-telemetry.json"

    def _run_id(self) -> str | None:
        return self.run_id or os.getenv("PIPELINE_RUN_ID", "").strip() or None

    def ensure_run_id(self, context: dict[str, Any] | None = None) -> None:
        """Bind run id from handoff context when AgentCore child runtimes lack PIPELINE_RUN_ID."""
        if self.run_id:
            return
        if context:
            rid = str(context.get("runId") or context.get("run_id") or "").strip()
            if rid:
                self.run_id = rid

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
        """Write current snapshot for the next run to compare against. Silent on failure.

        Also mirrors the snapshot to the run's S3 prefix under
        ``<slug>/telemetry/<agent>-telemetry.json`` so the control-plane UI can surface
        per-agent tokens for cloud runs (local disk isn't shared with the frontend).
        """
        path = self._path()
        payload = json.dumps(self.to_dict(), indent=2) + "\n"
        if path:
            try:
                path.write_text(payload, encoding="utf-8")
            except OSError:
                pass
        self._mirror_to_run_artifacts(payload)

    def _mirror_to_run_artifacts(self, payload: str) -> None:
        if not self.target_app:
            return
        try:
            from .artifact_store import is_s3_store, put_artifact, resolve_run_id
        except ImportError:
            return
        if not is_s3_store():
            return
        run_id = self._run_id() or resolve_run_id({"targetApp": self.target_app})
        if not run_id:
            print(
                f"[{self.agent_name}] telemetry mirror skipped: no run_id",
                file=sys.stderr,
            )
            return
        rel_path = f"{self.target_app}/telemetry/{self.agent_name}-telemetry.json"
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    data["runId"] = run_id
                    payload = json.dumps(data, indent=2) + "\n"
                put_artifact(run_id, rel_path, payload, content_type="application/json")
                if attempt > 0:
                    print(
                        f"[{self.agent_name}] telemetry mirrored to S3 on retry",
                        file=sys.stderr,
                    )
                return
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    import time
                    time.sleep(0.5)
        print(
            f"[{self.agent_name}] WARNING: telemetry mirror to S3 failed after 2 attempts "
            f"(run={run_id}, path={rel_path}): {last_exc}",
            file=sys.stderr,
        )

    def print_compact(self, *, stream: Any = sys.stderr) -> None:
        """One-line token summary after each agent (default)."""
        cur = self.to_dict()
        model = cur.get("modelLabel") or ""
        model_note = f" ({model})" if model else ""
        print(
            f"[{self.agent_name}]{model_note} "
            f"{cur['elapsedSec']:.1f}s | in={cur['inputTokens']:,} out={cur['outputTokens']:,}",
            file=stream,
        )

    def print_summary(self, *, stream: Any = sys.stderr) -> None:
        """Print a one-screen telemetry block + delta vs the prior run."""
        previous = self.load_previous()
        cur = self.to_dict()
        prefix = f"[{self.agent_name}]"
        model_note = f" ({cur['modelLabel']})" if cur.get("modelLabel") else ""

        def _delta(curv: int | float, prev: int | float | None, unit: str = "") -> str:
            if prev is None:
                return ""
            d = curv - prev
            if isinstance(d, float):
                d = round(d, 2)
            if d == 0:
                return "  (= prev)"
            sign = "+" if d > 0 else ""
            return f"  ({sign}{d}{unit} vs prev)"

        prev = previous or {}
        cache_pct = self.cache_hit_ratio * 100
        prev_cache_pct = (prev.get("cacheHitRatio") or 0) * 100

        lines = [
            "",
            "=" * 64,
            f"{prefix} Telemetry{model_note} - {self.agent_name} on {self.target_app or '(no app)'}",
            "-" * 64,
            f"  wall clock        : {cur['elapsedSec']:>8.2f}s{_delta(cur['elapsedSec'], prev.get('elapsedSec'), 's')}",
            f"  tool calls        : {cur['toolCount']:>8d}{_delta(cur['toolCount'], prev.get('toolCount'))}",
            f"  input tokens      : {cur['inputTokens']:>8d}{_delta(cur['inputTokens'], prev.get('inputTokens'))}",
            f"  cache-read tokens : {cur['cacheReadInputTokens']:>8d}{_delta(cur['cacheReadInputTokens'], prev.get('cacheReadInputTokens'))}",
            f"  cache-write tokens: {cur['cacheWriteInputTokens']:>8d}{_delta(cur['cacheWriteInputTokens'], prev.get('cacheWriteInputTokens'))}",
            f"  output tokens     : {cur['outputTokens']:>8d}{_delta(cur['outputTokens'], prev.get('outputTokens'))}",
            f"  billed (in+out)   : {cur['totalTokens']:>8d}{_delta(cur['totalTokens'], prev.get('totalTokens'))}",
            f"  cache hit ratio   : {cache_pct:>7.1f}%{_delta(round(cache_pct, 1), round(prev_cache_pct, 1), '%')}",
        ]
        if self.extra:
            lines.append(f"  extra             : {json.dumps(self.extra, default=str)}")
        lines.append("=" * 64)
        print("\n".join(lines), file=stream)

    def finalize(
        self,
        *,
        stream: Any = sys.stderr,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Persist snapshot; compact line by default; full block when PIPELINE_TELEMETRY_VERBOSE=1."""
        self.ensure_run_id(context)
        if _telemetry_verbose():
            self.print_summary(stream=stream)
        elif not _telemetry_silent():
            self.print_compact(stream=stream)
        self.persist()


def _telemetry_verbose() -> bool:
    return os.getenv("PIPELINE_TELEMETRY_VERBOSE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _telemetry_silent() -> bool:
    return os.getenv("PIPELINE_TELEMETRY_SILENT", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


class StrandsTelemetryCallback:
    """Reusable Strands callback — tool progress + Bedrock usage capture."""

    def __init__(
        self,
        agent_name: str,
        telemetry: RunTelemetry | None = None,
        *,
        show_thinking: bool = False,
        log_tools: bool = True,
    ) -> None:
        self._agent_name = agent_name
        self._show_thinking = show_thinking
        self._log_tools = log_tools
        self.telemetry = telemetry

    def __call__(self, **kwargs: Any) -> None:
        reasoning_text = kwargs.get("reasoningText")
        if self._show_thinking and reasoning_text:
            print(reasoning_text, end="", file=sys.stderr)

        event = kwargs.get("event", {})
        tool_use = event.get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use:
            name = tool_use.get("name", "<unknown>")
            if self.telemetry is not None:
                self.telemetry.record_tool(name)
                if self._log_tools:
                    print(
                        f"\n[{self._agent_name}] Tool #{self.telemetry.tool_count}: {name}",
                        file=sys.stderr,
                    )
            elif self._log_tools:
                print(f"\n[{self._agent_name}] Tool: {name}", file=sys.stderr)

        if self.telemetry is not None:
            usage = usage_from_event(kwargs) or usage_from_event(event)
            if usage:
                self.telemetry.record_usage(usage)


def agent_telemetry_path(target_app: str, agent_name: str) -> Path:
    return _PIPELINE_DIR / f"{target_app}.{agent_name}-telemetry.json"


def pipeline_telemetry_path(target_app: str) -> Path:
    return _PIPELINE_DIR / f"{target_app}.pipeline-telemetry.json"


def load_agent_telemetry(target_app: str, agent_name: str) -> dict[str, Any] | None:
    path = agent_telemetry_path(target_app, agent_name)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def discover_agents_with_telemetry(target_app: str) -> list[str]:
    """Agent names that have a persisted telemetry snapshot for this target app."""
    if not _PIPELINE_DIR.is_dir():
        return []
    prefix = f"{target_app}."
    suffix = "-telemetry.json"
    found: set[str] = set()
    for path in _PIPELINE_DIR.glob(f"{prefix}*{suffix}"):
        if path.name == f"{target_app}.pipeline-telemetry.json":
            continue
        middle = path.name[len(prefix) : -len(suffix)]
        if middle:
            found.add(middle)
    ordered = [a for a in DEFAULT_PIPELINE_AGENTS if a in found]
    return ordered


def _billed_tokens(snap: dict[str, Any]) -> int:
    inp = int(snap.get("inputTokens", 0) or 0)
    out = int(snap.get("outputTokens", 0) or 0)
    return inp + out if (inp or out) else int(snap.get("totalTokens", 0) or 0)


def aggregate_pipeline_telemetry(
    target_app: str,
    agents: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Sum token usage across all persisted agent telemetry for this target app."""
    on_disk = discover_agents_with_telemetry(target_app)
    names = on_disk if on_disk else (list(agents) if agents else list(DEFAULT_PIPELINE_AGENTS))
    per_agent: list[dict[str, Any]] = []
    totals = {
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "cacheReadInputTokens": 0,
        "cacheWriteInputTokens": 0,
        "elapsedSec": 0.0,
        "toolCount": 0,
    }
    for name in names:
        snap = load_agent_telemetry(target_app, name)
        if not snap:
            continue
        per_agent.append(snap)
        totals["inputTokens"] += int(snap.get("inputTokens", 0) or 0)
        totals["outputTokens"] += int(snap.get("outputTokens", 0) or 0)
        totals["totalTokens"] += _billed_tokens(snap)
        totals["cacheReadInputTokens"] += int(snap.get("cacheReadInputTokens", 0) or 0)
        totals["cacheWriteInputTokens"] += int(snap.get("cacheWriteInputTokens", 0) or 0)
        totals["elapsedSec"] += float(snap.get("elapsedSec", 0) or 0)
        totals["toolCount"] += int(snap.get("toolCount", 0) or 0)

    return {
        "targetApp": target_app,
        "agents": per_agent,
        "totals": {
            **totals,
            "elapsedSec": round(totals["elapsedSec"], 2),
        },
    }


def print_pipeline_summary(
    target_app: str,
    agents: list[str] | tuple[str, ...] | None = None,
    *,
    agents_run: list[str] | tuple[str, ...] | None = None,
    stream: Any = sys.stderr,
) -> dict[str, Any]:
    """Print pipeline rollup table and persist agents/pipeline/<app>.pipeline-telemetry.json."""
    rollup = aggregate_pipeline_telemetry(target_app, agents)
    per_agent = rollup["agents"]
    totals = rollup["totals"]

    if not per_agent:
        print(
            f"\n[pipeline] No agent telemetry files for {target_app!r} "
            f"(expected under agents/pipeline/)",
            file=stream,
        )
        return rollup

    width = 72
    lines = [
        "",
        "=" * width,
        f"Pipeline token usage - {target_app}",
        "-" * width,
        f"  {'agent':<18} {'model':<12} {'input':>9} {'output':>9} {'billed':>9} {'time':>8}",
        "-" * width,
    ]
    for snap in per_agent:
        agent = str(snap.get("agent", "?"))[:18]
        model = str(snap.get("modelLabel") or short_model_label(str(snap.get("modelId", ""))))[:12]
        billed = _billed_tokens(snap)
        lines.append(
            f"  {agent:<18} {model:<12} "
            f"{int(snap.get('inputTokens', 0)):>9,} "
            f"{int(snap.get('outputTokens', 0)):>9,} "
            f"{billed:>9,} "
            f"{float(snap.get('elapsedSec', 0)):>7.1f}s"
        )
    lines.append("-" * width)
    lines.append(
        f"  {'TOTAL':<18} {'':<12} "
        f"{totals['inputTokens']:>9,} "
        f"{totals['outputTokens']:>9,} "
        f"{totals['totalTokens']:>9,} "
        f"{totals['elapsedSec']:>7.1f}s"
    )
    lines.append("=" * width)
    if agents_run:
        run_set = set(agents_run)
        rollup_names = [str(s.get("agent", "")) for s in per_agent]
        prior_only = [a for a in rollup_names if a not in run_set]
        if prior_only:
            lines.append(
                f"This run: {', '.join(agents_run)} | "
                f"rollup includes prior telemetry: {', '.join(prior_only)}"
            )
        else:
            lines.append(f"This run: {', '.join(agents_run)}")
    rel_path = pipeline_telemetry_path(target_app).relative_to(_REPO_ROOT).as_posix()
    lines.append(f"Saved: {rel_path}")
    print("\n".join(lines), file=stream)

    _PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        pipeline_telemetry_path(target_app).write_text(
            json.dumps(rollup, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    _mirror_pipeline_rollup_to_run_artifacts(target_app, rollup)
    return rollup


def _mirror_pipeline_rollup_to_run_artifacts(target_app: str, rollup: dict[str, Any]) -> None:
    """Upload pipeline rollup to runs/<runId>/<app>/telemetry/ for the control-plane UI."""
    try:
        from .artifact_store import is_s3_store, put_artifact, resolve_run_id
    except ImportError:
        return
    if not is_s3_store():
        return
    run_id = resolve_run_id({"targetApp": target_app})
    if not run_id:
        return
    payload = json.dumps(rollup, indent=2) + "\n"
    rel_path = f"{target_app}/telemetry/pipeline-telemetry.json"
    try:
        put_artifact(run_id, rel_path, payload, content_type="application/json")
    except Exception:
        pass


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
