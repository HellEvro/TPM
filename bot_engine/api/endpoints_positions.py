"""
API endpoints для работы с позициями (State Manager версия)
"""

from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)


def register_positions_endpoints(app, state):
    """
    Регистрирует endpoints для работы с позициями
    
    Args:
        app: Flask приложение
        state: BotSystemState instance
    """
    
    @app.route('/api/bots/account-info', methods=['GET'])
    def get_account_info():
        """Получает информацию о торговом счете"""
        try:
            # Получаем данные с биржи через ExchangeManager
            exchange = state.exchange_manager.get_exchange()
            if not exchange:
                return jsonify({
                    'success': False,
                    'error': 'Exchange not initialized'
                }), 500
            
            # Получаем данные с биржи
            account_info = exchange.get_unified_account_info()
            if not account_info.get("success"):
                account_info = {
                    'success': False,
                    'error': 'Failed to get account info'
                }
            
            # Добавляем информацию о ботах
            bots_list = state.bot_manager.list_bots()
            account_info["bots_count"] = len(bots_list)
            account_info["active_bots"] = state.bot_manager.get_active_bots_count()
            
            response = jsonify(account_info)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка получения информации о счете: {str(e)}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route('/api/bots/manual-positions/refresh', methods=['POST'])
    def refresh_manual_positions():
        """Обновить список монет с ручными позициями"""
        try:
            manual_positions = []
            exchange = state.exchange_manager.get_exchange()
            
            if exchange:
                exchange_positions = exchange.get_positions()
                if isinstance(exchange_positions, tuple):
                    positions_list = exchange_positions[0] if exchange_positions else []
                else:
                    positions_list = exchange_positions if exchange_positions else []
                
                for pos in positions_list:
                    if abs(float(pos.get('size', 0))) > 0:
                        symbol = pos.get('symbol', '')
                        clean_symbol = symbol.replace('USDT', '') if symbol else ''
                        if clean_symbol and clean_symbol not in manual_positions:
                            manual_positions.append(clean_symbol)
                
                logger.info(f"[MANUAL_POSITIONS] Обновлено {len(manual_positions)} монет")
                
            return jsonify({
                'success': True,
                'count': len(manual_positions),
                'positions': manual_positions
            })
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка обновления ручных позиций: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/bots/sync-positions', methods=['POST'])
    def sync_positions_manual():
        """Принудительная синхронизация позиций с биржей"""
        try:
            # Синхронизируем через воркер
            from bot_engine.workers.state_aware_worker import sync_positions_with_exchange
            result = sync_positions_with_exchange(state)
            
            return jsonify({
                'success': True,
                'message': 'Синхронизация позиций выполнена',
                'synced': True
            })
                
        except Exception as e:
            logger.error(f"[MANUAL_SYNC] Ошибка синхронизации: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/bots/active-detailed', methods=['GET'])
    def get_active_bots_detailed():
        """Получает детальную информацию о активных ботах"""
        try:
            all_bots = state.bot_manager.list_bots()
            active_bots = []
            
            for bot in all_bots:
                # Фильтруем только активных
                if hasattr(bot, 'status') and bot.status not in ['idle', 'paused']:
                    bot_dict = bot.to_dict()
                    
                    # Получаем текущую цену
                    rsi_data = state.rsi_manager.get_coin(bot.symbol)
                    if rsi_data:
                        bot_dict['current_price'] = rsi_data.get('price')
                    
                    active_bots.append(bot_dict)
            
            return jsonify({
                'success': True,
                'bots': active_bots,
                'total': len(active_bots)
            })
                
        except Exception as e:
            logger.error(f"[API] Ошибка получения детальной информации: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    logger.info("[API] Positions endpoints registered")

