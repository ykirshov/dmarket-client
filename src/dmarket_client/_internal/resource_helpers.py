import math
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ..exceptions import RequestValidationError
from ..filters import TreeFilters, tree_filter
from ..models import Currency, Game, Money


def game_value(game: Game) -> Game:
    try:
        return Game(game)
    except ValueError, TypeError:
        raise RequestValidationError("Unsupported game") from None


def sequence[T](items: Sequence[T], *, name: str, maximum: int | None = None) -> list[T]:
    if isinstance(items, (str, bytes)) or not isinstance(items, Sequence) or not items:
        raise RequestValidationError(f"{name} must be a nonempty sequence")
    if maximum is not None and len(items) > maximum:
        raise RequestValidationError(f"{name} exceeds {maximum} elements")
    return list(items)


def identifiers(items: Sequence[str], *, name: str) -> list[str]:
    result = sequence(items, name=name)
    if any(not isinstance(x, str) or not x for x in result):
        raise RequestValidationError(f"{name} must contain nonempty strings")
    if len(set(result)) != len(result):
        raise RequestValidationError(f"{name} contains duplicate identifiers")
    return result


def payloads[T](items: Sequence[T], cls: type[T], *, maximum: int | None = None) -> list[T]:
    result = sequence(items, name="requests", maximum=maximum)
    if any(not isinstance(x, cls) for x in result):
        raise RequestValidationError(f"Expected {cls.__name__} request objects")
    return result


def listing(
    scope: str,
    game: Game,
    title: str | None,
    filters: TreeFilters | None,
    raw_tree_filters: str | None,
    order_by: str | None,
    order_dir: str | None,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    game = game_value(game)
    return {
        "gameId": game.value,
        "title": title,
        "treeFilters": tree_filter(filters, raw_tree_filters, game=game, scope=scope),
        "orderBy": order_by,
        "orderDir": order_dir,
        "limit": limit,
        "cursor": cursor,
    }


def price_range(low: Money | None, high: Money | None) -> dict[str, int | None]:
    for value in (low, high):
        if value is not None and (
            not isinstance(value, Money) or value.currency != Currency.USD or value.amount < 0
        ):
            raise RequestValidationError("Price bounds must be nonnegative USD Money values")
    if low is not None and high is not None and low.amount > high.amount:
        raise RequestValidationError("price_from cannot exceed price_to")
    return {
        "priceFrom": low.to_minor_units() if low is not None else None,
        "priceTo": high.to_minor_units() if high is not None else None,
    }


def unix(value: datetime | int | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise RequestValidationError("Datetime filters must include a timezone")
        return str(int(value.timestamp()))
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestValidationError("Time filters must be timezone-aware datetime or Unix integer")
    return str(value)


def positive_int(value: int, name: str, *, zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if zero else 1):
        raise RequestValidationError(f"{name} must be {'nonnegative' if zero else 'positive'}")
    return value


def closed(
    kind: str,
    limit: int,
    order_dir: str,
    created_from: datetime | int | None,
    created_to: datetime | int | None,
    closed_from: datetime | int | None,
    closed_to: datetime | int | None,
    finalization_from: datetime | int | None,
    finalization_to: datetime | int | None,
    statuses: Sequence[str] | None,
    cursor: str | None,
) -> dict[str, Any]:
    positive_int(limit, "limit")
    result: dict[str, Any] = {"Limit": str(limit), "OrderDir": order_dir, "Cursor": cursor}
    for prefix, start, end in [
        (f"{kind}Created", created_from, created_to),
        (f"{kind}Closed", closed_from, closed_to),
        ("Finalization", finalization_from, finalization_to),
    ]:
        a, b = unix(start), unix(end)
        if a is not None and b is not None and int(a) > int(b):
            raise RequestValidationError("Time range start exceeds end")
        result[prefix + ".From"], result[prefix + ".To"] = a, b
    if statuses is not None:
        result["Status"] = sequence(statuses, name="statuses")
    return result


def polling_args(timeout: float, interval: float) -> None:
    if not math.isfinite(timeout) or not math.isfinite(interval) or timeout <= 0 or interval <= 0:
        raise RequestValidationError("Polling timeout and interval must be positive and finite")
