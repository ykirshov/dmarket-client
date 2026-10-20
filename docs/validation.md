# Перевірка реалізації 0.1.0

Дата: 20.10.2026. Середовище: CPython **3.14.8**, macOS arm64. Реальні ключі та торговий акаунт не використовувалися.

| Перевірка | Результат |
| --- | --- |
| Офлайн pytest suite | **219 passed** |
| Strict mypy для SDK | Усі 24 Python-модулі без помилок |
| Ruff lint і форматування | Без помилок |
| Генеровані файли | Wire models, endpoints, async resources відповідають джерелам |
| Покриття API | 23 операції перевірено через sync та async методи |
| Покриття схем | 111 іменованих схем імпортуються та валідують мінімальні значення |
| Підпис | Окремий локальний HTTP-сервер перевіряє Ed25519 над отриманими URL/body bytes |
| Зовнішній споживач | Wheel встановлено в окремий venv без editable-посилання на source |
| Consumer smoke | 3 офлайн HTTP-запити: balance, target create, async offers; підписи перевірені |
| Типи встановленого wheel | Окремий consumer-модуль проходить strict mypy через py.typed |
| Snapshot | SHA-256 збігається з оригінальним наданим OpenAPI; оригінал не змінено |
| Дистрибутиви | Wheel та sdist збираються; runtime wheel не потребує OpenAPI/генераторів |

Тести охоплюють Decimal units, валідність запитів, усі ігри, sync enum, partial batches, status-before-schema, unknown enum/fields, missing/null/zero/false, cursor/offset, повторний cursor, дедлайни, відсутність write-retries, requestId, polling, async cancellation, ownership HTTP-client, redirects та rate-limit backpressure для конкурентних запитів.

Джерела для відтворення: `tests/`, `tools/check_generated.py`, `pyproject.toml`, `uv.lock`. Типові команди — у README. У sandbox для loopback-тесту може знадобитися дозвіл на локальний socket.

CI для Linux/macOS/Windows налаштований, але в цьому середовищі запущено лише macOS. Live-поведінка акаунта, P2P, серверні batch-ліміти offers, ідемпотентність withdrawal та free-threaded Python не підтверджені. Вони не моделюються як гарантовані можливості SDK. Віддалений статус релізів доступний у GitHub Actions і PyPI.
