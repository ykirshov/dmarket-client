import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from conftest import response_for
from pydantic import ValidationError
from test_contracts import UUID, verify

from dmarket_client import (
    AsyncDMarketClient,
    BuyOffer,
    ClientConfig,
    CreateOffer,
    CreateTarget,
    DMarketClient,
    Game,
    InventoryFilters,
    Money,
    OfferFilters,
    TargetAttrs,
    WithdrawAsset,
)
from dmarket_client._internal.serialization import decode_json
from dmarket_client._internal.wire import AssetAttributes, MarketplaceTransferStatus
from dmarket_client.exceptions import (
    APIError,
    AuthenticationError,
    BatchOperationError,
    ConfigurationError,
    DepositFailedError,
    IndeterminateOperationError,
    PaginationError,
    PollingTimeoutError,
    RateLimitError,
    RequestTimeoutError,
    RequestValidationError,
    ResponseValidationError,
    ServerError,
)


def client_with(keys, handler, **kwargs):
    return DMarketClient(
        *keys, transport=httpx.MockTransport(handler), rate_limiter=False, **kwargs
    )


def test_wire_optional_null_unknown_values():
    absent = AssetAttributes.model_validate({})
    null = AssetAttributes.model_validate({"unlockDate": None})
    assert "unlock_date" not in absent.model_fields_set
    assert "unlock_date" in null.model_fields_set
    assert absent.to_api_dict() == {}
    assert null.to_api_dict() == {"unlockDate": None}
    with pytest.raises(ValidationError):
        AssetAttributes.model_validate({"tradable": None})
    value = AssetAttributes.model_validate({"tradable": False, "future": {"enabled": True}})
    assert value.to_api_dict()["future"] == {"enabled": True}
    assert value.tradable is False
    assert MarketplaceTransferStatus("FutureStatus").value == "FutureStatus"


@pytest.mark.parametrize("value", [1.5, True, "NaN", "Infinity", "-Infinity"])
def test_money_rejects_inexact_input(value):
    with pytest.raises((ValueError, RequestValidationError, ArithmeticError)):
        Money.usd(value)


def test_money_precision_limits_and_dmc():
    assert Money.usd("0.10").to_minor_units() == 10
    assert Money.from_minor_units("150").amount == Decimal("1.5")
    with pytest.raises(RequestValidationError):
        Money.usd("0.001")
    with pytest.raises(RequestValidationError):
        Money.usd("1e100").to_minor_units()
    with pytest.raises(ValidationError):
        CreateTarget(title="x", price=Money.usd("0"))
    with pytest.raises(ValidationError):
        CreateTarget(title="x", price=Money.usd("1"), amount=101)


def test_request_validation_happens_before_network(keys):
    def forbidden(_):
        pytest.fail("Invalid input reached the network")

    with client_with(keys, forbidden) as client:
        bad_calls = [
            lambda: client.inventory.list_items(game=Game.CS2, limit=101),
            lambda: client.inventory.list_items(game="invalid"),
            lambda: client.deposits.create(asset_ids=[UUID]),
            lambda: client.deposits.list_blocked_titles(game=Game.CS2, cursor="not+urlsafe"),
            lambda: client.targets.create(
                game=Game.CS2, targets=[CreateTarget(title="x", price=Money.usd("1"))] * 101
            ),
            lambda: client.offers.batch_delete(offer_ids="offer-1"),
            lambda: client.offers.batch_delete(offer_ids=["a", "a"]),
            lambda: client.targets.list(
                game=Game.CS2, price_from=Money.usd("2"), price_to=Money.usd("1")
            ),
            lambda: client.offers.list_closed(created_from=datetime(2026, 1, 1)),
            lambda: client.inventory.list_items(
                game=Game.CS2, filters=InventoryFilters(), raw_tree_filters="tradable=true"
            ),
            lambda: client.market.list_offers(game=Game.CS2, filters=OfferFilters(price_cents=100)),
            lambda: client.inventory.list_items(
                game=Game.RUST, filters=InventoryFilters(phase="ruby")
            ),
        ]
        for call in bad_calls:
            with pytest.raises(RequestValidationError):
                call()


def test_filters_and_all_market_query_options(keys):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"items": [], "cursor": "", "total": "0"})

    with client_with(keys, handler) as client:
        client.market.list_offers(
            game=Game.CS2,
            title="AK-47 | X",
            filters=OfferFilters(
                exterior=("factory new", "minimal wear"),
                charm_exists=False,
                sticker=("Sticker | A",),
            ),
            price_from=Money.usd("1.50"),
            price_to=Money.usd("2.50"),
            order_by="discount",
            order_dir="desc",
            limit=2,
            cursor="a+b/=",
            with_images=False,
            offer_type="p2p",
            online_sellers_only=True,
        )
    query = requests[0].url.params
    assert query["priceFrom"] == "150"
    assert query["priceTo"] == "250"
    assert query["withImages"] == "false"
    assert query["onlineSellersOnly"] == "true"
    assert query["cursor"] == "a+b/="
    assert (
        query["treeFilters"]
        == "exterior[]=factory new,exterior[]=minimal wear,charmExists=false,sticker[]=Sticker | A"
    )
    verify(requests[0], keys[0])


