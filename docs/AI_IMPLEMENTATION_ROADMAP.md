# 🚀 ПЛАН ВНЕДРЕНИЯ ИИ В ТОРГОВОГО БОТА

**Дата начала:** 2025-10-17  
**Статус:** Планирование  
**Подход:** Собственные модели (бесплатно)

---

## 🎯 ЦЕЛИ ПРОЕКТА

### **Модули ИИ (приоритеты):**

1. **🥇 LSTM Predictor** - предсказание направления движения цены
2. **🥈 Pattern Recognition (CNN)** - распознавание графических паттернов
3. **🥉 Dynamic Risk Management (LSTM+RL)** - умный SL/TP
4. **🏅 Anomaly Detection** - улучшение ExitScam фильтра

---

## 📅 ДЕТАЛЬНЫЙ ПЛАН (8-10 недель)

### **ФАЗА 1: Сбор и подготовка данных (1-2 недели)**

#### **Неделя 1: Сбор исторических данных**

**Задачи:**
1. Скачать исторические свечи 6H для всех монет (1-2 года)
2. Собрать данные о сделках (если есть история торговли)
3. Создать unified датасет

**Структура данных:**
```
data/
  ai/
    historical/
      BTC_6h_2023-2025.csv
      ETH_6h_2023-2025.csv
      ...
    training/
      dataset_lstm.npz
      dataset_pattern.npz
      dataset_risk.npz
    models/
      lstm_predictor_v1.h5
      pattern_detector_v1.h5
      risk_manager_v1.h5
```

**Скрипт для сбора:**
```python
# scripts/ai/collect_historical_data.py
"""
Скрипт для сбора исторических данных с биржи
"""

import sys
sys.path.append('.')

from exchanges.exchange_factory import ExchangeFactory
from app.config import EXCHANGES
import pandas as pd
from datetime import datetime, timedelta
import time

def collect_data_for_coin(exchange, symbol, start_date, end_date):
    """Собирает данные для одной монеты"""
    print(f"[{symbol}] Сбор данных с {start_date} по {end_date}...")
    
    all_candles = []
    current_date = start_date
    
    while current_date < end_date:
        # Запрашиваем данные пакетами по 1000 свечей
        response = exchange.get_chart_data(symbol, '6h', '60d')
        
        if response and response['success']:
            candles = response['data']['candles']
            all_candles.extend(candles)
            print(f"[{symbol}] Получено {len(candles)} свечей")
        
        time.sleep(0.5)  # Rate limiting
        current_date += timedelta(days=60)
    
    # Сохраняем в CSV
    df = pd.DataFrame(all_candles)
    df.to_csv(f'data/ai/historical/{symbol}_6h_2023-2025.csv', index=False)
    print(f"[{symbol}] ✅ Сохранено {len(all_candles)} свечей")
    
    return len(all_candles)

def main():
    # Инициализируем биржу
    exchange = ExchangeFactory.create_exchange(
        'BYBIT',
        EXCHANGES['BYBIT']['api_key'],
        EXCHANGES['BYBIT']['api_secret']
    )
    
    # Получаем список всех монет
    from bots_modules.sync_and_cache import load_bots_state
    load_bots_state()
    
    # Список топ монет для обучения (начнем с них)
    priority_symbols = [
        'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'DOT', 'LINK', 'MATIC',
        'AVAX', 'UNI', 'ATOM', 'XRP', 'DOGE', 'SHIB', 'APE', 'SAND'
    ]
    
    # Даты сбора
    start_date = datetime(2023, 1, 1)
    end_date = datetime.now()
    
    print(f"Сбор данных для {len(priority_symbols)} монет")
    print(f"Период: {start_date} - {end_date}")
    print()
    
    for symbol in priority_symbols:
        try:
            count = collect_data_for_coin(exchange, symbol, start_date, end_date)
            print(f"✅ {symbol}: {count} свечей")
        except Exception as e:
            print(f"❌ {symbol}: Ошибка - {e}")
        print()

if __name__ == '__main__':
    main()
```

**Запуск:**
```bash
python scripts/ai/collect_historical_data.py
```

**Ожидаемый результат:**
- ~3000-4000 свечей на монету (2 года * 6H)
- ~50-100 монет
- ~150,000-400,000 свечей всего

---

#### **Неделя 2: Подготовка датасета**

**Задачи:**
1. Создать признаки (features) для обучения
2. Разметить данные (labels)
3. Разделить на train/val/test

