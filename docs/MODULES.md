# 📦 Описание модулей Bots Service

Подробное описание модулей после разбиения `bots.py` (актуально на 2026).

---

## 📊 Обзор модулей

| Модуль | Описание |
|--------|----------|
| `imports_and_globals.py` | Импорты, константы, Flask app, GlobalState |
| `calculations.py` | Расчеты RSI/EMA/trend |
| `maturity.py` | Зрелость монет (БД `bots_data.db`, JSON fallback) |
| `filters.py` | Фильтры, RSI, autobot, delisting cache |
| `bot_class.py` | Класс NewTradingBot |
| `sync_and_cache.py` | Кэш, синхронизация позиций, сохранение в БД |
| `workers.py` | Auto Save, Auto Bot, Smart RSI |
| `init_functions.py` | Инициализация сервиса |
| `api_endpoints.py` | REST API (включая `/api/bots/resume`) |
| `config_writer.py` | Запись конфига в `configs/bot_config.py` |
| `continuous_data_loader.py` | Непрерывное обновление RSI/зрелости |

> Optimal EMA Worker удалён из runtime. Персистентность ботов — `data/bots_data.db`, не `bots_state.json`.

---

## 1️⃣ imports_and_globals.py

### Назначение:
Базовый модуль с общими импортами, константами и глобальными переменными.

### Что содержит:

#### Импорты библиотек:
```python
import os, sys, signal, threading, time, logging, json, atexit
import asyncio, requests, socket, psutil
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import concurrent.futures
```

#### Константы RSI/EMA:
```python
RSI_OVERSOLD = 29      # Порог для LONG
RSI_OVERBOUGHT = 71    # Порог для SHORT
RSI_EXIT_LONG = 65     # Выход из LONG
RSI_EXIT_SHORT = 35    # Выход из SHORT

EMA_FAST = 50          # Быстрая EMA
EMA_SLOW = 200         # Медленная EMA
TREND_CONFIRMATION_BARS = 3
```

#### Константы интервалов:
```python
BOT_STATUS_UPDATE_INTERVAL = 30       # 30 сек
STOP_LOSS_SETUP_INTERVAL = 300        # 5 мин
POSITION_SYNC_INTERVAL = 30           # 30 сек
INACTIVE_BOT_CLEANUP_INTERVAL = 600   # 10 мин
```

#### Глобальные переменные:
```python
bots_data = {
    'bots': {},
    'auto_bot_config': {...},
    'global_stats': {...}
}

coins_rsi_data = {
    'coins': {},
    'last_update': None,
    'update_in_progress': False
}

bots_cache_data = {
    'bots': [],
    'account_info': {},
    'last_update': None
}
```

#### GlobalState для обмена данными:
```python
class GlobalState:
    exchange = None
    smart_rsi_manager = None
    async_processor = None
    system_initialized = False

def get_exchange():
    return _state.exchange

def set_exchange(exch):
    _state.exchange = exch
```

#### Блокировки (Locks):
```python
bots_data_lock = threading.Lock()
rsi_data_lock = threading.Lock()
bots_cache_lock = threading.Lock()
mature_coins_lock = threading.Lock()
```

#### Flask приложение:
```python
bots_app = Flask(__name__)
CORS(bots_app)
```

#### Функции:
- `check_and_stop_existing_bots_processes()` - проверка и освобождение порта 5001
- `should_log_message()` - подавление повторяющихся логов
- `load_auto_bot_config()` - загрузка конфигурации автобота
- `init_exchange()` - инициализация биржи
- `get_coin_processing_lock()` - получение блокировки для монеты

---

## 2️⃣ calculations.py

### Назначение:
Математические расчеты для технического анализа.

### Функции:

#### `calculate_rsi(prices, period=14)`
Расчет RSI по алгоритму Wilder's.

**Параметры:**
- `prices` - массив цен закрытия
- `period` - период RSI (по умолчанию 14)

**Возвращает:** `float` (0-100) или `None`

**Пример:**
```python
prices = [100, 102, 101, 103, 105, ...]
rsi = calculate_rsi(prices, 14)  # 52.3
```

#### `calculate_rsi_history(prices, period=14)`
Полная история RSI для всех свечей.

**Возвращает:** `list[float]` - массив RSI значений

**Использование:** Для проверки зрелости монет (нужна полная история)

#### `calculate_ema(prices, period)`
Расчет экспоненциальной скользящей средней.

