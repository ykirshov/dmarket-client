"""Keyword types shared by list methods and lazy iterators."""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Required, TypedDict

from .filters import InventoryFilters, OfferFilters, TargetFilters
from .models import Game, Money, OrderDir, TradeStatus


class ListingParams(TypedDict, total=False):
    game: Required[Game]
    title: str | None
    order_dir: OrderDir | None
    limit: int
    cursor: str | None
    raw_tree_filters: str | None


class InventoryParams(ListingParams, total=False):
    filters: InventoryFilters | None
    order_by: Literal["price", "title", "float", "createdAt", "updatedAt"] | None


class OffersParams(ListingParams, total=False):
    filters: OfferFilters | None
    order_by: Literal["price", "title", "float", "createdAt"] | None


class MarketParams(ListingParams, total=False):
    filters: OfferFilters | None
    order_by: Literal["price", "title", "float", "createdAt", "discount"] | None
    price_from: Money | None
    price_to: Money | None
    with_images: bool | None
    offer_type: Literal["dmarket", "p2p", "all"] | None
    online_sellers_only: bool | None


class TargetsParams(ListingParams, total=False):
    filters: TargetFilters | None
    order_by: Literal["price", "title", "createdAt"] | None
    price_from: Money | None
    price_to: Money | None


class ClosedParams(TypedDict, total=False):
    limit: int
    order_dir: OrderDir
    created_from: datetime | int | None
    created_to: datetime | int | None
    closed_from: datetime | int | None
    closed_to: datetime | int | None
    finalization_from: datetime | int | None
    finalization_to: datetime | int | None
    statuses: Sequence[TradeStatus] | None
    cursor: str | None


class BlockedParams(TypedDict, total=False):
    game: Required[Game]
    limit: int
    cursor: str | None


class AggregatedParams(TypedDict, total=False):
    game: Required[Game]
    titles: Required[Sequence[str]]
    include_p2p: bool | None
    limit: int
    cursor: str | None


class SalesParams(TypedDict, total=False):
    game: Required[Game]
    title: Required[str]
    filters: str | None
    tx_operation_types: Sequence[Literal["Offer", "Target"]] | None
    limit: int
    offset: int


class FeesParams(TypedDict, total=False):
    game: Required[Game]
    offer_type: Literal["dmarket", "p2p"]
    limit: int
    offset: int
