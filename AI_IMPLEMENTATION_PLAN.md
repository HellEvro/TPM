# План реализации улучшений AI системы InfoBot

## ИНСТРУКЦИИ ДЛЯ CURSOR AGENT

**ВАЖНО:** Этот файл содержит детальный план для автоматического выполнения в Cursor Agent Mode.  
**КОНФИДЕНЦИАЛЬНО:** Файл не синхронизируется в публичный репозиторий.

---

## Как использовать этот план

1. Открой Cursor в Agent Mode (Ctrl+I или Cmd+I)
2. Скопируй нужный раздел задачи
3. Cursor выполнит задачу автоматически
4. После завершения - сделай "пуш" для сохранения

---

## ФАЗА 1: Критические улучшения

### Задача 1.1: Создание модуля Smart Money Concepts (SMC)

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/smart_money_features.py со следующим функционалом:

1. Класс SmartMoneyFeatures с методом compute_features(df: pd.DataFrame)

2. ОСНОВА - RSI (уже используется, только улучшить):
   - RSI 14 периодов на 6H таймфрейме (основной)
   - RSI дивергенции (скрытые и обычные)
   - RSI зоны перепроданности (<30) и перекупленности (>70)
   - Время с последнего сигнала RSI для каждой монеты

3. SMART MONEY CONCEPTS (SMC):

   a) Order Blocks (ордерблоки):
      - Bullish OB: последняя медвежья свеча перед импульсным ростом
      - Bearish OB: последняя бычья свеча перед импульсным падением
      - Метод find_order_blocks(df, lookback=50) -> List[Dict]
      - Возвращает: цена, тип (bullish/bearish), сила, был ли протестирован
   
   b) Fair Value Gaps (FVG / Imbalance):
      - Bullish FVG: gap между high свечи N-2 и low свечи N (цена не заполнена)
      - Bearish FVG: gap между low свечи N-2 и high свечи N
      - Метод find_fvg(df) -> List[Dict] с верхней/нижней границей
      - Отслеживание: заполнен ли gap (mitigation)
   
   c) Liquidity Zones (зоны ликвидности):
      - Equal highs/lows (двойные/тройные вершины/дно)
      - Зоны со стоп-лоссами (выше swing high, ниже swing low)
      - Метод find_liquidity_zones(df) -> List[Dict]
   
   d) Break of Structure (BOS):
      - Пробой предыдущего swing high (бычий BOS)
      - Пробой предыдущего swing low (медвежий BOS)
      - Метод detect_bos(df) -> Dict с направлением и силой
   
   e) Change of Character (CHoCH):
      - Первый признак смены тренда (слом структуры)
      - Метод detect_choch(df) -> Dict
   
   f) Premium/Discount Zones:
      - Premium: верхние 50% диапазона (для продаж)
      - Discount: нижние 50% диапазона (для покупок)
      - Equilibrium: середина диапазона
      - Метод get_price_zone(df, current_price) -> str

4. SWING STRUCTURE:
   - Swing Highs / Swing Lows (локальные экстремумы)
   - Higher Highs (HH), Higher Lows (HL) - восходящий тренд
   - Lower Highs (LH), Lower Lows (LL) - нисходящий тренд
   - Метод analyze_market_structure(df) -> Dict

5. Метод get_smc_signal(df) -> Dict:
   - Возвращает комплексный сигнал на основе всех SMC факторов
   - signal: 'LONG', 'SHORT', 'WAIT'
   - confidence: 0-100
   - reasons: список причин
   - entry_zone: оптимальная зона входа (Order Block или FVG)

