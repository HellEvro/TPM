# System Overview — InfoBot 1.7

**Дата:** 14 ноября 2025  
**Назначение:** Один документ, который объясняет, как устроена не‑AI часть InfoBot: сервисы, потоки данных, конфигурация, история, лицензирование и мониторинг.

---

## 1. Топология сервисов

| Компонент | Порт / Файл | Что делает |
| --- | --- | --- |
| Web UI | `app.py` (порт 5000) | Панель управления, страница «Боты», настройки и статусы. |
| Bots Service | `bots.py` (порт 5001) + `bots_modules/*` | REST API, обработка сигналов, автосоздание/управление ботами. |
| AI Launcher | `ai.py` (см. `docs/AI_README.md`) | Сбор данных, обучение моделей, Smart Risk, лицензирование, самообучение в реальном времени. |
| Launcher GUI | `start_infobot_manager.*` | Устанавливает зависимости, запускает сервисы, проверяет лицензии. |
| InfoBot_Public | `scripts/sync_to_public.py` | Собирает релизный пакет с необходимыми скриптами и защищёнными файлами. |

> Детальное описание модулей и зависимостей — в `docs/ARCHITECTURE.md` и `docs/MODULES.md`.

---

## 2. Жизненный цикл сигналов (кратко)

1. `SmartRSIManager` в `bots_modules/workers.py` обновляет RSI и кеширует монеты.  
2. `bots_modules/filters.py` в `get_coin_rsi_data()` проверяет зрелость монет (для UI, НЕ блокирует).  
3. Auto Bot (если включён) вызывает `process_auto_bot_signals()` и создаёт ботов через `bots_modules/bot_class.py`.  
4. **При входе в позицию** (`bot_engine/trading_bot.py::_enter_position()`): единая проверка `check_entry_allowed()` (пороги RSI + `apply_entry_filters()`), в т.ч. для autobot (`force_market_entry`):
   - Пороги RSI (LONG ≤ порог, SHORT ≥ порог), Global switches, Scope, Trend, Maturity, RSI Time Filter, ExitScam
   - 🤖 AI Anomaly Detection (внутри ExitScam)
   - 🤖 AI Optimal Entry Detection
   - 🤖 AI Risk Management (размер позиции и стоп-лосс)
5. **После закрытия позиции**: AISelfLearning автоматически обучается на результате для улучшения будущих решений
5. Статусы и действия пишутся в `bots_data` (в памяти) и SQLite `data/bots_data.db` (таблица `bots_state`, autosave ~30 с).  
6. История сделок/действий уходит в `bot_engine/bot_history.py` → REST `/api/bots/history|trades|statistics`. Подробности — `docs/BOT_SIGNAL_PROCESSING_FLOW.md` и `docs/BOT_HISTORY.md`.

**⚠️ ВАЖНО:** ExitScam и RSI Time Filter НЕ проверяются в `get_coin_rsi_data()` для всех монет. Они проверяются только при входе в позицию для оптимизации производительности.

---

## 3. Поток конфигурации (UI → backend → файл)

1. **UI** (`static/js/managers/bots_manager.js`): `collectConfigurationData()` собирает значения формы и сравнивает их с `originalConfig`.  
2. **API** (`bots_modules/api_endpoints.py` → `POST /api/bots/auto-bot`): принимает только изменённые поля, обновляет `bots_data['auto_bot_config']`.  
3. **Сохранение** (`bots_modules/sync_and_cache.py::save_auto_bot_config`): выносит конфиг в отдельный поток, вызывает `config_writer.save_auto_bot_config_to_py`.  
4. **Файл** (`bot_engine/bot_config.py`): блок `DEFAULT_AUTO_BOT_CONFIG` перезаписывается, затем модуль принудительно перезагружается.  
5. **Перезагрузка UI**: `bots_manager.js` перезагружает конфиг через API и обновляет DOM.

