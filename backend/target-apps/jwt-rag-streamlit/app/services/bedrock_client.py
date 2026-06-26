import boto3
import json
from typing import List, Dict, Any
from app.config import get_settings


def get_bedrock_client():
    """Get Bedrock runtime client"""
    settings = get_settings()
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.bedrock_region or settings.aws_region
    )


def invoke_text(prompt: str, max_tokens: int = 4000) -> str:
    """Generate text using Claude Sonnet"""
    settings = get_settings()
    client = get_bedrock_client()
    
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    response = client.invoke_model(
        modelId=settings.bedrock_model_id,
        body=json.dumps(body)
    )
    
    response_body = json.loads(response["body"].read())
    return response_body["content"][0]["text"]


def invoke_embed(text: str) -> List[float]:
    """Generate embeddings using Titan Embed"""
    settings = get_settings()
    client = get_bedrock_client()
    
    body = {
        "inputText": text,
        "dimensions": settings.embed_dim,
        "normalize": True
    }
    
    response = client.invoke_model(
        modelId=settings.bedrock_embed_model_id,
        body=json.dumps(body)
    )
    
    response_body = json.loads(response["body"].read())
    return response_body["embedding"]