6. Добавь docstrings на русском языке
7. Используй numpy и pandas
8. В конце файла добавь тестовый код: if __name__ == '__main__'
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/smart_money_features.py`
- Изменить: `bot_engine/ai/lstm_predictor.py` (импорт SMC features)
- Изменить: `bot_engine/ai/ai_integration.py` (использование SMC сигналов)
- Изменить: `bots_modules/filters.py` (интеграция SMC в фильтры)

**Критерии успеха:**
- [ ] Order Blocks корректно определяются на исторических данных
- [ ] FVG находятся и отслеживается их заполнение
- [ ] Break of Structure детектируется
- [ ] Интеграция с существующей RSI логикой
- [ ] Тестовый код показывает найденные SMC зоны

---

### Задача 1.2: Добавление Attention к LSTM

**Промпт для Cursor:**
```
Модифицируй файл bot_engine/ai/lstm_predictor.py:

1. Добавь класс MultiHeadSelfAttention:
   - nn.MultiheadAttention с num_heads=4
   - Layer Normalization
   - Residual connection

2. Создай новый класс ImprovedLSTMModel (не удаляй старый LSTMModel!):
   - Bidirectional LSTM (2 слоя, hidden_sizes=[256, 128])
   - Self-Attention после первого LSTM
   - LayerNorm вместо BatchNorm
   - Residual connections
   - Gated Linear Units в MLP голове
   - Отдельные головы для direction, change, confidence

3. Добавь параметр use_improved_model=True в класс LSTMPredictor:
   - Если True - использовать ImprovedLSTMModel
   - Если False - использовать старый LSTMModel (для совместимости)

4. Сохрани обратную совместимость со старыми моделями

5. Обнови метод _create_new_model() для выбора архитектуры

6. Добавь логирование какая архитектура используется

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 2.2 как референс.
```

**Файлы для изменения:**
- `bot_engine/ai/lstm_predictor.py`

**Критерии успеха:**
- [ ] ImprovedLSTMModel работает
- [ ] Старые модели загружаются (обратная совместимость)
- [ ] Attention визуализируется в логах
- [ ] GPU ускорение работает

---

### Задача 1.3: Bayesian Optimization вместо Grid Search

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/bayesian_optimizer.py:

1. Класс BayesianOptimizer:
   - __init__(param_space, objective_function, n_initial_points=20)
   - optimize(n_iterations=100) -> Dict[str, Any]
   - Gaussian Process для surrogate model
   - Expected Improvement acquisition function
   - Multi-start оптимизация

2. Функция optimize_strategy_bayesian(symbol, candles, current_win_rate) -> Optional[Dict]:
   - Параметры: rsi_long/short, exit levels, SL, TP, trailing
   - Objective: win_rate * 100 + total_pnl * 0.5 + sharpe * 10
   - Возвращает лучшие параметры

3. Добавь интеграцию с Optuna (опционально, если установлен):
   - TPESampler
   - HyperbandPruner
   - Параллельные trials

Затем модифицируй bot_engine/ai/ai_strategy_optimizer.py:

4. Добавь метод optimize_coin_parameters_bayesian() как альтернативу Grid Search
5. Добавь параметр optimization_method='bayesian' | 'grid' в конфиг
6. Логируй прогресс оптимизации

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 5.2-5.3.
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/bayesian_optimizer.py`
- Изменить: `bot_engine/ai/ai_strategy_optimizer.py`
- Изменить: `bot_engine/bot_config.py` (добавить настройку)

**Критерии успеха:**
- [ ] Bayesian оптимизация работает
- [ ] Находит решение за меньше итераций чем Grid Search
- [ ] Логи показывают прогресс
- [ ] Optuna интеграция (опционально)

---

### Задача 1.4: Data Drift Detection

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/drift_detector.py:

1. Класс DataDriftDetector:
   - __init__(reference_data, threshold=0.05)
   - detect_drift(new_data) -> Dict с drift_detected, drifted_features, recommendation
   - Kolmogorov-Smirnov test для каждого признака
   - Сохранение reference статистик

2. Класс ModelPerformanceMonitor:
   - log_prediction(prediction, actual)
   - get_metrics() -> Dict с direction_accuracy, MAE, calibration
   - get_performance_trend() для отслеживания деградации

