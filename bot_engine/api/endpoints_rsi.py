"""
API endpoints для RSI данных (новая версия для State Manager).
"""

from flask import request, jsonify
import logging
import threading

logger = logging.getLogger(__name__)


def register_rsi_endpoints(app, state):
    """
    Регистрирует endpoints для RSI данных.
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    
    @app.route('/api/bots/coins-with-rsi', methods=['GET'])
    def get_coins_with_rsi():
        """Получить все монеты с RSI данными"""
        try:
            # Получаем все монеты через RSIDataManager
            all_coins = state.rsi_manager.get_all_coins()
            
            # Статистика обновления
            try:
                update_stats = state.rsi_manager.get_update_stats()
            except Exception as stats_error:
                logger.warning(f"[API] Не удалось получить статистику обновления: {stats_error}")
                update_stats = {
                    'update_in_progress': False,
                    'last_update': None,
                    'successful_coins': 0,
                    'failed_coins': 0
                }
            
            # Распределение сигналов
            try:
                signal_dist = state.rsi_manager.get_signal_distribution()
            except Exception as dist_error:
                logger.warning(f"[API] Не удалось получить распределение сигналов: {dist_error}")
                signal_dist = {'long': 0, 'short': 0, 'neutral': 0}
            
            return jsonify({
                'success': True,
                'coins': all_coins,
                'total_coins': len(all_coins),
                'update_in_progress': update_stats.get('update_in_progress', False),
                'last_update': update_stats.get('last_update'),
                'successful_coins': update_stats.get('successful_coins', 0),
                'failed_coins': update_stats.get('failed_coins', 0),
                'signals': signal_dist
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка получения RSI данных: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'coins': {}
            }), 500
    
    @app.route('/api/bots/load-rsi', methods=['POST'])
    def load_rsi():
        """Запустить загрузку RSI данных"""
        try:
            # Проверяем не идет ли уже обновление
            if state.rsi_manager.is_update_in_progress():
                return jsonify({
                    'success': False,
                    'error': 'Обновление уже идет'
                }), 400
            
            # Запускаем обновление в отдельном потоке
            def update_rsi_data():
                try:
                    # Импортируем функцию загрузки из legacy
                    from bots_legacy import load_all_coins_rsi
                    load_all_coins_rsi()
                except Exception as e:
                    logger.error(f"[RSI_UPDATE] Ошибка: {e}")
            
            thread = threading.Thread(target=update_rsi_data, daemon=True)
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Загрузка RSI запущена'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/force-rsi-update', methods=['POST'])
    def force_rsi_update():
        """Принудительное обновление RSI"""
        try:
            # Запускаем обновление
            if not state.rsi_manager.start_update():
                return jsonify({
                    'success': False,
                    'error': 'Обновление уже идет'
                }), 400
            
            def update_rsi_data():
                try:
                    from bots_legacy import load_all_coins_rsi
                    load_all_coins_rsi()
                except Exception as e:
                    logger.error(f"[RSI_UPDATE] Ошибка: {e}")
                    state.rsi_manager.finish_update(0, 1)
            
            thread = threading.Thread(target=update_rsi_data, daemon=True)
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Принудительное обновление RSI запущено'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

