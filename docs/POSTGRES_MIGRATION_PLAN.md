# План миграции на PostgreSQL

## 1. Цели и критерии успеха

- Обеспечить мультипользовательский доступ, параллельные записи и масштабируемость для AI/бот подсистем.
- Сохранить целостность истории торгов, обучающих выборок и конфигураций.
- Дать возможность выполнять перекрёстные выборки по множеству клиентов (tenant-aware запросы).
- Перевести все модули на единый слой доступа к данным с миграциями схемы и CI-тестами.

## 2. Текущий ландшафт данных

| Область | Текущее хранилище | Основные файлы / таблицы | Модули |
|---------|-------------------|--------------------------|--------|
| AI тренировки | SQLite `data/ai/ai_data.db` (+ JSON история) | `simulated_trades`, `bot_trades`, `candles_history`, `bots_data_snapshots`, `parameter_training_samples`, `used_training_parameters`, `best_params_per_symbol`, `blocked_params`, `win_rate_targets` | `bot_engine/ai/ai_database.py`, `bot_engine/ai/*.py`, `bot_engine/trading_bot.py` |
| Bots runtime | SQLite `data/bots_data.db` | `bots_state`, `bot_positions_registry`, `rsi_cache`, `mature_coins`, `process_state`, `individual_coin_settings`, `maturity_check_cache`, `delisted` | `bot_engine/bots_database.py`, `bot_engine/bot_history.py`, `bot_engine/storage.py` |
| JSON кэши | Файлы в `data/*.json`, `data/ai/*.json` | Кэши свечей, истории процессов, конфиги | `bots_modules/`, `bot_engine/utils` |
| Лицензирование | SQLite `license_generator/license_data.db` | пользователи/лицензии | `license_generator/*` |

## 3. Целевая архитектура PostgreSQL

- Единый кластер PostgreSQL (Docker Compose для разработки, Managed/VM для прод).
- Схемы:
  - `ai_core` — обучение и аналитика.
  - `bots_core` — состояние ботов/рынка.
  - `supporting` — лицензирование, фоновые процессы.
- Общие требования: строгие типы (`TIMESTAMPTZ`, `NUMERIC`), JSONB для сложных параметров, все таблицы включают `tenant_id UUID NOT NULL`.
- Row Level Security для многоарендности, отдельные роли `infobot_app`, `infobot_readonly`, `infobot_admin`.
- Инструменты: SQLAlchemy 2.0 + Alembic, `asyncpg` (для async сервисов), PgBouncer перед приложением.

## 4. Карта "что куда"

| Источник | Путь/Таблица | Новая таблица (схема) | Комментарий |
|----------|--------------|-----------------------|-------------|
| JSON `data/ai/simulated_trades.json` → SQLite `simulated_trades` | `ai_data.db.simulated_trades` | `ai_core.simulated_trades` | `id` → `BIGSERIAL`; `created_at` → `TIMESTAMPTZ`; `*_json` поля → `JSONB`. |
| `bot_trades` | `ai_data.db.bot_trades` | `ai_core.bot_trades` | Добавить `tenant_id`, `exchange_id`, `strategy_id`. |
| `exchange_trades` | `ai_data.db.exchange_trades` | `ai_core.exchange_trades` | Ввести foreign key на `ai_core.training_sessions`. |
| `candles_history` | `ai_data.db.candles_history` | `ai_core.candles_history` | Рассмотреть партиционирование по `symbol`/`bucket`. |
| `bots_data_snapshots` | `ai_data.db.bots_data_snapshots` | `ai_core.bot_snapshots` | Перевести снимки в JSONB + `generated_at`. |
| `parameter_training_samples` | `ai_data.db.parameter_training_samples` | `ai_core.training_samples` | Типизация числовых полей `NUMERIC(18,8)`. |
| `used_training_parameters` | `ai_data.db.used_training_parameters` | `ai_core.training_parameters` | Хранить истории в отдельной таблице версий. |
| `best_params_per_symbol` | `ai_data.db.best_params_per_symbol` | `ai_core.best_params` | Добавить уникальный индекс `(tenant_id, symbol, timeframe)`. |
| `blocked_params` | `ai_data.db.blocked_params` | `ai_core.blocked_params` | Строгие enum типы для причин блокировки. |
| `win_rate_targets` | `ai_data.db.win_rate_targets` | `ai_core.win_rate_targets` | Использовать `NUMERIC(5,2)` для процентов. |
| `bots_state` | `bots_data.db.bots_state` | `bots_core.bots_state` | Присвоить `tenant_id`, `bot_uid`, `status`. |
| `bot_positions_registry` | `bots_data.db.bot_positions_registry` | `bots_core.positions` | Нормализовать связку `bot_id`/`symbol`. |
| `rsi_cache` | `bots_data.db.rsi_cache` | `bots_core.rsi_cache` | Рассмотреть хранение в `materialized view`. |
| `mature_coins` / `maturity_check_cache` | `bots_data.db.*` | `bots_core.maturity_cache` | Объединить логику на уровне SQL. |
| `process_state`, `bots_state.json` и др. | JSON/SQLite | `bots_core.process_state` + вспомогательные таблицы | Перевести статусы процессов и конфиги. |
| `license_generator` SQLite | `license_generator/license_data.db` | `supporting.licenses` | Выделить отдельный коннект, но использовать общие инструменты миграций. |
| Кэш свечей (`data/candles_cache.json`) | JSON | `ai_core.candles_cache_view` | Либо Redis/Postgres JSONB, решение TBD. |

