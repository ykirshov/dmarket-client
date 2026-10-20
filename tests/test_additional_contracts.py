import asyncio
import time

import httpx
import pytest
from conftest import SPEC, minimal, response_for
from pydantic import BaseModel, ValidationError

from dmarket_client import (
    AsyncDMarketClient,
    ClientConfig,
    Currency,
    DMarketClient,
    Game,
    MinorMoney,
    Money,
    RateLimiter,
    SyncGame,
    TargetFilters,
)
from dmarket_client._internal.serialization import decode_json
from dmarket_client._internal.wire import SCHEMA_MODELS
from dmarket_client.exceptions import RequestTimeoutError


@pytest.mark.parametrize("name", SCHEMA_MODELS)
def test_all_named_contracts_resolve_and_validate_minimal_values(name):
    cls = SCHEMA_MODELS[name]
    value = minimal(SPEC["components"]["schemas"][name])
    if issubclass(cls, BaseModel):
        cls.model_validate(value)
    else:
        cls(value)


@pytest.mark.parametrize(
    "game,field", [(Game.CS2, "cs2"), (Game.DOTA2, "dota2"), (Game.TF2, "tf2"), (Game.RUST, "rust")]
)
def test_all_four_inventory_attribute_types(game, field, keys):
    raw = {"items": [{"attributes": {"gameId": game.value, field: {}}}], "cursor": ""}
    with DMarketClient(
        *keys,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw)),
        rate_limiter=False,
    ) as client:
        item = client.inventory.list_items(game=game).items[0]
        assert getattr(item.attributes, field) is not None


def test_full_sync_enum(keys):
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={})

    with DMarketClient(*keys, transport=httpx.MockTransport(handler), rate_limiter=False) as client:
        client.inventory.sync(game=SyncGame.LIFE_BEYOND)
    assert decode_json(captured[0].content)["GameID"] == "LifeBeyond"


async def test_async_fee_offset_iterator(keys):
    offsets = []

    async def handler(request):
        offsets.append(int(request.url.params["offset"]))
        result = response_for("fees")
        result["reducedFees"] = [
            {
                "title": "item",
                "fraction": "0.01",
                "minPrice": 1,
                "maxPrice": 100,
                "expiresAt": 1800000000,
            }
        ] * (2 if offsets[-1] == 0 else 1)
        return httpx.Response(200, json=result)

    async with AsyncDMarketClient(
        *keys, transport=httpx.MockTransport(handler), rate_limiter=False
    ) as client:
        items = [x async for x in client.fees.iter_reduced(game=Game.CS2, limit=2)]
    assert len(items) == 3
    assert offsets == [0, 2]


def test_dmc_is_exact_and_scale_is_explicit():
    raw = MinorMoney(minor_units=1000001, currency=Currency.DMC)
    assert (
        raw.to_money(scale=100000000).amount
        == Money(amount="0.01000001", currency=Currency.DMC).amount
    )
    with pytest.raises(ValueError):
        Money.from_minor_units("150.0")
    with pytest.raises(ValueError):
        raw.to_money(scale=3)


def test_target_filter_has_its_own_schema():
    filters = TargetFilters(amount=2, status="active", is_advanced=False, paint_seed=0)
    assert (
        filters.serialize(scope="user_targets", game=Game.CS2)
        == "amount=2,status=active,isAdvanced=false,paintSeed=0"
    )
    with pytest.raises(ValidationError):
        TargetFilters(float_part="INVALID")


async def test_async_read_deadline(keys):
    calls = []

    async def handler(request):
        calls.append(request)
        await asyncio.sleep(0.1)
        return httpx.Response(200, json=response_for("balance"))

    async with AsyncDMarketClient(
        *keys,
        transport=httpx.MockTransport(handler),
        rate_limiter=False,
        config=ClientConfig(total_timeout=0.01, max_retries=0),
    ) as client:
        with pytest.raises(RequestTimeoutError):
            await client.account.get_balance()
    assert len(calls) == 1


async def test_waiting_requests_recheck_server_backpressure(keys):
    calls = []

    async def handler(request):
        calls.append(time.monotonic())
        if len(calls) == 1:
            # Other requests start waiting while this response is in flight.
            await asyncio.sleep(0.002)
            return httpx.Response(429, headers={"Retry-After": "0.05"})
        return httpx.Response(200, json=response_for("balance"))

    async with AsyncDMarketClient(
        *keys,
        transport=httpx.MockTransport(handler),
        rate_limiter=RateLimiter(100),
        config=ClientConfig(retry_base_delay=0),
    ) as client:
        await asyncio.gather(*(client.account.get_balance() for _ in range(3)))
    assert len(calls) == 4
    assert calls[1] - calls[0] >= 0.045
