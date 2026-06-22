"""AWS Bedrock Titan embedding client."""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


class BedrockClientError(RuntimeError):
    """Bedrock misconfiguration or invoke failure."""


class BedrockClient:
    def __init__(
        self,
        *,
        embed_model_id: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.embed_model_id = embed_model_id or get_settings().bedrock_embed_model_id
        if not self.embed_model_id:
            raise BedrockClientError("BEDROCK_EMBED_MODEL_ID is not set.")
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

    def invoke_embedding(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("text must not be empty")
        try:
            response = self._client.invoke_model(
                modelId=self.embed_model_id,
                accept="application/json",
                contentType="application/json",
                body=json.dumps({"inputText": text}),
            )
            payload = json.loads(response["body"].read())
            return [float(x) for x in payload["embedding"]]
        except (ClientError, BotoCoreError) as exc:
            logger.exception("Bedrock embedding failed model_id=%s", self.embed_model_id)
            raise BedrockClientError("Bedrock embedding failed") from exc
        except (KeyError, TypeError) as exc:
            raise BedrockClientError("Unexpected Bedrock embedding response") from exc


def get_bedrock_client() -> BedrockClient:
    return BedrockClient()
