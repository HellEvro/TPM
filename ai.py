#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный модуль AI системы для торговых ботов

Модульная система искусственного интеллекта, которая:
- Обучается на истории трейдов
- Обучается на параметрах стратегии
- Обучается на исторических данных
- Делает бэктест стратегий
- Мониторит данные из bots.py (свечи, RSI, стохастик, сигналы)
- Управляет ботами через API

Интеграция:
- Работает совместно с bots.py (порт 5001)
- Работает совместно с app.py (порт 5000)
- Использует данные из bot_engine/bot_history.py
- Мониторит данные из bots_modules/
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests

# Настройка кодировки для Windows консоли
if os.name == 'nt':
    try:
        # Пытаемся установить UTF-8 для консоли Windows
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        # Если не получилось, пробуем через os
        try:
            import subprocess
            subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
        except:
            pass

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[AI] %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ai.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AI.Main')

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импорт подмодулей AI из bot_engine/ai
try:
    from bot_engine.ai.ai_data_collector import AIDataCollector
    from bot_engine.ai.ai_trainer import AITrainer
    from bot_engine.ai.ai_backtester_new import AIBacktester
    from bot_engine.ai.ai_strategy_optimizer import AIStrategyOptimizer
    from bot_engine.ai.ai_bot_manager import AIBotManager
except ImportError as e:
    logger.error(f"❌ Ошибка импорта AI модулей: {e}")
    logger.error("Убедитесь, что все модули созданы в директории bot_engine/ai/")
    sys.exit(1)

# Импорт существующих AI модулей из bot_engine/ai
try:
    from bot_engine.ai.ai_manager import get_ai_manager
    from bot_engine.ai.auto_trainer import AutoTrainer
    # SmartRiskManager может требовать лицензию, но это не критично
    try:
        from bot_engine.ai.smart_risk_manager import SmartRiskManager
    except ImportError:
        # Это нормально, если нет лицензии
        SmartRiskManager = None
    EXISTING_AI_AVAILABLE = True
    logger.info("✅ Существующие AI модули обнаружены")
except ImportError:
    EXISTING_AI_AVAILABLE = False
    SmartRiskManager = None
    logger.info("ℹ️ Существующие AI модули недоступны (работаем независимо)")

# Конфигурация
AI_CONFIG = {
    'bots_service_url': 'http://127.0.0.1:5001',
    'app_service_url': 'http://127.0.0.1:5000',
    'data_collection_interval': 60,  # секунды
    'training_interval': 3600,  # 1 час
    'backtest_interval': 86400,  # 24 часа
    'strategy_optimization_interval': 86400,  # 24 часа
    'enabled': True,
    'auto_trading': False,  # Автоматическая торговля через AI
    'min_trades_for_training': 50,  # Минимум сделок для обучения
    'backtest_period_days': 30,  # Период бэктеста
}


