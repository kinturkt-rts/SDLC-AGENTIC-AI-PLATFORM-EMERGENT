"""Unit tests for BedrockClient — no live AWS calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.bedrock_client import BedrockClient, BedrockClientError


def test_invoke_text_returns_assistant_message() -> None:
    mock_runtime = MagicMock()
    mock_runtime.converse.return_value = {
        "output": {"message": {"content": [{"text": "likely cause: timeout"}]}}
    }
    client = BedrockClient(model_id="us.anthropic.claude-3-haiku", client=mock_runtime)

    result = client.invoke_text(
        user_message="Error: connection timed out",
        system_message="You are a triage bot.",
    )

    assert result == "likely cause: timeout"
    mock_runtime.converse.assert_called_once()


def test_invoke_text_rejects_empty_user_message() -> None:
    mock_runtime = MagicMock()
    client = BedrockClient(model_id="test-model", client=mock_runtime)

    with pytest.raises(ValueError, match="user_message"):
        client.invoke_text(user_message="   ")


def test_missing_model_id_raises() -> None:
    with pytest.raises(BedrockClientError, match="BEDROCK_MODEL_ID"):
        BedrockClient(model_id="", client=MagicMock())
