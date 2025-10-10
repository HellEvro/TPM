# 📚 State Manager - Примеры кода

Практические примеры использования новой архитектуры с State Manager.

---

## 🔄 Сравнение: До и После

### Пример 1: Создание бота

#### ❌ ДО (с глобальными переменными)

```python
# bots.py
exchange = None
bots_data = {}
bots_data_lock = threading.Lock()

def create_bot(symbol):
    global exchange, bots_data, bots_data_lock
    
    with bots_data_lock:
        if symbol in bots_data['bots']:
            raise ValueError(f"Bot {symbol} already exists")
        
        bot = NewTradingBot(symbol, exchange)
        bots_data['bots'][symbol] = bot
        
        return bot

# Проблемы:
# 1. Невозможно протестировать изолированно
# 2. Неясно откуда берется exchange
# 3. Трудно мокировать зависимости
```

#### ✅ ПОСЛЕ (с State Manager)

```python
# bot_engine/managers/bot_manager.py
class BotManager:
    def __init__(self, exchange_manager, rsi_manager):
        self.exchange_manager = exchange_manager
        self.rsi_manager = rsi_manager
        self._bots = {}
        self._lock = threading.Lock()
    
    def create_bot(self, symbol, config):
        with self._lock:
            if symbol in self._bots:
                raise ValueError(f"Bot {symbol} already exists")
            
            bot = TradingBot(
                symbol=symbol,
                exchange_manager=self.exchange_manager,
                rsi_manager=self.rsi_manager,
                config=config
            )
            self._bots[symbol] = bot
            return bot

# Преимущества:
# 1. Легко тестировать с mock зависимостями
# 2. Явные зависимости
# 3. Инкапсуляция логики
```

**Тест для новой версии:**

```python
def test_create_bot():
    # Создаем mock зависимости
    mock_exchange = Mock()
    mock_rsi = Mock()
    
    # Создаем менеджер
    bot_manager = BotManager(mock_exchange, mock_rsi)
    
    # Тестируем создание
    bot = bot_manager.create_bot('BTCUSDT', {})
    
    # Проверяем
    assert bot.symbol == 'BTCUSDT'
    assert bot_manager.get_bot('BTCUSDT') == bot
```

---

### Пример 2: Получение RSI данных

#### ❌ ДО

```python
# bots.py
coins_rsi_data = {'coins': {}}
rsi_data_lock = threading.Lock()

def get_rsi(symbol):
    global coins_rsi_data, rsi_data_lock
    
    with rsi_data_lock:
        coin_data = coins_rsi_data['coins'].get(symbol)
        if coin_data:
            return coin_data.get('rsi')
        return None

# Проблемы:
# 1. Глобальное состояние
# 2. Трудно тестировать
# 3. Можно забыть блокировку
```

#### ✅ ПОСЛЕ

```python
# bot_engine/managers/rsi_manager.py
class RSIDataManager:
    def __init__(self):
        self._data = {'coins': {}}
        self._lock = threading.Lock()
    
    def get_rsi(self, symbol):
        with self._lock:
            coin_data = self._data['coins'].get(symbol)
            return coin_data.get('rsi') if coin_data else None
    
    def update_rsi(self, symbol, rsi_value):
        with self._lock:
            if symbol not in self._data['coins']:
                self._data['coins'][symbol] = {}
            self._data['coins'][symbol]['rsi'] = rsi_value
            self._data['coins'][symbol]['timestamp'] = datetime.now()

# Преимущества:
# 1. Инкапсуляция
# 2. Легко тестировать
# 3. Блокировка встроена
```

**Использование:**

```python
# В воркере
def rsi_update_worker(state: BotSystemState):
    for symbol in get_all_symbols():
        rsi = calculate_rsi(symbol)
        state.rsi_manager.update_rsi(symbol, rsi)
```

---

### Пример 3: Auto Bot Worker

#### ❌ ДО

```python
def auto_bot_worker():
    global exchange, bots_data, coins_rsi_data, shutdown_flag
    global bots_data_lock, rsi_data_lock
    
    while not shutdown_flag.is_set():
        # Получаем конфиг
        with bots_data_lock:
            config = bots_data['auto_bot_config']
            if not config.get('enabled'):
                time.sleep(60)
                continue
        
        # Получаем монеты с сигналами
        with rsi_data_lock:
            long_signals = {
                symbol: data 
                for symbol, data in coins_rsi_data['coins'].items()
                if data.get('signal') == 'LONG'
            }
        
        # Создаем ботов
        for symbol in long_signals:
            with bots_data_lock:
                if symbol not in bots_data['bots']:
                    bot = NewTradingBot(symbol, exchange)
                    bots_data['bots'][symbol] = bot

# Проблемы:
# 1. Множество global переменных
# 2. Много блокировок в разных местах
# 3. Риск забыть блокировку
# 4. Трудно тестировать
```

