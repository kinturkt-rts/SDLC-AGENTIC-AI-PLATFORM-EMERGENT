"""Synchronous A2A peer invocation for the SDLC pipeline runner."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

from .a2a_registry import agent_base_url

logger = logging.getLogger(__name__)

DEFAULT_A2A_TIMEOUT = 600


def format_agent_task(task: str, context: dict[str, Any] | None = None) -> str:
    """Build the task body specialist agents expect (task + JSON context)."""
    if not context:
        return task
    return f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"


async def _send_message_async(
    target_url: str,
    message_text: str,
    *,
    timeout: int = DEFAULT_A2A_TIMEOUT,
) -> dict[str, Any]:
    """Send one A2A user message and return the first response event."""
    base_url = target_url.rstrip("/") + "/"
    async with httpx.AsyncClient(timeout=timeout) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
        agent_card = await resolver.get_agent_card()
        config = ClientConfig(httpx_client=httpx_client, streaming=False)
        client = ClientFactory(config).create(agent_card)
        message_id = uuid4().hex
        message = Message(
            kind="message",
            role=Role.user,
            parts=[Part(TextPart(kind="text", text=message_text))],
            message_id=message_id,
        )
        async for event in client.send_message(message):
            if isinstance(event, Message):
                return {
                    "status": "success",
                    "response": event.model_dump(mode="python", exclude_none=True),
                    "message_id": message_id,
                    "target_agent_url": base_url,
                }
            if isinstance(event, tuple) and len(event) == 2:
                task_obj, update_event = event
                return {
                    "status": "success",
                    "response": {
                        "task": task_obj.model_dump(mode="python", exclude_none=True),
                        "update": (
                            update_event.model_dump(mode="python", exclude_none=True)
                            if update_event
                            else None
                        ),
                    },
                    "message_id": message_id,
                    "target_agent_url": base_url,
                }
            return {
                "status": "success",
                "response": {"raw_response": str(event)},
                "message_id": message_id,
                "target_agent_url": base_url,
            }
    return {"status": "error", "error": "No response from agent", "target_agent_url": base_url}


def invoke_agent(
    agent_name: str,
    task: str,
    *,
    context: dict[str, Any] | None = None,
    timeout: int = DEFAULT_A2A_TIMEOUT,
) -> dict[str, Any]:
    """Invoke a specialist agent by registry name (AgentCore ARN or A2A HTTP)."""
    body = format_agent_task(task, context)

    if should_use_agentcore_arn_invoke():
        from .agentcore_invoke import invoke_agent_runtime_a2a

        result = invoke_agent_runtime_a2a(agent_name, body, timeout=timeout)
        if result.get("status") == "success":
            return result
        logger.warning(
            "AgentCore ARN invoke failed for %s: %s",
            agent_name,
            result.get("error"),
        )

    url = agent_base_url(agent_name).rstrip("/")
    try:
        http_result = asyncio.run(_send_message_async(url, body, timeout=timeout))
        return http_result
    except Exception as exc:
        logger.exception("A2A HTTP invoke failed for %s", agent_name)
        return {"status": "error", "error": str(exc), "target_agent_url": url}


def should_use_agentcore_arn_invoke() -> bool:
    from .agentcore_invoke import should_use_agentcore_arn_invoke as _should

    return _should()


def response_text(result: dict[str, Any]) -> str:
    """Extract human-readable text from an A2A invoke result."""
    if result.get("text"):
        return str(result["text"])
    if result.get("status") != "success":
        return str(result.get("error") or result)
    payload = result.get("response") or {}
    if isinstance(payload, dict) and "parts" in payload:
        parts = payload.get("parts") or []
        texts: list[str] = []
        for part in parts:
            if isinstance(part, dict):
                text = part.get("text")
                if text:
                    texts.append(str(text))
        if texts:
            return "\n".join(texts)
    return json.dumps(payload, indent=2)
