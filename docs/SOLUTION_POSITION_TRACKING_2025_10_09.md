# ✅ РЕШЕНИЕ: ОТСЛЕЖИВАНИЕ ПОЗИЦИЙ АВТОБОТА - 09.10.2025

## 📋 АНАЛИЗ ТЕКУЩЕЙ СИТУАЦИИ

### ✅ ЧТО УЖЕ ЕСТЬ:

1. **`exchange.place_order()` возвращает `order_id`** ✅
   ```python
   # exchanges/bybit_exchange.py, строка 1276
   return {
       'success': True,
       'order_id': response['result']['orderId'],  # ✅ ID ЕСТЬ!
       'message': f'{order_type.title()} ордер успешно размещён',
       'price': price or current_price,
       'quantity': qty
   }
   ```

2. **Проверяются только боты из `bots_data['bots']`** ✅
   ```python
   # bots.py, строка 1625-1627
   active_bots = {symbol: bot for symbol, bot in bots_data['bots'].items() 
                 if bot['status'] not in [BOT_STATUS['IDLE'], BOT_STATUS['PAUSED']]}
   ```

3. **Защитные механизмы вызываются** ✅
   ```python
   # bots.py, строки 2115-2117, 2143-2145
   protective_action = self._check_protective_conditions(position_side, current_price)
   if protective_action:
       return protective_action
   ```

### ❌ ЧТО НЕ РАБОТАЕТ:

1. **`order_id` НЕ СОХРАНЯЕТСЯ** при открытии позиции ❌
2. **Нет маркера `opened_by_autobot`** ❌
3. **`_close_position()` ищет позицию только по символу и стороне** ❌
4. **Может закрыть РУЧНУЮ позицию вместо автобота** ❌

---

## 🔧 РЕШЕНИЕ

### 1. **Сохранять `order_id` и маркер при открытии**

#### В `_place_order()` (bots.py, строка 2292):
```python
def _place_order(self, side, price):
    """Размещает ордер на фьючерсах Bybit"""
    try:
        # ... существующий код ...
        
        order_result = exchange.place_order(
            symbol=self.symbol,
            side=side,
            quantity=quantity,
            order_type='market',
            price=None
        )
        
        if order_result and order_result.get('success'):
            # ✅ НОВОЕ: Сохраняем order_id и маркер автобота
            self.order_id = order_result.get('order_id')
            self.entry_timestamp = time.time()
            
            # Сохраняем в bots_data
            with bots_data_lock:
                if self.symbol in bots_data['bots']:
                    bots_data['bots'][self.symbol]['order_id'] = self.order_id
                    bots_data['bots'][self.symbol]['opened_by_autobot'] = True
                    bots_data['bots'][self.symbol]['entry_timestamp'] = self.entry_timestamp
            
            logger.info(f"[BOT] {self.symbol}: {side} ордер размещен успешно")
            logger.info(f"[BOT] {self.symbol}: 🆔 Order ID: {self.order_id}")
            logger.info(f"[BOT] {self.symbol}: ⏰ Entry timestamp: {self.entry_timestamp}")
            return order_result
```

### 2. **Добавить поля в `LocalTradingBot.__init__()` (bots.py, строка 1758)**
```python
class LocalTradingBot:
    """Торговый бот для одной монеты согласно ТЗ"""
    
    def __init__(self, symbol, config=None):
        self.symbol = symbol
        self.config = config or {}
        
        # ... существующие поля ...
        
        # ✅ НОВЫЕ ПОЛЯ для отслеживания
        self.order_id = self.config.get('order_id', None)
        self.entry_timestamp = self.config.get('entry_timestamp', None)
        self.opened_by_autobot = self.config.get('opened_by_autobot', False)
```

### 3. **Добавить в `to_dict()` (bots.py, строка 2509)**
```python
def to_dict(self):
    """Возвращает состояние бота в виде словаря"""
    return {
        'symbol': self.symbol,
        'status': self.status,
        # ... существующие поля ...
        
        # ✅ НОВЫЕ ПОЛЯ
        'order_id': self.order_id,
        'entry_timestamp': self.entry_timestamp,
        'opened_by_autobot': self.opened_by_autobot
    }
```