#### ✅ ПОСЛЕ

```python
def auto_bot_worker(state: BotSystemState, shutdown_flag, interval):
    """
    Воркер автоматического создания ботов.
    
    Args:
        state: Состояние системы
        shutdown_flag: Флаг остановки
        interval: Интервал проверки
    """
    while not shutdown_flag.is_set():
        # Получаем конфиг (thread-safe)
        config = state.config_manager.get_auto_bot_config()
        if not config.get('enabled'):
            time.sleep(interval)
            continue
        
        # Получаем монеты с сигналами (thread-safe)
        long_signals = state.rsi_manager.get_coins_with_signal('LONG')
        
        # Создаем ботов (thread-safe)
        for symbol in long_signals:
            if not state.bot_manager.get_bot(symbol):
                try:
                    bot = state.bot_manager.create_bot(symbol, config)
                    bot.start()
                except Exception as e:
                    logger.error(f"Error creating bot: {e}")
        
        time.sleep(interval)

# Преимущества:
# 1. Нет global переменных
# 2. Явные зависимости
# 3. Thread-safety встроена в менеджеры
# 4. Легко тестировать
```

**Тест:**

```python
def test_auto_bot_worker():
    # Mock состояние
    state = Mock(spec=BotSystemState)
    state.config_manager.get_auto_bot_config.return_value = {
        'enabled': True,
        'max_concurrent_bots': 5
    }
    state.rsi_manager.get_coins_with_signal.return_value = {
        'BTCUSDT': {'rsi': 25, 'signal': 'LONG'}
    }
    state.bot_manager.get_bot.return_value = None
    
    # Запускаем воркер в отдельном потоке
    shutdown = threading.Event()
    thread = threading.Thread(
        target=auto_bot_worker,
        args=(state, shutdown, 0.1)
    )
    thread.start()
    
    # Даем время на выполнение
    time.sleep(0.5)
    
    # Останавливаем
    shutdown.set()
    thread.join()
    
    # Проверяем что бот был создан
    state.bot_manager.create_bot.assert_called_once_with('BTCUSDT', ...)
```

---

### Пример 4: API Endpoint

#### ❌ ДО

```python
@app.route('/api/bots/list')
def list_bots():
    global bots_data, bots_data_lock
    
    with bots_data_lock:
        bots = list(bots_data['bots'].values())
        
        return jsonify({
            'success': True,
            'bots': [bot.to_dict() for bot in bots]
        })

# Проблемы:
# 1. Глобальные переменные
# 2. Трудно тестировать endpoint
```

#### ✅ ПОСЛЕ

```python
def register_bot_endpoints(app, state: BotSystemState):
    """
    Регистрация endpoints для ботов.
    
    Args:
        app: Flask приложение
        state: Состояние системы
    """
    
    @app.route('/api/bots/list')
    def list_bots():
        bots = state.bot_manager.list_bots()
        
        return jsonify({
            'success': True,
            'bots': [bot.to_dict() for bot in bots]
        })
    
    @app.route('/api/bots/create', methods=['POST'])
    def create_bot():
        data = request.get_json()
        symbol = data.get('symbol')
        config = data.get('config', {})
        
        try:
            bot = state.bot_manager.create_bot(symbol, config)
            return jsonify({
                'success': True,
                'bot': bot.to_dict()
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400

# Преимущества:
# 1. Явная зависимость от state
# 2. Легко тестировать
```

**Использование:**

```python
# bots.py
app = Flask(__name__)
state = BotSystemState(exchange_config)

# Регистрируем endpoints
register_bot_endpoints(app, state)
register_rsi_endpoints(app, state)
register_config_endpoints(app, state)
```

**Тест:**

```python
def test_list_bots_endpoint():
    # Создаем тестовое приложение
    app = Flask(__name__)
    
    # Mock состояние
    state = Mock(spec=BotSystemState)
    mock_bot = Mock()
    mock_bot.to_dict.return_value = {'symbol': 'BTCUSDT'}
    state.bot_manager.list_bots.return_value = [mock_bot]
    
    # Регистрируем endpoints
    register_bot_endpoints(app, state)
    
    # Создаем тестовый клиент
    with app.test_client() as client:
        response = client.get('/api/bots/list')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert len(data['bots']) == 1
```

---

