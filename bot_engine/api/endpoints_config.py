"""
API endpoints для управления конфигурацией (новая версия для State Manager).
"""

from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)


def register_config_endpoints(app, state):
    """
    Регистрирует endpoints для конфигурации.
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    
    @app.route('/api/bots/auto-bot', methods=['GET'])
    def get_auto_bot_config():
        """Получить конфигурацию Auto Bot"""
        try:
            config = state.config_manager.get_auto_bot_config()
            
            return jsonify({
                'success': True,
                'config': config
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка получения конфигурации: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/auto-bot', methods=['POST'])
    def update_auto_bot_config():
        """Обновить конфигурацию Auto Bot"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Обновляем через ConfigManager
            state.config_manager.update_auto_bot_config(data)
            
            # Получаем обновленную конфигурацию
            updated_config = state.config_manager.get_auto_bot_config()
            
            logger.info(f"[CONFIG] Auto Bot конфигурация обновлена")
            
            return jsonify({
                'success': True,
                'config': updated_config,
                'message': 'Конфигурация обновлена'
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка обновления конфигурации: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/auto-bot/restore-defaults', methods=['POST'])
    def restore_auto_bot_defaults():
        """Восстановить дефолтную конфигурацию Auto Bot"""
        try:
            state.config_manager.restore_default_auto_bot_config()
            
            config = state.config_manager.get_auto_bot_config()
            
            logger.info("[CONFIG] Восстановлена дефолтная конфигурация Auto Bot")
            
            return jsonify({
                'success': True,
                'config': config,
                'message': 'Конфигурация восстановлена'
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка восстановления конфигурации: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/system-config', methods=['GET'])
    def get_system_config():
        """Получить системную конфигурацию"""
        try:
            config = state.config_manager.get_system_config()
            
            return jsonify({
                'success': True,
                'config': config
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/system-config', methods=['POST'])
    def update_system_config():
        """Обновить системную конфигурацию"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            state.config_manager.update_system_config(data)
            
            return jsonify({
                'success': True,
                'config': state.config_manager.get_system_config(),
                'message': 'Системная конфигурация обновлена'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/system-config', methods=['GET', 'POST'])
    def system_config_endpoint():
        """Получить или обновить системную конфигурацию"""
        try:
            if request.method == 'GET':
                # Получаем системную конфигурацию
                config = state.config_manager.get_system_config()
                
                return jsonify({
                    'success': True,
                    'config': config
                })
            
            else:  # POST
                # Обновляем системную конфигурацию
                new_config = request.get_json()
                
                if not new_config:
                    return jsonify({'success': False, 'error': 'Не указана конфигурация'}), 400
                
                # Сохраняем через ConfigManager
                state.config_manager.update_system_config(new_config)
                
                return jsonify({
                    'success': True,
                    'message': 'Системная конфигурация обновлена'
                })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