Ключевые артефакты: `bots_data`, `data/bots_data.db`, `configs/bot_config.py` (экспорт UI). Этот раздел полностью покрывает информацию из старого `CONFIG_DATA_FLOW.md`.

---

## 4. Состояние и данные

| Файл / директория | Что хранит | Когда обновляется |
| --- | --- | --- |
| `data/bots_data.db` | Боты, RSI cache, mature coins, process_state, delisted | Auto Save worker (~30 с) |
| `data/mature_coins.json` | Fallback при сбое записи в БД (не основной путь) | редко |
| `data/ema_legacy_removed.json` | Исторический артефакт (удален из runtime) | не используется |
| `data/bot_history.json` | История действий, сделок и статистика | при каждом событии в `bot_engine/bot_history.py` |
| `logs/*.log` | `bots.log`, `ai.log`, `app.log` | непрерывно |

> Управление логами — `docs/LOG_ROTATION.md`. История и API — `docs/BOT_HISTORY.md`.

---

## 5. Лицензии, whitelist/blacklist, защита

- **HWID лицензия:** `scripts/activate_premium.py` → `.lic` в корне. Проверка в `bot_engine/ai/license_checker.pyc`. Подробности — `docs/PREMIUM_STOP_ANALYSIS_ARCHITECTURE.md`, `docs/ML_MODELS_DISTRIBUTION.md`, `docs/HWID_FIX_REPORT.md`.  
- **Whitelist / blacklist монет:** `docs/WHITELIST_BLACKLIST.md` описывает формат файлов и UI.  
- **Stop/Risk premium:** Smart Risk доступен только при валидной лицензии (см. `docs/AI_README.md`).  
- **Release sync:** `scripts/sync_to_public.py` исключает приватные каталоги (`license_generator`, `docs/ai_*`, backups) и собирает обязательные файлы (`README`, `start_infobot_manager.*`, `InfoBot_Public/bot_engine/ai/*.pyc`). 

---

## 6. Мониторинг и эксплуатация

- **Статусы:**  
  - `GET /api/status` — сервисы ботов;  
  - `GET /api/bots/history|trades|statistics` — история;  
  - `GET /api/ai/status` — AI/лицензия.  
- **CLI/скрипты:** `scripts/verify_ai_ready.py`, `scripts/test_full_ai_system.py`, `scripts/test_hwid_check.py`.  
- **Логи:** `logs/bots.log` (фильтруйте по `AI` или `AutoBot`), `logs/ai.log`, `logs/app.log`.  
- **GUI:** `start_infobot_manager` показывает прогресс шагов, статусы сервисов и быстрый запуск скриптов.

---

## 7. Что читать дальше

| Тема | Документы |
| --- | --- |
| Глубокая архитектура | `docs/ARCHITECTURE.md`, `docs/MODULES.md` |
| Сигналы и фильтры | `docs/BOT_SIGNAL_PROCESSING_FLOW.md`, `docs/WHITELIST_BLACKLIST.md` |
| История/отчётность | `docs/BOT_HISTORY.md`, `docs/READY_FOR_YOU.md` |
| Установка и запуск | `docs/START_HERE.md`, `docs/QUICKSTART.md`, `docs/INSTALL.md` |
| AI и премиальные модули | `docs/AI_README.md`, `docs/AI_UI_CONFIGURATION.md`, `docs/PREMIUM_STOP_ANALYSIS_ARCHITECTURE.md`, `docs/AI_SELF_LEARNING_SYSTEM.md` |
| Будущие задачи | `docs/FUTURE_FEATURES.md`, `docs/Bots_TZ.md` (оригинальное ТЗ) |

---

**TL;DR:** `app.py` обслуживает UI, `bots.py` отдаёт API и управляет ботами, `ai.py` обеспечивает AI и лицензии; конфиги идут из UI прямо в `bot_engine/bot_config.py`, история и логи сохраняются в `data/*` и `logs/*`. Этот документ заменяет разрозненные `CONFIG_DATA_FLOW.md`, `HOW_IT_WORKS.md` и подобные описания потока данных.

