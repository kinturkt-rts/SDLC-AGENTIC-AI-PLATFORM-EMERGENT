"""Amazon Bedrock client wrapper for LLM inference and embedding."""
from __future__ import annotations

import json
import logging
from functools import lru_cache

import boto3

from app.config import get_settings

logger = logging.getLogger(__name__)


class BedrockClient:
    """Wrapper around Bedrock Runtime for text generation and embedding."""

    def __init__(self) -> None:
        settings = get_settings()
        self._runtime = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
        )
        self._model_id = settings.bedrock_model_id
        self._embed_model_id = settings.bedrock_embed_model_id
        self._max_tokens = settings.bedrock_max_tokens

    def invoke_text(self, prompt: str) -> str:
        """Generate text using Claude."""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = self._runtime.invoke_model(
            modelId=self._model_id,
            body=json.dumps(body),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    def invoke_embed(self, text: str) -> list[float]:
        """Generate embedding using Titan Embed."""
        body = {
            "inputText": text,
        }
        response = self._runtime.invoke_model(
            modelId=self._embed_model_id,
            body=json.dumps(body),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    def ping(self) -> bool:
        """Simple health check — just verifies client is instantiated."""
        return True


@lru_cache(maxsize=1)
def get_bedrock_client() -> BedrockClient:
    return BedrockClient()
