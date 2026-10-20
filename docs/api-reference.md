# Довідник публічного API

Згенеровано з реалізації. Для `AsyncDMarketClient` звичайні методи викликаються через `await`, `iter_*` — через `async for`.

Усі серверні методи можуть підняти APIError, TransportError або ResponseValidationError та їхні спеціалізовані підкласи. Перевірки аргументів дають RequestValidationError або Pydantic ValidationError. Див. README для політики повторів.

## `account.get_profile`

`GET /account/v1/user`

```text
client.account.get_profile() -> UserProfile
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `representation.UserAccountResponse` у [OpenAPI](../contracts/openapi.json).

## `account.get_balance`

`GET /account/v1/balance`

```text
client.account.get_balance() -> Balance
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `representation.UserBalance` у [OpenAPI](../contracts/openapi.json).

## `deposits.create`

`POST /marketplace-api/v1/deposit-assets`

```text
client.deposits.create(*, asset_ids: Sequence[str]) -> DepositCreated
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `marketplaceDepositAssetsResponse` у [OpenAPI](../contracts/openapi.json).

## `deposits.get_status`

`GET /marketplace-api/v1/deposit-status/{DepositID}`

```text
client.deposits.get_status(deposit_id: str) -> DepositStatus
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplaceGetDepositStatusResponse` у [OpenAPI](../contracts/openapi.json).

## `deposits.list_blocked_titles`

`GET /marketplace-api/v2/deposit-blocked-titles`

```text
client.deposits.list_blocked_titles(*, game: Game, limit: int = 1000, cursor: str | None = None) -> BlockedTitlesPage
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplacev2GetDepositBlockedTitlesResponse` у [OpenAPI](../contracts/openapi.json).

## `inventory.list_items`

`GET /marketplace-api/v2/user/inventory`

```text
client.inventory.list_items(*, game: Game, title: str | None = None, filters: InventoryFilters | None = None, raw_tree_filters: str | None = None, order_by: Literal['price', 'title', 'float', 'createdAt', 'updatedAt'] | None = None, order_dir: Literal['asc', 'desc'] | None = None, limit: int = 100, cursor: str | None = None) -> Page[InventoryItem]
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplacev2GetUserInventoryResponse` у [OpenAPI](../contracts/openapi.json).

## `inventory.sync`

`POST /marketplace-api/v1/user-inventory/sync`

```text
client.inventory.sync(*, game: Game | SyncGame) -> InventorySyncResult
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `marketplaceUserInventorySyncResponse` у [OpenAPI](../contracts/openapi.json).

## `offers.list`

`GET /marketplace-api/v2/user/offers`

```text
client.offers.list(*, game: Game, title: str | None = None, filters: OfferFilters | None = None, raw_tree_filters: str | None = None, order_by: Literal['price', 'title', 'float', 'createdAt'] | None = None, order_dir: Literal['asc', 'desc'] | None = None, limit: int = 100, cursor: str | None = None) -> Page[Offer]
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplacev2GetUserOffersResponse` у [OpenAPI](../contracts/openapi.json).

## `offers.list_closed`

`GET /marketplace-api/v1/user-offers/closed`

```text
client.offers.list_closed(*, limit: int = 100, order_dir: Literal['asc', 'desc'] = 'desc', created_from: datetime.datetime | int | None = None, created_to: datetime.datetime | int | None = None, closed_from: datetime.datetime | int | None = None, closed_to: datetime.datetime | int | None = None, finalization_from: datetime.datetime | int | None = None, finalization_to: datetime.datetime | int | None = None, statuses: Sequence[Literal['successful', 'reverted', 'trade_protected']] | None = None, cursor: str | None = None) -> Page[ClosedOfferTrade]
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplaceGetUserClosedOffersResponse` у [OpenAPI](../contracts/openapi.json).

## `market.get_targets_by_title`

`GET /marketplace-api/v1/targets-by-title/{game_id}/{title}`

```text
client.market.get_targets_by_title(*, game: Game, title: str) -> TargetDepth
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplaceGetTargetsByTitleResponse` у [OpenAPI](../contracts/openapi.json).

## `market.get_aggregated_prices`

`POST /marketplace-api/v1/aggregated-prices`

```text
client.market.get_aggregated_prices(*, game: Game, titles: Sequence[str], include_p2p: bool | None = None, limit: int = 100, cursor: str | None = None) -> Page[AggregatedPrice]
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplaceListAggregatedPricesResponse` у [OpenAPI](../contracts/openapi.json).

## `targets.list`

`GET /marketplace-api/v2/user/targets`

```text
client.targets.list(*, game: Game, title: str | None = None, filters: TargetFilters | None = None, raw_tree_filters: str | None = None, price_from: Money | None = None, price_to: Money | None = None, order_by: Literal['price', 'title', 'createdAt'] | None = None, order_dir: Literal['asc', 'desc'] | None = None, limit: int = 100, cursor: str | None = None) -> Page[Target]
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplacev2GetUserTargetsResponse` у [OpenAPI](../contracts/openapi.json).

## `targets.list_closed`

