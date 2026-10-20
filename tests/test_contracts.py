import inspect
import json
from decimal import Decimal

import httpx
import pytest
from conftest import SPEC, response_for
from nacl.signing import VerifyKey

from dmarket_client import (
    AsyncDMarketClient,
    BuyOffer,
    CreateOffer,
    CreateTarget,
    DMarketClient,
    Game,
    Money,
    UpdateOffer,
    WithdrawAsset,
)
from dmarket_client._internal.endpoints import ENDPOINTS
from dmarket_client._internal.serialization import decode_json
from dmarket_client._internal.wire import SCHEMA_MODELS

UUID = "11111111-1111-4111-8111-111111111111"
CALLS = {
    "profile": ("account", "get_profile", {}),
    "balance": ("account", "get_balance", {}),
    "deposit": ("deposits", "create", {"asset_ids": ["0:12:34:730"]}),
    "deposit_status": ("deposits", "get_status", {"deposit_id": "deposit-1"}),
    "blocked_titles": ("deposits", "list_blocked_titles", {"game": Game.CS2}),
    "inventory": ("inventory", "list_items", {"game": Game.CS2}),
    "sync": ("inventory", "sync", {"game": Game.CS2}),
    "user_offers": ("offers", "list", {"game": Game.CS2}),
    "closed_offers": ("offers", "list_closed", {}),
    "target_depth": ("market", "get_targets_by_title", {"game": Game.CS2, "title": "item"}),
    "aggregated_prices": (
        "market",
        "get_aggregated_prices",
        {"game": Game.CS2, "titles": ["item"]},
    ),
    "user_targets": ("targets", "list", {"game": Game.CS2}),
    "closed_targets": ("targets", "list_closed", {}),
    "create_targets": (
        "targets",
        "create",
        {"game": Game.CS2, "targets": [CreateTarget(title="item", price=Money.usd("1.50"))]},
    ),
    "delete_targets": ("targets", "delete", {"target_ids": ["target-1"]}),
    "batch_create": (
        "offers",
        "batch_create",
        {"requests": [CreateOffer(asset_id=UUID, price=Money.usd("1.50"))]},
    ),
    "batch_update": (
        "offers",
        "batch_update",
        {"requests": [UpdateOffer(offer_id="offer-1", price=Money.usd("1.50"))]},
    ),
    "batch_delete": ("offers", "batch_delete", {"offer_ids": ["offer-1"]}),
    "market_offers": ("market", "list_offers", {"game": Game.CS2}),
    "buy": ("market", "buy", {"offers": [BuyOffer(offer_id="offer-1", price=Money.usd("1.50"))]}),
    "withdraw": (
        "withdrawals",
        "create",
        {
            "assets": [WithdrawAsset(id=UUID, class_id="12", game=Game.CS2)],
            "request_id": "request-1",
        },
    ),
    "fees": ("fees", "list_reduced", {"game": Game.CS2}),
    "last_sales": ("sales", "list_recent", {"game": Game.CS2, "title": "item"}),
}


def verify(request: httpx.Request, public: str) -> None:
    from urllib.parse import unquote, urlsplit

    # Rebuild from the transmitted URL independently of SDK signing code.
    url = urlsplit(str(request.url))
    message = (
        (request.method + unquote(url.path) + ("?" + url.query if url.query else "")).encode()
        + request.content
        + request.headers["x-sign-date"].encode()
    )
    signature = request.headers["x-request-sign"]
    assert signature.startswith("dmar ed25519 ")
    assert len(signature.removeprefix("dmar ed25519 ")) == 128
    VerifyKey(bytes.fromhex(public)).verify(
        message, bytes.fromhex(signature.removeprefix("dmar ed25519 "))
    )


@pytest.mark.parametrize("operation", CALLS)
def test_all_sync_contracts(operation, keys):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == ENDPOINTS[operation].method
        verify(request, keys[0])
        if ENDPOINTS[operation].body is not None:
            assert request.headers["content-type"] == "application/json"
        return httpx.Response(200, json=response_for(operation))

    with DMarketClient(*keys, transport=httpx.MockTransport(handler), rate_limiter=False) as client:
        resource, method, kwargs = CALLS[operation]
        result = getattr(getattr(client, resource), method)(**kwargs)
        assert result is not None
        assert result.to_api_dict() == decode_json(json.dumps(response_for(operation)).encode())
        assert result.metadata.status_code == 200
    assert len(calls) == 1


