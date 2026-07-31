"""CloudWatch Logs reader for Bedrock AgentCore runtimes.

Reads agent stdout/stderr from CloudWatch Logs so the control-plane UI can show
real cloud agent activity instead of only local smoke-script captures.

Usage:
    from _shared.cloudwatch_logs import list_cloudwatch_logs
    entries = list_cloudwatch_logs(agent="orchestrator-agent", minutes=30)

No agent or runtime changes are required — Bedrock AgentCore automatically
emits runtime stdout/stderr to a log group named:
    /aws/bedrock-agentcore/runtimes/<awsName>-<runtimeId>-DEFAULT

Mapping is loaded from config/agentcore/log-groups.json (derived from
runtimes.json; re-derive after any agent redeploy).
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config as BotoConfig

from botocore.exceptions import ClientError

_REPO = Path(__file__).resolve().parents[2]
_LOG_GROUPS_JSON = _REPO / "config" / "agentcore" / "log-groups.json"

_LEVEL_RE = re.compile(r"^(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL):")
_RUN_ID_RE = re.compile(r"\brun[_-]?id[=: ]+([A-Za-z0-9-]+)", re.IGNORECASE)

# Pipeline agents only - excludes optional runtimes like web-crawler from platform tail.
PIPELINE_LOG_AGENTS = frozenset({
    "orchestrator-agent",
    "product-agent",
    "architect-agent",
    "database-agent",
    "developer-agent",
    "gitlab-agent",
})


def _run_filter_patterns(run_id: str) -> list[str]:
    """CloudWatch filter patterns; agents log runId=, run_id=, or bare UUID in messages."""
    rid = run_id.strip()
    if not rid:
        return []
    return [
        f'"{rid}"',
        f'"run_id={rid}"',
        f'"runId={rid}"',
    ]


def _message_matches_run(message: str, run_id: str | None) -> bool:
    if not run_id:
        return False
    if run_id in message:
        return True
    extracted = _extract_run_id(message)
    return extracted == run_id if extracted else False


def _load_log_group_map() -> dict[str, dict[str, str]]:
    if not _LOG_GROUPS_JSON.is_file():
        return {}
    data = json.loads(_LOG_GROUPS_JSON.read_text(encoding="utf-8"))
    agents = data.get("agents") or {}
    if not isinstance(agents, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for agent_id, entry in agents.items():
        if isinstance(entry, dict) and entry.get("logGroup"):
            out[str(agent_id)] = {"logGroup": str(entry["logGroup"])}
    return out


def _logs_client(region: str | None = None):
    load_repo_env()
    region = region or os.getenv("AWS_REGION", "us-east-2")
    return boto3.client(
        "logs",
        region_name=region,
        config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
    )


def _parse_level(message: str) -> str:
    m = _LEVEL_RE.match(message)
    if m:
        lvl = m.group(1).upper()
        if lvl == "WARNING":
            return "warn"
        if lvl == "CRITICAL":
            return "error"
        return lvl.lower()
    lower = message.lower()
    if "traceback" in lower or "exception" in lower or lower.startswith("error"):
        return "error"
    if "warn" in lower or "degraded" in lower:
        return "warn"
    if "debug" in lower:
        return "debug"
    return "info"


def _extract_run_id(message: str) -> str | None:
    m = _RUN_ID_RE.search(message)
    return m.group(1) if m else None


def _strip_level_prefix(message: str) -> str:
    m = _LEVEL_RE.match(message)
    if not m:
        return message
    rest = message[m.end():]
    # Drop leading "logger:" prefix for display brevity.
    if rest.startswith(":"):
        rest = rest[1:]
    colon = rest.find(":")
    if 0 < colon < 60:
        rest = rest[colon + 1:]
    return rest.strip() or message


def _filter_one_log_group(
    client,
    *,
    agent_id: str,
    log_group: str,
    run_id: str | None,
    start_ms: int | None,
    end_ms: int | None = None,
    limit: int,
    filter_pattern: str | None = None,
    tag_run_id: str | None = None,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "logGroupName": log_group,
        "interleaved": True,
        "limit": min(limit, 10000),
    }
    if start_ms is not None:
        kwargs["startTime"] = start_ms
    if end_ms is not None:
        kwargs["endTime"] = end_ms
    if filter_pattern:
        kwargs["filterPattern"] = filter_pattern

    events: list[dict[str, Any]] = []
    try:
        paginator = client.get_paginator("filter_log_events")
        for page in paginator.paginate(**kwargs):
            for ev in page.get("events", []) or []:
                msg = ev.get("message", "") or ""
                if (
                    run_id
                    and not tag_run_id
                    and filter_pattern is None
                    and not _message_matches_run(msg, run_id)
                ):
                    continue
                events.append({
                    "id": f"cw-{agent_id}-{ev.get('eventId') or ev.get('timestamp')}-{len(events)}",
                    "ts": _ms_to_iso(ev.get("timestamp")),
                    "level": _parse_level(msg),
                    "agent": agent_id,
                    "runId": tag_run_id or _extract_run_id(msg) or (
                        run_id if run_id and _message_matches_run(msg, run_id) else ""
                    ),
                    "message": _strip_level_prefix(msg),
                    "stream": ev.get("logStreamName", ""),
                    "source": "cloudwatch",
                })
            if len(events) >= limit:
                break
    except ClientError as err:
        code = err.response.get("Error", {}).get("Code", "")
        if code in {"ResourceNotFoundException", "AccessDeniedException"}:
            return []
        raise
    return events[:limit]


def _fetch_log_group_for_run(
    client,
    *,
    agent_id: str,
    log_group: str,
    run_id: str,
    start_ms: int | None,
    end_ms: int | None,
    limit: int,
    time_window: bool = False,
) -> list[dict[str, Any]]:
    """Fetch run logs — time-window (all stdout) or UUID/runId pattern search."""
    if time_window and start_ms is not None:
        return _filter_one_log_group(
            client,
            agent_id=agent_id,
            log_group=log_group,
            run_id=run_id,
            start_ms=start_ms,
            end_ms=end_ms,
            limit=limit,
            filter_pattern=None,
            tag_run_id=run_id,
        )

    seen: set[str | int] = set()
    merged: list[dict[str, Any]] = []

    def _merge(batch: list[dict[str, Any]]) -> None:
        for row in batch:
            key = row.get("id") or row.get("message")
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

    per_pattern = max(20, limit // max(1, len(_run_filter_patterns(run_id))))
    for pattern in _run_filter_patterns(run_id):
        _merge(
            _filter_one_log_group(
                client,
                agent_id=agent_id,
                log_group=log_group,
                run_id=run_id,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=per_pattern,
                filter_pattern=pattern,
            )
        )
        if len(merged) >= limit:
            return merged[:limit]

    if len(merged) < limit // 4:
        _merge(
            _filter_one_log_group(
                client,
                agent_id=agent_id,
                log_group=log_group,
                run_id=run_id,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=limit,
                filter_pattern=None,
            )
        )
    return merged[:limit]


def _ms_to_iso(ms: int | None) -> str:
    if not ms:
        return ""
    # ms is epoch milliseconds from CloudWatch
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ms / 1000.0, tz=_dt.timezone.utc).isoformat()


def list_cloudwatch_logs(
    *,
    agent: str | None = None,
    run_id: str | None = None,
    minutes: int | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int = 500,
    region: str | None = None,
    mvp_only: bool = True,
    time_window_for_run: bool = False,
) -> list[dict[str, Any]]:
    """Fetch CloudWatch log events for one or all agents.

    Returns entries sorted newest-first, each with:
      id, ts (ISO), level, agent, runId, message, stream, source
    """
    agent_map = _load_log_group_map()
    if not agent_map:
        return []

    if agent:
        if agent not in agent_map:
            return []
        targets = {agent: agent_map[agent]["logGroup"]}
    else:
        targets = {
            aid: entry["logGroup"]
            for aid, entry in agent_map.items()
            if entry.get("logGroup")
        }

    if mvp_only:
        targets = {aid: lg for aid, lg in targets.items() if aid in PIPELINE_LOG_AGENTS}

    if start_ms is None and minutes and minutes > 0:
        import time as _time
        start_ms = int((_time.time() - minutes * 60) * 1000)

    client = _logs_client(region)
    per_agent_limit = max(50, limit // max(1, len(targets)))

    all_events: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(6, len(targets) or 1)) as ex:
        futures = []
        for aid, lg in targets.items():
            if run_id:
                futures.append(
                    ex.submit(
                        _fetch_log_group_for_run,
                        client,
                        agent_id=aid,
                        log_group=lg,
                        run_id=run_id,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        limit=per_agent_limit,
                        time_window=time_window_for_run,
                    )
                )
            else:
                futures.append(
                    ex.submit(
                        _filter_one_log_group,
                        client,
                        agent_id=aid,
                        log_group=lg,
                        run_id=None,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        limit=per_agent_limit,
                        filter_pattern=None,
                    )
                )
        for fut in as_completed(futures):
            try:
                all_events.extend(fut.result())
            except Exception:
                continue

    all_events.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return all_events[:limit]


def load_repo_env() -> None:
    """Best-effort .env load so AWS_PROFILE/AWS_REGION are visible."""
    try:
        from _shared.env import load_repo_env as _load  # type: ignore
        _load()
    except Exception:
        pass
