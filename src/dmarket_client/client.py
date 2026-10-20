import time
from typing import Any, Literal, Self

import httpx

from . import resources as r
from ._internal.core import Core
from ._internal.wire_base import WireModel
from .config import ClientConfig
from .exceptions import ConfigurationError
from .models import ResponseModel
from .rate_limits import Limiter


class DMarketClient(Core):
    """Reusable synchronous DMarket client. Close it or use a with block."""

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        *,
        config: ClientConfig | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        rate_limiter: Limiter | Literal[False] | None = None,
        secret_key_is_seed: bool = False,
    ) -> None:
        super().__init__(
            public_key,
            secret_key,
            config=config,
            rate_limiter=rate_limiter,
            secret_key_is_seed=secret_key_is_seed,
        )
        if http_client is not None and transport is not None:
            raise ConfigurationError("Pass http_client or transport, not both")
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(
            transport=transport, follow_redirects=False, trust_env=False
        )
        self.account = r.Account(self)
        self.inventory = r.Inventory(self)
        self.offers = r.Offers(self)
        self.targets = r.Targets(self)
        self.market = r.Market(self)
        self.deposits = r.Deposits(self)
        self.withdrawals = r.Withdrawals(self)
        self.fees = r.Fees(self)
        self.sales = r.Sales(self)

    def _execute[T: ResponseModel | WireModel](
        self,
        operation: str,
        *,
        response_type: type[T],
        params: dict[str, Any] | None = None,
        path_params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        deadline: float | None = None,
    ) -> T:
        endpoint, relative, content, end = self._prepare(
            operation, params, path_params, body, deadline
        )
        for attempt in range(self.config.max_retries + 1):
            if self._limiter is not None:
                while (delay := self._limiter.reserve(endpoint.group)) > 0:
                    time.sleep(self._wait_delay(end, endpoint, delay))
            request = self._request(self._http, endpoint, relative, content, end)
            try:
                response = self._http.send(request, follow_redirects=False)
            except httpx.RequestError as exc:
                if endpoint.safe_to_retry and attempt < self.config.max_retries:
                    time.sleep(self._wait_delay(end, endpoint, self._backoff(attempt)))
                    continue
                raise self._transport_error(endpoint, exc, body) from None
            self._observe(endpoint, response)
            if self._retry_status(endpoint, attempt, response.status_code):
                delay = self._backoff(attempt, response)
                response.close()
                time.sleep(self._wait_delay(end, endpoint, delay))
                continue
            try:
                return self._decode(endpoint, response, attempt + 1, body, response_type)
            finally:
                response.close()
        raise AssertionError("Unreachable retry state")

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._owns_http:
                self._http.close()

    def __enter__(self) -> Self:
        if self._closed:
            raise ConfigurationError("Client is closed")
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