@pytest.mark.parametrize("operation", CALLS)
async def test_all_async_contracts(operation, keys):
    calls = []

    async def handler(request):
        calls.append(request)
        verify(request, keys[0])
        return httpx.Response(200, json=response_for(operation))

    async with AsyncDMarketClient(
        *keys, transport=httpx.MockTransport(handler), rate_limiter=False
    ) as client:
        resource, method, kwargs = CALLS[operation]
        result = await getattr(getattr(client, resource), method)(**kwargs)
        assert result.to_api_dict() == decode_json(json.dumps(response_for(operation)).encode())
    assert len(calls) == 1


def test_registry_is_complete():
    assert set(CALLS) == set(ENDPOINTS)
    assert {(e.method.lower(), e.path) for e in ENDPOINTS.values()} == {
        (method, path)
        for path, operations in SPEC["paths"].items()
        for method in operations
        if method in {"get", "post", "patch", "delete", "put"}
    }
    assert set(SCHEMA_MODELS) == set(SPEC["components"]["schemas"])
    assert len(SCHEMA_MODELS) == 111


def test_sync_async_signatures_match():
    import dmarket_client.async_resources as ar
    import dmarket_client.resources as sr

    for name in [
        "Account",
        "Inventory",
        "Offers",
        "Targets",
        "Market",
        "Deposits",
        "Withdrawals",
        "Fees",
        "Sales",
    ]:
        sync, async_ = getattr(sr, name), getattr(ar, name)
        for method, function in vars(sync).items():
            if not method.startswith("_") and callable(function):
                assert (
                    inspect.signature(function).parameters
                    == inspect.signature(getattr(async_, method)).parameters
                )
                assert inspect.iscoroutinefunction(getattr(async_, method)) == (
                    not method.startswith("iter_")
                )


def test_money_units_and_request_bodies(keys):
    captured = []

    def handler(request):
        captured.append(request)
        if "user-targets/create" in request.url.path:
            response = response_for("create_targets")
        elif "offers:batch" in request.url.path:
            response = response_for("batch_create")
        else:
            response = response_for("buy")
        return httpx.Response(200, json=response)

    with DMarketClient(*keys, transport=httpx.MockTransport(handler), rate_limiter=False) as client:
        client.targets.create(
            game=Game.CS2, targets=[CreateTarget(title="item", price=Money.usd("1.50"))]
        )
        client.offers.batch_create(requests=[CreateOffer(asset_id=UUID, price=Money.usd("1.50"))])
        client.market.buy(offers=[BuyOffer(offer_id="offer-1", price=Money.usd("1.50"))])
    target = decode_json(captured[0].content)
    assert target["Targets"][0]["Price"]["Amount"] == Decimal("1.50")
    assert isinstance(json.loads(captured[0].content)["Targets"][0]["Price"]["Amount"], float)
    assert json.loads(captured[1].content)["requests"][0]["priceCents"] == "150"
    assert json.loads(captured[2].content)["offers"][0]["price"] == {
        "currency": "USD",
        "amount": "150",
    }


def test_response_prices_are_not_confused(keys):
    by_path = {
        ENDPOINTS[op].path: response_for(op)
        for op in ["balance", "target_depth", "aggregated_prices", "last_sales", "inventory"]
    }

    def handler(request):
        path = request.url.path
        return httpx.Response(
            200,
            json=response_for("target_depth")
            if path.startswith("/marketplace-api/v1/targets-by-title/")
            else by_path[path],
        )

    with DMarketClient(*keys, transport=httpx.MockTransport(handler), rate_limiter=False) as client:
        assert client.account.get_balance().usd.amount == Decimal("1.50")
        assert client.account.get_balance().dmc.minor_units == 1000001
        assert client.market.get_targets_by_title(game=Game.CS2, title="item").orders[
            0
        ].price.amount == Decimal("1550")
        assert client.market.get_aggregated_prices(game=Game.CS2, titles=["item"]).items[
            0
        ].order_best_price.amount == Decimal("1.50")
        assert client.sales.list_recent(game=Game.CS2, title="item").items[
            0
        ].price.amount == Decimal("1550.00")
        assert client.inventory.list_items(game=Game.CS2).items[
            0
        ].suggested_price.amount == Decimal("15.99")
