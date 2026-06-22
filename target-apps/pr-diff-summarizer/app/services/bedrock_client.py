"""AWS Bedrock inference client for chat, triage, and RAG answer generation.

Use when design §2 specifies Bedrock (or another model on Bedrock). Routers should
call this module — not boto3 directly — so tests can patch `get_bedrock_client()`.

Local auth: AWS SSO / `AWS_PROFILE` (same as the SDLC agents). Do not hardcode keys.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


class BedrockClientError(RuntimeError):
    """Bedrock misconfiguration or invoke failure."""


class BedrockClient:
    """Thin sync wrapper around Bedrock Runtime Converse API."""

    def __init__(
        self,
        *,
        model_id: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model_id = model_id or get_settings().bedrock_model_id
        if not self.model_id:
            raise BedrockClientError(
                "BEDROCK_MODEL_ID is not set. Configure .env when design §2 requires Bedrock."
            )
        region = region_name or get_settings().aws_region
        if client is not None:
            self._client = client
        else:
            settings = get_settings()
            session_kwargs: dict[str, str] = {"region_name": region}
            profile = settings.aws_profile.strip()
            if profile:
                session_kwargs["profile_name"] = profile
            elif settings.aws_access_key_id and settings.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
                if settings.aws_session_token.strip():
                    session_kwargs["aws_session_token"] = settings.aws_session_token
            session = boto3.Session(**session_kwargs)
            self._client = session.client("bedrock-runtime")

    def invoke_text(
        self,
        *,
        user_message: str,
        system_message: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Run a single user turn and return the assistant text response."""
        if not user_message.strip():
            raise ValueError("user_message must not be empty")

        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_message}],
                }
            ],
        }
        if system_message:
            request["system"] = [{"text": system_message}]

        inference_config: dict[str, Any] = {}
        if max_tokens is not None:
            inference_config["maxTokens"] = max_tokens
        elif get_settings().bedrock_max_tokens:
            inference_config["maxTokens"] = get_settings().bedrock_max_tokens
        if temperature is not None:
            inference_config["temperature"] = temperature
        if inference_config:
            request["inferenceConfig"] = inference_config

        try:
            response = self._client.converse(**request)
        except (ClientError, BotoCoreError) as exc:
            logger.exception("Bedrock converse failed model_id=%s", self.model_id)
            raise BedrockClientError("Bedrock invoke failed") from exc

        try:
            return response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise BedrockClientError("Unexpected Bedrock response shape") from exc

    def invoke_embedding(self, text: str) -> list[float]:
        """Return a Titan embedding vector for `text` (RAG ingestion + query).

        Only used by the pgvector RAG pattern. Requires BEDROCK_EMBED_MODEL_ID
        (e.g. amazon.titan-embed-text-v2:0 → 1024 dims).
        """
        import json

        embed_model = get_settings().bedrock_embed_model_id
        if not embed_model:
            raise BedrockClientError(
                "BEDROCK_EMBED_MODEL_ID is not set. Configure .env for RAG embeddings."
            )
        if not text.strip():
            raise ValueError("text must not be empty")
        try:
            response = self._client.invoke_model(
                modelId=embed_model,
                accept="application/json",
                contentType="application/json",
                body=json.dumps({"inputText": text}),
            )
            payload = json.loads(response["body"].read())
            return list(payload["embedding"])
        except (ClientError, BotoCoreError) as exc:
            logger.exception("Bedrock embedding failed model_id=%s", embed_model)
            raise BedrockClientError("Bedrock embedding failed") from exc
        except (KeyError, TypeError) as exc:
            raise BedrockClientError("Unexpected Bedrock embedding response") from exc


def get_bedrock_client() -> BedrockClient:
    """Factory for FastAPI dependencies; override in tests with a fake client."""
    return BedrockClient()
