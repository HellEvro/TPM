"""
API endpoints для работы с зрелыми монетами (State Manager версия)
"""

from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)


def register_mature_endpoints(app, state):
    """
    Регистрирует endpoints для работы с зрелыми монетами
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    
    @app.route('/api/bots/mature-coins', methods=['GET'])
    def get_mature_coins():
        """Получить список зрелых монет"""
        try:
            # TODO: Добавить в State Manager если нужно
            return jsonify({
                'success': True,
                'coins': [],
                'count': 0
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка получения зрелых монет: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/mature-coins-list', methods=['GET'])
    def get_mature_coins_list():
        """Получить список зрелых монет (альтернативный формат)"""
        try:
            return jsonify({
                'success': True,
                'mature_coins': [],
                'total': 0
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    logger.info("[API] Mature coins endpoints registered")