**Алгоритм:**
1. SMA для первого значения
2. EMA = (Price × Multiplier) + (EMA_prev × (1 - Multiplier))
3. Multiplier = 2 / (period + 1)

#### `analyze_trend_6h(symbol, exchange_obj=None)`
Анализ тренда на таймфрейме 6H.

**Логика определения тренда:**

**UP trend** (все условия):
- Close > EMA_long
- EMA_short > EMA_long
- Наклон EMA_long > 0
- Минимум 3 закрытия подряд > EMA_long

**DOWN trend** (все условия):
- Close < EMA_long
- EMA_short < EMA_long
- Наклон EMA_long < 0
- Минимум 3 закрытия подряд < EMA_long

**NEUTRAL** - все остальное

**Возвращает:**
```python
{
    'trend': 'UP'|'DOWN'|'NEUTRAL',
    'ema_short': 50123.45,
    'ema_long': 49876.32,
    'current_close': 50200.00,
    'ema_long_slope': 5.67,
    'accuracy': 72.5  # из расчетного EMA-кэша
}
```

#### `perform_enhanced_rsi_analysis(candles, current_rsi, symbol)`
Расширенный анализ RSI с дополнительными индикаторами.

**Использует:**
- Stochastic RSI
- RSI дивергенция
- Подтверждение объемом
- Адаптивные уровни RSI
- Длительность в экстремальной зоне

**Возвращает:**
```python
{
    'enabled': True,
    'warning_type': 'OVERSOLD'|'OVERBOUGHT'|None,
    'warning_message': str,
    'extreme_duration': int,
    'adaptive_levels': [low, high],
    'confirmations': {
        'volume': bool,
        'divergence': bool,
        'stoch_rsi_k': float,
        'stoch_rsi_d': float
    },
    'enhanced_signal': 'LONG'|'SHORT'|'WAIT'
}
```

---

## 3️⃣ maturity.py

### Назначение:
Проверка зрелости монет для безопасной торговли.

### Критерии зрелости:

Монета считается **зрелой**, если:
1. ✅ Минимум 200 свечей 6H (≈50 дней истории)
2. ✅ RSI достигал значения ≤35 (был низ)
3. ✅ RSI достигал значения ≥65 (был верх)

**Зачем?** Чтобы не торговать новые/нестабильные монеты без достаточной истории.

### Функции:

#### `check_coin_maturity(symbol, candles)`
Проверяет зрелость монеты по свечам.

**Возвращает:**
```python
{
    'is_mature': True|False,
    'reason': 'Монета зрелая' | 'Недостаточно свечей',
    'details': {
        'candles_count': 250,
        'rsi_min': 28.5,
        'rsi_max': 72.3,
        'rsi_range': 43.8
    }
}
```

#### `check_coin_maturity_with_storage(symbol, candles)`
Проверка с использованием постоянного хранилища.

**Логика:**
1. Проверяет хранилище → если есть, возвращает True (кэш)
2. Если нет → полная проверка
3. Если зрелая → добавляет в хранилище

**Преимущество:** Не пересчитывает зрелость постоянно.

#### Хранилище зрелых монет:

**Файл:** `data/mature_coins.json`

**Структура:**
```json
{
  "BTC": {
    "timestamp": 1697328000,
    "maturity_data": {
      "is_mature": true,
      "rsi_min": 25.3,
      "rsi_max": 78.9
    },
    "last_verified": 1697414400
  }
}
```

#### Функции управления:
- `load_mature_coins_storage()` - загрузка из файла
- `save_mature_coins_storage()` - сохранение в файл
- `is_coin_mature_stored(symbol)` - проверка наличия
- `add_mature_coin_to_storage()` - добавление
- `remove_mature_coin_from_storage()` - удаление
- `update_mature_coin_verification()` - обновление времени

---

## 4️⃣ Исторический EMA модуль (удален)

### Назначение:
Управление оптимальными EMA периодами для каждой монеты.

### Концепция:

Вместо фиксированных EMA(50, 200) для всех монет, система использует **индивидуальные** периоды, подобранные для каждой монеты.

### Функции:

Исторический EMA-модуль удален и больше не используется в runtime.

**Возвращает:**
```python
{
    'ema_short': 45,      # Может быть 30-100
    'ema_long': 180,      # Может быть 150-300
    'accuracy': 75.5,     # Точность в %
    'long_signals': 12,   # Успешных LONG
    'short_signals': 8,   # Успешных SHORT
    'analysis_method': 'optimized'
}
```

