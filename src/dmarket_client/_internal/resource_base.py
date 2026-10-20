from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import TYPE_CHECKING, Any

from ..exceptions import PaginationError, RequestValidationError
from ..models import Page

if TYPE_CHECKING:
    from ..async_client import AsyncDMarketClient
    from ..client import DMarketClient


def bounds(max_items: int | None, max_pages: int | None) -> None:
    for name, value in [("max_items", max_items), ("max_pages", max_pages)]:
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise RequestValidationError(f"{name} must be a nonnegative integer")


class SyncResource:
    def __init__(self, client: DMarketClient) -> None:
        self._client = client

    def _iterate[T](
        self,
        fetch: Callable[..., Page[T]],
        kwargs: dict[str, Any],
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        offset: bool = False,
    ) -> Iterator[T]:
        bounds(max_items, max_pages)
        if max_items == 0 or max_pages == 0:
            return
        kwargs = dict(kwargs)
        seen = {kwargs["cursor"]} if kwargs.get("cursor") else set()
        count, pages = 0, 0
        while True:
            page = fetch(**kwargs)
            pages += 1
            for item in page.items:
                yield item
                count += 1
                if max_items is not None and count >= max_items:
                    return
            if max_pages is not None and pages >= max_pages:
                return
            if offset:
                if not page.items or len(page.items) < kwargs.get("limit", 100):
                    return
                kwargs["offset"] = kwargs.get("offset", 0) + len(page.items)
            else:
                if not page.next_cursor:
                    return
                if page.next_cursor in seen:
                    raise PaginationError("Server repeated a pagination cursor")
                seen.add(page.next_cursor)
                kwargs["cursor"] = page.next_cursor


class AsyncResource:
    def __init__(self, client: AsyncDMarketClient) -> None:
        self._client = client

    async def _iterate[T](
        self,
        fetch: Callable[..., Awaitable[Page[T]]],
        kwargs: dict[str, Any],
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        offset: bool = False,
    ) -> AsyncIterator[T]:
        bounds(max_items, max_pages)
        if max_items == 0 or max_pages == 0:
            return
        kwargs = dict(kwargs)
        seen = {kwargs["cursor"]} if kwargs.get("cursor") else set()
        count, pages = 0, 0
        while True:
            page = await fetch(**kwargs)
            pages += 1
            for item in page.items:
                yield item
                count += 1
                if max_items is not None and count >= max_items:
                    return
            if max_pages is not None and pages >= max_pages:
                return
            if offset:
                if not page.items or len(page.items) < kwargs.get("limit", 100):
                    return
                kwargs["offset"] = kwargs.get("offset", 0) + len(page.items)
            else:
                if not page.next_cursor:
                    return
                if page.next_cursor in seen:
                    raise PaginationError("Server repeated a pagination cursor")
                seen.add(page.next_cursor)
                kwargs["cursor"] = page.next_cursor
