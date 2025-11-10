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
        
        # Файл для отслеживания сделок с AI решениями
        self.ai_decisions_file = os.path.join(self.data_dir, 'ai_decisions_tracking.json')
        
        # Инициализируем хранилище данных AI
        try:
            from bot_engine.ai.ai_data_storage import AIDataStorage
            self.data_storage = AIDataStorage(self.data_dir)
        except Exception as e:
            logger.debug(f"⚠️ Не удалось инициализировать AIDataStorage: {e}")
            self.data_storage = None
        
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
        trades = []
        
        # 1. Пробуем загрузить из data/ai/history_data.json (данные собранные через API)
        try:
            history_file = os.path.join(self.data_dir, 'history_data.json')
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Извлекаем все сделки из истории
                latest = data.get('latest', {})
                history = data.get('history', [])
                
                # Добавляем сделки из latest
                if latest:
                    trades.extend(latest.get('trades', []))
                
                # Добавляем сделки из истории
                for entry in history:
                    trades.extend(entry.get('trades', []))
                
                logger.debug(f"📊 Загружено {len(trades)} сделок из history_data.json")
        except Exception as e:
            logger.debug(f"⚠️ Ошибка загрузки history_data.json: {e}")
        
        # 2. Пробуем загрузить напрямую из data/bot_history.json (основной файл bots.py)
        try:
            bot_history_file = os.path.join('data', 'bot_history.json')
            if os.path.exists(bot_history_file):
                with open(bot_history_file, 'r', encoding='utf-8') as f:
                    bot_history_data = json.load(f)
                
                # Извлекаем сделки из bot_history.json
                bot_trades = bot_history_data.get('trades', [])
                if bot_trades:
                    # Добавляем только новые сделки (избегаем дубликатов)
                    existing_ids = {t.get('id') for t in trades if t.get('id')}
                    for trade in bot_trades:
                        trade_id = trade.get('id') or trade.get('timestamp')
                        if trade_id not in existing_ids:
                            trades.append(trade)
                    
                    logger.debug(f"📊 Добавлено {len(bot_trades)} сделок из bot_history.json")
        except json.JSONDecodeError as json_error:
            logger.warning(f"⚠️ Файл bot_history.json поврежден (JSON ошибка на позиции {json_error.pos})")
            logger.info("🗑️ Удаляем поврежденный файл, bots.py пересоздаст его автоматически")
            try:
                os.remove(bot_history_file)
                logger.info("✅ Поврежденный файл удален")
            except Exception as del_error:
                logger.debug(f"⚠️ Не удалось удалить файл: {del_error}")
        except Exception as e:
            logger.debug(f"⚠️ Ошибка загрузки bot_history.json: {e}")
        
        # 3. Фильтруем только закрытые сделки с PnL
        closed_trades = [
            t for t in trades
            if t.get('status') == 'CLOSED' and t.get('pnl') is not None
        ]
        
        if len(closed_trades) > 0:
            logger.info(f"✅ Загружено {len(closed_trades)} закрытых сделок для обучения (всего {len(trades)} сделок)")
        
        return closed_trades
    
    def _load_market_data(self) -> Dict:
        """
        Загрузить рыночные данные
        
        ВАЖНО: Использует ТОЛЬКО полную историю свечей из data/ai/candles_full_history.json
        (загруженную через пагинацию по 2000 свечей для каждой монеты)
        
        НЕ использует candles_cache.json - только полная история для качественного обучения!
        """
        try:
            # ВАЖНО: Загружаем ТОЛЬКО из полной истории свечей (data/ai/candles_full_history.json)
            # НЕ используем market_data.json - свечи всегда из candles_full_history.json!
            # НЕ используем candles_cache.json - только полная история!
            # Если файла нет - возвращаем пустые данные (не fallback на кэш!)
            full_history_file = os.path.join('data', 'ai', 'candles_full_history.json')
            market_data = {'latest': {'candles': {}}}
            
            # Загружаем свечи напрямую из полной истории (ВСЕГДА)
            if not os.path.exists(full_history_file):
                logger.error("=" * 80)
                logger.error("❌ ФАЙЛ ПОЛНОЙ ИСТОРИИ СВЕЧЕЙ НЕ НАЙДЕН!")
                logger.error("=" * 80)
                logger.error(f"   📁 Файл: {full_history_file}")
                logger.error("   💡 Файл должен быть загружен через load_full_candles_history()")
                logger.error("   💡 Загрузка запускается автоматически при старте ai.py")
                logger.error("   ⏳ ДОЖДИТЕСЬ пока файл не будет создан и загружен")
                logger.error("   ❌ НЕ используем candles_cache.json - только полная история!")
                logger.error("   ⏸️ Обучение будет пропущено до загрузки файла")
                logger.error("=" * 80)
                return market_data
            
            # Читаем ТОЛЬКО из полной истории свечей
            try:
                logger.info(f"📖 Загрузка полной истории свечей из {full_history_file}...")
                logger.info("   💡 Это файл загружен через пагинацию по 2000 свечей для каждой монеты")
                logger.info("   💡 Содержит ВСЕ доступные свечи для качественного обучения AI")
                logger.info("   ✅ Используем ТОЛЬКО полную историю (не используем candles_cache.json)")
                
                with open(full_history_file, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)
                
                # Извлекаем свечи из структуры с метаданными
                candles_data = {}
                if 'candles' in full_data:
                    candles_data = full_data['candles']
                elif isinstance(full_data, dict) and not full_data.get('metadata'):
                    candles_data = full_data
                else:
                    logger.warning("⚠️ Неожиданная структура файла candles_full_history.json")
                    candles_data = {}
                
                if candles_data:
                    logger.info(f"✅ Загружено полной истории для {len(candles_data)} монет")
                    
                    if 'latest' not in market_data:
                        market_data['latest'] = {}
                    if 'candles' not in market_data['latest']:
                        market_data['latest']['candles'] = {}
                    
                    candles_count = 0
                    total_candles = 0
                    
                    for symbol, candle_info in candles_data.items():
                        candles = candle_info.get('candles', []) if isinstance(candle_info, dict) else []
                        if candles:
                            market_data['latest']['candles'][symbol] = {
                                'candles': candles,
                                'timeframe': candle_info.get('timeframe', '6h') if isinstance(candle_info, dict) else '6h',
                                'last_update': candle_info.get('last_update') or candle_info.get('loaded_at') if isinstance(candle_info, dict) else None,
                                'count': len(candles),
                                'source': 'candles_full_history.json'
                            }
                            candles_count += 1
                            total_candles += len(candles)
                    
                    logger.info(f"✅ Обработано: {candles_count} монет, {total_candles} свечей")
                else:
                    logger.error("=" * 80)
                    logger.error("❌ ФАЙЛ ПОЛНОЙ ИСТОРИИ СВЕЧЕЙ ПУСТ ИЛИ ПОВРЕЖДЕН!")
                    logger.error("=" * 80)
                    logger.error(f"   📁 Файл: {full_history_file}")
                    logger.error("   ⏳ Дождитесь перезагрузки файла через load_full_candles_history()")
                    logger.error("   ⏸️ Обучение будет пропущено до загрузки файла")
                    logger.error("=" * 80)
                    
            except json.JSONDecodeError as json_error:
                logger.error("=" * 80)
                logger.error("❌ ФАЙЛ ПОЛНОЙ ИСТОРИИ СВЕЧЕЙ ПОВРЕЖДЕН!")
                logger.error("=" * 80)
                logger.error(f"   📁 Файл: {full_history_file}")
                logger.error(f"   ⚠️ JSON ошибка на позиции {json_error.pos}")
                logger.error("   🗑️ Удаляем поврежденный файл, он будет пересоздан при следующей загрузке")
                try:
                    os.remove(full_history_file)
                    logger.info("   ✅ Поврежденный файл удален")
                except Exception as del_error:
                    logger.debug(f"   ⚠️ Не удалось удалить файл: {del_error}")
                logger.error("   ⏳ Дождитесь перезагрузки файла через load_full_candles_history()")
                logger.error("   ⏸️ Обучение будет пропущено до загрузки файла")
                logger.error("=" * 80)
            except Exception as e:
                logger.error(f"❌ Ошибка чтения candles_full_history.json: {e}")
                import traceback
                logger.error(traceback.format_exc())
                logger.error("   ⏸️ Обучение будет пропущено до загрузки файла")
            
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
    
    def train_on_real_trades_with_candles(self):
        """
        ГЛАВНЫЙ МЕТОД ОБУЧЕНИЯ: Обучается на РЕАЛЬНЫХ СДЕЛКАХ с PnL
        
        Связывает свечи с реальными сделками:
        - Что было на свечах когда открыли позицию (RSI, тренд, волатильность)
        - Что было когда закрыли позицию
        - Реальный PnL сделки
        
        Успешные сделки = положительные примеры для обучения
        Неуспешные сделки = отрицательные примеры для обучения
        """
        logger.info("=" * 80)
        logger.info("🤖 ОБУЧЕНИЕ НА РЕАЛЬНЫХ СДЕЛКАХ С ОБРАТНОЙ СВЯЗЬЮ")
        logger.info("=" * 80)
        
        try:
            # 1. Загружаем реальные сделки с PnL
            trades = self._load_history_data()
            
            if len(trades) < 10:
                logger.warning(f"⚠️ Недостаточно реальных сделок для обучения (есть {len(trades)})")
                logger.info("💡 Накопите больше сделок - AI будет обучаться на вашем опыте!")
                return
            
            logger.info(f"📊 Загружено {len(trades)} реальных сделок с PnL")
            
            # 2. Загружаем свечи для анализа
            market_data = self._load_market_data()
            latest = market_data.get('latest', {})
            candles_data = latest.get('candles', {})
            
            if not candles_data:
                logger.warning("⚠️ Нет свечей для анализа")
                return
            
            logger.info(f"📈 Загружено свечей для {len(candles_data)} монет")
            
            # 3. Связываем сделки со свечами и обучаемся
            successful_samples = []  # Успешные сделки (PnL > 0)
            failed_samples = []      # Неуспешные сделки (PnL <= 0)
            
            # Импортируем функцию расчета RSI
            try:
                from bot_engine.indicators import TechnicalIndicators
                calculate_rsi_history_func = TechnicalIndicators.calculate_rsi_history
            except ImportError:
                try:
                    from bots_modules.calculations import calculate_rsi_history
                    calculate_rsi_history_func = calculate_rsi_history
                except ImportError:
                    from bot_engine.utils.rsi_utils import calculate_rsi_history
                    calculate_rsi_history_func = calculate_rsi_history
            
            processed_trades = 0
            skipped_trades = 0
            
            for trade in trades:
                try:
                    symbol = trade.get('symbol')
                    if not symbol or symbol not in candles_data:
                        skipped_trades += 1
                        continue
                    
                    candles = candles_data[symbol].get('candles', [])
                    if len(candles) < 50:
                        skipped_trades += 1
                        continue
                    
                    # Сортируем свечи по времени
                    candles = sorted(candles, key=lambda x: x.get('time', 0))
                    
                    # Данные сделки
                    entry_price = trade.get('entry_price') or trade.get('entryPrice')
                    exit_price = trade.get('exit_price') or trade.get('exitPrice')
                    pnl = trade.get('pnl', 0)
                    direction = trade.get('direction', 'LONG')
                    entry_time = trade.get('timestamp') or trade.get('entry_time')
                    exit_time = trade.get('close_timestamp') or trade.get('exit_time')
                    
                    if not entry_price or not exit_price:
                        skipped_trades += 1
                        continue
                    
                    # Находим свечи в момент входа и выхода
                    entry_candle_idx = None
                    exit_candle_idx = None
                    
                    if entry_time:
                        try:
                            if isinstance(entry_time, str):
                                from datetime import datetime
                                entry_dt = datetime.fromisoformat(entry_time.replace('Z', ''))
                                entry_timestamp = int(entry_dt.timestamp() * 1000)
                            else:
                                entry_timestamp = entry_time
                            
                            # Ищем ближайшую свечу к моменту входа
                            for idx, candle in enumerate(candles):
                                candle_time = candle.get('time', 0)
                                if abs(candle_time - entry_timestamp) < 3600000:  # В пределах 1 часа
                                    entry_candle_idx = idx
                                    break
                        except:
                            pass
                    
                    if exit_time:
                        try:
                            if isinstance(exit_time, str):
                                from datetime import datetime
                                exit_dt = datetime.fromisoformat(exit_time.replace('Z', ''))
                                exit_timestamp = int(exit_dt.timestamp() * 1000)
                            else:
                                exit_timestamp = exit_time
                            
                            for idx, candle in enumerate(candles):
                                candle_time = candle.get('time', 0)
                                if abs(candle_time - exit_timestamp) < 3600000:
                                    exit_candle_idx = idx
                                    break
                        except:
                            pass
                    
                    # Если не нашли точные свечи, используем последние
                    if entry_candle_idx is None:
                        entry_candle_idx = len(candles) - 1
                    if exit_candle_idx is None:
                        exit_candle_idx = len(candles) - 1
                    
                    # Вычисляем RSI на момент входа
                    closes = [float(c.get('close', 0) or 0) for c in candles]
                    volumes = [float(c.get('volume', 0) or 0) for c in candles]
                    highs = [float(c.get('high', 0) or 0) for c in candles]
                    lows = [float(c.get('low', 0) or 0) for c in candles]
                    
                    if len(closes) < 50:
                        skipped_trades += 1
                        continue
                    
                    # RSI история
                    rsi_history = calculate_rsi_history_func(candles, period=14)
                    if not rsi_history or len(rsi_history) < 20:
                        skipped_trades += 1
                        continue
                    
                    # RSI на момент входа
                    rsi_idx = max(0, entry_candle_idx - 14)
                    if rsi_idx < len(rsi_history):
                        entry_rsi = rsi_history[rsi_idx]
                    else:
                        entry_rsi = rsi_history[-1] if rsi_history else 50
                    
                    # Тренд на момент входа
                    if entry_candle_idx >= 20:
                        ema_short = self._calculate_ema(closes[max(0, entry_candle_idx-12):entry_candle_idx+1], 12)
                        ema_long = self._calculate_ema(closes[max(0, entry_candle_idx-26):entry_candle_idx+1], 26)
                        if ema_short and ema_long:
                            entry_trend = 'UP' if ema_short > ema_long else ('DOWN' if ema_short < ema_long else 'NEUTRAL')
                        else:
                            entry_trend = 'NEUTRAL'
                    else:
                        entry_trend = 'NEUTRAL'
                    
                    # Волатильность на момент входа
                    volatility_window = 20
                    if entry_candle_idx >= volatility_window:
                        price_changes = [(closes[j] - closes[j-1]) / closes[j-1] * 100 
                                        for j in range(entry_candle_idx-volatility_window+1, entry_candle_idx+1)]
                        entry_volatility = np.std(price_changes) if price_changes else 0
                    else:
                        entry_volatility = 0
                    
                    # Объемы
                    volume_window = 20
                    if entry_candle_idx >= volume_window:
                        avg_volume = np.mean(volumes[entry_candle_idx-volume_window:entry_candle_idx+1])
                    else:
                        avg_volume = np.mean(volumes[:entry_candle_idx+1]) if entry_candle_idx > 0 else volumes[0]
                    entry_volume_ratio = volumes[entry_candle_idx] / avg_volume if avg_volume > 0 else 1.0
                    
                    # ROI сделки
                    if direction == 'LONG':
                        roi = ((exit_price - entry_price) / entry_price) * 100
                    else:
                        roi = ((entry_price - exit_price) / entry_price) * 100
                    
                    # Создаем обучающий пример
                    sample = {
                        'symbol': symbol,
                        'entry_rsi': entry_rsi,
                        'entry_trend': entry_trend,
                        'entry_volatility': entry_volatility,
                        'entry_volume_ratio': entry_volume_ratio,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'direction': direction,
                        'pnl': pnl,
                        'roi': roi,
                        'is_successful': pnl > 0
                    }
                    
                    # Разделяем на успешные и неуспешные
                    if pnl > 0:
                        successful_samples.append(sample)
                    else:
                        failed_samples.append(sample)
                    
                    processed_trades += 1
                    
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка обработки сделки {trade.get('symbol', 'unknown')}: {e}")
                    skipped_trades += 1
                    continue
            
            logger.info(f"✅ Обработано {processed_trades} сделок")
            logger.info(f"   ✅ Успешных: {len(successful_samples)} (PnL > 0)")
            logger.info(f"   ❌ Неуспешных: {len(failed_samples)} (PnL <= 0)")
            logger.info(f"   ⏭️ Пропущено: {skipped_trades}")
            
            # 4. ОБУЧАЕМСЯ НА РЕАЛЬНОМ ОПЫТЕ
            all_samples = successful_samples + failed_samples
            
            if len(all_samples) >= 20:  # Минимум 20 сделок
                logger.info("=" * 80)
                logger.info("🤖 ОБУЧЕНИЕ НЕЙРОСЕТИ НА РЕАЛЬНОМ ОПЫТЕ")
                logger.info("=" * 80)
                
                # Подготавливаем данные
                X = []
                y_signal = []  # 1 = успешная сделка, 0 = неуспешная
                y_profit = []  # Реальный PnL
                
                for sample in all_samples:
                    features = [
                        sample['entry_rsi'],
                        sample['entry_volatility'],
                        sample['entry_volume_ratio'],
                        1.0 if sample['entry_trend'] == 'UP' else 0.0,
                        1.0 if sample['entry_trend'] == 'DOWN' else 0.0,
                        1.0 if sample['direction'] == 'LONG' else 0.0,
                        sample['entry_price'] / 1000.0 if sample['entry_price'] > 0 else 0,
                    ]
                    
                    X.append(features)
                    y_signal.append(1 if sample['is_successful'] else 0)
                    y_profit.append(sample['pnl'])
                
                X = np.array(X)
                y_signal = np.array(y_signal)
                y_profit = np.array(y_profit)
                
                # Нормализация
                if not hasattr(self.scaler, 'mean_') or self.scaler.mean_ is None:
                    from sklearn.preprocessing import StandardScaler
                    self.scaler = StandardScaler()
                    X_scaled = self.scaler.fit_transform(X)
                else:
                    # Переобучение на новых данных (incremental learning)
                    X_scaled = self.scaler.transform(X)
                
                # Обучаем модель предсказания успешности сделок
                if not self.signal_predictor:
                    from sklearn.ensemble import RandomForestClassifier
                    self.signal_predictor = RandomForestClassifier(
                        n_estimators=200,
                        max_depth=15,
                        min_samples_split=5,
                        min_samples_leaf=2,
                        random_state=42,
                        n_jobs=-1,
                        class_weight='balanced'  # Балансировка классов
                    )
                
                logger.info("   📈 Обучение модели на успешных/неуспешных сделках...")
                self.signal_predictor.fit(X_scaled, y_signal)
                
                # Оценка качества
                train_score = self.signal_predictor.score(X_scaled, y_signal)
                logger.info(f"   ✅ Модель обучена! Точность: {train_score:.2%}")
                
                # Статистика по классам
                from collections import Counter
                class_dist = Counter(y_signal)
                logger.info(f"   📊 Распределение: Успешных={class_dist.get(1, 0)}, Неуспешных={class_dist.get(0, 0)}")
                
                # Анализ важности признаков
                if hasattr(self.signal_predictor, 'feature_importances_'):
                    feature_names = ['RSI', 'Volatility', 'Volume Ratio', 'Trend UP', 'Trend DOWN', 'Direction LONG', 'Price']
                    importances = self.signal_predictor.feature_importances_
                    logger.info("   🔍 Важность признаков:")
                    for name, importance in zip(feature_names, importances):
                        logger.info(f"      {name}: {importance:.3f}")
                
                # Обучаем модель предсказания прибыли
                if not self.profit_predictor:
                    from sklearn.ensemble import GradientBoostingRegressor
                    self.profit_predictor = GradientBoostingRegressor(
                        n_estimators=100,
                        max_depth=5,
                        learning_rate=0.1,
                        random_state=42
                    )
                
                logger.info("   💰 Обучение модели предсказания прибыли...")
                self.profit_predictor.fit(X_scaled, y_profit)
                
                # Оценка предсказания прибыли
                profit_pred = self.profit_predictor.predict(X_scaled)
                profit_mse = mean_squared_error(y_profit, profit_pred)
                logger.info(f"   ✅ Модель прибыли обучена! MSE: {profit_mse:.2f}")
                
                # Сохраняем модели
                self._save_models()
                logger.info("   💾 Модели сохранены!")
                
                # Анализ успешных паттернов
                if successful_samples:
                    logger.info("=" * 80)
                    logger.info("📊 АНАЛИЗ УСПЕШНЫХ ПАТТЕРНОВ")
                    logger.info("=" * 80)
                    
                    successful_rsi = [s['entry_rsi'] for s in successful_samples]
                    successful_trends = [s['entry_trend'] for s in successful_samples]
                    successful_directions = [s['direction'] for s in successful_samples]
                    
                    avg_successful_rsi = np.mean(successful_rsi)
                    logger.info(f"   📈 Средний RSI успешных сделок: {avg_successful_rsi:.2f}")
                    
                    from collections import Counter
                    trend_dist = Counter(successful_trends)
                    logger.info(f"   📊 Тренды успешных сделок: {dict(trend_dist)}")
                    
                    direction_dist = Counter(successful_directions)
                    logger.info(f"   📊 Направления успешных сделок: {dict(direction_dist)}")
                    
                    logger.info("=" * 80)
            else:
                logger.warning(f"⚠️ Недостаточно сделок для обучения (нужно минимум 20, есть {len(all_samples)})")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения на реальных сделках: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def train_on_historical_data(self):
        """
        ОБУЧЕНИЕ НА ИСТОРИЧЕСКИХ ДАННЫХ С ИСПОЛЬЗОВАНИЕМ ВАШИХ НАСТРОЕК
        
        Симулирует торговлю на исторических данных используя:
        - Ваши RSI параметры из bot_config.py
        - Ваши стратегии входа/выхода
        - Проверяет как отработали сигналы
        - Обучается на успешных/неуспешных симуляциях
        """
        logger.info("=" * 80)
        logger.info("🤖 ОБУЧЕНИЕ НА ИСТОРИЧЕСКИХ ДАННЫХ (СИМУЛЯЦИЯ ТОРГОВЛИ)")
        logger.info("=" * 80)
        logger.info("💡 Используем ВАШИ настройки из bots.py для симуляции сделок")
        logger.info("💡 Симулируем входы/выходы по вашим правилам и проверяем результаты")
        
        try:
            # Импортируем ВАШИ настройки из bots.py
            try:
                from bot_engine.bot_config import (
                    RSI_OVERSOLD, RSI_OVERBOUGHT,
                    RSI_EXIT_LONG_WITH_TREND, RSI_EXIT_LONG_AGAINST_TREND,
                    RSI_EXIT_SHORT_WITH_TREND, RSI_EXIT_SHORT_AGAINST_TREND,
                    RSI_PERIOD, DEFAULT_AUTO_BOT_CONFIG
                )
                logger.info("✅ Загружены настройки из bot_config.py")
                logger.info(f"   📊 RSI вход LONG: <= {RSI_OVERSOLD}, SHORT: >= {RSI_OVERBOUGHT}")
                logger.info(f"   📊 RSI выход LONG: {RSI_EXIT_LONG_WITH_TREND}/{RSI_EXIT_LONG_AGAINST_TREND}, SHORT: {RSI_EXIT_SHORT_WITH_TREND}/{RSI_EXIT_SHORT_AGAINST_TREND}")
            except ImportError as e:
                logger.warning(f"⚠️ Не удалось загрузить настройки из bot_config.py: {e}")
                # Используем значения по умолчанию
                RSI_OVERSOLD = 29
                RSI_OVERBOUGHT = 71
                RSI_EXIT_LONG_WITH_TREND = 65
                RSI_EXIT_LONG_AGAINST_TREND = 60
                RSI_EXIT_SHORT_WITH_TREND = 35
                RSI_EXIT_SHORT_AGAINST_TREND = 40
                RSI_PERIOD = 14
            
            # Импортируем функцию расчета RSI истории
            try:
                from bot_engine.indicators import TechnicalIndicators
                calculate_rsi_history_func = TechnicalIndicators.calculate_rsi_history
            except ImportError:
                try:
                    from bots_modules.calculations import calculate_rsi_history
                    calculate_rsi_history_func = calculate_rsi_history
                except ImportError:
                    from bot_engine.utils.rsi_utils import calculate_rsi_history
                    calculate_rsi_history_func = calculate_rsi_history
            
            # Загружаем рыночные данные
            # ВАЖНО: Используем ТОЛЬКО полную историю свечей из candles_full_history.json
            market_data = self._load_market_data()
            
            if not market_data:
                logger.warning("⚠️ Нет рыночных данных для обучения")
                return
            
            latest = market_data.get('latest', {})
            candles_data = latest.get('candles', {})
            
            if not candles_data:
                logger.warning("⚠️ Нет свечей для обучения!")
                logger.info("💡 Файл data/ai/candles_full_history.json не найден или пуст")
                logger.info("💡 Запустите загрузку полной истории свечей через ai.py")
                logger.info("   💡 Это загрузит ВСЕ доступные свечи для всех монет через пагинацию")
                return
            
            logger.info(f"📊 Начинаем ИНДИВИДУАЛЬНОЕ обучение для каждой монеты из {len(candles_data)} монет...")
            logger.info(f"💡 Для каждой монеты: симулируем торговлю → обучаем модель → сохраняем модель")
            logger.info(f"💡 Симулируем входы/выходы используя ВАШИ настройки из bots.py")
            logger.info("=" * 80)
            
            # ОБУЧЕНИЕ ДЛЯ КАЖДОЙ МОНЕТЫ ОТДЕЛЬНО
            total_trained_coins = 0
            total_failed_coins = 0
            total_models_saved = 0
            total_candles_processed = 0
            
            # ОБУЧАЕМ КАЖДУЮ МОНЕТУ ОТДЕЛЬНО
            for symbol_idx, (symbol, candle_info) in enumerate(candles_data.items(), 1):
                try:
                    candles = candle_info.get('candles', [])
                    if not candles or len(candles) < 100:  # Нужно больше свечей для симуляции
                        continue
                    
                    # ВАЖНО: Используем ВСЕ свечи, без ограничений!
                    # Проверяем что не обрезаны свечи
                    original_count = len(candles)
                    
                    # Сортируем свечи по времени (от старых к новым)
                    candles = sorted(candles, key=lambda x: x.get('time', 0))
                    
                    # Проверяем что количество не изменилось после сортировки
                    if len(candles) != original_count:
                        logger.warning(f"   ⚠️ {symbol}: количество свечей изменилось после сортировки ({original_count} -> {len(candles)})")
                    
                    # Проверяем существующую модель и количество свечей при предыдущем обучении
                    symbol_models_dir = os.path.join(self.models_dir, symbol)
                    metadata_path = os.path.join(symbol_models_dir, 'metadata.json')
                    previous_candles_count = 0
                    model_exists = False
                    
                    if os.path.exists(metadata_path):
                        try:
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                existing_metadata = json.load(f)
                            previous_candles_count = existing_metadata.get('candles_count', 0)
                            model_exists = True
                        except Exception as e:
                            logger.debug(f"   ⚠️ Ошибка чтения метаданных модели для {symbol}: {e}")
                    
                    current_candles_count = len(candles)
                    candles_increased = current_candles_count > previous_candles_count
                    increase_percent = ((current_candles_count - previous_candles_count) / previous_candles_count * 100) if previous_candles_count > 0 else 0
                    
                    logger.info("=" * 80)
                    logger.info(f"🎓 [{symbol_idx}/{len(candles_data)}] ОБУЧЕНИЕ ДЛЯ {symbol}")
                    logger.info("=" * 80)
                    logger.info(f"   📊 Свечей для анализа: {len(candles)} (используем ВСЕ доступные свечи)")
                    
                    if model_exists:
                        if candles_increased:
                            logger.info(f"   🔄 Модель будет ПЕРЕОБУЧЕНА: свечей стало больше!")
                            logger.info(f"      📈 Было: {previous_candles_count} свечей")
                            logger.info(f"      📈 Стало: {current_candles_count} свечей (+{increase_percent:.1f}%)")
                            logger.info(f"      💡 Модель переобучится на всех {current_candles_count} свечах для лучшего качества")
                        else:
                            logger.info(f"   ✅ Модель существует: обучена на {previous_candles_count} свечах")
                            logger.info(f"      💡 Переобучаем на всех {current_candles_count} свечах для актуальности")
                    else:
                        logger.info(f"   🆕 Новая модель: будет обучена на {current_candles_count} свечах")
                    
                    # Предупреждение если свечей меньше 1000 (возможно используется кэш вместо полной истории)
                    if len(candles) <= 1000:
                        logger.warning(f"   ⚠️ {symbol}: только {len(candles)} свечей (возможно используется candles_cache.json вместо полной истории)")
                        logger.info(f"   💡 Убедитесь что файл data/ai/candles_full_history.json содержит больше свечей для {symbol}")
                    
                    # Извлекаем данные из свечей
                    closes = [float(c.get('close', 0) or 0) for c in candles]
                    volumes = [float(c.get('volume', 0) or 0) for c in candles]
                    highs = [float(c.get('high', 0) or 0) for c in candles]
                    lows = [float(c.get('low', 0) or 0) for c in candles]
                    opens = [float(c.get('open', 0) or 0) for c in candles]
                    times = [c.get('time', 0) for c in candles]
                    
                    if len(closes) < 100:
                        continue
                    
                    # Вычисляем RSI для КАЖДОЙ свечи
                    rsi_history = calculate_rsi_history_func(candles, period=RSI_PERIOD)
                    
                    if not rsi_history or len(rsi_history) < 50:
                        logger.debug(f"   ⚠️ Недостаточно данных для расчета RSI ({len(rsi_history) if rsi_history else 0})")
                        continue
                    
                    # СИМУЛЯЦИЯ: Проходим по свечам и симулируем входы/выходы
                    simulated_trades_symbol = []  # Симулированные сделки ТОЛЬКО для этой монеты
                    current_position = None  # {'direction': 'LONG'/'SHORT', 'entry_idx': int, 'entry_price': float, 'entry_rsi': float, 'entry_trend': str}
                    trades_for_symbol = 0
                    
                    for i in range(RSI_PERIOD, len(candles)):
                        try:
                            # RSI на текущей позиции
                            rsi_idx = i - RSI_PERIOD
                            if rsi_idx >= len(rsi_history):
                                continue
                            
                            current_rsi = rsi_history[rsi_idx]
                            current_price = closes[i]
                            
                            # Определяем тренд (используем EMA как в bots.py)
                            trend = 'NEUTRAL'
                            if i >= 50:
                                ema_short = self._calculate_ema(closes[max(0, i-50):i+1], 50)
                                ema_long = self._calculate_ema(closes[max(0, i-200):i+1], 200)
                                if ema_short and ema_long:
                                    if ema_short > ema_long:
                                        trend = 'UP'
                                    elif ema_short < ema_long:
                                        trend = 'DOWN'
                            
                            # ПРОВЕРКА ВЫХОДА (если есть открытая позиция)
                            if current_position:
                                entry_trend = current_position['entry_trend']
                                direction = current_position['direction']
                                should_exit = False
                                exit_reason = None
                                
                                # Используем ВАШИ правила выхода из bot_config.py
                                if direction == 'LONG':
                                    # Определяем был ли вход по тренду или против
                                    if entry_trend == 'UP':
                                        # Вход по тренду - используем WITH_TREND
                                        if current_rsi >= RSI_EXIT_LONG_WITH_TREND:
                                            should_exit = True
                                            exit_reason = 'RSI_EXIT_WITH_TREND'
                                    else:
                                        # Вход против тренда - используем AGAINST_TREND
                                        if current_rsi >= RSI_EXIT_LONG_AGAINST_TREND:
                                            should_exit = True
                                            exit_reason = 'RSI_EXIT_AGAINST_TREND'
                                    
                                    # Стоп-лосс (используем настройки из bots.py)
                                    stop_loss_pct = DEFAULT_AUTO_BOT_CONFIG.get('max_loss_percent', 15)
                                    if current_price <= current_position['entry_price'] * (1 - stop_loss_pct / 100):
                                        should_exit = True
                                        exit_reason = 'STOP_LOSS'
                                    
                                    # Take Profit
                                    take_profit_pct = DEFAULT_AUTO_BOT_CONFIG.get('take_profit_percent', 20)
                                    if current_price >= current_position['entry_price'] * (1 + take_profit_pct / 100):
                                        should_exit = True
                                        exit_reason = 'TAKE_PROFIT'
                                
                                elif direction == 'SHORT':
                                    if entry_trend == 'DOWN':
                                        if current_rsi <= RSI_EXIT_SHORT_WITH_TREND:
                                            should_exit = True
                                            exit_reason = 'RSI_EXIT_WITH_TREND'
                                    else:
                                        if current_rsi <= RSI_EXIT_SHORT_AGAINST_TREND:
                                            should_exit = True
                                            exit_reason = 'RSI_EXIT_AGAINST_TREND'
                                    
                                    stop_loss_pct = DEFAULT_AUTO_BOT_CONFIG.get('max_loss_percent', 15)
                                    if current_price >= current_position['entry_price'] * (1 + stop_loss_pct / 100):
                                        should_exit = True
                                        exit_reason = 'STOP_LOSS'
                                    
                                    take_profit_pct = DEFAULT_AUTO_BOT_CONFIG.get('take_profit_percent', 20)
                                    if current_price <= current_position['entry_price'] * (1 - take_profit_pct / 100):
                                        should_exit = True
                                        exit_reason = 'TAKE_PROFIT'
                                
                                if should_exit:
                                    # Закрываем позицию и записываем результат
                                    entry_price = current_position['entry_price']
                                    if direction == 'LONG':
                                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                                    else:
                                        pnl_pct = ((entry_price - current_price) / entry_price) * 100
                                    
                                    # Симулируем PnL в USDT (используем размер позиции из настроек)
                                    position_size_usdt = DEFAULT_AUTO_BOT_CONFIG.get('default_position_size', 5)
                                    pnl_usdt = position_size_usdt * (pnl_pct / 100)
                                    
                                    simulated_trade = {
                                        'symbol': symbol,
                                        'direction': direction,
                                        'entry_idx': current_position['entry_idx'],
                                        'exit_idx': i,
                                        'entry_price': entry_price,
                                        'exit_price': current_price,
                                        'entry_rsi': current_position['entry_rsi'],
                                        'exit_rsi': current_rsi,
                                        'entry_trend': entry_trend,
                                        'exit_trend': trend,
                                        'pnl': pnl_usdt,
                                        'pnl_pct': pnl_pct,
                                        'roi': pnl_pct,
                                        'exit_reason': exit_reason,
                                        'is_successful': pnl_usdt > 0,
                                        'entry_time': times[current_position['entry_idx']],
                                        'exit_time': times[i],
                                        'duration_candles': i - current_position['entry_idx']
                                    }
                                    
                                    simulated_trades_symbol.append(simulated_trade)
                                    trades_for_symbol += 1
                                    current_position = None
                            
                            # ПРОВЕРКА ВХОДА (если нет открытой позиции)
                            if not current_position:
                                # Используем ВАШИ правила входа из bot_config.py
                                should_enter_long = False
                                should_enter_short = False
                                
                                # LONG: RSI <= RSI_OVERSOLD (29)
                                if current_rsi <= RSI_OVERSOLD:
                                    should_enter_long = True
                                
                                # SHORT: RSI >= RSI_OVERBOUGHT (71)
                                if current_rsi >= RSI_OVERBOUGHT:
                                    should_enter_short = True
                                
                                if should_enter_long:
                                    current_position = {
                                        'direction': 'LONG',
                                        'entry_idx': i,
                                        'entry_price': current_price,
                                        'entry_rsi': current_rsi,
                                        'entry_trend': trend
                                    }
                                elif should_enter_short:
                                    current_position = {
                                        'direction': 'SHORT',
                                        'entry_idx': i,
                                        'entry_price': current_price,
                                        'entry_rsi': current_rsi,
                                        'entry_trend': trend
                                    }
                            
                        except Exception as e:
                            logger.debug(f"   ⚠️ Ошибка симуляции свечи {i} для {symbol}: {e}")
                            continue
                    
                    total_candles_processed += len(candles)
                    
                    if trades_for_symbol > 0:
                        symbol_successful = sum(1 for t in simulated_trades_symbol if t['is_successful'])
                        symbol_win_rate = symbol_successful / trades_for_symbol * 100
                        symbol_pnl = sum(t['pnl'] for t in simulated_trades_symbol)
                        
                        logger.info(f"   ✅ Симулировано {trades_for_symbol} сделок")
                        logger.info(f"   📊 Успешных: {symbol_successful} ({symbol_win_rate:.1f}%)")
                        logger.info(f"   💰 PnL: {symbol_pnl:.2f} USDT")
                        
                        # ОБУЧАЕМ МОДЕЛЬ ДЛЯ ЭТОЙ МОНЕТЫ ОТДЕЛЬНО
                        if trades_for_symbol >= 5:  # Минимум 5 сделок для обучения
                            logger.info(f"   🎓 Обучаем модель для {symbol}...")
                            
                            # Подготавливаем данные для обучения
                            X_symbol = []
                            y_signal_symbol = []
                            y_profit_symbol = []
                            
                            symbol_trades = simulated_trades_symbol
                            for trade in symbol_trades:
                                features = [
                                    trade['entry_rsi'],
                                    trade['entry_trend'] == 'UP',
                                    trade['entry_trend'] == 'DOWN',
                                    trade['direction'] == 'LONG',
                                    trade['entry_price'] / 1000.0 if trade['entry_price'] > 0 else 0,
                                ]
                                X_symbol.append(features)
                                y_signal_symbol.append(1 if trade['is_successful'] else 0)
                                y_profit_symbol.append(trade['pnl'])
                            
                            X_symbol = np.array(X_symbol)
                            y_signal_symbol = np.array(y_signal_symbol)
                            y_profit_symbol = np.array(y_profit_symbol)
                            
                            # Создаем scaler для этой монеты
                            from sklearn.preprocessing import StandardScaler
                            symbol_scaler = StandardScaler()
                            X_symbol_scaled = symbol_scaler.fit_transform(X_symbol)
                            
                            # Обучаем модель сигналов для этой монеты
                            from sklearn.ensemble import RandomForestClassifier
                            symbol_signal_predictor = RandomForestClassifier(
                                n_estimators=100,
                                max_depth=10,
                                min_samples_split=3,
                                random_state=42,
                                n_jobs=-1,
                                class_weight='balanced'
                            )
                            symbol_signal_predictor.fit(X_symbol_scaled, y_signal_symbol)
                            signal_score = symbol_signal_predictor.score(X_symbol_scaled, y_signal_symbol)
                            
                            # Обучаем модель прибыли для этой монеты
                            from sklearn.ensemble import GradientBoostingRegressor
                            symbol_profit_predictor = GradientBoostingRegressor(
                                n_estimators=50,
                                max_depth=4,
                                learning_rate=0.1,
                                random_state=42
                            )
                            symbol_profit_predictor.fit(X_symbol_scaled, y_profit_symbol)
                            profit_pred = symbol_profit_predictor.predict(X_symbol_scaled)
                            profit_mse = mean_squared_error(y_profit_symbol, profit_pred)
                            
                            # Сохраняем модели для этой монеты
                            symbol_models_dir = os.path.join(self.models_dir, symbol)
                            os.makedirs(symbol_models_dir, exist_ok=True)
                            
                            signal_model_path = os.path.join(symbol_models_dir, 'signal_predictor.pkl')
                            profit_model_path = os.path.join(symbol_models_dir, 'profit_predictor.pkl')
                            scaler_path = os.path.join(symbol_models_dir, 'scaler.pkl')
                            
                            joblib.dump(symbol_signal_predictor, signal_model_path)
                            joblib.dump(symbol_profit_predictor, profit_model_path)
                            joblib.dump(symbol_scaler, scaler_path)
                            
                            # Сохраняем метаданные (включая количество свечей для проверки при следующем обучении)
                            metadata = {
                                'symbol': symbol,
                                'trained_at': datetime.now().isoformat(),
                                'candles_count': len(candles),  # ВАЖНО: сохраняем количество свечей для проверки
                                'trades_count': trades_for_symbol,
                                'win_rate': symbol_win_rate,
                                'signal_accuracy': signal_score,
                                'profit_mse': profit_mse,
                                'total_pnl': symbol_pnl,
                                'previous_candles_count': previous_candles_count if 'previous_candles_count' in locals() else 0,
                                'candles_increased': candles_increased if 'candles_increased' in locals() else False
                            }
                            metadata_path = os.path.join(symbol_models_dir, 'metadata.json')
                            with open(metadata_path, 'w', encoding='utf-8') as f:
                                json.dump(metadata, f, indent=2, ensure_ascii=False)
                            
                            logger.info(f"   ✅ Модель для {symbol} обучена и сохранена!")
                            logger.info(f"      📈 Точность сигналов: {signal_score:.2%}")
                            logger.info(f"      💰 MSE прибыли: {profit_mse:.2f}")
                            logger.info(f"      📊 Win Rate: {symbol_win_rate:.1f}%")
                            total_models_saved += 1
                        else:
                            logger.info(f"   ⏳ Недостаточно сделок для обучения ({trades_for_symbol} < 5)")
                    
                    total_trained_coins += 1
                    
                    # Логируем прогресс каждые 10 монет
                    if total_trained_coins % 10 == 0:
                        logger.info(f"📊 Прогресс: {total_trained_coins}/{len(candles_data)} монет обработано, {total_models_saved} моделей сохранено...")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обучения для {symbol}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    total_failed_coins += 1
                    continue
            
            # ИТОГОВАЯ СТАТИСТИКА
            logger.info("=" * 80)
            logger.info(f"✅ ИНДИВИДУАЛЬНОЕ ОБУЧЕНИЕ ЗАВЕРШЕНО")
            logger.info("=" * 80)
            logger.info(f"   📊 Монет обработано: {total_trained_coins}")
            logger.info(f"   ✅ Моделей сохранено: {total_models_saved}")
            logger.info(f"   ⚠️ Ошибок: {total_failed_coins}")
            logger.info(f"   📈 Свечей обработано: {total_candles_processed}")
            logger.info(f"   💾 Модели сохранены в: data/ai/models/{{SYMBOL}}/")
            logger.info("=" * 80)
            
            # Также создаем общую модель на всех данных (для монет без индивидуальных моделей)
            logger.info("💡 Общая модель будет создана при следующем обучении (после сбора всех сделок)")
            
            logger.info("=" * 80)
            logger.info(f"✅ СИМУЛЯЦИЯ И ОБУЧЕНИЕ ЗАВЕРШЕНЫ")
            logger.info(f"   📊 Монет обработано: {total_trained_coins}")
            logger.info(f"   📈 Свечей обработано: {total_candles_processed}")
            logger.info(f"   ✅ Моделей сохранено: {total_models_saved}")
            logger.info(f"   ⚠️ Ошибок: {total_failed_coins}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения на исторических данных: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Вычисляет EMA (Exponential Moving Average)"""
        if not prices or len(prices) < period:
            return None
        
        prices_array = np.array(prices[-period:])
        multiplier = 2.0 / (period + 1)
        
        ema = prices_array[0]
        for price in prices_array[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return float(ema)
    
    def _determine_signal_from_rsi_trend(self, rsi: float, trend: str) -> str:
        """Определяет сигнал на основе RSI и тренда"""
        # Логика определения сигнала (можно настроить)
        if rsi <= 30 and trend == 'UP':
            return 'LONG'
        elif rsi >= 70 and trend == 'DOWN':
            return 'SHORT'
        elif rsi <= 25:
            return 'LONG'
        elif rsi >= 75:
            return 'SHORT'
        else:
            return 'WAIT'
    
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

