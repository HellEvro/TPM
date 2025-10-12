"""
API endpoints для State Manager (новая версия).
"""

import logging

from .endpoints_health_new import register_health_endpoints
from .endpoints_bots_new import register_bots_endpoints
from .endpoints_config_new import register_config_endpoints
from .endpoints_rsi_new import register_rsi_endpoints

logger = logging.getLogger(__name__)

__all__ = [
    'register_all_endpoints_new',
]


def register_all_endpoints_new(app, state):
    """
    Регистрирует все API endpoints для State Manager.
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    logger.info("[API] Регистрация endpoints для State Manager...")
    
    register_health_endpoints(app, state)
    logger.info("[API] ✅ Health endpoints зарегистрированы")
    
    register_bots_endpoints(app, state)
    logger.info("[API] ✅ Bots endpoints зарегистрированы")
    
    register_config_endpoints(app, state)
    logger.info("[API] ✅ Config endpoints зарегистрированы")
    
    register_rsi_endpoints(app, state)
    logger.info("[API] ✅ RSI endpoints зарегистрированы")
    
    logger.info("[API] ✅ Все endpoints зарегистрированы!")