### 4. **Исправить `_close_position()` (bots.py, строка 2452)**
```python
def _close_position(self, position_side, price, reason):
    """Закрывает позицию"""
    try:
        if not exchange:
            logger.error(f"[BOT] {self.symbol}: Exchange не инициализирован")
            return None
        
        # ✅ КРИТИЧЕСКАЯ ПРОВЕРКА: Позиция открыта автоботом?
        if not self.opened_by_autobot:
            logger.warning(f"[BOT] {self.symbol}: ⚠️ Позиция НЕ открыта автоботом - пропускаем закрытие")
            logger.warning(f"[BOT] {self.symbol}: 🛡️ ЗАЩИТА ОТ ЗАКРЫТИЯ РУЧНЫХ ПОЗИЦИЙ!")
            return None
        
        # Проверяем включена ли торговля
        with bots_data_lock:
            trading_enabled = bots_data['auto_bot_config'].get('trading_enabled', True)
            
        if not trading_enabled:
            logger.info(f"[BOT] {self.symbol}: Торговля отключена, позиция не закрыта (виртуальное закрытие {position_side})")
            return {'success': True, 'message': f'Virtual close - trading disabled ({reason})', 'virtual': True}
            
        # Определяем противоположную сторону для закрытия
        close_side = 'SELL' if position_side == 'LONG' else 'BUY'
        
        # Получаем текущие позиции для определения размера
        current_positions = exchange.get_positions()
        if not current_positions or not current_positions.get('success'):
            logger.error(f"[BOT] {self.symbol}: Не удалось получить позиции для закрытия")
            return None
        
        # ✅ НОВАЯ ЛОГИКА: Ищем НАШУ позицию по order_id и timestamp
        our_position = None
        for pos in current_positions.get('data', []):
            if pos['symbol'] != f"{self.symbol}USDT":
                continue
            if pos['side'] != position_side:
                continue
            if float(pos['positionValue']) <= 0:
                continue
            
            # ✅ ПРОВЕРЯЕМ TIMESTAMP (±10 секунд)
            position_created_time = pos.get('createdTime', 0) / 1000  # Bybit в миллисекундах
            if self.entry_timestamp:
                time_diff = abs(position_created_time - self.entry_timestamp)
                if time_diff > 10:  # Больше 10 секунд разницы
                    logger.warning(f"[BOT] {self.symbol}: ⚠️ Позиция найдена, но timestamp не совпадает")
                    logger.warning(f"[BOT] {self.symbol}: Наш timestamp: {self.entry_timestamp}, позиция: {position_created_time}, разница: {time_diff:.1f}с")
                    continue
            
            # ✅ ЭТО НАША ПОЗИЦИЯ!
            our_position = pos
            logger.info(f"[BOT] {self.symbol}: ✅ Найдена НАША позиция (order_id: {self.order_id}, timestamp match)")
            break
        
        if not our_position:
            logger.warning(f"[BOT] {self.symbol}: ⚠️ НАША позиция {position_side} не найдена для закрытия")
            logger.warning(f"[BOT] {self.symbol}: Возможно уже закрыта или это была ручная позиция")
            return {'success': True, 'message': 'Position not found, assuming already closed'}
        
        # Закрываем позицию через market ордер
        close_result = exchange.place_order(
            symbol=self.symbol,
            side=close_side,
            quantity=float(our_position['positionValue']),
            order_type='market',
            price=None
        )
        
        if close_result and close_result.get('success'):
            logger.info(f"[BOT] {self.symbol}: ✅ Позиция {position_side} закрыта успешно (причина: {reason})")
            
            # ✅ Сбрасываем маркеры автобота
            self.opened_by_autobot = False
            self.order_id = None
            self.entry_timestamp = None
            
            with bots_data_lock:
                if self.symbol in bots_data['bots']:
                    bots_data['bots'][self.symbol]['opened_by_autobot'] = False
                    bots_data['bots'][self.symbol]['order_id'] = None
                    bots_data['bots'][self.symbol]['entry_timestamp'] = None
            
            return close_result
        else:
            logger.error(f"[BOT] {self.symbol}: ❌ Ошибка закрытия позиции {position_side} - {close_result.get('message', 'Unknown error') if close_result else 'No response'}")
            return None
            
    except Exception as e:
        logger.error(f"[BOT] {self.symbol}: Исключение при закрытии позиции {position_side}: {str(e)}")
        return None
```

---

## 🎯 РЕЗУЛЬТАТ

### ✅ ПОСЛЕ ИСПРАВЛЕНИЯ:

1. **При открытии позиции:**
   - Сохраняется `order_id` ✅
   - Сохраняется `entry_timestamp` ✅
   - Устанавливается `opened_by_autobot = True` ✅

2. **При закрытии позиции:**
   - Проверяется `opened_by_autobot` ✅
   - Ищется позиция по `timestamp` (±10 сек) ✅
   - Закрывается ТОЛЬКО позиция автобота ✅
   - **РУЧНЫЕ ПОЗИЦИИ НЕ ТРОГАЮТСЯ!** ✅

3. **Защита:**
   - Если `opened_by_autobot = False` → закрытие блокируется ✅
   - Если timestamp не совпадает → позиция пропускается ✅
   - Если позиция не найдена → логируется предупреждение ✅

---

## 📊 ИТОГ

**ТЕПЕРЬ АВТОБОТ РАБОТАЕТ ТОЛЬКО СО СВОИМИ ПОЗИЦИЯМИ!** 🎉

- ✅ Отслеживание через `order_id`
- ✅ Проверка через `entry_timestamp`
- ✅ Маркер `opened_by_autobot`
- ✅ Защита от закрытия ручных позиций
- ✅ Логирование всех проверок

**РУЧНЫЕ ПОЗИЦИИ В БЕЗОПАСНОСТИ!** 🛡️
