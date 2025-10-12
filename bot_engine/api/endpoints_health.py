"""
API endpoints для проверки здоровья системы (новая версия для State Manager).
"""

from flask import jsonify
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def register_health_endpoints(app, state):
    """
    Регистрирует endpoints для проверки здоровья системы.
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Проверка здоровья сервиса"""
        try:
            # Получаем информацию от всех менеджеров
            exchange_info = state.exchange_manager.get_exchange_info()
            rsi_info = state.rsi_manager.get_info()
            bots_info = state.bot_manager.get_info()
            
            return jsonify({
                'status': 'ok',
                'service': 'bots',
                'timestamp': datetime.now().isoformat(),
                'exchange_connected': exchange_info['initialized'],
                'coins_loaded': rsi_info['total_coins'],
                'bots_active': bots_info['active_bots']
            })
            
        except Exception as e:
            logger.error(f"[HEALTH] Ошибка: {e}")
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500
    
    @app.route('/api/system-status', methods=['GET'])
    def system_status():
        """Полный статус системы (детальный)"""
        try:
            # Получаем полный статус от BotSystemState
            system_status = state.get_system_status()
            
            return jsonify({
                'success': True,
                'status': system_status,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"[API_STATUS] Ошибка: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