3. Интеграция в auto_trainer.py:
   - Проверка дрифта перед обучением
   - Автоматическое переобучение при сильном дрифте

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 9.1.
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/drift_detector.py`
- Изменить: `bot_engine/ai/auto_trainer.py`

**Критерии успеха:**
- [ ] Drift detection работает
- [ ] Метрики логируются
- [ ] Автоматическое переобучение срабатывает

---

## ФАЗА 2: Важные улучшения

### Задача 2.1: Transformer архитектура

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/transformer_predictor.py:

1. Класс PositionalEncoding для временных рядов

2. Класс GatedResidualNetwork (GRN):
   - Linear -> ELU -> Linear -> GLU
   - Residual connection
   - LayerNorm

3. Класс VariableSelectionNetwork:
   - Softmax attention для выбора важных признаков
   - Возвращает weights для интерпретации

4. Класс TemporalFusionTransformer:
   - Variable Selection
   - LSTM Encoder
   - Interpretable Multi-Head Attention
   - Position-wise Feed-Forward
   - Quantile output heads

5. Класс TransformerPredictor (аналог LSTMPredictor):
   - Методы: train(), predict(), save_model(), load_model(), get_status()
   - Совместимый API с LSTMPredictor

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 3.2.
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/transformer_predictor.py`
- Изменить: `bot_engine/ai/__init__.py` (экспорт)

**Критерии успеха:**
- [ ] TFT модель обучается
- [ ] Variable weights интерпретируемы
- [ ] Производительность не хуже LSTM

---

### Задача 2.2: Ensemble методы

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/ensemble.py:

1. Класс VotingEnsemble:
   - add_model(name, model, weight)
   - predict(x) с взвешенным голосованием
   - Возвращает predictions от каждой модели

2. Класс StackingEnsemble(nn.Module):
   - base_models: Dict[str, nn.Module]
   - meta_model: MLP
   - train_meta_model() для обучения только мета-модели
   - forward() возвращает финальное предсказание

3. Класс EnsemblePredictor:
   - Объединяет LSTM, Transformer, CNN
   - Методы: train(), predict(), get_status()
   - Автоматический выбор весов на основе валидации

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 6.
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/ensemble.py`

**Критерии успеха:**
- [ ] Voting ensemble работает
- [ ] Stacking ensemble обучается
- [ ] Улучшение метрик vs одиночные модели

---

### Задача 2.3: CNN Pattern Detector

**Промпт для Cursor:**
```
Модифицируй файл bot_engine/ai/pattern_detector.py:

1. Добавь класс CNNPatternDetector(nn.Module):
   - Conv1d слои для временных паттернов
   - Multi-scale features (kernel 3, 5, 7)
   - Global average и max pooling
   - Classification head для 10 паттернов

2. Обнови PATTERN_LABELS:
   - bullish_engulfing, hammer, double_bottom, ascending_triangle (bullish)
   - bearish_engulfing, shooting_star, double_top (bearish)
   - descending_triangle, doji, no_pattern (neutral)

3. Добавь метод train_cnn() для обучения CNN модели

4. Добавь параметр use_cnn=True в PatternDetector:
   - Если True - использовать CNN
   - Если False - использовать текущую эвристику

