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
import argparse
from multiprocessing import Process
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
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

# Настройка логирования - используем цветной форматтер как в bots.py
from utils.color_logger import setup_color_logging
from utils.log_rotation import RotatingFileHandlerWithSizeLimit

# Настраиваем цветное логирование для консоли
setup_color_logging()

# Добавляем файловый логгер с ротацией для сохранения в файл
os.makedirs('logs', exist_ok=True)
file_handler = RotatingFileHandlerWithSizeLimit(
    filename='logs/ai.log',
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=0,  # Перезаписываем файл
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('[AI] %(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Получаем корневой логгер и добавляем файловый обработчик
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

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
    from bot_engine.ai.ai_continuous_learning import AIContinuousLearning
except ImportError as e:
    logger.error(f"❌ Ошибка импорта AI модулей: {e}")
    logger.error("Убедитесь, что все модули созданы в директории bot_engine/ai/")
    sys.exit(1)

# Импорт модуля проверки лицензии
try:
    from bot_engine.ai.license_checker import get_license_checker, check_ai_license
    LICENSE_CHECKER_AVAILABLE = True
except ImportError:
    LICENSE_CHECKER_AVAILABLE = False
    logger.warning("⚠️ Модуль проверки лицензии недоступен")

# Импорт существующих AI модулей из bot_engine/ai
try:
    from bot_engine.ai.ai_manager import get_ai_manager
    from bot_engine.ai.auto_trainer import AutoTrainer, get_auto_trainer
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
    # Флаги включения подсистем (используются разными режимами запуска)
    'enable_data_service': True,
    'enable_training': True,
    'enable_backtest': True,
    'enable_optimizer': True,
    # Дополнительные настройки для разделения ролей
    'wait_for_data_service': False,
    'training_refresh_data': True,
    'data_status_file': os.path.join('data', 'ai', 'status', 'data_service.json'),
    'data_ready_timeout': 900,  # 15 минут
    'instance_name': 'Main',
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
        self.instance_name = self.config.get('instance_name', 'Main')
        self.data_status_file = self.config.get('data_status_file')
        self.running = False
        self.threads = []
        
        # ✅ КРИТИЧНО: Проверка лицензии перед инициализацией
        self.license_valid = False
        self.license_info = None
        if LICENSE_CHECKER_AVAILABLE:
            # ✅ ПЕРЕДАЕМ КОРЕНЬ ПРОЕКТА ЯВНО (где находится ai.py)
            project_root = Path(__file__).parent
            license_checker = get_license_checker(project_root=project_root)
            self.license_valid = license_checker.is_valid()
            self.license_info = license_checker.get_info()
            
            if not self.license_valid:
                logger.error("")
                logger.error("=" * 80)
                logger.error("🔴🔴🔴 ЛИЦЕНЗИЯ НЕ ВАЛИДНА - AI ФУНКЦИИ ОТКЛЮЧЕНЫ 🔴🔴🔴")
                logger.error("=" * 80)
                logger.error("⚠️ Весь функционал AI системы требует валидной лицензии")
                logger.error("💡 Для активации лицензии поместите файл .lic в корень проекта")
                logger.error("💡 Получите HWID: python scripts/activate_premium.py")
                logger.error("=" * 80)
                logger.error("")
            else:
                license_type = self.license_info.get('type', 'premium')
                expires_at = self.license_info.get('expires_at', 'N/A')
                logger.info("")
                logger.info("=" * 80)
                logger.info("🟢🟢🟢 ЛИЦЕНЗИЯ АКТИВНА - AI ФУНКЦИИ ДОСТУПНЫ 🟢🟢🟢")
                logger.info("=" * 80)
                logger.info(f"🎫 Тип лицензии: {license_type.upper()}")
                logger.info(f"📅 Действительна до: {expires_at}")
                logger.info("=" * 80)
                logger.info("")
        else:
            logger.warning("⚠️ Проверка лицензии недоступна, продолжаем без проверки")
            self.license_valid = True  # В режиме разработки разрешаем без лицензии
        
        # Инициализация подмодулей
        logger.info("🤖 Инициализация AI модулей...")
        
        # Модуль постоянного обучения и улучшения торговой методики
        self.continuous_learning = AIContinuousLearning()
        logger.info("✅ AIContinuousLearning инициализирован")
        
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
            need_data_collector = self.config.get('enable_data_service', False) or self.config.get('training_refresh_data', True)
            if need_data_collector:
                self.data_collector = AIDataCollector(
                    bots_service_url=self.config['bots_service_url'],
                    app_service_url=self.config['app_service_url']
                )
                logger.info("✅ AIDataCollector инициализирован")
            else:
                self.data_collector = None
                logger.debug("ℹ️ AIDataCollector не требуется в текущем режиме")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AIDataCollector: {e}")
            self.data_collector = None
        
        try:
            if self.config.get('enable_training', False):
                # ✅ Проверка лицензии для обучения
                if not self.license_valid:
                    logger.error("❌ Обучение недоступно: требуется валидная лицензия")
                    self.trainer = None
                elif not (self.license_info and self.license_info.get('features', {}).get('ai_training', False)):
                    logger.error("❌ Обучение недоступно: функция 'ai_training' не включена в лицензию")
                    self.trainer = None
                else:
                    # Используем существующие данные для обучения если доступны
                    self.trainer = AITrainer()
                    if self.existing_ai_manager:
                        logger.info("✅ AITrainer инициализирован (использует существующие данные)")
                    else:
                        logger.info("✅ AITrainer инициализирован")
            else:
                self.trainer = None
                logger.debug("ℹ️ AITrainer отключён (режим без обучения)")
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
            
            if self.config.get('enable_backtest', False):
                # ✅ Проверка лицензии для бэктеста
                if not self.license_valid:
                    logger.error("❌ Бэктест недоступен: требуется валидная лицензия")
                    self.backtester = None
                elif not (self.license_info and self.license_info.get('features', {}).get('ai_backtest', False)):
                    logger.error("❌ Бэктест недоступен: функция 'ai_backtest' не включена в лицензию")
                    self.backtester = None
                else:
                    self.backtester = AIBacktester()
                    logger.info("✅ AIBacktester инициализирован")
            else:
                self.backtester = None
                logger.debug("ℹ️ AIBacktester отключён (режим без бэктеста)")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AIBacktester: {e}")
            self.backtester = None
        
        try:
            if self.config.get('enable_optimizer', False):
                # ✅ Проверка лицензии для оптимизации
                if not self.license_valid:
                    logger.error("❌ Оптимизация недоступна: требуется валидная лицензия")
                    self.strategy_optimizer = None
                elif not (self.license_info and self.license_info.get('features', {}).get('ai_optimization', False)):
                    logger.error("❌ Оптимизация недоступна: функция 'ai_optimization' не включена в лицензию")
                    self.strategy_optimizer = None
                else:
                    self.strategy_optimizer = AIStrategyOptimizer()
                    logger.info("✅ AIStrategyOptimizer инициализирован")
            else:
                self.strategy_optimizer = None
                logger.debug("ℹ️ AIStrategyOptimizer отключён (режим без оптимизации)")
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
        
        logger.info("🚀 Запуск AI системы...")
        
        self.running = True
        data_service_enabled = self.config.get('enable_data_service', False)
        training_enabled = self.config.get('enable_training', False)
        backtest_enabled = self.config.get('enable_backtest', False)
        optimizer_enabled = self.config.get('enable_optimizer', False)
        
        # ВАЖНО: Загружаем/обновляем полную историю свечей при каждом запуске (только для data-service)
        if self.data_collector and data_service_enabled:
            full_history_file = os.path.join('data', 'ai', 'candles_full_history.json')
            
            if not os.path.exists(full_history_file):
                logger.info("📊 Первая загрузка свечей (может занять несколько минут)...")
            else:
                logger.debug("🔄 Инкрементальное обновление свечей...")
            
            # Загружаем/обновляем в фоне - НЕ блокируем запуск
            def load_candles_background():
                try:
                    max_retries = 10
                    retry_delay = 5
                    
                    logger.debug(f"🔄 Фоновая загрузка свечей (до {max_retries} попыток)...")
                    
                    for attempt in range(max_retries):
                        try:
                            logger.debug(f"Попытка {attempt + 1}/{max_retries}...")
                            success = self.data_collector.load_full_candles_history()
                            if success:
                                logger.info("✅ История свечей загружена")
                                self._update_data_status(history_loaded=True, ready=True)
                                return
                            else:
                                if attempt < max_retries - 1:
                                    logger.debug(f"⏳ bots.py не готов, ждем {retry_delay} сек...")
                                    time.sleep(retry_delay)
                                else:
                                    logger.warning("⚠️ Не удалось загрузить свечи после всех попыток")
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logger.debug(f"⚠️ Ошибка подключения, ждем {retry_delay} сек... ({e})")
                                time.sleep(retry_delay)
                            else:
                                logger.error(f"❌ Критическая ошибка при загрузке свечей: {e}")
                                import traceback
                                logger.debug(traceback.format_exc())
                except Exception as bg_error:
                    logger.error(f"❌ Ошибка фоновой загрузки свечей: {bg_error}")
                    import traceback
                    logger.debug(traceback.format_exc())
            
            # Запускаем в отдельном потоке
            candles_thread = threading.Thread(
                target=load_candles_background,
                daemon=True,
                name="AI-CandlesLoader"
            )
            candles_thread.start()
            logger.info("   ✅ Загрузка/обновление свечей запущено в фоне")
        elif not data_service_enabled:
            logger.debug("🔕 Режим без загрузки свечей (data-service отключен)")
        
        # Запуск сбора данных (это можно делать параллельно)
        if self.data_collector and data_service_enabled:
            data_thread = threading.Thread(
                target=self._data_collection_worker,
                daemon=True,
                name="AI-DataCollector"
            )
            data_thread.start()
            self.threads.append(data_thread)
            logger.info("✅ Поток сбора данных запущен")
        elif not data_service_enabled:
            logger.debug("🔕 Поток сбора данных отключен для данного режима")
        
        # ВАЖНО: Собираем начальные данные (неблокирующий вызов)
        # Обучение продолжается даже если bots.py недоступен
        if self.data_collector and data_service_enabled:
            logger.info("📊 Собираем начальные данные перед обучением...")
            logger.info("   💡 Используем доступные данные (candles_full_history.json, bot_history.json)")
            logger.info("   💡 Обучение НЕ блокируется если bots.py недоступен")
            try:
                # Собираем рыночные данные один раз для обучения
                market_data = self.data_collector.collect_market_data()
                candles_count = len(market_data.get('candles', {}))
                indicators_count = len(market_data.get('indicators', {}))
                logger.info(f"✅ Начальные данные собраны: {candles_count} монет со свечами, {indicators_count} с индикаторами")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сбора начальных данных: {e}")
        
        # ✅ Запуск Auto Trainer (автоматическое обновление данных и переобучение)
        # Перенесено из bots.py - теперь обучение полностью в ai.py
        if EXISTING_AI_AVAILABLE and self.license_valid:
            try:
                from bot_engine.bot_config import AIConfig
                if AIConfig.AI_AUTO_TRAIN_ENABLED:
                    auto_trainer = get_auto_trainer()
                    auto_trainer.start()
                    self.existing_auto_trainer = auto_trainer
                    logger.info("✅ AI Auto Trainer запущен (автообновление данных и переобучение)")
                else:
                    logger.debug("ℹ️ AI Auto Trainer отключен в конфигурации")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось запустить Auto Trainer: {e}")
        elif not self.license_valid:
            logger.debug("🔕 AI Auto Trainer недоступен: требуется валидная лицензия")
        
        # Запуск обучения (только после загрузки свечей)
        if training_enabled and self.trainer:
            training_thread = threading.Thread(
                target=self._training_worker,
                daemon=True,
                name="AI-Trainer"
            )
            training_thread.start()
            self.threads.append(training_thread)
            logger.info("✅ Поток обучения запущен")
        elif not training_enabled:
            logger.debug("🔕 Обучение отключено в этом режиме")
        
        # Запуск бэктеста (только после загрузки свечей)
        if backtest_enabled and self.backtester:
            backtest_thread = threading.Thread(
                target=self._backtest_worker,
                daemon=True,
                name="AI-Backtester"
            )
            backtest_thread.start()
            self.threads.append(backtest_thread)
            logger.info("✅ Поток бэктеста запущен")
        elif not backtest_enabled:
            logger.debug("🔕 Поток бэктеста отключен в этом режиме")
        
        # Запуск оптимизации стратегий
        if optimizer_enabled and self.strategy_optimizer:
            optimization_thread = threading.Thread(
                target=self._strategy_optimization_worker,
                daemon=True,
                name="AI-StrategyOptimizer"
            )
            optimization_thread.start()
            self.threads.append(optimization_thread)
            logger.info("✅ Поток оптимизации стратегий запущен")
        elif not optimizer_enabled:
            logger.debug("🔕 Поток оптимизации стратегий отключен")
        
        logger.info("=" * 80)
        logger.info("✅ AI СИСТЕМА ЗАПУЩЕНА")
        logger.info("=" * 80)
    
    def stop(self):
        """Остановка AI системы"""
        if not self.running:
            return
        
        logger.info("🛑 Остановка AI системы...")
        self.running = False
        
        # Останавливаем Auto Trainer
        if self.existing_auto_trainer:
            try:
                self.existing_auto_trainer.stop()
                logger.info("✅ AI Auto Trainer остановлен")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка остановки Auto Trainer: {e}")
        
        # Ждем завершения потоков
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        logger.info("✅ AI система остановлена")
    
    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ РЕЖИМОВ
    # ------------------------------------------------------------------
    def _update_data_status(self, **kwargs):
        """Обновить файл статуса data-service."""
        status_file = self.config.get('data_status_file')
        if not status_file:
            return
        try:
            status_dir = os.path.dirname(status_file)
            os.makedirs(status_dir, exist_ok=True)
            status = {}
            if os.path.exists(status_file):
                with open(status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
            status.update(kwargs)
            status['timestamp'] = datetime.now().isoformat()
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
        except Exception as status_error:
            logger.debug(f"⚠️ Не удалось обновить статус данных: {status_error}")
    
    def _wait_for_data_ready(self):
        """Ожидание готовности данных от data-service."""
        status_file = self.config.get('data_status_file')
        if not status_file:
            return True
        timeout = self.config.get('data_ready_timeout', 900)
        poll_interval = 5
        start_time = time.time()
        logger.info("⏳ Ожидание готовности данных (data-service)...")
        while True:
            if not self.running and self.config.get('enable_training', False):
                return False
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r', encoding='utf-8') as f:
                        status = json.load(f)
                    if status.get('ready') and status.get('history_loaded'):
                        logger.info("✅ Данные готовы, запускаем обучение")
                        return True
                except Exception as status_error:
                    logger.debug(f"⚠️ Ошибка чтения статуса данных: {status_error}")
            if timeout and (time.time() - start_time) > timeout:
                logger.warning("⚠️ Не удалось дождаться готовности данных за отведённое время")
                return False
            time.sleep(poll_interval)
    
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
                    
                    # ВАЖНО: Собираем данные из bot_history ПЕРВЫМ делом
                    history_data = self.data_collector.collect_history_data()
                    trades_count = len(history_data.get('trades', []))
                    logger.info(f"   ✅ История трейдов: {trades_count} сделок")
                    
                    # Проверяем также напрямую из bot_history.json
                    try:
                        import os
                        bot_history_file = os.path.join('data', 'bot_history.json')
                        if os.path.exists(bot_history_file):
                            import json
                            with open(bot_history_file, 'r', encoding='utf-8') as f:
                                bot_history = json.load(f)
                            direct_trades_count = len(bot_history.get('trades', []))
                            if direct_trades_count > trades_count:
                                logger.info(f"   💡 В bot_history.json найдено {direct_trades_count} сделок (больше чем через API)")
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка проверки bot_history.json: {e}")
                    
                    # Собираем рыночные данные (используем ПОЛНУЮ ИСТОРИЮ из candles_full_history.json)
                    market_data = self.data_collector.collect_market_data()
                    candles_count = len(market_data.get('candles', {}))
                    indicators_count = len(market_data.get('indicators', {}))
                    logger.info(f"   ✅ Рыночные данные: {candles_count} монет со свечами, {indicators_count} с индикаторами")
                    logger.info(f"   💡 Используем ПОЛНУЮ ИСТОРИЮ из data/ai/candles_full_history.json (не candles_cache.json!)")
                    
                    logger.info(f"📊 Сбор данных #{collection_count} завершен успешно")
                    self._update_data_status(
                        last_collection=datetime.now().isoformat(),
                        trades=trades_count,
                        candles=candles_count,
                        ready=True
                    )
                
                time.sleep(self.config['data_collection_interval'])
                
            except Exception as e:
                logger.error(f"❌ Ошибка в потоке сбора данных: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(10)
    
    def _training_worker(self):
        """Рабочий поток для обучения - ПОСТОЯННОЕ ОБУЧЕНИЕ БЕЗ ПАУЗ"""
        logger.info("🎓 Запуск потока ПОСТОЯННОГО обучения...")
        logger.info("🔥 Обучение будет идти НЕПРЕРЫВНО для перебора миллиардов комбинаций параметров!")

        if self.config.get('wait_for_data_service'):
            data_ready = self._wait_for_data_ready()
            if not data_ready:
                logger.warning("⚠️ Продолжаем обучение без подтверждённого статуса данных")
        
        # Показываем результаты предыдущего обучения
        try:
            from bot_engine.ai.ai_data_storage import AIDataStorage
            storage = AIDataStorage()
            last_training = storage.get_training_history(limit=1)
            if last_training:
                training = last_training[0]
                logger.info("=" * 80)
                logger.info("📊 РЕЗУЛЬТАТЫ ПРЕДЫДУЩЕГО ОБУЧЕНИЯ:")
                logger.info(f"   📅 Дата: {training.get('timestamp', 'Unknown')}")
                logger.info(f"   📈 Монет обработано: {training.get('total_trained_coins', 0)}")
                logger.info(f"   ✅ Моделей сохранено: {training.get('total_models_saved', 0)}")
                logger.info(f"   📊 Средний Win Rate: {training.get('overall_win_rate', 0):.1f}%")
                logger.info(f"   💰 Общий PnL: {training.get('overall_pnl', 0):.2f} USDT")
                logger.info("=" * 80)
            else:
                logger.info("ℹ️ Предыдущих обучений не найдено - начинаем с первого обучения")
        except Exception as e:
            logger.debug(f"⚠️ Не удалось загрузить историю обучения: {e}")
        
        training_count = 0
        
        # ВАЖНО: НЕПРЕРЫВНЫЙ ЦИКЛ ОБУЧЕНИЯ - БЕЗ ПАУЗ И ИНТЕРВАЛОВ!
        while self.running:
            try:
                if not self.trainer:
                    logger.warning("⚠️ Trainer недоступен, ждем 10 секунд...")
                    time.sleep(10)
                    continue
                
                training_count += 1
                
                # Проверяем достаточно ли данных для обучения
                trades_count = self.trainer.get_trades_count()
                
                logger.info("=" * 80)
                logger.info(f"🎓 ОБУЧЕНИЕ #{training_count} (НЕПРЕРЫВНОЕ)")
                logger.info(f"   📊 Реальных сделок: {trades_count}")
                
                # Показываем статистику использования параметров
                try:
                    if self.trainer and self.trainer.param_tracker:
                        stats = self.trainer.param_tracker.get_usage_stats()
                        logger.info(f"   📊 Параметры: использовано {stats['used_combinations']} из {stats['total_combinations']} комбинаций ({stats['usage_percentage']:.2f}%)")
                        if stats['is_exhausted']:
                            logger.warning(f"   ⚠️ Параметры почти исчерпаны ({stats['usage_percentage']:.1f}%)!")
                        
                        # Показываем лучшие параметры (топ-3)
                        best_params = self.trainer.param_tracker.get_best_params(limit=3)
                        if best_params:
                            logger.info(f"   🏆 Лучшие параметры (топ-3):")
                            for idx, bp in enumerate(best_params, 1):
                                logger.info(f"      {idx}. Win Rate: {bp.get('win_rate', 0):.1f}%, PnL: {bp.get('total_pnl', 0):.2f} USDT, Рейтинг: {bp.get('rating', 0):.1f}")
                except Exception as stats_error:
                    logger.debug(f"⚠️ Ошибка получения статистики параметров: {stats_error}")
                
                logger.info("=" * 80)
                
                # ВАЖНО: Получаем СВЕЖИЕ данные перед каждым обучением!
                logger.info("📥 Получение свежих данных перед обучением...")
                if self.config.get('training_refresh_data', True) and self.data_collector:
                    try:
                        # Обновляем полную историю свечей (инкрементально - только новые)
                        self.data_collector.load_full_candles_history(force_reload=False)
                        # Собираем свежие рыночные данные
                        market_data = self.data_collector.collect_market_data()
                        candles_count = len(market_data.get('candles', {}))
                        indicators_count = len(market_data.get('indicators', {}))
                        logger.info(f"   ✅ Свежие данные: {candles_count} монет со свечами, {indicators_count} с индикаторами")
                        self._update_data_status(last_training_refresh=datetime.now().isoformat(), ready=True)
                    except Exception as candles_error:
                        logger.warning(f"⚠️ Ошибка получения свежих данных: {candles_error}")
                        logger.info("   ⏭️ Продолжаем обучение на существующих данных...")
                elif not self.config.get('training_refresh_data', True):
                    logger.debug("   💡 Обновление данных отключено для режима обучения (используем готовые данные)")
                
                if trades_count >= 10:
                    logger.info(f"✅ Обучение на {trades_count} реальных сделках...")
                    self.trainer.train_on_real_trades_with_candles()
                    self.trainer.retrain_on_ai_decisions()
                    self.trainer.train_on_historical_data()
                    
                    # Постоянное улучшение (тихо)
                    try:
                        history_data = {}
                        if self.data_collector:
                            history_data = self.data_collector.collect_history_data()
                        real_trades = history_data.get('trades', []) if history_data else []
                        if len(real_trades) >= 10:
                            self.continuous_learning.learn_from_real_trades(real_trades)
                    except Exception as cl_error:
                        logger.debug(f"⚠️ Ошибка постоянного улучшения: {cl_error}")
                else:
                    logger.info(f"📈 Обучение на исторических данных ({trades_count} реальных сделок, нужно >=10)")
                    self.trainer.train_on_historical_data()
                    
                    # Все равно пробуем переобучиться на решениях AI (если есть)
                    try:
                        self.trainer.retrain_on_ai_decisions()
                    except:
                        pass
                
                # Показываем результаты обучения и прогресс улучшения
                try:
                    from bot_engine.ai.ai_data_storage import AIDataStorage
                    storage = AIDataStorage()
                    latest_trainings = storage.get_training_history(limit=2)
                    
                    if latest_trainings:
                        current_training = latest_trainings[0]
                        previous_training = latest_trainings[1] if len(latest_trainings) > 1 else None
                        
                        logger.info("=" * 80)
                        logger.info("✅ ОБУЧЕНИЕ #{} ЗАВЕРШЕНО".format(training_count))
                        logger.info(f"   📈 Монет обработано: {current_training.get('total_trained_coins', 0)}")
                        logger.info(f"   ✅ Моделей сохранено: {current_training.get('total_models_saved', 0)}")
                        logger.info(f"   📊 Средний Win Rate: {current_training.get('overall_win_rate', 0):.1f}%")
                        logger.info(f"   💰 Общий PnL: {current_training.get('overall_pnl', 0):.2f} USDT")
                        
                        # Показываем прогресс улучшения (сравнение с предыдущим обучением)
                        if previous_training:
                            prev_win_rate = previous_training.get('overall_win_rate', 0)
                            curr_win_rate = current_training.get('overall_win_rate', 0)
                            prev_pnl = previous_training.get('overall_pnl', 0)
                            curr_pnl = current_training.get('overall_pnl', 0)
                            
                            win_rate_change = curr_win_rate - prev_win_rate
                            pnl_change = curr_pnl - prev_pnl
                            
                            if win_rate_change > 0:
                                logger.info(f"   📈 Win Rate улучшился на +{win_rate_change:.1f}% (было {prev_win_rate:.1f}%)")
                            elif win_rate_change < 0:
                                logger.info(f"   📉 Win Rate снизился на {win_rate_change:.1f}% (было {prev_win_rate:.1f}%)")
                            
                            if pnl_change > 0:
                                logger.info(f"   💰 PnL улучшился на +{pnl_change:.2f} USDT (было {prev_pnl:.2f})")
                            elif pnl_change < 0:
                                logger.info(f"   💸 PnL снизился на {pnl_change:.2f} USDT (было {prev_pnl:.2f})")
                        
                        # Показываем статистику параметров после обучения
                        if self.trainer and self.trainer.param_tracker:
                            stats = self.trainer.param_tracker.get_usage_stats()
                            logger.info(f"   📊 Параметры: использовано {stats['used_combinations']} из {stats['total_combinations']} комбинаций ({stats['usage_percentage']:.2f}%)")
                            
                            # Показываем лучшие параметры (топ-3)
                            best_params = self.trainer.param_tracker.get_best_params(limit=3)
                            if best_params:
                                logger.info(f"   🏆 Лучшие параметры (топ-3):")
                                for idx, bp in enumerate(best_params, 1):
                                    rsi = bp.get('rsi_params', {})
                                    logger.info(f"      {idx}. RSI: {rsi.get('oversold', 0)}/{rsi.get('overbought', 0)}, Win Rate: {bp.get('win_rate', 0):.1f}%, PnL: {bp.get('total_pnl', 0):.2f} USDT, Рейтинг: {bp.get('rating', 0):.1f}")
                        
                        logger.info("   🔥 СРАЗУ ЗАПУСКАЕМ СЛЕДУЮЩЕЕ ОБУЧЕНИЕ С СВЕЖИМИ ДАННЫМИ...")
                        logger.info("=" * 80)
                    else:
                        logger.info("✅ Обучение #{} завершено, запускаем следующее...".format(training_count))
                except Exception as e:
                    logger.debug(f"⚠️ Не удалось загрузить результаты: {e}")
                    logger.info("✅ Обучение #{} завершено, запускаем следующее...".format(training_count))
                finally:
                    self._update_data_status(last_training=datetime.now().isoformat(), ready=True)
                
                # ВАЖНО: НЕТ ПАУЗЫ! Сразу запускаем следующее обучение!
                # Только небольшая пауза для предотвращения перегрузки системы (1 секунда)
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в потоке обучения: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # При ошибке ждем 10 секунд перед повтором
                time.sleep(10)
    
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


def create_mode_config(mode: str) -> Dict:
    """Создать конфигурацию для выбранного режима запуска."""
    base = {**AI_CONFIG}
    if mode == 'data-service':
        base.update({
            'instance_name': 'DataService',
            'enable_data_service': True,
            'enable_training': False,
            'enable_backtest': False,
            'enable_optimizer': False,
            'wait_for_data_service': False,
            'training_refresh_data': False,
        })
    elif mode == 'train':
        base.update({
            'instance_name': 'Trainer',
            'enable_data_service': False,
            'enable_training': True,
            'enable_backtest': False,
            'enable_optimizer': False,
            'wait_for_data_service': True,
            'training_refresh_data': False,
            'data_ready_timeout': 900,
        })
    elif mode == 'scheduler':
        base.update({
            'instance_name': 'Scheduler',
            'enable_data_service': False,
            'enable_training': False,
            'enable_backtest': True,
            'enable_optimizer': True,
            'wait_for_data_service': False,
            'training_refresh_data': False,
        })
    else:  # режим all / совместимый
        base.update({
            'instance_name': 'Main',
            'enable_data_service': True,
            'enable_training': True,
            'enable_backtest': True,
            'enable_optimizer': True,
            'wait_for_data_service': False,
            'training_refresh_data': True,
            'data_ready_timeout': 900,
        })
    return base


def run_mode(mode: str):
    """Запуск определённого режима AI системы."""
    config = create_mode_config(mode)
    os.makedirs('logs', exist_ok=True)
    ai_system = AISystem(config)
    ai_system.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info(f"Остановка режима {mode}...")
        ai_system.stop()
    except Exception as run_error:
        logger.error(f"❌ Критическая ошибка режима {mode}: {run_error}")
        import traceback
        logger.error(traceback.format_exc())
        ai_system.stop()


def get_ai_system(config: Dict = None) -> AISystem:
    """Получить глобальный экземпляр AI системы"""
    global _ai_system
    
    if _ai_system is None:
        _ai_system = AISystem(config)
    
    return _ai_system


def main():
    """Главная функция для запуска AI системы отдельно"""
    parser = argparse.ArgumentParser(description="AI система для торговых ботов")
    parser.add_argument(
        '--mode',
        choices=['all', 'data-service', 'train', 'scheduler'],
        default='all',
        help='Режим запуска: все сервисы, только сбор данных, только обучение или только планировщик'
    )
    args = parser.parse_args()

    if args.mode == 'all':
        # Оркестратор: запускаем отдельные процессы
        modes = ['data-service', 'scheduler', 'train']
        processes: List[Process] = []
        try:
            for mode in modes:
                proc = Process(target=run_mode, args=(mode,), daemon=False)
                proc.start()
                processes.append(proc)
                logger.info(f"🚀 Запущен процесс режима {mode} (PID {proc.pid})")
            for proc in processes:
                proc.join()
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки, завершаем процессы...")
            for proc in processes:
                if proc.is_alive():
                    proc.terminate()
            for proc in processes:
                proc.join()
        except Exception as orchestrator_error:
            logger.error(f"❌ Ошибка оркестратора: {orchestrator_error}")
            for proc in processes:
                if proc.is_alive():
                    proc.terminate()
            for proc in processes:
                proc.join()
    else:
        run_mode(args.mode)


if __name__ == '__main__':
    main()