**Скрипт подготовки:**
```python
# scripts/ai/prepare_dataset.py
import numpy as np
import pandas as pd

def calculate_features(candles):
    """Вычисляет признаки для ML"""
    closes = [c['close'] for c in candles]
    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]
    volumes = [c['volume'] for c in candles]
    
    features = []
    
    # 1. RSI (14)
    rsi = calculate_rsi(closes, 14)
    features.append(rsi)
    
    # 2. EMA (50, 200)
    ema_50 = calculate_ema(closes, 50)
    ema_200 = calculate_ema(closes, 200)
    features.append(ema_50)
    features.append(ema_200)
    features.append(ema_50 / ema_200)  # Отношение
    
    # 3. Volatility (волатильность)
    volatility = np.std(closes[-20:]) / np.mean(closes[-20:])
    features.append(volatility)
    
    # 4. Price momentum (импульс)
    momentum_5 = (closes[-1] - closes[-5]) / closes[-5]
    momentum_10 = (closes[-1] - closes[-10]) / closes[-10]
    features.append(momentum_5)
    features.append(momentum_10)
    
    # 5. Volume trend (тренд объема)
    volume_sma = np.mean(volumes[-20:])
    volume_ratio = volumes[-1] / volume_sma
    features.append(volume_ratio)
    
    # 6. High-Low spread
    hl_spread = (highs[-1] - lows[-1]) / closes[-1]
    features.append(hl_spread)
    
    # 7. Distance from EMA
    dist_from_ema50 = (closes[-1] - ema_50) / ema_50
    dist_from_ema200 = (closes[-1] - ema_200) / ema_200
    features.append(dist_from_ema50)
    features.append(dist_from_ema200)
    
    # Всего: ~15-20 признаков
    
    return np.array(features)

def create_labels(candles, horizon=6):
    """Создает метки для обучения"""
    # Смотрим что произошло через N свечей
    current_price = candles[-horizon]['close']
    future_price = candles[-1]['close']
    
    change_percent = (future_price - current_price) / current_price * 100
    
    # Классификация:
    if change_percent > 2:
        return 'UP'  # Рост > 2%
    elif change_percent < -2:
        return 'DOWN'  # Падение > 2%
    else:
        return 'NEUTRAL'  # Боковик

def prepare_dataset():
    """Подготавливает датасет для обучения"""
    all_data = []
    
    for csv_file in Path('data/ai/historical').glob('*.csv'):
        df = pd.read_csv(csv_file)
        
        # Скользящее окно: 60 свечей → предсказание
        for i in range(60, len(df) - 6):
            candles_window = df.iloc[i-60:i].to_dict('records')
            future_candles = df.iloc[i:i+6].to_dict('records')
            
            features = calculate_features(candles_window)
            label = create_labels(future_candles, horizon=6)
            
            all_data.append({
                'features': features,
                'label': label,
                'symbol': csv_file.stem.split('_')[0]
            })
    
    # Сохраняем
    np.savez('data/ai/training/dataset_lstm.npz', data=all_data)
    print(f"✅ Создан датасет: {len(all_data)} примеров")
```

---

### **ФАЗА 2: LSTM Predictor (2-3 недели)**

#### **Неделя 3: Создание и обучение LSTM**

**Архитектура:**
```python
# bot_engine/ai/lstm_predictor.py
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

class LSTMPricePredictor:
    """LSTM модель для предсказания движения цены"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.sequence_length = 60  # 60 свечей = 15 дней на 6H
        
    def build_model(self, input_shape):
        """Строит архитектуру LSTM"""
        model = Sequential([
            # Первый LSTM слой
            LSTM(128, return_sequences=True, input_shape=input_shape),
            Dropout(0.3),
            BatchNormalization(),
            
            # Второй LSTM слой
            LSTM(64, return_sequences=True),
            Dropout(0.3),
            BatchNormalization(),
            
            # Третий LSTM слой
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            
            # Полносвязные слои
            Dense(16, activation='relu'),
            Dropout(0.2),
            
            # Выход: 3 класса (UP, DOWN, NEUTRAL)
            Dense(3, activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def train(self, X_train, y_train, X_val, y_val, epochs=100):
        """Обучает модель"""
        self.model = self.build_model((X_train.shape[1], X_train.shape[2]))
        
        callbacks = [
            EarlyStopping(patience=10, restore_best_weights=True),
            ModelCheckpoint('data/ai/models/lstm_best.h5', save_best_only=True)
        ]
        
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=32,
            callbacks=callbacks,
            verbose=1
        )
        
        return history
    
    def predict(self, candles):
        """Предсказывает направление движения"""
        # Подготовка данных
        features = self.prepare_sequence(candles)
        
        # Предсказание
        prediction = self.model.predict(features, verbose=0)[0]
        
        # prediction = [prob_UP, prob_DOWN, prob_NEUTRAL]
        direction_idx = np.argmax(prediction)
        directions = ['UP', 'DOWN', 'NEUTRAL']
        
        return {
            'direction': directions[direction_idx],
            'confidence': float(prediction[direction_idx]),
            'probabilities': {
                'UP': float(prediction[0]),
                'DOWN': float(prediction[1]),
                'NEUTRAL': float(prediction[2])
            }
        }
```