5. Обнови get_pattern_signal() для работы с CNN

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 8.2.
```

**Файлы для изменения:**
- `bot_engine/ai/pattern_detector.py`

**Критерии успеха:**
- [ ] CNN обучается на паттернах
- [ ] Accuracy > 70% на валидации
- [ ] Интеграция с существующим кодом

---

### Задача 2.4: Performance Monitoring Dashboard

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/monitoring.py:

1. Класс AIPerformanceMonitor:
   - track_prediction(symbol, prediction, timestamp)
   - track_actual_result(symbol, actual, timestamp)
   - get_daily_metrics() -> Dict
   - get_weekly_report() -> str
   - export_metrics_to_db()

2. Класс ModelHealthChecker:
   - check_model_staleness(model_path) -> bool
   - check_prediction_distribution() -> Dict
   - get_recommendations() -> List[str]

3. Интеграция с endpoints_ai.py:
   - Добавь /api/ai/performance endpoint
   - Добавь /api/ai/health endpoint

4. Добавь визуализацию в Web UI (templates/pages/bots.html):
   - Карточка "AI Performance"
   - Графики accuracy, win_rate за последние 7 дней
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/monitoring.py`
- Изменить: `bot_engine/api/endpoints_ai.py`
- Изменить: `templates/pages/bots.html`
- Изменить: `static/js/managers/ai_config_manager.js`

**Критерии успеха:**
- [ ] Метрики собираются
- [ ] API работает
- [ ] UI показывает данные

---

## ФАЗА 3: Продвинутые функции

### Задача 3.1: Reinforcement Learning Agent

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/rl_agent.py:

1. Класс TradingEnvironment:
   - reset() -> state
   - step(action) -> (next_state, reward, done, info)
   - Actions: HOLD=0, BUY=1, SELL=2, CLOSE=3
   - Reward shaping для PnL

2. Класс DQNNetwork(nn.Module):
   - MLP: 256 -> 128 -> 64 -> action_size
   - Dropout для регуляризации

3. Класс DQNAgent:
   - act(state, training) с epsilon-greedy
   - remember(experience) в replay buffer
   - replay() для обучения на batch
   - Double DQN для стабильности

4. Класс RLTrader:
   - train(candles, episodes=1000)
   - predict_action(state) -> int
   - save_model(), load_model()
   - get_status()

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 7.2.
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/rl_agent.py`

**Критерии успеха:**
- [ ] Agent обучается
- [ ] Положительный reward на тесте
- [ ] Модель сохраняется/загружается

---

### Задача 3.2: Sentiment Analysis

**Промпт для Cursor:**
```
Создай новый файл bot_engine/ai/sentiment.py:

1. Класс SentimentAnalyzer:
   - analyze_text(text) -> Dict с sentiment, confidence
   - Использовать transformers pipeline если доступен
   - Fallback на простые правила

2. Класс CryptoSentimentCollector:
   - get_twitter_sentiment(symbol) [placeholder для API]
   - get_reddit_sentiment(symbol) [placeholder]
   - get_news_sentiment(symbol) [placeholder]
   - get_aggregated_sentiment(symbol) -> Dict

3. Интеграция в ai_integration.py:
   - Добавить sentiment как дополнительный сигнал
   - Логировать sentiment при принятии решений

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 10.1.
```

**Файлы для изменения:**
- Создать: `bot_engine/ai/sentiment.py`
- Изменить: `bot_engine/ai/ai_integration.py`

**Критерии успеха:**
- [ ] Базовый sentiment работает
- [ ] Placeholders для API готовы
- [ ] Интеграция в решения AI

---

### Задача 3.3: MLflow Experiment Tracking

**Промпт для Cursor:**
```
Модифицируй bot_engine/ai/auto_trainer.py:

1. Добавь класс ExperimentTracker:
   - start_run(run_name)
   - log_params(params)
   - log_metrics(metrics, step)
   - log_model(model, name)
   - end_run()
   - Работает без MLflow если не установлен

2. Интегрируй tracking в _retrain():
   - Логировать все гиперпараметры
   - Логировать loss на каждой эпохе
   - Сохранять лучшую модель

3. Добавь UI для просмотра экспериментов:
   - /api/ai/experiments endpoint
   - Список runs с метриками