### Пример 5: TradingBot с зависимостями

#### ❌ ДО

```python
class NewTradingBot:
    def __init__(self, symbol):
        global exchange, coins_rsi_data, rsi_data_lock
        
        self.symbol = symbol
        self.exchange = exchange  # Глобальная переменная!
    
    def process_signal(self):
        global coins_rsi_data, rsi_data_lock
        
        # Получаем RSI из глобальной переменной
        with rsi_data_lock:
            rsi_data = coins_rsi_data['coins'].get(self.symbol)
        
        if not rsi_data:
            return
        
        # Торговая логика
        if rsi_data['signal'] == 'LONG':
            self._open_position('long')

# Проблемы:
# 1. Зависимость от глобальных переменных
# 2. Невозможно протестировать изолированно
```

#### ✅ ПОСЛЕ

```python
class TradingBot:
    def __init__(self, symbol, exchange_manager, rsi_manager, config):
        """
        Args:
            symbol: Символ монеты
            exchange_manager: Менеджер биржи
            rsi_manager: Менеджер RSI данных
            config: Конфигурация бота
        """
        self.symbol = symbol
        self.exchange_manager = exchange_manager
        self.rsi_manager = rsi_manager
        self.config = config
        
        self.status = 'idle'
        self.position = None
        self._lock = threading.Lock()
    
    def process_signal(self):
        """Обработка торгового сигнала"""
        with self._lock:
            # Получаем RSI через менеджер
            rsi_data = self.rsi_manager.get_rsi(self.symbol)
            if not rsi_data:
                return
            
            # Торговая логика
            if rsi_data['signal'] == 'LONG' and not self.has_position():
                self._open_position('long')
            elif rsi_data['signal'] == 'SHORT' and not self.has_position():
                self._open_position('short')
    
    def _open_position(self, side):
        """Открытие позиции"""
        # Получаем баланс через exchange_manager
        balance = self.exchange_manager.get_balance()
        
        # Рассчитываем размер позиции
        amount = self._calculate_position_size(balance)
        
        # Создаем ордер через exchange_manager
        order = self.exchange_manager.create_order(
            symbol=self.symbol,
            side=side,
            amount=amount
        )
        
        self.position = side
        self.entry_price = order['price']
        self.status = f'in_position_{side}'

# Преимущества:
# 1. Явные зависимости
# 2. Легко тестировать
# 3. Можно мокировать exchange и rsi
```

**Тест:**

```python
def test_trading_bot_process_signal():
    # Mock зависимости
    exchange_manager = Mock()
    rsi_manager = Mock()
    
    # Настраиваем mock
    rsi_manager.get_rsi.return_value = {
        'rsi': 25,
        'signal': 'LONG'
    }
    exchange_manager.get_balance.return_value = {'USDT': 1000}
    exchange_manager.create_order.return_value = {
        'price': 50000,
        'amount': 0.01
    }
    
    # Создаем бота
    bot = TradingBot(
        symbol='BTCUSDT',
        exchange_manager=exchange_manager,
        rsi_manager=rsi_manager,
        config={}
    )
    
    # Обрабатываем сигнал
    bot.process_signal()
    
    # Проверяем что позиция открыта
    assert bot.has_position()
    assert bot.position == 'long'
    assert bot.entry_price == 50000
    
    # Проверяем что методы вызваны
    rsi_manager.get_rsi.assert_called_once_with('BTCUSDT')
    exchange_manager.create_order.assert_called_once()
```

---

## 🔄 Миграция существующего кода

### Шаг 1: Определить все глобальные переменные

```python
# Найти все global переменные
grep -r "global " bots.py

# Результат:
# global exchange
# global bots_data
# global coins_rsi_data
# global shutdown_flag
# ... и т.д.
```

### Шаг 2: Создать соответствующие менеджеры

```python
# Для каждой глобальной переменной создать менеджер
exchange          → ExchangeManager
bots_data         → BotManager
coins_rsi_data    → RSIDataManager
config            → ConfigManager
```

### Шаг 3: Заменить global на state

```python
# ДО
def some_function():
    global exchange, bots_data
    # ... код

# ПОСЛЕ
def some_function(state: BotSystemState):
    # Используем state.exchange_manager
    # Используем state.bot_manager
```

### Шаг 4: Обновить вызовы функций

```python
# ДО
result = some_function()

# ПОСЛЕ
result = some_function(state)
```

---

## 📦 Структура файлов после миграции

