import json
from pathlib import Path
from typing import Any

import pytest
from nacl.signing import SigningKey

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "contracts/openapi.json").read_text())


@pytest.fixture
def keys() -> tuple[str, str]:
    key = SigningKey.generate()
    public = bytes(key.verify_key)
    return public.hex(), (bytes(key) + public).hex()


def minimal(schema: dict[str, Any]) -> Any:
    if "$ref" in schema:
        return minimal(SPEC["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]])
    if "enum" in schema:
        return schema["enum"][0]
    if "properties" in schema or schema.get("type") == "object":
        return {
            name: minimal(value)
            for name, value in schema.get("properties", {}).items()
            if name in schema.get("required", [])
        }
    kind = schema.get("type", "string")
    if kind == "array":
        return []
    if kind == "boolean":
        return False
    if kind in {"number", "integer"}:
        return 1
    return "1" if schema.get("format") in {"int64", "uint64"} else "test"


def response_for(operation: str) -> dict[str, Any]:
    from dmarket_client._internal.endpoints import ENDPOINTS

    endpoint = ENDPOINTS[operation]
    op = SPEC["paths"][endpoint.path][endpoint.method.lower()]
    content = op["responses"]["200"]["content"]["application/json"]
    if "example" in content:
        return content["example"]
    responses = {
        "profile": minimal(content["schema"]),
        "balance": {
            "usd": "150",
            "usdAvailableToWithdraw": "100",
            "dmc": "1000001",
            "dmcAvailableToWithdraw": "1",
        },
        "deposit": {"DepositID": "deposit-1"},
        "deposit_status": {
            "DepositID": "deposit-1",
            "Status": "TransferStatusSuccess",
            "AssetID": ["0:12:34:730"],
            "Assets": [{"InGameAssetID": "0:12:34:730", "DmarketAssetID": "uuid"}],
        },
        "sync": {},
        "closed_offers": {
            "Trades": [
                {
                    "Price": {"Currency": "USD", "Amount": 1.5},
                    "Status": "trade_protected",
                    "Amount": "1",
                    "FinalizationTime": "1700000000",
                    "OfferCreatedAt": "1700000000",
                }
            ],
            "Cursor": "",
            "Total": "1",
        },
        "closed_targets": {
            "Trades": [
                {
                    "Price": {"Currency": "USD", "Amount": 1.5},
                    "Amount": "1",
                    "Status": "reverted",
                    "ClosedAt": "1700000000",
                }
            ],
            "Cursor": "",
            "Total": "1",
        },
        "target_depth": {
            "orders": [
                {"price": "150", "amount": "2", "title": "item", "attributes": {"paintSeed": "any"}}
            ]
        },
        "aggregated_prices": {
            "aggregatedPrices": [
                {
                    "title": "item",
                    "orderBestPrice": {"Currency": "USD", "Amount": "150"},
                    "offerBestPrice": {"Currency": "USD", "Amount": "200"},
                    "orderCount": "2",
                    "offerCount": "3",
                }
            ],
            "nextCursor": "",
        },
        "create_targets": {"Result": [{"TargetID": "target-1", "Successful": True}]},
        "delete_targets": {
            "Result": [{"DeleteTarget": {"TargetID": "target-1"}, "Successful": True}]
        },
        "batch_create": {
            "offers": [{"id": "offer-1", "assetId": "11111111-1111-4111-8111-111111111111"}],
            "failed": [],
        },
        "batch_update": {"offers": [{"id": "offer-1"}], "failed": []},
        "batch_delete": {"offers": [{"id": "offer-1"}], "failed": []},
        "buy": {
            "status": "TxPending",
            "orderId": "order-1",
            "txId": "tx-1",
            "dmOffersFailReason": {"code": ""},
            "dmOffersStatus": {"offer-1": {"started": True}},
        },
        "withdraw": {"transferId": "transfer-1"},
        "fees": {"defaultFee": {"fraction": "0.02", "minAmount": 1}, "reducedFees": []},
        "last_sales": {
            "sales": [
                {
                    "price": "1.50",
                    "date": "1700000000",
                    "txOperationType": "Offer",
                    "offerAttributes": {"floatValue": None},
                }
            ]
        },
    }
    if operation == "market_offers":
        return response_for("user_offers")
    return responses[operation]
