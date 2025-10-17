"""
API endpoints для управления ИИ модулями
"""

from flask import jsonify, request
import logging

logger = logging.getLogger('API.AI')


def register_ai_endpoints(app):
    """Регистрирует API endpoints для ИИ"""
    
    @app.route('/api/ai/status', methods=['GET'])
    def get_ai_status():
        """Получить статус ИИ системы"""
        try:
            from bot_engine.ai.ai_manager import get_ai_manager
            from bot_engine.ai.auto_trainer import get_auto_trainer
            from bot_engine.bot_config import AIConfig
            
            ai_manager = get_ai_manager()
            auto_trainer = get_auto_trainer()
            
            return jsonify({
                'success': True,
                'ai_status': ai_manager.get_status(),
                'auto_trainer': auto_trainer.get_status(),
                'config': {
                    'enabled': AIConfig.AI_ENABLED,
                    'auto_train_enabled': AIConfig.AI_AUTO_TRAIN_ENABLED,
                    'auto_update_data': AIConfig.AI_AUTO_UPDATE_DATA,
                    'auto_retrain': AIConfig.AI_AUTO_RETRAIN,
                    'data_update_interval_hours': AIConfig.AI_DATA_UPDATE_INTERVAL / 3600,
                    'retrain_interval_days': AIConfig.AI_RETRAIN_INTERVAL / 86400
                }
            })
        
        except Exception as e:
            logger.error(f"Ошибка получения статуса ИИ: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/ai/force-update', methods=['POST'])
    def force_ai_update():
        """Принудительное обновление данных и переобучение"""
        try:
            from bot_engine.ai.auto_trainer import get_auto_trainer
            
            auto_trainer = get_auto_trainer()
            success = auto_trainer.force_update()
            
            return jsonify({
                'success': success,
                'message': 'Обновление запущено' if success else 'Ошибка обновления'
            })
        
        except Exception as e:
            logger.error(f"Ошибка принудительного обновления: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/ai/anomaly-stats', methods=['GET'])
    def get_anomaly_stats():
        """Получить статистику обнаруженных аномалий"""
        try:
            # TODO: Реализовать сбор статистики аномалий
            # Можно хранить в отдельном файле или БД
            
            return jsonify({
                'success': True,
                'stats': {
                    'total_analyzed': 0,
                    'anomalies_detected': 0,
                    'blocked_entries': 0,
                    'by_type': {
                        'PUMP': 0,
                        'DUMP': 0,
                        'MANIPULATION': 0
                    }
                }
            })
        
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    logger.info("[API] ✅ AI endpoints зарегистрированы")

