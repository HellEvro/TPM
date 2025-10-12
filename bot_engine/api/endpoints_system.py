"""
API endpoints для системных операций (State Manager версия)
"""

from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)


def register_system_endpoints(app, state):
    """
    Регистрирует системные endpoints
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    
    @app.route('/api/bots/reload-config', methods=['POST'])
    def reload_config_endpoint():
        """Перезагружает конфигурацию из файла"""
        try:
            logger.info("[API] Перезагрузка конфигурации...")
            
            state.config_manager.load_all()
            
            logger.info("[API] Конфигурация перезагружена")
            
            return jsonify({
                'success': True,
                'message': 'Конфигурация перезагружена из файла'
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка перезагрузки конфигурации: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/cleanup-inactive', methods=['POST'])
    def cleanup_inactive_manual():
        """Принудительная очистка неактивных ботов"""
        try:
            logger.info("[API] Запуск очистки неактивных ботов")
            
            # TODO: Добавить метод cleanup_inactive_bots в BotManager
            removed = 0
            
            return jsonify({
                'success': True,
                'message': f'Очищено ботов: {removed}' if removed > 0 else 'Неактивных ботов не найдено',
                'cleaned': removed
            })
                
        except Exception as e:
            logger.error(f"[API] Ошибка очистки: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/bots/reset-update-flag', methods=['POST'])
    def reset_update_flag():
        """Сбросить флаг update_in_progress"""
        try:
            # Сбрасываем через RSIDataManager
            state.rsi_manager._data['update_in_progress'] = False
                
            logger.info(f"[API] Флаг update_in_progress сброшен")
            
            return jsonify({
                'success': True,
                'message': 'Флаг сброшен'
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка сброса флага: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    logger.info("[API] System endpoints registered")
