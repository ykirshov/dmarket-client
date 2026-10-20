import math

import httpx
from pydantic import Field, field_validator

from ._version import __version__
from .models import InputModel


class ClientConfig(InputModel):
    base_url: str = "https://api.dmarket.com"
    request_timeout: float = Field(default=30.0, gt=0)
    total_timeout: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10, strict=True)
    retry_base_delay: float = Field(default=0.25, ge=0)
    retry_max_delay: float = Field(default=10.0, ge=0)
    user_agent: str = f"dmarket-client/{__version__}"

    @field_validator("request_timeout", "total_timeout", "retry_base_delay", "retry_max_delay")
    @classmethod
    def finite_timeout(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Timeouts and delays must be finite")
        return value

    @field_validator("base_url")
    @classmethod
    def safe_base_url(cls, value: str) -> str:
        url = httpx.URL(value)
        local_http = url.scheme == "http" and url.host in {"127.0.0.1", "localhost", "::1"}
        if (url.scheme != "https" and not local_http) or not url.host:
            raise ValueError("Use HTTPS, or loopback HTTP for local tests")
        if url.userinfo or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("base_url must be an origin without userinfo, path, query or fragment")
        return str(url).rstrip("/")
