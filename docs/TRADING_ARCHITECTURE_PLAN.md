# 🏗️ АРХИТЕКТУРА ТОРГОВОЙ СИСТЕМЫ

## 📋 **ОБЩИЙ ЧЕКЛИСТ ПРОЕКТА**

### ✅ **ВЫПОЛНЕНО:**
- [x] RSI Time Filter исправлен
- [x] LSTM модель мигрирована в Keras 3
- [x] AI модули интегрированы
- [x] Базовый UI создан
- [x] Система фильтров работает

### 🔄 **В РАБОТЕ:**
- [ ] **КРИТИЧНО: Исправить запуск ботов (НЕ ВХОДЯТ В ПОЗИЦИИ)**
- [ ] Реализовать предпроцесс между фильтрами и ботами
- [ ] Создать AI мониторинг активных позиций
- [ ] Реализовать гибридные стоп-лоссы с AI

### 📝 **ПЛАН РЕАЛИЗАЦИИ:**

## 🎯 **ЭТАП 1: ИСПРАВЛЕНИЕ ЗАПУСКА БОТОВ (КРИТИЧНО)**

### **Проблема:**
- Боты создаются ✅
- Боты НЕ ВХОДЯТ в позиции ❌
- Система удаляет "неактивных" ботов ❌

### **Причины:**
1. Метод `enter_position` не работает
2. `INACTIVE_CLEANUP` удаляет ботов без позиций
3. Рассинхронизация UI и API

### **Исправления:**
- [x] Добавлен метод `enter_position` в `NewTradingBot`
- [x] Исправлен импорт `rsi_data_lock`
- [x] Исправлен возврат `test_exit_scam_filter`
- [ ] **ПРОВЕРИТЬ: Почему боты не входят в позиции**
- [ ] **ИСПРАВИТЬ: Логику `INACTIVE_CLEANUP`**

---

## 🏗️ **ЭТАП 2: НОВАЯ АРХИТЕКТУРА ТОРГОВОЙ СИСТЕМЫ**

### **ТЕКУЩАЯ АРХИТЕКТУРА (ПРОБЛЕМНАЯ):**
```
ФИЛЬТРЫ → Создание бота → Бот сам определяет параметры → Торговля
```

### **НОВАЯ АРХИТЕКТУРА (ПРАВИЛЬНАЯ):**
```
ФИЛЬТРЫ → ПРЕДПРОЦЕСС → БОТЫ → ИИ МОНИТОРИНГ
    ↓         ↓          ↓         ↓
  RSI      СТОПЫ/ТЕЙКИ  СДЕЛКИ   СИГНАЛЫ
 ВРЕМЯ       ИИ/RSI     SL/TP    УПРАВЛЕНИЕ
ЗРЕЛОСТЬ     ЛИЦЕНЗИЯ   СЛЕЖЕНИЕ  РИСКИ
```

---

## 🔧 **МОДУЛИ ДЛЯ СОЗДАНИЯ:**

### **1. `pre_process_trading.py` - Предпроцесс торговли**
```python
class TradingPreProcessor:
    """Предпроцесс между фильтрами и созданием ботов"""
    
    def __init__(self):
        self.ai_manager = AIManager()
        self.config = load_config()
    
    def process_filtered_coins(self, filtered_coins):
        """Обрабатывает отфильтрованные монеты"""
        results = []
        for coin in filtered_coins:
            # Определяем стопы и тейки по приоритету
            stop_loss, take_profit = self._calculate_stops_and_targets(coin)
            
            # Определяем размер позиции
            position_size = self._calculate_position_size(coin)
            
            # Проверяем лицензию ИИ
            ai_enabled = self._check_ai_license()
            
            results.append({
                'symbol': coin['symbol'],
                'side': coin['side'],  # LONG/SHORT
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'ai_enabled': ai_enabled,
                'entry_price': coin['current_price']
            })
        return results
    
    def _calculate_stops_and_targets(self, coin):
        """Определяет стопы и тейки по приоритету"""
        if self._ai_priority_enabled() and self._check_ai_license():
            # ИИ приоритет
            return self.ai_manager.calculate_stops_targets(coin)
        else:
            # RSI приоритет (fallback)
            return self._calculate_rsi_based_stops(coin)
    
    def _ai_priority_enabled(self):
        """Проверяет приоритет ИИ в настройках"""
        return self.config.get('ai_priority_enabled', False)
    
    def _calculate_rsi_based_stops(self, coin):
        """Расчет стопов на основе RSI"""
        rsi = coin.get('rsi', 50)
        current_price = coin['current_price']
        
        if coin['side'] == 'LONG':
            # Для LONG: стоп ниже текущей цены
            stop_loss = current_price * 0.85  # -15%
            take_profit = current_price * 1.30  # +30%
        else:
            # Для SHORT: стоп выше текущей цены
            stop_loss = current_price * 1.15  # +15%
            take_profit = current_price * 0.70  # -30%
        
        return stop_loss, take_profit
```