def test_closed_query_arrays_and_dotted_names(keys):
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"Trades": [], "Cursor": ""})

    with client_with(keys, handler) as client:
        client.offers.list_closed(
            limit=2,
            statuses=["successful", "reverted"],
            created_from=datetime(2026, 1, 1, tzinfo=UTC),
            finalization_to=1800000000,
        )
    query = captured[0].url.params
    assert query.get_list("Status") == ["successful", "reverted"]
    assert query["OfferCreated.From"] == "1767225600"
    assert query["Finalization.To"] == "1800000000"
    assert query["Limit"] == "2"
    verify(captured[0], keys[0])


def test_target_attributes_and_sync_game_mapping(keys):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200, json={} if request.url.path.endswith("/sync") else {"Result": []}
        )

    with client_with(keys, handler) as client:
        client.inventory.sync(game=Game.CS2)
        client.targets.create(
            game=Game.CS2,
            targets=[
                CreateTarget(
                    title="★ X ™",
                    price=Money.usd("1.50"),
                    attrs=TargetAttrs(paint_seed=0, phase=None, float_part_value="FT-2"),
                )
            ],
        )
    assert decode_json(requests[0].content) == {"Type": "Inventory", "GameID": "CSGO"}
    body = decode_json(requests[1].content)
    assert body["GameID"] == "a8db"
    assert body["Targets"][0]["Attrs"] == {"paintSeed": 0, "phase": None, "floatPartValue": "FT-2"}


def test_lazy_cursor_pagination_preserves_filters_and_limits(keys):
    requests = []

    def handler(request):
        requests.append(request)
        n = len(requests)
        return httpx.Response(
            200,
            json={
                "items": [{"offerId": str(n), "priceCents": "150"}],
                "cursor": "next" if n == 1 else "",
                "total": "100",
            },
        )

    with client_with(keys, handler) as client:
        iterator = client.market.iter_offers(game=Game.CS2, title="item", max_items=2)
        assert requests == []
        assert [x.offer_id for x in iterator] == ["1", "2"]
        assert requests[1].url.params["title"] == "item"
        assert requests[1].url.params["cursor"] == "next"
        assert list(client.market.iter_offers(game=Game.CS2, max_items=0)) == []
        assert len(requests) == 2


def test_pagination_detects_repeated_cursor(keys):
    with client_with(
        keys, lambda _: httpx.Response(200, json={"items": [], "cursor": "repeat"})
    ) as client:
        with pytest.raises(PaginationError):
            list(client.inventory.iter_items(game=Game.CS2))


async def test_async_cursor_pagination(keys):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "items": [{"targetId": str(len(calls))}],
                "cursor": "next" if len(calls) == 1 else "",
            },
        )

    async with AsyncDMarketClient(
        *keys, transport=httpx.MockTransport(handler), rate_limiter=False
    ) as client:
        iterator = client.targets.iter_targets(game=Game.CS2)
        assert calls == []
        assert [x.target_id async for x in iterator] == ["1", "2"]


def test_offset_pagination(keys):
    offsets = []

    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        sales = [{"price": "1.50"}] * (2 if offset == 0 else 1)
        return httpx.Response(200, json={"sales": sales})

    with client_with(keys, handler) as client:
        assert len(list(client.sales.iter_recent(game=Game.CS2, title="item", limit=2))) == 3
    assert offsets == [0, 2]


def test_partial_batches_preserve_success_and_failure(keys):
    response = {
        "offers": [{"id": "ok", "assetId": UUID}],
        "failed": [{"assetId": "bad", "code": "UnknownNewCode", "message": "rejected"}],
    }
    with client_with(keys, lambda _: httpx.Response(200, json=response)) as client:
        result = client.offers.batch_create(requests=[CreateOffer(asset_id=UUID)])
        assert result.successful[0].id == "ok"
        assert result.failed[0].asset_id == "bad"
        assert result.to_api_dict() == response
        with pytest.raises(BatchOperationError) as error:
            result.raise_for_errors()
        assert error.value.result is result


def test_target_partial_failure_has_original_request(keys):
    raw = {
        "Result": [
            {"Successful": True, "TargetID": "ok"},
            {
                "Successful": False,
                "CreateTarget": {"Title": "failed"},
                "Error": {"Code": "FutureError", "Message": "rejected"},
            },
        ]
    }
    with client_with(keys, lambda _: httpx.Response(200, json=raw)) as client:
        result = client.targets.create(
            game=Game.CS2, targets=[CreateTarget(title="x", price=Money.usd("1"))]
        )
    assert result.failed[0].request == {"Title": "failed"}
    assert result.successful[0].target_id == "ok"


