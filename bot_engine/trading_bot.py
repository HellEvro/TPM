"""
Основной класс торгового бота с логикой RSI на 6H таймфрейме
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from .bot_config import (
    BotStatus, TrendDirection, VolumeMode, 
    DEFAULT_BOT_CONFIG, TIMEFRAME
)
from .indicators import SignalGenerator
from .scaling_calculator import calculate_scaling_for_bot


class TradingBot:
    """Торговый бот для одной монеты"""
    
    def __init__(self, symbol: str, exchange, config: dict = None):
        self.symbol = symbol
        self.exchange = exchange
        self.config = {**DEFAULT_BOT_CONFIG, **(config or {})}
        
        # Состояние бота
        self.status = self.config.get('status', BotStatus.IDLE)
        self.auto_managed = self.config.get('auto_managed', False)
        
        # Параметры сделки
        self.volume_mode = self.config.get('volume_mode', VolumeMode.FIXED_USDT)
        self.volume_value = self.config.get('volume_value', 10.0)
        self.max_loss_percent = self.config.get('max_loss_percent', 2.0)
        
        # Текущая позиция
        self.position = self.config.get('position')
        self.entry_price = self.config.get('entry_price')
        self.entry_time = self.config.get('entry_time')
        self.last_signal_time = self.config.get('last_signal_time')
        self.last_price = self.config.get('last_price')
        self.last_rsi = self.config.get('last_rsi')
        self.last_trend = self.config.get('last_trend')
        
        # Расширенные параметры позиции
        self.position_side = self.config.get('position_side')
        position_start = self.config.get('position_start_time')
        if position_start and hasattr(position_start, 'isoformat'):
            self.position_start_time = position_start
        elif isinstance(position_start, str):
            try:
                self.position_start_time = datetime.fromisoformat(position_start)
            except ValueError:
                self.position_start_time = position_start
        else:
            self.position_start_time = position_start
        
        self.position_size = self.config.get('position_size')
        self.position_size_coins = self.config.get('position_size_coins')
        self.unrealized_pnl = self.config.get('unrealized_pnl', 0.0)
        self.unrealized_pnl_usdt = self.config.get('unrealized_pnl_usdt', 0.0)
        self.realized_pnl = self.config.get('realized_pnl', 0.0)
        self.leverage = self.config.get('leverage', 1.0)
        self.margin_usdt = self.config.get('margin_usdt')
        self.max_profit_achieved = self.config.get('max_profit_achieved', 0.0)
        self.trailing_stop_price = self.config.get('trailing_stop_price')
        self.trailing_activation_profit = self.config.get('trailing_activation_profit', 0.0)
        self.trailing_activation_threshold = self.config.get('trailing_activation_threshold', 0.0)
        self.trailing_locked_profit = self.config.get('trailing_locked_profit', 0.0)
        self.trailing_active = bool(self.config.get('trailing_active', False))
        self.trailing_max_profit_usdt = float(self.config.get('trailing_max_profit_usdt', 0.0) or 0.0)
        self.trailing_step_usdt = float(self.config.get('trailing_step_usdt', 0.0) or 0.0)
        self.trailing_step_price = float(self.config.get('trailing_step_price', 0.0) or 0.0)
        self.trailing_steps = int(self.config.get('trailing_steps', 0) or 0)
        self.break_even_activated = self.config.get('break_even_activated', False)
        self.order_id = self.config.get('order_id')
        self.current_price = self.config.get('current_price')
        created = self.config.get('created_at')
        if created and hasattr(created, 'isoformat'):
            self.created_at = created
        elif isinstance(created, str):
            try:
                self.created_at = datetime.fromisoformat(created)
            except ValueError:
                self.created_at = created
        else:
            self.created_at = datetime.now()
        self.rsi_data = self.config.get('rsi_data', {})
        
        # Масштабирование (лесенка)
        self.scaling_enabled = self.config.get('scaling_enabled', False)
        self.scaling_levels = self.config.get('scaling_levels', [])
        self.scaling_current_level = self.config.get('scaling_current_level', 0)
        self.scaling_group_id = self.config.get('scaling_group_id', None)
        
        # Логирование
        self.logger = logging.getLogger(f'TradingBot.{symbol}')
        
        # Анализ
        try:
            self.signal_generator = SignalGenerator()
            self.logger.info(f"[TRADING_BOT] {symbol}: SignalGenerator создан успешно")
        except Exception as e:
            self.logger.error(f"[TRADING_BOT] {symbol}: Ошибка создания SignalGenerator: {e}")
            raise
        self.last_analysis = None
        self.last_bar_timestamp = None
        
        self.logger.info(f"Bot initialized for {symbol} with config: {self.config}")
    
    def to_dict(self) -> Dict:
        """Преобразует состояние бота в словарь для сохранения"""
        if hasattr(self.status, 'value'):
            raw_status = self.status.value
        else:
            raw_status = str(self.status) if self.status is not None else ''

        normalized_status = raw_status.lower()

        return {
            'symbol': self.symbol,
            'status': normalized_status,
            'auto_managed': self.auto_managed,
            'volume_mode': self.volume_mode.value if hasattr(self.volume_mode, 'value') else str(self.volume_mode),
            'volume_value': self.volume_value,
            'position': self.position,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time and hasattr(self.entry_time, 'isoformat') else self.entry_time,
            'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time and hasattr(self.last_signal_time, 'isoformat') else self.last_signal_time,
            'last_bar_timestamp': self.last_bar_timestamp,
            'position_side': self.position_side or (self.position.get('side') if self.position else None),
            'position_start_time': self.position_start_time.isoformat() if self.position_start_time and hasattr(self.position_start_time, 'isoformat') else self.position_start_time,
            'position_size': self.position_size,
            'position_size_coins': self.position_size_coins,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_usdt': self.unrealized_pnl_usdt,
            'realized_pnl': self.realized_pnl,
            'leverage': self.leverage,
            'margin_usdt': self.margin_usdt,
            'max_profit_achieved': self.max_profit_achieved,
            'trailing_stop_price': self.trailing_stop_price,
            'trailing_activation_profit': self.trailing_activation_profit,
            'trailing_activation_threshold': self.trailing_activation_threshold,
            'trailing_locked_profit': self.trailing_locked_profit,
            'trailing_active': self.trailing_active,
            'trailing_max_profit_usdt': self.trailing_max_profit_usdt,
            'trailing_step_usdt': self.trailing_step_usdt,
            'trailing_step_price': self.trailing_step_price,
            'trailing_steps': self.trailing_steps,
            'break_even_activated': self.break_even_activated,
            'order_id': self.order_id,
            'current_price': self.current_price,
            'last_price': self.last_price,
            'last_rsi': self.last_rsi,
            'last_trend': self.last_trend,
            'rsi_data': self.rsi_data,
            'created_at': self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            'scaling_enabled': self.scaling_enabled,
            'scaling_levels': self.scaling_levels,
            'scaling_current_level': self.scaling_current_level,
            'scaling_group_id': self.scaling_group_id
        }
    
    def update(self, force_analysis: bool = False, external_signal: str = None, external_trend: str = None) -> Dict:
        """
        Обновляет состояние бота и выполняет торговую логику
        
        Args:
            force_analysis: Принудительный анализ (игнорирует временные ограничения)
            external_signal: Внешний сигнал (ENTER_LONG, ENTER_SHORT, WAIT)
            external_trend: Внешний тренд (UP, DOWN, NEUTRAL)
            
        Returns:
            Словарь с результатами обновления
        """
        try:
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Начинаем update method...")
            self.logger.info(f"[TRADING_BOT] {self.symbol}: External signal: {external_signal}, trend: {external_trend}")
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: если статус указывает на позицию, но position = null, сбрасываем статус
            if self.status in [BotStatus.IN_POSITION_LONG, BotStatus.IN_POSITION_SHORT] and self.position is None:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Несоответствие статуса! Статус: {self.status}, но позиция: {self.position}. Сбрасываем статус.")
                self.status = BotStatus.IDLE
            
            # КРИТИЧЕСКАЯ СИНХРОНИЗАЦИЯ: проверяем реальные позиции на бирже
            try:
                exchange_positions = self.exchange.get_positions()
                if isinstance(exchange_positions, tuple):
                    positions_list = exchange_positions[0] if exchange_positions else []
                else:
                    positions_list = exchange_positions if exchange_positions else []
                
                # Ищем позицию по нашему символу
                real_position = None
                for pos in positions_list:
                    if pos.get('symbol') == self.symbol and abs(float(pos.get('size', 0))) > 0:
                        real_position = pos
                        break
                
                # Если на бирже есть позиция, но в боте её нет - синхронизируем
                if real_position and not self.position:
                    self.logger.warning(f"[TRADING_BOT] {self.symbol}: 🔄 Синхронизация: на бирже есть позиция {real_position}, но в боте нет!")
                    self.position = {
                        'side': 'LONG' if float(real_position.get('size', 0)) > 0 else 'SHORT',
                        'quantity': abs(float(real_position.get('size', 0))),
                        'entry_price': real_position.get('entry_price'),
                        'order_id': real_position.get('order_id', 'unknown')
                    }
                    self.entry_price = real_position.get('entry_price')
                    self.status = BotStatus.IN_POSITION_LONG if self.position['side'] == 'LONG' else BotStatus.IN_POSITION_SHORT
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Синхронизировано: {self.position}")
                
                # Если в боте есть позиция, но на бирже нет - очищаем
                elif self.position and not real_position:
                    self.logger.warning(f"[TRADING_BOT] {self.symbol}: 🔄 Синхронизация: в боте есть позиция {self.position}, но на бирже нет!")
                    self.position = None
                    self.entry_price = None
                    self.entry_time = None
                    self.status = BotStatus.IDLE
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Позиция очищена")
                    
            except Exception as sync_error:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: Ошибка синхронизации с биржей: {sync_error}")
            
            # Если есть внешний сигнал, используем его вместо генерации
            if external_signal:
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Используем внешний сигнал: {external_signal}")
                
                # КРИТИЧЕСКАЯ ПРОВЕРКА: если уже есть позиция, НЕ ОТКРЫВАЕМ новую!
                if self.position:
                    self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Уже есть позиция {self.position['side']} - ИГНОРИРУЕМ внешний сигнал {external_signal}")
                    analysis = {
                        'signal': 'WAIT',  # Игнорируем внешний сигнал
                        'trend': external_trend or 'NEUTRAL',
                        'rsi': 0,
                        'price': self._get_current_price() or 0
                    }
                else:
                    analysis = {
                        'signal': external_signal,
                        'trend': external_trend or 'NEUTRAL',
                        'rsi': 0,  # Заглушка, так как RSI не используется в торговой логике
                        'price': self._get_current_price() or 0
                    }
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Внешний анализ: {analysis}")
            else:
                # Получаем данные свечей
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Получаем данные свечей...")
                candles_data = self._get_candles_data()
                if not candles_data:
                    self.logger.warning(f"[TRADING_BOT] {self.symbol}: Не удалось получить данные свечей")
                    return {'success': False, 'error': 'failed_to_get_candles'}
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Получено {len(candles_data)} свечей")
                
                # Проверяем, нужно ли обновлять анализ
                current_bar_timestamp = candles_data[-1].get('timestamp')
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Проверяем необходимость обновления: force_analysis={force_analysis}, current_bar={current_bar_timestamp}, last_bar={self.last_bar_timestamp}")
                if not force_analysis and current_bar_timestamp == self.last_bar_timestamp:
                    # Бар не изменился, возвращаем последний анализ
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: Бар не изменился, возвращаем последний анализ")
                    return self._get_current_state()
                else:
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: Бар изменился или принудительный анализ, продолжаем...")
                
                # Выполняем анализ
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Генерируем сигналы...")
                analysis = self.signal_generator.generate_signals(candles_data)
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Анализ завершен: {analysis}")
                self.last_bar_timestamp = current_bar_timestamp
            
            self.last_analysis = analysis
            
            # Выполняем торговую логику
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Выполняем торговую логику...")
            if self.status != BotStatus.PAUSED:
                action_result = self._execute_trading_logic(analysis)
                if action_result:
                    self.logger.info(f"Action executed: {action_result}")
                else:
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: Нет действий для выполнения")
            else:
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Бот приостановлен")
            
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Возвращаем текущее состояние...")
            return self._get_current_state()
            
        except Exception as e:
            self.logger.error(f"Error in update: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_candles_data(self) -> List[Dict]:
        """Получает данные свечей с биржи"""
        try:
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Получаем данные свечей...")
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Exchange type: {type(self.exchange)}")
            # Получаем данные за последние 200 баров 6H для анализа
            chart_response = self.exchange.get_chart_data(
                symbol=self.symbol,
                timeframe=TIMEFRAME,
                period='1w'  # Используем period вместо limit
            )
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Chart response type: {type(chart_response)}")
            
            # Проверяем успешность ответа и извлекаем свечи
            if isinstance(chart_response, dict) and chart_response.get('success'):
                candles = chart_response.get('data', {}).get('candles', [])
                
                # Конвертируем в нужный формат с timestamp
                # (порядок уже исправлен в exchange классе)
                formatted_candles = []
                for candle in candles:
                    formatted_candle = {
                        'timestamp': candle.get('time'),
                        'open': float(candle.get('open', 0)),
                        'high': float(candle.get('high', 0)),
                        'low': float(candle.get('low', 0)),
                        'close': float(candle.get('close', 0)),
                        'volume': float(candle.get('volume', 0))
                    }
                    formatted_candles.append(formatted_candle)
                
                # Логируем для проверки
                if formatted_candles:
                    self.logger.debug(f"Got {len(formatted_candles)} candles for {self.symbol}")
                    self.logger.debug(f"First: {formatted_candles[0]['timestamp']}, Last: {formatted_candles[-1]['timestamp']}")
                
                return formatted_candles
            else:
                self.logger.error(f"Failed to get chart data: {chart_response}")
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to get candles data: {str(e)}")
            return []
    
    def _execute_trading_logic(self, analysis: Dict) -> Optional[Dict]:
        """
        Выполняет торговую логику на основе анализа
        
        Args:
            analysis: Результат анализа сигналов
            
        Returns:
            Результат выполненного действия или None
        """
        signal = analysis.get('signal')
        trend = analysis.get('trend')
        
        # Проверяем изменение тренда для принудительного выхода
        if self._should_force_exit(trend):
            return self._force_exit_position()
        
        # Выполняем действия в зависимости от текущего статуса
        if self.status in [BotStatus.IDLE, 'running']:
            return self._handle_idle_state(signal, trend)
        
        
        elif self.status in [BotStatus.IN_POSITION_LONG, BotStatus.IN_POSITION_SHORT]:
            # Проверяем, есть ли реальная позиция
            if not self.position:
                # Если статус IN_POSITION, но позиции нет - это ошибка синхронизации
                # Возвращаемся в IDLE и пытаемся открыть позицию заново
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: Статус {self.status} но позиции нет! Возвращаемся в IDLE")
                self.status = BotStatus.IDLE
                return self._handle_idle_state(signal, trend)
            else:
                return self._handle_position_state(signal, trend)
        
        return None
    
    def _should_force_exit(self, current_trend: str) -> bool:
        """Проверяет, нужно ли принудительно закрыть позицию при смене тренда"""
        if not self.position:
            return False
        
        position_type = self.position.get('side')
        
        # Принудительный выход при смене тренда на противоположный
        if position_type == 'LONG' and current_trend == 'DOWN':
            return True
        elif position_type == 'SHORT' and current_trend == 'UP':
            return True
        
        return False
    
    def _handle_idle_state(self, signal: str, trend: str) -> Optional[Dict]:
        """Обрабатывает состояние IDLE - СРАЗУ открывает сделки!"""
        self.logger.info(f"[TRADING_BOT] {self.symbol}: _handle_idle_state: signal={signal}, trend={trend}")
        
        # Проверяем, есть ли уже позиция в боте
        if self.position:
            self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Уже есть позиция {self.position['side']} - пропускаем вход")
            return {'action': 'position_exists', 'side': self.position['side'], 'price': self.position.get('entry_price')}
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем реальные позиции на бирже!
        try:
            exchange_positions = self.exchange.get_positions()
            if isinstance(exchange_positions, tuple):
                positions_list = exchange_positions[0] if exchange_positions else []
            else:
                positions_list = exchange_positions if exchange_positions else []
            
            # Проверяем, есть ли уже позиция по этому символу на бирже
            for pos in positions_list:
                if pos.get('symbol') == self.symbol and abs(float(pos.get('size', 0))) > 0:
                    existing_side = pos.get('side', 'UNKNOWN')
                    position_size = pos.get('size', 0)
                    
                    self.logger.warning(f"[TRADING_BOT] {self.symbol}: 🚫 НА БИРЖЕ УЖЕ ЕСТЬ ПОЗИЦИЯ {existing_side} размер {position_size}!")
                    self.logger.warning(f"[TRADING_BOT] {self.symbol}: ❌ БЛОКИРУЕМ ОТКРЫТИЕ НОВОЙ ПОЗИЦИИ - ЗАЩИТА ОТ ДУБЛИРОВАНИЯ!")
                    
                    return {
                        'action': 'blocked_exchange_position', 
                        'side': existing_side, 
                        'size': position_size,
                        'message': f'На бирже уже есть позиция {existing_side} размер {position_size}'
                    }
            
            self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ На бирже нет позиций - можно открывать сделку")
            
        except Exception as check_error:
            self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка проверки позиций на бирже: {check_error}")
            self.logger.error(f"[TRADING_BOT] {self.symbol}: 🚫 БЛОКИРУЕМ ОТКРЫТИЕ ПОЗИЦИИ ИЗ-ЗА ОШИБКИ ПРОВЕРКИ!")
            return {
                'action': 'blocked_check_error', 
                'error': str(check_error),
                'message': 'Ошибка проверки позиций на бирже'
            }
        
        # ПРОВЕРКА RSI ВРЕМЕННОГО ФИЛЬТРА
        try:
            # Импортируем функцию проверки временного фильтра
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from bots import check_rsi_time_filter
            
            # Получаем свечи для анализа временного фильтра
            candles = self.exchange.get_candles(self.symbol, '6h', 100)
            if candles and len(candles) > 0:
                # Получаем текущий RSI из данных монеты
                current_rsi = getattr(self, 'current_rsi', None)
                if current_rsi is None:
                    # Если RSI не сохранен в боте, получаем из API
                    try:
                        rsi_data = self.exchange.get_rsi_data(self.symbol, '6h', 14)
                        current_rsi = rsi_data.get('rsi', 50) if rsi_data else 50
                    except:
                        current_rsi = 50
                
                # Проверяем временной фильтр
                time_filter_result = check_rsi_time_filter(candles, current_rsi, signal)
                
                if not time_filter_result['allowed']:
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: ⏰ Временной фильтр блокирует вход: {time_filter_result['reason']}")
                    return {
                        'action': 'blocked_time_filter',
                        'reason': time_filter_result['reason'],
                        'last_extreme_candles_ago': time_filter_result.get('last_extreme_candles_ago')
                    }
                else:
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Временной фильтр разрешает вход: {time_filter_result['reason']}")
            else:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Не удалось получить свечи для проверки временного фильтра")
        except Exception as e:
            self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка проверки временного фильтра: {e}")
            # В случае ошибки разрешаем сделку (безопасность)
        
        # КРИТИЧЕСКИ ВАЖНО: Если автобот выключен - НЕ ОТКРЫВАЕМ новые позиции!
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from bots import bots_data, bots_data_lock
            
            with bots_data_lock:
                auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            
            if not auto_bot_enabled:
                self.logger.info(f"[TRADING_BOT] {self.symbol}: ⏹️ Auto Bot выключен - НЕ открываем новую позицию из IDLE состояния")
                return {'action': 'blocked_autobot_disabled', 'reason': 'autobot_off'}
        except Exception as e:
            self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка проверки автобота: {e}")
            # В случае ошибки блокируем для безопасности
            return {'action': 'blocked_check_error', 'reason': 'autobot_check_failed'}
        
        # ПРЯМАЯ ЛОГИКА: Сразу открываем сделки без промежуточных состояний
        if signal == 'ENTER_LONG':
            self.logger.info(f"[TRADING_BOT] {self.symbol}: 🚀 СРАЗУ открываем LONG позицию!")
            return self._enter_position('LONG')
        
        elif signal == 'ENTER_SHORT':
            self.logger.info(f"[TRADING_BOT] {self.symbol}: 🚀 СРАЗУ открываем SHORT позицию!")
            return self._enter_position('SHORT')
        
        self.logger.info(f"[TRADING_BOT] {self.symbol}: Нет сигналов для входа: signal={signal}, trend={trend}")
        return None
    
    
    def _handle_position_state(self, signal: str, trend: str) -> Optional[Dict]:
        """Обрабатывает состояния IN_POSITION_LONG/SHORT"""
        # КРИТИЧЕСКИ ВАЖНО: Если автобот выключен - НЕ ОТКРЫВАЕМ новые позиции!
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from bots import bots_data, bots_data_lock
            
            with bots_data_lock:
                auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            
            if not auto_bot_enabled:
                # Если автобот выключен - только управляем существующими позициями (стопы, трейлинг)
                # НЕ открываем новые позиции
                if signal in ['ENTER_LONG', 'ENTER_SHORT']:
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: ⏹️ Auto Bot выключен - НЕ открываем новые позиции из POSITION состояния")
                    return {'action': 'blocked_autobot_disabled', 'reason': 'autobot_off', 'status': self.status}
        except Exception as e:
            self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка проверки автобота: {e}")
        
        position_type = self.position.get('side') if self.position else None
        
        if (self.status == BotStatus.IN_POSITION_LONG and 
            (signal == 'EXIT_LONG' or position_type == 'LONG')):
            return self._exit_position()
        
        elif (self.status == BotStatus.IN_POSITION_SHORT and 
              (signal == 'EXIT_SHORT' or position_type == 'SHORT')):
            return self._exit_position()
        
        return None
    
    def _enter_position(self, side: str) -> Dict:
        """Входит в позицию"""
        try:
            # КРИТИЧЕСКАЯ ПРОВЕРКА: не открываем новую позицию, если уже есть открытая
            if self.position is not None:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Позиция уже открыта! Текущая позиция: {self.position}")
                return {'success': False, 'error': 'position_already_exists', 'message': 'Позиция уже открыта'}
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: не открываем позицию, если статус бота указывает на позицию
            if self.status in [BotStatus.IN_POSITION_LONG, BotStatus.IN_POSITION_SHORT]:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Бот уже в позиции! Статус: {self.status}")
                return {'success': False, 'error': 'bot_already_in_position', 'message': f'Бот уже в позиции (статус: {self.status})'}
            
            # КРИТИЧЕСКАЯ ПРОВЕРКА: проверяем реальные позиции на бирже ПЕРЕД открытием!
            try:
                exchange_positions = self.exchange.get_positions()
                if isinstance(exchange_positions, tuple):
                    positions_list = exchange_positions[0] if exchange_positions else []
                else:
                    positions_list = exchange_positions if exchange_positions else []
                
                # Проверяем, есть ли уже позиция по этому символу на бирже
                for pos in positions_list:
                    if pos.get('symbol') == self.symbol and abs(float(pos.get('size', 0))) > 0:
                        existing_side = pos.get('side', 'UNKNOWN')
                        position_size = pos.get('size', 0)
                        
                        self.logger.error(f"[TRADING_BOT] {self.symbol}: 🚫 КРИТИЧЕСКАЯ ОШИБКА! НА БИРЖЕ УЖЕ ЕСТЬ ПОЗИЦИЯ {existing_side} размер {position_size}!")
                        self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ НЕ МОЖЕМ ОТКРЫТЬ ПОЗИЦИЮ {side} - ЗАЩИТА ОТ ДУБЛИРОВАНИЯ!")
                        
                        return {
                            'success': False, 
                            'error': 'exchange_position_exists', 
                            'message': f'На бирже уже есть позиция {existing_side} размер {position_size}',
                            'existing_side': existing_side,
                            'existing_size': position_size
                        }
                
                self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Финальная проверка: на бирже нет позиций - открываем {side}")
                
            except Exception as exchange_check_error:
                self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка финальной проверки позиций на бирже: {exchange_check_error}")
                self.logger.error(f"[TRADING_BOT] {self.symbol}: 🚫 БЛОКИРУЕМ ОТКРЫТИЕ ПОЗИЦИИ ИЗ-ЗА ОШИБКИ ПРОВЕРКИ!")
                return {
                    'success': False, 
                    'error': 'exchange_check_failed', 
                    'message': f'Ошибка проверки позиций на бирже: {exchange_check_error}'
                }
            
            # Дополнительная проверка через биржу
            try:
                exchange_positions = self.exchange.get_positions()
                if isinstance(exchange_positions, tuple):
                    positions_list = exchange_positions[0] if exchange_positions else []
                else:
                    positions_list = exchange_positions if exchange_positions else []
                
                for pos in positions_list:
                    if pos.get('symbol') == self.symbol and abs(float(pos.get('size', 0))) > 0:
                        self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ На бирже уже есть позиция: {pos}")
                        return {'success': False, 'error': 'exchange_position_exists', 'message': 'На бирже уже есть позиция'}
            except Exception as e:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: Не удалось проверить позиции на бирже: {e}")
            
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Начинаем открытие {side} позиции...")
            
            # Адаптируем размер позиции с помощью AI (если доступно)
            try:
                from bot_engine.bot_config import AIConfig
                if AIConfig.AI_ENABLED and AIConfig.AI_RISK_MANAGEMENT_ENABLED:
                    from bot_engine.ai.ai_manager import get_ai_manager
                    ai_manager = get_ai_manager()
                    
                    if ai_manager and ai_manager.risk_manager and self.volume_mode == VolumeMode.FIXED_USDT:
                        # Получаем свечи и баланс
                        candles = self.exchange.get_chart_data(self.symbol, '6h', limit=50)
                        balance = self._get_available_balance() or 1000  # Fallback
                        
                        if candles and len(candles) >= 20:
                            dynamic_size = ai_manager.risk_manager.calculate_position_size(
                                self.symbol, candles, balance, signal_confidence=0.7
                            )
                            
                            # Обновляем volume_value для адаптивного размера
                            original_size = self.volume_value
                            self.volume_value = dynamic_size['size_usdt']
                            
                            self.logger.info(
                                f"[TRADING_BOT] {self.symbol}: 🤖 AI адаптировал размер: "
                                f"{original_size} USDT → {self.volume_value} USDT "
                                f"({dynamic_size['reason']})"
                            )
            except Exception as ai_error:
                self.logger.debug(f"[TRADING_BOT] {self.symbol}: AI адаптация размера недоступна: {ai_error}")
            
            # Рассчитываем размер позиции
            quantity = self._calculate_position_size()
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Рассчитанный размер позиции: {quantity}")
            if not quantity:
                self.logger.error(f"[TRADING_BOT] {self.symbol}: Не удалось рассчитать размер позиции")
                return {'success': False, 'error': 'failed_to_calculate_position_size'}
            
            # Размещаем ордер
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Размещаем {side} ордер на {quantity}...")
            order_result = self.exchange.place_order(
                symbol=self.symbol,
                side=side,
                quantity=quantity,
                order_type='market'
            )
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Результат ордера: {order_result}")
            
            if order_result.get('success'):
                # Обновляем состояние
                self.position = {
                    'side': side,
                    'quantity': quantity,
                    'entry_price': order_result.get('price'),
                    'order_id': order_result.get('order_id')
                }
                self.entry_price = order_result.get('price')
                self.entry_time = datetime.now()
                self.status = (BotStatus.IN_POSITION_LONG if side == 'LONG' 
                              else BotStatus.IN_POSITION_SHORT)
                
                # ✅ РЕГИСТРИРУЕМ ПОЗИЦИЮ В РЕЕСТРЕ
                try:
                    from bots_modules.imports_and_globals import register_bot_position
                    order_id = order_result.get('order_id')
                    if order_id:
                        register_bot_position(
                            symbol=self.symbol,
                            order_id=order_id,
                            side=side,
                            entry_price=order_result.get('price'),
                            quantity=quantity
                        )
                        self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Позиция зарегистрирована в реестре: order_id={order_id}")
                    else:
                        self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Не удалось зарегистрировать позицию - нет order_id")
                except Exception as registry_error:
                    self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка регистрации позиции в реестре: {registry_error}")
                    # Не блокируем торговлю из-за ошибки реестра
                
                # Устанавливаем стоп-лосс (с AI адаптацией если доступно)
                try:
                    # Пытаемся получить динамический SL от AI
                    sl_percent = self.max_loss_percent
                    ai_reason = None
                    
                    try:
                        from bot_engine.bot_config import AIConfig
                        if AIConfig.AI_ENABLED and AIConfig.AI_RISK_MANAGEMENT_ENABLED:
                            from bot_engine.ai.ai_manager import get_ai_manager
                            ai_manager = get_ai_manager()
                            
                            if ai_manager and ai_manager.risk_manager:
                                # Получаем свечи для анализа
                                candles = self.exchange.get_chart_data(self.symbol, '6h', limit=50)
                                
                                if candles and len(candles) >= 20:
                                    dynamic_sl = ai_manager.risk_manager.calculate_dynamic_sl(
                                        self.symbol, candles, side
                                    )
                                    
                                    sl_percent = dynamic_sl['sl_percent']
                                    ai_reason = dynamic_sl['reason']
                                    
                                    self.logger.info(
                                        f"[TRADING_BOT] {self.symbol}: 🤖 AI адаптировал SL: "
                                        f"{self.max_loss_percent}% → {sl_percent}% "
                                        f"({ai_reason})"
                                    )
                    except Exception as ai_error:
                        self.logger.debug(f"[TRADING_BOT] {self.symbol}: AI SL недоступен: {ai_error}")
                    
                    # Устанавливаем стоп-лосс (стандартный или адаптивный)
                    stop_result = self._place_stop_loss(side, self.entry_price, sl_percent)
                    if stop_result and stop_result.get('success'):
                        self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Стоп-лосс установлен на {sl_percent}%")
                    else:
                        self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Не удалось установить стоп-лосс")
                except Exception as stop_error:
                    self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка установки стоп-лосса: {stop_error}")
                
                self.logger.info(f"Entered {side} position: {quantity} at {self.entry_price}")
                return {
                    'success': True,
                    'action': 'position_entered',
                    'side': side,
                    'quantity': quantity,
                    'entry_price': self.entry_price
                }
            else:
                self.logger.error(f"Failed to enter position: {order_result}")
                return {'success': False, 'error': order_result.get('error', 'order_failed')}
                
        except Exception as e:
            self.logger.error(f"Error entering position: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _exit_position(self) -> Dict:
        """Выходит из позиции"""
        try:
            if not self.position:
                return {'success': False, 'error': 'no_position_to_exit'}
            
            # Размещаем ордер на закрытие
            side = 'SELL' if self.position['side'] == 'LONG' else 'BUY'
            order_result = self.exchange.place_order(
                symbol=self.symbol,
                side=side,
                quantity=self.position['quantity'],
                order_type='market'
            )
            
            if order_result.get('success'):
                exit_price = order_result.get('fill_price')
                
                # Рассчитываем PnL только если exit_price не None
                pnl = 0.0
                if exit_price is not None:
                    pnl = self._calculate_pnl(exit_price)
                
                self.logger.info(f"Exited position: PnL = {pnl}")
                
                # ✅ УДАЛЯЕМ ПОЗИЦИЮ ИЗ РЕЕСТРА
                try:
                    from bots_modules.imports_and_globals import unregister_bot_position
                    order_id = self.position.get('order_id') if self.position else None
                    if order_id:
                        unregister_bot_position(order_id)
                        self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Позиция удалена из реестра: order_id={order_id}")
                    else:
                        self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Не удалось удалить позицию из реестра - нет order_id")
                except Exception as registry_error:
                    self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка удаления позиции из реестра: {registry_error}")
                    # Не блокируем торговлю из-за ошибки реестра
                
                # Сбрасываем состояние
                self.position = None
                self.entry_price = None
                self.entry_time = None
                self.status = BotStatus.IDLE
                
                return {
                    'success': True,
                    'action': 'position_exited',
                    'exit_price': exit_price,
                    'pnl': pnl
                }
            else:
                self.logger.error(f"Failed to exit position: {order_result}")
                return {'success': False, 'error': order_result.get('error', 'order_failed')}
                
        except Exception as e:
            self.logger.error(f"Error exiting position: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _force_exit_position(self) -> Dict:
        """Принудительный выход из позиции при смене тренда"""
        self.logger.warning("Force exiting position due to trend change")
        return self._exit_position()
    
    def _calculate_position_size(self) -> Optional[float]:
        """Рассчитывает размер позиции"""
        try:
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Рассчитываем размер позиции...")
            self.logger.info(f"[TRADING_BOT] {self.symbol}: volume_mode={self.volume_mode}, volume_value={self.volume_value}")
            
            if self.volume_mode == VolumeMode.FIXED_QTY or self.volume_mode == 'qty':
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Режим FIXED_QTY, возвращаем {self.volume_value}")
                return self.volume_value
            
            elif self.volume_mode == VolumeMode.FIXED_USDT or self.volume_mode == 'usdt':
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Режим FIXED_USDT, получаем цену...")
                current_price = self._get_current_price()
                if current_price:
                    size = self.volume_value / current_price
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: Размер позиции: {self.volume_value} / {current_price} = {size}")
                    return size
                else:
                    self.logger.warning(f"[TRADING_BOT] {self.symbol}: Не удалось получить цену")
                    return None
            
            elif self.volume_mode == VolumeMode.PERCENT_BALANCE or self.volume_mode == 'percent':
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Режим PERCENT_BALANCE")
                balance = self._get_available_balance()
                if balance:
                    usdt_amount = balance * (self.volume_value / 100)
                    current_price = self._get_current_price()
                    if current_price:
                        return usdt_amount / current_price
            
            self.logger.warning(f"[TRADING_BOT] {self.symbol}: Неизвестный режим volume_mode: {self.volume_mode}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            return None
    
    def _calculate_scaling_levels(self) -> Dict:
        """Рассчитывает уровни лесенки для текущего бота"""
        try:
            if not self.scaling_enabled:
                return {
                    'success': False,
                    'error': 'Масштабирование отключено',
                    'levels': []
                }
            
            # Получаем текущую цену
            current_price = self._get_current_price()
            if not current_price:
                return {
                    'success': False,
                    'error': 'Не удалось получить текущую цену',
                    'levels': []
                }
            
            # Получаем конфигурацию масштабирования из автобота
            scaling_config = {
                'scaling_enabled': self.scaling_enabled,
                'scaling_mode': 'auto_double',  # Пока используем только автоматическое удвоение
                'auto_double_start_percent': 1.0,
                'auto_double_max_levels': 5,
                'scaling_min_usdt_per_trade': 5.0
            }
            
            # Рассчитываем лесенку
            result = calculate_scaling_for_bot(
                base_usdt=self.volume_value,
                price=current_price,
                scaling_config=scaling_config
            )
            
            if result['success']:
                self.scaling_levels = result['levels']
                self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Лесенка рассчитана: {len(result['levels'])} уровней")
                for i, level in enumerate(result['levels']):
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: Уровень {i+1}: {level['percent']}% = {level['usdt']:.2f} USDT")
            else:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка расчета лесенки: {result['error']}")
                if result.get('recommendation'):
                    rec = result['recommendation']
                    self.logger.info(f"[TRADING_BOT] {self.symbol}: 💡 Рекомендация: минимум {rec['min_base_usdt']:.2f} USDT для {rec['min_levels']} уровней")
            
            return result
            
        except Exception as e:
            self.logger.error(f"[TRADING_BOT] {self.symbol}: Ошибка расчета лесенки: {e}")
            return {
                'success': False,
                'error': str(e),
                'levels': []
            }
    
    def _get_current_price(self) -> Optional[float]:
        """Получает текущую цену"""
        try:
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Получаем цену...")
            ticker = self.exchange.get_ticker(self.symbol)
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Ticker response: {ticker}")
            if ticker:
                price = float(ticker.get('last', 0))
                self.logger.info(f"[TRADING_BOT] {self.symbol}: Цена получена: {price}")
                return price
            else:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: Ticker пустой")
                return None
        except Exception as e:
            self.logger.error(f"Error getting current price: {str(e)}")
            return None
    
    def _get_available_balance(self) -> Optional[float]:
        """Получает доступный баланс в USDT"""
        try:
            balance_data = self.exchange.get_wallet_balance()
            return float(balance_data.get('available_balance', 0))
        except Exception as e:
            self.logger.error(f"Error getting balance: {str(e)}")
            return None
    
    def _calculate_pnl(self, exit_price: float) -> float:
        """Рассчитывает PnL"""
        try:
            if not self.position or not self.entry_price or exit_price is None:
                return 0.0
            
            quantity = self.position.get('quantity', 0)
            entry_price = self.entry_price
            
            if self.position['side'] == 'LONG':
                return (exit_price - entry_price) * quantity
            else:  # SHORT
                return (entry_price - exit_price) * quantity
        except Exception as e:
            self.logger.error(f"Error calculating PnL: {e}")
            return 0.0
    
    def _get_current_state(self) -> Dict:
        """Возвращает текущее состояние бота"""
        current_price = self._get_current_price()
        current_pnl = 0.0
        
        if self.position and current_price:
            current_pnl = self._calculate_pnl(current_price)
        
        return {
            'success': True,
            'symbol': self.symbol,
            'status': self.status,
            'auto_managed': self.auto_managed,
            'trend': self.last_analysis.get('trend') if self.last_analysis else 'NEUTRAL',
            'rsi': self.last_analysis.get('rsi') if self.last_analysis else None,
            'price': current_price,
            'position': self.position,
            'pnl': current_pnl,
            'volume_mode': self.volume_mode,
            'volume_value': self.volume_value,
            'last_update': datetime.now().isoformat()
        }
    
    # Методы управления ботом
    def start(self, volume_mode: str = None, volume_value: float = None) -> Dict:
        """Запускает бота"""
        if volume_mode:
            self.volume_mode = volume_mode
        if volume_value:
            self.volume_value = volume_value
        
        if self.status == BotStatus.PAUSED:
            self.logger.info("Bot resumed from pause")
        else:
            self.status = BotStatus.IDLE
            self.logger.info("Bot started")
        
        return {'success': True, 'action': 'started'}
    
    def pause(self) -> Dict:
        """Приостанавливает бота"""
        self.status = BotStatus.PAUSED
        self.logger.info("Bot paused")
        return {'success': True, 'action': 'paused'}
    
    def stop(self) -> Dict:
        """Останавливает бота"""
        # Если есть открытая позиция, закрываем её
        if self.position:
            exit_result = self._exit_position()
            if not exit_result.get('success'):
                return exit_result
        
        self.status = BotStatus.IDLE
        self.position = None
        self.entry_price = None
        self.entry_time = None
        
        self.logger.info("Bot stopped")
        return {'success': True, 'action': 'stopped'}
    
    def force_close_position(self) -> Dict:
        """Принудительно закрывает позицию"""
        if not self.position:
            return {'success': False, 'error': 'no_position_to_close'}
        
        return self._exit_position()
    
    def get_state_dict(self) -> Dict:
        """Возвращает состояние для сохранения"""
        return {
            'symbol': self.symbol,
            'status': self.status,
            'auto_managed': self.auto_managed,
            'volume_mode': self.volume_mode,
            'volume_value': self.volume_value,
            'position': self.position,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'last_bar_timestamp': self.last_bar_timestamp
        }
    
    def restore_from_state(self, state_dict: Dict):
        """Восстанавливает состояние из словаря"""
        self.status = state_dict.get('status', BotStatus.IDLE)
        self.auto_managed = state_dict.get('auto_managed', False)
        self.volume_mode = state_dict.get('volume_mode', VolumeMode.FIXED_USDT)
        self.volume_value = state_dict.get('volume_value', 10.0)
        self.position = state_dict.get('position')
        self.entry_price = state_dict.get('entry_price')
        self.last_bar_timestamp = state_dict.get('last_bar_timestamp')
        
        entry_time_str = state_dict.get('entry_time')
        if entry_time_str:
            self.entry_time = datetime.fromisoformat(entry_time_str)
        
        self.logger.info(f"Bot state restored: {self.status}")
    
    def _place_stop_loss(self, side: str, entry_price: float, loss_percent: float) -> Dict:
        """Устанавливает стоп-лосс для позиции"""
        try:
            if not entry_price or entry_price <= 0:
                self.logger.error(f"[TRADING_BOT] {self.symbol}: Некорректная цена входа для стоп-лосса: {entry_price}")
                return {'success': False, 'error': 'invalid_entry_price'}
            
            # Рассчитываем цену стоп-лосса
            if side == 'LONG':
                # Для лонга: стоп-лосс ниже цены входа
                stop_price = entry_price * (1 - loss_percent / 100)
            else:  # SHORT
                # Для шорта: стоп-лосс выше цены входа
                stop_price = entry_price * (1 + loss_percent / 100)
            
            self.logger.info(f"[TRADING_BOT] {self.symbol}: Устанавливаем стоп-лосс: {side} @ {stop_price:.6f} (потеря: {loss_percent}%)")
            
            # Размещаем стоп-лосс ордер
            stop_result = self.exchange.place_stop_loss(
                symbol=self.symbol,
                side=side,
                quantity=self.position.get('quantity', 0) if self.position else 0,
                stop_price=stop_price,
                order_type='stop_market'
            )
            
            if stop_result and stop_result.get('success'):
                self.logger.info(f"[TRADING_BOT] {self.symbol}: ✅ Стоп-лосс установлен успешно")
                return {'success': True, 'stop_price': stop_price, 'order_id': stop_result.get('order_id')}
            else:
                self.logger.warning(f"[TRADING_BOT] {self.symbol}: ⚠️ Не удалось установить стоп-лосс: {stop_result}")
                return {'success': False, 'error': stop_result.get('error', 'stop_loss_failed')}
                
        except Exception as e:
            self.logger.error(f"[TRADING_BOT] {self.symbol}: ❌ Ошибка установки стоп-лосса: {e}")
            return {'success': False, 'error': str(e)}
