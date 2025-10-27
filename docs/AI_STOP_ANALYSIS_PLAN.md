# План системы обучения ИИ на стопах и бэктестинга

## ✅ Что уже сделано

### 1. Расширена система истории (`bot_engine/bot_history.py`)
- ✅ Добавлены дополнительные поля в `log_position_closed()`:
  - `entry_data`: RSI на входе, волатильность, тренд
  - `market_data`: данные рынка при выходе
  - `stop_analysis`: детальный анализ стопов (RSI, max drawdown, дневное движение)
- ✅ Добавлен метод `get_stopped_trades()` для извлечения стоп-сделок
- ✅ Добавлен API endpoint `/api/bots/stops` для получения стопов через UI

### 2. Интеграция в UI (уже существует)
- ✅ Страница истории уже реализована (`bots_manager.js`)
- ✅ Есть фильтры и подвкладки (actions, trades, signals)
- ✅ API endpoints уже есть в `api_endpoints.py`

## 🔨 Что нужно сделать

### 1. Интегрировать сохранение данных в `bot_class.py`

При закрытии позиции добавить вызов `bot_history_manager.log_position_closed()` с дополнительными данными:

```python
# В bots_modules/bot_class.py в методе _close_position_on_exchange()

# Подготовка данных для истории
entry_data = {
    'entry_price': self.entry_price,
    'rsi': self.entry_rsi,  # RSI при входе
    'volatility': self.entry_volatility,  # Волатильность при входе
    'trend': self.entry_trend,  # Тренд при входе
    'duration_hours': duration_hours,
    'max_profit_achieved': self.max_profit_achieved
}

market_data = {
    'volatility': current_volatility,  # Текущая волатильность
    'trend': current_trend,  # Текущий тренд
    'price_movement': price_change_pct  # % изменения за период
}

# Логируем закрытие с детальными данными
from bot_engine.bot_history import bot_history_manager
bot_history_manager.log_position_closed(
    bot_id=self.symbol,
    symbol=self.symbol,
    direction=self.position_side,
    exit_price=exit_price,
    pnl=pnl,
    roi=roi,
    reason=reason,
    entry_data=entry_data,
    market_data=market_data
)
```

### 2. Создать модуль `SmartRiskManager`

**Файл:** `bot_engine/ai/smart_risk_manager.py`

**Функционал:**
- **Анализ стопов**: Анализирует историю стоп-сделок, выявляет паттерны
- **Бэктест для каждой монеты**: Перед входом запускает бэктест на последних N свечах
- **Оптимизация параметров**: Определяет оптимальные SL/TP на основе бэктеста
- **Предсказание убытков**: Использует машинное обучение для прогноза вероятности стопа

**Пример использования:**
```python
from bot_engine.ai.smart_risk_manager import SmartRiskManager

risk_manager = SmartRiskManager()

# Перед входом в позицию
backtest_result = risk_manager.backtest_coin(
    symbol='BTCUSDT',
    candles=last_100_candles,
    direction='LONG'
)

# Получаем оптимальные параметры
optimal_sl = backtest_result['optimal_stop_loss']
optimal_tp = backtest_result['optimal_take_profit']
entry_confidence = backtest_result['confidence']

# Анализируем стопы для улучшения
stop_patterns = risk_manager.analyze_stopped_trades()
```

### 3. Интегрировать в `DynamicRiskManager`

Расширить `bot_engine/ai/risk_manager.py`:

```python
def calculate_dynamic_sl_with_backtest(self, symbol: str, candles: List[dict], side: str):
    """Рассчитывает SL с учетом бэктеста"""
    
    # Запускаем быстрый бэктест на последних 50 свечах
    backtest_result = self._quick_backtest(symbol, candles[-50:], side)
    
    # Берем оптимальный SL из бэктеста
    optimal_sl = backtest_result.get('optimal_stop_loss_pct', self.base_sl_percent)
    
    return {
        'sl_percent': optimal_sl,
        'confidence': backtest_result.get('confidence', 0.5),
        'reason': f'Бэктест показал оптимальный SL: {optimal_sl}%'
    }
```

### 4. Добавить UI для анализа стопов

**В `bots_manager.js`:**

```javascript
async loadStoppedTrades() {
    const response = await fetch(`${this.BOTS_SERVICE_URL}/api/bots/stops`);
    const data = await response.json();
    
    if (data.success) {
        this.displayStoppedTrades(data.trades);
    }
}

displayStoppedTrades(trades) {
    // Отображаем анализ стопов
    // - RSI на входе
    // - Волатильность
    // - Max drawdown
    // - Причина стопа
    // - Рекомендации ИИ
}
```

### 5. Автоматическое обучение ИИ

Создать скрипт `scripts/ai/analyze_stops_for_training.py`:

```python
# Анализирует стопы и готовит данные для обучения ИИ
# Запускается раз в день
stops = bot_history_manager.get_stopped_trades(limit=1000)

# Анализируем паттерны
patterns = {
    'high_rsi_stops': [s for s in stops if s['entry_rsi'] > 70],
    'low_volatility_stops': [s for s in stops if s['entry_volatility'] < 0.5],
    'rapid_stops': [s for s in stops if s['duration_hours'] < 6]
}

# Экспортируем в формат для обучения
export_stops_for_training(stops)
```

## 📋 Приоритет задач

1. **Высокий приоритет:**
   - ✅ Расширен BotHistoryManager
   - 🔨 Интегрировать сохранение данных в `bot_class.py` при закрытии позиций
   - 🔨 Создать `SmartRiskManager` с бэктестингом
   - 🔨 Добавить UI для просмотра анализа стопов

2. **Средний приоритет:**
   - 🔨 Автоматическое обучение ИИ на стопах
   - 🔨 Интеграция с существующими AI модулями
   - 🔨 Система рекомендаций на основе анализа стопов

3. **Низкий приоритет:**
   - 🔨 Экспорт данных для внешнего анализа
   - 🔨 Dashboard для визуализации паттернов стопов

## 🎯 Результат

После реализации:
- ✅ ИИ будет анализировать каждый стоп
- ✅ Перед входом в позицию будет запускаться бэктест
- ✅ Система будет предлагать оптимальные SL/TP на основе истории
- ✅ UI покажет анализ стопов с рекомендациями
- ✅ Автоматическое обучение улучшит точность предсказаний

