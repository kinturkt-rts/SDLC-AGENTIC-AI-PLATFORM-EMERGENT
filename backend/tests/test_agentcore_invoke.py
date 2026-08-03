"""Tests for AgentCore ARN invoke helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_load_runtime_arn_peer_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AGENTCORE_PEER_RUNTIME_ARNS",
        '{"product-agent":"arn:aws:bedrock-agentcore:us-east-2:123:runtime/product_agent_demo-ABC"}',
    )
    arn = load_runtime_arn("product-agent")
    assert arn is not None
    assert "product_agent_demo" in arn


def test_load_runtime_arn_demo_config_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    demo = tmp_path / "runtimes.demo.json"
    demo.write_text(
        json.dumps(
            {
                "agents": {
                    "architect-agent": {
                        "runtimeArn": "arn:aws:bedrock-agentcore:us-east-2:123:runtime/architect_agent_demo-XYZ"
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("AGENTCORE_PEER_RUNTIME_ARNS", raising=False)
    monkeypatch.setenv("AGENTCORE_RUNTIMES_CONFIG", str(demo))
    arn = load_runtime_arn("architect-agent")
    assert arn is not None
    assert "architect_agent_demo" in arn
