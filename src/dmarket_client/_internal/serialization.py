"""One serialization of the exact bytes that are signed and sent."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import simplejson


def _default(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON type: {type(value).__name__}")


def encode_json(data: object) -> bytes:
    return simplejson.dumps(
        data,
        use_decimal=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        default=_default,
    ).encode("utf-8")


def decode_json(data: bytes) -> Any:
    return simplejson.loads(data, use_decimal=True, allow_nan=False)


def decimal_value(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Expected an exact decimal string, integer or Decimal")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("Monetary values must be finite")
    return result
