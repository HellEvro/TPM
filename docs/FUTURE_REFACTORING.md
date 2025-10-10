# План дальнейшего рефакторинга

## Текущий статус

✅ **Завершено:**
- Создано 7 модулей в `bot_engine/` (~1080 строк)
- Вынесены утилиты, фильтры, проверка зрелости, хранилище
- Создана документация и инструменты качества кода
- Все тесты пройдены

⚠️ **Осталось в bots.py:**
- API endpoints (~2000 строк)
- Класс NewTradingBot (~500 строк)
- Воркеры (~300 строк)
- Глобальные переменные и блокировки (~500 строк)
- Инициализация и запуск (~400 строк)

**Итого в bots.py:** ~6500 строк (было 7623)

## Почему не вынесли все сразу?

### Проблема: Глобальные переменные
Многие функции зависят от глобальных переменных:
- `exchange` - объект биржи
- `bots_data` - данные ботов
- `coins_rsi_data` - RSI данные
- `bots_data_lock`, `rsi_data_lock` - блокировки
- `shutdown_flag` - флаг остановки
- `system_initialized` - флаг инициализации

### Решение: Поэтапный рефакторинг

## Этап 2: API Endpoints (будущее)

### Цель: Вынести ~2000 строк API кода

### План:

#### 1. bot_engine/api/endpoints_bots.py (~500 строк)
```python
# Управление ботами
- POST /api/bots/create
- POST /api/bots/start
- POST /api/bots/stop
- POST /api/bots/pause
- POST /api/bots/delete
- POST /api/bots/close-position
- GET  /api/bots/list
- GET  /api/bots/active-detailed
```

#### 2. bot_engine/api/endpoints_config.py (~400 строк)
```python
# Конфигурация
- GET  /api/bots/auto-bot
- POST /api/bots/auto-bot
- POST /api/bots/auto-bot/restore-defaults
- GET  /api/bots/system-config
- POST /api/bots/system-config
- GET  /api/bots/default-config
```

#### 3. bot_engine/api/endpoints_rsi.py (~400 строк)
```python
# RSI данные
- GET  /api/bots/coins-with-rsi
- POST /api/bots/force-rsi-update
- POST /api/bots/refresh-rsi/<symbol>
- POST /api/bots/refresh-rsi-all
- POST /api/bots/clear-rsi-cache
```

#### 4. bot_engine/api/endpoints_system.py (~400 строк)
```python
# Системные операции
- POST /api/bots/sync-positions
- POST /api/bots/cleanup-inactive
- POST /api/bots/reload-modules
- POST /api/bots/reload-config
- POST /api/bots/restart-service
- GET  /api/bots/test-exit-scam/<symbol>
- GET  /api/bots/test-rsi-time-filter/<symbol>
```

#### 5. bot_engine/api/endpoints_history.py (~200 строк)
```python
# История ботов
- GET  /api/bots/history
- GET  /api/bots/trades
- GET  /api/bots/statistics
- POST /api/bots/history/clear
- POST /api/bots/history/demo
```

#### 6. bot_engine/api/endpoints_mature.py (~100 строк)
```python
# Зрелые монеты
- GET  /api/bots/mature-coins
- GET  /api/bots/mature-coins-list
- POST /api/bots/mature-coins/reload
- POST /api/bots/mature-coins/clear
- POST /api/bots/remove-mature-coins
- DELETE /api/bots/mature-coins/<symbol>
```

### Проблема: Зависимости

Каждый endpoint зависит от:
- Глобальных переменных (`exchange`, `bots_data`, etc.)
- Блокировок (`bots_data_lock`, `rsi_data_lock`)
- Других функций из `bots.py`

### Решение: Dependency Injection

```python
# Вместо глобальных переменных
def register_bots_endpoints(app, state_manager):
    @app.route('/api/bots/list')
    def get_bots_list():
        bots = state_manager.get_bots()
        return jsonify({'bots': bots})
```

## Этап 3: State Manager (будущее)

### Цель: Убрать глобальные переменные

### План:

#### bot_engine/state_manager.py
```python
class StateManager:
    def __init__(self):
        self.exchange = None
        self.bots_data = {}
        self.coins_rsi_data = {}
        self.locks = {
            'bots': threading.Lock(),
            'rsi': threading.Lock()
        }
    
    def get_bots(self):
        with self.locks['bots']:
            return self.bots_data.copy()
    
    def update_bot(self, symbol, data):
        with self.locks['bots']:
            self.bots_data[symbol] = data
```

### Преимущества:
- Нет глобальных переменных
- Легче тестировать
- Четкие зависимости
- Thread-safe по дизайну

## Этап 4: NewTradingBot рефакторинг (будущее)

### Цель: Вынести ~500 строк класса

### Проблема:
Класс зависит от:
- `bots_data_lock`
- `bots_data`
- `BOT_STATUS`
- `coins_rsi_data`
- `rsi_data_lock`

### Решение:
```python
class NewTradingBot:
    def __init__(self, symbol, config, exchange, state_manager):
        self.symbol = symbol
        self.config = config
        self.exchange = exchange
        self.state_manager = state_manager  # Вместо глобальных переменных
```

## Этап 5: Воркеры (будущее)

### bot_engine/workers/auto_save_worker.py
```python
def auto_save_worker(state_manager, shutdown_flag):
    while not shutdown_flag.is_set():
        state_manager.save_all()
        time.sleep(interval)
```

### bot_engine/workers/position_sync_worker.py
```python
def position_sync_worker(state_manager, exchange, shutdown_flag):
    while not shutdown_flag.is_set():
        sync_positions(state_manager, exchange)
        time.sleep(interval)
```

## Оценка трудозатрат

| Этап | Строк кода | Сложность | Время |
|------|------------|-----------|-------|
| Этап 1 (✅ завершен) | ~1080 | Средняя | 2-3 часа |
| Этап 2: API endpoints | ~2000 | Высокая | 4-6 часов |
| Этап 3: State Manager | ~500 | Очень высокая | 6-8 часов |
| Этап 4: NewTradingBot | ~500 | Высокая | 3-4 часа |
| Этап 5: Воркеры | ~300 | Средняя | 2-3 часа |

**Итого:** ~4380 строк, 17-24 часа работы

## Рекомендации

### Сейчас (после Этапа 1):
✅ Используйте новые модули для новых функций  
✅ Применяйте автоформатирование  
✅ Проверяйте синтаксис перед коммитом  

### Когда делать Этап 2-5:
- Когда будет время на большой рефакторинг
- Когда понадобится добавить много новых функций
- Когда bots.py станет совсем неуправляемым

### Альтернатива:
Можно оставить как есть - текущая структура уже намного лучше чем была!

## Текущие преимущества

✅ Основная логика вынесена в модули  
✅ Меньше дублирования кода  
✅ Автоформатирование работает  
✅ Проще находить и исправлять ошибки  
✅ Готовность к дальнейшему рефакторингу  

---

**Вывод:** Этап 1 завершен успешно. Этапы 2-5 опциональны и могут быть выполнены позже.