**По умолчанию** (если нет данных): `{ema_short: 50, ema_long: 200}`

Данные и воркеры этого модуля удалены.

**Структура:**
```json
{
  "BTC": {
    "ema_short_period": 45,
    "ema_long_period": 185,
    "accuracy": 78.9,
    "long_signals": 15,
    "short_signals": 12,
    "analysis_method": "historical_backtest"
  }
}
```

---

## 5️⃣ filters.py (1207 строк)

### Назначение:
Фильтры торговых сигналов и загрузка RSI данных.

### Ключевые функции:

#### `check_rsi_time_filter(candles, rsi, signal)`
**Гибридный временной фильтр RSI**

**⚠️ ВАЖНО:** Эта функция вызывается ТОЛЬКО при входе в позицию в `_enter_position()` через `apply_entry_filters()`, а НЕ в `get_coin_rsi_data()` для всех монет!

**Логика для SHORT:**
1. Ищет последний пик RSI ≥71
2. Проверяет что после пика все свечи ≥65 (спокойная зона)
3. Проверяет что прошло минимум N свечей (по умолчанию 4)
4. Если есть провалы <65 → **блокирует вход** (момент упущен)

**Логика для LONG:** Зеркальная (лой ≤29, спокойная зона ≤35)

**Возвращает:**
```python
{
    'allowed': True|False,
    'reason': 'Разрешено: с пика прошло 8 свечей',
    'last_extreme_candles_ago': 8,
    'calm_candles': 8
}
```

#### `check_exit_scam_filter(symbol, coin_data)`
Фильтр против exit scam / памп-дамп схем.

**⚠️ ВАЖНО:** Эта функция вызывается ТОЛЬКО при входе в позицию в `_enter_position()` через `apply_entry_filters()`, а НЕ в `get_coin_rsi_data()` для всех монет!

**Проверяет:**
- Резкий рост объема (>500% за короткое время)
- Резкий рост цены (>100% за 24ч)
- Аномальная волатильность
- 🤖 AI Anomaly Detection (если включен) - внутри этого фильтра

#### `check_no_existing_position(symbol, signal)`
Проверяет отсутствие существующей позиции.

**Зачем?** Чтобы не открыть 2 позиции на одну монету.

#### `load_all_coins_rsi(exchange_obj=None)`
**Ключевая функция!** Загружает RSI для всех 583 торговых пар.

**Алгоритм:**
1. Получает список пар с биржи
2. Разбивает на пакеты по 50 монет
3. Параллельно обрабатывает (3 воркера)
4. Для каждой монеты (`get_coin_rsi_data()`):
   - Загружает свечи 6H за 30 дней
   - Расчитывает RSI(14)
   - Анализирует тренд
   - Проверяет зрелость (для UI, НЕ блокирует)
   - Расширенный RSI анализ
   - ⚠️ ExitScam и RSI Time Filter НЕ проверяются здесь!
5. Инкрементально обновляет `coins_rsi_data`
6. Сохраняет кэш

**Время выполнения:** ~2-3 минуты для 583 монет

**Оптимизация:** Блокирующие фильтры (ExitScam, RSI Time Filter) проверяются только при входе в позицию в `_enter_position()`, что значительно улучшает производительность.

#### `get_effective_signal(coin)`
Определяет итоговый торговый сигнал.

**Логика:**
```python
if rsi <= 29: return 'ENTER_LONG'
elif rsi >= 71: return 'ENTER_SHORT'
elif rsi >= 65 and in_long: return 'EXIT_LONG'
elif rsi <= 35 and in_short: return 'EXIT_SHORT'
else: return 'WAIT'
```

#### `process_auto_bot_signals(exchange_obj=None)`
Обрабатывает сигналы для автоматического создания ботов.

**Алгоритм:**
1. Проверяет `enabled` статус
2. Проверяет лимит `max_concurrent`
3. Для каждой монеты с сигналом:
   - Проверяет отсутствие существующей позиции ✓
   - Создает бота (фильтры проверятся в `_enter_position()`)
4. **Все блокирующие фильтры проверяются в `_enter_position()`** через `apply_entry_filters()`:
   - Global switches
   - Scope (whitelist/blacklist)
   - Trend (avoid_down_trend/avoid_up_trend)
   - Maturity (enable_maturity_check)
   - RSI Time Filter (rsi_time_filter_enabled)
   - ExitScam (exit_scam_enabled)
   - 🤖 AI Anomaly Detection (внутри ExitScam)
   - 🤖 AI Optimal Entry Detection
   - 🤖 AI Risk Management (размер позиции и стоп-лосс)