```
bot_engine/
├── __init__.py
├── state_manager.py          # BotSystemState (главный)
├── bot.py                     # TradingBot
├── managers/
│   ├── __init__.py
│   ├── exchange_manager.py   # ExchangeManager
│   ├── rsi_manager.py         # RSIDataManager
│   ├── bot_manager.py         # BotManager
│   ├── config_manager.py      # ConfigManager
│   └── worker_manager.py      # WorkerManager
├── workers/
│   ├── __init__.py
│   ├── auto_bot_worker.py
│   ├── sync_positions_worker.py
│   └── status_update_worker.py
├── api/
│   ├── __init__.py
│   ├── endpoints_bots.py
│   ├── endpoints_rsi.py
│   └── endpoints_config.py
└── utils/
    ├── __init__.py
    ├── rsi_utils.py
    └── ema_utils.py

tests/
├── test_exchange_manager.py
├── test_rsi_manager.py
├── test_bot_manager.py
├── test_config_manager.py
├── test_state_manager.py
├── test_trading_bot.py
└── test_integration.py

bots.py                        # Упрощенный главный файл (~200 строк)
```

---

## 🎯 Чеклист миграции

### Подготовка
- [ ] Создать git ветку
- [ ] Создать backup
- [ ] Убедиться что все тесты проходят
- [ ] Создать структуру папок

### Создание менеджеров
- [ ] ExchangeManager
- [ ] RSIDataManager
- [ ] BotManager
- [ ] ConfigManager
- [ ] WorkerManager
- [ ] BotSystemState

### Переработка компонентов
- [ ] TradingBot
- [ ] auto_bot_worker
- [ ] sync_positions_worker
- [ ] status_update_worker
- [ ] API endpoints

### Тестирование
- [ ] Unit тесты для каждого менеджера
- [ ] Интеграционные тесты
- [ ] E2E тесты
- [ ] Performance тесты

### Финализация
- [ ] Обновить документацию
- [ ] Code review
- [ ] Merge в main
- [ ] Deploy

---

## 💡 Полезные паттерны

### Dependency Injection

```python
# Вместо создания зависимостей внутри
class BadBot:
    def __init__(self, symbol):
        self.exchange = ExchangeFactory.create()  # ❌ Создаем внутри

# Передаем зависимости извне
class GoodBot:
    def __init__(self, symbol, exchange_manager):  # ✅ Получаем извне
        self.exchange_manager = exchange_manager
```

### Factory Pattern

```python
class BotFactory:
    def __init__(self, state: BotSystemState):
        self.state = state
    
    def create_bot(self, symbol, bot_type='standard'):
        if bot_type == 'standard':
            return TradingBot(
                symbol,
                self.state.exchange_manager,
                self.state.rsi_manager,
                self.state.config_manager.get_bot_config()
            )
        elif bot_type == 'advanced':
            return AdvancedTradingBot(...)
```

### Observer Pattern

```python
class RSIDataManager:
    def __init__(self):
        self._observers = []
    
    def subscribe(self, observer):
        self._observers.append(observer)
    
    def update_rsi(self, symbol, rsi):
        # Обновляем данные
        self._data[symbol] = rsi
        
        # Уведомляем подписчиков
        for observer in self._observers:
            observer.on_rsi_update(symbol, rsi)

# Использование
state.rsi_manager.subscribe(bot)
```

---

## 🎓 Дополнительные примеры

### Кэширование с State Manager

```python
class CacheManager:
    def __init__(self, ttl=60):
        self._cache = {}
        self._ttl = ttl
        self._lock = threading.Lock()
    
    def get(self, key):
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    return value
            return None
    
    def set(self, key, value):
        with self._lock:
            self._cache[key] = (value, time.time())

# В BotSystemState
class BotSystemState:
    def __init__(self, ...):
        self.cache = CacheManager(ttl=60)
    
    def get_account_info(self):
        # Пробуем из кэша
        cached = self.cache.get('account_info')
        if cached:
            return cached
        
        # Получаем с биржи
        info = self.exchange_manager.get_balance()
        
        # Кэшируем
        self.cache.set('account_info', info)
        
        return info
```

### Logging с контекстом

```python
class BotSystemState:
    def __init__(self, ...):
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        logger = logging.getLogger('BotSystem')
        # Настройка logger
        return logger

# В компонентах
class TradingBot:
    def __init__(self, symbol, state):
        self.state = state
        self.logger = state.logger.getChild(f'Bot.{symbol}')
    
    def process_signal(self):
        self.logger.info("Processing signal")
        # Вывод: [BotSystem.Bot.BTCUSDT] Processing signal
```

---

**Эти примеры показывают как правильно использовать State Manager для построения чистой и тестируемой архитектуры! 🚀**

