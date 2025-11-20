# Руководство по миграции на SQLite БД

**Важно:** Это руководство описывает миграцию AI модуля (файлы в `data/ai/`). Для миграции bots модуля (`bots.py`) используйте раздел "Миграция других модулей".

### ⚠️ Ключевое различие

- **AI модуль:** Файлы в `data/ai/` → БД `data/ai/ai_data.db` ✅ **Уже мигрировано**
- **Bots модуль:** Файлы в `data/` (не в `data/ai/`) → Требует миграции ⏳
  - `data/bots_state.json` - состояние ботов
  - `data/bot_history.json` - история действий и сделок
  - `data/rsi_cache.json` - кэш RSI данных
  - И другие файлы в `data/`

**Bots.py НЕ читает файлы из `data/ai/`** - это отдельная папка только для AI модуля!

## 📋 Содержание

1. [Обзор](#обзор)
2. [Архитектура БД](#архитектура-бд)
3. [Структура таблиц](#структура-таблиц)
4. [Работа с AIDatabase](#работа-с-aidatabase)
5. [Миграция данных](#миграция-данных)
6. [Примеры использования](#примеры-использования)
7. [Best Practices](#best-practices)
8. [Миграция других модулей](#миграция-других-модулей)
9. [Улучшения и защита данных](#улучшения-и-защита-данных)

---

## Обзор

### Зачем нужна БД?

**Проблемы JSON файлов:**
- ❌ Ограничение размера (50,000+ записей = проблемы)
- ❌ Медленные операции поиска
- ❌ Невозможность делать JOIN запросы
- ❌ Проблемы с параллельным доступом
- ❌ Нет индексов для быстрого поиска
- ❌ Сложность анализа больших объемов данных

**Преимущества SQLite БД:**
- ✅ Хранит миллиарды записей
- ✅ Быстрый поиск по индексам
- ✅ JOIN запросы между таблицами
- ✅ WAL режим для параллельных чтений/записей
- ✅ Атомарные операции
- ✅ Поддержка UNC путей (сетевые диски)
- ✅ Автоматическая миграция схемы

### Что было мигрировано (только AI модуль)

**Важно:** Мигрированы только файлы AI модуля из `data/ai/`. Bots модуль (`bots.py`) использует свои собственные файлы в `data/` (не в `data/ai/`) и они пока не мигрированы.

| Файл (data/ai/) | Таблица БД | Статус |
|----------------|-----------|--------|
| `simulated_trades.json` | `simulated_trades` | ✅ Полностью мигрировано |
| `bot_trades.json` | `bot_trades` | ✅ Полностью мигрировано |
| `exchange_trades.json` | `exchange_trades` | ✅ Полностью мигрировано |
| `candles_full_history.json` | `candles_history` | ✅ Полностью мигрировано |
| `bots_data.json` | `bots_data_snapshots` | ✅ Полностью мигрировано |
| `parameter_training_data.json` | `parameter_training_samples` | ✅ Полностью мигрировано |
| `used_training_parameters.json` | `used_training_parameters` | ✅ Полностью мигрировано |
| `best_params_per_symbol.json` | `best_params_per_symbol` | ✅ Полностью мигрировано |
| `blocked_params.json` | `blocked_params` | ✅ Полностью мигрировано |
| `win_rate_targets.json` | `win_rate_targets` | ✅ Полностью мигрировано |

### Файлы bots.py (еще не мигрированы)

Bots модуль использует свои собственные файлы в `data/` (не в `data/ai/`):

| Файл (data/) | Назначение | Статус |
|-------------|-----------|--------|
| `bots_state.json` | Состояние всех ботов | ⏳ Требует миграции |
| `bot_history.json` | История действий и сделок ботов | ⏳ Требует миграции |
| `rsi_cache.json` | Кэш RSI данных | ⏳ Требует миграции |
| `mature_coins.json` | Зрелые монеты | ⏳ Требует миграции |
| `process_state.json` | Состояние процессов | ⏳ Требует миграции |
| `system_config.json` | Системные настройки | ⏳ Требует миграции |
| `individual_coin_settings.json` | Индивидуальные настройки монет | ⏳ Требует миграции |

**Примечание:** `bots_data.json` в `data/ai/` - это снимки данных ботов, собираемые AI модулем для обучения. Это НЕ то же самое, что `bots_state.json` в `data/`, который используется самим `bots.py`.

---

## Архитектура БД

### Расположение

**Путь по умолчанию:**
```
data/ai/ai_data.db
```

**Поддержка UNC путей:**
```python
# Работает с сетевыми путями
\\Evromini\projects\InfoBot\data\ai\ai_data.db
```

### Инициализация

БД создается автоматически при первом обращении:

```python
from bot_engine.ai.ai_database import get_ai_database

# Получаем глобальный экземпляр (singleton)
ai_db = get_ai_database()

# Или с кастомным путем
ai_db = get_ai_database(db_path='custom/path/ai_data.db')
```

### Настройки производительности

БД автоматически настраивается для оптимальной производительности:

```sql
PRAGMA journal_mode=WAL;        -- Write-Ahead Logging для параллельных операций
PRAGMA synchronous=NORMAL;       -- Баланс между скоростью и надежностью
PRAGMA cache_size=-64000;        -- 64MB кеш
PRAGMA temp_store=MEMORY;        -- Временные таблицы в памяти
```

### WAL режим

**Преимущества:**
- ✅ Читатели не блокируют писателей
- ✅ Писатели не блокируют читателей
- ✅ Параллельная работа нескольких процессов
- ✅ Быстрые операции записи

**Как работает:**
- Чтения идут из основного файла БД
- Записи идут в WAL файл (`ai_data.db-wal`)
- Периодически WAL применяется к основному файлу

---

## Структура таблиц

### 1. Сделки и торговля

#### `simulated_trades` - AI симуляции
```sql
CREATE TABLE simulated_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,              -- 'LONG' или 'SHORT'
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    entry_time INTEGER NOT NULL,          -- Unix timestamp
    exit_time INTEGER NOT NULL,
    entry_rsi REAL,
    exit_rsi REAL,
    entry_trend TEXT,                     -- 'UP', 'DOWN', 'NEUTRAL'
    exit_trend TEXT,
    pnl REAL NOT NULL,
    pnl_pct REAL NOT NULL,
    exit_reason TEXT,
    is_successful INTEGER DEFAULT 0,      -- 0 или 1
    training_session_id INTEGER,
    rsi_params_json TEXT,                 -- JSON с параметрами RSI
    risk_params_json TEXT,                -- JSON с риск-параметрами
    config_params_json TEXT,              -- JSON с конфигурацией
    created_at TEXT NOT NULL,
    FOREIGN KEY (training_session_id) REFERENCES training_sessions(id)
)
```

**Индексы:**
- `idx_simulated_symbol` - по символу
- `idx_simulated_time` - по времени входа
- `idx_simulated_session` - по сессии обучения

#### `bot_trades` - Реальные сделки ботов
```sql
CREATE TABLE bot_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    entry_time INTEGER NOT NULL,
    exit_time INTEGER,
    pnl REAL,
    pnl_pct REAL,
    is_simulated INTEGER DEFAULT 0,       -- 0 = реальная, 1 = симуляция
    bot_id TEXT,
    config_json TEXT,                     -- JSON с конфигурацией бота
    created_at TEXT NOT NULL
)
```

#### `exchange_trades` - История биржи
```sql
CREATE TABLE exchange_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    trade_time INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
```

### 2. Свечи и рыночные данные

#### `candles_history` - История свечей
```sql
CREATE TABLE candles_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL DEFAULT '6h',
    candle_time INTEGER NOT NULL,          -- Unix timestamp
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    volume REAL NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(symbol, timeframe, candle_time)
)
```

**Индексы:**
- `idx_candles_symbol` - по символу
- `idx_candles_time` - по времени
- `idx_candles_symbol_time` - составной индекс

**Особенности:**
- UNIQUE constraint предотвращает дубликаты
- Поддержка разных таймфреймов (по умолчанию '6h')
- Быстрый поиск по символу и времени

### 3. Обучение и параметры

#### `training_sessions` - Сессии обучения
```sql
CREATE TABLE training_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_type TEXT NOT NULL,            -- 'historical', 'simulated', 'real'
    start_time TEXT NOT NULL,
    end_time TEXT,
    symbols_count INTEGER,
    trades_count INTEGER,
    config_json TEXT,
    created_at TEXT NOT NULL
)
```

#### `parameter_training_samples` - Образцы для обучения ML
```sql
CREATE TABLE parameter_training_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rsi_params_json TEXT NOT NULL,
    risk_params_json TEXT,
    win_rate REAL NOT NULL,
    total_pnl REAL NOT NULL,
    trades_count INTEGER NOT NULL,
    quality REAL NOT NULL,
    blocked INTEGER DEFAULT 0,
    symbol TEXT,
    created_at TEXT NOT NULL
)
```

#### `used_training_parameters` - Использованные параметры
```sql
CREATE TABLE used_training_parameters (
    param_hash TEXT PRIMARY KEY,           -- MD5 хеш параметров
    rsi_params_json TEXT NOT NULL,
    training_seed INTEGER,
    win_rate REAL,
    total_pnl REAL,
    signal_accuracy REAL,
    trades_count INTEGER,
    rating REAL,
    symbol TEXT,
    used_at TEXT NOT NULL,
    update_count INTEGER DEFAULT 0
)
```

**Особенности:**
- `param_hash` - уникальный идентификатор комбинации параметров
- `update_count` - счетчик обновлений (для отслеживания популярности)
- `INSERT OR REPLACE` для атомарных обновлений

#### `best_params_per_symbol` - Лучшие параметры по символам
```sql
CREATE TABLE best_params_per_symbol (
    symbol TEXT PRIMARY KEY,
    rsi_params_json TEXT NOT NULL,
    risk_params_json TEXT,
    win_rate REAL NOT NULL,
    total_pnl REAL NOT NULL,
    trades_count INTEGER NOT NULL,
    rating REAL NOT NULL,
    updated_at TEXT NOT NULL
)
```

#### `blocked_params` - Заблокированные параметры
```sql
CREATE TABLE blocked_params (
    param_hash TEXT PRIMARY KEY,
    rsi_params_json TEXT NOT NULL,
    block_reasons_json TEXT,               -- JSON с причинами блокировки
    blocked_at TEXT NOT NULL
)
```

#### `win_rate_targets` - Целевые значения Win Rate
```sql
CREATE TABLE win_rate_targets (
    symbol TEXT PRIMARY KEY,
    target_win_rate REAL NOT NULL,
    current_win_rate REAL,
    updated_at TEXT NOT NULL
)
```

### 4. Координация и снимки

#### `training_locks` - Блокировки для параллельной работы
```sql
CREATE TABLE training_locks (
    symbol TEXT PRIMARY KEY,
    process_id TEXT NOT NULL,              -- hostname-PID-timestamp
    hostname TEXT NOT NULL,
    locked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL               -- Автоматическое истечение
)
```

**Использование:**
- Координация параллельной работы на разных ПК
- Автоматическое истечение блокировок (120 минут)
- Предотвращение обработки одного символа несколькими процессами

#### `bots_data_snapshots` - Снимки данных ботов
```sql
CREATE TABLE bots_data_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TEXT NOT NULL,           -- ISO timestamp
    bots_json TEXT,                        -- JSON массив ботов
    rsi_data_json TEXT,                    -- JSON RSI данных
    signals_json TEXT,                     -- JSON сигналов
    bots_status_json TEXT,                 -- JSON статуса ботов
    created_at TEXT NOT NULL
)
```

**Индексы:**
- `idx_bots_snapshots_time` - по времени снимка
- `idx_bots_snapshots_created` - по времени создания

---

## Работа с AIDatabase

### Базовое использование

```python
from bot_engine.ai.ai_database import get_ai_database

# Получаем экземпляр БД
db = get_ai_database()

# Сохраняем симуляцию
db.save_simulated_trade({
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'entry_price': 50000.0,
    'exit_price': 51000.0,
    'entry_time': 1234567890,
    'exit_time': 1234567891,
    'pnl': 1000.0,
    'pnl_pct': 2.0,
    # ... остальные поля
})

# Получаем сделки
trades = db.get_simulated_trades(
    symbol='BTCUSDT',
    limit=100,
    start_time=1234567890,
    end_time=1234567900
)

# Подсчитываем
count = db.count_simulated_trades(symbol='BTCUSDT')
```

### Сохранение данных

#### Свечи

```python
# Одна монета
candles = [
    {'time': 1234567890, 'open': 50000, 'high': 51000, 'low': 49000, 'close': 50500, 'volume': 1000},
    {'time': 1234567891, 'open': 50500, 'high': 51500, 'low': 50000, 'close': 51000, 'volume': 1200},
]
saved = db.save_candles('BTCUSDT', candles, timeframe='6h')

# Несколько монет (батч)
candles_data = {
    'BTCUSDT': candles_btc,
    'ETHUSDT': candles_eth,
}
results = db.save_candles_batch(candles_data, timeframe='6h')
```

#### Снимки данных ботов

```python
snapshot = {
    'timestamp': '2024-01-01T12:00:00',
    'bots': [...],
    'rsi_data': {...},
    'signals': {...},
    'bots_status': {...}
}
snapshot_id = db.save_bots_data_snapshot(snapshot)
```

### Получение данных

#### Свечи

```python
# Все свечи для символа
candles = db.get_candles('BTCUSDT', timeframe='6h')

# С фильтрами
candles = db.get_candles(
    symbol='BTCUSDT',
    timeframe='6h',
    limit=100,
    start_time=1234567890,
    end_time=1234567900
)

# Все свечи для всех символов
all_candles = db.get_all_candles_dict(timeframe='6h')
# Возвращает: {'BTCUSDT': [candles], 'ETHUSDT': [candles], ...}

# Время последней свечи
last_time = db.get_candles_last_time('BTCUSDT', timeframe='6h')
```

#### Снимки данных ботов

```python
# Последний снимок
latest = db.get_latest_bots_data()

# Несколько снимков
snapshots = db.get_bots_data_snapshots(
    limit=1000,
    start_time='2024-01-01T00:00:00',
    end_time='2024-01-02T00:00:00'
)
```

### Параметры обучения

```python
# Сохранить использованные параметры
db.save_used_training_parameter(
    rsi_params={'oversold': 30, 'overbought': 70},
    training_seed=12345,
    win_rate=0.65,
    total_pnl=1000.0,
    symbol='BTCUSDT'
)

# Проверить использованы ли параметры
is_used = db.get_used_training_parameter(param_hash='abc123')

# Получить лучшие параметры для символа
best = db.get_best_params_for_symbol('BTCUSDT')

# Сохранить заблокированные параметры
db.save_blocked_params(
    rsi_params={'oversold': 20, 'overbought': 80},
    block_reasons=['Too aggressive', 'Low win rate']
)
```

### Координация параллельной работы

```python
import socket
import os
import time

# Генерируем уникальный ID процесса
hostname = socket.gethostname()
process_id = f"{hostname}-{os.getpid()}-{int(time.time())}"

# Пытаемся заблокировать символ
if db.try_lock_symbol('BTCUSDT', process_id, hostname, lock_duration_minutes=120):
    try:
        # Обрабатываем символ
        process_symbol('BTCUSDT')
    finally:
        # Освобождаем блокировку
        db.release_lock('BTCUSDT', process_id)

# Получить доступные символы (не заблокированные)
available = db.get_available_symbols(all_symbols, process_id, hostname)
```

### Статистика

```python
stats = db.get_database_stats()
# Возвращает:
# {
#     'simulated_trades_count': 1000000,
#     'bot_trades_count': 50000,
#     'candles_history_count': 5000000,
#     'database_size_mb': 1024.5,
#     'unique_symbols_simulated': 500,
#     ...
# }
```

---

## Миграция данных

### Автоматическая миграция

При первом запуске БД автоматически мигрирует данные из JSON файлов:

```python
# В ai_trainer.py
def _migrate_json_to_database(self):
    """Однократная миграция данных из JSON в БД"""
    if self.ai_db:
        # Миграция симуляций
        if os.path.exists('data/ai/simulated_trades.json'):
            # Загружает и сохраняет в БД
            ...
```

### Ручная миграция

Если нужно мигрировать данные вручную:

```python
import json
from bot_engine.ai.ai_database import get_ai_database

db = get_ai_database()

# Загружаем из JSON
with open('data/ai/simulated_trades.json', 'r') as f:
    data = json.load(f)

# Сохраняем в БД
for trade in data:
    db.save_simulated_trade(trade)
```

### Миграция схемы

БД автоматически мигрирует схему при добавлении новых полей:

```python
def _migrate_schema(self, cursor, conn):
    """Добавляет новые поля если их нет"""
    # Проверяет наличие колонок и добавляет их если нужно
    # Использует PRAGMA table_info для проверки
```

**Важно:** Миграция схемы безопасна - она только добавляет новые поля, не удаляет существующие.

---

## Примеры использования

### Пример 1: Сохранение симуляции

```python
from bot_engine.ai.ai_database import get_ai_database

db = get_ai_database()

trade = {
    'symbol': 'BTCUSDT',
    'direction': 'LONG',
    'entry_price': 50000.0,
    'exit_price': 51000.0,
    'entry_time': 1234567890,
    'exit_time': 1234567900,
    'entry_rsi': 30.5,
    'exit_rsi': 70.2,
    'entry_trend': 'UP',
    'exit_trend': 'UP',
    'pnl': 1000.0,
    'pnl_pct': 2.0,
    'exit_reason': 'TP',
    'is_successful': 1,
    'rsi_params': {'oversold': 30, 'overbought': 70},
    'risk_params': {'sl': 2.0, 'tp': 4.0},
    'config': {...},
}

db.save_simulated_trade(trade)
```

### Пример 2: Анализ производительности

```python
# Получаем все сделки для символа
trades = db.get_simulated_trades(symbol='BTCUSDT', limit=10000)

# Фильтруем успешные
successful = [t for t in trades if t['is_successful'] == 1]

# Считаем статистику
win_rate = len(successful) / len(trades) if trades else 0
total_pnl = sum(t['pnl'] for t in trades)
avg_pnl = total_pnl / len(trades) if trades else 0

print(f"Win Rate: {win_rate:.2%}")
print(f"Total PnL: {total_pnl:.2f}")
print(f"Avg PnL: {avg_pnl:.2f}")
```

### Пример 3: Загрузка свечей для обучения

```python
# Загружаем все свечи для всех символов
all_candles = db.get_all_candles_dict(timeframe='6h')

for symbol, candles in all_candles.items():
    print(f"{symbol}: {len(candles)} свечей")
    
    # Используем для обучения
    train_on_candles(symbol, candles)
```

### Пример 4: Параллельная обработка

```python
import socket
import os
import time

def process_symbols_parallel(symbols):
    db = get_ai_database()
    hostname = socket.gethostname()
    process_id = f"{hostname}-{os.getpid()}-{int(time.time())}"
    
    # Получаем доступные символы
    available = db.get_available_symbols(symbols, process_id, hostname)
    
    for symbol in available:
        # Пытаемся заблокировать
        if db.try_lock_symbol(symbol, process_id, hostname, lock_duration_minutes=120):
            try:
                # Обрабатываем
                process_symbol(symbol)
            finally:
                # Освобождаем
                db.release_lock(symbol, process_id)
```

---

## Best Practices

### 1. Используйте батч-операции

**Плохо:**
```python
for candle in candles:
    db.save_candles('BTCUSDT', [candle])
```

**Хорошо:**
```python
db.save_candles('BTCUSDT', candles)  # Все сразу
# Или для нескольких символов:
db.save_candles_batch(candles_data)
```

### 2. Используйте фильтры при чтении

**Плохо:**
```python
all_trades = db.get_simulated_trades()
filtered = [t for t in all_trades if t['symbol'] == 'BTCUSDT' and t['entry_time'] > 1234567890]
```

**Хорошо:**
```python
filtered = db.get_simulated_trades(
    symbol='BTCUSDT',
    start_time=1234567890
)
```

### 3. Обрабатывайте ошибки

```python
try:
    db.save_simulated_trade(trade)
except Exception as e:
    logger.error(f"Ошибка сохранения: {e}")
    # Не прерываем выполнение, продолжаем работу
```

### 4. Используйте транзакции для множественных операций

```python
with db._get_connection() as conn:
    cursor = conn.cursor()
    # Множественные операции
    cursor.execute("INSERT INTO ...")
    cursor.execute("UPDATE ...")
    # Автоматический commit при выходе из контекста
```

### 5. Очищайте старые данные

```python
# Автоматическая очистка старых снимков
deleted = db.cleanup_old_bots_data_snapshots(keep_count=1000)
```

### 6. Проверяйте наличие БД перед использованием

```python
db = get_ai_database()
if not db:
    logger.error("БД не доступна")
    return
```

---

## Миграция других модулей

### Важно: Разделение AI и Bots модулей

**AI модуль:**
- Файлы в `data/ai/` → БД `data/ai/ai_data.db`
- Уже полностью мигрировано ✅

**Bots модуль:**
- Файлы в `data/` (не в `data/ai/`) → Требует миграции ⏳
- Использует: `bots_state.json`, `bot_history.json`, `rsi_cache.json` и др.
- **Не читает файлы из `data/ai/`** - это отдельная папка для AI модуля

### Шаг 1: Анализ текущего хранилища

Определите:
- Какие данные хранятся в файлах?
- Где находятся файлы (`data/` или `data/ai/`)?
- Как часто они обновляются?
- Какие операции выполняются (чтение/запись)?
- Нужны ли JOIN запросы?

**Для bots.py:**
- Файлы находятся в `data/` (не в `data/ai/`)
- Основные файлы: `bots_state.json`, `bot_history.json`, `rsi_cache.json`
- Используются через `bot_engine/storage.py`

### Шаг 2: Проектирование таблиц

**Вариант 1: Отдельная БД для bots**
```python
# Создать отдельную БД для bots
bots_db = BotsDatabase(db_path='data/bots_data.db')
```

**Вариант 2: Общая БД с отдельными таблицами**
```python
# Использовать существующую AI БД, но добавить таблицы для bots
# В ai_database.py добавить таблицы:
```

**Пример таблиц для bots.py:**

```sql
-- Состояние ботов (из bots_state.json)
CREATE TABLE bot_states (
    bot_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL,              -- 'idle', 'running', 'in_position'
    position_side TEXT,                -- 'LONG', 'SHORT'
    entry_price REAL,
    position_size REAL,
    unrealized_pnl REAL,
    config_json TEXT,
    updated_at TEXT NOT NULL
);

-- История действий ботов (из bot_history.json)
CREATE TABLE bot_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id TEXT NOT NULL,
    action_type TEXT NOT NULL,         -- 'start', 'stop', 'entry', 'exit'
    action_data_json TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (bot_id) REFERENCES bot_states(bot_id)
);

-- История сделок ботов
CREATE TABLE bot_trades_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_id TEXT UNIQUE,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    pnl REAL,
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    created_at TEXT NOT NULL
);

-- RSI кэш (из rsi_cache.json)
CREATE TABLE rsi_cache (
    symbol TEXT PRIMARY KEY,
    rsi_value REAL NOT NULL,
    trend TEXT,
    price REAL,
    volume REAL,
    updated_at TEXT NOT NULL
);

-- Зрелые монеты (из mature_coins.json)
CREATE TABLE mature_coins (
    symbol TEXT PRIMARY KEY,
    maturity_data_json TEXT,
    timestamp TEXT NOT NULL
);
```

### Шаг 3: Создание методов в AIDatabase

```python
# В ai_database.py

def save_bot_state(self, bot_id: str, state: Dict) -> bool:
    """Сохраняет состояние бота"""
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO bot_states (
                    bot_id, symbol, status, position_side,
                    entry_price, position_size, unrealized_pnl,
                    config_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bot_id,
                state['symbol'],
                state['status'],
                state.get('position_side'),
                state.get('entry_price'),
                state.get('position_size'),
                state.get('unrealized_pnl'),
                json.dumps(state.get('config', {})),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Ошибка сохранения состояния бота {bot_id}: {e}")
        return False

def get_bot_state(self, bot_id: str) -> Optional[Dict]:
    """Получает состояние бота"""
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bot_states WHERE bot_id = ?", (bot_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'bot_id': row['bot_id'],
                    'symbol': row['symbol'],
                    'status': row['status'],
                    'position_side': row['position_side'],
                    'entry_price': row['entry_price'],
                    'position_size': row['position_size'],
                    'unrealized_pnl': row['unrealized_pnl'],
                    'config': json.loads(row['config_json']) if row['config_json'] else {},
                    'updated_at': row['updated_at']
                }
            return None
    except Exception as e:
        logger.error(f"Ошибка получения состояния бота {bot_id}: {e}")
        return None
```

### Шаг 4: Обновление модуля

**Было (JSON):**
```python
# Сохранение
with open('data/bots_state.json', 'w') as f:
    json.dump(bots_data, f)

# Загрузка
with open('data/bots_state.json', 'r') as f:
    bots_data = json.load(f)
```

**Стало (БД):**
```python
from bot_engine.ai.ai_database import get_ai_database

db = get_ai_database()

# Сохранение
db.save_bot_state(bot_id, bot_state)

# Загрузка
bot_state = db.get_bot_state(bot_id)
```

### Шаг 5: Миграция существующих данных

```python
def migrate_bots_data_to_db():
    """Мигрирует данные из JSON в БД"""
    db = get_ai_database()
    
    # Загружаем из JSON
    if os.path.exists('data/bots_state.json'):
        with open('data/bots_state.json', 'r') as f:
            bots_data = json.load(f)
        
        # Сохраняем в БД
        for bot_id, state in bots_data.get('bots', {}).items():
            db.save_bot_state(bot_id, state)
        
        logger.info(f"Мигрировано {len(bots_data.get('bots', {}))} ботов")
```

### Шаг 6: Удаление файлов

После успешной миграции:
1. Убедитесь что все данные мигрированы
2. Удалите JSON файлы
3. Обновите `.gitignore` (если нужно)
4. Обновите документацию

### Шаг 7: Тестирование

```python
# Проверка сохранения
db.save_bot_state('test_bot', {'symbol': 'BTCUSDT', 'status': 'running'})
state = db.get_bot_state('test_bot')
assert state['symbol'] == 'BTCUSDT'

# Проверка обновления
db.save_bot_state('test_bot', {'symbol': 'ETHUSDT', 'status': 'idle'})
state = db.get_bot_state('test_bot')
assert state['symbol'] == 'ETHUSDT'

# Проверка производительности
import time
start = time.time()
for i in range(1000):
    db.save_bot_state(f'bot_{i}', {'symbol': 'BTCUSDT', 'status': 'running'})
print(f"1000 сохранений: {time.time() - start:.2f} сек")
```

---

## Часто задаваемые вопросы

### Q: Как обрабатывать ошибки БД?

A: Все методы AIDatabase обрабатывают ошибки внутри и логируют их. При ошибке они возвращают безопасные значения (None, [], 0).

### Q: Можно ли использовать БД из нескольких процессов?

A: Да! WAL режим позволяет параллельные чтения и записи. Используйте `training_locks` для координации.

### Q: Что делать если БД повреждена?

A: SQLite автоматически восстанавливается. Если проблема серьезная, можно пересоздать БД и мигрировать данные заново.

### Q: Как оптимизировать производительность?

A:
- Используйте индексы (они уже созданы)
- Используйте батч-операции
- Используйте фильтры при чтении
- Очищайте старые данные

### Q: Можно ли использовать другую БД (PostgreSQL, MySQL)?

A: Текущая реализация использует SQLite. Для перехода на другую БД нужно:
1. Изменить драйвер БД
2. Адаптировать SQL запросы
3. Обновить настройки подключения

### Q: Где находятся файлы для миграции bots.py?

A: Bots модуль использует файлы в `data/` (не в `data/ai/`):
- `data/bots_state.json` - состояние ботов
- `data/bot_history.json` - история действий и сделок
- `data/rsi_cache.json` - кэш RSI данных
- И другие файлы в `data/`

AI модуль использует файлы в `data/ai/` - они уже мигрированы.

### Q: Можно ли использовать одну БД для AI и bots?

A: Да, можно. Но рекомендуется:
- **Вариант 1:** Отдельные БД (`data/ai/ai_data.db` и `data/bots_data.db`) - проще управление
- **Вариант 2:** Общая БД с префиксами таблиц (`ai_simulated_trades`, `bots_states`) - проще JOIN запросы между модулями

Выбор зависит от того, нужны ли вам JOIN запросы между данными AI и bots.

---

## Улучшения и защита данных

### 🔒 Автоматическая проверка целостности БД

**Проблема:** БД может быть повреждена при сбоях, некорректном завершении работы или проблемах с сетью.

**Решение:** При каждом запуске автоматически выполняется проверка целостности БД.

#### Реализация

```python
def _check_integrity(self) -> Tuple[bool, Optional[str]]:
    """
    Проверяет целостность БД
    
    Returns:
        Tuple[bool, Optional[str]]: (is_ok, error_message)
    """
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        # Быстрая проверка целостности
        cursor.execute("PRAGMA quick_check")
        result = cursor.fetchone()[0]
        
        if result == "ok":
            return True, None
        else:
            # Полная проверка для деталей
            cursor.execute("PRAGMA integrity_check")
            integrity_results = cursor.fetchall()
            error_details = "; ".join([row[0] for row in integrity_results if row[0] != "ok"])
            return False, error_details or result
```

#### Использование при инициализации

```python
def _init_database(self):
    """Создает все таблицы и индексы"""
    # Проверяем целостность БД при каждом запуске
    if os.path.exists(self.db_path):
        logger.info("🔍 Проверка целостности БД...")
        is_ok, error_msg = self._check_integrity()
        
        if not is_ok:
            logger.error(f"❌ Обнаружены повреждения в БД: {error_msg}")
            logger.warning("🔧 Попытка автоматического исправления...")
            
            if self._repair_database():
                logger.info("✅ БД успешно исправлена")
```

### 💾 Резервное копирование перед удалением

**Проблема:** При повреждении БД система могла удалять её без резервной копии, что приводило к потере данных.

**Решение:** Перед удалением поврежденной БД автоматически создается резервная копия.

#### Реализация

```python
def _backup_database(self) -> Optional[str]:
    """
    Создает резервную копию БД перед удалением
    
    Returns:
        Путь к резервной копии или None если не удалось создать
    """
    if not os.path.exists(self.db_path):
        return None
    
    try:
        import shutil
        from datetime import datetime
        
        # Создаем имя резервной копии с timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.db_path}.backup_{timestamp}"
        
        # Копируем БД и связанные файлы
        shutil.copy2(self.db_path, backup_path)
        
        # Копируем WAL и SHM файлы если есть
        wal_file = self.db_path + '-wal'
        shm_file = self.db_path + '-shm'
        if os.path.exists(wal_file):
            shutil.copy2(wal_file, f"{backup_path}-wal")
        if os.path.exists(shm_file):
            shutil.copy2(shm_file, f"{backup_path}-shm")
        
        logger.warning(f"💾 Создана резервная копия БД: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"❌ Ошибка создания резервной копии БД: {e}")
        return None
```

#### Защита от потери данных

```python
def _recreate_database(self):
    """Удаляет поврежденную БД и создает новую"""
    # Проверяем, есть ли данные в БД
    has_data = self._check_database_has_data()
    
    if has_data:
        # Если есть данные - ОБЯЗАТЕЛЬНО создаем резервную копию
        backup_path = self._backup_database()
        if not backup_path:
            # Не удаляем БД если не удалось создать резервную копию!
            logger.error(f"❌ КРИТИЧНО: Не удалось создать резервную копию БД с данными!")
            logger.error(f"❌ БД НЕ БУДЕТ УДАЛЕНА для защиты данных!")
            raise Exception("Не удалось создать резервную копию БД с данными - удаление отменено")
```

#### Восстановление из резервной копии

```python
def restore_from_backup(self, backup_path: str = None) -> bool:
    """
    Восстанавливает БД из резервной копии
    
    Args:
        backup_path: Путь к резервной копии (если None, используется последняя)
    
    Returns:
        True если восстановление успешно
    """
    # Если путь не указан, используем последнюю резервную копию
    if backup_path is None:
        backups = self.list_backups()
        if not backups:
            logger.error("❌ Нет доступных резервных копий")
            return False
        backup_path = backups[0]['path']
    
    # Восстанавливаем БД
    shutil.copy2(backup_path, self.db_path)
    # Восстанавливаем WAL и SHM файлы если есть
    # ...
```

### 🔄 Retry логика при блокировках БД

**Проблема:** При параллельном доступе к одной БД с нескольких серверов возникали ошибки `database is locked`.

**Решение:** Автоматические повторы при ошибках блокировки с экспоненциальной задержкой.

#### Реализация

```python
@contextmanager
def _get_connection(self, retry_on_locked: bool = True, max_retries: int = 5):
    """
    Контекстный менеджер для работы с БД с поддержкой retry при блокировках
    
    Args:
        retry_on_locked: Повторять попытки при ошибке "database is locked"
        max_retries: Максимальное количество попыток при блокировке
    """
    for attempt in range(max_retries if retry_on_locked else 1):
        try:
            # Увеличиваем timeout для операций записи при параллельном доступе
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            # ...
            
            try:
                yield conn
                conn.commit()
                conn.close()
                return  # Успешно выполнили операцию
            except sqlite3.OperationalError as e:
                error_str = str(e).lower()
                if "database is locked" in error_str or "locked" in error_str:
                    conn.rollback()
                    conn.close()
                    if retry_on_locked and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 0.5  # Экспоненциальная задержка
                        logger.debug(f"⚠️ БД заблокирована (попытка {attempt + 1}/{max_retries}), ждем {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue  # Повторяем попытку
                    else:
                        raise
```

#### Преимущества

- ✅ Автоматические повторы при временных блокировках
- ✅ Экспоненциальная задержка (0.5s, 1s, 1.5s, 2s, 2.5s)
- ✅ Увеличенный timeout (60 секунд) для сетевых операций
- ✅ Подробное логирование попыток

### 🏷️ Флаги миграций в таблице db_metadata

**Проблема:** Миграция выполнялась при каждом запуске, даже если данные уже были в БД.

**Решение:** Таблица `db_metadata` для хранения флагов миграций и других метаданных.

#### Создание таблицы

```sql
CREATE TABLE IF NOT EXISTS db_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_db_metadata_key ON db_metadata(key);
```

#### Универсальные методы для работы с флагами

```python
def _set_metadata_flag(self, key: str, value: str):
    """
    Устанавливает флаг в метаданных БД
    
    Универсальный метод для установки любых флагов миграций или других метаданных.
    
    Args:
        key: Ключ флага (например, 'json_migration_completed', 'schema_v2_migrated')
        value: Значение флага (обычно '0' или '1', но может быть любое строковое значение)
    """
    now = datetime.now().isoformat()
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO db_metadata (key, value, updated_at, created_at)
            VALUES (?, ?, ?, 
                    COALESCE((SELECT created_at FROM db_metadata WHERE key = ?), ?))
        """, (key, value, now, key, now))
        conn.commit()

def _get_metadata_flag(self, key: str, default: str = None) -> Optional[str]:
    """
    Получает значение флага из метаданных БД
    
    Args:
        key: Ключ флага
        default: Значение по умолчанию если флаг не найден
    
    Returns:
        Значение флага или default
    """
    with self._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM db_metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row['value']
        return default

def _is_migration_flag_set(self, flag_key: str) -> bool:
    """
    Проверяет, установлен ли флаг миграции
    
    Args:
        flag_key: Ключ флага миграции
    
    Returns:
        True если флаг установлен в '1', False в противном случае
    """
    flag_value = self._get_metadata_flag(flag_key, '0')
    return flag_value == '1'
```

#### Использование для миграций

```python
def migrate_json_to_database(self) -> Dict[str, int]:
    """Мигрирует данные из JSON файлов в БД (однократно)"""
    # Проверяем флаг миграции
    if not self._is_migration_needed():
        logger.debug("ℹ️ Миграция не требуется - данные уже есть в БД")
        return {}
    
    migration_stats = {}
    # ... выполнение миграции ...
    
    if migration_stats:
        # Устанавливаем флаг что миграция выполнена
        self._set_metadata_flag('json_migration_completed', '1')
    
    return migration_stats

def _is_migration_needed(self) -> bool:
    """Проверяет, нужна ли миграция из JSON файлов"""
    # Проверяем флаг миграции в метаданных БД
    flag_value = self._get_metadata_flag('json_migration_completed', '0')
    return flag_value != '1'
```

#### Примеры для будущих миграций

```python
# Пример 1: Миграция схемы v2
if not db._is_migration_flag_set('schema_v2_migrated'):
    # Выполнить миграцию схемы
    db.migrate_schema_v2()
    db._set_metadata_flag('schema_v2_migrated', '1')

# Пример 2: Миграция данных из другого источника
if not db._is_migration_flag_set('external_data_migrated'):
    # Выполнить миграцию
    db.migrate_external_data()
    db._set_metadata_flag('external_data_migrated', '1')

# Пример 3: Хранение версии БД
version = db._get_metadata_flag('db_version', '1.0')
if version != '2.0':
    # Выполнить миграцию на версию 2.0
    db.migrate_to_v2()
    db._set_metadata_flag('db_version', '2.0')
```

### 🔧 Автоматическое исправление поврежденной БД

**Проблема:** При обнаружении повреждений БД требовалось ручное вмешательство.

**Решение:** Автоматическое исправление через VACUUM или восстановление из резервной копии.

#### Реализация

```python
def _repair_database(self) -> bool:
    """
    Пытается исправить поврежденную БД
    
    Returns:
        True если удалось исправить, False в противном случае
    """
    logger.warning("🔧 Попытка исправления БД...")
    
    # Создаем резервную копию перед исправлением
    backup_path = self._backup_database()
    if not backup_path:
        logger.error("❌ Не удалось создать резервную копию перед исправлением")
        return False
    
    # Пытаемся использовать VACUUM для исправления
    try:
        conn = sqlite3.connect(self.db_path, timeout=300.0)  # 5 минут для VACUUM
        cursor = conn.cursor()
        logger.info("🔧 Выполняю VACUUM для исправления БД (это может занять время)...")
        cursor.execute("VACUUM")
        conn.commit()
        conn.close()
        logger.info("✅ VACUUM выполнен")
    except Exception as vacuum_error:
        logger.warning(f"⚠️ VACUUM не помог: {vacuum_error}")
    
    # Проверяем, исправилась ли БД
    is_ok, error_msg = self._check_integrity()
    if is_ok:
        logger.info("✅ БД успешно исправлена с помощью VACUUM")
        return True
    else:
        logger.warning(f"⚠️ БД все еще повреждена после VACUUM: {error_msg}")
        # Пытаемся восстановить из резервной копии
        logger.info("🔄 Попытка восстановления из резервной копии...")
        backups = self.list_backups()
        if backups and len(backups) > 1:
            # Используем предпоследнюю копию (последняя - это та, что мы только что создали)
            older_backup = backups[1]['path']
            return self.restore_from_backup(older_backup)
        elif backups:
            return self.restore_from_backup(backups[0]['path'])
        else:
            logger.error("❌ Нет доступных резервных копий для восстановления")
            return False
```

### 📋 Резюме улучшений

Все эти улучшения должны быть реализованы при создании БД для bots.py:

1. ✅ **Автоматическая проверка целостности** при каждом запуске
2. ✅ **Резервное копирование** перед удалением поврежденной БД
3. ✅ **Таблица db_metadata** для хранения флагов миграций
4. ✅ **Универсальные методы** для работы с флагами (`_set_metadata_flag`, `_get_metadata_flag`, `_is_migration_flag_set`)
5. ✅ **Retry логика** при блокировках БД (до 5 попыток с экспоненциальной задержкой)
6. ✅ **Увеличенный timeout** (60 секунд) для сетевых операций
7. ✅ **Автоматическое исправление** через VACUUM или восстановление из резервной копии
8. ✅ **Методы восстановления** из резервных копий (`restore_from_backup`, `list_backups`)

### 🎯 Рекомендации для bots.py БД

При создании БД для bots.py обязательно реализуйте:

1. **Таблицу db_metadata** для флагов миграций
2. **Проверку целостности** при инициализации
3. **Резервное копирование** перед удалением
4. **Retry логику** для параллельного доступа
5. **Флаги миграций** для однократного выполнения миграций

Пример структуры для bots.py:

```python
class BotsDatabase:
    def __init__(self, db_path: str = None):
        # ... инициализация ...
        self._init_database()
    
    def _init_database(self):
        # 1. Проверка целостности
        if os.path.exists(self.db_path):
            is_ok, error_msg = self._check_integrity()
            if not is_ok:
                self._repair_database()
        
        # 2. Создание таблиц включая db_metadata
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Создать db_metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS db_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            # Создать остальные таблицы
            # Установить флаг миграции = 0 если БД новая
            if not db_exists:
                now = datetime.now().isoformat()
                cursor.execute("""
                    INSERT OR IGNORE INTO db_metadata (key, value, updated_at, created_at)
                    VALUES ('json_migration_completed', '0', ?, ?)
                """, (now, now))
    
    def migrate_json_to_database(self):
        # Проверить флаг миграции
        if self._is_migration_flag_set('json_migration_completed'):
            return {}
        
        # Выполнить миграцию
        # ...
        
        # Установить флаг
        self._set_metadata_flag('json_migration_completed', '1')
```

---

## Полезные ссылки

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [WAL Mode](https://www.sqlite.org/wal.html)
- [AI Database Code](../bot_engine/ai/ai_database.py)
- [AI Database UNC Paths Guide](./AI_DATABASE_UNC_PATHS.md)

---

## Заключение

Миграция на SQLite БД дает:
- ✅ Масштабируемость (миллиарды записей)
- ✅ Производительность (индексы, WAL)
- ✅ Гибкость (JOIN запросы, сложные выборки)
- ✅ Надежность (атомарные операции, транзакции)
- ✅ Параллелизм (WAL режим)

Используйте это руководство для миграции других модулей системы на БД!

