"""Public domain types and validated request objects."""

import re
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, localcontext
from enum import StrEnum
from typing import Any, Literal, NewType
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StrictInt,
    StrictStr,
    field_validator,
)

from ._internal import wire
from ._internal.serialization import decimal_value
from .exceptions import BatchOperationError, RequestValidationError
from .metadata import ResponseMetadata

AssetId = NewType("AssetId", str)
OfferId = NewType("OfferId", str)
TargetId = NewType("TargetId", str)
InGameAssetId = NewType("InGameAssetId", str)
OrderDir = Literal["asc", "desc"]
TradeStatus = Literal["successful", "reverted", "trade_protected"]
OfferType = Literal["dmarket", "p2p"]


class Game(StrEnum):
    CS2 = "a8db"
    DOTA2 = "9a92"
    TF2 = "tf2"
    RUST = "rust"

    @property
    def sync_id(self) -> str:
        return {Game.CS2: "CSGO", Game.DOTA2: "Dota2", Game.TF2: "TF2", Game.RUST: "Rust"}[self]


class Currency(StrEnum):
    USD = "USD"
    DMC = "DMC"


class SyncGame(StrEnum):
    """Full inventory-sync enum; Game is used by the four-game trading endpoints."""

    UNKNOWN = "UnknownGame"
    CS2 = "CSGO"
    DOTA2 = "Dota2"
    TF2 = "TF2"
    LIFE_BEYOND = "LifeBeyond"
    RUST = "Rust"


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Money(InputModel):
    """Amount in major currency units. No binary floats or silent USD rounding."""

    amount: Decimal
    currency: Currency = Currency.USD

    @field_validator("amount", mode="before")
    @classmethod
    def exact_amount(cls, value: object) -> Decimal:
        return decimal_value(value)

    @field_validator("amount")
    @classmethod
    def finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Amount must be finite")
        return value

    @classmethod
    def usd(cls, amount: str | int | Decimal) -> Money:
        result = cls(amount=decimal_value(amount), currency=Currency.USD)
        result.to_minor_units()
        return result

    @classmethod
    def from_minor_units(
        cls, amount: int | str, currency: Currency = Currency.USD, *, scale: int | None = None
    ) -> Money:
        factor = scale if scale is not None else (100 if currency == Currency.USD else None)
        if (
            not isinstance(factor, int)
            or isinstance(factor, bool)
            or not re.fullmatch(r"10*", str(factor))
        ):
            raise RequestValidationError(
                "Currency conversion requires an explicit power-of-ten scale"
            )
        if isinstance(amount, str) and not re.fullmatch(r"-?\d+", amount):
            raise RequestValidationError("Minor units must be an integer string")
        value = decimal_value(amount)
        if value != value.to_integral_value():
            raise RequestValidationError("Minor units must be integral")
        with localcontext() as ctx:
            ctx.prec = max(50, len(value.as_tuple().digits) + 20)
            return cls(amount=value / factor, currency=currency)

    def to_minor_units(self, *, scale: int | None = None) -> int:
        factor = scale if scale is not None else (100 if self.currency == Currency.USD else None)
        if (
            not isinstance(factor, int)
            or isinstance(factor, bool)
            or not re.fullmatch(r"10*", str(factor))
        ):
            raise RequestValidationError(
                "Currency conversion requires an explicit power-of-ten scale"
            )
        with localcontext() as ctx:
            ctx.prec = max(50, len(self.amount.as_tuple().digits) + 20)
            units = self.amount * factor
            if units != units.to_integral_value():
                raise RequestValidationError("Amount is not an exact number of minor units")
            if not -(2**63) <= units <= 2**63 - 1:
                raise RequestValidationError("Amount exceeds signed int64 minor units")
            return int(units)