class AISystem:
    """
    Главный класс AI системы
    """
    
    def __init__(self, config: Dict = None):
        """
        Инициализация AI системы
        
        Args:
            config: Конфигурация системы
        """
        self.config = {**AI_CONFIG, **(config or {})}
        self.running = False
        self.threads = []
        
        # Инициализация подмодулей
        logger.info("🤖 Инициализация AI модулей...")
        
        # Интеграция с существующими AI модулями
        self.existing_ai_manager = None
        self.existing_auto_trainer = None
        self.existing_smart_risk = None
        
        if EXISTING_AI_AVAILABLE:
            try:
                self.existing_ai_manager = get_ai_manager()
                if self.existing_ai_manager and self.existing_ai_manager.is_available():
                    logger.info("✅ Интегрирован с существующими AI модулями (ai_manager)")
                else:
                    logger.info("ℹ️ Существующие AI модули требуют лицензию")
            except Exception as e:
                logger.debug(f"Существующие AI модули недоступны: {e}")
        
        try:
            self.data_collector = AIDataCollector(
                bots_service_url=self.config['bots_service_url'],
                app_service_url=self.config['app_service_url']
            )
            logger.info("✅ AIDataCollector инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AIDataCollector: {e}")
            self.data_collector = None
        
        try:
            # Используем существующие данные для обучения если доступны
            self.trainer = AITrainer()
            if self.existing_ai_manager:
                logger.info("✅ AITrainer инициализирован (использует существующие данные)")
            else:
                logger.info("✅ AITrainer инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AITrainer: {e}")
            self.trainer = None
        
        try:
            # Используем существующий backtester если доступен
            if EXISTING_AI_AVAILABLE:
                try:
                    from bot_engine.ai.backtester import BacktestEngine
                    self.existing_backtester = BacktestEngine()
                    logger.info("✅ Используется существующий BacktestEngine")
                except:
                    self.existing_backtester = None
            
            self.backtester = AIBacktester()
            logger.info("✅ AIBacktester инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AIBacktester: {e}")
            self.backtester = None
        
        try:
            self.strategy_optimizer = AIStrategyOptimizer()
            logger.info("✅ AIStrategyOptimizer инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AIStrategyOptimizer: {e}")
            self.strategy_optimizer = None
        
        try:
            self.bot_manager = AIBotManager(
                bots_service_url=self.config['bots_service_url']
            )
            logger.info("✅ AIBotManager инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AIBotManager: {e}")
            self.bot_manager = None
        
        logger.info("🤖 AI система инициализирована")
    
    def start(self):
        """Запуск AI системы"""
        if self.running:
            logger.warning("⚠️ AI система уже запущена")
            return
        
        if not self.config.get('enabled', True):
            logger.info("ℹ️ AI система отключена в конфигурации")
            return
        
        logger.info("=" * 80)
        logger.info("🚀 ЗАПУСК AI СИСТЕМЫ")
        logger.info("=" * 80)
        
        self.running = True
        
        # Запуск сбора данных
        if self.data_collector:
            data_thread = threading.Thread(
                target=self._data_collection_worker,
                daemon=True,
                name="AI-DataCollector"
            )
            data_thread.start()
            self.threads.append(data_thread)
            logger.info("✅ Поток сбора данных запущен")
        
        # Запуск обучения
        if self.trainer:
            training_thread = threading.Thread(
                target=self._training_worker,
                daemon=True,
                name="AI-Trainer"
            )
            training_thread.start()
            self.threads.append(training_thread)
            logger.info("✅ Поток обучения запущен")
        
        # Запуск бэктеста
        if self.backtester:
            backtest_thread = threading.Thread(
                target=self._backtest_worker,
                daemon=True,
                name="AI-Backtester"
            )
            backtest_thread.start()
            self.threads.append(backtest_thread)
            logger.info("✅ Поток бэктеста запущен")
        
        # Запуск оптимизации стратегий
        if self.strategy_optimizer:
            optimization_thread = threading.Thread(
                target=self._strategy_optimization_worker,
                daemon=True,
                name="AI-StrategyOptimizer"
            )
            optimization_thread.start()
            self.threads.append(optimization_thread)
            logger.info("✅ Поток оптимизации стратегий запущен")
        
        logger.info("=" * 80)
        logger.info("✅ AI СИСТЕМА ЗАПУЩЕНА")
        logger.info("=" * 80)
    
    def stop(self):
        """Остановка AI системы"""
        if not self.running:
            return
        
        logger.info("🛑 Остановка AI системы...")
        self.running = False
        
        # Ждем завершения потоков
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        logger.info("✅ AI система остановлена")
    
    def _data_collection_worker(self):
        """Рабочий поток для сбора данных"""
        logger.info("📊 Запуск потока сбора данных...")
        
        collection_count = 0
        
        while self.running:
            try:
                if self.data_collector:
                    collection_count += 1
                    logger.info(f"📊 Сбор данных #{collection_count}...")
                    
                    # Собираем данные из bots.py
                    bots_data = self.data_collector.collect_bots_data()
                    bots_count = len(bots_data.get('bots', []))
                    rsi_count = len(bots_data.get('rsi_data', {}))
                    logger.info(f"   ✅ Боты: {bots_count}, RSI данных: {rsi_count}")
                    
                    # Собираем данные из bot_history
                    history_data = self.data_collector.collect_history_data()
                    trades_count = len(history_data.get('trades', []))
                    logger.info(f"   ✅ История трейдов: {trades_count} сделок")
                    
                    # Собираем рыночные данные (свечи для всех монет)
                    market_data = self.data_collector.collect_market_data()
                    candles_count = len(market_data.get('candles', {}))
                    indicators_count = len(market_data.get('indicators', {}))
                    logger.info(f"   ✅ Рыночные данные: {candles_count} монет со свечами, {indicators_count} с индикаторами")
                    
                    logger.info(f"📊 Сбор данных #{collection_count} завершен успешно")
                
                time.sleep(self.config['data_collection_interval'])
                
            except Exception as e:
                logger.error(f"❌ Ошибка в потоке сбора данных: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(10)
    
    def _training_worker(self):
        """Рабочий поток для обучения"""
        logger.info("🎓 Запуск потока обучения...")
        
        last_training_time = 0
        training_count = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Проверяем интервал обучения
                if current_time - last_training_time >= self.config['training_interval']:
                    if self.trainer:
                        training_count += 1
                        
                        # Проверяем достаточно ли данных для обучения
                        trades_count = self.trainer.get_trades_count()
                        
                        logger.info("=" * 80)
                        logger.info(f"🎓 ОБУЧЕНИЕ #{training_count}")
                        logger.info(f"📊 Доступно сделок: {trades_count}")
                        logger.info("=" * 80)
                        
                        if trades_count >= self.config['min_trades_for_training']:
                            logger.info(f"✅ Достаточно данных для обучения (нужно: {self.config['min_trades_for_training']}, есть: {trades_count})")
                            
                            # Обучение на истории трейдов
                            logger.info("\n📈 Этап 1/3: Обучение на истории трейдов...")
                            self.trainer.train_on_history()
                            
                            # Обучение на параметрах стратегии
                            logger.info("\n📈 Этап 2/3: Обучение на параметрах стратегии...")
                            self.trainer.train_on_strategy_params()
                            
                            # Обучение на исторических данных (свечах)
                            logger.info("\n📈 Этап 3/3: Обучение на исторических данных (свечах)...")
                            self.trainer.train_on_historical_data()
                            
                            last_training_time = current_time
                            logger.info("=" * 80)
                            logger.info("✅ ОБУЧЕНИЕ ЗАВЕРШЕНО")
                            logger.info("=" * 80)
                        else:
                            logger.info(f"⏳ Недостаточно данных для обучения (нужно: {self.config['min_trades_for_training']}, есть: {trades_count})")
                            logger.info("💡 Накопите больше сделок для качественного обучения")
                            
                            # Но все равно обучаемся на свечах (если есть данные)
                            logger.info("\n📈 Обучение на свечах (без истории трейдов)...")
                            self.trainer.train_on_historical_data()
                
                time.sleep(60)  # Проверяем каждую минуту
                
            except Exception as e:
                logger.error(f"❌ Ошибка в потоке обучения: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(60)
    
    def _backtest_worker(self):
        """Рабочий поток для бэктеста"""
        logger.info("📈 Запуск потока бэктеста...")
        
        last_backtest_time = 0
        backtest_count = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Проверяем интервал бэктеста
                if current_time - last_backtest_time >= self.config['backtest_interval']:
                    if self.backtester:
                        backtest_count += 1
                        logger.info("=" * 80)
                        logger.info(f"📈 БЭКТЕСТ #{backtest_count}")
                        logger.info("=" * 80)
                        logger.info(f"📊 Период: {self.config['backtest_period_days']} дней")
                        
                        results = self.backtester.backtest_strategies(
                            period_days=self.config['backtest_period_days']
                        )
                        
                        last_backtest_time = current_time
                        
                        if results:
                            logger.info("=" * 80)
                            logger.info("✅ БЭКТЕСТ ЗАВЕРШЕН")
                            logger.info(f"📊 Протестировано стратегий: {len(results)}")
                            if results:
                                best = results[0]
                                logger.info(f"🏆 Лучшая стратегия: {best.get('strategy_name', 'Unknown')}")
                                logger.info(f"   📈 Return: {best.get('total_return', 0):.2f}%")
                                logger.info(f"   📊 Win Rate: {best.get('win_rate', 0):.2f}%")
                                logger.info(f"   💰 Сделок: {best.get('total_trades', 0)}")
                            logger.info("=" * 80)
                        else:
                            logger.warning("⚠️ Бэктест не вернул результатов")
                
                time.sleep(3600)  # Проверяем каждый час
                
            except Exception as e:
                logger.error(f"❌ Ошибка в потоке бэктеста: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(3600)
    
    def _strategy_optimization_worker(self):
        """Рабочий поток для оптимизации стратегий"""
        logger.info("⚙️ Запуск потока оптимизации стратегий...")
        
        last_optimization_time = 0
        optimization_count = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Проверяем интервал оптимизации
                if current_time - last_optimization_time >= self.config['strategy_optimization_interval']:
                    if self.strategy_optimizer:
                        optimization_count += 1
                        logger.info("=" * 80)
                        logger.info(f"⚙️ ОПТИМИЗАЦИЯ СТРАТЕГИЙ #{optimization_count}")
                        logger.info("=" * 80)
                        
                        optimized_params = self.strategy_optimizer.optimize_strategy()
                        
                        last_optimization_time = current_time
                        
                        logger.info("=" * 80)
                        logger.info("✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
                        if optimized_params:
                            logger.info(f"📊 Оптимизированные параметры:")
                            for key, value in optimized_params.items():
                                logger.info(f"   - {key}: {value}")
                        else:
                            logger.warning("⚠️ Оптимизация не вернула параметров")
                        logger.info("=" * 80)
                
                time.sleep(3600)  # Проверяем каждый час
                
            except Exception as e:
                logger.error(f"❌ Ошибка в потоке оптимизации: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(3600)
    
    def get_status(self) -> Dict:
        """Получить статус AI системы"""
        status = {
            'running': self.running,
            'enabled': self.config.get('enabled', True),
            'auto_trading': self.config.get('auto_trading', False),
            'modules': {
                'data_collector': self.data_collector is not None,
                'trainer': self.trainer is not None,
                'backtester': self.backtester is not None,
                'strategy_optimizer': self.strategy_optimizer is not None,
                'bot_manager': self.bot_manager is not None
            },
            'threads': len([t for t in self.threads if t.is_alive()])
        }
        
        # Добавляем информацию о существующих AI модулях
        if self.existing_ai_manager:
            try:
                status['existing_ai'] = {
                    'available': self.existing_ai_manager.is_available() if self.existing_ai_manager else False,
                    'modules': {
                        'anomaly_detector': self.existing_ai_manager.anomaly_detector is not None if self.existing_ai_manager else False,
                        'lstm_predictor': self.existing_ai_manager.lstm_predictor is not None if self.existing_ai_manager else False,
                        'pattern_detector': self.existing_ai_manager.pattern_detector is not None if self.existing_ai_manager else False,
                        'risk_manager': self.existing_ai_manager.risk_manager is not None if self.existing_ai_manager else False
                    }
                }
            except:
                status['existing_ai'] = {'available': False}
        
        return status
    
    def predict_signal(self, symbol: str, market_data: Dict) -> Dict:
        """
        Предсказание торгового сигнала для символа
        
        Использует обученные модели из data/ai/models/:
        - signal_predictor.pkl - предсказание сигналов
        - profit_predictor.pkl - предсказание прибыльности
        
        Args:
            symbol: Символ монеты (например, BTCUSDT)
            market_data: Рыночные данные (RSI, свечи, тренд и т.д.)
        
        Returns:
            Словарь с предсказанием сигнала
        """
        if not self.trainer:
            return {'error': 'Trainer not initialized'}
        
        if not self.trainer.signal_predictor:
            logger.debug(f"🤖 Модель signal_predictor.pkl не обучена для {symbol}")
            return {
                'signal': 'WAIT',
                'confidence': 0,
                'error': 'Model not trained yet. Run training first.',
                'model_path': 'data/ai/models/signal_predictor.pkl'
            }
        
        try:
            # Используем обученную модель для предсказания
            prediction = self.trainer.predict(symbol, market_data)
            
            # Добавляем информацию о модели
            prediction['model_used'] = 'signal_predictor.pkl'
            prediction['model_path'] = 'data/ai/models/signal_predictor.pkl'
            
            return prediction
        except Exception as e:
            logger.error(f"❌ Ошибка предсказания для {symbol}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {'error': str(e)}
    
    def optimize_bot_config(self, symbol: str) -> Dict:
        """
        Оптимизация конфигурации бота для символа
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Оптимизированная конфигурация
        """
        if not self.strategy_optimizer:
            return {'error': 'Strategy optimizer not initialized'}
        
        try:
            optimized = self.strategy_optimizer.optimize_bot_config(symbol)
            return optimized
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации для {symbol}: {e}")
            return {'error': str(e)}


# Глобальный экземпляр AI системы
_ai_system = None


def get_ai_system(config: Dict = None) -> AISystem:
    """Получить глобальный экземпляр AI системы"""
    global _ai_system
    
    if _ai_system is None:
        _ai_system = AISystem(config)
    
    return _ai_system


def main():
    """Главная функция для запуска AI системы отдельно"""
    import signal
    
    # Создаем директорию для логов
    os.makedirs('logs', exist_ok=True)
    
    # Инициализация AI системы
    ai_system = get_ai_system()
    
    # Обработчик сигналов для graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Получен сигнал остановки...")
        ai_system.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск системы
    ai_system.start()
    
    # Ожидание
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя...")
        ai_system.stop()


if __name__ == '__main__':
    main()

