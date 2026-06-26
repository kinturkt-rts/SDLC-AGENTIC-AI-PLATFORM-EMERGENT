from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any


def logger(agent_name: str):
    class _Logger:
        def info(self, msg: str, **meta: Any) -> None:
            print(
                json.dumps({"level": "info", "agent": agent_name, "msg": msg, **meta}),
                flush=True,
            )

        def error(self, msg: str, **meta: Any) -> None:
            print(
                json.dumps({"level": "error", "agent": agent_name, "msg": msg, **meta}),
                file=sys.stderr,
                flush=True,
            )

    return _Logger()


def build_message(
    from_agent: str,
    to: str,
    msg_type: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "correlationId": correlation_id or str(uuid.uuid4()),
        "from": from_agent,
        "to": to,
        "type": msg_type,
        "payload": payload,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }