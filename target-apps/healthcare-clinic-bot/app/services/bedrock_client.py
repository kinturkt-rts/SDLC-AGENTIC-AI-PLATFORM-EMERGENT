"""AWS Bedrock client for healthcare-clinic-bot."""
import json
import logging
from functools import lru_cache

import boto3

from app.config import get_settings

logger = logging.getLogger(__name__)


class BedrockClient:
    """Thin wrapper around Bedrock InvokeModel for text generation."""

    def __init__(self):
        settings = get_settings()
        self._client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        self._model_id = settings.bedrock_model_id

    def invoke_text(self, system_prompt: str, user_message: str) -> str:
        """Invoke the Bedrock model and return the text response."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message}
            ],
        })
        try:
            response = self._client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(response["body"].read())
            return result.get("content", [{}])[0].get("text", "")
        except Exception as exc:
            logger.error("Bedrock invocation failed: %s", exc)
            raise


@lru_cache(maxsize=1)
def get_bedrock_client() -> BedrockClient:
    """Singleton factory for BedrockClient."""
    return BedrockClient()
