# 🤖 КАК БОТ ОТРАБАТЫВАЕТ СИГНАЛЫ

## 📊 ОБЩАЯ СХЕМА РАБОТЫ

```
┌─────────────────────────────────────────────────────────────┐
│              CONTINUOUS DATA LOADER (Основной цикл)          │
│                    Обновление каждые ~23 сек                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ЭТАП 1: Загрузка свечей (load_all_coins_candles_fast)      │
│  ├─ Загружает свечи 6H для всех 573 монет                   │
│  └─ Кэширует в coins_rsi_data['candles_cache']              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ЭТАП 2: Расчет RSI (load_all_coins_rsi)                    │
│  ├─ Для каждой монеты:                                       │
│  │  ├─ get_coin_rsi_data(symbol)                            │
│  │  │  ├─ Рассчитывает RSI 6H                               │
│  │  │  ├─ Получает Optimal EMA периоды                      │
│  │  │  ├─ Определяет базовый сигнал (ENTER_LONG/SHORT/WAIT) │
│  │  │  │  └─ На основе Optimal EMA периодов!                │
│  │  │  ├─ Применяет Enhanced RSI анализ                     │
│  │  │  │  ├─ Volatility (волатильность)                     │
│  │  │  │  ├─ Divergence (дивергенции)                       │
│  │  │  │  ├─ Volume (объемы)                                │
│  │  │  │  └─ Stochastic RSI                                 │
│  │  │  └─ Проверяет зрелость монеты (для UI, НЕ блокирует)  │
│  │  │     ⚠️ ExitScam и RSI Time Filter НЕ проверяются здесь!│
│  │  │     ✅ Они проверяются только при входе в позицию!     │
│  │  └─ Сохраняет в coins_rsi_data['coins'][symbol]          │
│  └─ Результат: 569 монет с полными данными                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ЭТАП 3: Расчет зрелости (calculate_all_coins_maturity)     │
│  ├─ СУПЕР-ОПТИМИЗАЦИЯ: Пропускает если не изменилось        │
│  └─ Проверяет только новые/измененные монеты                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ЭТАП 4: Анализ трендов (analyze_trends_for_signal_coins)   │
│  ├─ Анализирует ТОЛЬКО сигнальные монеты (RSI <=29 или >=71)│
│  └─ Определяет тренд 6H: UP/DOWN/NEUTRAL                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ЭТАП 5: Фильтрация (process_long_short_coins_with_filters) │
│  ├─ Берет монеты с ENTER_LONG/ENTER_SHORT                   │
│  └─ Дополнительные проверки фильтров                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ЭТАП 6: Автобот (_set_filtered_coins_for_autobot)          │
│  └─ Сохраняет отфильтрованные монеты в конфиг автобота      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              AUTO BOT WORKER (Каждые 60 секунд)              │
│  process_auto_bot_signals()                                  │
│  ├─ Берет отфильтрованные монеты                            │
│  ├─ Проверяет, нет ли уже ботов на этих монетах             │
│  ├─ Проверяет, нет ли ручных позиций на бирже               │
│  └─ Создает новых ботов: create_new_autobot(symbol)         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           ОБРАБОТКА СИГНАЛОВ АКТИВНЫХ БОТОВ                  │
│  process_trading_signals_for_all_bots()                      │
│  (Вызывается каждый раунд ContinuousDataLoader)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
```

## 🎯 ДЕТАЛЬНЫЙ ЦИКЛ ОБРАБОТКИ СИГНАЛОВ ДЛЯ ОДНОГО БОТА

### 1️⃣ **ИНИЦИАЛИЗАЦИЯ БОТА**
```python
bot = NewTradingBot(symbol, config, exchange)
```
**Параметры:**
- `symbol`: Название монеты (например, "BTC")
- `config`: Конфигурация бота
  - `volume_mode`: "usdt" или "percent"
  - `volume_value`: Размер позиции (например, 10 USDT)
  - `status`: Текущий статус (IDLE, IN_POSITION_LONG, IN_POSITION_SHORT)
  - `entry_price`: Цена входа
  - `position_side`: LONG или SHORT