**Скрипт обучения:**
```python
# scripts/ai/train_lstm.py
"""
Обучение LSTM модели для предсказания движения цены
"""

from bot_engine.ai.lstm_predictor import LSTMPricePredictor
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def load_and_prepare_data():
    """Загружает и подготавливает данные"""
    # Загружаем датасет
    data = np.load('data/ai/training/dataset_lstm.npz', allow_pickle=True)['data']
    
    X = []
    y = []
    
    for sample in data:
        X.append(sample['features'])
        
        # One-hot encoding для меток
        label = sample['label']
        if label == 'UP':
            y.append([1, 0, 0])
        elif label == 'DOWN':
            y.append([0, 1, 0])
        else:
            y.append([0, 0, 1])
    
    X = np.array(X)
    y = np.array(y)
    
    # Нормализация
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X.reshape(-1, X.shape[-1])).reshape(X.shape)
    
    # Разделение на train/val/test
    X_train, X_temp, y_train, y_temp = train_test_split(X_scaled, y, test_size=0.3)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5)
    
    return X_train, y_train, X_val, y_val, X_test, y_test, scaler

def main():
    print("🚀 Начинаем обучение LSTM модели...")
    
    # Загружаем данные
    X_train, y_train, X_val, y_val, X_test, y_test, scaler = load_and_prepare_data()
    
    print(f"📊 Размеры датасета:")
    print(f"   Train: {X_train.shape}")
    print(f"   Val: {X_val.shape}")
    print(f"   Test: {X_test.shape}")
    
    # Создаем и обучаем модель
    predictor = LSTMPricePredictor()
    history = predictor.train(X_train, y_train, X_val, y_val, epochs=100)
    
    # Оценка на тестовых данных
    test_loss, test_accuracy = predictor.model.evaluate(X_test, y_test)
    print(f"✅ Точность на тестовых данных: {test_accuracy*100:.2f}%")
    
    # Сохраняем модель
    predictor.model.save('data/ai/models/lstm_predictor_v1.h5')
    
    # Сохраняем scaler
    import joblib
    joblib.dump(scaler, 'data/ai/models/scaler.pkl')
    
    print("✅ Модель обучена и сохранена!")

if __name__ == '__main__':
    main()
```

---

#### **Неделя 4: Интеграция LSTM в бота**

