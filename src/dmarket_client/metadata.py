from pydantic import BaseModel, Field


class ResponseMetadata(BaseModel):
    status_code: int
    request_id: str | None = None
    attempts: int = 1
    rate_limit_headers: dict[str, str] = Field(default_factory=dict)
