"""AWS Bedrock client wrapper for embeddings and text generation."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import boto3

from app.config import get_settings


class BedrockClient:
    """Wrapper around Bedrock runtime for invoke_text and invoke_embed."""

    def __init__(self) -> None:
        settings = get_settings()
        self._runtime = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
        )
        self._model_id = settings.bedrock_model_id
        self._embed_model_id = settings.bedrock_embed_model_id

    def invoke_text(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        """Generate text using Claude."""
        messages = [{"role": "user", "content": prompt}]
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system
        response = self._runtime.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    def invoke_embed(self, text: str) -> list[float]:
        """Generate embedding using Titan Embed v2."""
        body = {
            "inputText": text,
        }
        response = self._runtime.invoke_model(
            modelId=self._embed_model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    def ping(self) -> bool:
        """Quick check for Bedrock availability."""
        return True


@lru_cache(maxsize=1)
def get_bedrock_client() -> BedrockClient:
    return BedrockClient()