**Создаем модуль:**
```python
# bot_engine/ai/ai_manager.py
"""
Менеджер ИИ модулей
"""

from .lstm_predictor import LSTMPricePredictor
from bot_engine.bot_config import SystemConfig
import logging

logger = logging.getLogger('AI')

class AIManager:
    """Управление всеми ИИ модулями"""
    
    def __init__(self):
        self.lstm_predictor = None
        self.pattern_detector = None
        self.risk_manager = None
        self.anomaly_detector = None
        
        # Загружаем модули согласно конфигурации
        self.load_modules()
    
    def load_modules(self):
        """Загружает ИИ модули согласно настройкам"""
        if SystemConfig.AI_LSTM_ENABLED:
            try:
                self.lstm_predictor = LSTMPricePredictor()
                self.lstm_predictor.load_model('data/ai/models/lstm_predictor_v1.h5')
                logger.info("[AI] ✅ LSTM Predictor загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки LSTM: {e}")
        
        if SystemConfig.AI_PATTERN_ENABLED:
            try:
                from .pattern_detector import PatternDetector
                self.pattern_detector = PatternDetector()
                logger.info("[AI] ✅ Pattern Detector загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Pattern Detector: {e}")
        
        if SystemConfig.AI_RISK_MANAGEMENT_ENABLED:
            try:
                from .risk_manager import DynamicRiskManager
                self.risk_manager = DynamicRiskManager()
                logger.info("[AI] ✅ Risk Manager загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Risk Manager: {e}")
        
        if SystemConfig.AI_ANOMALY_DETECTION_ENABLED:
            try:
                from .anomaly_detector import AnomalyDetector
                self.anomaly_detector = AnomalyDetector()
                logger.info("[AI] ✅ Anomaly Detector загружен")
            except Exception as e:
                logger.error(f"[AI] ❌ Ошибка загрузки Anomaly Detector: {e}")
    
    def analyze_coin(self, symbol, coin_data, candles):
        """Комплексный анализ монеты всеми ИИ модулями"""
        analysis = {
            'lstm_prediction': None,
            'pattern_analysis': None,
            'risk_analysis': None,
            'anomaly_score': None
        }
        
        # LSTM предсказание
        if self.lstm_predictor:
            try:
                lstm_pred = self.lstm_predictor.predict(candles)
                analysis['lstm_prediction'] = lstm_pred
                logger.info(f"[AI] {symbol} LSTM: {lstm_pred['direction']} ({lstm_pred['confidence']:.2%})")
            except Exception as e:
                logger.error(f"[AI] Ошибка LSTM для {symbol}: {e}")
        
        # Распознавание паттернов
        if self.pattern_detector:
            try:
                pattern = self.pattern_detector.detect(candles)
                analysis['pattern_analysis'] = pattern
                if pattern['pattern_found']:
                    logger.info(f"[AI] {symbol} Pattern: {pattern['pattern_found']} ({pattern['confidence']:.2%})")
            except Exception as e:
                logger.error(f"[AI] Ошибка Pattern для {symbol}: {e}")
        
        # Динамический риск-менеджмент
        if self.risk_manager and coin_data.get('in_position'):
            try:
                risk = self.risk_manager.analyze(symbol, coin_data, candles)
                analysis['risk_analysis'] = risk
                logger.info(f"[AI] {symbol} Risk: {risk['hold_recommendation']}")
            except Exception as e:
                logger.error(f"[AI] Ошибка Risk для {symbol}: {e}")
        
        # Обнаружение аномалий
        if self.anomaly_detector:
            try:
                anomaly = self.anomaly_detector.detect(candles)
                analysis['anomaly_score'] = anomaly
                if anomaly['is_anomaly']:
                    logger.warning(f"[AI] {symbol} Anomaly: {anomaly['anomaly_type']} ({anomaly['severity']:.2%})")
            except Exception as e:
                logger.error(f"[AI] Ошибка Anomaly для {symbol}: {e}")
        
        return analysis
    
    def get_final_recommendation(self, symbol, system_signal, ai_analysis):
        """Объединяет системный сигнал и ИИ анализ"""
        
        # Если ИИ не активен, возвращаем системный сигнал
        if not any([
            ai_analysis['lstm_prediction'],
            ai_analysis['pattern_analysis'],
            ai_analysis['anomaly_score']
        ]):
            return {
                'signal': system_signal,
                'confidence': 0.5,
                'source': 'SYSTEM',
                'ai_enabled': False
            }
        
        # Взвешенное голосование
        votes = {'ENTER_LONG': 0, 'ENTER_SHORT': 0, 'WAIT': 0}
        total_weight = 0
        
        # Системный сигнал (вес = 1.0)
        votes[system_signal] += 1.0
        total_weight += 1.0
        
        # LSTM предсказание (вес = 1.5 если уверенность > 0.7)
        if ai_analysis['lstm_prediction']:
            lstm = ai_analysis['lstm_prediction']
            weight = 1.5 if lstm['confidence'] > 0.7 else 0.8
            
            if lstm['direction'] == 'UP' and system_signal == 'ENTER_LONG':
                votes['ENTER_LONG'] += weight
            elif lstm['direction'] == 'DOWN' and system_signal == 'ENTER_SHORT':
                votes['ENTER_SHORT'] += weight
            elif lstm['confidence'] > 0.8:
                # LSTM очень уверен - даем ему больше веса
                votes['WAIT'] += weight
            
            total_weight += weight
        
        # Pattern recognition (вес = 1.0)
        if ai_analysis['pattern_analysis']:
            pattern = ai_analysis['pattern_analysis']
            
            if pattern['pattern_found'] in ['BULLISH_FLAG', 'DOUBLE_BOTTOM']:
                votes['ENTER_LONG'] += 1.0 * pattern['confidence']
            elif pattern['pattern_found'] in ['BEARISH_FLAG', 'DOUBLE_TOP']:
                votes['ENTER_SHORT'] += 1.0 * pattern['confidence']
            
            total_weight += 1.0
        
        # Anomaly detection (вес = 2.0 - очень важно!)
        if ai_analysis['anomaly_score']:
            anomaly = ai_analysis['anomaly_score']
            
            if anomaly['is_anomaly'] and anomaly['severity'] > 0.7:
                # Аномалия обнаружена - блокируем вход!
                votes['WAIT'] += 2.0
                total_weight += 2.0
        
        # Определяем финальный сигнал
        final_signal = max(votes, key=votes.get)
        confidence = votes[final_signal] / total_weight
        
        return {
            'signal': final_signal,
            'confidence': confidence,
            'source': 'AI_ENSEMBLE',
            'votes': votes,
            'system_signal': system_signal,
            'ai_enabled': True
        }

# Глобальный экземпляр
ai_manager = None

def get_ai_manager():
    """Получает глобальный экземпляр AI Manager"""
    global ai_manager
    if ai_manager is None:
        ai_manager = AIManager()
    return ai_manager
```

**Интеграция в фильтры:**
```python
# bots_modules/filters.py

def get_coin_rsi_data(symbol, exchange_obj=None):
    # ... существующая логика получения RSI, тренда, фильтров ...
    
    # После всех фильтров - добавляем ИИ анализ
    if SystemConfig.AI_ENABLED:
        from bot_engine.ai.ai_manager import get_ai_manager
        
        try:
            ai_manager = get_ai_manager()
            
            # Получаем свечи для ИИ анализа
            if candles and len(candles) >= 60:
                ai_analysis = ai_manager.analyze_coin(symbol, coin_data, candles)
                
                # Получаем финальную рекомендацию
                final_recommendation = ai_manager.get_final_recommendation(
                    symbol, 
                    signal,  # Системный сигнал
                    ai_analysis
                )
                
                # Добавляем ИИ анализ в результат
                coin_data['ai_analysis'] = ai_analysis
                coin_data['ai_recommendation'] = final_recommendation
                
                # Если ИИ меняет сигнал
                if final_recommendation['signal'] != signal:
                    logger.info(f"[AI] {symbol}: Системный сигнал {signal} → ИИ рекомендует {final_recommendation['signal']} (уверенность: {final_recommendation['confidence']:.2%})")
                    
                    # Применяем рекомендацию ИИ если уверенность высокая
                    if final_recommendation['confidence'] > SystemConfig.AI_CONFIDENCE_THRESHOLD:
                        signal = final_recommendation['signal']
                        coin_data['signal_source'] = 'AI'
        
        except Exception as e:
            logger.error(f"[AI] Ошибка анализа {symbol}: {e}")
    
    return coin_data
```

