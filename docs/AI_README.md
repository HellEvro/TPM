# AI Overview — InfoBot 1.8

**Дата обновления:** 26 января 2026  
**Статус:** Production Ready  
**Автопроверка:** `python scripts/verify_ai_ready.py`

---

## Зачем этот документ

Актуальная информация об AI системе: активные модули, сервисы, данные/обучение, интеграция, лицензирование. Для деталей см. исходный код в `bot_engine/ai/*` и `ai.py`.

---

## Активные AI модули

### Базовые модули

| Модуль | Файл | Назначение |
| --- | --- | --- |
| Anomaly Detection | `anomaly_detector.py` | IsolationForest, блокирует pump/dump |
| LSTM Predictor | `lstm_predictor.py` | 6h прогноз направления, PyTorch + GPU, Attention |
| Smart Risk Manager | `smart_risk_manager.py` | Динамические SL/TP, размер позиции |
| Parameter Quality Predictor | `parameter_quality_predictor.py` | ML предсказание качества параметров |
| AI Self Learning | `ai_self_learning.py` | Самообучение на сделках |
| Auto Trainer | `auto_trainer.py` | Автоматическое переобучение |

### Новые модули (Фаза 1-3)

| Модуль | Файл | Назначение |
| --- | --- | --- |
| **Smart Money Concepts** | `smart_money_features.py` | Order Blocks, FVG, Liquidity, BOS, CHoCH |
| **Transformer Predictor** | `transformer_predictor.py` | Temporal Fusion Transformer |
| **Bayesian Optimizer** | `bayesian_optimizer.py` | Оптимизация гиперпараметров |
| **Drift Detector** | `drift_detector.py` | Обнаружение дрифта данных |
| **Ensemble** | `ensemble.py` | VotingEnsemble, StackingEnsemble |
| **CNN Pattern Detector** | `pattern_detector.py` | CNN для свечных паттернов |
| **AI Monitoring** | `monitoring.py` | Метрики производительности |
| **RL Agent** | `rl_agent.py` | DQN для торговли |
| **Sentiment Analyzer** | `sentiment.py` | Анализ настроений |
| **AI Integration** | `ai_integration.py` | Интеграция SMC + AI |

---

## Smart Money Concepts (SMC)

Новый модуль институционального анализа:

```python
from bot_engine.ai.smart_money_features import SmartMoneyFeatures

smc = SmartMoneyFeatures()

# Комплексный сигнал
signal = smc.get_smc_signal(df)
# {'signal': 'LONG', 'score': 75, 'reasons': [...]}

# Отдельные компоненты
order_blocks = smc.find_order_blocks(df)  # Ордерблоки
fvg = smc.find_fvg(df)                    # Fair Value Gaps
liquidity = smc.find_liquidity_zones(df)  # Зоны ликвидности
structure = smc.analyze_market_structure(df)  # HH/HL/LH/LL
bos = smc.detect_bos(df)                  # Break of Structure
choch = smc.detect_choch(df)              # Change of Character
```

---

## LSTM с Attention

Улучшенная архитектура LSTM:

```python
from bot_engine.ai.lstm_predictor import LSTMPredictor

# Улучшенная модель (Bidirectional LSTM + Self-Attention)
predictor = LSTMPredictor(use_improved_model=True)

# Базовая модель (обратная совместимость)
predictor = LSTMPredictor(use_improved_model=False)

# Предсказание
result = predictor.predict(candles, current_price)
```

Архитектура ImprovedLSTMModel:
- Bidirectional LSTM (256 → 128)
- Multi-Head Self-Attention
- Gated Linear Units
- Layer Normalization
- Residual connections

---

## AI Launcher & сервисы

`ai.py` управляет защищённым ядром и запускает:

- `AIDataCollector` — сбор котировок в `data/ai/raw/`
- `AITrainer` / `AIContinuousLearning` — переобучение моделей
- `AISelfLearning` — самообучение на сделках
- `AIBacktester` — прогон стратегий
- `AIStrategyOptimizer` — оптимизация параметров
- `AIBotManager` — оркестрация модулей
- `ParameterQualityPredictor` — ML для параметров

Запуск: `python ai.py`

---

## Архитектура защиты

```
ЯДРО (защищено .pyc):
├── ai_manager.pyc        ← Логика AI
├── license_checker.pyc   ← Проверка лицензий
└── _ai_launcher.pyc      ← Загрузчик

AI МОДУЛИ (обычные .py):
├── smart_money_features.py
├── lstm_predictor.py
├── transformer_predictor.py
├── bayesian_optimizer.py
├── drift_detector.py
├── ensemble.py
├── monitoring.py
├── rl_agent.py
├── sentiment.py
├── pattern_detector.py
└── ai_integration.py
```

**Важно:**
- Проверка лицензии только в ядре
- AI модули — обычные .py файлы
- Редактируются на лету без перекомпиляции

---

## Проверка лицензии

```python
from bot_engine.ai import check_premium_license

if check_premium_license():
    # Премиум функции доступны
    from bot_engine.ai.smart_money_features import SmartMoneyFeatures
    smc = SmartMoneyFeatures()
```

---

## Интеграция в торговлю

```python
from bot_engine.ai.ai_integration import get_smc_signal, should_open_position_with_ai

# SMC сигнал
signal = get_smc_signal(candles, current_price)

# Проверка входа с AI
result = should_open_position_with_ai(
    symbol='BTCUSDT',
    candles=candles,
    current_price=50000,
    direction='LONG'
)
```

---

## Тестирование

```bash
# Проверка AI системы
python scripts/verify_ai_ready.py

# Тест SMC
python bot_engine/ai/smart_money_features.py

# Тест LSTM
python bot_engine/ai/lstm_predictor.py

# Импорты
python -c "from bot_engine.ai.smart_money_features import SmartMoneyFeatures; print('OK')"
python -c "from bot_engine.ai.lstm_predictor import LSTMPredictor; print('OK')"
python -c "from bot_engine.ai.transformer_predictor import TransformerPredictor; print('OK')"
```

---

## GPU поддержка

LSTM и Transformer используют PyTorch с автоматической GPU поддержкой:

```python
# Проверка GPU
import torch
print(f"CUDA: {torch.cuda.is_available()}")
print(f"Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
```

---

## Файлы данных

```
data/ai/
├── raw/           # Сырые данные
├── feeds/         # Подготовленные фичи
├── models/        # Обученные модели
│   ├── lstm_predictor.pth
│   ├── transformer_predictor.pth
│   └── *.pkl (scalers)
└── monitoring/    # Метрики
```

---

## Ссылки

- План реализации: `AI_IMPLEMENTATION_PLAN.md` (приватный)
- Лицензирование: `license_generator/README.md`
- Архитектура: `docs/ARCHITECTURE.md`
