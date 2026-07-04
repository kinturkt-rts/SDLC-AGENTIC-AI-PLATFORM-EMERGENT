"""Dry-run dashboard token telemetry — prints JSON the UI would show."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.telemetry import aggregate_pipeline_telemetry  # noqa: E402

# Mirror frontend/src/lib/bedrock-pricing.ts (USD per 1M tokens).
_PRICING = {
    "sonnet": {"in": 3.0, "out": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "opus": {"in": 15.0, "out": 75.0, "cache_read": 1.5, "cache_write": 18.75},
    "haiku": {"in": 0.8, "out": 4.0, "cache_read": 0.08, "cache_write": 1.0},
}


def _family(model_id: str, model_label: str) -> str:
    text = f"{model_id} {model_label}".lower()
    if "opus" in text:
        return "opus"
    if "haiku" in text:
        return "haiku"
    return "sonnet"


def estimate_cost(snap: dict) -> float:
    rates = _PRICING[_family(str(snap.get("modelId", "")), str(snap.get("modelLabel", "")))]
    cost = (
        int(snap.get("inputTokens", 0) or 0) * rates["in"]
        + int(snap.get("outputTokens", 0) or 0) * rates["out"]
        + int(snap.get("cacheReadInputTokens", 0) or 0) * rates["cache_read"]
        + int(snap.get("cacheWriteInputTokens", 0) or 0) * rates["cache_write"]
    ) / 1_000_000
    return round(cost, 4)


def build_summary(project: str) -> dict:
    rollup = aggregate_pipeline_telemetry(project)
    agents = []
    total_cost = 0.0
    for snap in rollup["agents"]:
        billed = int(snap.get("inputTokens", 0) or 0) + int(snap.get("outputTokens", 0) or 0)
        cost = estimate_cost(snap)
        total_cost += cost
        agents.append(
            {
                "agentId": snap.get("agent"),
                "modelLabel": snap.get("modelLabel"),
                "inputTokens": snap.get("inputTokens", 0),
                "outputTokens": snap.get("outputTokens", 0),
                "totalTokens": billed,
                "costUsd": cost,
            }
        )
    totals = rollup["totals"]
    totals = {**totals, "costUsd": round(total_cost, 2)}
    return {"projectId": project, "agents": agents, "totals": totals}


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run dashboard telemetry for a project slug")
    parser.add_argument("project", help="Target app slug, e.g. platform-desk or contacts-api")
    parser.add_argument("--compare", action="store_true", help="Exit 1 when no telemetry files exist")
    args = parser.parse_args()

    summary = build_summary(args.project)
    print(json.dumps(summary, indent=2))

    if args.compare and not summary["agents"]:
        print(f"\nNo telemetry files for {args.project!r}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
