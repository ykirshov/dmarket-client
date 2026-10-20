# DMarket Client · Python 3.14

Типізований пакет для всіх 23 операцій наданого DMarket OpenAPI: sync/native asyncio, моделі запитів і відповідей, Ed25519, Decimal, пагінація, часткові batch-результати.

## Встановлення

Потрібен Python **3.14+**. Пакет поки не опубліковано в PyPI; встановіть із цієї папки або з наданого wheel:

```bash
python3.14 -m pip install /absolute/path/to/dmarket-client
```

Для розробки в корені пакета:

```bash
uv sync --locked --python 3.14
uv run pytest -q
uv run mypy src/dmarket_client
uv run ruff check .
uv run ruff format --check .
uv run python tools/check_generated.py
uv build
```

Тести використовують синтетичні ключі, MockTransport і локальний HTTP-сервер. Вони не звертаються до торгового акаунта. Для loopback-тесту середовище має дозволяти відкриття локального порту.

## Перший запит

Задайте `DMARKET_PUBLIC_KEY` і `DMARKET_SECRET_KEY` у середовищі зовнішнього застосунку. SDK не завантажує `.env` автоматично та не записує ключі у файли.

```python
from dmarket_client import DMarketClient, Game

with DMarketClient.from_env() as client:
    balance = client.account.get_balance()
    print(balance.usd.amount)  # Decimal у доларах

    for item in client.inventory.iter_items(game=Game.CS2, max_items=20):
        if item.attributes is not None:
            print(item.attributes.title)
```

Також доступний `DMarketClient(public_key=..., secret_key=...)`. Стандартний secret — 64 bytes / 128 hex-символів у форматі Ed25519 seed + public key. Пара перевіряється локально. Для явного 32-byte seed використайте `secret_key_is_seed=True`. API-ключі створюються в налаштуваннях DMarket.

```python
import asyncio
from dmarket_client import AsyncDMarketClient, Game


async def main() -> None:
    async with AsyncDMarketClient.from_env() as client:
        async for offer in client.market.iter_offers(game=Game.CS2, max_items=20):
            print(offer.offer_id, offer.price)


asyncio.run(main())
```

## Ресурси

| Ресурс | Серверні методи |
| --- | --- |
| `account` | `get_profile`, `get_balance` |
| `inventory` | `list_items`, `sync` |
| `market` | `list_offers`, `get_targets_by_title`, `get_aggregated_prices`, `buy` |
| `offers` | `list`, `list_closed`, `batch_create`, `batch_update`, `batch_delete` |
| `targets` | `list`, `list_closed`, `create`, `delete` |
| `deposits` | `create`, `get_status`, `list_blocked_titles` |
| `withdrawals` | `create` |
| `fees` | `list_reduced` |
| `sales` | `list_recent` |

[Довідник усіх аргументів і типів](docs/api-reference.md). [OpenAPI](contracts/openapi.json). [Уточнення контракту](contracts/contract_overrides.json).

`offers.create/update/delete` — одиничні обгортки над batch. `inventory.sync(game=Game.CS2)` передає sync-ID `CSGO`. Повний sync-enum, включно з LifeBeyond, доступний як `SyncGame`; торгові listings використовують чотири значення `Game`.

## Гроші, фільтри та сторінки

У наступних фрагментах `client` — відкритий екземпляр клієнта.

```python
from dmarket_client import Game, Money, OfferFilters

page = client.market.list_offers(
    game=Game.CS2,
    title="AK-47",
    price_from=Money.usd("1.50"),
    price_to=Money.usd("20.00"),
    filters=OfferFilters(exterior=("factory new", "minimal wear")),
    order_by="price",
    limit=20,
)
for offer in page.items:
    print(offer.price)
```

`Money.amount` — головні одиниці валюти; `Money.usd("1.50")` — USD 1.50. Передавайте `str`, `int` або `Decimal`; binary float відхиляється, частки cents не округлюються мовчки. `Money.from_minor_units(150)` явно створює USD 1.50.

DMC-баланс повертається як `MinorMoney`: `.minor_units` містить точні dimoshi. Контракт не задає масштаб DMC. Можна явно перетворити через `.to_money(scale=...)` з підтвердженим додатним степенем десяти. `BuyOffer` також приймає `MinorMoney` для явної ціни в coins.

`InventoryFilters`, `OfferFilters`, `TargetFilters` перевіряють правила ресурсу та гри. `raw_tree_filters` дає доступ до розширених серверних фільтрів; його не можна поєднувати з `filters`. Назви предметів передаються звичайним текстом, SDK виконує URL encoding.

`list_*`/`list` повертають одну сторінку з `items`, `next_cursor`, `total`. Ітератори ліниво обходять cursor/offset, зберігають фільтри й підтримують `max_items` / `max_pages`:

- `inventory.iter_items`;
- `market.iter_offers`, `market.iter_aggregated_prices`;
- `offers.iter_offers/iter_closed`, `targets.iter_targets/iter_closed`;
- `deposits.iter_blocked_titles`, `fees.iter_reduced`, `sales.iter_recent`.

Активний ринок може змінюватися під час обходу; snapshot не гарантується. Необов'язкові поля відповіді можуть бути `None`. `to_api_dict()` зберігає повний контракт і невідомі поля; JSON numbers можуть бути Decimal, а timestamp-поля — aware datetime. Це Python-структура, а не готовий JSON-текст. `.metadata` містить HTTP status, request ID, кількість спроб і rate-limit headers.

## Операції запису

Наступний приклад створює реальну заявку при виконанні з чинними ключами:

