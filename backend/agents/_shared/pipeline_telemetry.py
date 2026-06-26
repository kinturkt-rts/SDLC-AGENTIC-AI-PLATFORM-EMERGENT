"""CLI rollup for pipeline token usage — reads per-agent telemetry JSON files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.telemetry import DEFAULT_PIPELINE_AGENTS, print_pipeline_summary  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print pipeline token rollup from agents/pipeline/*.telemetry.json",
    )
    parser.add_argument("--target-app", required=True, help="Feature slug (target-apps/<app>)")
    parser.add_argument(
        "--agents-run",
        default="",
        help="Comma-separated agents executed in this pipeline invocation (footnote only)",
    )
    args = parser.parse_args()

    agents_run: list[str] | None = None
    if args.agents_run.strip():
        agents_run = [a.strip() for a in args.agents_run.split(",") if a.strip()]

    print_pipeline_summary(
        args.target_app,
        list(DEFAULT_PIPELINE_AGENTS),
        agents_run=agents_run,
    )


if __name__ == "__main__":
    main()