class MinorMoney(InputModel):
    """Exact coins when the upstream currency scale is unspecified (DMC dimoshi)."""

    minor_units: StrictInt
    currency: Currency

    def to_money(self, *, scale: int) -> Money:
        return Money.from_minor_units(self.minor_units, self.currency, scale=scale)


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)
    metadata: ResponseMetadata | None = Field(default=None, exclude=True, repr=False)
    _api_data: dict[str, Any] = PrivateAttr(default_factory=dict)

    def to_api_dict(self) -> dict[str, Any]:
        """Return a detached copy of the complete original server object."""
        return deepcopy(self._api_data)


class Page[T](ResponseModel):
    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = None
    total: int | None = None


class Balance(ResponseModel):
    usd: Money
    usd_available_to_withdraw: Money
    dmc: MinorMoney
    dmc_available_to_withdraw: MinorMoney


OfferReference = wire.Marketplacev2Offer
UserProfile = wire.RepresentationUserAccountResponse
AssetAttributes = wire.AssetAttributes
TargetAttributes = wire.Marketplacev2TargetAttributes
DepositCreated = wire.MarketplaceDepositAssetsResponse
DepositStatus = wire.MarketplaceGetDepositStatusResponse
InventorySyncResult = wire.MarketplaceUserInventorySyncResponse
PurchaseResult = wire.EntityOfferBuyResponse
ReducedFees = wire.EntityListFeeResponse
ReducedFee = wire.EntityListPersonalFee
BlockedTitle = wire.Marketplacev2DepositBlockedTitle


class Offer(ResponseModel):
    offer_id: str | None = None
    attributes: AssetAttributes | None = None
    price: Money | None = None
    created_at: datetime | None = None
    locked: bool | None = None
    discount_percent: Decimal | None = None
    offer_type: str | None = None


class InventoryItem(ResponseModel):
    attributes: AssetAttributes | None = None
    suggested_price: Money | None = None
    offer_recommended_price: Money | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    in_market: bool | None = None


class Target(ResponseModel):
    target_id: str | None = None
    title: str | None = None
    amount: int | None = None
    status: str | None = None
    price: Money | None = None
    attributes: TargetAttributes | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ClosedTrade(ResponseModel):
    offer_id: str | None = None
    target_id: str | None = None
    asset_id: str | None = None
    price: Money | None = None
    currency_code: str | None = None
    amount: int | None = None
    title: str | None = None
    status: str | None = None
    finalization_time: datetime | None = None


class ClosedOfferTrade(ClosedTrade):
    fee: wire.TradeFeeData | None = None
    offer_created_at: datetime | None = None
    offer_closed_at: datetime | None = None


class ClosedTargetTrade(ClosedTrade):
    closed_at: datetime | None = None


class TargetDepthOrder(ResponseModel):
    amount: int | None = None
    price: Money | None = None
    title: str | None = None
    attributes: wire.GetTargetsByTitleResponseOrderAttributes | None = None


class TargetDepth(ResponseModel):
    orders: list[TargetDepthOrder] = Field(default_factory=list)


class AggregatedPrice(ResponseModel):
    title: str | None = None
    order_best_price: Money | MinorMoney | None = None
    order_count: int | None = None
    offer_best_price: Money | MinorMoney | None = None
    offer_count: int | None = None


class Sale(ResponseModel):
    price: Money | None = None
    date: datetime | None = None
    tx_operation_type: str | None = None
    offer_attributes: dict[str, Any] | None = None
    order_attributes: dict[str, Any] | None = None


class SalesPage(Page[Sale]):
    pass


class BlockedTitlesPage(Page[BlockedTitle]):
    game_id: str | None = None
    updated_at: datetime | None = None


class BatchFailure(ResponseModel):
    asset_id: str | None = None
    offer_id: str | None = None
    target_id: str | None = None
    code: str | int | None = None
    message: str | None = None
    request: dict[str, Any] | None = None


class BatchResult[T](ResponseModel):
    successful: list[T] = Field(default_factory=list)
    failed: list[BatchFailure] = Field(default_factory=list)

    def raise_for_errors(self) -> None:
        if self.failed:
            raise BatchOperationError(self)


class OfferBatchResult(BatchResult[wire.Marketplacev2Offer]):
    pass


class TargetCreateBatchResult(BatchResult[wire.MarketplaceCreateTargetResponse]):
    pass