Используй код из IMPROVEMENTS_PROPOSAL.md раздел 9.2.
```

**Файлы для изменения:**
- Изменить: `bot_engine/ai/auto_trainer.py`
- Изменить: `bot_engine/api/endpoints_ai.py`

**Критерии успеха:**
- [ ] Эксперименты логируются
- [ ] История доступна через API
- [ ] Работает без MLflow

---

## ПОРЯДОК ВЫПОЛНЕНИЯ

### Рекомендуемая последовательность:

```
1. Задача 1.1 (Smart Money Concepts) - БАЗОВАЯ, институциональный анализ
   ↓
2. Задача 1.2 (Attention LSTM) - улучшает модель для SMC сигналов
   ↓
3. Задача 1.3 (Bayesian Opt) - ускоряет оптимизацию параметров
   ↓
4. Задача 1.4 (Drift Detection) - мониторинг качества
   ↓
5. Задача 2.3 (CNN Patterns) - распознавание SMC паттернов визуально
   ↓
6. Задача 2.1 (Transformer) - альтернативная архитектура для SMC
   ↓
7. Задача 2.2 (Ensemble) - объединяет модели
   ↓
8. Задача 2.4 (Monitoring) - полный мониторинг
   ↓
9. Задача 3.1 (RL Agent) - продвинутая торговля на базе SMC
   ↓
10. Задача 3.2 (Sentiment) - дополнительные данные
    ↓
11. Задача 3.3 (MLflow) - эксперименты
```

---

## ПРАВИЛА ДЛЯ CURSOR AGENT

### При выполнении каждой задачи:

1. **Перед началом:**
   - Прочитай все связанные файлы
   - Проверь текущую структуру импортов
   - Убедись что понял задачу

2. **Во время выполнения:**
   - Сохраняй обратную совместимость
   - Добавляй docstrings на русском
   - Используй type hints
   - Логируй важные события

3. **После завершения:**
   - Проверь linter ошибки (ReadLints)
   - Запусти тесты если есть
   - Сделай commit и push

4. **При ошибках:**
   - Не удаляй существующий код без необходимости
   - Создавай новые классы/методы рядом со старыми
   - Добавляй флаги для переключения версий

### Шаблон commit сообщения:

```
AI улучшения: [название задачи]

- Добавлено: [что добавлено]
- Изменено: [что изменено]  
- Исправлено: [что исправлено]
```

---

## ТЕСТИРОВАНИЕ

### После каждой задачи проверить:

```python
# 1. Импорты работают
from bot_engine.ai.smart_money_features import SmartMoneyFeatures
from bot_engine.ai.lstm_predictor import LSTMPredictor, ImprovedLSTMModel
from bot_engine.ai.bayesian_optimizer import BayesianOptimizer

# 2. Классы инстанцируются
smc = SmartMoneyFeatures()
predictor = LSTMPredictor()
optimizer = BayesianOptimizer(param_space, objective)

# 3. Основные методы работают
signal = smc.get_smc_signal(df)
order_blocks = smc.find_order_blocks(df)
fvg = smc.find_fvg(df)
structure = smc.analyze_market_structure(df)
prediction = predictor.predict(candles, current_price)
best_params = optimizer.optimize(n_iterations=50)
```

### Скрипты для тестирования:

```bash
# Проверка AI системы
python scripts/verify_ai_ready.py

# Тест обучения LSTM
python scripts/ai/train_lstm_predictor.py --coins 1 --epochs 5

# Тест оптимизатора
python -c "from bot_engine.ai.ai_strategy_optimizer import AIStrategyOptimizer; o = AIStrategyOptimizer(); print(o.analyze_trade_patterns())"
```

---

## ССЫЛКИ НА ДОКУМЕНТАЦИЮ

- Полные предложения: `IMPROVEMENTS_PROPOSAL.md`
- Текущая архитектура: `docs/ARCHITECTURE.md`
- AI документация: `docs/AI_README.md`
- TODO проекта: `TODO.txt`

---

**Автор:** AI Assistant  
**Версия:** 1.0  
**Дата:** 26 января 2026  
**Статус:** КОНФИДЕНЦИАЛЬНО - только для приватного репозитория
