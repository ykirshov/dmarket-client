"""Build the public method reference without making network requests."""

import inspect
import json
from pathlib import Path

from dmarket_client import resources

ROOT = Path(__file__).resolve().parents[1]
METHODS = {
    "profile": ("account", "Account", "get_profile"),
    "balance": ("account", "Account", "get_balance"),
    "deposit": ("deposits", "Deposits", "create"),
    "deposit_status": ("deposits", "Deposits", "get_status"),
    "blocked_titles": ("deposits", "Deposits", "list_blocked_titles"),
    "inventory": ("inventory", "Inventory", "list_items"),
    "sync": ("inventory", "Inventory", "sync"),
    "user_offers": ("offers", "Offers", "list"),
    "closed_offers": ("offers", "Offers", "list_closed"),
    "target_depth": ("market", "Market", "get_targets_by_title"),
    "aggregated_prices": ("market", "Market", "get_aggregated_prices"),
    "user_targets": ("targets", "Targets", "list"),
    "closed_targets": ("targets", "Targets", "list_closed"),
    "create_targets": ("targets", "Targets", "create"),
    "delete_targets": ("targets", "Targets", "delete"),
    "batch_create": ("offers", "Offers", "batch_create"),
    "batch_update": ("offers", "Offers", "batch_update"),
    "batch_delete": ("offers", "Offers", "batch_delete"),
    "market_offers": ("market", "Market", "list_offers"),
    "buy": ("market", "Market", "buy"),
    "withdraw": ("withdrawals", "Withdrawals", "create"),
    "fees": ("fees", "Fees", "list_reduced"),
    "last_sales": ("sales", "Sales", "list_recent"),
}


if __name__ == "__main__":
    endpoints = json.loads((ROOT / "contracts/endpoints.json").read_text())
    lines = [
        "# Довідник публічного API",
        "",
        "Згенеровано з реалізації. Для `AsyncDMarketClient` звичайні методи викликаються через `await`, `iter_*` — через `async for`.",
        "",
        "Усі серверні методи можуть підняти APIError, TransportError або ResponseValidationError та їхні спеціалізовані підкласи. Перевірки аргументів дають RequestValidationError або Pydantic ValidationError. Див. README для політики повторів.",
        "",
    ]
    for operation, data in endpoints.items():
        resource, classname, method = METHODS[operation]
        function = getattr(getattr(resources, classname), method)
        signature = str(inspect.signature(function)).replace("self, ", "").replace("(self)", "()")
        for prefix in [
            "dmarket_client.models.",
            "dmarket_client.filters.",
            "dmarket_client._internal.wire.",
            "collections.abc.",
            "typing.",
        ]:
            signature = signature.replace(prefix, "")
        for original, alias in {
            "RepresentationUserAccountResponse": "UserProfile",
            "MarketplaceDepositAssetsResponse": "DepositCreated",
            "MarketplaceGetDepositStatusResponse": "DepositStatus",
            "MarketplaceUserInventorySyncResponse": "InventorySyncResult",
            "EntityOfferBuyResponse": "PurchaseResult",
            "EntityListFeeResponse": "ReducedFees",
        }.items():
            signature = signature.replace(original, alias)
        lines.extend(
            [
                f"## `{resource}.{method}`",
                "",
                f"`{data['method']} {data['path']}`",
                "",
                "```text",
                f"client.{resource}.{method}{signature}",
                "```",
                "",
                "Повтори за замовчуванням: "
                + (
                    "дозволені для тимчасових збоїв читання."
                    if data["safe_to_retry"]
                    else "вимкнені; метод змінює стан."
                ),
                "",
                f"Повна wire-схема відповіді: `{data['response_schema']}` у [OpenAPI](../contracts/openapi.json).",
                "",
            ]
        )
    lines.extend(
        [
            "## Допоміжні методи",
            "",
            "`inventory.iter_items`, `offers.iter_offers`, `offers.iter_closed`, `targets.iter_targets`, `targets.iter_closed`, `market.iter_offers`, `market.iter_aggregated_prices`, `deposits.iter_blocked_titles`, `fees.iter_reduced`, `sales.iter_recent` приймають ті самі фільтри та `max_items` / `max_pages`.",
            "",
            "`offers.create`, `offers.update`, `offers.delete` обгортають відповідні batch-операції. `deposits.wait(deposit_id, timeout=120, poll_interval=2)` опитує статус без повторного створення депозиту.",
            "",
        ]
    )
    (ROOT / "docs/api-reference.md").write_text("\n".join(lines))