### **2. `ai_monitoring.py` - ИИ мониторинг**
```python
class AIMonitoringService:
    """Сервис мониторинга активных позиций через ИИ"""
    
    def __init__(self):
        self.ai_manager = AIManager()
        self.active_bots = {}
        self.monitoring_thread = None
    
    def register_bot(self, bot_id, symbol, side, entry_price, stop_loss, take_profit):
        """Регистрирует бота для мониторинга"""
        self.active_bots[bot_id] = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'start_time': datetime.now(),
            'last_update': datetime.now()
        }
        
        logger.info(f"[AI_MONITOR] 📊 Зарегистрирован бот {bot_id} для мониторинга")
    
    def start_monitoring(self):
        """Запускает мониторинг в отдельном потоке"""
        if not self.monitoring_thread:
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            logger.info("[AI_MONITOR] 🚀 ИИ мониторинг запущен")
    
    def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        while True:
            try:
                self._monitor_active_positions()
                time.sleep(30)  # Проверка каждые 30 секунд
            except Exception as e:
                logger.error(f"[AI_MONITOR] ❌ Ошибка мониторинга: {e}")
                time.sleep(60)
    
    def _monitor_active_positions(self):
        """Мониторит активные позиции"""
        for bot_id, bot_data in self.active_bots.items():
            try:
                # Получаем текущие данные
                market_data = self._get_market_data(bot_data['symbol'])
                
                # Анализируем ИИ
                ai_signal = self.ai_manager.analyze_position(
                    bot_data['symbol'], 
                    bot_data['side'],
                    market_data,
                    bot_data
                )
                
                # Обрабатываем сигнал
                self._process_ai_signal(bot_id, ai_signal)
                
            except Exception as e:
                logger.error(f"[AI_MONITOR] ❌ Ошибка анализа {bot_id}: {e}")
    
    def _process_ai_signal(self, bot_id, ai_signal):
        """Обрабатывает сигнал от ИИ"""
        if ai_signal['action'] == 'CLOSE':
            self._send_close_signal(bot_id, ai_signal['reason'])
        elif ai_signal['action'] == 'ADJUST_SL':
            self._send_adjust_sl_signal(bot_id, ai_signal['new_sl'])
        elif ai_signal['action'] == 'ADJUST_TP':
            self._send_adjust_tp_signal(bot_id, ai_signal['new_tp'])
        elif ai_signal['action'] == 'TRAILING_STOP':
            self._send_trailing_stop_signal(bot_id, ai_signal['trailing_data'])
```

### **3. Обновленный `bot_class.py`**
```python
class NewTradingBot:
    """Торговый бот с предопределенными параметрами"""
    
    def __init__(self, symbol, trading_params):
        self.symbol = symbol
        self.side = trading_params['side']
        self.stop_loss = trading_params['stop_loss']
        self.take_profit = trading_params['take_profit']
        self.position_size = trading_params['position_size']
        self.ai_enabled = trading_params['ai_enabled']
        
        # Инициализация
        self.exchange = None
        self.position_id = None
        self.order_id = None
        self.status = BOT_STATUS['RUNNING']
        
        # ИИ мониторинг
        self.ai_monitoring = None
    
    def start_trading(self):
        """Запускает торговлю с предопределенными параметрами"""
        try:
            logger.info(f"[BOT_{self.symbol}] 🚀 Запуск торговли с параметрами:")
            logger.info(f"[BOT_{self.symbol}] 📊 Сторона: {self.side}")
            logger.info(f"[BOT_{self.symbol}] 🛑 Стоп-лосс: {self.stop_loss}")
            logger.info(f"[BOT_{self.symbol}] 🎯 Тейк-профит: {self.take_profit}")
            logger.info(f"[BOT_{self.symbol}] 💰 Размер: {self.position_size}")
            
            # 1. Открываем позицию
            entry_result = self._open_position()
            if not entry_result['success']:
                return entry_result
            
            # 2. Выставляем стопы и тейки
            sl_tp_result = self._place_stop_loss_take_profit()
            if not sl_tp_result['success']:
                return sl_tp_result
            
            # 3. Регистрируем в ИИ мониторинге
            self._register_for_ai_monitoring()
            
            # 4. Обновляем статус
            self.status = BOT_STATUS['IN_POSITION']
            self.last_update_time = datetime.now()
            
            logger.info(f"[BOT_{self.symbol}] ✅ Торговля успешно запущена")
            return {'success': True, 'position_id': self.position_id}
            
        except Exception as e:
            logger.error(f"[BOT_{self.symbol}] ❌ Ошибка запуска торговли: {e}")
            return {'success': False, 'error': str(e)}
    
    def handle_ai_signal(self, signal):
        """Обрабатывает сигналы от ИИ"""
        try:
            logger.info(f"[BOT_{self.symbol}] 🤖 Получен ИИ сигнал: {signal['action']}")
            
            if signal['action'] == 'CLOSE':
                return self._close_position(signal['reason'])
            elif signal['action'] == 'ADJUST_SL':
                return self._update_stop_loss(signal['new_sl'])
            elif signal['action'] == 'ADJUST_TP':
                return self._update_take_profit(signal['new_tp'])
            elif signal['action'] == 'TRAILING_STOP':
                return self._update_trailing_stop(signal['trailing_data'])
            
        except Exception as e:
            logger.error(f"[BOT_{self.symbol}] ❌ Ошибка обработки ИИ сигнала: {e}")
            return {'success': False, 'error': str(e)}
```

