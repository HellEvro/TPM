"""
BotAdapter - адаптер между старым NewTradingBot и новым State Manager.

Это промежуточное решение, которое позволяет использовать State Manager
без полной переработки NewTradingBot.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BotAdapter:
    """
    Адаптер для работы со старым NewTradingBot через State Manager.
    
    Этот класс оборачивает NewTradingBot и предоставляет доступ
    к менеджерам через state, избегая глобальных переменных.
    
    Attributes:
        bot: Instance старого NewTradingBot
        state: BotSystemState instance
        symbol: Символ монеты
    """
    
    def __init__(self, symbol: str, config: Dict[str, Any], state):
        """
        Инициализация адаптера.
        
        Args:
            symbol: Символ монеты
            config: Конфигурация бота
            state: BotSystemState instance
        """
        self.symbol = symbol
        self.state = state
        self.config = config
        
        # Импортируем старый класс
        from bots import NewTradingBot
        
        # Создаем бота с exchange из state
        self.bot = NewTradingBot(
            symbol=symbol,
            config=config,
            exchange=state.exchange_manager.exchange
        )
        
        logger.info(f"[BotAdapter] Создан адаптер для бота {symbol}")
    
    # ==================== Делегирование к bot ====================
    
    @property
    def status(self):
        """Получить статус бота"""
        return self.bot.status
    
    @status.setter
    def status(self, value):
        """Установить статус бота"""
        self.bot.status = value
    
    @property
    def entry_price(self):
        """Получить цену входа"""
        return self.bot.entry_price
    
    @property
    def position_side(self):
        """Получить сторону позиции"""
        return self.bot.position_side
    
    @property
    def unrealized_pnl(self):
        """Получить нереализованный P&L"""
        return getattr(self.bot, 'unrealized_pnl', 0.0)
    
    @property
    def realized_pnl(self):
        """Получить реализованный P&L"""
        return getattr(self.bot, 'realized_pnl', 0.0)
    
    # ==================== Основные методы ====================
    
    def update_status(self, new_status: str, **kwargs):
        """Обновить статус бота"""
        return self.bot.update_status(new_status, **kwargs)
    
    def update(self, force_analysis: bool = False, 
              external_signal: Optional[str] = None,
              external_trend: Optional[str] = None):
        """
        Обновить бота.
        
        Args:
            force_analysis: Принудительный анализ
            external_signal: Внешний сигнал
            external_trend: Внешний тренд
        
        Returns:
            Результат обновления
        """
        # Получаем RSI данные из state
        rsi_data = self.state.rsi_manager.get_rsi(self.symbol)
        
        # Если есть внешние данные, используем их
        if external_signal:
            return self.bot.update(
                force_analysis=force_analysis,
                external_signal=external_signal,
                external_trend=external_trend
            )
        
        # Иначе используем данные из RSI manager
        if rsi_data:
            return self.bot.update(
                force_analysis=force_analysis,
                external_signal=rsi_data.get('signal'),
                external_trend=rsi_data.get('trend')
            )
        
        # Если нет данных, просто обновляем
        return self.bot.update(force_analysis=force_analysis)
    
    def start(self):
        """Запустить бота"""
        if hasattr(self.bot, 'start'):
            return self.bot.start()
        else:
            self.update_status('running')
            return {'success': True}
    
    def stop(self):
        """Остановить бота"""
        if hasattr(self.bot, 'stop'):
            return self.bot.stop()
        else:
            self.update_status('idle')
            return {'success': True}
    
    def pause(self):
        """Приостановить бота"""
        if hasattr(self.bot, 'pause'):
            return self.bot.pause()
        else:
            self.update_status('paused')
            return {'success': True}
    
    def resume(self):
        """Возобновить бота"""
        if hasattr(self.bot, 'resume'):
            return self.bot.resume()
        else:
            self.update_status('running')
            return {'success': True}
    
    def close_position(self):
        """Закрыть позицию"""
        if hasattr(self.bot, 'close_position'):
            return self.bot.close_position()
        return {'success': False, 'error': 'Method not implemented'}
    
    # ==================== Проверки состояния ====================
    
    def has_position(self) -> bool:
        """Проверить есть ли открытая позиция"""
        return self.status in ['in_position_long', 'in_position_short']
    
    def is_active(self) -> bool:
        """Проверить активен ли бот"""
        return self.status == 'running'
    
    def is_paused(self) -> bool:
        """Проверить приостановлен ли бот"""
        return self.status == 'paused'
    
    # ==================== Сериализация ====================
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализовать бота в словарь.
        
        Returns:
            Словарь с данными бота
        """
        if hasattr(self.bot, 'to_dict'):
            return self.bot.to_dict()
        
        # Базовая сериализация
        return {
            'symbol': self.symbol,
            'status': self.status,
            'entry_price': self.entry_price,
            'position_side': self.position_side,
            'unrealized_pnl': self.unrealized_pnl,
            'config': self.config
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """
        Восстановить бота из словаря.
        
        Args:
            data: Словарь с данными бота
        """
        if hasattr(self.bot, 'from_dict'):
            self.bot.from_dict(data)
        else:
            # Базовое восстановление
            self.bot.status = data.get('status', 'idle')
            self.bot.entry_price = data.get('entry_price')
            self.bot.position_side = data.get('position_side')
    
    # ==================== Утилиты ====================
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"<BotAdapter(symbol={self.symbol}, status={self.status})>"
    
    def __getattr__(self, name):
        """
        Делегирование всех остальных атрибутов к bot.
        
        Это позволяет прозрачно использовать методы NewTradingBot.
        """
        return getattr(self.bot, name)

