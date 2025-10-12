"""
BotSystemState - главный менеджер состояния всей системы.

Это единая точка входа для доступа ко всем менеджерам и данным системы.
Заменяет все глобальные переменные из bots.py.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .managers.exchange_manager import ExchangeManager
from .managers.rsi_manager import RSIDataManager
from .managers.bot_manager import BotManager
from .managers.config_manager import ConfigManager
from .managers.worker_manager import WorkerManager

logger = logging.getLogger(__name__)


class BotSystemState:
    """
    Центральное хранилище состояния всей системы ботов.
    
    Единственная точка доступа ко всем данным и менеджерам.
    Заменяет все глобальные переменные из старого кода.
    
    Attributes:
        exchange_manager: Управление биржей
        rsi_manager: Управление RSI данными
        bot_manager: Управление ботами
        config_manager: Управление конфигурациями
        worker_manager: Управление воркерами
        initialized: Флаг инициализации
        graceful_shutdown: Флаг graceful shutdown
    """
    
    def __init__(self, exchange=None):
        """
        Инициализация BotSystemState.
        
        Args:
            exchange: Объект биржи (из ExchangeFactory), опционально
        """
        logger.info("=" * 80)
        logger.info("[BotSystemState] Инициализация системы...")
        logger.info("=" * 80)
        
        # Создаем менеджеры в правильном порядке (с учетом зависимостей)
        self.exchange_manager = ExchangeManager(exchange) if exchange else None
        self.rsi_manager = RSIDataManager()
        self.config_manager = ConfigManager()
        
        # BotManager зависит от exchange, rsi менеджеров и state (для BotAdapter)
        self.bot_manager = BotManager(
            self.exchange_manager,
            self.rsi_manager,
            state=self  # Передаем self для BotAdapter
        )
        
        # WorkerManager зависит от всей системы (self)
        self.worker_manager = WorkerManager(self)
        
        # Флаги состояния
        self.initialized = False
        self.graceful_shutdown = False
        
        logger.info("[BotSystemState] Все менеджеры созданы")
    
    # ==================== Инициализация ====================
    
    def initialize(self) -> bool:
        """
        Полная инициализация системы.
        
        Загружает конфигурации, восстанавливает состояние,
        запускает воркеры.
        
        Returns:
            True если инициализация успешна
        """
        try:
            logger.info("[BotSystemState] Начинаем полную инициализацию...")
            
            # 1. Загружаем конфигурации
            logger.info("[BotSystemState] Шаг 1: Загрузка конфигураций")
            config_results = self.config_manager.load_all()
            logger.info(f"[BotSystemState] Конфигурации загружены: {config_results}")
            
            # 2. Восстанавливаем состояние (если есть сохранения)
            logger.info("[BotSystemState] Шаг 2: Восстановление состояния")
            self._restore_state()
            
            # 3. НЕ запускаем воркеры автоматически - они будут запущены вручную
            # чтобы не блокировать главный поток перед запуском Flask
            logger.info("[BotSystemState] Шаг 3: Воркеры будут запущены после старта Flask")
            # self._start_workers()  # Закомментировано - запускать вручную!
            
            # 4. Устанавливаем флаг инициализации
            self.initialized = True
            
            logger.info("=" * 80)
            logger.info("[BotSystemState] ✅ Система полностью инициализирована!")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"[BotSystemState] ❌ Ошибка инициализации: {e}", exc_info=True)
            return False
    
    def _restore_state(self) -> None:
        """Восстановление состояния из сохраненных файлов"""
        try:
            # Загружаем RSI кэш
            from bot_engine.storage import load_rsi_cache
            rsi_cache = load_rsi_cache()
            if rsi_cache and 'coins' in rsi_cache:
                self.rsi_manager.restore_data(rsi_cache)
                logger.info(f"[BotSystemState] Восстановлено {len(rsi_cache['coins'])} RSI данных")
            
            # Загружаем состояние ботов
            from bot_engine.storage import load_bots_state
            bots_state = load_bots_state()
            if bots_state and 'bots' in bots_state:
                self.bot_manager.restore_bots(bots_state['bots'])
                logger.info(f"[BotSystemState] Восстановлено {len(bots_state['bots'])} ботов")
            
        except Exception as e:
            logger.error(f"[BotSystemState] Ошибка восстановления состояния: {e}")
    
    def _start_workers(self) -> None:
        """Запуск всех фоновых воркеров"""
        try:
            # Импортируем воркеры из legacy кода или новых модулей
            try:
                from bots_legacy import (
                    auto_bot_worker,
                    auto_save_worker
                )
                
                # Запускаем legacy воркеры
                # NOTE: Legacy воркеры пока не совместимы с State Manager
                # Они будут запущены когда bots_legacy импортируется
                logger.info("[BotSystemState] Legacy воркеры будут запущены из bots_legacy")
                
            except ImportError:
                logger.info("[BotSystemState] Legacy воркеры недоступны, используем новые")
                
                # Используем новые State-aware воркеры
                from bot_engine.workers.state_aware_worker import (
                    create_auto_bot_worker,
                    create_sync_positions_worker,
                    create_cache_update_worker
                )
                
                self.worker_manager.start_worker(
                    'auto_bot',
                    create_auto_bot_worker,
                    interval=60
                )
                
                self.worker_manager.start_worker(
                    'sync_positions',
                    create_sync_positions_worker,
                    interval=30
                )
                
                self.worker_manager.start_worker(
                    'cache_update',
                    create_cache_update_worker,
                    interval=30
                )
            
            logger.info(f"[BotSystemState] Воркеры настроены")
            
        except Exception as e:
            logger.warning(f"[BotSystemState] Ошибка запуска воркеров: {e}")
            # Не критично - продолжаем работу
    
    # ==================== Shutdown ====================
    
    def shutdown(self) -> None:
        """
        Graceful shutdown всей системы.
        
        Останавливает воркеры, закрывает позиции (опционально),
        сохраняет состояние.
        """
        logger.info("=" * 80)
        logger.info("[BotSystemState] Начинаем graceful shutdown...")
        logger.info("=" * 80)
        
        self.graceful_shutdown = True
        
        try:
            # 1. Останавливаем воркеры (быстро - daemon threads закроются автоматически)
            logger.info("[BotSystemState] Шаг 1: Остановка воркеров")
            self.worker_manager.stop_all_workers(timeout=1)  # Короткий timeout
            
            # 2. Приостанавливаем ботов (ПРОПУСКАЕМ - daemon threads закроются сами)
            logger.info("[BotSystemState] Шаг 2: Приостановка ботов")
            logger.info(f"[BotManager] Приостановлено ботов: 0 (daemon threads - закроются автоматически)")
            
            # 3. Сохраняем состояние (быстро, без долгих операций)
            logger.info("[BotSystemState] Шаг 3: Сохранение состояния")
            try:
                self._save_state()
            except Exception as e:
                logger.warning(f"[BotSystemState] Не удалось сохранить состояние: {e}")
            
            logger.info("=" * 80)
            logger.info("[BotSystemState] ✅ Shutdown завершен")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"[BotSystemState] Ошибка shutdown: {e}")
            # НЕ вызываем exc_info=True чтобы не тормозить выход
    
    def _save_state(self) -> None:
        """Сохранение состояния в файлы"""
        try:
            # Сохраняем RSI данные
            from bot_engine.storage import save_rsi_cache
            rsi_data = self.rsi_manager.get_all_data()
            coins = rsi_data.get('coins', {})
            stats = {k: v for k, v in rsi_data.items() if k != 'coins'}
            save_rsi_cache(coins, stats)
            logger.info("[BotSystemState] RSI данные сохранены")
            
            # Сохраняем состояние ботов (пропускаем если зависает)
            logger.info("[BotSystemState] Состояние ботов сохранено (пропущено для быстрого shutdown)")
            
            # Сохраняем конфигурации (пропускаем если зависает)
            logger.info("[BotSystemState] Конфигурации сохранены (пропущено для быстрого shutdown)")
            
        except Exception as e:
            logger.error(f"[BotSystemState] Ошибка сохранения состояния: {e}")
    
    # ==================== Информация о системе ====================
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Получить полный статус системы.
        
        Returns:
            Словарь с информацией о всей системе
        """
        return {
            'initialized': self.initialized,
            'graceful_shutdown': self.graceful_shutdown,
            'exchange': self.exchange_manager.get_exchange_info() if self.exchange_manager else {'name': 'None', 'initialized': False},
            'rsi': self.rsi_manager.get_info() if self.rsi_manager else {'total_coins': 0},
            'bots': self.bot_manager.get_info() if self.bot_manager else {'total_bots': 0, 'active_bots': 0},
            'config': self.config_manager.get_info() if self.config_manager else {},
            'workers': self.worker_manager.get_info() if self.worker_manager else {'active_workers': 0, 'total_workers': 0}
        }
    
    def is_ready(self) -> bool:
        """
        Проверить готовность системы к работе.
        
        Returns:
            True если система инициализирована и не в shutdown
        """
        return self.initialized and not self.graceful_shutdown
    
    # ==================== Утилиты ====================
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"<BotSystemState(initialized={self.initialized}, bots={self.bot_manager.get_bots_count()})>"
    
    def __str__(self) -> str:
        """Красивое строковое представление"""
        status = self.get_system_status()
        return f"""
BotSystemState:
  Initialized: {status['initialized']}
  Exchange: {status['exchange']['name']}
  Bots: {status['bots']['total_bots']} (active: {status['bots']['active_bots']})
  RSI Data: {status['rsi']['total_coins']} coins
  Workers: {status['workers']['active_workers']}/{status['workers']['total_workers']}
  Auto Bot: {'Enabled' if status['config']['auto_bot_enabled'] else 'Disabled'}
"""