`GET /marketplace-api/v1/user-targets/closed`

```text
client.targets.list_closed(*, limit: int = 100, order_dir: Literal['asc', 'desc'] = 'desc', created_from: datetime.datetime | int | None = None, created_to: datetime.datetime | int | None = None, closed_from: datetime.datetime | int | None = None, closed_to: datetime.datetime | int | None = None, finalization_from: datetime.datetime | int | None = None, finalization_to: datetime.datetime | int | None = None, statuses: Sequence[Literal['successful', 'reverted', 'trade_protected']] | None = None, cursor: str | None = None) -> Page[ClosedTargetTrade]
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplaceGetUserClosedTargetsResponse` у [OpenAPI](../contracts/openapi.json).

## `targets.create`

`POST /marketplace-api/v1/user-targets/create`

```text
client.targets.create(*, game: Game, targets: Sequence[CreateTarget]) -> TargetCreateBatchResult
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `marketplaceCreateTargetsResponse` у [OpenAPI](../contracts/openapi.json).

## `targets.delete`

`POST /marketplace-api/v1/user-targets/delete`

```text
client.targets.delete(*, target_ids: Sequence[str]) -> TargetDeleteBatchResult
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `marketplaceDeleteTargetsResponse` у [OpenAPI](../contracts/openapi.json).

## `offers.batch_create`

`POST /marketplace-api/v2/offers:batchCreate`

```text
client.offers.batch_create(*, requests: Sequence[CreateOffer]) -> OfferBatchResult
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `marketplacev2BatchCreateOffersResponse` у [OpenAPI](../contracts/openapi.json).

## `offers.batch_update`

`POST /marketplace-api/v2/offers:batchUpdate`

```text
client.offers.batch_update(*, requests: Sequence[UpdateOffer]) -> OfferBatchResult
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `marketplacev2BatchUpdateOffersResponse` у [OpenAPI](../contracts/openapi.json).

## `offers.batch_delete`

`POST /marketplace-api/v2/offers:batchDelete`

```text
client.offers.batch_delete(*, offer_ids: Sequence[str]) -> OfferBatchResult
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `marketplacev2BatchDeleteOffersResponse` у [OpenAPI](../contracts/openapi.json).

## `market.list_offers`

`GET /marketplace-api/v2/offers`

```text
client.market.list_offers(*, game: Game, title: str | None = None, filters: OfferFilters | None = None, raw_tree_filters: str | None = None, price_from: Money | None = None, price_to: Money | None = None, order_by: Literal['price', 'title', 'float', 'createdAt', 'discount'] | None = None, order_dir: Literal['asc', 'desc'] | None = None, limit: int = 100, cursor: str | None = None, with_images: bool | None = None, offer_type: Literal['dmarket', 'p2p', 'all'] | None = None, online_sellers_only: bool | None = None) -> Page[Offer]
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `marketplacev2GetMarketplaceOffersResponse` у [OpenAPI](../contracts/openapi.json).

## `market.buy`

`PATCH /exchange/v1/offers-buy`

```text
client.market.buy(*, offers: Sequence[BuyOffer]) -> PurchaseResult
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `entity.OfferBuyResponse` у [OpenAPI](../contracts/openapi.json).

## `withdrawals.create`

`POST /exchange/v1/withdraw-assets`

```text
client.withdrawals.create(*, assets: Sequence[WithdrawAsset], request_id: str | None = None) -> WithdrawalCreated
```

Повтори за замовчуванням: вимкнені; метод змінює стан.

Повна wire-схема відповіді: `entity.WithdrawResponse` у [OpenAPI](../contracts/openapi.json).

## `fees.list_reduced`

`GET /exchange/v1/customized-fees`

```text
client.fees.list_reduced(*, game: Game, offer_type: Literal['dmarket', 'p2p'] = 'dmarket', limit: int = 10, offset: int = 0) -> ReducedFees
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `entity.ListFeeResponse` у [OpenAPI](../contracts/openapi.json).

## `sales.list_recent`

`GET /trade-aggregator/v1/last-sales`

```text
client.sales.list_recent(*, game: Game, title: str, filters: str | None = None, tx_operation_types: Sequence[Literal['Offer', 'Target']] | None = None, limit: int = 100, offset: int = 0) -> SalesPage
```

Повтори за замовчуванням: дозволені для тимчасових збоїв читання.

Повна wire-схема відповіді: `tradeGetLastSalesResponse` у [OpenAPI](../contracts/openapi.json).

## Допоміжні методи

`inventory.iter_items`, `offers.iter_offers`, `offers.iter_closed`, `targets.iter_targets`, `targets.iter_closed`, `market.iter_offers`, `market.iter_aggregated_prices`, `deposits.iter_blocked_titles`, `fees.iter_reduced`, `sales.iter_recent` приймають ті самі фільтри та `max_items` / `max_pages`.

`offers.create`, `offers.update`, `offers.delete` обгортають відповідні batch-операції. `deposits.wait(deposit_id, timeout=120, poll_interval=2)` опитує статус без повторного створення депозиту.