## 5. Фазы работ и задачи

### Фаза 0 — Подготовка
- [ ] Хостинг PostgreSQL - on-prem и бэкапам.
- [ ] Добавить docker-compose профиль для `postgres + pgadmin + pgbouncer`.
- [ ] Обновить `requirements.txt` (SQLAlchemy, asyncpg, alembic, psycopg2-binary).

### Фаза 1 — Слой доступа и конфигурация
- [ ] Создать модуль `db/core.py` с фабрикой движков и пулом соединений.
- [ ] Вынести параметры подключения в `app/config.py` + `.env`.
- [ ] Внедрить SQLAlchemy модели для `ai_core` и `bots_core`.
- [ ] Добавить Alembic конфигурацию, автогенерацию миграций, скрипты `scripts/db_upgrade.py`, `scripts/db_downgrade.py`.

### Фаза 2 — Схемы и миграции
- [ ] Спроектировать `schema.sql` с таблицами/индексами, включая `tenant_id`, `created_at`, `updated_at`.
- [ ] Настроить RLS и роли (`infobot_app`, `infobot_admin`, `infobot_readonly`).
- [ ] Подготовить тестовые данные и сиды (минимальные справочники).

### Фаза 3 — Миграция данных
- [ ] Написать ETL-скрипт `scripts/migrate_sqlite_to_pg.py`:
  - чтение из SQLite (и JSON) батчами;
  - валидация схемы;
  - параллельная загрузка в PostgreSQL;
  - отчёт о расхождениях.
- [ ] Подготовить стратегию миграции лицензий (если требуется).
- [ ] Задокументировать процедуру бэкапа/rollback.

### Фаза 4 — Обновление кода
- [ ] `bot_engine/ai/ai_database.py`: заменить прямой `sqlite3` на DAL, адаптировать API.
- [ ] `bot_engine/bots_database.py`, `storage.py`, `bot_history.py`: переход на новые репозитории/ORM.
- [ ] `bots_modules/filters.py`, `bot_engine/trading_bot.py`: переписать запросы на SQLAlchemy, устранить зависимости от SQLite-специфики.
- [ ] Обновить сервисы резервного копирования/вакуума под PostgreSQL (VACUUM ANALYZE, logical backups).
- [ ] Пересмотреть лицензирование (`license_generator`) и вынести в отдельный DB-коннект.

### Фаза 5 — Тесты и эксплуатация
- [ ] Добавить интеграционные тесты с PostgreSQL (Docker service) в `tests/`.
- [ ] Обновить CI (GitHub Actions) для запуска `pytest` с поднятым Postgres.
- [ ] Написать пост-мортем чек-лист: миграция завершена, данные совпадают, мониторинг включен.

## 6. Документация и коммуникация

- Обновить `docs/AI_DATABASE_MIGRATION_GUIDE.md`, `INSTALL.md`, `README.md` — описать новые зависимости, переменные окружения, команды.
- Создать runbook `docs/POSTGRES_RUNBOOK.md` (после реализации) с инструкциями по бэкапам, мониторингу, проверке здоровья.
- В `docs/MIGRATION_SUMMARY.md` фиксировать прогресс по фазам.

## 7. Риски и меры

- **Несогласованность схемы**: использовать Alembic + code review для каждой миграции.
- **Потеря данных при ETL**: пошаговые бэкапы SQLite/JSON, dry-run ETL, контрольные суммы записей.
- **Производительность**: планировать индексы, рассмотреть партиционирование исторических таблиц (`candles_history`, `trades`).
- **Миграция лицензий**: согласовать приоритет, возможно оставить SQLite до отдельной итерации.

## 8. Следующие шаги

1. Утвердить план и схему.
2. Настроить окружение PostgreSQL и зависимости.
3. Реализовать слой доступа и первую миграцию схемы.
4. Подготовить ETL и выполнить пробную миграцию на тестовых данных.