```python
from dmarket_client import CreateTarget, Game, Money, TargetAttrs

result = client.targets.create(
    game=Game.CS2,
    targets=[
        CreateTarget(
            title="AK-47 | Redline (Field-Tested)",
            price=Money.usd("1.50"),
            amount=1,
            attrs=TargetAttrs(float_part_value="FT-2"),
        )
    ],
)
print(result.successful, result.failed)
result.raise_for_errors()
```

`BatchOperationError.result` зберігає весь результат, включно з успішними елементами. `CreateOffer`, `UpdateOffer`, `BuyOffer`, `WithdrawAsset` задають інші write-контракти. Купівля потребує очікуваної ціни кожного offer.

Deposit приймає composite `attributes.in_game_asset_id`, наприклад `0:3938946694:512345678901234567:252490`. Steam asset ID та DMarket UUID не підходять; початковий `0` зберігається.

```python
deposit = client.deposits.create(asset_ids=[composite_in_game_asset_id])
if deposit.deposit_id is not None:
    completed = client.deposits.wait(deposit.deposit_id, timeout=120, poll_interval=2)
```

`wait` опитує лише status-ендпоінт. `DepositFailedError.status` і `PollingTimeoutError.last_status` містять діагностику; невідомий стан не означає успіх. Async-скасування поширюється як `CancelledError`.

Withdrawal генерує request ID або приймає ваш `request_id`; він зберігається в результаті/винятку. `transfer_id` і `PurchaseResult.status == "TxPending"` не підтверджують завершення. У наданому контракті немає status-методів для buy/withdrawal.

## Помилки, повтори та конфігурація

- GET і read-only POST aggregated-prices: до двох повторів для мережевих збоїв, 429 і 500/502/503/504, з backoff/jitter та Retry-After.
- Операції запису не повторюються автоматично. `IndeterminateOperationError` повідомляє про втрату відповіді, коли операція могла виконатися.
- `ResponseValidationError` після write-виклику також не означає відкату серверної операції.
- HTTP status перевіряється раніше success-моделі, включно з помилковими OpenAPI `default` schemas.
- Винятки імпортуються з `dmarket_client.exceptions`: `APIError`, `AuthenticationError`, `RateLimitError`, `TransportError`, `RequestTimeoutError`, `ResponseValidationError`, `IndeterminateOperationError`.
- Моделі вводу можуть підняти Pydantic `ValidationError`; перевірки методів — `RequestValidationError`.

```python
from dmarket_client import ClientConfig, DMarketClient, RateLimiter

limiter = RateLimiter()  # спільний консервативний бюджет 5 RPS
config = ClientConfig(request_timeout=20, total_timeout=60, max_retries=2)
with DMarketClient.from_env(config=config, rate_limiter=limiter) as client:
    balance = client.account.get_balance()
```

Один limiter можна передати кільком клієнтам акаунта. Server headers можуть зменшити швидкість і відкласти запити. Для кількох процесів реалізуйте протокол `Limiter`: `reserve(group)` видає дозвіл через 0 або повертає delay перед повторною перевіркою; `observe(group, headers)` обробляє відповідь. `rate_limiter=False` вимикає лише локальний limiter.

`request_timeout` обмежує мережеві фази; `total_timeout` — чергу та повтори. Async-клієнт додатково використовує загальний asyncio timeout. Sync має фазові HTTPX timeouts, без примусового переривання потоку за wall-clock deadline.

Можна передати власний HTTPX client або transport. Переданий client закриває власник. SDK вимикає redirects для своїх викликів. Auth/hooks/retries власного transport залишаються відповідальністю застосунку. Створений SDK HTTP-client не підхоплює proxy settings із середовища; proxy можна задати у переданому client.

## Перевірка та межі

Локальна перевірка — Python 3.14 на macOS arm64. CI налаштований для Linux, macOS і Windows; `3.14t` не заявлений як перевірений runtime. Live-акаунт не використовувався. Підпис перевірено окремим loopback HTTP-сервером над отриманими URL/body bytes.

Описи P2P суперечливі: buy-схема містить `p2p`, aggregated-prices говорить про купівлю через сайт. Значення збережене, але live P2P-покупки не підтверджено. Batch-ліміти offers та ідемпотентність requestId не вигадуються. Blocked titles перевіряє назву; конкретний предмет може мати інші обмеження. Прихованого кешу списку немає.

## Джерела та оновлення

SHA-256 snapshot: `24ddbbf72bb25a52d0b37a8f0f719a3f1a189748b72e7aed2847acb593ef5492`.

[DMarket API](https://docs.dmarket.com/v1/swagger.html), [приклад підпису](https://github.com/dmarket/dm-trading-tools), [ліміти](https://support.dmarket.com/hc/en-us/articles/25269064897297-What-are-the-rate-limits-for-requests), [Terms of Use](https://dmarket.com/terms-of-use).

Wire-моделі та async resources статичні: runtime не читає OpenAPI і не запускає генератори. Після оновлення контракту:

```bash
uv run python tools/generate_wire.py
uv run python tools/generate_endpoints.py
uv run python tools/generate_async.py
uv run ruff check --fix .
uv run ruff format .
uv run python tools/check_generated.py
uv run python tools/build_reference.py
uv run pytest -q
```

## Релізи

Після merge у `master` GitHub Actions перевіряє пакет і автоматично публікує наступну patch-версію в PyPI. Одноразове налаштування Trusted Publishing та відновлення невдалих релізів описані в [docs/publishing.md](docs/publishing.md).
