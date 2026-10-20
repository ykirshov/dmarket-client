import os
import random
import re
import time
from typing import Any, Literal, Self, TypeVar, cast

import httpx

from ..config import ClientConfig
from ..exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    IndeterminateOperationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    RequestTimeoutError,
    ResponseValidationError,
    ServerError,
    TransportError,
)
from ..metadata import ResponseMetadata
from ..models import ResponseModel, WithdrawalCreated
from ..rate_limits import Limiter, RateLimiter, retry_after
from .adapters import adapt, snapshot
from .auth import Signer
from .endpoints import ENDPOINTS
from .endpoints_base import Endpoint
from .serialization import decode_json
from .wire_base import WireModel

T = TypeVar("T", bound=ResponseModel | WireModel)


class Core:
    def __init__(
        self,
        public_key: str,
        secret_key: str,
        *,
        config: ClientConfig | None = None,
        rate_limiter: Limiter | Literal[False] | None = None,
        secret_key_is_seed: bool = False,
    ) -> None:
        self.config = config or ClientConfig()
        self._signer = Signer.from_hex(
            public_key, secret_key, secret_key_is_seed=secret_key_is_seed
        )
        self._redact_values = (public_key, public_key.lower(), secret_key, secret_key.lower())
        self._limiter: Limiter | None = (
            None if rate_limiter is False else (rate_limiter or RateLimiter())
        )
        self._closed = False

    @classmethod
    def from_env(cls, **kwargs: Any) -> Self:
        public, secret = os.getenv("DMARKET_PUBLIC_KEY"), os.getenv("DMARKET_SECRET_KEY")
        if not public or not secret:
            raise ConfigurationError("Set DMARKET_PUBLIC_KEY and DMARKET_SECRET_KEY")
        return cls(public, secret, **kwargs)

    def _remaining(self, deadline: float, endpoint: str) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RequestTimeoutError("Request budget exhausted before sending", endpoint=endpoint)
        return remaining

    def _wait_delay(self, deadline: float, endpoint: Endpoint, delay: float) -> float:
        if delay >= self._remaining(deadline, endpoint.path):
            raise RequestTimeoutError(
                "Rate limit or retry exceeds request budget", endpoint=endpoint.path
            )
        return delay

    def _prepare(
        self,
        operation: str,
        params: dict[str, Any] | None,
        path_params: dict[str, str] | None,
        body: dict[str, Any] | None,
        deadline: float | None,
    ) -> tuple[Endpoint, str, bytes, float]:
        if self._closed:
            raise ConfigurationError("Client is closed")
        end = (
            min(deadline, time.monotonic() + self.config.total_timeout)
            if deadline is not None
            else time.monotonic() + self.config.total_timeout
        )
        endpoint = ENDPOINTS[operation]
        relative_url, content = endpoint.prepare(params=params, path_params=path_params, body=body)
        return endpoint, relative_url, content, end

    def _request(
        self,
        http: httpx.Client | httpx.AsyncClient,
        endpoint: Endpoint,
        relative_url: str,
        content: bytes,
        deadline: float,
    ) -> httpx.Request:
        headers = {"User-Agent": self.config.user_agent, "Accept": "application/json"}
        if endpoint.body is not None:
            headers["Content-Type"] = "application/json"
        request = http.build_request(
            endpoint.method,
            self.config.base_url + relative_url,
            content=content,
            headers=headers,
            timeout=min(self.config.request_timeout, self._remaining(deadline, endpoint.path)),
        )
        request.headers.update(self._signer.headers(endpoint.method, request.url, request.content))
        return request

    def _sanitized(self, value: object) -> str:
        text = str(value)
        for secret in self._redact_values:
            text = text.replace(secret, "[REDACTED]")
        text = re.sub(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
        text = re.sub(r"\b[0-9a-fA-F]{32,}\b", "[REDACTED]", text)
        text = re.sub(
            r"(?i)(token|secret|api[-_ ]?key|signature)\s*[=:]\s*\S+", r"\1=[REDACTED]", text
        )
        return text[:500]

    def _api_error(self, endpoint: Endpoint, response: httpx.Response) -> APIError:
        code: str | int | None = None
        message = "DMarket returned an HTTP error"
        try:
            obj = decode_json(response.content)
            if isinstance(obj, dict):
                candidate = obj.get("code", obj.get("Code"))
                if isinstance(candidate, (str, int)) and not isinstance(candidate, bool):
                    code = candidate
                message = self._sanitized(
                    obj.get("message") or obj.get("Message") or obj.get("error") or message
                )
        except ValueError, UnicodeError:
            pass
        status = response.status_code
        cls: type[APIError] = {
            401: AuthenticationError,
            403: PermissionDeniedError,
            404: NotFoundError,
            409: ConflictError,
            429: RateLimitError,
        }.get(status, ServerError if status >= 500 else APIError)
        return cls(
            message,
            status_code=status,
            code=code,
            endpoint=endpoint.path,
            request_id=response.headers.get("x-request-id"),
        )

    def _decode(
        self,
        endpoint: Endpoint,
        response: httpx.Response,
        attempts: int,
        body: dict[str, Any] | None,
        response_type: type[T],
    ) -> T:
        if not 200 <= response.status_code < 300:
            raise self._api_error(endpoint, response)
        try:
            raw = decode_json(response.content)
            if not isinstance(raw, dict):
                raise ValueError("Expected an object")
            validated = endpoint.response.model_validate(raw)
            result = adapt(endpoint.name, raw, validated)
            if endpoint.name == "withdraw":
                result = snapshot(
                    WithdrawalCreated,
                    raw,
                    transfer_id=raw["transferId"],
                    request_id=(body or {})["requestId"],
                )
            result.metadata = ResponseMetadata(
                status_code=response.status_code,
                request_id=response.headers.get("x-request-id"),
                attempts=attempts,
                rate_limit_headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.startswith(("ratelimit-", "x-ratelimit-"))
                },
            )
            return cast(T, result)
        except ValueError, TypeError, KeyError, ArithmeticError:
            raise ResponseValidationError(
                "DMarket response does not match the endpoint contract",
                endpoint=endpoint.path,
                request_id=response.headers.get("x-request-id"),
            ) from None

    def _backoff(self, attempt: int, response: httpx.Response | None = None) -> float:
        if response is not None:
            server = retry_after(response.headers)
            if server is not None:
                return server
        ceiling = min(self.config.retry_max_delay, self.config.retry_base_delay * 2**attempt)
        return random.uniform(ceiling / 2, ceiling)  # noqa: S311

    def _transport_error(
        self,
        endpoint: Endpoint,
        exc: Exception,
        body: dict[str, Any] | None,
    ) -> TransportError:
        if not endpoint.safe_to_retry and not isinstance(
            exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
        ):
            return IndeterminateOperationError(
                "Write outcome is unknown; reconcile before repeating the operation",
                endpoint=endpoint.path,
                request_id=(body or {}).get("requestId"),
            )
        cls = (
            RequestTimeoutError
            if isinstance(exc, (httpx.TimeoutException, TimeoutError))
            else TransportError
        )
        return cls("HTTP request failed", endpoint=endpoint.path)

    def _observe(self, endpoint: Endpoint, response: httpx.Response) -> None:
        if self._limiter is not None:
            self._limiter.observe(endpoint.group, response.headers)

    def _retry_status(self, endpoint: Endpoint, attempt: int, status: int) -> bool:
        return (
            endpoint.safe_to_retry
            and attempt < self.config.max_retries
            and status in {429, 500, 502, 503, 504}
        )
