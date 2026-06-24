"""Auth request/response schemas."""
from pydantic import BaseModel, ConfigDict, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str
    display_name: str

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)