---

### **ФАЗА 3: Pattern Recognition (2 недели)**

#### **Неделя 5-6: CNN для паттернов**

```python
# bot_engine/ai/pattern_detector.py
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
import cv2
import numpy as np

class PatternDetector:
    """CNN модель для распознавания графических паттернов"""
    
    def __init__(self):
        self.model = None
        self.pattern_types = [
            'BULLISH_FLAG',
            'BEARISH_FLAG',
            'DOUBLE_BOTTOM',
            'DOUBLE_TOP',
            'HEAD_SHOULDERS',
            'INVERSE_HEAD_SHOULDERS',
            'ASCENDING_TRIANGLE',
            'DESCENDING_TRIANGLE',
            'NO_PATTERN'
        ]
    
    def build_model(self):
        """Строит CNN для распознавания паттернов"""
        model = Sequential([
            Conv2D(32, (3, 3), activation='relu', input_shape=(64, 64, 1)),
            MaxPooling2D((2, 2)),
            
            Conv2D(64, (3, 3), activation='relu'),
            MaxPooling2D((2, 2)),
            
            Conv2D(128, (3, 3), activation='relu'),
            MaxPooling2D((2, 2)),
            
            Flatten(),
            Dense(128, activation='relu'),
            Dropout(0.5),
            Dense(len(self.pattern_types), activation='softmax')
        ])
        
        model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def candles_to_image(self, candles):
        """Преобразует свечи в изображение для CNN"""
        # Создаем изображение графика 64x64
        img = np.zeros((64, 64))
        
        # Нормализуем цены
        prices = [c['close'] for c in candles]
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price
        
        # Рисуем свечи
        for i, candle in enumerate(candles[-64:]):
            x = i
            y_close = int((candle['close'] - min_price) / price_range * 63)
            y_high = int((candle['high'] - min_price) / price_range * 63)
            y_low = int((candle['low'] - min_price) / price_range * 63)
            
            # Рисуем тело свечи
            img[y_low:y_high, x] = 0.5
            img[y_close, x] = 1.0  # Закрытие ярче
        
        return img.reshape(64, 64, 1)
    
    def detect(self, candles):
        """Обнаруживает паттерны на свечах"""
        if len(candles) < 64:
            return {
                'pattern_found': None,
                'confidence': 0.0
            }
        
        # Преобразуем в изображение
        img = self.candles_to_image(candles)
        
        # Предсказание
        prediction = self.model.predict(np.array([img]), verbose=0)[0]
        
        pattern_idx = np.argmax(prediction)
        pattern_name = self.pattern_types[pattern_idx]
        
        if pattern_name == 'NO_PATTERN':
            return {
                'pattern_found': None,
                'confidence': 0.0
            }
        
        # Определяем уровни поддержки/сопротивления
        support, resistance = self.find_support_resistance(candles)
        
        return {
            'pattern_found': pattern_name,
            'confidence': float(prediction[pattern_idx]),
            'support_level': support,
            'resistance_level': resistance,
            'breakout_probability': self.calculate_breakout_probability(candles, pattern_name)
        }
    
    def find_support_resistance(self, candles):
        """Находит уровни поддержки и сопротивления"""
        lows = [c['low'] for c in candles[-20:]]
        highs = [c['high'] for c in candles[-20:]]
        
        # Простой метод: локальные минимумы/максимумы
        support = np.percentile(lows, 10)  # 10-й процентиль
        resistance = np.percentile(highs, 90)  # 90-й процентиль
        
        return support, resistance
```

---

### **ФАЗА 4: Dynamic Risk Management (2 недели)**

#### **Неделя 7-8: Умный SL/TP**

