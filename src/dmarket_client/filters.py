"""Typed treeFilters builders. raw_tree_filters remains an explicit escape hatch."""

from typing import Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from .exceptions import RequestValidationError
from .models import Game, InputModel, TargetAttrs

Exterior = Literal[
    "factory new",
    "minimal wear",
    "field-tested",
    "well-worn",
    "battle-scarred",
    "not painted",
    "battle scarred",
]
Phase = Literal[
    "phase-1", "phase-2", "phase-3", "phase-4", "ruby", "sapphire", "emerald", "black-pearl"
]


class TreeFilters(InputModel):
    category_path: StrictStr | None = None

    @field_validator("float_part", check_fields=False)
    @classmethod
    def valid_float_bucket(cls, value: str | None) -> str | None:
        return TargetAttrs.float_bucket(value)

    def serialize(self, *, scope: str, game: Game) -> str:
        aliases = {
            "category_path": "categoryPath",
            "in_market": "inMarket",
            "paint_seed": "paintSeed",
            "float_part": "floatPart",
            "charm_name": "charmName",
            "charm_exists": "charmExists",
            "is_proskin": "isProskin",
            "fade_percent_from": "fadePercentFrom",
            "fade_percent_to": "fadePercentTo",
            "is_craftable": "isCraftable",
            "price_cents": "priceCents",
            "trade_lock_from": "tradeLockFrom",
            "trade_lock_to": "tradeLockTo",
            "is_advanced": "isAdvanced",
            "not_exterior": "not_exterior",
        }
        fields = self.model_dump(exclude_none=True)
        cs2_only = {
            "paint_seed",
            "float_part",
            "phase",
            "category",
            "charm_name",
            "charm_exists",
            "is_proskin",
            "fade_percent_from",
            "fade_percent_to",
            "sticker",
            "is_advanced",
        }
        for name in fields:
            if name in cs2_only and game != Game.CS2:
                raise RequestValidationError(f"{name} is a CS2 filter")
            if name in {"exterior", "not_exterior", "collection"} and game not in {
                Game.CS2,
                Game.TF2,
            }:
                raise RequestValidationError(f"{name} applies to CS2 or TF2")
            if name == "is_craftable" and game != Game.TF2:
                raise RequestValidationError("is_craftable is a TF2 filter")
            if name == "hero" and game != Game.DOTA2:
                raise RequestValidationError("hero is a Dota 2 filter")
            if name == "price_cents" and scope != "user_offers":
                raise RequestValidationError("price_cents is only supported by user offers filters")
            if name in {"exterior", "not_exterior"}:
                values = fields[name] if isinstance(fields[name], tuple) else (fields[name],)
                if game == Game.CS2 and "battle scarred" in values:
                    raise RequestValidationError("CS2 uses the exterior spelling battle-scarred")
                if game == Game.TF2 and "not painted" in values:
                    raise RequestValidationError("not painted is a CS2 exterior filter")
            if name == "category" and fields[name] not in {
                "stattrak_tm",
                "souvenir",
                "normal",
                "★",
            }:
                raise RequestValidationError("Unsupported CS2 category filter")
        pairs = []
        for name, value in fields.items():
            key = aliases.get(name, name)
            values = value if isinstance(value, tuple) else (value,)
            multi = isinstance(value, tuple)
            for item in values:
                text = str(item).lower() if isinstance(item, bool) else str(item)
                if any(c in text for c in ",="):
                    raise RequestValidationError(
                        "Typed filter values cannot contain ',' or '='; use raw_tree_filters"
                    )
                pairs.append(f"{key}{'[]' if multi else ''}={text}")
        return ",".join(pairs)


class InventoryFilters(TreeFilters):
    tradable: StrictBool | None = None
    in_market: StrictBool | None = None
    type: StrictStr | None = None
    exterior: Exterior | tuple[Exterior, ...] | None = None
    not_exterior: Exterior | None = None
    paint_seed: StrictInt | None = Field(default=None, ge=0)
    float_part: StrictStr | None = None
    phase: Phase | None = None
    category: StrictStr | None = None
    collection: StrictStr | None = None
    charm_name: StrictStr | None = None
    charm_exists: StrictBool | None = None
    is_proskin: StrictBool | None = None
    fade_percent_from: float | None = Field(default=None, ge=0, le=100)
    fade_percent_to: float | None = Field(default=None, ge=0, le=100)
    is_craftable: StrictBool | None = None
    hero: StrictStr | None = None

    @model_validator(mode="after")
    def valid_ranges(self) -> InventoryFilters:
        if (
            self.fade_percent_from is not None
            and self.fade_percent_to is not None
            and self.fade_percent_from > self.fade_percent_to
        ):
            raise ValueError("fade_percent_from cannot exceed fade_percent_to")
        return self


class OfferFilters(TreeFilters):
    type: StrictStr | None = None
    price_cents: StrictInt | None = Field(default=None, ge=0)
    trade_lock_from: StrictInt | None = Field(default=None, ge=0)
    trade_lock_to: StrictInt | None = Field(default=None, ge=0)
    exterior: Exterior | tuple[Exterior, ...] | None = None
    not_exterior: Exterior | None = None
    paint_seed: StrictInt | None = Field(default=None, ge=0)
    float_part: StrictStr | None = None
    phase: Phase | None = None
    category: StrictStr | None = None
    collection: StrictStr | None = None
    charm_name: StrictStr | None = None
    charm_exists: StrictBool | None = None
    sticker: tuple[StrictStr, ...] | None = None
    is_proskin: StrictBool | None = None
    fade_percent_from: float | None = Field(default=None, ge=0, le=100)
    fade_percent_to: float | None = Field(default=None, ge=0, le=100)
    is_craftable: StrictBool | None = None
    hero: StrictStr | None = None

    @model_validator(mode="after")
    def valid_ranges(self) -> OfferFilters:
        if (
            self.trade_lock_from is not None
            and self.trade_lock_to is not None
            and self.trade_lock_from >= self.trade_lock_to
        ):
            raise ValueError("trade_lock_to must exceed trade_lock_from (exclusive upper bound)")
        if (
            self.fade_percent_from is not None
            and self.fade_percent_to is not None
            and self.fade_percent_from > self.fade_percent_to
        ):
            raise ValueError("fade_percent_from cannot exceed fade_percent_to")
        return self


class TargetFilters(TreeFilters):
    amount: StrictInt | None = Field(default=None, ge=1)
    status: StrictStr | None = None
    category: StrictStr | None = None
    exterior: Exterior | tuple[Exterior, ...] | None = None
    float_part: StrictStr | None = None
    is_advanced: StrictBool | None = None
    paint_seed: StrictInt | None = Field(default=None, ge=0)
    phase: Phase | None = None


def tree_filter(
    filters: TreeFilters | None,
    raw: str | None,
    *,
    game: Game,
    scope: str,
) -> str | None:
    if filters is not None and raw is not None:
        raise RequestValidationError("Pass filters or raw_tree_filters, not both")
    expected: dict[str, type[TreeFilters]] = {
        "inventory": InventoryFilters,
        "user_offers": OfferFilters,
        "market_offers": OfferFilters,
        "user_targets": TargetFilters,
    }
    if filters is not None and not isinstance(filters, expected[scope]):
        raise RequestValidationError("Filter type does not match the resource")
    return filters.serialize(scope=scope, game=game) if filters is not None else raw