---

## ⚙️ **НАСТРОЙКИ КОНФИГУРАЦИИ:**

### **Добавить в `auto_bot_config.json`:**
```json
{
  "ai_priority_enabled": true,
  "ai_monitoring_enabled": true,
  "ai_monitoring_interval": 30,
  "fallback_to_rsi": true,
  "default_stop_loss_percent": 15,
  "default_take_profit_percent": 30,
  "trailing_stop_enabled": true,
  "trailing_stop_distance": 5
}
```

---

## 🔄 **ИНТЕГРАЦИЯ В ОСНОВНОЙ ПОТОК:**

### **Обновленный `process_auto_bot_signals`:**
```python
def process_auto_bot_signals(exchange_obj=None):
    """Обрабатывает сигналы Auto Bot с новой архитектурой"""
    
    # 1. Получаем отфильтрованные монеты
    filtered_coins = get_filtered_coins_for_trading()
    
    if not filtered_coins:
        logger.info("[AUTO_BOT] ⏳ Нет подходящих монет для торговли")
        return
    
    # 2. Предпроцесс - определяем параметры торговли
    pre_processor = TradingPreProcessor()
    trading_params = pre_processor.process_filtered_coins(filtered_coins)
    
    # 3. Создаем ботов с предопределенными параметрами
    for params in trading_params:
        bot = create_bot_with_params(params)
        if bot:
            bot.start_trading()
    
    # 4. Запускаем ИИ мониторинг
    ai_monitoring = AIMonitoringService()
    ai_monitoring.start_monitoring()
```

---

## 📋 **ЧЕКЛИСТ РЕАЛИЗАЦИИ:**

### **ЭТАП 1: ИСПРАВЛЕНИЕ ТЕКУЩИХ ПРОБЛЕМ**
- [ ] Исправить метод `enter_position` в `NewTradingBot`
- [ ] Исправить логику `INACTIVE_CLEANUP`
- [ ] Проверить работу API endpoints
- [ ] Синхронизировать UI и бэкенд

### **ЭТАП 2: СОЗДАНИЕ ПРЕДПРОЦЕССА**
- [ ] Создать `pre_process_trading.py`
- [ ] Реализовать `TradingPreProcessor`
- [ ] Добавить настройки приоритета ИИ
- [ ] Интегрировать в `process_auto_bot_signals`

### **ЭТАП 3: СОЗДАНИЕ ИИ МОНИТОРИНГА**
- [ ] Создать `ai_monitoring.py`
- [ ] Реализовать `AIMonitoringService`
- [ ] Добавить регистрацию ботов
- [ ] Реализовать обработку ИИ сигналов

### **ЭТАП 4: ОБНОВЛЕНИЕ БОТОВ**
- [ ] Обновить `NewTradingBot` для работы с предопределенными параметрами
- [ ] Добавить обработку ИИ сигналов
- [ ] Реализовать управление стоп-лоссами
- [ ] Добавить трейлинг-стопы

### **ЭТАП 5: ИНТЕГРАЦИЯ И ТЕСТИРОВАНИЕ**
- [ ] Интегрировать все компоненты
- [ ] Протестировать полный цикл
- [ ] Оптимизировать производительность
- [ ] Добавить логирование и мониторинг

---

## 🎯 **ПРИОРИТЕТЫ:**

1. **КРИТИЧНО:** Исправить текущую проблему с запуском ботов
2. **ВЫСОКИЙ:** Реализовать предпроцесс торговли
3. **СРЕДНИЙ:** Добавить ИИ мониторинг
4. **НИЗКИЙ:** Оптимизация и дополнительные функции

---

*Документ создан: 2025-10-18*
*Статус: В разработке*
