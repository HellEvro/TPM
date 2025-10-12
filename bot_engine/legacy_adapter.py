"""
Legacy Adapter - адаптер между State Manager и старыми API endpoints.

Предоставляет совместимость со старыми endpoints которые ожидают
глобальные переменные bots_data, coins_rsi_data, etc.
"""

import threading
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LegacyStateAdapter:
    """
    Адаптер который эмулирует старую структуру данных
    используя новый State Manager.
    
    Это позволяет старым endpoints работать без изменений.
    """
    
    def __init__(self, bot_system_state):
        """
        Args:
            bot_system_state: BotSystemState instance
        """
        self.state = bot_system_state
        
        # Импортируем функции из legacy кода
        from bots_legacy import (
            BOT_STATUS,
            ensure_exchange_initialized,
            create_new_bot,
            save_bots_state,
            update_bots_cache_data,
            log_bot_stop,
            check_coin_maturity_with_storage
        )
        
        self.BOT_STATUS = BOT_STATUS
        self.ensure_exchange_func = ensure_exchange_initialized
        self.create_bot_func = create_new_bot
        self.save_bots_func = save_bots_state
        self.update_cache_func = update_bots_cache_data
        self.log_bot_stop_func = log_bot_stop
        self.check_maturity_func = check_coin_maturity_with_storage
        
        logger.info("[LegacyAdapter] Инициализирован")
    
    def get_legacy_state_dict(self) -> Dict[str, Any]:
        """
        Создает словарь в формате старых endpoints.
        
        Returns:
            Словарь с данными в старом формате
        """
        # Эмулируем bots_data
        bots_list = self.state.bot_manager.list_bots()
        bots_dict = {}
        for bot in bots_list:
            bot_data = bot.to_dict() if hasattr(bot, 'to_dict') else {'symbol': bot.symbol, 'status': bot.status}
            bots_dict[bot.symbol] = bot_data
        
        bots_data = {
            'bots': bots_dict,
            'auto_bot_config': self.state.config_manager.get_auto_bot_config(),
            'global_stats': self.state.bot_manager.get_global_stats()
        }
        
        # Эмулируем coins_rsi_data
        coins_rsi_data = self.state.rsi_manager.get_all_data()
        
        # Создаем фейковые блокировки (они не нужны, так как state уже thread-safe)
        fake_lock = threading.Lock()
        
        return {
            # Данные
            'bots_data': bots_data,
            'coins_rsi_data': coins_rsi_data,
            
            # Блокировки (фейковые - state уже thread-safe)
            'bots_data_lock': fake_lock,
            'rsi_data_lock': fake_lock,
            
            # Объекты
            'exchange': self.state.exchange_manager.exchange,
            
            # Функции из legacy кода
            'ensure_exchange_func': self.ensure_exchange_func,
            'create_bot_func': self.create_bot_func,
            'save_bots_func': self.save_bots_func,
            'update_cache_func': self.update_cache_func,
            'log_bot_stop_func': self.log_bot_stop_func,
            'check_maturity_func': self.check_maturity_func,
            
            # Константы
            'BOT_STATUS': self.BOT_STATUS,
            
            # Функция получения состояния
            'get_state_func': lambda: {
                'exchange': self.state.exchange_manager.get_exchange_info(),
                'bots': self.state.bot_manager.get_global_stats(),
                'rsi': self.state.rsi_manager.get_info(),
                'config': self.state.config_manager.get_info()
            }
        }

