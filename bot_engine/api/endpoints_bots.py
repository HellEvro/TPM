"""
API endpoints для управления ботами (новая версия для State Manager).
"""

from flask import request, jsonify
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def register_bots_endpoints(app, state):
    """
    Регистрирует endpoints для управления ботами.
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    
    @app.route('/api/bots/list', methods=['GET'])
    def get_bots_list():
        """Получить список всех ботов"""
        try:
            # Получаем ботов через BotManager
            bots = state.bot_manager.list_bots()
            bots_list = [bot.to_dict() for bot in bots]
            
            # Получаем конфиг через ConfigManager
            auto_config = state.config_manager.get_auto_bot_config()
            auto_bot_enabled = auto_config.get('enabled', False)
            
            # Статистика через BotManager
            stats = state.bot_manager.get_global_stats()
            
            return jsonify({
                'success': True,
                'bots': bots_list,
                'count': len(bots_list),
                'auto_bot_enabled': auto_bot_enabled,
                'last_update': datetime.now().isoformat(),
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка получения списка ботов: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'bots': [],
                'count': 0
            }), 500
    
    @app.route('/api/bots/create', methods=['POST'])
    def create_bot_endpoint():
        """Создать нового бота"""
        try:
            # Проверяем инициализацию биржи
            if not state.exchange_manager.is_initialized():
                return jsonify({
                    'success': False,
                    'error': 'Биржа не инициализирована'
                }), 503
            
            data = request.get_json()
            if not data or not data.get('symbol'):
                return jsonify({'success': False, 'error': 'Symbol required'}), 400
            
            symbol = data['symbol']
            config = data.get('config', {})
            
            logger.info(f"[BOT_CREATE] Создание бота для {symbol}")
            
            # Проверяем зрелость если включена
            enable_maturity_check = config.get('enable_maturity_check', True)
            if enable_maturity_check:
                from bot_engine.maturity_checker import check_coin_maturity_with_storage
                
                # Получаем свечи
                klines = state.exchange_manager.get_klines(symbol, '6h', 120)
                if klines and len(klines) >= 15:
                    auto_config = state.config_manager.get_auto_bot_config()
                    maturity_check = check_coin_maturity_with_storage(
                        symbol, 
                        klines,
                        auto_config,
                        lambda s: state.rsi_manager.get_rsi_history(s)
                    )
                    
                    if not maturity_check['is_mature']:
                        return jsonify({
                            'success': False,
                            'error': f'Монета не прошла проверку зрелости: {maturity_check["reason"]}'
                        }), 400
            
            # Создаем бота через BotManager
            bot = state.bot_manager.create_bot(symbol, config)
            
            logger.info(f"[BOT_CREATE] Бот создан для {symbol}")
            
            return jsonify({
                'success': True,
                'bot': bot.to_dict(),
                'message': f'Бот для {symbol} создан успешно'
            })
            
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            logger.error(f"[API] Ошибка создания бота: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/start', methods=['POST'])
    def start_bot_endpoint():
        """Запустить бота"""
        try:
            data = request.get_json()
            if not data or not data.get('symbol'):
                return jsonify({'success': False, 'error': 'Symbol required'}), 400
            
            symbol = data['symbol']
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Запускаем бота
            if hasattr(bot, 'start'):
                bot.start()
            else:
                bot.update_status('running')
            
            logger.info(f"[BOT_START] Бот {symbol} запущен")
            
            return jsonify({
                'success': True,
                'bot': bot.to_dict(),
                'message': f'Бот {symbol} запущен'
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка запуска бота: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/stop', methods=['POST'])
    def stop_bot_endpoint():
        """Остановить бота"""
        try:
            data = request.get_json()
            if not data or not data.get('symbol'):
                return jsonify({'success': False, 'error': 'Symbol required'}), 400
            
            symbol = data['symbol']
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Останавливаем бота
            if hasattr(bot, 'stop'):
                bot.stop()
            else:
                bot.update_status('idle')
            
            logger.info(f"[BOT_STOP] Бот {symbol} остановлен")
            
            return jsonify({
                'success': True,
                'bot': bot.to_dict(),
                'message': f'Бот {symbol} остановлен'
            })
            
        except Exception as e:
            logger.error(f"[API] Ошибка остановки бота: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/pause', methods=['POST'])
    def pause_bot_endpoint():
        """Приостановить бота"""
        try:
            data = request.get_json()
            if not data or not data.get('symbol'):
                return jsonify({'success': False, 'error': 'Symbol required'}), 400
            
            symbol = data['symbol']
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Приостанавливаем
            if hasattr(bot, 'pause'):
                bot.pause()
            else:
                bot.update_status('paused')
            
            return jsonify({
                'success': True,
                'bot': bot.to_dict(),
                'message': f'Бот {symbol} приостановлен'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/delete', methods=['POST'])
    def delete_bot_endpoint():
        """Удалить бота"""
        try:
            data = request.get_json()
            if not data or not data.get('symbol'):
                return jsonify({'success': False, 'error': 'Symbol required'}), 400
            
            symbol = data['symbol']
            
            # Удаляем через BotManager
            deleted = state.bot_manager.delete_bot(symbol)
            
            if not deleted:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            logger.info(f"[BOT_DELETE] Бот {symbol} удален")
            
            return jsonify({
                'success': True,
                'message': f'Бот {symbol} удален'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/close-position', methods=['POST'])
    def close_position_endpoint():
        """Закрыть позицию бота"""
        try:
            data = request.get_json()
            if not data or not data.get('symbol'):
                return jsonify({'success': False, 'error': 'Symbol required'}), 400
            
            symbol = data['symbol']
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Закрываем позицию
            if hasattr(bot, 'close_position'):
                result = bot.close_position()
            else:
                result = state.exchange_manager.close_position(symbol)
            
            return jsonify({
                'success': True,
                'message': f'Позиция {symbol} закрыта'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/resume', methods=['POST'])
    def resume_bot():
        """Возобновить работу приостановленного бота"""
        try:
            data = request.get_json()
            symbol = data['symbol']
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Возобновляем бота
            if hasattr(bot, 'resume'):
                bot.resume()
            
            return jsonify({
                'success': True,
                'message': f'Бот {symbol} возобновлен'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/individual-settings/<symbol>', methods=['GET'])
    def get_individual_settings(symbol):
        """Получить индивидуальные настройки бота"""
        try:
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Возвращаем настройки бота
            settings = {
                'symbol': symbol,
                'stop_loss': getattr(bot, 'stop_loss_percent', 15.0),
                'trailing_stop': getattr(bot, 'trailing_stop_percent', 300.0)
            }
            
            return jsonify({
                'success': True,
                'settings': settings
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/individual-settings/<symbol>', methods=['POST'])
    def update_individual_settings(symbol):
        """Обновить индивидуальные настройки бота"""
        try:
            data = request.get_json()
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Обновляем настройки
            if 'stop_loss' in data and hasattr(bot, 'stop_loss_percent'):
                bot.stop_loss_percent = float(data['stop_loss'])
            
            if 'trailing_stop' in data and hasattr(bot, 'trailing_stop_percent'):
                bot.trailing_stop_percent = float(data['trailing_stop'])
            
            return jsonify({
                'success': True,
                'message': f'Настройки бота {symbol} обновлены'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/individual-settings/<symbol>', methods=['DELETE'])
    def delete_individual_settings(symbol):
        """Удалить индивидуальные настройки (вернуть к дефолтным)"""
        try:
            bot = state.bot_manager.get_bot(symbol)
            
            if not bot:
                return jsonify({'success': False, 'error': f'Бот {symbol} не найден'}), 404
            
            # Возвращаем к дефолтным настройкам
            auto_config = state.config_manager.get_auto_bot_config()
            if hasattr(bot, 'stop_loss_percent'):
                bot.stop_loss_percent = auto_config.get('stop_loss_percent', 15.0)
            if hasattr(bot, 'trailing_stop_percent'):
                bot.trailing_stop_percent = auto_config.get('trailing_stop_percent', 300.0)
            
            return jsonify({
                'success': True,
                'message': f'Настройки бота {symbol} сброшены к дефолтным'
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