---

### 2️⃣ **ОСНОВНОЙ ЦИКЛ: `bot.update()`**

Этот метод вызывается из `process_trading_signals_for_all_bots()`:

```python
# Для каждого активного бота:
signal_result = trading_bot.update(
    force_analysis=True, 
    external_signal=external_signal,  # Из coins_rsi_data
    external_trend=external_trend     # Из coins_rsi_data
)
```

**Что делает `update()`:**

1. **Получает данные:**
   ```python
   - current_price   # Текущая цена из coins_rsi_data
   - current_rsi     # RSI 6H из coins_rsi_data
   - current_trend   # UP/DOWN/NEUTRAL из coins_rsi_data
   - candles         # Свечи 6H за 30 дней с биржи
   ```

2. **Определяет действие по статусу:**
   ```python
   if status == IDLE:
       → _handle_idle_state()      # Ищет возможность входа
   elif status == IN_POSITION_LONG/SHORT:
       → _handle_position_state()  # Управляет позицией
   ```

---

### 3️⃣ **СОСТОЯНИЕ IDLE: ПОИСК ТОЧКИ ВХОДА**

**`_handle_idle_state(rsi, trend, candles, price)`**

#### A) Проверка LONG позиции (`should_open_long`)

```python
✅ ОТКРЫВАЕМ LONG если:
   1. RSI <= 29 (по умолчанию, настраивается)
   2. Вызывается _enter_position('LONG')
```

#### B) Проверка SHORT позиции (`should_open_short`)

```python
✅ ОТКРЫВАЕМ SHORT если:
   1. RSI >= 71 (по умолчанию, настраивается)
   2. Вызывается _enter_position('SHORT')
```

#### C) **КРИТИЧЕСКАЯ ПРОВЕРКА: ВСЕ ФИЛЬТРЫ В `_enter_position()`**

**`_enter_position(side)` - единая точка входа в позицию**

```python
def _enter_position(self, side: str):
    # 1. Проверка делистинга
    if symbol in delisted_coins:
        return {'success': False, 'error': 'coin_delisted'}
    
    # 2. Проверка существующих позиций
    if self.position is not None:
        return {'success': False, 'error': 'position_already_exists'}
    
    # 3. ✅ ВСЕ ФИЛЬТРЫ ПЕРЕД ОТКРЫТИЕМ ПОЗИЦИИ!
    config_snapshot = get_config_snapshot(self.symbol)
    filter_config = config_snapshot.get('merged', {})
    
    filters_allowed, filters_reason = apply_entry_filters(
        self.symbol,
        candles,
        current_rsi,
        signal,  # 'ENTER_LONG' или 'ENTER_SHORT'
        filter_config,
        trend=current_trend
    )
    
    if not filters_allowed:
        return {'success': False, 'error': 'filters_blocked', 'message': filters_reason}
    
    # 4. 🤖 AI Optimal Entry Detection (если включен)
    if ai_optimal_entry_enabled:
        entry_decision = ai_manager.risk_manager.should_enter_now(...)
        if not entry_decision['should_enter']:
            return {'success': False, 'error': 'optimal_entry_wait', 'message': entry_decision['reason']}
    
    # 5. 🤖 AI Risk Management - адаптация размера позиции
    if AI_RISK_MANAGEMENT_ENABLED:
        dynamic_size = ai_manager.risk_manager.calculate_position_size(...)
        self.volume_value = dynamic_size['size_usdt']
    
    # 6. Открытие позиции на бирже
    order_result = self.exchange.place_order(...)
    
    # 7. 🤖 AI Risk Management - адаптация стоп-лосса
    if AI_RISK_MANAGEMENT_ENABLED:
        dynamic_sl = ai_manager.risk_manager.calculate_dynamic_sl(...)
        sl_percent = dynamic_sl['sl_percent']
```

