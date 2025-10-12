"""
State-Aware Worker - обертка для воркеров с State Manager.

Позволяет воркерам работать через State Manager вместо глобальных переменных.
"""

import logging
import time
from datetime import datetime
from typing import Callable, Any

logger = logging.getLogger(__name__)


class StateAwareWorker:
    """
    Обертка для воркеров, которая предоставляет доступ к State Manager.
    
    Позволяет постепенно мигрировать воркеры на новую архитектуру.
    """
    
    def __init__(self, name: str, state, interval: int = 60):
        """
        Инициализация воркера.
        
        Args:
            name: Имя воркера
            state: BotSystemState instance
            interval: Интервал выполнения (секунды)
        """
        self.name = name
        self.state = state
        self.interval = interval
        self.error_count = 0
        self.success_count = 0
        self.last_run = None
        
        logger.info(f"[{self.name}] Воркер инициализирован (interval={interval}s)")
    
    def run_periodic(self, shutdown_flag, work_func: Callable):
        """
        Запустить воркер в периодическом режиме.
        
        Args:
            shutdown_flag: threading.Event для остановки
            work_func: Функция работы (принимает self.state)
        """
        logger.info(f"[{self.name}] Воркер запущен")
        
        while not shutdown_flag.is_set():
            try:
                # Выполняем работу
                work_func(self.state)
                
                self.success_count += 1
                self.last_run = datetime.now()
                
                # Логируем каждые 10 успешных выполнений
                if self.success_count % 10 == 0:
                    logger.info(
                        f"[{self.name}] ✅ Выполнено {self.success_count} раз "
                        f"(ошибок: {self.error_count})"
                    )
                
            except Exception as e:
                self.error_count += 1
                logger.error(f"[{self.name}] ❌ Ошибка: {e}")
                
                # Логируем каждую ошибку но не спамим
                if self.error_count % 10 == 0:
                    logger.warning(
                        f"[{self.name}] ⚠️ Накоплено {self.error_count} ошибок"
                    )
            
            # Ждем интервал или сигнал остановки
            if shutdown_flag.wait(self.interval):
                break
        
        logger.info(
            f"[{self.name}] Воркер остановлен "
            f"(успешно: {self.success_count}, ошибок: {self.error_count})"
        )
    
    def get_stats(self) -> dict:
        """Получить статистику воркера"""
        return {
            'name': self.name,
            'interval': self.interval,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'last_run': self.last_run.isoformat() if self.last_run else None
        }


# ==================== Примеры воркеров ====================

def example_auto_bot_worker(state):
    """
    Пример воркера Auto Bot с State Manager.
    
    Args:
        state: BotSystemState instance
    """
    # Получаем конфиг через state (принудительно обновляем)
    config = state.config_manager.get_auto_bot_config()
    logger.info(f"[AUTO_BOT] 🔧 Конфиг: enabled={config.get('enabled', False)}")
    
    if not config.get('enabled'):
        logger.info("[AUTO_BOT] Выключен, пропускаем")
        return
    
    # Получаем активные боты
    active_bots = state.bot_manager.get_active_bots_count()
    max_bots = config.get('max_concurrent_bots', 5)
    
    if active_bots >= max_bots:
        logger.info(f"[AUTO_BOT] Достигнут лимит ботов ({active_bots}/{max_bots})")
        return
    
    # Получаем сигналы через state
    long_signals = state.rsi_manager.get_coins_with_signal('LONG')
    short_signals = state.rsi_manager.get_coins_with_signal('SHORT')
    
    logger.info(
        f"[AUTO_BOT] 🔍 Сигналы: LONG={len(long_signals)}, SHORT={len(short_signals)}, "
        f"Боты: {active_bots}/{max_bots}"
    )
    
    # Здесь можно добавить логику создания ботов
    # for symbol in long_signals:
    #     if active_bots >= max_bots:
    #         break
    #     # Проверяем фильтры
    #     # Создаем бота
    #     # active_bots += 1


def example_sync_positions_worker(state):
    """
    Пример воркера синхронизации позиций с State Manager.
    
    Args:
        state: BotSystemState instance
    """
    # Получаем позиции с биржи через state
    try:
        exchange_positions = state.exchange_manager.get_all_positions()
    except Exception as e:
        logger.warning(f"[SYNC] Не удалось получить позиции: {e}")
        return
    
    # Получаем ботов в позиции через state
    bots_in_position = state.bot_manager.get_bots_in_position()
    
    logger.info(
        f"[SYNC] Биржа: {len(exchange_positions)} позиций, "
        f"Боты: {len(bots_in_position)} в позиции"
    )
    
    # Здесь можно добавить логику синхронизации
    # ...


def example_cache_update_worker(state):
    """
    Пример воркера обновления кэша с State Manager.
    
    Args:
        state: BotSystemState instance
    """
    # Получаем статистику через state
    stats = state.bot_manager.get_global_stats()
    
    logger.debug(
        f"[CACHE] Обновление: ботов={stats['total_bots']}, "
        f"активных={stats['active_bots']}, "
        f"в позиции={stats['bots_in_position']}"
    )
    
    # Здесь можно обновлять кэши, БД, и т.д.
    # ...


# ==================== Фабрика воркеров ====================

def create_auto_bot_worker(state, shutdown_flag, interval=60):
    """
    Создать и запустить Auto Bot воркер.
    
    Args:
        state: BotSystemState instance
        shutdown_flag: threading.Event для остановки
        interval: Интервал в секундах
    """
    worker = StateAwareWorker('AUTO_BOT', state, interval)
    worker.run_periodic(shutdown_flag, example_auto_bot_worker)


def create_sync_positions_worker(state, shutdown_flag, interval=30):
    """
    Создать и запустить воркер синхронизации позиций.
    
    Args:
        state: BotSystemState instance
        shutdown_flag: threading.Event для остановки
        interval: Интервал в секундах
    """
    worker = StateAwareWorker('SYNC_POSITIONS', state, interval)
    worker.run_periodic(shutdown_flag, example_sync_positions_worker)


def create_cache_update_worker(state, shutdown_flag, interval=30):
    """
    Создать и запустить воркер обновления кэша.
    
    Args:
        state: BotSystemState instance
        shutdown_flag: threading.Event для остановки
        interval: Интервал в секундах
    """
    worker = StateAwareWorker('CACHE_UPDATE', state, interval)
    worker.run_periodic(shutdown_flag, example_cache_update_worker)

