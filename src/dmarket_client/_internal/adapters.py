"""Explicit per-field units and endpoint response adapters."""

from datetime import UTC, datetime
from typing import Any

from .. import models as m
from .wire_base import WireModel


def snapshot[T: m.ResponseModel](cls: type[T], raw: dict[str, Any], **fields: Any) -> T:
    result = cls(**fields)
    result._api_data = raw
    return result


def integer(value: Any) -> int | None:
    return int(value) if value is not None else None


def timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and ("T" in value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp lacks a timezone")
        return parsed
    return datetime.fromtimestamp(int(value), tz=UTC)


def cents(value: Any) -> m.Money | None:
    return m.Money.from_minor_units(value) if value is not None else None


def major(value: dict[str, Any] | None, *, upper: bool = False) -> m.Money | None:
    if value is None:
        return None
    a, c = ("Amount", "Currency") if upper else ("amount", "currency")
    if value.get(a) is None or value.get(c) is None:
        raise ValueError("Monetary object lacks amount or currency")
    return m.Money(amount=value[a], currency=m.Currency(value[c]))


def minor(value: dict[str, Any] | None) -> m.Money | m.MinorMoney | None:
    if value is None:
        return None
    currency = m.Currency(value["Currency"])
    if currency == m.Currency.USD:
        return m.Money.from_minor_units(value["Amount"])
    return m.MinorMoney(currency=currency, minor_units=int(value["Amount"]))


def offer(raw: dict[str, Any]) -> m.Offer:
    return snapshot(
        m.Offer,
        raw,
        offer_id=raw.get("offerId"),
        attributes=raw.get("attributes"),
        price=cents(raw.get("priceCents")),
        created_at=timestamp(raw.get("createdAt")),
        locked=raw.get("locked"),
        discount_percent=raw.get("discountPercent"),
        offer_type=raw.get("offerType"),
    )


def inventory_item(raw: dict[str, Any]) -> m.InventoryItem:
    return snapshot(
        m.InventoryItem,
        raw,
        attributes=raw.get("attributes"),
        suggested_price=major(raw.get("suggestedPrice")),
        offer_recommended_price=major(raw.get("offerRecommendedPrice")),
        created_at=timestamp(raw.get("createdAt")),
        updated_at=timestamp(raw.get("updatedAt")),
        in_market=raw.get("inMarket"),
    )


def target(raw: dict[str, Any]) -> m.Target:
    return snapshot(
        m.Target,
        raw,
        target_id=raw.get("targetId"),
        title=raw.get("title"),
        amount=integer(raw.get("amount")),
        status=raw.get("status"),
        price=cents(raw.get("priceCents")),
        attributes=raw.get("attributes"),
        created_at=timestamp(raw.get("createdAt")),
        updated_at=timestamp(raw.get("updatedAt")),
    )


def closed_trade(raw: dict[str, Any], *, offers: bool) -> m.ClosedTrade:
    fields: dict[str, Any] = {
        "offer_id": raw.get("OfferID"),
        "target_id": raw.get("TargetID"),
        "asset_id": raw.get("AssetID"),
        "price": major(raw.get("Price"), upper=True),
        "currency_code": raw.get("CurrencyCode"),
        "amount": integer(raw.get("Amount")),
        "title": raw.get("Title"),
        "status": raw.get("Status"),
        "finalization_time": timestamp(raw.get("FinalizationTime")),
    }
    if offers:
        return snapshot(
            m.ClosedOfferTrade,
            raw,
            **fields,
            fee=raw.get("Fee"),
            offer_created_at=timestamp(raw.get("OfferCreatedAt")),
            offer_closed_at=timestamp(raw.get("OfferClosedAt")),
        )
    return snapshot(m.ClosedTargetTrade, raw, **fields, closed_at=timestamp(raw.get("ClosedAt")))


def adapt(operation: str, raw: dict[str, Any], validated: WireModel) -> m.ResponseModel | WireModel:
    if operation == "balance":
        return snapshot(
            m.Balance,
            raw,
            usd=cents(raw["usd"]),
            usd_available_to_withdraw=cents(raw["usdAvailableToWithdraw"]),
            dmc=m.MinorMoney(currency=m.Currency.DMC, minor_units=int(raw["dmc"])),
            dmc_available_to_withdraw=m.MinorMoney(
                currency=m.Currency.DMC, minor_units=int(raw["dmcAvailableToWithdraw"])
            ),
        )
    if operation in {"inventory", "user_offers", "market_offers", "user_targets"}:
        convert = {
            "inventory": inventory_item,
            "user_offers": offer,
            "market_offers": offer,
            "user_targets": target,
        }[operation]
        return snapshot(
            m.Page[Any],
            raw,
            items=[convert(x) for x in raw.get("items", [])],
            next_cursor=raw.get("cursor") or None,
            total=integer(raw.get("total")),
        )
    if operation in {"closed_offers", "closed_targets"}:
        return snapshot(
            m.Page[Any],
            raw,
            items=[
                closed_trade(x, offers=operation == "closed_offers") for x in raw.get("Trades", [])
            ],
            next_cursor=raw.get("Cursor") or None,
            total=integer(raw.get("Total")),
        )
    if operation == "blocked_titles":
        return snapshot(
            m.BlockedTitlesPage,
            raw,
            items=raw.get("titles", []),
            next_cursor=raw.get("cursor") or None,
            total=integer(raw.get("total")),
            game_id=raw.get("gameId"),
            updated_at=timestamp(raw.get("updatedAt")),
        )
    if operation == "target_depth":
        return snapshot(
            m.TargetDepth,
            raw,
            orders=[
                snapshot(
                    m.TargetDepthOrder,
                    x,
                    amount=integer(x.get("amount")),
                    price=cents(x.get("price")),
                    title=x.get("title"),
                    attributes=x.get("attributes"),
                )
                for x in raw.get("orders", [])
            ],
        )
    if operation == "aggregated_prices":
        return snapshot(
            m.Page[m.AggregatedPrice],
            raw,
            items=[
                snapshot(
                    m.AggregatedPrice,
                    x,
                    title=x.get("title"),
                    order_best_price=minor(x.get("orderBestPrice")),
                    order_count=integer(x.get("orderCount")),
                    offer_best_price=minor(x.get("offerBestPrice")),
                    offer_count=integer(x.get("offerCount")),
                )
                for x in raw.get("aggregatedPrices", [])
            ],
            next_cursor=raw.get("nextCursor") or None,
        )
    if operation == "last_sales":
        return snapshot(
            m.SalesPage,
            raw,
            items=[
                snapshot(
                    m.Sale,
                    x,
                    price=m.Money.usd(x["price"]) if x.get("price") is not None else None,
                    date=timestamp(x.get("date")),
                    tx_operation_type=x.get("txOperationType"),
                    offer_attributes=x.get("offerAttributes"),
                    order_attributes=x.get("orderAttributes"),
                )
                for x in raw.get("sales", [])
            ],
        )
    if operation.startswith("batch_"):
        return snapshot(
            m.OfferBatchResult,
            raw,
            successful=raw.get("offers", []),
            failed=[
                snapshot(
                    m.BatchFailure,
                    x,
                    asset_id=x.get("assetId"),
                    offer_id=x.get("offerId"),
                    code=x.get("code"),
                    message=x.get("message"),
                )
                for x in raw.get("failed", [])
            ],
        )
    if operation in {"create_targets", "delete_targets"}:
        results = raw.get("Result", [])
        failure = []
        for x in results:
            if x.get("Successful") is True:
                continue
            request = (
                x.get("CreateTarget") if operation == "create_targets" else x.get("DeleteTarget")
            )
            error = x.get("Error") or {}
            failure.append(
                snapshot(
                    m.BatchFailure,
                    x,
                    target_id=x.get("TargetID") or (request or {}).get("TargetID"),
                    code=error.get("Code"),
                    message=error.get("Message"),
                    request=request,
                )
            )
        cls = (
            m.TargetCreateBatchResult
            if operation == "create_targets"
            else m.TargetDeleteBatchResult
        )
        return snapshot(
            cls, raw, successful=[x for x in results if x.get("Successful") is True], failed=failure
        )
    return validated
