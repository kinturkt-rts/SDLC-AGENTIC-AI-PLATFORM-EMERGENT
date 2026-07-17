"""Set AgentCore runtime lifecycle settings (idle timeout + max lifetime).

The async pipeline keeps sessions alive with HealthyBusy pings while background
work runs, so lifecycle settings are a safety net, not the primary mechanism:
- idleRuntimeSessionTimeout: how long a session may report "Healthy" (idle)
  before termination. Raised so brief quiet gaps (e.g. between the developer
  handoff completing and the orchestrator's next poll) never kill a session.
- maxLifetime: hard ceiling per microVM instance (background thread state dies
  with the instance) — keep runs well under this.

UpdateAgentRuntime requires the full runtime definition, so this script reads
the current definition via GetAgentRuntime and re-submits it with the new
lifecycleConfiguration.

Usage (from backend/):
  python scripts/update-agentcore-lifecycle.py --dry-run
  python scripts/update-agentcore-lifecycle.py
  python scripts/update-agentcore-lifecycle.py --agents orchestrator-agent,developer-agent
  python scripts/update-agentcore-lifecycle.py --idle-timeout 3600 --max-lifetime 28800
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.env import load_repo_env  # noqa: E402

load_repo_env()

RUNTIMES_CONFIG = _REPO_ROOT / "config" / "agentcore" / "runtimes.json"
DEFAULT_IDLE_TIMEOUT_SEC = 3600  # 1h (default 900s/15m)
DEFAULT_MAX_LIFETIME_SEC = 28800  # 8h (service maximum)
# Runtimes that host long-running async work benefit most; update all deployed
# MVP agents by default so every hop has the same safety net.
DEFAULT_AGENTS = (
    "orchestrator-agent",
    "product-agent",
    "architect-agent",
    "database-agent",
    "developer-agent",
    "gitlab-agent",
)

# GetAgentRuntime response fields accepted back by UpdateAgentRuntime.
_UPDATABLE_FIELDS = (
    "agentRuntimeArtifact",
    "roleArn",
    "networkConfiguration",
    "protocolConfiguration",
    "environmentVariables",
    "authorizerConfiguration",
    "requestHeaderConfiguration",
    "metadataConfiguration",
    "description",
)


def _load_runtimes() -> dict:
    return json.loads(RUNTIMES_CONFIG.read_text(encoding="utf-8"))


def update_lifecycle(
    agents: list[str],
    idle_timeout: int,
    max_lifetime: int,
    *,
    dry_run: bool,
) -> int:
    import boto3

    if not 60 <= idle_timeout <= 28800 or not 60 <= max_lifetime <= 28800:
        print("ERROR: timeouts must be within 60..28800 seconds")
        return 1
    if idle_timeout > max_lifetime:
        print("ERROR: idle timeout must be <= max lifetime")
        return 1

    config = _load_runtimes()
    region = config.get("region", "us-east-2")
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    failures = 0

    for agent in agents:
        entry = (config.get("agents") or {}).get(agent) or {}
        runtime_id = str(entry.get("runtimeId") or "").strip()
        if not entry.get("deployed") or not runtime_id:
            print(f"skip  {agent}: not deployed")
            continue

        current = client.get_agent_runtime(agentRuntimeId=runtime_id)
        existing = current.get("lifecycleConfiguration") or {}
        print(
            f"{agent} ({runtime_id}): "
            f"idle {existing.get('idleRuntimeSessionTimeout', 900)}s -> {idle_timeout}s, "
            f"maxLifetime {existing.get('maxLifetime', 28800)}s -> {max_lifetime}s"
        )
        if dry_run:
            continue

        kwargs = {k: current[k] for k in _UPDATABLE_FIELDS if current.get(k)}
        kwargs["agentRuntimeId"] = runtime_id
        kwargs["lifecycleConfiguration"] = {
            "idleRuntimeSessionTimeout": idle_timeout,
            "maxLifetime": max_lifetime,
        }
        try:
            client.update_agent_runtime(**kwargs)
            print(f"  updated {agent}")
        except Exception as exc:  # surface per-agent failures, keep going
            failures += 1
            print(f"  ERROR updating {agent}: {exc}")

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agents",
        default=",".join(DEFAULT_AGENTS),
        help="Comma-separated registry agent names (default: deployed MVP chain)",
    )
    parser.add_argument("--idle-timeout", type=int, default=DEFAULT_IDLE_TIMEOUT_SEC)
    parser.add_argument("--max-lifetime", type=int, default=DEFAULT_MAX_LIFETIME_SEC)
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()

    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    return update_lifecycle(
        agents,
        args.idle_timeout,
        args.max_lifetime,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())