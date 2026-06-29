"""Inter-agent message contracts (BullMQ envelopes). JSON field `from` maps to from_agent."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

AgentName = Literal[
    "orchestrator-agent",
    "product-agent",
    "architect-agent",
    "web-crawler-agent",
    "database-agent",
    "developer-agent",
    "gitlab-agent",
    "qa-agent",
    "devops-agent",
    "security-agent",
]

MessageType = Literal["task.assign", "task.result", "task.error", "task.status"]


class AgentMessage(BaseModel):
    id: str
    correlationId: str
    from_agent: str = Field(alias="from")
    to: str
    type: MessageType
    payload: Any
    createdAt: str

    model_config = {"populate_by_name": True}


class TaskPayload(BaseModel):
    taskId: str
    description: str
    context: Optional[dict[str, Any]] = None


class Artifact(BaseModel):
    type: Literal["file", "url", "json"]
    name: str
    content: str


class ResultPayload(BaseModel):
    taskId: str
    status: Literal["success", "failure", "partial"]
    output: Any
    artifacts: Optional[list[Artifact]] = None