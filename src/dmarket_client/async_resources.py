"""Generated native async resources; edit resources.py and run tools/generate_async.py."""

import asyncio
import re
import time
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Any, Literal, Unpack
from uuid import uuid4

from . import models as m
from ._internal.resource_base import AsyncResource
from ._internal.resource_helpers import (
    closed,
    game_value,
    identifiers,
    listing,
    payloads,
    polling_args,
    positive_int,
    price_range,
    sequence,
)
from .exceptions import (
    DepositFailedError,
    PollingTimeoutError,
    RequestTimeoutError,
    RequestValidationError,
    ResponseValidationError,
)
from .filters import InventoryFilters, OfferFilters, TargetFilters
from .params import (
    AggregatedParams,
    BlockedParams,
    ClosedParams,
    FeesParams,
    InventoryParams,
    MarketParams,
    OffersParams,
    SalesParams,
    TargetsParams,
)


class Account(AsyncResource):
    async def get_profile(self) -> m.UserProfile:
        """Get the authenticated user's full profile. Contains sensitive account data."""
        return await self._client._execute("profile", response_type=m.UserProfile)

    async def get_balance(self) -> m.Balance:
        """Read USD as Money and exact DMC dimoshi as MinorMoney."""
        return await self._client._execute("balance", response_type=m.Balance)


