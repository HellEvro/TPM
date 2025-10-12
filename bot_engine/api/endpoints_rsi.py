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
            # Получаем все монеты через RSIDataManager с таймаутом
            import threading
            import queue
            
            result_queue = queue.Queue()
            
            def get_coins_thread():
                try:
                    coins = state.rsi_manager.get_all_coins()
                    result_queue.put(('success', coins))
                except Exception as e:
                    result_queue.put(('error', str(e)))
            
            thread = threading.Thread(target=get_coins_thread, daemon=True)
            thread.start()
            thread.join(timeout=5)  # 5 секунд таймаут
            
            if thread.is_alive():
                logger.error("[API] Таймаут получения RSI данных")
                return jsonify({
                    'success': False,
                    'error': 'Таймаут получения данных RSI'
                }), 408
            
            if result_queue.empty():
                logger.error("[API] Не удалось получить RSI данные")
                return jsonify({
                    'success': False,
                    'error': 'Не удалось получить RSI данные'
                }), 500
            
            status, result = result_queue.get()
            if status == 'error':
                logger.error(f"[API] Ошибка получения RSI данных: {result}")
                return jsonify({
                    'success': False,
                    'error': result
                }), 500
            
            all_coins = result
            
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
            
            # Запускаем обновление через RSIDataManager
            def update_rsi_data():
                try:
                    logger.info("[RSI_UPDATE] Запуск загрузки RSI...")
                    
                    # Получаем биржу
                    exchange = state.exchange_manager.get_exchange()
                    if not exchange:
                        logger.error("[RSI_UPDATE] Биржа не инициализирована")
                        return
                    
                    # Получаем список монет
                    pairs = exchange.get_all_pairs()
                    logger.info(f"[RSI_UPDATE] Загрузка RSI для {len(pairs)} монет...")
                    
                    # Загружаем RSI для каждой монеты
                    state.rsi_manager.start_update(len(pairs))
                    
                    for i, symbol in enumerate(pairs):
                        try:
                            # Получаем свечи
                            candles = exchange.get_klines(symbol + 'USDT', '6h', limit=100)
                            if candles and len(candles) >= 14:
                                # Вычисляем RSI
                                closes = [float(c['close']) for c in candles]
                                
                                # Простой RSI расчет
                                from bot_engine.utils.rsi_utils import calculate_rsi
                                rsi = calculate_rsi(closes, period=14)
                                
                                if rsi is not None:
                                    # Сохраняем данные
                                    coin_data = {
                                        'rsi': rsi,
                                        'price': closes[-1],
                                        'timestamp': candles[-1]['timestamp'],
                                        'signal': 'long' if rsi <= 29 else ('short' if rsi >= 71 else 'neutral')
                                    }
                                    state.rsi_manager.update_coin(symbol, coin_data)
                        except Exception as e:
                            logger.warning(f"[RSI_UPDATE] Ошибка загрузки {symbol}: {e}")
                    
                    state.rsi_manager.finish_update(len(pairs), 0)
                    logger.info("[RSI_UPDATE] ✅ Загрузка RSI завершена")
                    
                except Exception as e:
                    logger.error(f"[RSI_UPDATE] Ошибка: {e}")
                    state.rsi_manager.finish_update(0, 0)
            
            import threading
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
                    # Используем правильный метод из RSIDataManager
                    exchange = state.exchange_manager.get_exchange()
                    if exchange:
                        state.rsi_manager.load_all_coins_async(exchange)
                    else:
                        logger.error("[RSI_UPDATE] Exchange не инициализирован")
                        state.rsi_manager.finish_update(0, 1)
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

