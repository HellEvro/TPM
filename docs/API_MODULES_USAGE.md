# Использование API модулей

## Статус

✅ **Созданы модули API endpoints:**
- `bot_engine/api/endpoints_health.py` - health checks
- `bot_engine/api/endpoints_bots.py` - управление ботами
- `bot_engine/api/endpoints_config.py` - конфигурация
- `bot_engine/api/endpoints_rsi.py` - RSI данные
- `bot_engine/api/endpoints_positions.py` - позиции
- `bot_engine/api/endpoints_mature.py` - зрелые монеты
- `bot_engine/api/endpoints_system.py` - системные операции

⚠️ **Проблема:** Endpoints зависят от глобальных переменных из `bots.py`

## Почему не интегрировали сейчас?

### Зависимости endpoints:

Каждый endpoint требует доступ к:
- `exchange` - объект биржи
- `bots_data` - данные ботов
- `coins_rsi_data` - RSI данные
- `bots_data_lock`, `rsi_data_lock` - блокировки
- `BOT_STATUS` - константы
- Множество функций из `bots.py`

### Пример зависимостей для одного endpoint:

```python
@app.route('/api/bots/create')
def create_bot():
    # Нужны:
    - ensure_exchange_initialized()
    - exchange
    - bots_data
    - bots_data_lock
    - check_coin_maturity_with_storage()
    - create_bot()
    - save_bots_state()
    - log_bot_start()
```

## Решение: State Manager (Этап 3)

Для полной интеграции нужен **State Manager**:

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
        self.BOT_STATUS = {...}
    
    def get_bots(self):
        with self.locks['bots']:
            return self.bots_data.copy()
```

Тогда регистрация будет простой:

```python
# В bots.py
from bot_engine.api import register_all_endpoints

state_manager = StateManager()
register_all_endpoints(bots_app, state_manager)
```

## Текущее использование

Пока endpoints остаются в `bots.py`, но:

✅ **Готовы модули** - можно использовать когда будет State Manager  
✅ **Документированы** - понятна структура  
✅ **Протестированы** - логика работает  

## Как использовать новые модули сейчас

### 1. Импортируйте функции регистрации:

```python
from bot_engine.api import register_health_endpoints
```

### 2. Подготовьте state словарь:

```python
state = {
    'exchange': exchange,
    'bots_data': bots_data,
    'bots_data_lock': bots_data_lock,
    'ensure_exchange_func': ensure_exchange_initialized,
    # ... и так далее
}
```

### 3. Зарегистрируйте endpoints:

```python
register_health_endpoints(bots_app, lambda: {
    'exchange_connected': exchange is not None,
    'coins_loaded': len(coins_rsi_data['coins']),
    'bots_active': len(bots_data['bots'])
})
```

## Когда интегрировать?

Интегрировать API модули стоит когда:
1. ✅ Создан State Manager (Этап 3)
2. ✅ Убраны глобальные переменные
3. ✅ Рефакторен NewTradingBot

**Оценка времени:** 6-8 часов работы

## Текущая польза модулей

Даже без интеграции, модули полезны:
- ✅ Документируют структуру API
- ✅ Готовы к использованию
- ✅ Упрощают понимание кода
- ✅ Шаблон для новых endpoints

## Следующие шаги

1. **Сейчас:** Оставить endpoints в `bots.py`
2. **Этап 3:** Создать State Manager
3. **Этап 4:** Интегрировать API модули
4. **Этап 5:** Удалить дубликаты из `bots.py`

---

**Вывод:** API модули созданы и готовы, но для интеграции нужен State Manager.

