"""Stable public exception hierarchy. Exceptions never include raw HTTP request objects."""

from typing import Any


class DMarketError(Exception):
    """Base class for SDK errors."""


class ConfigurationError(DMarketError, ValueError):
    pass


class RequestValidationError(DMarketError, ValueError):
    pass


class APIError(DMarketError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | int | None = None,
        endpoint: str = "",
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.endpoint = endpoint
        self.request_id = request_id


class AuthenticationError(APIError):
    pass


class PermissionDeniedError(APIError):
    pass


class NotFoundError(APIError):
    pass


class ConflictError(APIError):
    pass


class RateLimitError(APIError):
    pass


class ServerError(APIError):
    pass


class TransportError(DMarketError):
    def __init__(self, message: str, *, endpoint: str = "") -> None:
        super().__init__(message)
        self.endpoint = endpoint


class RequestTimeoutError(TransportError):
    pass


class IndeterminateOperationError(TransportError):
    """The server may have applied a write. Reconcile before repeating it."""

    def __init__(self, message: str, *, endpoint: str, request_id: str | None = None) -> None:
        super().__init__(message, endpoint=endpoint)
        self.request_id = request_id


class ResponseValidationError(DMarketError):
    def __init__(self, message: str, *, endpoint: str = "", request_id: str | None = None) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.request_id = request_id


class PaginationError(DMarketError):
    pass


class BatchOperationError(DMarketError):
    def __init__(self, result: Any) -> None:
        super().__init__(f"{len(result.failed)} batch item(s) failed; inspect .result")
        self.result = result


class DepositFailedError(DMarketError):
    def __init__(self, status: Any) -> None:
        super().__init__("Deposit failed; inspect .status for the server result")
        self.status = status


class PollingTimeoutError(DMarketError):
    def __init__(self, deposit_id: str, last_status: Any = None) -> None:
        super().__init__("Deposit did not complete within the polling deadline")
        self.deposit_id = deposit_id
        self.last_status = last_status
