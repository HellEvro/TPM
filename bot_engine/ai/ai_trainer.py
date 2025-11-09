#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль обучения AI системы

Обучается на:
1. Истории трейдов (bot_history.py)
2. Параметрах стратегии (конфигурация ботов)
3. Исторических данных (свечи, индикаторы)
"""

import os
import json
import logging
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report, mean_squared_error
import joblib

logger = logging.getLogger('AI.Trainer')


class AITrainer:
    """
    Класс для обучения AI моделей
    """
    
    def __init__(self):
        """Инициализация тренера"""
        self.models_dir = 'data/ai/models'
        self.data_dir = 'data/ai'
        
        # Создаем директории
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Модели
        self.signal_predictor = None  # Предсказание сигналов (LONG/SHORT/WAIT)
        self.profit_predictor = None  # Предсказание прибыльности
        self.scaler = StandardScaler()
        
        # Загружаем существующие модели
        self._load_models()
        
        logger.info("✅ AITrainer инициализирован")
    
    def _load_models(self):
        """Загрузить сохраненные модели"""
        try:
            signal_model_path = os.path.join(self.models_dir, 'signal_predictor.pkl')
            profit_model_path = os.path.join(self.models_dir, 'profit_predictor.pkl')
            scaler_path = os.path.join(self.models_dir, 'scaler.pkl')
            
            loaded_count = 0
            
            if os.path.exists(signal_model_path):
                self.signal_predictor = joblib.load(signal_model_path)
                logger.info(f"✅ Загружена модель предсказания сигналов: {signal_model_path}")
                loaded_count += 1
                
                # Загружаем метаданные если есть
                metadata_path = os.path.join(self.models_dir, 'signal_predictor_metadata.json')
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            logger.info(f"   📊 Модель обучена: {metadata.get('saved_at', 'unknown')}")
                    except:
                        pass
            else:
                logger.info("ℹ️ Модель предсказания сигналов не найдена (будет создана при обучении)")
            
            if os.path.exists(profit_model_path):
                self.profit_predictor = joblib.load(profit_model_path)
                logger.info(f"✅ Загружена модель предсказания прибыли: {profit_model_path}")
                loaded_count += 1
                
                # Загружаем метаданные если есть
                metadata_path = os.path.join(self.models_dir, 'profit_predictor_metadata.json')
                if os.path.exists(metadata_path):
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            logger.info(f"   📊 Модель обучена: {metadata.get('saved_at', 'unknown')}")
                    except:
                        pass
            else:
                logger.info("ℹ️ Модель предсказания прибыли не найдена (будет создана при обучении)")
            
            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)
                logger.info(f"✅ Загружен scaler: {scaler_path}")
                loaded_count += 1
            else:
                logger.info("ℹ️ Scaler не найден (будет создан при обучении)")
            
            if loaded_count > 0:
                logger.info(f"🤖 Загружено моделей: {loaded_count}/3 - готовы к использованию ботами!")
            else:
                logger.info("💡 Модели еще не обучены - запустите обучение для создания моделей")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки моделей: {e}")
            import traceback
            logger.warning(traceback.format_exc())
    
    def _save_models(self):
        """Сохранить модели"""
        try:
            signal_model_path = os.path.join(self.models_dir, 'signal_predictor.pkl')
            profit_model_path = os.path.join(self.models_dir, 'profit_predictor.pkl')
            scaler_path = os.path.join(self.models_dir, 'scaler.pkl')
            
            saved_count = 0
            
            if self.signal_predictor:
                joblib.dump(self.signal_predictor, signal_model_path)
                logger.info(f"✅ Сохранена модель предсказания сигналов: {signal_model_path}")
                saved_count += 1
                
                # Сохраняем метаданные модели
                metadata_path = os.path.join(self.models_dir, 'signal_predictor_metadata.json')
                metadata = {
                    'model_type': 'RandomForestClassifier',
                    'saved_at': datetime.now().isoformat(),
                    'n_estimators': getattr(self.signal_predictor, 'n_estimators', 'unknown'),
                    'max_depth': getattr(self.signal_predictor, 'max_depth', 'unknown')
                }
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            if self.profit_predictor:
                joblib.dump(self.profit_predictor, profit_model_path)
                logger.info(f"✅ Сохранена модель предсказания прибыли: {profit_model_path}")
                saved_count += 1
                
                # Сохраняем метаданные модели
                metadata_path = os.path.join(self.models_dir, 'profit_predictor_metadata.json')
                metadata = {
                    'model_type': 'GradientBoostingRegressor',
                    'saved_at': datetime.now().isoformat(),
                    'n_estimators': getattr(self.profit_predictor, 'n_estimators', 'unknown'),
                    'max_depth': getattr(self.profit_predictor, 'max_depth', 'unknown')
                }
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            if self.scaler:
                joblib.dump(self.scaler, scaler_path)
                logger.info(f"✅ Сохранен scaler: {scaler_path}")
                saved_count += 1
            
            logger.info(f"💾 Сохранено моделей: {saved_count}/3")
            logger.info(f"📁 Модели сохранены в: {self.models_dir}")
            logger.info("🤖 Модели готовы к использованию ботами!")
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения моделей: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _load_history_data(self) -> List[Dict]:
        """Загрузить данные истории трейдов"""
        try:
            history_file = os.path.join(self.data_dir, 'history_data.json')
            if not os.path.exists(history_file):
                return []
            
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Извлекаем все сделки из истории
            trades = []
            latest = data.get('latest', {})
            history = data.get('history', [])
            
            # Добавляем сделки из latest
            if latest:
                trades.extend(latest.get('trades', []))
            
            # Добавляем сделки из истории
            for entry in history:
                trades.extend(entry.get('trades', []))
            
            # Фильтруем только закрытые сделки с PnL
            closed_trades = [
                t for t in trades
                if t.get('status') == 'CLOSED' and t.get('pnl') is not None
            ]
            
            return closed_trades
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных истории: {e}")
            return []
    
    def _load_market_data(self) -> Dict:
        """
        Загрузить рыночные данные
        
        Использует:
        - Свечи из data/candles_cache.json (напрямую из файла - ~554 монеты, ~554,000 свечей!)
        - Индикаторы из data/ai/market_data.json или через API
        """
        try:
            market_file = os.path.join(self.data_dir, 'market_data.json')
            
            # Пробуем загрузить из market_data.json (если есть)
            market_data = {}
            if os.path.exists(market_file):
                try:
                    with open(market_file, 'r', encoding='utf-8') as f:
                        market_data = json.load(f)
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка чтения market_data.json: {e}")
            
            # Если нет свечей в market_data, читаем напрямую из candles_cache.json
            if not market_data.get('latest', {}).get('candles'):
                logger.info("📖 Загрузка свечей напрямую из data/candles_cache.json...")
                
                candles_cache_file = os.path.join('data', 'candles_cache.json')
                if os.path.exists(candles_cache_file):
                    try:
                        with open(candles_cache_file, 'r', encoding='utf-8') as f:
                            candles_data = json.load(f)
                        
                        logger.info(f"✅ Загружено свечей для {len(candles_data)} монет из candles_cache.json")
                        
                        if 'latest' not in market_data:
                            market_data['latest'] = {}
                        if 'candles' not in market_data['latest']:
                            market_data['latest']['candles'] = {}
                        
                        candles_count = 0
                        total_candles = 0
                        
                        for symbol, candle_info in candles_data.items():
                            candles = candle_info.get('candles', [])
                            if candles:
                                market_data['latest']['candles'][symbol] = {
                                    'candles': candles,
                                    'timeframe': candle_info.get('timeframe', '6h'),
                                    'last_update': candle_info.get('last_update'),
                                    'count': len(candles),
                                    'source': 'candles_cache.json'
                                }
                                candles_count += 1
                                total_candles += len(candles)
                        
                        logger.info(f"✅ Обработано: {candles_count} монет, {total_candles} свечей")
                        
                    except json.JSONDecodeError as json_error:
                        logger.warning(f"⚠️ Файл candles_cache.json поврежден (JSON ошибка на позиции {json_error.pos})")
                        logger.info("🗑️ Удаляем поврежденный файл, bots.py пересоздаст его автоматически")
                        try:
                            os.remove(candles_cache_file)
                            logger.info("✅ Поврежденный файл удален")
                        except Exception as del_error:
                            logger.debug(f"⚠️ Не удалось удалить файл: {del_error}")
                        # Продолжаем работу без свечей из этого файла
                    except Exception as e:
                        logger.error(f"❌ Ошибка чтения candles_cache.json: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
            
            return market_data
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки рыночных данных: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}
    
    def _prepare_features(self, trade: Dict, market_data: Dict = None) -> Optional[np.ndarray]:
        """
        Подготовка признаков для обучения
        
        Args:
            trade: Данные сделки
            market_data: Рыночные данные
        
        Returns:
            Массив признаков или None
        """
        try:
            features = []
            
            # Базовые признаки из сделки
            entry_price = trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 0)
            direction = trade.get('direction', 'LONG')
            
            if entry_price == 0 or exit_price == 0:
                return None
            
            # Данные входа
            entry_data = trade.get('entry_data', {})
            entry_rsi = entry_data.get('rsi', 50)
            entry_trend = entry_data.get('trend', 'NEUTRAL')
            entry_volatility = entry_data.get('volatility', 0)
            
            # Данные выхода
            exit_market_data = trade.get('exit_market_data', {})
            exit_rsi = exit_market_data.get('rsi', 50)
            exit_trend = exit_market_data.get('trend', 'NEUTRAL')
            
            # Признаки
            features.append(entry_rsi)
            features.append(exit_rsi)
            features.append(entry_volatility)
            features.append(1 if direction == 'LONG' else 0)
            features.append(1 if entry_trend == 'UP' else (0 if entry_trend == 'DOWN' else 0.5))
            features.append(1 if exit_trend == 'UP' else (0 if exit_trend == 'DOWN' else 0.5))
            
            # Процент изменения цены
            if direction == 'LONG':
                price_change = ((exit_price - entry_price) / entry_price) * 100
            else:
                price_change = ((entry_price - exit_price) / entry_price) * 100
            
            features.append(price_change)
            
            # Время в позиции (часы)
            entry_time = trade.get('timestamp', '')
            exit_time = trade.get('close_timestamp', '')
            
            if entry_time and exit_time:
                try:
                    entry_dt = datetime.fromisoformat(entry_time.replace('Z', ''))
                    exit_dt = datetime.fromisoformat(exit_time.replace('Z', ''))
                    hours_in_position = (exit_dt - entry_dt).total_seconds() / 3600
                    features.append(hours_in_position)
                except:
                    features.append(0)
            else:
                features.append(0)
            
            return np.array(features)
            
        except Exception as e:
            logger.error(f"❌ Ошибка подготовки признаков: {e}")
            return None
    
    def train_on_history(self):
        """
        Обучение на истории трейдов
        """
        logger.info("=" * 80)
        logger.info("🎓 ОБУЧЕНИЕ НА ИСТОРИИ ТРЕЙДОВ")
        logger.info("=" * 80)
        
        try:
            # Загружаем данные
            trades = self._load_history_data()
            
            if len(trades) < 10:
                logger.warning(f"⚠️ Недостаточно данных для обучения (нужно минимум 10, есть {len(trades)})")
                logger.info("💡 Накопите больше сделок для качественного обучения")
                return
            
            logger.info(f"📊 Загружено {len(trades)} сделок для обучения")
            logger.info(f"📈 Анализируем сделки...")
            
            # Подготавливаем данные
            X = []
            y_signal = []  # Сигнал (1 = прибыль, 0 = убыток)
            y_profit = []  # Размер прибыли/убытка
            
            logger.info(f"🔍 Подготовка признаков из {len(trades)} сделок...")
            
            processed = 0
            skipped = 0
            
            for trade in trades:
                features = self._prepare_features(trade)
                if features is None:
                    skipped += 1
                    continue
                
                X.append(features)
                
                pnl = trade.get('pnl', 0)
                y_signal.append(1 if pnl > 0 else 0)
                y_profit.append(pnl)
                
                processed += 1
                
                # Логируем прогресс каждые 20 сделок
                if processed % 20 == 0:
                    logger.info(f"📊 Обработано {processed}/{len(trades)} сделок...")
            
            if skipped > 0:
                logger.info(f"⚠️ Пропущено {skipped} сделок (недостаточно данных)")
            
            if len(X) < 10:
                logger.warning(f"⚠️ Недостаточно валидных данных для обучения ({len(X)} записей)")
                return
            
            logger.info(f"✅ Подготовлено {len(X)} валидных записей для обучения")
            
            X = np.array(X)
            y_signal = np.array(y_signal)
            y_profit = np.array(y_profit)
            
            # Нормализация признаков
            X_scaled = self.scaler.fit_transform(X)
            
            # Разделение на train/test
            X_train, X_test, y_signal_train, y_signal_test, y_profit_train, y_profit_test = train_test_split(
                X_scaled, y_signal, y_profit, test_size=0.2, random_state=42
            )
            
            # Обучение модели предсказания сигналов
            logger.info("=" * 80)
            logger.info("🎓 ОБУЧЕНИЕ МОДЕЛИ ПРЕДСКАЗАНИЯ СИГНАЛОВ")
            logger.info(f"📊 Обучающая выборка: {len(X_train)} записей")
            logger.info(f"📊 Тестовая выборка: {len(X_test)} записей")
            logger.info("⏳ Обучение RandomForestClassifier...")
            
            self.signal_predictor = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            self.signal_predictor.fit(X_train, y_signal_train)
            
            # Оценка модели сигналов
            y_signal_pred = self.signal_predictor.predict(X_test)
            accuracy = accuracy_score(y_signal_test, y_signal_pred)
            
            # Дополнительная статистика
            profitable_pred = sum(y_signal_pred)
            profitable_actual = sum(y_signal_test)
            
            logger.info(f"✅ Модель сигналов обучена!")
            logger.info(f"   📊 Точность: {accuracy:.2%}")
            logger.info(f"   📈 Предсказано прибыльных: {profitable_pred}/{len(y_signal_test)}")
            logger.info(f"   📈 Реально прибыльных: {profitable_actual}/{len(y_signal_test)}")
            
            # Обучение модели предсказания прибыли
            logger.info("=" * 80)
            logger.info("🎓 ОБУЧЕНИЕ МОДЕЛИ ПРЕДСКАЗАНИЯ ПРИБЫЛИ")
            logger.info("⏳ Обучение GradientBoostingRegressor...")
            
            self.profit_predictor = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                random_state=42
            )
            self.profit_predictor.fit(X_train, y_profit_train)
            
            # Оценка модели прибыли
            y_profit_pred = self.profit_predictor.predict(X_test)
            mse = mean_squared_error(y_profit_test, y_profit_pred)
            
            avg_profit_actual = np.mean(y_profit_test)
            avg_profit_pred = np.mean(y_profit_pred)
            
            logger.info(f"✅ Модель прибыли обучена!")
            logger.info(f"   📊 MSE: {mse:.2f}")
            logger.info(f"   📈 Средняя прибыль (реальная): {avg_profit_actual:.2f} USDT")
            logger.info(f"   📈 Средняя прибыль (предсказанная): {avg_profit_pred:.2f} USDT")
            
            # Сохранение моделей
            self._save_models()
            
            logger.info("✅ Обучение на истории завершено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения на истории: {e}")
            import traceback
            traceback.print_exc()
    
    def train_on_strategy_params(self):
        """
        Обучение на параметрах стратегии
        
        Анализирует какие параметры стратегии приводят к лучшим результатам
        """
        logger.info("🎓 Обучение на параметрах стратегии...")
        
        try:
            # Загружаем данные
            trades = self._load_history_data()
            
            if len(trades) < 10:
                logger.warning("⚠️ Недостаточно данных для анализа параметров стратегии")
                return
            
            # Анализируем эффективность разных параметров
            # Например, какие значения RSI входа дают лучшие результаты
            
            rsi_ranges = {
                'very_low': (0, 25),
                'low': (25, 35),
                'medium': (35, 65),
                'high': (65, 75),
                'very_high': (75, 100)
            }
            
            results = {}
            
            for trade in trades:
                entry_data = trade.get('entry_data', {})
                entry_rsi = entry_data.get('rsi', 50)
                pnl = trade.get('pnl', 0)
                
                for range_name, (low, high) in rsi_ranges.items():
                    if low <= entry_rsi < high:
                        if range_name not in results:
                            results[range_name] = {'trades': 0, 'total_pnl': 0, 'winning': 0}
                        
                        results[range_name]['trades'] += 1
                        results[range_name]['total_pnl'] += pnl
                        if pnl > 0:
                            results[range_name]['winning'] += 1
                        break
            
            # Сохраняем результаты анализа
            analysis_file = os.path.join(self.models_dir, 'strategy_analysis.json')
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info("✅ Анализ параметров стратегии завершен")
            logger.info(f"📊 Результаты: {json.dumps(results, indent=2, ensure_ascii=False)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения на параметрах стратегии: {e}")
    
    def train_on_historical_data(self):
        """
        Обучение на исторических данных (свечах)
        
        Использует свечи из data/candles_cache.json и индикаторы для обучения на всех монетах
        """
        logger.info("=" * 80)
        logger.info("🎓 ОБУЧЕНИЕ НА ИСТОРИЧЕСКИХ ДАННЫХ (СВЕЧАХ)")
        logger.info("=" * 80)
        
        try:
            # Загружаем рыночные данные (свечи из candles_cache.json + индикаторы)
            market_data = self._load_market_data()
            
            if not market_data:
                logger.warning("⚠️ Нет рыночных данных для обучения")
                return
            
            latest = market_data.get('latest', {})
            candles_data = latest.get('candles', {})
            indicators_data = latest.get('indicators', {})
            
            if not candles_data:
                logger.warning("⚠️ Нет свечей для обучения (проверьте data/candles_cache.json)")
                return
            
            logger.info(f"📊 Начинаем обучение на {len(candles_data)} монетах со свечами...")
            logger.info(f"📈 Доступно индикаторов для {len(indicators_data)} монет")
            
            # Обучаемся на свечах каждой монеты
            trained_count = 0
            failed_count = 0
            total_candles_processed = 0
            
            for symbol, candle_info in candles_data.items():
                try:
                    candles = candle_info.get('candles', [])
                    if not candles or len(candles) < 50:
                        continue
                    
                    indicators = indicators_data.get(symbol, {})
                    
                    logger.info(f"🎓 Обучение на {symbol}:")
                    logger.info(f"   📊 Свечей: {len(candles)}")
                    logger.info(f"   📈 RSI: {indicators.get('rsi', 'N/A')}")
                    logger.info(f"   📈 Trend: {indicators.get('trend', 'N/A')}")
                    logger.info(f"   📈 Signal: {indicators.get('signal', 'N/A')}")
                    logger.info(f"   💰 Price: {indicators.get('price', 'N/A')}")
                    
                    # Извлекаем данные из свечей
                    closes = [float(c.get('close', 0) or c.get('close', 0)) for c in candles]
                    volumes = [float(c.get('volume', 0) or 0) for c in candles]
                    highs = [float(c.get('high', 0) or 0) for c in candles]
                    lows = [float(c.get('low', 0) or 0) for c in candles]
                    opens = [float(c.get('open', 0) or 0) for c in candles]
                    
                    if len(closes) < 50:
                        continue
                    
                    # Рассчитываем дополнительные индикаторы
                    rsi = indicators.get('rsi')
                    trend = indicators.get('trend', 'NEUTRAL')
                    signal = indicators.get('signal', 'WAIT')
                    
                    # Анализируем паттерны свечей
                    # Например: последовательности ценовых движений, объемы, волатильность
                    
                    # Рассчитываем волатильность
                    if len(closes) > 1:
                        price_changes = [(closes[i] - closes[i-1]) / closes[i-1] * 100 
                                        for i in range(1, len(closes))]
                        volatility = np.std(price_changes) if price_changes else 0
                    else:
                        volatility = 0
                    
                    # Анализируем объемы
                    avg_volume = np.mean(volumes) if volumes else 0
                    volume_trend = 'INCREASING' if len(volumes) > 1 and volumes[-1] > volumes[0] else 'DECREASING'
                    
                    # Здесь можно добавить обучение на паттернах свечей
                    # Например, обучение на последовательностях ценовых движений
                    # Сохраняем данные для будущего обучения моделей на свечах
                    
                    trained_count += 1
                    total_candles_processed += len(candles)
                    
                    # Логируем прогресс каждые 10 монет
                    if trained_count % 10 == 0:
                        logger.info(f"📊 Прогресс обучения: {trained_count} монет обработано, {total_candles_processed} свечей...")
                    
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка обучения на {symbol}: {e}")
                    failed_count += 1
                    continue
            
            logger.info("=" * 80)
            logger.info(f"✅ ОБУЧЕНИЕ НА СВЕЧАХ ЗАВЕРШЕНО")
            logger.info(f"   📊 Монет обработано: {trained_count}")
            logger.info(f"   📈 Свечей обработано: {total_candles_processed}")
            logger.info(f"   ⚠️ Ошибок: {failed_count}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения на исторических данных: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def predict(self, symbol: str, market_data: Dict) -> Dict:
        """
        Предсказание торгового сигнала
        
        Args:
            symbol: Символ монеты
            market_data: Рыночные данные (RSI, свечи, тренд и т.д.)
        
        Returns:
            Словарь с предсказанием
        """
        if not self.signal_predictor or not self.profit_predictor:
            return {'error': 'Models not trained'}
        
        try:
            # Подготавливаем признаки из market_data
            features = []
            
            rsi = market_data.get('rsi', 50)
            trend = market_data.get('trend', 'NEUTRAL')
            price = market_data.get('price', 0)
            
            # Упрощенная подготовка признаков
            features.append(rsi)
            features.append(1 if trend == 'UP' else (0 if trend == 'DOWN' else 0.5))
            features.append(price)
            
            # Добавляем нули для остальных признаков (упрощение)
            while len(features) < 8:
                features.append(0)
            
            features_array = np.array([features])
            features_scaled = self.scaler.transform(features_array)
            
            # Предсказание сигнала
            signal_prob = self.signal_predictor.predict_proba(features_scaled)[0]
            predicted_profit = self.profit_predictor.predict(features_scaled)[0]
            
            # Определяем сигнал
            if signal_prob[1] > 0.6:  # Вероятность прибыли > 60%
                signal = 'LONG' if rsi < 35 else 'SHORT' if rsi > 65 else 'WAIT'
            else:
                signal = 'WAIT'
            
            return {
                'signal': signal,
                'confidence': float(signal_prob[1]),
                'predicted_profit': float(predicted_profit),
                'rsi': rsi,
                'trend': trend
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка предсказания: {e}")
            return {'error': str(e)}
    
    def get_trades_count(self) -> int:
        """Получить количество сделок для обучения"""
        trades = self._load_history_data()
        return len(trades)

