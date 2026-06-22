"""Health check schema."""
from pydantic import BaseModel


class HealthChecks(BaseModel):
    api: str
    database: str
    bedrock: str | None = None


class HealthResponse(BaseModel):
    status: str
    checks: HealthChecks
