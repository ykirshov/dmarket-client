# Публікація пакета

Репозиторій: https://github.com/ykirshov/dmarket-client
Пакет: https://pypi.org/project/dmarket-client/

## Одноразове налаштування

1. Основна гілка GitHub — `master`.
2. У GitHub Settings → Environments створити `pypi`. Дозволити deployment лише з `master`. Для повністю автоматичних релізів не додавати required reviewers.
3. У PyPI → Your projects → Publishing додати pending publisher (або publisher на сторінці вже створеного проєкту):
   - PyPI project: `dmarket-client`
   - Owner: `ykirshov`
   - Repository: `dmarket-client`
   - Workflow: `release.yml`
   - Environment: `pypi`
4. Увімкнути GitHub Actions. Workflow використовує короткотривалий OIDC доступ, секрет `PYPI_API_TOKEN` не потрібен.
5. Запустити Release на `master` для першої публікації, якщо перший push уже відбувся до налаштування PyPI.

## Подальші релізи

Кожний push у `master`, включно з merge PR, запускає Release. Спочатку проходять Ruff, mypy, перевірка генерації контрактів, pytest і build на Linux, macOS та Windows з Python 3.14. Потім workflow резервує незмінний Git tag, збирає wheel/sdist, публікує їх у PyPI та створює GitHub Release.

Перша версія — `0.1.0`, далі автоматично збільшується patch: `0.1.1`, `0.1.2` тощо. Для переходу на minor/major треба змінити `tool.dmarket-release.initial-version` у `pyproject.toml`, наприклад на `0.2.0`. Версія встановленого клієнта береться з метаданих пакета; джерело версії для build — Git tag.

Релізи виконуються послідовно з чергою до 100 запусків. Повторний запуск того самого commit використовує його зарезервовану версію. Після невдалого запуску використати Actions → Release → Re-run all jobs. Якщо файли вже завантажені, workflow перевіряє SHA-256; відмінні файли для тієї самої версії спричиняють помилку. Git tags не пересуваються, файли PyPI не перезаписуються. Збій до публікації може залишити пропуск номера версії.

Необов'язково: налаштувати захист `master` з обов'язковими PR і перевірками CI. Merge має залишатися забороненим, якщо перевірки не пройшли.

## Локальна перевірка

```sh
uv sync --locked --python 3.14
uv run ruff check .
uv run ruff format --check .
uv run mypy src/dmarket_client
uv run python tools/check_generated.py
uv run pytest -q
uv build
```

Без release tag build із Git може мати dev-версію. Це очікувано: стабільні версії створює Release workflow.