---

## 6️⃣ bot_class.py

### Назначение:
Класс `NewTradingBot` - ядро торговой логики.

### Класс NewTradingBot:

#### Атрибуты:
```python
self.symbol = 'BTC'
self.status = 'idle' | 'running' | 'armed_up' | 'in_position_long' | ...
self.entry_price = 50000.0
self.position_side = 'Buy' | 'Sell'
self.unrealized_pnl = 125.50
self.max_profit_achieved = 200.00
self.trailing_stop_price = 51000.0
self.break_even_activated = False
```

#### Методы:

**`update(force_analysis=False, external_signal=None)`** - главный метод обновления

**`should_open_long(rsi, trend, candles)`** - проверка открытия LONG
- Проверяет RSI ≤29
- Проверяет тренд (избегает DOWN)
- Проверяет RSI time filter

**`should_open_short(rsi, trend, candles)`** - проверка открытия SHORT  
- Проверяет RSI ≥71
- Проверяет тренд (избегает UP)
- Проверяет RSI time filter

**`should_close_long(rsi, current_price)`** - проверка закрытия LONG
- Проверяет RSI ≥65
- Проверяет стоп-лосс
- Проверяет trailing stop

**`should_close_short(rsi, current_price)`** - проверка закрытия SHORT
- Проверяет RSI ≤35
- Проверяет стоп-лосс
- Проверяет trailing stop

---

## 7️⃣ sync_and_cache.py (1750 строк)

### Назначение:
Кэширование, синхронизация с биржей, управление состоянием.

### Группы функций:

#### А. Кэш RSI:
- `get_rsi_cache()` - получить кэшированные RSI
- `save_rsi_cache()` - сохранить в файл
- `load_rsi_cache()` - загрузить из файла

#### Б. Конфигурация:
- `save_default_config()` - сохранить дефолтную
- `load_default_config()` - загрузить дефолтную
- `restore_default_config()` - восстановить к дефолту

#### В. Состояние процессов:
- `update_process_state(process_name, status_update)` - обновить статус
- `save_process_state()` - сохранить в файл
- `load_process_state()` - загрузить из файла

#### Г. Системная конфигурация:
- `save_system_config(config_data)` - сохранить настройки
- `load_system_config()` - загрузить настройки

#### Д. Состояние ботов:
- `save_bots_state()` - сохранить всех ботов
- `load_bots_state()` - загрузить всех ботов
- `save_auto_bot_config()` - сохранить настройки автобота

#### Е. Синхронизация:
- `update_bots_cache_data()` - обновить кэш (каждые 30 сек)
- `update_bot_positions_status()` - обновить статус позиций
- `get_exchange_positions()` - получить позиции с биржи
- `sync_positions_with_exchange()` - умная синхронизация
- `check_missing_stop_losses()` - установить недостающие SL
- `cleanup_inactive_bots()` - удалить неактивные боты

---

## 8️⃣ workers.py

### Назначение:
Фоновые воркеры для автоматических задач.

### Воркеры:

#### `auto_save_worker()`
**Автосохранение состояния**

- Интервал: каждые 30 секунд (SystemConfig.AUTO_SAVE_INTERVAL)
- Сохраняет:
  - `bots_state.json`
  - `mature_coins.json`
- Атомарная запись с retry
- Логирует раз в 5 минут (подавление спама)

#### `auto_bot_worker()`
**Проверка Auto Bot сигналов**

**Логика:**
1. При запуске: принудительно выключает автобот
2. Логирует: "Автобот выключен, включите вручную"
3. Входит в цикл:
   ```python
   while not shutdown_flag:
       if auto_bot_enabled:
           process_auto_bot_signals()  # Создание ботов
       
       update_bots_cache_data()        # Каждые 30 сек
       check_missing_stop_losses()      # Каждые 5 мин
       cleanup_inactive_bots()          # Каждые 10 мин
   ```

**Интервалы:**
- Проверка сигналов: настраиваемая (по умолчанию 60 сек)
- Обновление кэша: 30 сек
- Стоп-лоссы: 5 мин
- Очистка: 10 мин

---

## 9️⃣ init_functions.py

### Назначение:
Инициализация всех компонентов системы.

