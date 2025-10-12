"""
NewTradingBot - торговый бот (вынесен из bots.py).

Этот класс использует зависимости которые передаются при создании.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Импортируем фильтры из bot_engine
try:
    from bot_engine.filters import check_rsi_time_filter
except ImportError:
    # Fallback если модуль не загружен
    def check_rsi_time_filter(candles, rsi, signal):
        return {'allowed': True, 'reason': 'Filter not available'}


class NewTradingBot:
    """Новый торговый бот согласно требованиям"""
    
    def __init__(self, symbol, config=None, exchange=None, 
                 get_config_func=None, get_rsi_data_func=None, BOT_STATUS=None):
        """
        Инициализация бота.
        
        Args:
            symbol: Символ монеты
            config: Конфигурация бота
            exchange: Объект биржи
            get_config_func: Функция для получения auto_bot_config
            get_rsi_data_func: Функция для получения RSI данных
            BOT_STATUS: Словарь статусов
        """
        self.symbol = symbol
        self.config = config or {}
        self.exchange = exchange
        
        # Функции для доступа к данным (вместо глобальных переменных)
        self.get_config = get_config_func or (lambda: {})
        self.get_rsi_data = get_rsi_data_func or (lambda s: None)
        self.BOT_STATUS = BOT_STATUS or {
            'IDLE': 'idle',
            'RUNNING': 'running',
            'IN_POSITION_LONG': 'in_position_long',
            'IN_POSITION_SHORT': 'in_position_short'
        }
        
        logger.info(f"[NEW_BOT_{symbol}] Инициализация нового торгового бота")
        
        # Параметры сделки из конфига
        self.volume_mode = self.config.get('volume_mode', 'usdt')
        self.volume_value = self.config.get('volume_value', 10.0)
        
        # Состояние бота
        self.status = self.config.get('status', self.BOT_STATUS['IDLE'])
        self.entry_price = self.config.get('entry_price', None)
        self.position_side = self.config.get('position_side', None)
        self.unrealized_pnl = self.config.get('unrealized_pnl', 0.0)
        self.created_at = self.config.get('created_at', datetime.now().isoformat())
        self.last_signal_time = self.config.get('last_signal_time', None)
        
        # Защитные механизмы
        self.max_profit_achieved = self.config.get('max_profit_achieved', 0.0)
        self.trailing_stop_price = self.config.get('trailing_stop_price', None)
        self.break_even_activated = bool(self.config.get('break_even_activated', False))
        
        # Время входа в позицию
        position_start_str = self.config.get('position_start_time', None)
        if position_start_str:
            try:
                self.position_start_time = datetime.fromisoformat(position_start_str)
            except:
                self.position_start_time = None
        else:
            self.position_start_time = None
        
        # Отслеживание позиций
        self.order_id = self.config.get('order_id', None)
        self.entry_timestamp = self.config.get('entry_timestamp', None)
        self.opened_by_autobot = self.config.get('opened_by_autobot', False)
        
        logger.info(f"[NEW_BOT_{symbol}] Бот инициализирован (статус: {self.status})")
    
    def update_status(self, new_status, entry_price=None, position_side=None):
        """Обновляет статус бота"""
        old_status = self.status
        self.status = new_status
        
        if entry_price is not None:
            self.entry_price = entry_price
        if position_side is not None:
            self.position_side = position_side
            
        # Инициализируем защитные механизмы при входе в позицию
        if new_status in [self.BOT_STATUS['IN_POSITION_LONG'], self.BOT_STATUS['IN_POSITION_SHORT']]:
            self.position_start_time = datetime.now()
            self.max_profit_achieved = 0.0
            self.trailing_stop_price = None
            self.break_even_activated = False
            
        logger.info(f"[NEW_BOT_{self.symbol}] Статус изменен: {old_status} -> {new_status}")
    
    def should_open_long(self, rsi, trend, candles):
        """Проверяет, нужно ли открывать LONG позицию"""
        try:
            # Получаем настройки через функцию
            auto_config = self.get_config()
            rsi_long_threshold = auto_config.get('rsi_long_threshold', 29)
            avoid_down_trend = auto_config.get('avoid_down_trend', True)
            rsi_time_filter_enabled = auto_config.get('rsi_time_filter_enabled', True)
            
            # 1. Проверка RSI
            if rsi > rsi_long_threshold:
                return False
            
            # 2. Проверка тренда
            if avoid_down_trend and trend == 'DOWN':
                return False
            
            # 3. RSI временной фильтр
            if rsi_time_filter_enabled:
                time_filter_result = check_rsi_time_filter(candles, rsi, 'ENTER_LONG')
                if not time_filter_result['allowed']:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка проверки LONG: {e}")
            return False
    
    def should_open_short(self, rsi, trend, candles):
        """Проверяет, нужно ли открывать SHORT позицию"""
        try:
            auto_config = self.get_config()
            rsi_short_threshold = auto_config.get('rsi_short_threshold', 71)
            avoid_up_trend = auto_config.get('avoid_up_trend', True)
            rsi_time_filter_enabled = auto_config.get('rsi_time_filter_enabled', True)
            
            # 1. Проверка RSI
            if rsi < rsi_short_threshold:
                return False
            
            # 2. Проверка тренда
            if avoid_up_trend and trend == 'UP':
                return False
            
            # 3. RSI временной фильтр
            if rsi_time_filter_enabled:
                time_filter_result = check_rsi_time_filter(candles, rsi, 'ENTER_SHORT')
                if not time_filter_result['allowed']:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка проверки SHORT: {e}")
            return False
    
    def should_close_long(self, rsi, current_price):
        """Проверяет, нужно ли закрывать LONG позицию"""
        try:
            auto_config = self.get_config()
            rsi_long_exit = auto_config.get('rsi_long_exit', 65)
            
            if rsi >= rsi_long_exit:
                return True, 'RSI_EXIT'
            
            return False, None
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка проверки закрытия LONG: {e}")
            return False, None
    
    def should_close_short(self, rsi, current_price):
        """Проверяет, нужно ли закрывать SHORT позицию"""
        try:
            auto_config = self.get_config()
            rsi_short_exit = auto_config.get('rsi_short_exit', 35)
            
            if rsi <= rsi_short_exit:
                return True, 'RSI_EXIT'
            
            return False, None
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка проверки закрытия SHORT: {e}")
            return False, None
    
    def update(self, force_analysis=False, external_signal=None, external_trend=None):
        """Основной метод обновления бота"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not initialized'}
            
            # Получаем RSI данные через функцию
            coin_data = self.get_rsi_data(self.symbol)
            if not coin_data:
                return {'success': False, 'error': 'No RSI data'}
            
            current_rsi = coin_data.get('rsi6h')
            current_price = coin_data.get('price')
            current_trend = external_trend or coin_data.get('trend6h', 'NEUTRAL')
            
            if current_rsi is None or current_price is None:
                return {'success': False, 'error': 'Incomplete RSI data'}
            
            # Получаем свечи
            chart_response = self.exchange.get_chart_data(self.symbol, '6h', '30d')
            if not chart_response or not chart_response.get('success'):
                return {'success': False, 'error': 'No candles data'}
            
            candles = chart_response.get('data', {}).get('candles', [])
            if not candles:
                return {'success': False, 'error': 'Empty candles'}
            
            # Обрабатываем в зависимости от статуса
            if self.status == self.BOT_STATUS['IDLE']:
                return self._handle_idle_state(current_rsi, current_trend, candles, current_price)
            elif self.status in [self.BOT_STATUS['IN_POSITION_LONG'], self.BOT_STATUS['IN_POSITION_SHORT']]:
                return self._handle_position_state(current_rsi, current_trend, candles, current_price)
            else:
                return {'success': True, 'status': self.status}
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка обновления: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_idle_state(self, rsi, trend, candles, price):
        """Обрабатывает состояние IDLE"""
        try:
            auto_config = self.get_config()
            if not auto_config.get('enabled', False):
                return {'success': True, 'status': self.status}
            
            # Проверяем LONG
            if self.should_open_long(rsi, trend, candles):
                if self._open_position_on_exchange('LONG', price):
                    self.update_status(self.BOT_STATUS['IN_POSITION_LONG'], price, 'LONG')
                    return {'success': True, 'action': 'OPEN_LONG'}
                return {'success': False, 'error': 'Failed to open LONG'}
            
            # Проверяем SHORT
            if self.should_open_short(rsi, trend, candles):
                if self._open_position_on_exchange('SHORT', price):
                    self.update_status(self.BOT_STATUS['IN_POSITION_SHORT'], price, 'SHORT')
                    return {'success': True, 'action': 'OPEN_SHORT'}
                return {'success': False, 'error': 'Failed to open SHORT'}
            
            return {'success': True, 'status': self.status}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_position_state(self, rsi, trend, candles, price):
        """Обрабатывает состояние в позиции"""
        try:
            # Проверяем защитные механизмы
            protection_result = self.check_protection_mechanisms(price)
            if protection_result['should_close']:
                self._close_position_on_exchange(protection_result['reason'])
                return {'success': True, 'action': f"CLOSE_{self.position_side}"}
            
            # Проверяем условия закрытия по RSI
            if self.position_side == 'LONG':
                should_close, reason = self.should_close_long(rsi, price)
                if should_close:
                    self._close_position_on_exchange(reason)
                    return {'success': True, 'action': 'CLOSE_LONG'}
            
            elif self.position_side == 'SHORT':
                should_close, reason = self.should_close_short(rsi, price)
                if should_close:
                    self._close_position_on_exchange(reason)
                    return {'success': True, 'action': 'CLOSE_SHORT'}
            
            # Обновляем защитные механизмы
            self._update_protection_mechanisms(price)
            
            return {'success': True, 'status': self.status}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def check_protection_mechanisms(self, current_price):
        """Проверяет защитные механизмы (stop-loss, trailing-stop, break-even)"""
        try:
            if not self.entry_price or not current_price:
                return {'should_close': False, 'reason': None}
            
            auto_config = self.get_config()
            stop_loss_percent = auto_config.get('stop_loss_percent', 15.0)
            trailing_activation_percent = auto_config.get('trailing_activation_percent', 300.0)
            trailing_distance_percent = auto_config.get('trailing_distance_percent', 150.0)
            break_even_trigger_percent = auto_config.get('break_even_trigger_percent', 100.0)
            
            # Вычисляем прибыль
            if self.position_side == 'LONG':
                profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
            else:
                profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100
            
            # 1. Стоп-лосс
            if profit_percent <= -stop_loss_percent:
                return {'should_close': True, 'reason': f'STOP_LOSS_{profit_percent:.2f}%'}
            
            # 2. Максимальная прибыль
            if profit_percent > self.max_profit_achieved:
                self.max_profit_achieved = profit_percent
            
            # 3. Безубыточность
            if not self.break_even_activated and profit_percent >= break_even_trigger_percent:
                self.break_even_activated = True
            
            if self.break_even_activated and profit_percent <= 0:
                return {'should_close': True, 'reason': f'BREAK_EVEN_MAX_{self.max_profit_achieved:.2f}%'}
            
            # 4. Trailing stop
            if self.max_profit_achieved >= trailing_activation_percent:
                if self.position_side == 'LONG':
                    max_price = self.entry_price * (1 + self.max_profit_achieved / 100)
                    trailing_stop = max_price * (1 - trailing_distance_percent / 100)
                    if current_price <= trailing_stop:
                        return {'should_close': True, 'reason': f'TRAILING_STOP_MAX_{self.max_profit_achieved:.2f}%'}
                else:
                    min_price = self.entry_price * (1 - self.max_profit_achieved / 100)
                    trailing_stop = min_price * (1 + trailing_distance_percent / 100)
                    if current_price >= trailing_stop:
                        return {'should_close': True, 'reason': f'TRAILING_STOP_MAX_{self.max_profit_achieved:.2f}%'}
            
            return {'should_close': False, 'reason': None}
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка защитных механизмов: {e}")
            return {'should_close': False, 'reason': None}
    
    def _update_protection_mechanisms(self, current_price):
        """Обновляет защитные механизмы"""
        try:
            if not self.entry_price or not current_price:
                return
            
            if self.position_side == 'LONG':
                profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
            else:
                profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100
            
            if profit_percent > self.max_profit_achieved:
                self.max_profit_achieved = profit_percent
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка обновления защитных механизмов: {e}")
    
    def _open_position_on_exchange(self, side, price):
        """Открывает позицию на бирже"""
        try:
            if not self.exchange:
                return False
            
            order_result = self.exchange.place_market_order(
                symbol=self.symbol,
                side=side,
                qty=None,
                qty_in_usdt=self.volume_value
            )
            
            if order_result and order_result.get('success'):
                self.order_id = order_result.get('order_id')
                self.entry_timestamp = datetime.now().isoformat()
                logger.info(f"[NEW_BOT_{self.symbol}] Позиция {side} открыта")
                return True
            
            return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка открытия позиции: {e}")
            return False
    
    def _close_position_on_exchange(self, reason):
        """Закрывает позицию на бирже"""
        try:
            if not self.exchange:
                return False
            
            close_result = self.exchange.close_position(
                symbol=self.symbol,
                side=self.position_side
            )
            
            if close_result and close_result.get('success'):
                self.update_status(self.BOT_STATUS['IDLE'])
                return True
            
            return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] Ошибка закрытия позиции: {e}")
            return False
    
    def to_dict(self):
        """Преобразует бота в словарь для сохранения"""
        return {
            'symbol': self.symbol,
            'status': self.status,
            'entry_price': self.entry_price,
            'position_side': self.position_side,
            'unrealized_pnl': self.unrealized_pnl,
            'created_at': self.created_at,
            'last_signal_time': self.last_signal_time,
            'max_profit_achieved': self.max_profit_achieved,
            'trailing_stop_price': self.trailing_stop_price,
            'break_even_activated': self.break_even_activated,
            'position_start_time': self.position_start_time.isoformat() if self.position_start_time else None,
            'order_id': self.order_id,
            'entry_timestamp': self.entry_timestamp,
            'opened_by_autobot': self.opened_by_autobot,
            'config': self.config
        }