class Inventory(AsyncResource):
    async def list_items(
        self,
        *,
        game: m.Game,
        title: str | None = None,
        filters: InventoryFilters | None = None,
        raw_tree_filters: str | None = None,
        order_by: Literal["price", "title", "float", "createdAt", "updatedAt"] | None = None,
        order_dir: m.OrderDir | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> m.Page[m.InventoryItem]:
        """List merged DMarket/Steam inventory, one cursor page at a time."""
        params = listing(
            "inventory", game, title, filters, raw_tree_filters, order_by, order_dir, limit, cursor
        )
        return await self._client._execute(
            "inventory", params=params, response_type=m.Page[m.InventoryItem]
        )

    def iter_items(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[InventoryParams],
    ) -> AsyncIterator[m.InventoryItem]:
        return self._iterate(
            self.list_items, dict(kwargs), max_items=max_items, max_pages=max_pages
        )

    async def sync(self, *, game: m.Game | m.SyncGame) -> m.InventorySyncResult:
        """Request a Steam inventory refresh; no automatic write retries."""
        return await self._client._execute(
            "sync",
            body={
                "Type": "Inventory",
                "GameID": game.value if isinstance(game, m.SyncGame) else game_value(game).sync_id,
            },
            response_type=m.InventorySyncResult,
        )


class Offers(AsyncResource):
    async def list(
        self,
        *,
        game: m.Game,
        title: str | None = None,
        filters: OfferFilters | None = None,
        raw_tree_filters: str | None = None,
        order_by: Literal["price", "title", "float", "createdAt"] | None = None,
        order_dir: m.OrderDir | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> m.Page[m.Offer]:
        """Read your active sell offers."""
        params = listing(
            "user_offers",
            game,
            title,
            filters,
            raw_tree_filters,
            order_by,
            order_dir,
            limit,
            cursor,
        )
        return await self._client._execute(
            "user_offers", params=params, response_type=m.Page[m.Offer]
        )

    def iter_offers(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[OffersParams],
    ) -> AsyncIterator[m.Offer]:
        return self._iterate(self.list, dict(kwargs), max_items=max_items, max_pages=max_pages)

    async def list_closed(
        self,
        *,
        limit: int = 100,
        order_dir: m.OrderDir = "desc",
        created_from: datetime | int | None = None,
        created_to: datetime | int | None = None,
        closed_from: datetime | int | None = None,
        closed_to: datetime | int | None = None,
        finalization_from: datetime | int | None = None,
        finalization_to: datetime | int | None = None,
        statuses: Sequence[m.TradeStatus] | None = None,
        cursor: str | None = None,
    ) -> m.Page[m.ClosedOfferTrade]:
        params = closed(
            "Offer",
            limit,
            order_dir,
            created_from,
            created_to,
            closed_from,
            closed_to,
            finalization_from,
            finalization_to,
            statuses,
            cursor,
        )
        return await self._client._execute(
            "closed_offers", params=params, response_type=m.Page[m.ClosedOfferTrade]
        )

    def iter_closed(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[ClosedParams],
    ) -> AsyncIterator[m.ClosedOfferTrade]:
        return self._iterate(
            self.list_closed, dict(kwargs), max_items=max_items, max_pages=max_pages
        )

    async def batch_create(self, *, requests: Sequence[m.CreateOffer]) -> m.OfferBatchResult:
        body = {"requests": [x.to_api_dict() for x in payloads(requests, m.CreateOffer)]}
        return await self._client._execute(
            "batch_create", body=body, response_type=m.OfferBatchResult
        )

    async def batch_update(self, *, requests: Sequence[m.UpdateOffer]) -> m.OfferBatchResult:
        body = {"requests": [x.to_api_dict() for x in payloads(requests, m.UpdateOffer)]}
        return await self._client._execute(
            "batch_update", body=body, response_type=m.OfferBatchResult
        )

    async def batch_delete(self, *, offer_ids: Sequence[str]) -> m.OfferBatchResult:
        body = {"requests": [{"offerId": x} for x in identifiers(offer_ids, name="offer_ids")]}
        return await self._client._execute(
            "batch_delete", body=body, response_type=m.OfferBatchResult
        )

    async def create(self, *, asset_id: str, price: m.Money | None = None) -> m.OfferReference:
        result = await self.batch_create(requests=[m.CreateOffer(asset_id=asset_id, price=price)])
        result.raise_for_errors()
        if len(result.successful) != 1:
            raise ResponseValidationError("Single-offer operation returned no unique result")
        return result.successful[0]

    async def update(self, *, offer_id: str, price: m.Money) -> m.OfferReference:
        result = await self.batch_update(requests=[m.UpdateOffer(offer_id=offer_id, price=price)])
        result.raise_for_errors()
        if len(result.successful) != 1:
            raise ResponseValidationError("Single-offer operation returned no unique result")
        return result.successful[0]

    async def delete(self, *, offer_id: str) -> m.OfferBatchResult:
        result = await self.batch_delete(offer_ids=[offer_id])
        result.raise_for_errors()
        return result


class Targets(AsyncResource):
    async def list(
        self,
        *,
        game: m.Game,
        title: str | None = None,
        filters: TargetFilters | None = None,
        raw_tree_filters: str | None = None,
        price_from: m.Money | None = None,
        price_to: m.Money | None = None,
        order_by: Literal["price", "title", "createdAt"] | None = None,
        order_dir: m.OrderDir | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> m.Page[m.Target]:
        params = listing(
            "user_targets",
            game,
            title,
            filters,
            raw_tree_filters,
            order_by,
            order_dir,
            limit,
            cursor,
        )
        params.update(price_range(price_from, price_to))
        return await self._client._execute(
            "user_targets", params=params, response_type=m.Page[m.Target]
        )

    def iter_targets(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[TargetsParams],
    ) -> AsyncIterator[m.Target]:
        return self._iterate(self.list, dict(kwargs), max_items=max_items, max_pages=max_pages)

    async def list_closed(
        self,
        *,
        limit: int = 100,
        order_dir: m.OrderDir = "desc",
        created_from: datetime | int | None = None,
        created_to: datetime | int | None = None,
        closed_from: datetime | int | None = None,
        closed_to: datetime | int | None = None,
        finalization_from: datetime | int | None = None,
        finalization_to: datetime | int | None = None,
        statuses: Sequence[m.TradeStatus] | None = None,
        cursor: str | None = None,
    ) -> m.Page[m.ClosedTargetTrade]:
        params = closed(
            "Target",
            limit,
            order_dir,
            created_from,
            created_to,
            closed_from,
            closed_to,
            finalization_from,
            finalization_to,
            statuses,
            cursor,
        )
        return await self._client._execute(
            "closed_targets", params=params, response_type=m.Page[m.ClosedTargetTrade]
        )

    def iter_closed(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[ClosedParams],
    ) -> AsyncIterator[m.ClosedTargetTrade]:
        return self._iterate(
            self.list_closed, dict(kwargs), max_items=max_items, max_pages=max_pages
        )

    async def create(
        self, *, game: m.Game, targets: Sequence[m.CreateTarget]
    ) -> m.TargetCreateBatchResult:
        body = {
            "GameID": game_value(game).value,
            "Targets": [x.to_api_dict() for x in payloads(targets, m.CreateTarget, maximum=100)],
        }
        return await self._client._execute(
            "create_targets", body=body, response_type=m.TargetCreateBatchResult
        )

    async def delete(self, *, target_ids: Sequence[str]) -> m.TargetDeleteBatchResult:
        body = {"Targets": [{"TargetID": x} for x in identifiers(target_ids, name="target_ids")]}
        return await self._client._execute(
            "delete_targets", body=body, response_type=m.TargetDeleteBatchResult
        )


class Market(AsyncResource):
    async def list_offers(
        self,
        *,
        game: m.Game,
        title: str | None = None,
        filters: OfferFilters | None = None,
        raw_tree_filters: str | None = None,
        price_from: m.Money | None = None,
        price_to: m.Money | None = None,
        order_by: Literal["price", "title", "float", "createdAt", "discount"] | None = None,
        order_dir: m.OrderDir | None = None,
        limit: int = 100,
        cursor: str | None = None,
        with_images: bool | None = None,
        offer_type: Literal["dmarket", "p2p", "all"] | None = None,
        online_sellers_only: bool | None = None,
    ) -> m.Page[m.Offer]:
        params = listing(
            "market_offers",
            game,
            title,
            filters,
            raw_tree_filters,
            order_by,
            order_dir,
            limit,
            cursor,
        )
        params.update(price_range(price_from, price_to))
        params.update(
            withImages=with_images, offerType=offer_type, onlineSellersOnly=online_sellers_only
        )
        return await self._client._execute(
            "market_offers", params=params, response_type=m.Page[m.Offer]
        )

    def iter_offers(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[MarketParams],
    ) -> AsyncIterator[m.Offer]:
        return self._iterate(
            self.list_offers, dict(kwargs), max_items=max_items, max_pages=max_pages
        )

    async def get_targets_by_title(self, *, game: m.Game, title: str) -> m.TargetDepth:
        """Exact title in path; pass a decoded title, never pre-encode it."""
        return await self._client._execute(
            "target_depth",
            path_params={"game_id": game_value(game).value, "title": title},
            response_type=m.TargetDepth,
        )

    async def get_aggregated_prices(
        self,
        *,
        game: m.Game,
        titles: Sequence[str],
        include_p2p: bool | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> m.Page[m.AggregatedPrice]:
        positive_int(limit, "limit")
        selected = sequence(titles, name="titles")
        if any(not isinstance(x, str) or not x for x in selected):
            raise RequestValidationError("titles must contain nonempty strings")
        filters: dict[str, Any] = {"game": game_value(game).value, "titles": selected}
        if include_p2p is not None:
            if not isinstance(include_p2p, bool):
                raise RequestValidationError("include_p2p must be boolean")
            filters["includeP2p"] = include_p2p
        body = {"filter": filters, "limit": str(limit)}
        if cursor is not None:
            body["cursor"] = cursor
        return await self._client._execute(
            "aggregated_prices", body=body, response_type=m.Page[m.AggregatedPrice]
        )

    def iter_aggregated_prices(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[AggregatedParams],
    ) -> AsyncIterator[m.AggregatedPrice]:
        return self._iterate(
            self.get_aggregated_prices, dict(kwargs), max_items=max_items, max_pages=max_pages
        )

    async def buy(self, *, offers: Sequence[m.BuyOffer]) -> m.PurchaseResult:
        """Buy at explicit expected prices. TxPending is not completion. No write retries.

        The contract accepts p2p but other documentation contradicts API support.
        Use dmarket offers unless P2P support has been confirmed for your account.
        """
        return await self._client._execute(
            "buy",
            body={"offers": [x.to_api_dict() for x in payloads(offers, m.BuyOffer)]},
            response_type=m.PurchaseResult,
        )


class Deposits(AsyncResource):
    async def create(self, *, asset_ids: Sequence[str]) -> m.DepositCreated:
        """Register a deposit using composite inGameAssetId, not UUID or Steam assetId."""
        values = identifiers(asset_ids, name="asset_ids")
        if any(not re.fullmatch("\\d+:\\d+:\\d+:\\d+", x) for x in values):
            raise RequestValidationError(
                "Deposit IDs must have instanceId:classId:assetId:appId format"
            )
        return await self._client._execute(
            "deposit", body={"AssetID": values}, response_type=m.DepositCreated
        )

    async def get_status(self, deposit_id: str) -> m.DepositStatus:
        return await self._client._execute(
            "deposit_status", path_params={"DepositID": deposit_id}, response_type=m.DepositStatus
        )

    async def list_blocked_titles(
        self, *, game: m.Game, limit: int = 1000, cursor: str | None = None
    ) -> m.BlockedTitlesPage:
        return await self._client._execute(
            "blocked_titles",
            params={"gameId": game_value(game).value, "limit": limit, "cursor": cursor},
            response_type=m.BlockedTitlesPage,
        )

    def iter_blocked_titles(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[BlockedParams],
    ) -> AsyncIterator[m.BlockedTitle]:
        return self._iterate(
            self.list_blocked_titles, dict(kwargs), max_items=max_items, max_pages=max_pages
        )

    async def wait(
        self, deposit_id: str, *, timeout: float = 120.0, poll_interval: float = 2.0
    ) -> m.DepositStatus:
        """Poll deposit status only; never resubmit the deposit."""
        polling_args(timeout, poll_interval)
        deadline = time.monotonic() + timeout
        last: m.DepositStatus | None = None
        while time.monotonic() < deadline:
            try:
                last = await self._client._execute(
                    "deposit_status",
                    path_params={"DepositID": deposit_id},
                    response_type=m.DepositStatus,
                    deadline=deadline,
                )
            except RequestTimeoutError:
                raise PollingTimeoutError(deposit_id, last) from None
            if last.status == "TransferStatusSuccess":
                return last
            if last.status in {"TransferStatusError", "TransferStatusFailedToCreate"}:
                raise DepositFailedError(last)
            await asyncio.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
        raise PollingTimeoutError(deposit_id, last)


class Withdrawals(AsyncResource):
    async def create(
        self, *, assets: Sequence[m.WithdrawAsset], request_id: str | None = None
    ) -> m.WithdrawalCreated:
        """Request item withdrawal. request_id is retained, not assumed idempotent."""
        rid = request_id if request_id is not None else str(uuid4())
        if not isinstance(rid, str) or not rid:
            raise RequestValidationError("request_id must be a nonempty string")
        return await self._client._execute(
            "withdraw",
            body={
                "assets": [x.to_api_dict() for x in payloads(assets, m.WithdrawAsset)],
                "requestId": rid,
            },
            response_type=m.WithdrawalCreated,
        )


class Fees(AsyncResource):
    def iter_reduced(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[FeesParams],
    ) -> AsyncIterator[m.ReducedFee]:
        params = {"limit": 10, **kwargs}
        return self._iterate(
            self._list_page, params, max_items=max_items, max_pages=max_pages, offset=True
        )

    async def _list_page(self, **kwargs: Unpack[FeesParams]) -> m.Page[m.ReducedFee]:
        result = await self.list_reduced(**kwargs)
        return m.Page[m.ReducedFee](items=result.reduced_fees, metadata=result.metadata)

    async def list_reduced(
        self, *, game: m.Game, offer_type: m.OfferType = "dmarket", limit: int = 10, offset: int = 0
    ) -> m.ReducedFees:
        positive_int(limit, "limit")
        positive_int(offset, "offset", zero=True)
        if offer_type not in {"dmarket", "p2p"}:
            raise RequestValidationError("offer_type must be dmarket or p2p")
        return await self._client._execute(
            "fees",
            params={
                "gameId": game_value(game).value,
                "offerType": offer_type,
                "limit": limit,
                "offset": offset,
            },
            response_type=m.ReducedFees,
        )


class Sales(AsyncResource):
    async def list_recent(
        self,
        *,
        game: m.Game,
        title: str,
        filters: str | None = None,
        tx_operation_types: Sequence[Literal["Offer", "Target"]] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> m.SalesPage:
        positive_int(limit, "limit")
        positive_int(offset, "offset", zero=True)
        params = {
            "gameId": game_value(game).value,
            "title": title,
            "filters": filters,
            "limit": str(limit),
            "offset": str(offset),
            "txOperationType": list(tx_operation_types) if tx_operation_types is not None else None,
        }
        if tx_operation_types is not None:
            sequence(tx_operation_types, name="tx_operation_types")
        return await self._client._execute("last_sales", params=params, response_type=m.SalesPage)

    def iter_recent(
        self,
        *,
        max_items: int | None = None,
        max_pages: int | None = None,
        **kwargs: Unpack[SalesParams],
    ) -> AsyncIterator[m.Sale]:
        return self._iterate(
            self.list_recent, dict(kwargs), max_items=max_items, max_pages=max_pages, offset=True
        )
