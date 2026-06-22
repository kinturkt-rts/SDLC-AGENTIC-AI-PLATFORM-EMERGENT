"""AWS Bedrock Titan Embeddings client."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import boto3

from app.config import get_settings


class BedrockEmbedder:
    """Wraps Bedrock Titan Embedding calls."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.bedrock_region or settings.aws_region,
        )
        self._model_id = settings.bedrock_model_id

    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for the given text."""
        settings = get_settings()
        body: dict[str, object] = {"inputText": text}
        if "titan-embed-text-v2" in self._model_id:
            body["dimensions"] = settings.embedding_dimension
            body["normalize"] = True
        resp = self._client.invoke_model(
            modelId=self._model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(resp["body"].read())
        vector = result["embedding"]
        expected = settings.embedding_dimension
        if len(vector) != expected:
            raise ValueError(
                f"Bedrock model {self._model_id!r} returned {len(vector)} dimensions; "
                f"expected {expected}. Set EMBEDDING_DIMENSION and migrate vector(n) on RDS to match."
            )
        return vector

    def ping(self) -> bool:
        """Quick connectivity check."""
        self.embed("ping")
        return True


@lru_cache(maxsize=1)
def get_bedrock_client() -> BedrockEmbedder:
    return BedrockEmbedder()