```python
# bot_engine/ai/risk_manager.py
"""
Динамический риск-менеджмент на основе ИИ
"""

import numpy as np
from tensorflow.keras.models import load_model

class DynamicRiskManager:
    """Управление рисками с помощью ИИ"""
    
    def __init__(self):
        self.model = None
        # Можно использовать LSTM или простую модель
    
    def analyze_position(self, symbol, coin_data, candles):
        """Анализирует текущую позицию и дает рекомендации"""
        
        # Текущая позиция
        entry_price = coin_data.get('entry_price')
        current_price = coin_data.get('price')
        position_side = coin_data.get('position_side')
        
        if not entry_price or not position_side:
            return None
        
        # Вычисляем текущие метрики
        pnl_percent = self.calculate_pnl_percent(
            entry_price, current_price, position_side
        )
        
        # Анализируем волатильность
        volatility = self.calculate_volatility(candles)
        
        # Предсказываем вероятность разворота
        reversal_prob = self.predict_reversal(candles, position_side)
        
        # Рекомендуемый SL на основе волатильности
        recommended_sl = self.calculate_dynamic_sl(
            entry_price, volatility, position_side
        )
        
        # Рекомендуемый TP
        recommended_tp = self.calculate_dynamic_tp(
            entry_price, volatility, pnl_percent, position_side
        )
        
        # Оптимальное расстояние trailing stop
        trailing_distance = self.calculate_optimal_trailing(
            volatility, pnl_percent
        )
        
        # Общая рекомендация
        hold_recommendation = self.get_hold_recommendation(
            pnl_percent, reversal_prob, volatility
        )
        
        return {
            'recommended_sl': recommended_sl,
            'recommended_tp': recommended_tp,
            'trailing_distance': trailing_distance,
            'exit_probability': reversal_prob,
            'hold_recommendation': hold_recommendation,
            'volatility': volatility,
            'current_pnl_percent': pnl_percent
        }
    
    def calculate_dynamic_sl(self, entry_price, volatility, position_side):
        """Динамический стоп-лосс на основе волатильности"""
        # Базовый SL = 15%
        base_sl_percent = 15.0
        
        # Корректируем на основе волатильности
        # Высокая волатильность → больше SL (чтобы не выбило)
        # Низкая волатильность → меньше SL (меньше риск)
        volatility_multiplier = 1.0 + (volatility - 0.05) * 2
        
        adjusted_sl_percent = base_sl_percent * volatility_multiplier
        adjusted_sl_percent = np.clip(adjusted_sl_percent, 8.0, 25.0)
        
        if position_side == 'LONG':
            sl_price = entry_price * (1 - adjusted_sl_percent / 100)
        else:
            sl_price = entry_price * (1 + adjusted_sl_percent / 100)
        
        return sl_price
    
    def predict_reversal(self, candles, position_side):
        """Предсказывает вероятность разворота"""
        # Используем LSTM для предсказания разворота
        # Или простой алгоритм на основе индикаторов
        
        # Простая версия:
        closes = [c['close'] for c in candles[-10:]]
        
        # Проверяем дивергенцию с RSI
        rsi_values = [calculate_rsi(candles[:i+1]) for i in range(-10, 0)]
        
        if position_side == 'LONG':
            # Ищем медвежью дивергенцию
            price_trend = closes[-1] > closes[0]
            rsi_trend = rsi_values[-1] < rsi_values[0]
            
            if price_trend and not rsi_trend:
                return 0.8  # Высокая вероятность разворота вниз
        else:
            # Ищем бычью дивергенцию
            price_trend = closes[-1] < closes[0]
            rsi_trend = rsi_values[-1] > rsi_values[0]
            
            if price_trend and not rsi_trend:
                return 0.8  # Высокая вероятность разворота вверх
        
        return 0.2  # Низкая вероятность разворота
    
    def get_hold_recommendation(self, pnl_percent, reversal_prob, volatility):
        """Дает рекомендацию HOLD/EXIT/MOVE_SL"""
        
        # Высокая вероятность разворота → EXIT
        if reversal_prob > 0.7:
            return 'EXIT'
        
        # Большая прибыль и средняя вероятность разворота → MOVE_SL
        if pnl_percent > 50 and reversal_prob > 0.4:
            return 'MOVE_SL'
        
        # Иначе держим
        return 'HOLD'
```

---

### **ФАЗА 5: Anomaly Detection (1 неделя)**

#### **Неделя 9: Обнаружение аномалий для ExitScam**

