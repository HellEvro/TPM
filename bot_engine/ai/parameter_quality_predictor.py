#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML модель для предсказания качества параметров торговли

Обучается на успешных/неуспешных параметрах и предсказывает:
- Вероятность успеха параметров
- Ожидаемый Win Rate
- Ожидаемый PnL

Используется для генерации оптимальных параметров вместо случайных
"""

import os
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib

logger = logging.getLogger('AI.ParameterQualityPredictor')


class ParameterQualityPredictor:
    """
    ML модель для предсказания качества параметров торговли
    """
    
    def __init__(self, data_dir: str = 'data/ai'):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self.model_file = os.path.join(data_dir, 'parameter_quality_predictor.pkl')
        self.scaler_file = os.path.join(data_dir, 'parameter_quality_scaler.pkl')
        self.training_data_file = os.path.join(data_dir, 'parameter_training_data.json')
        
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Загружаем модель если есть
        self._load_model()
    
    def _load_model(self):
        """Загрузить обученную модель"""
        try:
            if os.path.exists(self.model_file) and os.path.exists(self.scaler_file):
                self.model = joblib.load(self.model_file)
                self.scaler = joblib.load(self.scaler_file)
                self.is_trained = True
                logger.info("✅ Загружена модель предсказания качества параметров")
        except Exception as e:
            logger.debug(f"⚠️ Ошибка загрузки модели: {e}")
            self.is_trained = False
    
    def _save_model(self):
        """Сохранить обученную модель"""
        try:
            if self.model:
                joblib.dump(self.model, self.model_file)
                joblib.dump(self.scaler, self.scaler_file)
                logger.info("✅ Сохранена модель предсказания качества параметров")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения модели: {e}")
    
    def _extract_features(self, rsi_params: Dict, risk_params: Optional[Dict] = None) -> np.ndarray:
        """
        Извлечь признаки из параметров для обучения
        
        Args:
            rsi_params: Параметры RSI
            risk_params: Параметры риск-менеджмента (опционально)
        
        Returns:
            Массив признаков
        """
        features = [
            rsi_params.get('oversold', 29),
            rsi_params.get('overbought', 71),
            rsi_params.get('exit_long_with_trend', 65),
            rsi_params.get('exit_long_against_trend', 60),
            rsi_params.get('exit_short_with_trend', 35),
            rsi_params.get('exit_short_against_trend', 40),
        ]
        
        # Добавляем риск-параметры если есть
        if risk_params:
            features.extend([
                risk_params.get('stop_loss', 15.0),
                risk_params.get('take_profit', 20.0),
                risk_params.get('trailing_stop_activation', 30.0),
                risk_params.get('trailing_stop_distance', 5.0),
            ])
        else:
            # Заполняем нулями если нет
            features.extend([0, 0, 0, 0])
        
        return np.array(features).reshape(1, -1)
    
    def add_training_sample(self, rsi_params: Dict, win_rate: float, total_pnl: float,
                           trades_count: int, risk_params: Optional[Dict] = None,
                           symbol: Optional[str] = None, blocked: bool = False):
        """
        Добавить образец для обучения
        
        Args:
            rsi_params: Параметры RSI
            win_rate: Win Rate (0-100)
            total_pnl: Total PnL
            trades_count: Количество сделок
            risk_params: Параметры риск-менеджмента
            symbol: Символ монеты
            blocked: Были ли входы заблокированы
        """
        try:
            # Загружаем существующие данные
            training_data = []
            if os.path.exists(self.training_data_file):
                with open(self.training_data_file, 'r', encoding='utf-8') as f:
                    training_data = json.load(f)
            
            # Вычисляем качество (target для обучения)
            # Качество = комбинация win_rate, pnl, trades_count
            # Если заблокировано - качество = 0
            if blocked or trades_count == 0:
                quality = 0.0
            else:
                # Нормализуем метрики
                win_rate_norm = win_rate / 100.0  # 0-1
                pnl_norm = min(max(total_pnl / 1000.0, -1), 1)  # -1 до 1 (1000 USDT = 1.0)
                trades_norm = min(trades_count / 50.0, 1)  # 0-1 (50 сделок = 1.0)
                
                # Взвешенная сумма
                quality = (
                    win_rate_norm * 0.5 +
                    pnl_norm * 0.3 +
                    trades_norm * 0.2
                )
            
            # Добавляем образец
            sample = {
                'rsi_params': rsi_params,
                'risk_params': risk_params or {},
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'trades_count': trades_count,
                'quality': quality,
                'blocked': blocked,
                'symbol': symbol,
                'timestamp': datetime.now().isoformat()
            }
            
            training_data.append(sample)
            
            # Оставляем только последние 5000 образцов
            if len(training_data) > 5000:
                training_data = training_data[-5000:]
            
            # Сохраняем
            with open(self.training_data_file, 'w', encoding='utf-8') as f:
                json.dump(training_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"📝 Добавлен образец для обучения (quality: {quality:.3f}, win_rate: {win_rate:.1f}%)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления образца: {e}")
    
    def train(self, min_samples: int = 50) -> Optional[Dict[str, Any]]:
        """
        Обучить модель на накопленных данных
        
        Args:
            min_samples: Минимальное количество образцов для обучения
        
        Returns:
            Словарь с метриками обучения или None если обучение не удалось
        """
        try:
            if not os.path.exists(self.training_data_file):
                logger.warning("⚠️ Нет данных для обучения")
                return None
            
            with open(self.training_data_file, 'r', encoding='utf-8') as f:
                training_data = json.load(f)
            
            samples_count = len(training_data)
            if samples_count < min_samples:
                logger.warning(f"⚠️ Недостаточно данных для обучения: {samples_count}/{min_samples}")
                return {
                    'success': False,
                    'samples_count': samples_count,
                    'min_samples_required': min_samples,
                    'reason': 'not_enough_samples'
                }
            
            # Подготавливаем данные
            X = []
            y = []
            
            for sample in training_data:
                features = self._extract_features(
                    sample['rsi_params'],
                    sample.get('risk_params')
                )
                X.append(features[0])
                y.append(sample['quality'])
            
            X = np.array(X)
            y = np.array(y)
            
            # Нормализуем признаки
            X_scaled = self.scaler.fit_transform(X)
            
            # Создаем модель
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
                n_iter_no_change=10
            )
            
            # Обучаем
            logger.info(f"🎓 Обучение модели предсказания качества параметров на {len(X)} образцах...")
            self.model.fit(X_scaled, y)
            
            # Оценка качества
            train_score = self.model.score(X_scaled, y)
            logger.info(f"✅ Модель обучена! R² score: {train_score:.3f}")
            
            # Статистика по качеству образцов
            avg_quality = float(np.mean(y))
            max_quality = float(np.max(y))
            min_quality = float(np.min(y))
            blocked_count = sum(1 for s in training_data if s.get('blocked', False))
            
            self.is_trained = True
            self._save_model()
            
            return {
                'success': True,
                'samples_count': samples_count,
                'r2_score': float(train_score),
                'avg_quality': avg_quality,
                'max_quality': max_quality,
                'min_quality': min_quality,
                'blocked_samples': blocked_count,
                'successful_samples': samples_count - blocked_count
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения модели: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'reason': str(e)
            }
    
    def predict_quality(self, rsi_params: Dict, risk_params: Optional[Dict] = None) -> float:
        """
        Предсказать качество параметров
        
        Args:
            rsi_params: Параметры RSI
            risk_params: Параметры риск-менеджмента
        
        Returns:
            Предсказанное качество (0-1, где 1 = отлично)
        """
        if not self.is_trained or not self.model:
            return 0.5  # Среднее значение если модель не обучена
        
        try:
            features = self._extract_features(rsi_params, risk_params)
            features_scaled = self.scaler.transform(features)
            quality = self.model.predict(features_scaled)[0]
            return max(0.0, min(1.0, quality))  # Ограничиваем 0-1
        except Exception as e:
            logger.debug(f"⚠️ Ошибка предсказания: {e}")
            return 0.5
    
    def suggest_optimal_params(self, base_params: Dict, risk_params: Optional[Dict] = None,
                               num_suggestions: int = 10) -> List[Tuple[Dict, float]]:
        """
        Предложить оптимальные параметры на основе модели
        
        Args:
            base_params: Базовые параметры
            risk_params: Параметры риск-менеджмента
            num_suggestions: Количество предложений
        
        Returns:
            Список кортежей (параметры, предсказанное_качество)
        """
        if not self.is_trained:
            return []
        
        import random
        
        suggestions = []
        
        # Генерируем варианты и предсказываем их качество
        for _ in range(num_suggestions * 5):  # Генерируем больше, чтобы выбрать лучшие
            rsi_params = {
                'oversold': max(20, min(35, 
                    base_params.get('oversold', 29) + random.randint(-5, 5))),
                'overbought': max(65, min(80,
                    base_params.get('overbought', 71) + random.randint(-5, 5))),
                'exit_long_with_trend': max(55, min(70,
                    base_params.get('exit_long_with_trend', 65) + random.randint(-8, 8))),
                'exit_long_against_trend': max(50, min(65,
                    base_params.get('exit_long_against_trend', 60) + random.randint(-8, 8))),
                'exit_short_with_trend': max(25, min(40,
                    base_params.get('exit_short_with_trend', 35) + random.randint(-8, 8))),
                'exit_short_against_trend': max(30, min(45,
                    base_params.get('exit_short_against_trend', 40) + random.randint(-8, 8)))
            }
            
            quality = self.predict_quality(rsi_params, risk_params)
            suggestions.append((rsi_params, quality))
        
        # Сортируем по качеству и возвращаем лучшие
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:num_suggestions]