**Что проверяет `apply_entry_filters()`:**
1. ✅ Global switches (`trading_enabled`, `use_test_server`)
2. ✅ Scope (whitelist/blacklist)
3. ✅ Trend (`avoid_down_trend`, `avoid_up_trend`)
4. ✅ Maturity (`enable_maturity_check`)
5. ✅ RSI Time Filter (`rsi_time_filter_enabled`)
6. ✅ ExitScam (`exit_scam_enabled`)
7. 🤖 AI Anomaly Detection (если включен) - внутри ExitScam фильтра

#### D) Открытие позиции на бирже

```python
def _open_position_on_exchange(side, price):
    # 1. Рассчитывает количество монет
    if volume_mode == 'usdt':
        qty = volume_value  # Например, 10 USDT
    
    # 2. Отправляет ордер на биржу
    result = exchange.place_order(
        symbol=symbol,
        side=side,           # 'LONG' или 'SHORT'
        order_type='Market',
        qty=qty,
        marketUnit='quoteCoin'  # ⚡ Указываем qty в USDT!
    )
    
    # 3. Сохраняет данные позиции
    if result['success']:
        self.order_id = result['order_id']
        self.entry_price = price
        self.entry_timestamp = result['timestamp']
        self.position_side = side
        
        # 4. Обновляет статус
        self.status = IN_POSITION_LONG или IN_POSITION_SHORT
        
        return True
```

---

### 4️⃣ **СОСТОЯНИЕ IN_POSITION: УПРАВЛЕНИЕ ПОЗИЦИЕЙ**

**`_handle_position_state(rsi, trend, candles, price)`**

#### A) Обновление защитных механизмов

```python
# 1. Обновляем UnrealizedPnL
current_pnl_percent = ((current_price - entry_price) / entry_price) * 100
if position_side == 'SHORT':
    current_pnl_percent *= -1

self.unrealized_pnl = current_pnl_percent

# 2. Отслеживаем максимальную прибыль
if current_pnl_percent > self.max_profit_achieved:
    self.max_profit_achieved = current_pnl_percent

# 3. Активируем Break-Even (если прибыль >= 2%)
if current_pnl_percent >= 2.0 and not self.break_even_activated:
    self.break_even_activated = True
    logger.info(f"✅ Break-Even активирован при {current_pnl_percent:.2f}%")

# 4. Обновляем Trailing Stop
if self.break_even_activated:
    # Trailing Stop = max_profit - 1.5%
    self.trailing_stop_price = self.max_profit_achieved - 1.5
```

#### B) Проверка условий выхода

```python
✅ ЗАКРЫВАЕМ LONG позицию если:
   1. RSI >= 71 (перекупленность)
   2. ИЛИ Тренд изменился на DOWN
   3. ИЛИ Trailing Stop сработал (прибыль упала на 1.5% от макс)
   4. ИЛИ Break-Even сработал (прибыль < 0% после активации)

✅ ЗАКРЫВАЕМ SHORT позицию если:
   1. RSI <= 29 (перепроданность)
   2. ИЛИ Тренд изменился на UP
   3. ИЛИ Trailing Stop сработал
   4. ИЛИ Break-Even сработал
```

**Пример:**
```python
if position_side == 'LONG':
    if rsi >= 71:
        → ЗАКРЫВАЕМ LONG (выход по RSI) 📊
    elif trend == 'DOWN':
        → ЗАКРЫВАЕМ LONG (смена тренда) 📉
    elif trailing_stop_triggered:
        → ЗАКРЫВАЕМ LONG (trailing stop) 🛑
    elif break_even_triggered:
        → ЗАКРЫВАЕМ LONG (break-even) 🔒
```

#### C) Закрытие позиции на бирже