```python
# bot_engine/ai/anomaly_detector.py
"""
Обнаружение аномалий (pump/dump) с помощью Isolation Forest
"""

from sklearn.ensemble import IsolationForest
import numpy as np
import joblib

class AnomalyDetector:
    """Детектор аномалий для ExitScam фильтра"""
    
    def __init__(self):
        self.model = IsolationForest(
            contamination=0.1,  # 10% данных считаем аномалиями
            random_state=42
        )
        self.scaler = None
        
        # Попытка загрузить обученную модель
        try:
            self.model = joblib.load('data/ai/models/anomaly_detector.pkl')
            self.scaler = joblib.load('data/ai/models/anomaly_scaler.pkl')
        except:
            pass
    
    def extract_features(self, candles):
        """Извлекает признаки для детекции аномалий"""
        if len(candles) < 20:
            return None
        
        recent = candles[-20:]
        
        features = []
        
        # 1. Резкие изменения цены
        for i in range(1, len(recent)):
            change = (recent[i]['close'] - recent[i-1]['close']) / recent[i-1]['close'] * 100
            features.append(abs(change))
        
        # 2. Объем относительно средного
        volumes = [c['volume'] for c in recent]
        avg_volume = np.mean(volumes[:-1])
        volume_spike = volumes[-1] / avg_volume if avg_volume > 0 else 1.0
        features.append(volume_spike)
        
        # 3. Волатильность
        closes = [c['close'] for c in recent]
        volatility = np.std(closes) / np.mean(closes)
        features.append(volatility)
        
        # 4. Размах свечи
        for candle in recent[-5:]:
            candle_range = (candle['high'] - candle['low']) / candle['close']
            features.append(candle_range)
        
        return np.array(features).reshape(1, -1)
    
    def detect(self, candles):
        """Обнаруживает аномалии"""
        features = self.extract_features(candles)
        
        if features is None:
            return {
                'is_anomaly': False,
                'severity': 0.0,
                'anomaly_type': None
            }
        
        # Нормализация
        if self.scaler:
            features = self.scaler.transform(features)
        
        # Предсказание (-1 = аномалия, 1 = нормально)
        prediction = self.model.predict(features)[0]
        
        is_anomaly = prediction == -1
        
        # Вычисляем severity (насколько сильная аномалия)
        anomaly_score = self.model.score_samples(features)[0]
        severity = 1.0 - (anomaly_score + 0.5)  # Нормализуем к 0-1
        
        # Определяем тип аномалии
        anomaly_type = None
        if is_anomaly:
            # Смотрим на последние свечи
            last_changes = [
                (candles[-i]['close'] - candles[-i-1]['close']) / candles[-i-1]['close'] * 100
                for i in range(1, min(6, len(candles)))
            ]
            
            if all(c > 5 for c in last_changes):
                anomaly_type = 'PUMP'  # Резкий рост
            elif all(c < -5 for c in last_changes):
                anomaly_type = 'DUMP'  # Резкое падение
            else:
                anomaly_type = 'MANIPULATION'  # Другая аномалия
        
        return {
            'is_anomaly': is_anomaly,
            'severity': float(severity),
            'anomaly_type': anomaly_type,
            'anomaly_score': float(anomaly_score)
        }
```

---

### **ФАЗА 6: Reinforcement Learning (опционально, 3-4 недели)**

#### **Неделя 10-13: RL для оптимизации параметров**

**НЕ для принятия торговых решений, а для оптимизации параметров!**

```python
# bot_engine/ai/rl_optimizer.py
"""
RL агент для оптимизации параметров бота
"""

import gym
from stable_baselines3 import PPO
import numpy as np

class ParameterOptimizationEnv(gym.Env):
    """Среда для обучения RL агента оптимизировать параметры"""
    
    def __init__(self, historical_data):
        super().__init__()
        self.historical_data = historical_data
        
        # Action space: параметры бота
        self.action_space = gym.spaces.Box(
            low=np.array([25, 73, 1, 8, 200]),  # min значения
            high=np.array([30, 75, 5, 20, 400]),  # max значения
            dtype=np.float32
        )
        # [rsi_long, rsi_short, trend_bars, stop_loss, trailing_activation]
        
        # Observation space: состояние рынка
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(20,),  # 20 признаков
            dtype=np.float32
        )
    
    def step(self, action):
        """Выполняет шаг: применяет параметры и симулирует торговлю"""
        # action = новые параметры
        rsi_long, rsi_short, trend_bars, stop_loss, trailing = action
        
        # Симулируем торговлю с этими параметрами на исторических данных
        trades = self.simulate_trading_with_params({
            'rsi_long_threshold': int(rsi_long),
            'rsi_short_threshold': int(rsi_short),
            'trend_confirmation_bars': int(trend_bars),
            'max_loss_percent': stop_loss,
            'trailing_activation': trailing
        })
        
        # Вычисляем награду
        total_pnl = sum(t['pnl'] for t in trades)
        win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades)
        
        reward = total_pnl + (win_rate * 100)  # Комбинируем PnL и win rate
        
        # Новое состояние
        observation = self.get_market_state()
        
        done = self.current_step >= len(self.historical_data)
        
        return observation, reward, done, {}
    
    def simulate_trading_with_params(self, params):
        """Симулирует торговлю с заданными параметрами"""
        # Здесь используем твою существующую логику
        # но с параметрами от RL агента
        trades = []
        
        for candle_idx in range(100, len(self.historical_data) - 10):
            candles = self.historical_data[:candle_idx]
            
            # Применяем фильтры с параметрами от RL
            signal = self.apply_filters(candles, params)
            
            if signal == 'ENTER_LONG':
                # Симулируем сделку
                entry = candles[-1]['close']
                
                # Находим выход (через N свечей или по SL)
                exit_result = self.find_exit(
                    candles[candle_idx:], 
                    entry, 
                    'LONG', 
                    params
                )
                
                trades.append(exit_result)
        
        return trades

# Обучение RL агента
def train_rl_optimizer():
    # Загружаем исторические данные
    historical_data = load_historical_data()
    
    # Создаем среду
    env = ParameterOptimizationEnv(historical_data)
    
    # Обучаем PPO агента
    model = PPO('MlpPolicy', env, verbose=1)
    model.learn(total_timesteps=100000)
    
    # Сохраняем
    model.save('data/ai/models/rl_optimizer.zip')
    
    # Получаем оптимальные параметры
    optimal_params = model.predict(env.reset())[0]
    
    return optimal_params
```

---

