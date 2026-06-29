"""Tests for AgentCore ARN invoke helpers."""

from __future__ import annotations

from agents._shared.agentcore_invoke import extract_text_from_a2a_jsonrpc, load_runtime_arn


def test_extract_text_from_a2a_artifacts() -> None:
    data = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "artifacts": [
                {
                    "name": "agent_response",
                    "parts": [{"kind": "text", "text": "PRD created for inventory-app."}],
                }
            ]
        },
    }
    assert "PRD created" in extract_text_from_a2a_jsonrpc(data)


def test_load_runtime_arn_product_agent() -> None:
    arn = load_runtime_arn("product-agent")
    assert arn is not None
    assert "product_agent" in arn