```python
def _close_position_on_exchange():
    # 1. Отправляет ордер на закрытие
    result = exchange.close_position(
        symbol=symbol,
        side='LONG' или 'SHORT'
    )
    
    # 2. Сохраняет результат в историю
    if result['success']:
        realized_pnl = result['realized_pnl']
        
        # 3. Сбрасывает состояние бота
        self.status = BOT_STATUS['IDLE']
        self.position_side = None
        self.entry_price = None
        self.unrealized_pnl = 0
        self.max_profit_achieved = 0
        self.trailing_stop_price = None
        self.break_even_activated = False
        
        return True
```

---

## ⚙️ НАСТРОЙКИ ТОРГОВЫХ ПРАВИЛ

### 🎯 **RSI Thresholds (Пороги RSI)**
```python
rsi_long_threshold = 29   # Открываем LONG если RSI <= 29
rsi_short_threshold = 71  # Открываем SHORT если RSI >= 71
```

### 📈 **Trend Following (Следование тренду)**
```python
avoid_down_trend = True   # Не открываем LONG на DOWN тренде
avoid_up_trend = True     # Не открываем SHORT на UP тренде
```

### ⏱️ **RSI Time Filter (Временной фильтр RSI)**
```python
rsi_time_filter_enabled = True
rsi_time_filter_candles = 8      # Анализируем последние 8 свечей
rsi_time_filter_lower = 35       # Для LONG: RSI был >= 35
rsi_time_filter_upper = 65       # Для SHORT: RSI был <= 65
```
**⚠️ ВАЖНО:** Проверяется ТОЛЬКО при входе в позицию в `_enter_position()`, а не для всех монет!

### 🛡️ **Enhanced RSI (Улучшенный RSI)**
```python
enhanced_rsi_enabled = True
- Volatility check (проверка волатильности)
- Divergence check (поиск дивергенций)
- Volume confirmation (подтверждение объемами)
- Stochastic RSI (дополнительный осциллятор)
```

### 🚨 **Exit Scam Filter (Фильтр памп/дамп)**
```python
exit_scam_enabled = True
exit_scam_candles = 10              # Анализ последних 10 свечей
single_candle_percent = 15.0        # Одна свеча > 15% = блок
multi_candle_count = 4              # 4 свечи подряд
multi_candle_percent = 50.0         # Суммарно > 50% = блок
```
**⚠️ ВАЖНО:** Проверяется ТОЛЬКО при входе в позицию в `_enter_position()`, а не для всех монет!

### 🤖 **AI Модули (Premium)**
```python
# AI Anomaly Detection - обнаружение аномалий
AI_ENABLED = True
AI_ANOMALY_DETECTION_ENABLED = True
AI_ANOMALY_BLOCK_THRESHOLD = 0.7  # Блокирует при severity > 70%
# ✅ Включается внутри ExitScam фильтра при входе в позицию

# AI Risk Management - умный риск-менеджмент
AI_RISK_MANAGEMENT_ENABLED = True
# ✅ Адаптирует размер позиции и стоп-лосс при входе

# AI Optimal Entry Detection - оптимальная точка входа
ai_optimal_entry_enabled = True
# ✅ Определяет оптимальную цену входа и может отложить вход
```

### 🛡️ **Защитные механизмы в позиции**
```python
# Break-Even: фиксация безубытка
break_even_threshold = 2.0%         # Активируется при +2%
break_even_trigger = 0.0%           # Закрывает при 0%

# Trailing Stop: защита прибыли
trailing_stop_activation = 2.0%     # Активируется при +2%
trailing_stop_distance = 1.5%       # Дистанция от максимума
```

---

## 🔄 ЧАСТОТА ОБНОВЛЕНИЙ

```
Continuous Data Loader: ~23 секунды (один полный раунд)
├─ Свечи: обновляются каждый раунд
├─ RSI: пересчитывается каждый раунд
├─ Зрелость: пересчитывается только при изменениях
└─ Тренды: только для сигнальных монет

Auto Bot Worker: 60 секунд
└─ Создает новых ботов для отфильтрованных монет

Обработка сигналов: каждый раунд (~23 сек)
└─ process_trading_signals_for_all_bots()
```

