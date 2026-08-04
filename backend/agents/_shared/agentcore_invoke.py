"""Invoke Bedrock AgentCore Runtimes by ARN (via boto3)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from .artifact_store import repo_root

logger = logging.getLogger(__name__)

RUNTIMES_CONFIG = repo_root() / "config" / "agentcore" / "runtimes.json"


def load_runtime_arn(agent_name: str) -> str | None:
    """Resolve specialist runtime ARN.

    Priority:
    1. ``AGENTCORE_PEER_RUNTIME_ARNS`` JSON map (``{"product-agent":"arn:..."}``)
       — used by demo orchestrator so peers stay env-pinned without rebuilding.
    2. ``AGENTCORE_RUNTIMES_CONFIG`` file (e.g. ``config/agentcore/runtimes.demo.json``)
    3. Default ``config/agentcore/runtimes.json``
    """
    raw_peers = os.getenv("AGENTCORE_PEER_RUNTIME_ARNS", "").strip()
    if raw_peers:
        try:
            peers = json.loads(raw_peers)
        except json.JSONDecodeError:
            logger.warning("AGENTCORE_PEER_RUNTIME_ARNS is not valid JSON")
            peers = None
        if isinstance(peers, dict):
            arn = str(peers.get(agent_name) or "").strip()
            if arn:
                return arn

    override = os.getenv("AGENTCORE_RUNTIMES_CONFIG", "").strip()
    if override:
        cfg_path = Path(override)
        if not cfg_path.is_absolute():
            cfg_path = repo_root() / cfg_path
    else:
        cfg_path = RUNTIMES_CONFIG

    if not cfg_path.is_file():
        return None
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    entry = (data.get("agents") or {}).get(agent_name) or {}
    arn = str(entry.get("runtimeArn") or "").strip()
    return arn or None


def _a2a_message_send_payload(message_text: str) -> bytes:
    body = {
        "jsonrpc": "2.0",
        "id": uuid4().hex,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": uuid4().hex,
                "parts": [{"kind": "text", "text": message_text}],
            }
        },
    }
    return json.dumps(body).encode("utf-8")


def extract_text_from_a2a_jsonrpc(data: dict[str, Any]) -> str:
    """Pull agent text from an A2A JSON-RPC response body."""
    if data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            return f"A2A error {err.get('code')}: {err.get('message')}"
        return f"A2A error: {err}"

    result = data.get("result")
    if not isinstance(result, dict):
        return json.dumps(data, indent=2)

    texts: list[str] = []
    for artifact in result.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        for part in artifact.get("parts") or []:
            if isinstance(part, dict) and part.get("kind") == "text":
                text = part.get("text")
                if text:
                    texts.append(str(text))

    message = result.get("message")
    if isinstance(message, dict):
        for part in message.get("parts") or []:
            if isinstance(part, dict) and part.get("kind") == "text":
                text = part.get("text")
                if text:
                    texts.append(str(text))

    if texts:
        return "\n".join(texts)
    return json.dumps(result, indent=2)


def _read_response_body(raw: Any) -> str:
    if raw is None:
        return ""
    if hasattr(raw, "read"):
        raw = raw.read()
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def invoke_agent_runtime_a2a(
    agent_name: str,
    message_text: str,
    *,
    timeout: int = 600,  # noqa: ARG001 — boto3 uses botocore read timeout from config
) -> dict[str, Any]:
    """Call invoke_agent_runtime with an A2A message/send JSON-RPC body."""
    arn = load_runtime_arn(agent_name)
    if not arn:
        return {
            "status": "error",
            "error": f"No runtimeArn for {agent_name} in {RUNTIMES_CONFIG}",
            "agent_name": agent_name,
        }

    import boto3
    from botocore.config import Config

    region = os.getenv("AWS_REGION", "us-east-2")
    client = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(read_timeout=timeout, connect_timeout=60, retries={"max_attempts": 1}),
    )
    session_id = uuid4().hex + "0"  # AgentCore requires runtimeSessionId length >= 33
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=session_id,
            payload=_a2a_message_send_payload(message_text),
            contentType="application/json",
            accept="application/json",
        )
    except Exception as exc:
        logger.exception("invoke_agent_runtime failed for %s", agent_name)
        return {
            "status": "error",
            "error": str(exc),
            "agent_name": agent_name,
            "runtime_arn": arn,
        }

    status_code = int(response.get("statusCode") or 200)
    body_text = _read_response_body(response.get("response"))
    if status_code >= 400:
        return {
            "status": "error",
            "error": f"HTTP {status_code}: {body_text[:500]}",
            "agent_name": agent_name,
            "runtime_arn": arn,
        }

    try:
        parsed = json.loads(body_text) if body_text.strip() else {}
    except json.JSONDecodeError:
        return {
            "status": "success",
            "response": {"raw": body_text},
            "text": body_text,
            "agent_name": agent_name,
            "runtime_arn": arn,
            "runtime_session_id": session_id,
        }

    text = extract_text_from_a2a_jsonrpc(parsed)
    return {
        "status": "success",
        "response": parsed,
        "text": text,
        "agent_name": agent_name,
        "runtime_arn": arn,
        "runtime_session_id": session_id,
    }


def should_use_agentcore_arn_invoke() -> bool:
    """Use boto3 invoke when running on AgentCore or when S3 pipeline mode is enabled."""
    flag = os.getenv("AGENTCORE_USE_ARN_INVOKE", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    if os.getenv("AGENTCORE_AGENT", "").strip():
        return True
    from .artifact_store import is_s3_store

    return is_s3_store()

