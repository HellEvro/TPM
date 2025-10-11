"""
BotManager - управление всеми торговыми ботами.

Этот менеджер инкапсулирует всю логику работы с ботами,
заменяя глобальную переменную bots_data.
"""

import threading
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)


class BotManager:
    """
    Менеджер для управления всеми торговыми ботами.
    
    Инкапсулирует хранение ботов и операции с ними,
    обеспечивая thread-safety.
    
    Attributes:
        exchange_manager: Менеджер биржи
        rsi_manager: Менеджер RSI данных
        _bots: Словарь ботов {symbol: bot_instance}
        _lock: Блокировка для thread-safety
    """
    
    def __init__(self, exchange_manager, rsi_manager, state=None):
        """
        Инициализация менеджера ботов.
        
        Args:
            exchange_manager: ExchangeManager instance
            rsi_manager: RSIDataManager instance
            state: BotSystemState instance (опционально, для BotAdapter)
        """
        self.exchange_manager = exchange_manager
        self.rsi_manager = rsi_manager
        self.state = state  # Сохраняем ссылку на state
        
        self._bots = {}  # {symbol: bot_instance}
        self._lock = threading.Lock()
        
        logger.info("[BotManager] Инициализирован")
    
    # ==================== Основные операции ====================
    
    def create_bot(self, symbol: str, config: Dict[str, Any], bot_class=None, state=None):
        """
        Создать нового бота.
        
        Args:
            symbol: Символ монеты
            config: Конфигурация бота
            bot_class: Класс бота (если None, используется BotAdapter)
            state: BotSystemState (для BotAdapter)
        
        Returns:
            Созданный бот
        
        Raises:
            ValueError: Если бот уже существует
        """
        with self._lock:
            if symbol in self._bots:
                raise ValueError(f"Bot for {symbol} already exists")
            
            # Используем BotAdapter по умолчанию
            if bot_class is None:
                from bot_engine.bot_adapter import BotAdapter
                
                # Для BotAdapter нужен state - используем родительский
                if state is None:
                    # Пытаемся получить state из self если он там есть
                    state = getattr(self, 'state', None)
                    
                if state is None:
                    raise ValueError("State is required for BotAdapter")
                
                bot = BotAdapter(symbol, config, state)
            else:
                # Используем переданный класс
                bot = bot_class(symbol, config)
            
            self._bots[symbol] = bot
            logger.info(f"[BotManager] Создан бот для {symbol}")
            return bot
    
    def get_bot(self, symbol: str):
        """
        Получить бота по символу.
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Bot instance или None
        """
        with self._lock:
            return self._bots.get(symbol)
    
    def delete_bot(self, symbol: str) -> bool:
        """
        Удалить бота.
        
        Args:
            symbol: Символ монеты
        
        Returns:
            True если бот был удален, False если не найден
        """
        with self._lock:
            if symbol in self._bots:
                bot = self._bots[symbol]
                
                # Останавливаем бота если он запущен
                if hasattr(bot, 'stop'):
                    try:
                        bot.stop()
                    except Exception as e:
                        logger.error(f"[BotManager] Ошибка остановки бота {symbol}: {e}")
                
                del self._bots[symbol]
                logger.info(f"[BotManager] Удален бот {symbol}")
                return True
            
            return False
    
    def list_bots(self) -> List:
        """
        Получить список всех ботов.
        
        Returns:
            Список bot instances
        """
        with self._lock:
            return list(self._bots.values())
    
    def get_bots_dict(self) -> Dict[str, Any]:
        """
        Получить словарь всех ботов.
        
        Returns:
            Словарь {symbol: bot}
        """
        with self._lock:
            return dict(self._bots)
    
    # ==================== Статистика ====================
    
    def get_bots_count(self) -> int:
        """
        Получить общее количество ботов.
        
        Returns:
            Количество ботов
        """
        with self._lock:
            return len(self._bots)
    
    def get_active_bots_count(self) -> int:
        """
        Получить количество активных ботов (статус running).
        
        Returns:
            Количество активных ботов
        """
        with self._lock:
            return sum(1 for bot in self._bots.values() if bot.status == 'running')
    
    def get_bots_in_position_count(self) -> int:
        """
        Получить количество ботов с открытыми позициями.
        
        Returns:
            Количество ботов в позиции
        """
        with self._lock:
            count = sum(
                1 for bot in self._bots.values()
                if bot.status in ['in_position_long', 'in_position_short']
            )
            return count
    
    def get_armed_bots_count(self) -> int:
        """
        Получить количество взведенных ботов.
        
        Returns:
            Количество взведенных ботов
        """
        with self._lock:
            count = sum(
                1 for bot in self._bots.values()
                if bot.status in ['armed_up', 'armed_down']
            )
            return count
    
    def get_paused_bots_count(self) -> int:
        """
        Получить количество приостановленных ботов.
        
        Returns:
            Количество приостановленных ботов
        """
        with self._lock:
            return sum(1 for bot in self._bots.values() if bot.status == 'paused')
    
    def calculate_total_pnl(self) -> float:
        """
        Рассчитать общий P&L всех ботов.
        
        Returns:
            Суммарный P&L
        """
        with self._lock:
            total_pnl = 0.0
            for bot in self._bots.values():
                if hasattr(bot, 'realized_pnl'):
                    total_pnl += bot.realized_pnl
                if hasattr(bot, 'unrealized_pnl'):
                    total_pnl += bot.unrealized_pnl
            return total_pnl
    
    def get_global_stats(self) -> Dict[str, Any]:
        """
        Получить глобальную статистику по ботам.
        
        Returns:
            Словарь со статистикой
        """
        with self._lock:
            return {
                'total_bots': len(self._bots),
                'active_bots': self.get_active_bots_count(),
                'bots_in_position': self.get_bots_in_position_count(),
                'armed_bots': self.get_armed_bots_count(),
                'paused_bots': self.get_paused_bots_count(),
                'total_pnl': self.calculate_total_pnl()
            }
    
    # ==================== Фильтрация ====================
    
    def get_bots_by_status(self, status: str) -> List:
        """
        Получить ботов с определенным статусом.
        
        Args:
            status: Статус ('running', 'armed_up', 'in_position_long', etc.)
        
        Returns:
            Список ботов
        """
        with self._lock:
            return [bot for bot in self._bots.values() if bot.status == status]
    
    def get_bots_in_position(self) -> List:
        """
        Получить всех ботов с открытыми позициями.
        
        Returns:
            Список ботов в позиции
        """
        with self._lock:
            return [
                bot for bot in self._bots.values()
                if bot.status in ['in_position_long', 'in_position_short']
            ]
    
    def get_bots_without_position(self) -> List:
        """
        Получить ботов без позиций.
        
        Returns:
            Список ботов без позиций
        """
        with self._lock:
            return [
                bot for bot in self._bots.values()
                if bot.status not in ['in_position_long', 'in_position_short']
            ]
    
    # ==================== Массовые операции ====================
    
    def stop_all_bots(self) -> int:
        """
        Остановить всех ботов.
        
        Returns:
            Количество остановленных ботов
        """
        with self._lock:
            count = 0
            for bot in self._bots.values():
                if hasattr(bot, 'stop'):
                    try:
                        bot.stop()
                        count += 1
                    except Exception as e:
                        logger.error(f"[BotManager] Ошибка остановки бота {bot.symbol}: {e}")
            
            logger.info(f"[BotManager] Остановлено ботов: {count}")
            return count
    
    def pause_all_bots(self) -> int:
        """
        Приостановить всех ботов.
        
        Returns:
            Количество приостановленных ботов
        """
        with self._lock:
            count = 0
            for bot in self._bots.values():
                if hasattr(bot, 'pause'):
                    try:
                        bot.pause()
                        count += 1
                    except Exception as e:
                        logger.error(f"[BotManager] Ошибка паузы бота {bot.symbol}: {e}")
            
            logger.info(f"[BotManager] Приостановлено ботов: {count}")
            return count
    
    def resume_all_bots(self) -> int:
        """
        Возобновить работу всех приостановленных ботов.
        
        Returns:
            Количество возобновленных ботов
        """
        with self._lock:
            count = 0
            for bot in self._bots.values():
                if bot.status == 'paused' and hasattr(bot, 'resume'):
                    try:
                        bot.resume()
                        count += 1
                    except Exception as e:
                        logger.error(f"[BotManager] Ошибка возобновления бота {bot.symbol}: {e}")
            
            logger.info(f"[BotManager] Возобновлено ботов: {count}")
            return count
    
    def close_all_positions(self) -> int:
        """
        Закрыть все позиции.
        
        Returns:
            Количество закрытых позиций
        """
        with self._lock:
            count = 0
            for bot in self._bots.values():
                if bot.status in ['in_position_long', 'in_position_short']:
                    if hasattr(bot, 'close_position'):
                        try:
                            bot.close_position()
                            count += 1
                        except Exception as e:
                            logger.error(f"[BotManager] Ошибка закрытия позиции {bot.symbol}: {e}")
            
            logger.info(f"[BotManager] Закрыто позиций: {count}")
            return count
    
    # ==================== Сохранение/загрузка ====================
    
    def get_bots_state(self) -> Dict[str, Any]:
        """
        Получить состояние всех ботов для сохранения.
        
        Returns:
            Словарь с состоянием ботов
        """
        with self._lock:
            state = {}
            for symbol, bot in self._bots.items():
                if hasattr(bot, 'to_dict'):
                    state[symbol] = bot.to_dict()
                else:
                    # Базовое состояние если метода нет
                    state[symbol] = {
                        'symbol': bot.symbol,
                        'status': bot.status,
                        'config': getattr(bot, 'config', {})
                    }
            
            logger.debug(f"[BotManager] Сохранено состояние {len(state)} ботов")
            return state
    
    def restore_bots(self, bots_state: Dict[str, Any], bot_class=None) -> int:
        """
        Восстановить ботов из сохраненного состояния.
        
        Args:
            bots_state: Словарь с состоянием ботов
            bot_class: Класс бота для создания
        
        Returns:
            Количество восстановленных ботов
        """
        with self._lock:
            count = 0
            for symbol, bot_data in bots_state.items():
                try:
                    # Создаем бота
                    config = bot_data.get('config', {})
                    bot = self.create_bot(symbol, config, bot_class)
                    
                    # Восстанавливаем состояние
                    if hasattr(bot, 'from_dict'):
                        bot.from_dict(bot_data)
                    else:
                        # Базовое восстановление
                        bot.status = bot_data.get('status', 'idle')
                    
                    count += 1
                except Exception as e:
                    logger.error(f"[BotManager] Ошибка восстановления бота {symbol}: {e}")
            
            logger.info(f"[BotManager] Восстановлено {count} ботов")
            return count
    
    # ==================== Утилиты ====================
    
    def __repr__(self) -> str:
        """Строковое представление"""
        with self._lock:
            return f"<BotManager(bots={len(self._bots)}, active={self.get_active_bots_count()})>"
    
    def get_info(self) -> Dict[str, Any]:
        """
        Получить информацию о менеджере.
        
        Returns:
            Словарь с информацией
        """
        return {
            'total_bots': self.get_bots_count(),
            'active_bots': self.get_active_bots_count(),
            'bots_in_position': self.get_bots_in_position_count(),
            'armed_bots': self.get_armed_bots_count(),
            'paused_bots': self.get_paused_bots_count(),
            'total_pnl': self.calculate_total_pnl()
        }