class TargetDeleteBatchResult(BatchResult[wire.MarketplaceDeleteTargetResponse]):
    pass


class WithdrawalCreated(ResponseModel):
    transfer_id: str
    request_id: str


def positive_usd(price: Money) -> Money:
    if price.currency != Currency.USD or price.amount <= 0:
        raise ValueError("Price must be a positive USD amount")
    price.to_minor_units()
    return price


class TargetAttrs(InputModel):
    paint_seed: StrictInt | None = Field(default=None, ge=0)
    phase: (
        Literal[
            "",
            "phase-1",
            "phase-2",
            "phase-3",
            "phase-4",
            "ruby",
            "emerald",
            "sapphire",
            "black-pearl",
        ]
        | None
    ) = None
    float_part_value: StrictStr | None = None

    @field_validator("float_part_value")
    @classmethod
    def float_bucket(cls, value: str | None) -> str | None:
        allowed = {""} | {
            f"{prefix}-{i}"
            for prefix, limit in [("FN", 7), ("MW", 5), ("FT", 5), ("WW", 5), ("BS", 5)]
            for i in range(limit)
        }
        if value is not None and value not in allowed:
            raise ValueError("Invalid target float bucket")
        return value

    def to_api_dict(self) -> dict[str, Any]:
        names = {"paint_seed": "paintSeed", "phase": "phase", "float_part_value": "floatPartValue"}
        return {names[k]: v for k, v in self.model_dump(exclude_unset=True).items()}


class CreateTarget(InputModel):
    title: StrictStr = Field(min_length=1)
    price: Money
    amount: StrictInt = Field(default=1, ge=1, le=100)
    attrs: TargetAttrs | None = None

    @field_validator("price")
    @classmethod
    def valid_price(cls, value: Money) -> Money:
        return positive_usd(value)

    def to_api_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "Title": self.title,
            "Price": {"Currency": "USD", "Amount": self.price.amount},
            "Amount": str(self.amount),
        }
        if self.attrs is not None:
            result["Attrs"] = self.attrs.to_api_dict()
        return result


class CreateOffer(InputModel):
    asset_id: StrictStr
    price: Money | None = None

    @field_validator("asset_id")
    @classmethod
    def asset_uuid(cls, value: str) -> str:
        return str(UUID(value))

    @field_validator("price")
    @classmethod
    def valid_price(cls, value: Money | None) -> Money | None:
        return positive_usd(value) if value is not None else None

    def to_api_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"assetId": self.asset_id}
        if self.price is not None:
            result["priceCents"] = str(self.price.to_minor_units())
        return result


class UpdateOffer(InputModel):
    offer_id: StrictStr = Field(min_length=1)
    price: Money

    @field_validator("price")
    @classmethod
    def valid_price(cls, value: Money) -> Money:
        return positive_usd(value)

    def to_api_dict(self) -> dict[str, Any]:
        return {"offerId": self.offer_id, "priceCents": str(self.price.to_minor_units())}


class BuyOffer(InputModel):
    offer_id: StrictStr = Field(min_length=1)
    price: Money | MinorMoney
    offer_type: OfferType = "dmarket"

    @field_validator("price")
    @classmethod
    def valid_price(cls, value: Money | MinorMoney) -> Money | MinorMoney:
        units = value.to_minor_units() if isinstance(value, Money) else value.minor_units
        if units <= 0:
            raise ValueError("Purchase price must be positive")
        return value

    def to_api_dict(self) -> dict[str, Any]:
        units = (
            self.price.to_minor_units() if isinstance(self.price, Money) else self.price.minor_units
        )
        return {
            "offerId": self.offer_id,
            "type": self.offer_type,
            "price": {"currency": self.price.currency.value, "amount": str(units)},
        }


class WithdrawAsset(InputModel):
    id: StrictStr = Field(min_length=1)
    class_id: StrictStr = Field(min_length=1)
    game: Game

    def to_api_dict(self) -> dict[str, str]:
        return {"id": self.id, "classId": self.class_id, "gameId": self.game.value}