### Ключевая функция: `init_bot_service()`

**Порядок инициализации (критически важен!):**

```python
1. Загрузка хранилища зрелых монет
2. Загрузка optimal EMA данных
3. Создание дефолтной конфигурации
4. Загрузка системных настроек
5. Загрузка состояния процессов
6. Загрузка состояния ботов

7. ⚡ ИНИЦИАЛИЗАЦИЯ БИРЖИ (init_exchange_sync)
   ├─ ExchangeFactory.create_exchange('BYBIT')
   ├─ set_exchange(new_exchange)  # GlobalState
   └─ Тест подключения

8. Запуск Smart RSI Manager
   └─ Обновление RSI каждые 5 минут

9. Синхронизация с биржей
10. Проверка конфликтов позиций
11. Запуск async processor
12. system_initialized = True ✅
```

**Почему биржа первая?** Все остальные компоненты используют `exchange`!

### Другие функции:

#### `init_exchange_sync()`
Синхронная инициализация биржи с retry логикой.

#### `ensure_exchange_initialized()`
Проверяет что биржа готова к использованию.

#### `create_bot(symbol, config, exchange_obj)`
Создает нового бота.

#### `process_trading_signals_on_candle_close(candle_timestamp, exchange_obj)`
Обрабатывает сигналы при закрытии свечи 6H.

---

## 🔟 api_endpoints.py (2620 строк, 60+ endpoints)

### Назначение:
Все Flask API endpoints для управления системой.

### Категории endpoints:

#### Здоровье и статус:
- `GET /health` - проверка работоспособности
- `GET /api/status` - статус сервиса
- `GET /api/bots/async-status` - статус async processor

#### Управление ботами:
- `GET /api/bots` - список всех ботов
- `POST /api/bots/create` - создать бота
- `POST /api/bots/<id>/start` - запустить
- `POST /api/bots/<id>/stop` - остановить
- `POST /api/bots/<id>/pause` - пауза
- `DELETE /api/bots/<id>` - удалить

#### Позиции:
- `POST /api/positions/refresh` - обновить позиции
- `POST /api/positions/close` - закрыть позицию

#### Конфигурация:
- `GET/POST /api/bots/system-config` - системные настройки
- `GET/POST /api/auto-bot/config` - настройки автобота
- `POST /api/auto-bot/restore-defaults` - восстановить дефолт

#### RSI и данные:
- `GET /api/coins-with-rsi` - монеты с RSI данными
- `POST /api/smart-rsi/force-update` - принудительное обновление
- `POST /api/refresh-rsi/<symbol>` - обновить для одной монеты

#### Зрелые монеты:
- `GET /api/mature-coins` - список зрелых
- `POST /api/mature-coins/remove` - удалить из списка
- `POST /api/mature-coins/reload` - перезагрузить
- `POST /api/mature-coins/clear` - очистить все

#### Optimal EMA:
- `GET /api/optimal-ema` - все данные
- `GET /api/optimal-ema/<symbol>` - для монеты
- `POST /api/optimal-ema/rescan/<symbol>` - пересканировать

#### Сервисные:
- `POST /api/sync-positions` - синхронизация
- `POST /api/cleanup-inactive` - очистка
- `POST /api/reload-modules` - перезагрузка модулей
- `POST /api/restart-service` - рестарт

#### Тестирование:
- `GET /api/test/exit-scam/<symbol>` - тест exit scam фильтра
- `GET /api/test/rsi-time-filter/<symbol>` - тест RSI time filter

**Полный список:** [API_REFERENCE.md](API_REFERENCE.md)

---

## 🔄 Как модули импортируют друг друга

### Правило импорта через `from module import *`:

```python
# bots.py
from bots_modules.imports_and_globals import *
from bots_modules.calculations import *
from bots_modules.filters import *
# ...
```

Все функции доступны **как в едином файле**!

### Внутри модулей - явные импорты:

```python
# filters.py
from bots_modules.calculations import calculate_rsi
from bots_modules.maturity import check_coin_maturity
from bots_modules.imports_and_globals import RSI_OVERSOLD
```

**Преимущество:** Понятно откуда берется каждая функция.

---

## 📝 Следующие шаги

- **Настройка:** [CONFIGURATION.md](CONFIGURATION.md)
- **API:** [API_REFERENCE.md](API_REFERENCE.md)
- **Разработка:** [DEVELOPMENT.md](DEVELOPMENT.md)