@pytest.mark.parametrize(
    "status,error_cls",
    [(401, AuthenticationError), (429, RateLimitError), (503, ServerError), (302, APIError)],
)
def test_http_status_precedes_success_schema(keys, status, error_cls):
    config = ClientConfig(max_retries=0)
    with client_with(
        keys,
        lambda _: httpx.Response(status, json={"code": "InvalidAPIKey", "message": keys[1]}),
        config=config,
    ) as client:
        with pytest.raises(error_cls) as caught:
            client.account.get_profile()
        assert keys[1] not in str(caught.value)
        assert caught.value.status_code == status


def test_invalid_or_non_json_response_is_not_empty_success(keys):
    for response in [
        httpx.Response(200, text="<html>error</html>"),
        httpx.Response(200, json={"usd": "bad"}),
        httpx.Response(200, json={"items": [{"priceCents": "bad"}]}),
    ]:
        with client_with(keys, lambda _, r=response: r) as client:
            with pytest.raises(ResponseValidationError):
                if "items" in response.text:
                    client.market.list_offers(game=Game.CS2)
                else:
                    client.account.get_balance()


def test_safe_reads_retry_but_writes_never_retry(keys):
    calls = []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(503, text="unavailable")
            if len(calls) < 3
            else httpx.Response(200, json=response_for("balance"))
        )

    config = ClientConfig(retry_base_delay=0)
    with client_with(keys, handler, config=config) as client:
        result = client.account.get_balance()
        assert result.metadata.attempts == 3
    calls.clear()
    with client_with(keys, handler, config=config) as client:
        with pytest.raises(ServerError):
            client.market.buy(offers=[BuyOffer(offer_id="x", price=Money.usd("1"))])
    assert len(calls) == 1


def test_write_timeout_retains_request_id(keys):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("possibly applied", request=request)

    with client_with(keys, handler) as client:
        with pytest.raises(IndeterminateOperationError) as caught:
            client.withdrawals.create(
                assets=[WithdrawAsset(id=UUID, class_id="1", game=Game.CS2)], request_id="stable-id"
            )
        assert caught.value.request_id == "stable-id"
        assert caught.value.__suppress_context__
    assert len(calls) == 1


def test_retry_after_exceeding_deadline_does_not_send_again(keys):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "1000"}, json={"message": "limited"})

    with client_with(keys, handler) as client:
        with pytest.raises(RequestTimeoutError):
            client.account.get_balance()
    assert len(calls) == 1


def test_external_http_client_ownership_and_redirects(keys):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://other.invalid"})

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as http:
        with DMarketClient(*keys, http_client=http, rate_limiter=False) as client:
            with pytest.raises(APIError):
                client.account.get_balance()
        assert not http.is_closed
    assert len(requests) == 1


def test_closed_client_and_env_validation(keys, monkeypatch):
    client = client_with(keys, lambda _: httpx.Response(200, json={}))
    client.close()
    with pytest.raises(ConfigurationError):
        client.account.get_balance()
    monkeypatch.delenv("DMARKET_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("DMARKET_SECRET_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        DMarketClient.from_env()


def test_deposit_polling_terminal_status_and_failure(keys):
    statuses = iter(["TransferStatusPending", "TransferStatusSuccess"])
    with client_with(
        keys, lambda _: httpx.Response(200, json={"Status": next(statuses)})
    ) as client:
        assert client.deposits.wait("id", poll_interval=0.001).status == "TransferStatusSuccess"
    with client_with(
        keys,
        lambda _: httpx.Response(
            200, json={"Status": "TransferStatusError", "Error": "InventoryRevoked"}
        ),
    ) as client:
        with pytest.raises(DepositFailedError) as caught:
            client.deposits.wait("id")
        assert caught.value.status.error == "InventoryRevoked"
    with client_with(
        keys, lambda _: httpx.Response(200, json={"Status": "NewUnknownState"})
    ) as client:
        with pytest.raises(PollingTimeoutError) as caught:
            client.deposits.wait("id", timeout=0.005, poll_interval=0.001)
        assert caught.value.last_status.status == "NewUnknownState"


async def test_async_cancellation_is_not_swallowed(keys):
    entered = asyncio.Event()

    async def handler(request):
        entered.set()
        await asyncio.sleep(30)
        return httpx.Response(200, json={})

    async with AsyncDMarketClient(
        *keys, transport=httpx.MockTransport(handler), rate_limiter=False
    ) as client:
        task = asyncio.create_task(client.deposits.wait("id"))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
