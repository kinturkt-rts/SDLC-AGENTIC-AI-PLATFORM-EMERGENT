"""Aggregate per-agent elapsedSec from local + S3 telemetry snapshots."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "agents"))

from _shared.env import load_repo_env

load_repo_env()

AGENTS = [
    "product-agent",
    "architect-agent",
    "database-agent",
    "developer-agent",
    "gitlab-agent",
    "orchestrator-agent",
    "qa-agent",
]
MVP = ["product-agent", "architect-agent", "database-agent", "developer-agent"]


def _load_local() -> list[tuple[str, str, float, str | None, int]]:
    pipeline = _REPO / "agents" / "pipeline"
    rows: list[tuple[str, str, float, str | None, int]] = []
    for f in pipeline.glob("*.*-telemetry.json"):
        if ".pipeline-telemetry.json" in f.name:
            continue
        m = re.match(r"(.+)\.(.+-agent)-telemetry\.json$", f.name)
        if not m:
            continue
        app, agent = m.group(1), m.group(2)
        if agent not in AGENTS:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        elapsed = d.get("elapsedSec")
        if elapsed is None:
            continue
        rows.append((app, agent, float(elapsed), d.get("runId"), int(d.get("toolCount") or 0)))
    return rows


def _load_s3() -> list[tuple[str, str, float, str | None, int]]:
    rows: list[tuple[str, str, float, str | None, int]] = []
    if os.getenv("ARTIFACT_STORE", "").strip().lower() != "s3":
        return rows
    try:
        from _shared.artifact_store import list_run_ids, get_run_artifact_json
    except ImportError:
        return rows

    for run_id in list_run_ids()[:80]:
        for agent in AGENTS:
            for rel in (
                f"telemetry/{agent}-telemetry.json",
                f"handoffs/{agent}-telemetry.json",
            ):
                # try per-app paths under run prefix
                pass
        # list via prefix scan is heavy; use index if available
    return rows


def _summarize(rows: list[tuple[str, str, float, str | None, int]], label: str) -> None:
    by_agent: dict[str, list[float]] = defaultdict(list)
    for _app, agent, elapsed, _rid, _tc in rows:
        by_agent[agent].append(elapsed)

    print(f"\n=== {label} ===")
    for agent in AGENTS:
        vals = by_agent.get(agent, [])
        if not vals:
            print(f"  {agent:22}  (no data)")
            continue
        avg = sum(vals) / len(vals)
        med = sorted(vals)[len(vals) // 2]
        print(
            f"  {agent:22}  n={len(vals):3}  avg={avg:7.1f}s  "
            f"min={min(vals):6.1f}s  max={max(vals):7.1f}s  median={med:6.1f}s"
        )

    mvp_total = 0.0
    print("\n  MVP agent share (avg elapsed):")
    mvp_avgs: dict[str, float] = {}
    for agent in MVP:
        vals = by_agent.get(agent, [])
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        mvp_avgs[agent] = avg
        mvp_total += avg
    if mvp_total > 0:
        for agent in MVP:
            avg = mvp_avgs.get(agent, 0)
            if avg:
                print(f"    {agent:22} {avg:7.1f}s  ({100 * avg / mvp_total:4.0f}%)")
        print(f"    {'TOTAL (4 LLM agents)':22} {mvp_total:7.1f}s")


def main() -> None:
    local = _load_local()
    _summarize(local, "LOCAL TELEMETRY FILES")

    dev = [(app, e) for app, agent, e, _r, _t in local if agent == "developer-agent"]
    dev.sort(key=lambda x: -x[1])
    if dev:
        print("\n=== TOP 5 LONGEST DEVELOPER RUNS (local) ===")
        for app, e in dev[:5]:
            print(f"  {app:30} {e:.1f}s")


if __name__ == "__main__":
    main()