---

## 📊 ПРИМЕР ПОЛНОГО ЦИКЛА

### Сценарий: Открытие и закрытие LONG позиции

```
Раунд #1 (00:00):
├─ RSI = 28 (< 29) ✅
├─ Trend = NEUTRAL ✅
├─ _enter_position('LONG') вызван
│  ├─ apply_entry_filters() проверяет:
│  │  ├─ Global switches: OK ✅
│  │  ├─ Scope: OK ✅
│  │  ├─ Trend: OK ✅
│  │  ├─ Maturity: OK ✅
│  │  ├─ RSI Time Filter: OK ✅
│  │  └─ ExitScam: OK ✅ (AI Anomaly Detection: OK)
│  ├─ AI Optimal Entry: OK ✅
│  └─ AI Risk Management: размер адаптирован
└─ 🚀 ОТКРЫВАЕМ LONG @ 45,000 USDT

Раунд #2 (00:23):
├─ Price = 45,500 (+1.1%)
├─ RSI = 32
├─ UnrealizedPnL = +1.1%
└─ ⏳ ДЕРЖИМ позицию

Раунд #3 (00:46):
├─ Price = 46,000 (+2.2%)
├─ RSI = 38
├─ UnrealizedPnL = +2.2%
├─ ✅ Break-Even АКТИВИРОВАН
└─ ⏳ ДЕРЖИМ позицию

Раунд #4 (01:09):
├─ Price = 46,800 (+4.0%)
├─ RSI = 45
├─ UnrealizedPnL = +4.0%
├─ Max Profit = +4.0%
├─ Trailing Stop = +2.5% (4.0 - 1.5)
└─ ⏳ ДЕРЖИМ позицию

Раунд #5 (01:32):
├─ Price = 47,500 (+5.6%)
├─ RSI = 72 (> 71) ❌
└─ 📊 ЗАКРЫВАЕМ LONG @ 47,500 (причина: RSI перекуплен)
    Realized PnL: +5.6% 🎉
```

---

## 🎯 КЛЮЧЕВЫЕ МОМЕНТЫ

1. **Бот работает на свечах 6H** - это значит, что он реагирует на долгосрочные движения, а не на шум

2. **Все блокирующие фильтры проверяются ТОЛЬКО при входе** - ExitScam, RSI Time Filter, Maturity проверяются в `_enter_position()` через `apply_entry_filters()`, а не для всех монет постоянно

3. **Зрелость проверяется для всех монет (для UI)**, но блокирует сигнал только при входе в позицию

4. **AI модули включаются при входе** - Anomaly Detection (внутри ExitScam), Risk Management (размер позиции и SL), Optimal Entry Detection (оптимальная цена)

5. **Защитные механизмы** - Break-Even и Trailing Stop защищают прибыль

6. **Автоматическое создание ботов** - Auto Bot Worker создает ботов для новых сигналов

7. **Непрерывное обновление** - данные обновляются каждые ~23 секунды

8. **Умная оптимизация** - кэширование и пропуск ненужных пересчетов

9. **Enhanced RSI** - дополнительная аналитика повышает точность сигналов

---

## 📝 ЛОГИРОВАНИЕ

Каждый этап логируется:
```
[NEW_BOT_BTC] 🤖 Инициализация нового торгового бота
[NEW_BOT_BTC] ✅ Все проверки пройдены - открываем LONG (RSI: 28.5, Trend: NEUTRAL)
[NEW_BOT_BTC] 🚀 Открываем LONG позицию @ 45000 USDT
[NEW_BOT_BTC] ✅ Break-Even активирован при +2.20%
[NEW_BOT_BTC] 📊 Закрываем LONG позицию (RSI: 72.1 >= 71)
[NEW_BOT_BTC] 🎉 Realized PnL: +5.60%
```

---

**Система полностью автоматизирована и работает 24/7!** 🚀