## 📋 СТРУКТУРА ПРОЕКТА

```
InfoBot/
├── bot_engine/
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── ai_manager.py          # ✅ Главный менеджер ИИ
│   │   ├── lstm_predictor.py      # ✅ LSTM предсказания
│   │   ├── pattern_detector.py    # ✅ Распознавание паттернов
│   │   ├── risk_manager.py        # ✅ Динамический риск
│   │   └── anomaly_detector.py    # ✅ Обнаружение аномалий
│   └── bot_config.py              # + AI настройки
├── data/
│   └── ai/
│       ├── historical/            # Исторические данные
│       ├── training/              # Датасеты для обучения
│       └── models/                # Обученные модели
├── scripts/
│   └── ai/
│       ├── collect_historical_data.py
│       ├── prepare_dataset.py
│       ├── train_lstm.py
│       ├── train_pattern_detector.py
│       └── train_anomaly_detector.py
└── docs/
    ├── AI_IMPLEMENTATION_ROADMAP.md
    ├── AI_INTEGRATION_IDEAS.md
    └── LSTM_VS_RL_EXPLAINED.md
```

---

## ⚙️ НАСТРОЙКИ В BOT_CONFIG.PY

```python
# bot_engine/bot_config.py

class SystemConfig:
    # ... существующие настройки ...
    
    # ==========================================
    # ИИ МОДУЛИ
    # ==========================================
    
    # Общие настройки ИИ
    AI_ENABLED = False  # Включить ИИ модули (мастер-переключатель)
    AI_CONFIDENCE_THRESHOLD = 0.65  # Минимальная уверенность для применения рекомендации ИИ
    
    # LSTM Predictor
    AI_LSTM_ENABLED = False  # Предсказание движения цены
    AI_LSTM_MODEL_PATH = 'data/ai/models/lstm_predictor_v1.h5'
    AI_LSTM_WEIGHT = 1.5  # Вес в голосовании (если уверенность > 0.7)
    
    # Pattern Recognition
    AI_PATTERN_ENABLED = False  # Распознавание паттернов
    AI_PATTERN_MODEL_PATH = 'data/ai/models/pattern_detector_v1.h5'
    AI_PATTERN_WEIGHT = 1.0
    AI_PATTERN_MIN_CONFIDENCE = 0.7
    
    # Dynamic Risk Management
    AI_RISK_MANAGEMENT_ENABLED = False  # Динамический SL/TP
    AI_RISK_MODEL_PATH = 'data/ai/models/risk_manager_v1.h5'
    AI_RISK_UPDATE_INTERVAL = 300  # Обновление каждые 5 минут
    
    # Anomaly Detection
    AI_ANOMALY_DETECTION_ENABLED = False  # Обнаружение аномалий
    AI_ANOMALY_MODEL_PATH = 'data/ai/models/anomaly_detector.pkl'
    AI_ANOMALY_BLOCK_THRESHOLD = 0.7  # Блокировать вход если аномалия > 70%
```

---

## 🎯 ПОРЯДОК РЕАЛИЗАЦИИ

### **1. НАЧАТЬ С:**
✅ **Anomaly Detection** (1 неделя) - самое простое и полезное!
- Не требует сложного обучения
- Сразу улучшает ExitScam фильтр
- Можно обучить за 1 день

### **2. ЗАТЕМ:**
✅ **LSTM Predictor** (2-3 недели)
- Основной модуль
- Предсказывает движение цены
- Дополняет существующую логику

### **3. ПОТОМ:**
✅ **Pattern Recognition** (2 недели)
- Находит графические паттерны
- Дополнительный фильтр

### **4. В КОНЦЕ:**
✅ **Dynamic Risk Management** (2 недели)
- Оптимизирует SL/TP
- Предсказывает развороты

---

## 💰 СТОИМОСТЬ

### **Разработка:**
- Твое время: ~8-10 недель
- GPU для обучения: $0 (можно на CPU) или $50-100 (аренда GPU в облаке)

### **Эксплуатация:**
- **$0/месяц** - все модели локальные!

### **Сравнение с Claude:**
- Claude: $12/месяц
- Твои модели: $0/месяц
- Окупаемость: через 4-6 месяцев (с учетом времени разработки)

---

## ✅ ПРЕИМУЩЕСТВА СОБСТВЕННЫХ МОДЕЛЕЙ

1. ✅ **Бесплатно** - никаких ежемесячных платежей
2. ✅ **Полный контроль** - ты знаешь как все работает
3. ✅ **Приватность** - данные не уходят на внешние API
4. ✅ **Кастомизация** - можешь обучить под свою стратегию
5. ✅ **Оффлайн** - работает без интернета
6. ✅ **Обучение** - ты освоишь ML/Deep Learning

---

## 🚀 ГОТОВ НАЧАТЬ?

**Хочешь чтобы я:**
1. Создал скрипт сбора исторических данных?
2. Реализовал Anomaly Detector (самый простой старт)?
3. Создал базовую структуру всех ИИ модулей?

**С чего начнем?** 🎯

