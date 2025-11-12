"""Класс торгового бота NewTradingBot

Основной класс для управления торговым ботом с поддержкой:
- Автоматического открытия/закрытия позиций
- Проверки фильтров (RSI time filter, trend, maturity)
- Защитных механизмов (trailing stop, break-even)
"""

import logging
from datetime import datetime
import time
import threading
import math
from typing import Optional

logger = logging.getLogger('BotsService')

# Импортируем глобальные переменные
try:
    from bots_modules.imports_and_globals import (
        bots_data_lock, bots_data, rsi_data_lock, coins_rsi_data,
        BOT_STATUS, get_exchange, system_initialized, get_auto_bot_config
    )
except ImportError:
    # Fallback если импорт не удался
    bots_data_lock = threading.Lock()
    bots_data = {}
    rsi_data_lock = threading.Lock()
    coins_rsi_data = {}
    BOT_STATUS = {
        'IDLE': 'idle',
        'RUNNING': 'running',
        'IN_POSITION_LONG': 'in_position_long',
        'IN_POSITION_SHORT': 'in_position_short',
        'WAITING': 'waiting',
        'STOPPED': 'stopped',
        'ERROR': 'error',
        'PAUSED': 'paused'
    }
    def get_exchange():
        return None
    system_initialized = False

# Импорт функций фильтров (будут доступны после импорта)
try:
    from bots_modules.filters import check_rsi_time_filter
except:
    def check_rsi_time_filter(*args, **kwargs):
        return {'allowed': True, 'reason': 'Filter not loaded'}

# Импорт AI Risk Manager для умного расчета TP/SL
try:
    from bot_engine.ai.risk_manager import DynamicRiskManager
    AI_RISK_MANAGER_AVAILABLE = True
except ImportError:
    DynamicRiskManager = None
    AI_RISK_MANAGER_AVAILABLE = False

class NewTradingBot:
    """Новый торговый бот согласно требованиям"""
    
    BREAK_EVEN_FEE_MULTIPLIER = 2.5
    
    def __init__(self, symbol, config=None, exchange=None):
        self.symbol = symbol
        self.config = config or {}
        self.exchange = exchange
        
        
        # Параметры сделки из конфига
        self.volume_mode = self.config.get('volume_mode', 'usdt')
        self.volume_value = self.config.get('volume_value', 10.0)
        
        # Состояние бота
        self.status = self.config.get('status', BOT_STATUS['IDLE'])
        self.entry_price = self.config.get('entry_price', None)
        self.position_side = self.config.get('position_side', None)
        self.position_size = self.config.get('position_size', None)  # Размер позиции в монетах
        self.position_size_coins = self.config.get('position_size_coins', None)
        self.unrealized_pnl = self.config.get('unrealized_pnl', 0.0)
        self.unrealized_pnl_usdt = self.config.get('unrealized_pnl_usdt', 0.0)
        self.realized_pnl = self.config.get('realized_pnl', 0.0)
        self.leverage = self.config.get('leverage', 1.0)
        self.margin_usdt = self.config.get('margin_usdt', None)
        self.trailing_activation_profit = self.config.get('trailing_activation_profit', 0.0)
        self.trailing_locked_profit = self.config.get('trailing_locked_profit', 0.0)
        self.created_at = self.config.get('created_at', datetime.now().isoformat())
        self.last_signal_time = self.config.get('last_signal_time', None)
        
        # Защитные механизмы
        self.max_profit_achieved = self.config.get('max_profit_achieved', 0.0)
        self.trailing_stop_price = self.config.get('trailing_stop_price', None)
        self.break_even_activated = bool(self.config.get('break_even_activated', False))
        break_even_stop = self.config.get('break_even_stop_price')
        try:
            self.break_even_stop_price = float(break_even_stop) if break_even_stop is not None else None
        except (TypeError, ValueError):
            self.break_even_stop_price = None
        self.trailing_activation_threshold = self.config.get('trailing_activation_threshold', 0.0)
        self.trailing_active = bool(self.config.get('trailing_active', False))
        self.trailing_max_profit_usdt = float(self.config.get('trailing_max_profit_usdt', 0.0) or 0.0)
        self.trailing_step_usdt = float(self.config.get('trailing_step_usdt', 0.0) or 0.0)
        self.trailing_step_price = float(self.config.get('trailing_step_price', 0.0) or 0.0)
        self.trailing_steps = int(self.config.get('trailing_steps', 0) or 0)
        self.trailing_take_profit_price = self.config.get('trailing_take_profit_price', None)
        
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
        
        # Дополнительные поля для сохранения
        self.stop_loss = self.config.get('stop_loss', None)
        self.take_profit = self.config.get('take_profit', None)
        self.current_price = self.config.get('current_price', None)
        
        # ✅ Тренд при входе в позицию (для определения уровня RSI выхода)
        self.entry_trend = self.config.get('entry_trend', None)
        
        
    def update_status(self, new_status, entry_price=None, position_side=None):
        """Обновляет статус бота"""
        old_status = self.status
        self.status = new_status
        
        if entry_price is not None:
            self.entry_price = entry_price
        if position_side is not None:
            self.position_side = position_side
            
        # Инициализируем защитные механизмы при входе в позицию
        if new_status in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
            self.position_start_time = datetime.now()
            self.max_profit_achieved = 0.0
            self.trailing_stop_price = None
            self.break_even_activated = False
            self.break_even_stop_price = None
            self.trailing_active = False
            self.trailing_activation_profit = 0.0
            self.trailing_activation_threshold = 0.0
            self.trailing_locked_profit = 0.0
            self.trailing_max_profit_usdt = 0.0
            self.trailing_step_usdt = 0.0
            self.trailing_step_price = 0.0
            self.trailing_steps = 0
            self.trailing_take_profit_price = None
            
    
    def should_open_long(self, rsi, trend, candles):
        """Проверяет, нужно ли открывать LONG позицию"""
        try:
            # ✅ ПРОВЕРКА ДЕЛИСТИНГА: Проверяем ДО всех остальных проверок
            from bots_modules.sync_and_cache import load_delisted_coins
            delisted_data = load_delisted_coins()
            delisted_coins = delisted_data.get('delisted_coins', {})
            
            if self.symbol in delisted_coins:
                delisting_info = delisted_coins[self.symbol]
                logger.warning(f"[NEW_BOT_{self.symbol}] 🚨 ДЕЛИСТИНГ! Не открываем LONG - {delisting_info.get('reason', 'Delisting detected')}")
                return False
            
            # Получаем настройки из конфига (ВАЖНО: сначала индивидуальные настройки бота, потом глобальные)
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                # Используем индивидуальные настройки из self.config если есть, иначе из auto_config
                rsi_long_threshold = self.config.get('rsi_long_threshold') or auto_config.get('rsi_long_threshold', 29)
                avoid_down_trend = self.config.get('avoid_down_trend') if 'avoid_down_trend' in self.config else auto_config.get('avoid_down_trend', True)
                rsi_time_filter_enabled = self.config.get('rsi_time_filter_enabled') if 'rsi_time_filter_enabled' in self.config else auto_config.get('rsi_time_filter_enabled', True)
                rsi_time_filter_candles = self.config.get('rsi_time_filter_candles') or auto_config.get('rsi_time_filter_candles', 8)
                rsi_time_filter_lower = self.config.get('rsi_time_filter_lower') or auto_config.get('rsi_time_filter_lower', 35)
                ai_enabled = auto_config.get('ai_enabled', False)  # Включение AI
            
            # 🤖 ПРОВЕРКА AI ПРЕДСКАЗАНИЯ (если включено)
            if ai_enabled:
                try:
                    from bot_engine.ai.ai_integration import should_open_position_with_ai
                    
                    # Получаем текущую цену
                    current_price = 0
                    if candles and len(candles) > 0:
                        current_price = candles[-1].get('close', 0)
                    
                    if current_price > 0:
                        ai_result = should_open_position_with_ai(
                            symbol=self.symbol,
                            direction='LONG',
                            rsi=rsi,
                            trend=trend,
                            price=current_price,
                            config=auto_config
                        )
                        
                        if ai_result.get('ai_used') and not ai_result.get('should_open', True):
                            logger.info(f"[NEW_BOT_{self.symbol}] 🤖 AI блокирует LONG: {ai_result.get('reason', 'AI prediction')}")
                            return False
                        elif ai_result.get('ai_used') and ai_result.get('should_open'):
                            logger.info(f"[NEW_BOT_{self.symbol}] 🤖 AI подтверждает LONG (уверенность: {ai_result.get('ai_confidence', 0):.2%})")
                            # Сохраняем ID решения AI для последующего отслеживания результатов
                            self.ai_decision_id = ai_result.get('ai_decision_id')
                except ImportError:
                    # AI модуль недоступен - продолжаем без него
                    pass
                except Exception as ai_error:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка проверки AI: {ai_error}")
            
            # 1. Проверка RSI
            if rsi > rsi_long_threshold:
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ RSI {rsi:.1f} > {rsi_long_threshold} - не открываем LONG")
                return False
            
            # 2. Проверка тренда
            if avoid_down_trend and trend == 'DOWN':
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ DOWN тренд - не открываем LONG")
                return False
            
            # 3. RSI временной фильтр
            if rsi_time_filter_enabled:
                time_filter_result = self.check_rsi_time_filter_for_long(candles, rsi, rsi_time_filter_candles, rsi_time_filter_lower)
                if not time_filter_result['allowed']:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ❌ RSI Time Filter блокирует LONG: {time_filter_result['reason']}")
                    return False
            
            logger.info(f"[NEW_BOT_{self.symbol}] ✅ Открываем LONG (RSI: {rsi:.1f})")
            return True
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки LONG: {e}")
            return False
    
    def should_open_short(self, rsi, trend, candles):
        """Проверяет, нужно ли открывать SHORT позицию"""
        try:
            # ✅ ПРОВЕРКА ДЕЛИСТИНГА: Проверяем ДО всех остальных проверок
            from bots_modules.sync_and_cache import load_delisted_coins
            delisted_data = load_delisted_coins()
            delisted_coins = delisted_data.get('delisted_coins', {})
            
            if self.symbol in delisted_coins:
                delisting_info = delisted_coins[self.symbol]
                logger.warning(f"[NEW_BOT_{self.symbol}] 🚨 ДЕЛИСТИНГ! Не открываем SHORT - {delisting_info.get('reason', 'Delisting detected')}")
                return False
            
            # Получаем настройки из конфига (ВАЖНО: сначала индивидуальные настройки бота, потом глобальные)
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                # Используем индивидуальные настройки из self.config если есть, иначе из auto_config
                rsi_short_threshold = self.config.get('rsi_short_threshold') or auto_config.get('rsi_short_threshold', 71)
                avoid_up_trend = self.config.get('avoid_up_trend') if 'avoid_up_trend' in self.config else auto_config.get('avoid_up_trend', True)
                rsi_time_filter_enabled = self.config.get('rsi_time_filter_enabled') if 'rsi_time_filter_enabled' in self.config else auto_config.get('rsi_time_filter_enabled', True)
                rsi_time_filter_candles = self.config.get('rsi_time_filter_candles') or auto_config.get('rsi_time_filter_candles', 8)
                rsi_time_filter_upper = auto_config.get('rsi_time_filter_upper', 65)
                ai_enabled = auto_config.get('ai_enabled', False)  # Включение AI
            
            # 🤖 ПРОВЕРКА AI ПРЕДСКАЗАНИЯ (если включено)
            if ai_enabled:
                try:
                    from bot_engine.ai.ai_integration import should_open_position_with_ai
                    
                    # Получаем текущую цену
                    current_price = 0
                    if candles and len(candles) > 0:
                        current_price = candles[-1].get('close', 0)
                    
                    if current_price > 0:
                        ai_result = should_open_position_with_ai(
                            symbol=self.symbol,
                            direction='SHORT',
                            rsi=rsi,
                            trend=trend,
                            price=current_price,
                            config=auto_config
                        )
                        
                        if ai_result.get('ai_used') and not ai_result.get('should_open', True):
                            logger.info(f"[NEW_BOT_{self.symbol}] 🤖 AI блокирует SHORT: {ai_result.get('reason', 'AI prediction')}")
                            return False
                        elif ai_result.get('ai_used') and ai_result.get('should_open'):
                            logger.info(f"[NEW_BOT_{self.symbol}] 🤖 AI подтверждает SHORT (уверенность: {ai_result.get('ai_confidence', 0):.2%})")
                            # Сохраняем ID решения AI для последующего отслеживания результатов
                            self.ai_decision_id = ai_result.get('ai_decision_id')
                except ImportError:
                    # AI модуль недоступен - продолжаем без него
                    pass
                except Exception as ai_error:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка проверки AI: {ai_error}")
            
            # 1. Проверка RSI
            if rsi < rsi_short_threshold:
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ RSI {rsi:.1f} < {rsi_short_threshold} - не открываем SHORT")
                return False
            
            # 2. Проверка тренда
            if avoid_up_trend and trend == 'UP':
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ UP тренд - не открываем SHORT")
                return False
            
            # 3. RSI временной фильтр
            if rsi_time_filter_enabled:
                time_filter_result = self.check_rsi_time_filter_for_short(candles, rsi, rsi_time_filter_candles, rsi_time_filter_upper)
                if not time_filter_result['allowed']:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ❌ RSI Time Filter блокирует SHORT: {time_filter_result['reason']}")
                    return False
            
            logger.info(f"[NEW_BOT_{self.symbol}] ✅ Открываем SHORT (RSI: {rsi:.1f})")
            return True
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки SHORT: {e}")
            return False
    
    def check_rsi_time_filter_for_long(self, candles, rsi, filter_candles, filter_lower):
        """Проверяет RSI временной фильтр для LONG (использует сложную логику)"""
        try:
            # Используем старую сложную логику временного фильтра
            return check_rsi_time_filter(candles, rsi, 'ENTER_LONG')
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка RSI Time Filter для LONG: {e}")
            return {'allowed': False, 'reason': f'Ошибка анализа: {str(e)}'}
    
    def check_rsi_time_filter_for_short(self, candles, rsi, filter_candles, filter_upper):
        """Проверяет RSI временной фильтр для SHORT (использует сложную логику)"""
        try:
            # Используем старую сложную логику временного фильтра
            return check_rsi_time_filter(candles, rsi, 'ENTER_SHORT')
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка RSI Time Filter для SHORT: {e}")
            return {'allowed': False, 'reason': f'Ошибка анализа: {str(e)}'}
    
    @staticmethod
    def check_should_close_by_rsi(symbol, rsi, position_side):
        """
        Статическая функция проверки закрытия позиции по RSI (без создания объекта бота)
        
        Args:
            symbol: Символ монеты
            rsi: Текущее значение RSI
            position_side: Сторона позиции ('LONG' или 'SHORT')
        
        Returns:
            tuple: (should_close: bool, reason: str или None)
        """
        try:
            if position_side not in ['LONG', 'SHORT']:
                logger.error(f"[RSI_CHECK_{symbol}] ❌ Неизвестная сторона позиции: {position_side}")
                return False, None
            
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                
                # ✅ Определяем уровень RSI выхода в зависимости от тренда при входе
                # Получаем entry_trend из данных бота (сохраняется при входе в позицию)
                bot_data = bots_data.get('bots', {}).get(symbol, {})
                entry_trend = bot_data.get('entry_trend', None)
                
                # ВАЖНО: Используем индивидуальные настройки из bot_data если есть, иначе из auto_config
                
                if position_side == 'LONG':
                    # Для LONG: проверяем был ли вход по UP тренду или против DOWN тренда
                    if entry_trend == 'UP':
                        # Вход по тренду - можем ждать большего движения
                        config_key = 'rsi_exit_long_with_trend'
                        threshold = bot_data.get(config_key) or auto_config.get(config_key, 65)
                        logger.debug(f"[RSI_CHECK_{symbol}] 📈 LONG по тренду → выход на RSI >= {threshold}")
                    else:
                        # Вход против тренда или тренд неизвестен - выходим раньше
                        config_key = 'rsi_exit_long_against_trend'
                        threshold = bot_data.get(config_key) or auto_config.get(config_key, 60)
                        logger.debug(f"[RSI_CHECK_{symbol}] 📉 LONG против тренда ({entry_trend}) → выход на RSI >= {threshold}")
                    
                    condition_func = lambda r, t: r >= t  # RSI >= порог для LONG
                    condition_str = ">="
                    
                else:  # SHORT
                    # Для SHORT: проверяем был ли вход по DOWN тренду или против UP тренда
                    if entry_trend == 'DOWN':
                        # Вход по тренду - можем ждать большего движения
                        config_key = 'rsi_exit_short_with_trend'
                        threshold = bot_data.get(config_key) or auto_config.get(config_key, 35)
                        logger.debug(f"[RSI_CHECK_{symbol}] 📉 SHORT по тренду → выход на RSI <= {threshold}")
                    else:
                        # Вход против тренда или тренд неизвестен - выходим раньше
                        config_key = 'rsi_exit_short_against_trend'
                        threshold = bot_data.get(config_key) or auto_config.get(config_key, 40)
                        logger.debug(f"[RSI_CHECK_{symbol}] 📈 SHORT против тренда ({entry_trend}) → выход на RSI <= {threshold}")
                    
                    condition_func = lambda r, t: r <= t  # RSI <= порог для SHORT
                    condition_str = "<="
            
            # КРИТИЧНО: Если значение не найдено - это ОШИБКА КОНФИГУРАЦИИ!
            if threshold is None:
                logger.error(f"[RSI_CHECK_{symbol}] ❌ КРИТИЧЕСКАЯ ОШИБКА: {config_key} не найден в конфигурации! Позиция НЕ будет закрыта!")
                logger.error(f"[RSI_CHECK_{symbol}] ❌ Проверьте конфигурацию auto_bot_config в bots_data!")
                return False, None
            
            condition_result = condition_func(rsi, threshold)
            
            if condition_result:
                return True, 'RSI_EXIT'
            
            return False, None
            
        except Exception as e:
            logger.error(f"[RSI_CHECK_{symbol}] ❌ Ошибка проверки закрытия {position_side}: {e}")
            return False, None
    
    def should_close_position(self, rsi, current_price, position_side=None):
        """
        Универсальная функция проверки закрытия позиции по RSI
        
        Args:
            rsi: Текущее значение RSI
            current_price: Текущая цена (не используется, но оставлен для совместимости)
            position_side: Сторона позиции ('LONG' или 'SHORT'). Если None, берется из self.position_side
        
        Returns:
            tuple: (should_close: bool, reason: str или None)
        """
        # Используем статический метод для проверки
        if position_side is None:
            position_side = self.position_side
        return self.check_should_close_by_rsi(self.symbol, rsi, position_side)
    
    # Обратная совместимость - оставляем старые методы для совместимости
    def should_close_long(self, rsi, current_price):
        """Проверяет, нужно ли закрывать LONG позицию (обертка для совместимости)"""
        return self.should_close_position(rsi, current_price, 'LONG')
    
    def should_close_short(self, rsi, current_price):
        """Проверяет, нужно ли закрывать SHORT позицию (обертка для совместимости)"""
        return self.should_close_position(rsi, current_price, 'SHORT')
    
    def update(self, force_analysis=False, external_signal=None, external_trend=None):
        """Основной метод обновления бота"""
        try:
            if not self.exchange:
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Биржа не инициализирована")
                return {'success': False, 'error': 'Exchange not initialized'}
            
            # Получаем текущие данные
            current_price = None
            current_rsi = None
            current_trend = external_trend
            
            # Получаем RSI данные
            try:
                # Проверяем, определен ли rsi_data_lock
                if 'rsi_data_lock' in globals():
                    with rsi_data_lock:
                        coin_data = coins_rsi_data['coins'].get(self.symbol)
                        if coin_data:
                            current_rsi = coin_data.get('rsi6h')
                            current_price = coin_data.get('price')
                            if not current_trend:
                                current_trend = coin_data.get('trend6h', 'NEUTRAL')
                else:
                    # Fallback если lock не определен
                    coin_data = coins_rsi_data['coins'].get(self.symbol)
                    if coin_data:
                        current_rsi = coin_data.get('rsi6h')
                        current_price = coin_data.get('price')
                        if not current_trend:
                            current_trend = coin_data.get('trend6h', 'NEUTRAL')
            except Exception as e:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка получения RSI данных: {e}")
                # Fallback если lock не определен
                coin_data = coins_rsi_data['coins'].get(self.symbol)
                if coin_data:
                    current_rsi = coin_data.get('rsi6h')
                    current_price = coin_data.get('price')
                    if not current_trend:
                        current_trend = coin_data.get('trend6h', 'NEUTRAL')
            
            if current_rsi is None or current_price is None:
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Нет RSI данных")
                return {'success': False, 'error': 'No RSI data'}
            
            # Получаем свечи для анализа
            chart_response = self.exchange.get_chart_data(self.symbol, '6h', '30d')
            if not chart_response or not chart_response.get('success'):
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Не удалось получить свечи")
                return {'success': False, 'error': 'No candles data'}
            
            candles = chart_response.get('data', {}).get('candles', [])
            if not candles:
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Нет свечей")
                return {'success': False, 'error': 'Empty candles'}
            
            # Обрабатываем в зависимости от статуса
            if self.status == BOT_STATUS['IDLE']:
                return self._handle_idle_state(current_rsi, current_trend, candles, current_price)
            elif self.status in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
                return self._handle_position_state(current_rsi, current_trend, candles, current_price)
            else:
                logger.debug(f"[NEW_BOT_{self.symbol}] ⏳ Статус {self.status} - ждем")
                return {'success': True, 'status': self.status}
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка обновления: {e}")
            return {'success': False, 'error': str(e)}

    def _get_market_price(self, fallback_price: float = None) -> float:
        """Возвращает актуальную цену из биржи (last/mark), если доступна"""
        if not self.exchange:
            return fallback_price
        try:
            ticker = self.exchange.get_ticker(self.symbol)
            if not ticker:
                return fallback_price

            candidates = (
                ticker.get('last'),
                ticker.get('markPrice'),
                ticker.get('price'),
                ticker.get('lastPrice'),
                ticker.get('mark'),
            )
            for candidate in candidates:
                if candidate is None:
                    continue
                try:
                    value = float(candidate)
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    return value
        except Exception as e:
            logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось получить цену с биржи: {e}")
        return fallback_price

    def _handle_idle_state(self, rsi, trend, candles, price):
        """Обрабатывает состояние IDLE (ожидание сигнала)"""
        try:
            # Проверяем, включен ли автобот
            with bots_data_lock:
                auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            
            if not auto_bot_enabled:
                logger.debug(f"[NEW_BOT_{self.symbol}] ⏹️ Автобот выключен - не открываем позицию")
                return {'success': True, 'status': self.status}
            
            # Проверяем возможность открытия LONG
            if self.should_open_long(rsi, trend, candles):
                logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Открываем LONG")
                if self._open_position_on_exchange('LONG', price):
                    self.update_status(BOT_STATUS['IN_POSITION_LONG'], price, 'LONG')
                    return {'success': True, 'action': 'OPEN_LONG', 'status': self.status}
            else:
                    logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось открыть LONG позицию")
                    return {'success': False, 'error': 'Failed to open LONG position'}
            
            # Проверяем возможность открытия SHORT
            if self.should_open_short(rsi, trend, candles):
                logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Открываем SHORT")
                if self._open_position_on_exchange('SHORT', price):
                    self.update_status(BOT_STATUS['IN_POSITION_SHORT'], price, 'SHORT')
                    return {'success': True, 'action': 'OPEN_SHORT', 'status': self.status}
                else:
                    logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось открыть SHORT позицию")
                    return {'success': False, 'error': 'Failed to open SHORT position'}
            
            logger.debug(f"[NEW_BOT_{self.symbol}] ⏳ Ждем сигнал (RSI: {rsi:.1f}, Trend: {trend})")
            return {'success': True, 'status': self.status}
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка в idle состоянии: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_position_state(self, rsi, trend, candles, price):
        """Обрабатывает состояние в позиции"""
        try:
            # Логируем начало проверки позиции
            logger.debug(f"[NEW_BOT_{self.symbol}] 📊 Проверка позиции {self.position_side}: RSI={rsi:.2f}, Цена={price}")
            
            if not self.entry_price:
                logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Нет цены входа - обновляем из биржи")
                self._sync_position_with_exchange()
            
            # Обновляем цену из биржи, чтобы trailing работал по реальному значению
            market_price = self._get_market_price(price)
            if market_price and market_price > 0:
                if price and abs(market_price - price) / max(price, 1e-9) >= 0.01:
                    logger.debug(
                        f"[NEW_BOT_{self.symbol}] 📉 Обновили цену по бирже: {price} → {market_price}"
                    )
                price = market_price

            self.current_price = price

            # 1. Проверяем защитные механизмы
            protection_result = self.check_protection_mechanisms(price)
            if protection_result['should_close']:
                logger.info(f"[NEW_BOT_{self.symbol}] 🛡️ Закрываем: {protection_result['reason']}")
                self._close_position_on_exchange(protection_result['reason'])
                return {'success': True, 'action': f"CLOSE_{self.position_side}", 'reason': protection_result['reason']}
            
            # 2. Проверяем условия закрытия по RSI (универсальная функция)
            if self.position_side in ['LONG', 'SHORT']:
                should_close, reason = self.should_close_position(rsi, price, self.position_side)
                if should_close:
                    logger.info(f"[NEW_BOT_{self.symbol}] 🔴 Закрываем {self.position_side} по RSI")
                    close_success = self._close_position_on_exchange(reason)
                    if close_success:
                        logger.info(f"[NEW_BOT_{self.symbol}] ✅ {self.position_side} закрыта")
                        return {'success': True, 'action': f'CLOSE_{self.position_side}', 'reason': reason}
                    else:
                        logger.error(f"[NEW_BOT_{self.symbol}] ❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось закрыть {self.position_side} позицию на бирже!")
                        return {'success': False, 'error': 'Failed to close position on exchange', 'action': f'CLOSE_{self.position_side}_FAILED', 'reason': reason}
                else:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ⏳ Продолжаем держать {self.position_side} позицию (RSI не достиг порога)")
            
            # 3. Обновляем защитные механизмы
            self._update_protection_mechanisms(price)
            
            logger.debug(f"[NEW_BOT_{self.symbol}] 📊 В позиции {self.position_side} (RSI: {rsi:.1f}, Цена: {price})")
            return {'success': True, 'status': self.status, 'position_side': self.position_side}
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка в позиции: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_trailing_by_margin(self, _profit_percent: float, current_price: float):
        """Рассчитывает параметры трейлинг-стопа на основе маржи сделки."""
        try:
            auto_config = get_auto_bot_config()
            trailing_distance_percent = float(auto_config.get('trailing_stop_distance', 0.0) or 0.0)
            trailing_activation_percent = float(auto_config.get('trailing_stop_activation', 0.0) or 0.0)
        except Exception:
            trailing_distance_percent = 0.0
            trailing_activation_percent = 0.0

        entry_price = float(self.entry_price or 0.0)
        current_price = float(current_price or 0.0)
        realized_abs = abs(float(self.realized_pnl or 0.0))
        leverage = float(self.leverage or 1.0)
        if leverage <= 0:
            leverage = 1.0

        quantity = self.position_size_coins
        if quantity is None:
            if self.position_size and entry_price > 0:
                quantity = abs(float(self.position_size) / entry_price)
            else:
                quantity = 0.0
        quantity = abs(float(quantity or 0.0))

        if entry_price <= 0 or quantity <= 0:
            return {
                'active': False,
                'stop_price': None,
                'activation_profit_usdt': 0.0,
                'activation_threshold_usdt': 0.0,
                'locked_profit_usdt': 0.0,
                'margin_usdt': 0.0,
                'profit_usdt': 0.0,
                'profit_usdt_max': float(self.trailing_max_profit_usdt or 0.0),
                'trailing_step_usdt': 0.0,
                'trailing_step_price': 0.0,
                'steps': 0
            }

        # Рассчитываем маржу входа
        position_value = entry_price * quantity
        margin_usdt = float(self.margin_usdt or 0.0)
        if margin_usdt <= 0:
            margin_usdt = position_value / leverage if leverage else position_value
            self.margin_usdt = margin_usdt

        # Текущая плавающая прибыль
        side = (self.position_side or '').upper()
        profit_usdt = 0.0
        if side == 'LONG':
            profit_usdt = quantity * max(0.0, current_price - entry_price)
        elif side == 'SHORT':
            profit_usdt = quantity * max(0.0, entry_price - current_price)

        profit_usdt = float(profit_usdt)

        activation_from_config = margin_usdt * (trailing_activation_percent / 100.0)
        realized_times_three = realized_abs * 3.0
        if activation_from_config >= realized_times_three:
            activation_threshold_usdt = activation_from_config
        else:
            activation_threshold_usdt = realized_abs * 4.0

        activation_threshold_usdt = float(activation_threshold_usdt)

        # Обновляем максимум прибыли
        profit_usdt_max = max(float(self.trailing_max_profit_usdt or 0.0), profit_usdt)
        self.trailing_max_profit_usdt = profit_usdt_max

        trailing_step_usdt = margin_usdt * (trailing_distance_percent / 100.0)
        trailing_step_usdt = max(trailing_step_usdt, 0.0)
        trailing_step_price = trailing_step_usdt / quantity if quantity > 0 else 0.0

        # Определяем, активирован ли трейлинг
        trailing_active = False
        if margin_usdt > 0 and activation_threshold_usdt > 0:
            trailing_active = profit_usdt_max >= activation_threshold_usdt

        locked_profit_usdt = realized_abs * 3.0
        if locked_profit_usdt < 0:
            locked_profit_usdt = 0.0

        steps = 0
        stop_price = None

        if trailing_active:
            prirost_max = max(0.0, profit_usdt_max - activation_threshold_usdt)
            if trailing_step_usdt > 0:
                steps = int(math.floor(prirost_max / trailing_step_usdt))
            locked_profit_total = locked_profit_usdt + steps * trailing_step_usdt
            locked_profit_total = min(locked_profit_total, profit_usdt_max)

            profit_per_coin = locked_profit_total / quantity if quantity > 0 else 0.0

            if side == 'LONG':
                stop_price = entry_price + profit_per_coin
                if current_price > 0:
                    stop_price = min(stop_price, current_price)
                stop_price = max(stop_price, entry_price)
            elif side == 'SHORT':
                stop_price = entry_price - profit_per_coin
                if current_price > 0:
                    stop_price = max(stop_price, current_price)
                stop_price = min(stop_price, entry_price)

            locked_profit_usdt = locked_profit_total
        else:
            locked_profit_total = locked_profit_usdt

        self.trailing_active = trailing_active
        self.trailing_step_usdt = trailing_step_usdt
        self.trailing_step_price = trailing_step_price
        self.trailing_steps = steps

        return {
            'active': trailing_active,
            'stop_price': stop_price,
            'activation_profit_usdt': activation_threshold_usdt,
            'activation_threshold_usdt': activation_threshold_usdt,
            'locked_profit_usdt': locked_profit_usdt,
            'margin_usdt': margin_usdt,
            'profit_usdt': profit_usdt,
            'profit_usdt_max': profit_usdt_max,
            'trailing_step_usdt': trailing_step_usdt,
            'trailing_step_price': trailing_step_price,
            'steps': steps,
            'trailing_distance_percent': trailing_distance_percent
        }

    def _get_position_quantity(self) -> float:
        """Возвращает количество монет в позиции"""
        quantity = self.position_size_coins
        try:
            if quantity is not None:
                quantity = float(quantity)
        except (TypeError, ValueError):
            quantity = None

        if not quantity and self.position_size and self.entry_price:
            try:
                quantity = abs(float(self.position_size) / float(self.entry_price))
            except (TypeError, ValueError, ZeroDivisionError):
                quantity = None

        if not quantity and self.volume_value and self.entry_price:
            try:
                quantity = abs(float(self.volume_value) / float(self.entry_price))
            except (TypeError, ValueError, ZeroDivisionError):
                quantity = None

        try:
            return abs(float(quantity)) if quantity is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _calculate_break_even_stop_price(self, current_price: Optional[float] = None) -> Optional[float]:
        """Рассчитывает цену стоп-лосса для безубыточности"""
        if not self.entry_price or self.position_side not in ('LONG', 'SHORT'):
            return None

        quantity = self._get_position_quantity()
        if quantity <= 0:
            return None

        try:
            fee_usdt = abs(float(self.realized_pnl or 0.0))
        except (TypeError, ValueError):
            fee_usdt = 0.0
        if fee_usdt <= 0:
            return None

        buffer_usdt = fee_usdt * self.BREAK_EVEN_FEE_MULTIPLIER
        buffer_per_coin = buffer_usdt / quantity if quantity > 0 else 0.0
        if buffer_per_coin <= 0:
            return None

        try:
            entry_price = float(self.entry_price)
        except (TypeError, ValueError):
            return None

        price = float(current_price) if current_price is not None else None

        if self.position_side == 'LONG':
            stop_price = entry_price + buffer_per_coin
            if price:
                stop_price = min(stop_price, price)
            stop_price = max(stop_price, entry_price)
        else:  # SHORT
            stop_price = entry_price - buffer_per_coin
            if price:
                stop_price = max(stop_price, price)
            stop_price = min(stop_price, entry_price)

        return stop_price

    def _ensure_break_even_stop(self, current_price: Optional[float], force: bool = False) -> None:
        """Устанавливает/обновляет стоп-лосс для безубыточности"""
        if not self.exchange or self.position_side not in ('LONG', 'SHORT'):
            return

        stop_price = self._calculate_break_even_stop_price(current_price)
        if stop_price is None:
            return

        if not force and self.break_even_stop_price is not None:
            tolerance = 1e-8
            if self.position_side == 'LONG':
                if stop_price <= self.break_even_stop_price + tolerance:
                    return
            else:  # SHORT
                if stop_price >= self.break_even_stop_price - tolerance:
                    return

        try:
            result = self.exchange.update_stop_loss(self.symbol, stop_price, self.position_side)
            if result and result.get('success'):
                self.break_even_stop_price = stop_price
                logger.info(f"[NEW_BOT_{self.symbol}] 🛡️ Break-even стоп обновлён: {stop_price:.6f}")
            else:
                logger.warning(
                    f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось установить break-even стоп: "
                    f"{(result or {}).get('message', 'Unknown')}"
                )
        except Exception as exc:
            logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка установки break-even стопа: {exc}")

    def check_protection_mechanisms(self, current_price):
        """Проверяет все защитные механизмы"""
        try:
            if not self.entry_price or not current_price:
                return {'should_close': False, 'reason': None}
            
            # Получаем настройки из конфига
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                stop_loss_percent = auto_config.get('stop_loss_percent', 15.0)
                break_even_enabled = bool(auto_config.get('break_even_protection', True))
                break_even_trigger_raw = auto_config.get(
                    'break_even_trigger_percent',
                    auto_config.get('break_even_trigger', 100.0)
                )

            try:
                break_even_trigger_percent = float(break_even_trigger_raw if break_even_trigger_raw is not None else 0.0)
            except (TypeError, ValueError):
                break_even_trigger_percent = 0.0
            if break_even_trigger_percent < 0:
                break_even_trigger_percent = 0.0
            
            # Вычисляем текущую прибыль в процентах
            if self.position_side == 'LONG':
                profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
            else:  # SHORT
                profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100

            logger.info(
                f"[NEW_BOT_{self.symbol}] 🛡️ Break-even статус: enabled={break_even_enabled} "
                f"trigger={break_even_trigger_percent:.2f}% profit={profit_percent:.2f}% "
                f"activated={self.break_even_activated} stop={self.break_even_stop_price}"
            )
            
            # 1. Проверка стоп-лосса
            if profit_percent <= -stop_loss_percent:
                logger.warning(f"[NEW_BOT_{self.symbol}] 💀 Стоп-лосс! Убыток: {profit_percent:.2f}%")
                return {'should_close': True, 'reason': f'STOP_LOSS_{profit_percent:.2f}%'}
            
            # 2. Обновляем максимальную прибыль
            if profit_percent > self.max_profit_achieved:
                self.max_profit_achieved = profit_percent
                logger.debug(f"[NEW_BOT_{self.symbol}] 📈 Новая максимальная прибыль: {profit_percent:.2f}%")
            
            # 3. Проверка безубыточности
            if break_even_enabled and break_even_trigger_percent > 0:
                if not self.break_even_activated and profit_percent >= break_even_trigger_percent:
                    self.break_even_activated = True
                    logger.info(f"[NEW_BOT_{self.symbol}] 🛡️ Безубыток активирован: {profit_percent:.2f}%")
                    self._ensure_break_even_stop(current_price, force=True)

                if self.break_even_activated:
                    self._ensure_break_even_stop(current_price)
                    if profit_percent <= 0:
                        logger.info(f"[NEW_BOT_{self.symbol}] 🛡️ Закрываем по безубытку")
                        return {'should_close': True, 'reason': f'BREAK_EVEN_MAX_{self.max_profit_achieved:.2f}%'}
            else:
                if self.break_even_activated or self.break_even_stop_price is not None:
                    logger.debug(f"[NEW_BOT_{self.symbol}] 🛡️ Безубыток отключен настройками")
                self.break_even_activated = False
                self.break_even_stop_price = None
            
            # 4. Проверка trailing stop
            trailing_info = self._calculate_trailing_by_margin(profit_percent, current_price)
            try:
                logger.info(
                    f"[NEW_BOT_{self.symbol}] 🌀 Trailing расчёт: profit={trailing_info.get('profit_usdt', 0.0):.4f} "
                    f"max={trailing_info.get('profit_usdt_max', 0.0):.4f} "
                    f"threshold={trailing_info.get('activation_threshold_usdt', 0.0):.4f} "
                    f"locked={trailing_info.get('locked_profit_usdt', 0.0):.4f} "
                    f"steps={trailing_info.get('steps', 0)} "
                    f"active={trailing_info.get('active', False)} "
                    f"stop={trailing_info.get('stop_price')}"
                )
            except Exception:
                logger.debug(f"[NEW_BOT_{self.symbol}] 🌀 Trailing расчёт: {trailing_info}")
            self.trailing_activation_profit = trailing_info.get('activation_profit_usdt', 0.0)
            self.trailing_activation_threshold = trailing_info.get('activation_threshold_usdt', self.trailing_activation_threshold)
            self.trailing_locked_profit = trailing_info.get('locked_profit_usdt', 0.0)
            self.margin_usdt = trailing_info.get('margin_usdt', self.margin_usdt)
            self.unrealized_pnl_usdt = trailing_info.get('profit_usdt', self.unrealized_pnl_usdt)
            self.trailing_active = trailing_info.get('active', self.trailing_active)
            self.trailing_max_profit_usdt = trailing_info.get('profit_usdt_max', self.trailing_max_profit_usdt)
            self.trailing_step_usdt = trailing_info.get('trailing_step_usdt', self.trailing_step_usdt)
            self.trailing_step_price = trailing_info.get('trailing_step_price', self.trailing_step_price)
            self.trailing_steps = trailing_info.get('steps', self.trailing_steps)

            if trailing_info.get('active') and trailing_info.get('stop_price'):
                stop_price = trailing_info['stop_price']
                self.trailing_stop_price = stop_price
                if self.position_side == 'LONG' and current_price <= stop_price:
                    logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Trailing Stop (LONG) достигнут: {stop_price:.6f}")
                    return {'should_close': True, 'reason': f'TRAILING_STOP_USD_{self.trailing_locked_profit:.4f}'}
                if self.position_side == 'SHORT' and current_price >= stop_price:
                    logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Trailing Stop (SHORT) достигнут: {stop_price:.6f}")
                    return {'should_close': True, 'reason': f'TRAILING_STOP_USD_{self.trailing_locked_profit:.4f}'}
            
            try:
                trailing_take_distance_percent = auto_config.get('trailing_take_distance', trailing_info.get('trailing_distance_percent'))
            except Exception:
                trailing_take_distance_percent = trailing_info.get('trailing_distance_percent')
            self._update_trailing_take_profit(current_price, trailing_take_distance_percent or auto_config.get('trailing_stop_distance'))

            return {'should_close': False, 'reason': None}
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки защитных механизмов: {e}")
            return {'should_close': False, 'reason': None}
    
    def _update_protection_mechanisms(self, current_price):
        """Обновляет защитные механизмы"""
        try:
            if not self.entry_price or not current_price:
                return
            
            # Вычисляем текущую прибыль
            if self.position_side == 'LONG':
                profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
            else:  # SHORT
                profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100
            
                        # Обновляем максимальную прибыль
            if profit_percent > self.max_profit_achieved:
                self.max_profit_achieved = profit_percent
                logger.debug(f"[NEW_BOT_{self.symbol}] 📈 Обновлена максимальная прибыль: {profit_percent:.2f}%")
                
                # Обновляем стоп-лосс на бирже (программный трейлинг)
                self._update_stop_loss_on_exchange(current_price, profit_percent)
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка обновления защитных механизмов: {e}")
    
    def _update_stop_loss_on_exchange(self, current_price, profit_percent):
        """
        Обновляет стоп-лосс на бирже для программного трейлинга
        
        Args:
            current_price (float): Текущая цена
            profit_percent (float): Текущая прибыль в %
        """
        try:
            # Получаем настройки из конфига
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                trailing_activation_percent = auto_config.get('trailing_stop_activation', 300.0)
                trailing_distance_percent = auto_config.get('trailing_stop_distance', 150.0)
                trailing_take_distance_percent = auto_config.get('trailing_take_distance', trailing_distance_percent)

            trailing_info = self._calculate_trailing_by_margin(profit_percent, current_price)
            try:
                logger.info(
                    f"[NEW_BOT_{self.symbol}] 🔁 Trailing обновление: profit={trailing_info.get('profit_usdt', 0.0):.4f} "
                    f"max={trailing_info.get('profit_usdt_max', 0.0):.4f} "
                    f"threshold={trailing_info.get('activation_threshold_usdt', 0.0):.4f} "
                    f"locked={trailing_info.get('locked_profit_usdt', 0.0):.4f} "
                    f"steps={trailing_info.get('steps', 0)} "
                    f"active={trailing_info.get('active', False)} "
                    f"stop={trailing_info.get('stop_price')}"
                )
            except Exception:
                logger.debug(f"[NEW_BOT_{self.symbol}] 🔁 Trailing обновление: {trailing_info}")
            self.trailing_activation_profit = trailing_info.get('activation_profit_usdt', 0.0)
            self.trailing_activation_threshold = trailing_info.get('activation_threshold_usdt', self.trailing_activation_threshold)
            self.trailing_locked_profit = trailing_info.get('locked_profit_usdt', 0.0)
            self.margin_usdt = trailing_info.get('margin_usdt', self.margin_usdt)
            self.trailing_active = trailing_info.get('active', self.trailing_active)
            self.trailing_max_profit_usdt = trailing_info.get('profit_usdt_max', self.trailing_max_profit_usdt)
            self.trailing_step_usdt = trailing_info.get('trailing_step_usdt', self.trailing_step_usdt)
            self.trailing_step_price = trailing_info.get('trailing_step_price', self.trailing_step_price)
            self.trailing_steps = trailing_info.get('steps', self.trailing_steps)

            if self.break_even_activated:
                self._ensure_break_even_stop(current_price)

            activation_threshold_usdt = trailing_info.get('activation_threshold_usdt', 0.0)
            profit_usdt = trailing_info.get('profit_usdt', 0.0)
            profit_usdt_max = trailing_info.get('profit_usdt_max', self.trailing_max_profit_usdt)

            if not trailing_info.get('active'):
                # Фолбэк к процентам, если нет данных по комиссиям
                if activation_threshold_usdt > 0 and profit_usdt_max >= activation_threshold_usdt:
                    fallback_stop = None
                    if self.position_side == 'LONG':
                        max_price = self.entry_price * (1 + self.max_profit_achieved / 100)
                        fallback_stop = max_price * (1 - trailing_distance_percent / 100)
                        fallback_stop = max(fallback_stop, self.entry_price)
                    elif self.position_side == 'SHORT':
                        min_price = self.entry_price * (1 - self.max_profit_achieved / 100)
                        fallback_stop = min_price * (1 + trailing_distance_percent / 100)
                        fallback_stop = min(fallback_stop, self.entry_price)

                    if fallback_stop and self.exchange:
                        try:
                            result = self.exchange.update_stop_loss(self.symbol, fallback_stop, self.position_side)
                            if result and result.get('success'):
                                logger.debug(f"[NEW_BOT_{self.symbol}] 📈 Trailing stop (fallback) обновлен до {fallback_stop:.6f}")
                        except Exception as exc:
                            logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка fallback trailing stop: {exc}")
                return

            desired_stop = trailing_info.get('stop_price')
            if self.break_even_stop_price is not None:
                if self.position_side == 'LONG':
                    if desired_stop is None or desired_stop < self.break_even_stop_price:
                        desired_stop = self.break_even_stop_price
                elif self.position_side == 'SHORT':
                    if desired_stop is None or desired_stop > self.break_even_stop_price:
                        desired_stop = self.break_even_stop_price
            if desired_stop is None:
                logger.debug(f"[NEW_BOT_{self.symbol}] 🔁 Trailing: стоп не рассчитан")
                return

            self.trailing_stop_price = desired_stop

            if self.exchange:
                try:
                    result = self.exchange.update_stop_loss(self.symbol, desired_stop, self.position_side)
                    if result and result.get('success'):
                        logger.debug(f"[NEW_BOT_{self.symbol}] 📈 Trailing stop обновлен до {desired_stop:.6f}")
                    else:
                        logger.warning(
                            f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось обновить trailing stop: "
                            f"{result.get('message', 'Unknown error') if result else 'No response'}"
                        )
                except Exception as exc:
                    logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка обновления trailing stop: {exc}")

            self._update_trailing_take_profit(current_price, trailing_take_distance_percent)
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка расчета программного trailing stop: {e}")
    
    def _update_trailing_take_profit(self, current_price: Optional[float], distance_percent: Optional[float]) -> None:
        """Поддерживает резервный trailing take-profit через API биржи."""
        if not self.exchange or current_price is None:
            return
        try:
            price = float(current_price)
        except (TypeError, ValueError):
            return
        if price <= 0 or self.position_side not in ('LONG', 'SHORT'):
            return

        try:
            distance = float(distance_percent or 0.0)
        except (TypeError, ValueError):
            distance = 0.0
        if distance <= 0:
            return

        candidate_price: Optional[float] = None
        if self.position_side == 'LONG':
            candidate_price = price * (1 + distance / 100.0)
            if candidate_price <= self.entry_price:
                candidate_price = None
            elif self.trailing_take_profit_price is not None and candidate_price <= self.trailing_take_profit_price:
                candidate_price = None
        elif self.position_side == 'SHORT':
            candidate_price = price * (1 - distance / 100.0)
            if candidate_price >= self.entry_price or candidate_price <= 0:
                candidate_price = None
            elif self.trailing_take_profit_price is not None and candidate_price >= self.trailing_take_profit_price:
                candidate_price = None

        if candidate_price is None:
            return

        try:
            result = self.exchange.update_take_profit(self.symbol, candidate_price, self.position_side)
            if result and result.get('success'):
                self.trailing_take_profit_price = candidate_price
                logger.debug(f"[NEW_BOT_{self.symbol}] 🎯 Trailing TP обновлён: {candidate_price:.6f}")
            else:
                logger.warning(
                    f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось обновить trailing TP: "
                    f"{(result or {}).get('message', 'Unknown error')}"
                )
        except AttributeError:
            logger.debug(f"[NEW_BOT_{self.symbol}] ℹ️ Биржа не поддерживает update_take_profit")
        except Exception as exc:
            logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка обновления trailing TP: {exc}")

    def _sync_position_with_exchange(self):
        """Синхронизирует данные бота с позицией на бирже"""
        try:
            if not self.exchange:
                return
            
            exchange_positions = self.exchange.get_positions()
            if isinstance(exchange_positions, tuple):
                positions_list = exchange_positions[0] if exchange_positions else []
            else:
                positions_list = exchange_positions if exchange_positions else []
            
            for pos in positions_list:
                if pos.get('symbol') == self.symbol and abs(float(pos.get('size', 0))) > 0:
                    self.entry_price = float(pos.get('entry_price', 0))
                    raw_side = pos.get('side', self.position_side)
                    if isinstance(raw_side, str):
                        lower_side = raw_side.lower()
                        if lower_side in ['buy', 'long']:
                            self.position_side = 'LONG'
                        elif lower_side in ['sell', 'short']:
                            self.position_side = 'SHORT'
                        else:
                            self.position_side = raw_side
                    self.position_size = abs(float(pos.get('size', 0)))  # ✅ Сохраняем размер позиции (USDT)
                    self.position_size_coins = abs(float(pos.get('size', 0)))
                    self.unrealized_pnl = float(pos.get('unrealized_pnl', 0))
                    self.unrealized_pnl_usdt = float(pos.get('unrealized_pnl', 0))
                    self.realized_pnl = float(pos.get('realized_pnl', 0))
                    self.leverage = float(pos.get('leverage', self.leverage or 1) or 1)

                    if self.entry_price and self.position_size_coins:
                        position_value = self.entry_price * self.position_size_coins
                        self.margin_usdt = position_value / (self.leverage if self.leverage else 1)
                    break
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка синхронизации с биржей: {e}")
    
    def enter_position(self, direction):
        """
        Публичный метод для входа в позицию
        
        Args:
            direction (str): Направление сделки ('LONG' или 'SHORT')
            
        Returns:
            bool: True если вход успешен, False иначе
        """
        try:
            # Получаем текущую цену
            ticker = self.exchange.get_ticker(self.symbol) if self.exchange else None
            price = ticker['last'] if ticker and 'last' in ticker else 0
            
            
            # 🤖 Сбор данных для ИИ и проверка оптимальной точки входа (если включено)
            try:
                from bot_engine.bot_config import RiskConfig
                from bot_engine.ai.smart_risk_manager import SmartRiskManager
                from bots_modules.imports_and_globals import get_auto_bot_config, coins_rsi_data, rsi_data_lock
                
                auto_config = get_auto_bot_config()
                ai_optimal_entry_enabled = auto_config.get('ai_optimal_entry_enabled', False)
                
                # Получаем RSI
                rsi = 0
                with rsi_data_lock:
                    coin_data = coins_rsi_data['coins'].get(self.symbol)
                    if coin_data:
                        rsi = coin_data.get('rsi6h', 50)
                
                # Получаем свечи для анализа
                chart_response = self.exchange.get_chart_data(self.symbol, '6h', limit=30) if self.exchange else None
                candles = []
                if chart_response and chart_response.get('success'):
                    candles_data = chart_response.get('data', {}).get('candles', [])
                    candles = [{'open': float(c.get('open', 0)), 'high': float(c.get('high', 0)),
                                'low': float(c.get('low', 0)), 'close': float(c.get('close', 0)),
                                'volume': float(c.get('volume', 0))} for c in candles_data[-10:]] if candles_data else []
                
                # 📊 ВСЕГДА собираем данные для обучения ИИ (если есть лицензия)
                try:
                    smart_risk = SmartRiskManager()
                    smart_risk.collect_entry_data(
                        symbol=self.symbol,
                        current_price=price,
                        side=direction,
                        rsi=rsi,
                        candles=candles
                    )
                except Exception as collect_error:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось собрать данные ИИ: {collect_error}")
                
                # 🔍 Проверяем оптимальную точку входа (только если включено в конфиге)
                if ai_optimal_entry_enabled:
                    # Проверяем, стоит ли входить сейчас
                    smart_risk = SmartRiskManager()
                    decision = smart_risk.should_enter_now(
                        symbol=self.symbol,
                        current_price=price,
                        side=direction,
                        rsi=rsi,
                        candles=candles
                    )
                    
                    if not decision.get('should_enter', True):
                        logger.debug(f"[NEW_BOT_{self.symbol}] ⏳ ИИ: подождать")
                        return False
                    else:
                        logger.debug(f"[NEW_BOT_{self.symbol}] ✅ ИИ: вход")
                
            except ImportError:
                # ИИ функция недоступна (нет лицензии) - продолжаем как обычно
                pass
            except Exception as ai_error:
                logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка проверки ИИ входа: {ai_error}")
                # Продолжаем обычный вход при ошибке ИИ
            
            # ✅ Получаем текущий тренд монеты для сохранения
            current_trend = None
            try:
                with rsi_data_lock:
                    coin_data = coins_rsi_data['coins'].get(self.symbol)
                    if coin_data:
                        current_trend = coin_data.get('trend6h') or coin_data.get('trend')
            except Exception as trend_error:
                logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось получить тренд: {trend_error}")
            
            # Открываем позицию
            if self._open_position_on_exchange(direction, price):
                # ✅ Сохраняем тренд при входе (для определения правильного RSI выхода)
                self.entry_trend = current_trend
                
                # Обновляем статус
                status_key = 'IN_POSITION_LONG' if direction == 'LONG' else 'IN_POSITION_SHORT'
                self.update_status(BOT_STATUS[status_key], price, direction)
                
                # Сохраняем состояние
                with bots_data_lock:
                    bots_data['bots'][self.symbol] = self.to_dict()
                
                logger.info(f"[NEW_BOT_{self.symbol}] 📊 Вход в {direction} при тренде: {current_trend or 'UNKNOWN'}")
                
                return True
            else:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось войти в {direction} позицию")
                return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка входа в позицию: {e}")
            return False
    
    def _open_position_on_exchange(self, side, price):
        """Открывает позицию на бирже"""
        try:
            if not self.exchange:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Биржа не инициализирована")
                return False
            
            
            # Открываем позицию на бирже
            # Рассчитываем количество монет на основе volume_value в USDT
            qty_in_coins = self.volume_value / price if price > 0 else 0
            
            
            # Получаем max_loss_percent из конфига Auto Bot для стоп-лосса
            auto_bot_config = get_auto_bot_config()
            max_loss_percent = auto_bot_config.get('max_loss_percent', 15.0)
            
            
            # ШАГ 1: Открываем позицию БЕЗ стоп-лосса и тейк-профита
            order_result = self.exchange.place_order(
                symbol=self.symbol,
                side=side,
                quantity=self.volume_value,  # ⚡ Количество в USDT (не в монетах!)
                order_type='market',
                take_profit=None,  # 🔴 НЕ устанавливаем TP
                stop_loss=None,  # 🔴 НЕ устанавливаем SL
                max_loss_percent=None  # 🔴 НЕ рассчитываем SL
            )
            
            if order_result and order_result.get('success'):
                self.order_id = order_result.get('order_id')
                self.entry_timestamp = datetime.now().isoformat()
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ Позиция {side} открыта")
                
                # Определяем источник решения (AI или SCRIPT)
                decision_source = 'SCRIPT'
                ai_decision_id = None
                ai_confidence = None
                ai_signal = None
                
                if hasattr(self, 'ai_decision_id') and self.ai_decision_id:
                    decision_source = 'AI'
                    ai_decision_id = self.ai_decision_id
                    # Получаем данные AI решения если доступны
                    try:
                        from bot_engine.ai.ai_integration import get_ai_decision
                        ai_decision = get_ai_decision(self.ai_decision_id)
                        if ai_decision:
                            ai_confidence = ai_decision.get('ai_confidence')
                            ai_signal = ai_decision.get('ai_signal')
                    except:
                        pass
                
                # ШАГ 2: Получаем реальные данные позиции (entry_price, leverage, quantity) с RETRY
                
                actual_entry_price = None
                actual_leverage = None
                actual_qty = None
                
                # RETRY: 3 попытки с задержкой 0.5с, 1с, 2с (общий таймаут ~3.5с)
                max_attempts = 3
                retry_delays = [0.5, 1.0, 2.0]
                
                for attempt in range(max_attempts):
                    try:
                        # Задержка перед попыткой получения данных
                        time.sleep(retry_delays[attempt])
                        
                        # Получаем позицию с биржи
                        position_data = self.exchange.get_positions()
                        
                        if isinstance(position_data, tuple):
                            positions_list = position_data[0] if position_data else []
                        else:
                            positions_list = position_data if position_data else []
                        
                        # Ищем нашу позицию
                        for pos in positions_list:
                            if pos.get('symbol') == self.symbol and abs(float(pos.get('size', 0))) > 0:
                                actual_entry_price = float(pos.get('entry_price', 0))
                                actual_leverage = float(pos.get('leverage', 10.0))
                                actual_qty = float(pos.get('size', 0))
                                
                                # ✅ КРИТИЧНО: Сохраняем размер позиции в боте!
                                self.position_size = abs(actual_qty)
                                
                                
                                # Если получили валидные данные - выходим из цикла
                                if actual_entry_price and actual_entry_price > 0:
                                    logger.info(f"[NEW_BOT_{self.symbol}] ✅ Данные позиции получены успешно!")
                                    break
                        
                        # Если нашли валидную позицию - выходим из retry-цикла
                        if actual_entry_price and actual_entry_price > 0:
                            break
                        else:
                            logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Попытка {attempt + 1}/{max_attempts}: данные не получены, повторяем...")
                    
                    except Exception as retry_error:
                        logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Попытка {attempt + 1}/{max_attempts}: ошибка {retry_error}")
                        if attempt == max_attempts - 1:
                            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Все попытки исчерпаны!")
                
                # Если после всех попыток не получили данные - используем fallback
                if not actual_entry_price or actual_entry_price == 0:
                    logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось получить данные позиции, используем fallback: цена={price}, плечо=10x")
                    actual_entry_price = price
                    actual_leverage = 10.0  # Дефолт
                
                if not actual_leverage:
                    actual_leverage = 10.0  # Дефолт
                
                # 🔄 ШАГ 2.5: PREMIUM - Проверка частых стопов и бэктest перед расчетом SL/TP
                # ⚠️ ВАЖНО: Все функции ниже работают ТОЛЬКО с премиум лицензией!
                # Без премиума используется базовый расчет стоп-лосса (15% от стоимости входа)
                backtest_result = None
                should_avoid = False
                avoid_reason = None
                smart_risk = None
                
                try:
                    from bot_engine.ai import check_premium_license
                    is_premium = check_premium_license()
                    
                    if is_premium:
                        # ✅ ПРЕМИУМ ЛИЦЕНЗИЯ АКТИВНА - используем умные стопы
                        try:
                            from bot_engine.ai.smart_risk_manager import SmartRiskManager
                            smart_risk = SmartRiskManager()
                            
                            # 🚫 ШАГ 2.5.1: PREMIUM - Проверяем не слишком ли частые стопы для этой монеты
                            avoid_check = smart_risk.should_avoid_entry(self.symbol, side)
                            should_avoid = avoid_check.get('should_avoid', False)
                            avoid_reason = avoid_check.get('reason', '')
                            
                            if should_avoid:
                                wait_minutes = avoid_check.get('wait_minutes', 60)
                                logger.warning(f"[NEW_BOT_{self.symbol}] 🚫 [PREMIUM] УМНЫЙ ФИЛЬТР: Избегаем входа - {avoid_reason}. Ждем {wait_minutes} мин")
                                # Не открываем позицию, но не выбрасываем ошибку - просто пропускаем
                                return False
                            
                            # Если рекомендуется увеличенный SL - используем его
                            recommended_sl = avoid_check.get('recommended_sl_percent')
                            if recommended_sl:
                                logger.info(f"[NEW_BOT_{self.symbol}] 🤖 [PREMIUM] УМНЫЙ СТОП: Рекомендуется увеличенный SL: {recommended_sl}% (было {max_loss_percent}%)")
                                max_loss_percent = recommended_sl
                            
                            # Получаем свечи для бэктеста
                            chart_response = self.exchange.get_chart_data(self.symbol, '6h', limit=50)
                            candles_for_backtest = []
                            
                            if chart_response and chart_response.get('success'):
                                candles_data = chart_response.get('data', {}).get('candles', [])
                                if candles_data and len(candles_data) >= 20:
                                    for c in candles_data:
                                        candles_for_backtest.append({
                                            'open': float(c.get('open', 0)),
                                            'high': float(c.get('high', 0)),
                                            'low': float(c.get('low', 0)),
                                            'close': float(c.get('close', 0)),
                                            'volume': float(c.get('volume', 0))
                                        })
                                    
                                    # 🎯 PREMIUM - Запускаем бэктест на основе истории стопов для этой монеты
                                    backtest_result = smart_risk.backtest_coin(
                                        self.symbol, 
                                        candles_for_backtest, 
                                        side,
                                        actual_entry_price
                                    )
                                    
                                    logger.info(f"[NEW_BOT_{self.symbol}] 🤖 [PREMIUM] Бэктест завершен: SL={backtest_result.get('optimal_sl_percent')}%, TP={backtest_result.get('optimal_tp_percent')}%, confidence={backtest_result.get('confidence', 0):.1%}")
                                    
                                    # Сохраняем для обратной связи
                                    self._last_backtest_result = backtest_result
                        except ImportError as import_error:
                            # SmartRiskManager недоступен (нет премиум лицензии)
                            logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ [PREMIUM] SmartRiskManager недоступен: {import_error}. Используем базовый расчет.")
                            is_premium = False  # Отключаем премиум функции
                    else:
                        # Нет премиум лицензии - используем базовый расчет стоп-лосса
                        logger.debug(f"[NEW_BOT_{self.symbol}] ℹ️ Премиум лицензия не найдена - используем базовый расчет SL ({max_loss_percent}% от стоимости входа)")
                        
                except Exception as ai_error:
                    # Любая ошибка - используем базовый расчет
                    logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Premium функции недоступны: {ai_error}. Используем базовый расчет.")
                    self._last_backtest_result = None
                
                # ШАГ 3: Рассчитываем Stop Loss
                stop_loss_price = None
                sl_percent_from_config = max_loss_percent
                
                # 🤖 PREMIUM: Если есть результат бэктеста - используем его значения
                if backtest_result and backtest_result.get('confidence', 0) > 0.7:
                    optimal_sl_pct = backtest_result.get('optimal_sl_percent', max_loss_percent)
                    sl_percent_from_config = optimal_sl_pct
                    logger.info(f"[NEW_BOT_{self.symbol}] 🤖 [PREMIUM] Используем SL из бэктеста на основе истории: {optimal_sl_pct}%")
                
                if max_loss_percent:
                    # 🤖 БАЗОВЫЙ AI: Пытаемся использовать DynamicRiskManager для адаптивного SL (работает без премиума)
                    # Это базовая функция на основе волатильности, не требует премиум
                    if not backtest_result:
                        try:
                            if AI_RISK_MANAGER_AVAILABLE and DynamicRiskManager:
                                # Получаем свечи для AI анализа
                                chart_response = self.exchange.get_chart_data(self.symbol, '6h', limit=50)
                                candles_for_ai = []
                                
                                if chart_response and chart_response.get('success'):
                                    candles_data = chart_response.get('data', {}).get('candles', [])
                                    if candles_data and len(candles_data) >= 20:
                                        # Конвертируем свечи в формат для AI
                                        for c in candles_data[-30:]:  # Последние 30 свечей
                                            candles_for_ai.append({
                                                'open': float(c.get('open', 0)),
                                                'high': float(c.get('high', 0)),
                                                'low': float(c.get('low', 0)),
                                                'close': float(c.get('close', 0)),
                                                'volume': float(c.get('volume', 0))
                                            })
                                        
                                        # Используем AI Risk Manager
                                        risk_manager = DynamicRiskManager()
                                        ai_sl_result = risk_manager.calculate_dynamic_sl(
                                            self.symbol, candles_for_ai, side
                                        )
                                        
                                        # Берем AI адаптированный SL
                                        sl_percent_from_config = ai_sl_result['sl_percent']
                                        logger.info(f"[NEW_BOT_{self.symbol}] 🤖 AI адаптировал SL: {max_loss_percent}% → {sl_percent_from_config}% ({ai_sl_result['reason']})")
                        except Exception as ai_error:
                            logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ AI SL недоступен: {ai_error}, используем базовый расчет")
                    
                    # ✅ БАЗОВЫЙ РАСЧЕТ: Рассчитываем стоп на основе стоимости входа (НЕ от маржи!)
                    # Стоп-лосс должен быть % от стоимости входа позиции (как указано в конфиге: 15% убытка)
                    # Например: стоимость входа 5 USDT, стоп-лосс 15% → убыток 0.75 USDT
                    position_value = abs(actual_qty) * actual_entry_price if actual_qty else self.volume_value
                    
                    # Убыток в USDT = % от стоимости входа (как указано в конфиге)
                    max_loss_usdt = position_value * (sl_percent_from_config / 100)
                    
                    # Рассчитываем убыток на одну монету
                    if actual_qty and abs(actual_qty) > 0:
                        loss_per_coin = max_loss_usdt / abs(actual_qty)
                    else:
                        # Если нет actual_qty, рассчитываем через volume_value
                        estimated_qty = self.volume_value / actual_entry_price if actual_entry_price > 0 else 0
                        loss_per_coin = max_loss_usdt / estimated_qty if estimated_qty > 0 else 0
                    
                    # Рассчитываем цену стоп-лосса
                    if side == 'LONG':
                        stop_loss_price = actual_entry_price - loss_per_coin
                    else:
                        stop_loss_price = actual_entry_price + loss_per_coin
                    
                    logger.info(f"[NEW_BOT_{self.symbol}] 🛑 SL рассчитан: {stop_loss_price:.6f} (entry={actual_entry_price:.6f}, стоимость позиции={position_value:.4f} USDT, убыток={max_loss_usdt:.4f} USDT = {sl_percent_from_config}% от входа)")
                
                # ШАГ 4: Рассчитываем Take Profit от стоимости входа (как стоп-лосс!)
                # ⚠️ ВАЖНО: Основной выход по RSI 6h (65 для LONG, 35 для SHORT), TP только защитный
                # TP рассчитывается как стоп-лосс: % от стоимости входа позиции (из конфига)
                take_profit_price = None
                
                # Получаем процент TP из конфига
                auto_bot_config = get_auto_bot_config()
                tp_percent = auto_bot_config.get('take_profit_percent', 20.0)  # По умолчанию 20%
                
                # Рассчитываем TP на основе стоимости входа (как стоп-лосс!)
                # Стоимость позиции = количество × цена входа
                position_value = abs(actual_qty) * actual_entry_price if actual_qty else self.volume_value
                
                # Прибыль в USDT = % от стоимости входа (как указано в конфиге)
                target_profit_usdt = position_value * (tp_percent / 100)
                
                # Рассчитываем прибыль на одну монету
                if actual_qty and abs(actual_qty) > 0:
                    profit_per_coin = target_profit_usdt / abs(actual_qty)
                else:
                    # Если нет actual_qty, рассчитываем через volume_value
                    estimated_qty = self.volume_value / actual_entry_price if actual_entry_price > 0 else 0
                    profit_per_coin = target_profit_usdt / estimated_qty if estimated_qty > 0 else 0
                
                # Рассчитываем цену Take Profit
                if side == 'LONG':
                    take_profit_price = actual_entry_price + profit_per_coin
                    logger.info(f"[NEW_BOT_{self.symbol}] 🎯 Защитный TP установлен: {actual_entry_price:.6f} → {take_profit_price:.6f} (стоимость позиции={position_value:.4f} USDT, прибыль={target_profit_usdt:.4f} USDT = {tp_percent}% от входа, основной выход по RSI 6h=65)")
                else:  # SHORT
                    take_profit_price = actual_entry_price - profit_per_coin
                    logger.info(f"[NEW_BOT_{self.symbol}] 🎯 Защитный TP установлен: {actual_entry_price:.6f} → {take_profit_price:.6f} (стоимость позиции={position_value:.4f} USDT, прибыль={target_profit_usdt:.4f} USDT = {tp_percent}% от входа, основной выход по RSI 6h=35)")
                
                # ШАГ 5: Устанавливаем Stop Loss и Take Profit на бирже
                if stop_loss_price and stop_loss_price > 0:
                    sl_result = self.exchange.update_stop_loss(self.symbol, stop_loss_price, side)
                    if sl_result and sl_result.get('success'):
                        logger.info(f"[NEW_BOT_{self.symbol}] ✅ Stop Loss установлен: {stop_loss_price:.6f}")
                    else:
                        logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось установить SL: {sl_result.get('message') if sl_result else 'Unknown'}")
                
                if take_profit_price and take_profit_price > 0:
                    tp_result = self.exchange.update_take_profit(self.symbol, take_profit_price, side)
                    if tp_result and tp_result.get('success'):
                        logger.info(f"[NEW_BOT_{self.symbol}] ✅ Take Profit установлен: {take_profit_price:.6f}")
                    else:
                        logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Не удалось установить TP: {tp_result.get('message') if tp_result else 'Unknown'}")
                
                # Сохраняем данные позиции в боте
                self.entry_price = actual_entry_price
                self.position_side = side
                
                # Получаем RSI и тренд для логирования
                current_rsi = None
                current_trend = None
                try:
                    with rsi_data_lock:
                        coin_data = coins_rsi_data['coins'].get(self.symbol)
                        if coin_data:
                            current_rsi = coin_data.get('rsi')
                            current_trend = coin_data.get('trend6h')
                except:
                    pass
                
                # ВАЖНО: Логируем открытие позиции с информацией об источнике решения
                try:
                    from bot_engine.bot_history import bot_history_manager
                    position_size_usdt = abs(actual_qty) * actual_entry_price if actual_qty else self.volume_value
                    bot_history_manager.log_position_opened(
                        bot_id=self.symbol,
                        symbol=self.symbol,
                        direction=side,
                        size=position_size_usdt,
                        entry_price=actual_entry_price,
                        stop_loss=stop_loss_price,
                        take_profit=take_profit_price,
                        decision_source=decision_source,
                        ai_decision_id=ai_decision_id,
                        ai_confidence=ai_confidence,
                        ai_signal=ai_signal,
                        rsi=current_rsi,
                        trend=current_trend
                    )
                except Exception as log_error:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка логирования открытия: {log_error}")
                
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ Позиция успешно открыта с TP/SL")
                return True
            else:
                error = order_result.get('error', 'Unknown error') if order_result else 'No response'
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось открыть позицию: {error}")
                return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка открытия позиции: {e}")
            return False
    
    def _close_position_on_exchange(self, reason):
        """Закрывает позицию на бирже"""
        try:
            if not self.exchange:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Биржа не инициализирована")
                return False
            
            if not self.position_side:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ КРИТИЧЕСКАЯ ОШИБКА: position_side не установлен! Невозможно закрыть позицию!")
                return False
            
            # Получаем актуальный размер позиции с биржи
            position_size = None
            expected_side = 'Long' if self.position_side == 'LONG' else 'Short' if self.position_side == 'SHORT' else self.position_side
            
            try:
                positions = self.exchange.get_positions()
                if isinstance(positions, tuple):
                    positions_list = positions[0] if positions else []
                else:
                    positions_list = positions if positions else []
                
                for pos in positions_list:
                    symbol_name = pos.get('symbol', '')
                    normalized_symbol = symbol_name.replace('USDT', '')
                    if normalized_symbol == self.symbol or symbol_name == self.symbol:
                        pos_side = 'Long' if pos.get('side') in ['Buy', 'Long'] else 'Short'
                        if pos_side == expected_side and abs(float(pos.get('size', 0))) > 0:
                            position_size = abs(float(pos.get('size', 0)))
                            # Сохраняем актуальный размер
                            self.position_size = position_size
                            self.position_size_coins = position_size
                            break
            except Exception as e:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка получения размера позиции с биржи: {e}")
            
            # Если с биржи получить не удалось — используем кешированные значения как fallback
            if position_size is None or position_size <= 0:
                cached_sizes = [
                    self.position_size_coins,
                    self.position_size,
                    (self.volume_value / self.entry_price) if self.entry_price else None
                ]
                for cached_value in cached_sizes:
                    try:
                        if cached_value and abs(float(cached_value)) > 0:
                            position_size = abs(float(cached_value))
                            logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Используем кешированный размер позиции: {position_size}")
                            break
                    except (TypeError, ValueError):
                        continue
            
            if position_size is None or position_size <= 0:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось определить размер позиции для закрытия!")
                return False
            
            # ✅ КРИТИЧНО: Преобразуем side в формат, который ожидает биржа ('Long'/'Short')
            side_for_exchange = 'Long' if self.position_side == 'LONG' else 'Short' if self.position_side == 'SHORT' else self.position_side
            
            
            # Закрываем позицию на бирже
            close_result = self.exchange.close_position(
                symbol=self.symbol,
                size=position_size,
                side=side_for_exchange  # ✅ Используем правильный формат
            )
            
            
            if close_result and close_result.get('success'):
                
                # Сохраняем историю закрытия позиции (для обучения ИИ)
                try:
                    self._log_position_closed(reason, close_result)
                except Exception as log_error:
                    logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка логирования закрытия: {log_error}")
                
                # 🎓 Обратная связь для обучения ИИ (если есть backtest_result)
                if hasattr(self, '_last_backtest_result') and self._last_backtest_result:
                    try:
                        self._evaluate_ai_prediction(reason, close_result)
                    except Exception as ai_error:
                        logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка оценки ИИ: {ai_error}")
                
                # КРИТИЧНО: Обновляем статус бота
                old_status = self.status
                self.update_status(BOT_STATUS['IDLE'])
                self.position_side = None
                self.entry_price = None
                self.unrealized_pnl = 0
                self.break_even_stop_price = None
                
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ Статус бота обновлен: {old_status} → {BOT_STATUS['IDLE']}")
                
                # КРИТИЧНО: Сохраняем состояние бота в bots_data
                try:
                    with bots_data_lock:
                        if self.symbol in bots_data['bots']:
                            bots_data['bots'][self.symbol] = self.to_dict()
                            logger.info(f"[NEW_BOT_{self.symbol}] ✅ Состояние бота сохранено в bots_data")
                except Exception as save_error:
                    logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка сохранения состояния бота: {save_error}")
                
                return True
            else:
                error = close_result.get('error', 'Unknown error') if close_result else 'No response'
                error_msg = close_result.get('message', error) if close_result else error
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ НЕ УДАЛОСЬ закрыть позицию на бирже!")
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка: {error_msg}")
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Полный ответ: {close_result}")
                return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ КРИТИЧЕСКАЯ ОШИБКА при закрытии позиции: {e}")
            import traceback
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Traceback: {traceback.format_exc()}")
            return False
    
    def emergency_close_delisting(self):
        """Экстренное закрытие позиции при делистинге - рыночным ордером по любой цене"""
        try:
            if not self.exchange:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Биржа не инициализирована для экстренного закрытия")
                return False
            
            if self.status not in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
                logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Бот не в позиции, экстренное закрытие не требуется")
                return True
            
            logger.warning(f"[NEW_BOT_{self.symbol}] 🚨 ЭКСТРЕННОЕ ЗАКРЫТИЕ: ДЕЛИСТИНГ ОБНАРУЖЕН! Закрываем {self.position_side} рыночным ордером")
            
            # Получаем размер позиции
            position_size = None
            if self.position_size:
                position_size = self.position_size
            else:
                # Получаем размер позиции с биржи
                try:
                    positions = self.exchange.get_positions()
                    if isinstance(positions, tuple):
                        positions_list = positions[0] if positions else []
                    else:
                        positions_list = positions if positions else []
                    
                    for pos in positions_list:
                        if pos.get('symbol', '').replace('USDT', '') == self.symbol:
                            pos_side = 'Long' if pos.get('side') == 'Buy' else 'Short'
                            expected_side = 'Long' if self.position_side == 'LONG' else 'Short' if self.position_side == 'SHORT' else self.position_side
                            if pos_side == expected_side and abs(float(pos.get('size', 0))) > 0:
                                position_size = abs(float(pos.get('size', 0)))
                                break
                except Exception as e:
                    logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка получения размера позиции: {e}")
            
            if not position_size:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось определить размер позиции для экстренного закрытия")
                return False
            
            # Преобразуем side в формат биржи
            side_for_exchange = 'Long' if self.position_side == 'LONG' else 'Short' if self.position_side == 'SHORT' else self.position_side
            
            # Экстренное закрытие рыночным ордером
            emergency_result = self.exchange.close_position(
                symbol=self.symbol,
                size=position_size,
                side=side_for_exchange,
                order_type='Market'  # Принудительно рыночный ордер
            )
            
            if emergency_result and emergency_result.get('success'):
                logger.warning(f"[NEW_BOT_{self.symbol}] ✅ ЭКСТРЕННОЕ ЗАКРЫТИЕ УСПЕШНО: Позиция закрыта рыночным ордером")
                self.update_status(BOT_STATUS['IDLE'])
                
                # Дополнительно обнуляем все данные позиции
                self.position_side = None
                self.entry_price = None
                self.unrealized_pnl = 0.0
                self.max_profit_achieved = 0.0
                self.trailing_stop_price = None
                self.break_even_activated = False
                self.trailing_active = False
                self.trailing_activation_profit = 0.0
                self.trailing_activation_threshold = 0.0
                self.trailing_locked_profit = 0.0
                self.trailing_max_profit_usdt = 0.0
                self.trailing_step_usdt = 0.0
                self.trailing_step_price = 0.0
                self.trailing_steps = 0
                self.break_even_stop_price = None
                
                return True
            else:
                error = emergency_result.get('error', 'Unknown error') if emergency_result else 'No response'
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ ЭКСТРЕННОЕ ЗАКРЫТИЕ НЕУДАЧНО: {error}")
                return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ КРИТИЧЕСКАЯ ОШИБКА ЭКСТРЕННОГО ЗАКРЫТИЯ: {e}")
            return False
    
    def calculate_dynamic_take_profit(self, side, actual_entry_price, actual_leverage, actual_qty, tp_percent=None):
        """
        Рассчитывает Take Profit от маржи с учетом плеча
        
        Args:
            side (str): Направление позиции ('LONG' или 'SHORT')
            actual_entry_price (float): Реальная цена входа
            actual_leverage (float): Реальное плечо
            actual_qty (float): Реальное количество монет
            tp_percent (float, optional): TP процент от маржи. Если не указан, берется из конфига.
            
        Returns:
            float: Цена Take Profit
        """
        try:
            # Если tp_percent не указан, получаем из конфига (по умолчанию 100%)
            if tp_percent is None:
                auto_bot_config = get_auto_bot_config()
                tp_percent = auto_bot_config.get('take_profit_percent', 100.0)
            
            # Рассчитываем маржу и прибыль
            position_value = abs(actual_qty) * actual_entry_price if actual_qty else self.volume_value
            margin = position_value / actual_leverage
            target_profit_usdt = margin * (tp_percent / 100)
            
            # Рассчитываем прибыль на монету
            profit_per_coin = target_profit_usdt / abs(actual_qty) if actual_qty and abs(actual_qty) > 0 else (target_profit_usdt / (self.volume_value / actual_entry_price))
            
            logger.info(f"[NEW_BOT_{self.symbol}] 🎯 TP CALC: side={side}, entry={actual_entry_price}, leverage={actual_leverage}x, margin={margin:.4f} USDT, target_profit={target_profit_usdt:.4f} USDT (+{tp_percent}%)")
            
            if side == 'LONG':
                # Для LONG: TP выше
                tp_price = actual_entry_price + profit_per_coin
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ TP для LONG: {actual_entry_price:.6f} → {tp_price:.6f} (+{tp_percent}% от маржи)")
                return tp_price
                
            elif side == 'SHORT':
                # Для SHORT: TP ниже
                tp_price = actual_entry_price - profit_per_coin
                logger.info(f"[NEW_BOT_{self.symbol}] 📉 TP для SHORT: {actual_entry_price:.6f} → {tp_price:.6f} (+{tp_percent}% от маржи)")
                return tp_price
            
            return None
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка расчета TP: {e}")
            return None
    
    def _log_position_closed(self, reason, close_result):
        """Сохраняет детальные данные о закрытии позиции (для обучения ИИ)"""
        try:
            from bot_engine.bot_history import bot_history_manager
            from bot_engine.ai import check_premium_license
            
            # Получаем данные о закрытии
            exit_price = close_result.get('price', self.entry_price) if close_result else self.entry_price
            pnl = close_result.get('realized_pnl', self.unrealized_pnl) if close_result else self.unrealized_pnl
            pnl_pct = close_result.get('roi', 0) if close_result else 0
            
            # Подготавливаем данные для обучения ИИ (только если стоп И есть лицензия)
            entry_data = None
            market_data = None
            
            if 'STOP' in reason.upper():
                try:
                    is_premium = check_premium_license()
                    
                    if is_premium:
                        # Получаем входные данные для обучения ИИ
                        entry_data = {
                            'entry_price': self.entry_price,
                            'volatility': getattr(self, 'entry_volatility', None),
                            'trend': getattr(self, 'entry_trend', None),
                            'duration_hours': (self.position_start_time and 
                                             (datetime.now() - self.position_start_time).total_seconds() / 3600) if self.position_start_time else 0,
                            'max_profit_achieved': self.max_profit_achieved
                        }
                        
                        # Получаем рыночные данные при выходе
                        market_data = {
                            'exit_price': exit_price,
                            'volatility': None,  # TODO: Получить текущую волатильность
                            'trend': None,  # TODO: Получить текущий тренд
                            'price_movement': ((exit_price - self.entry_price) / self.entry_price * 100) if self.entry_price else 0
                        }
                except Exception as e:
                    logger.debug(f"[NEW_BOT_{self.symbol}] Лицензия проверка не удалась: {e}")
                    entry_data = None
                    market_data = None
            
            # Сохраняем в историю
            bot_history_manager.log_position_closed(
                bot_id=self.symbol,
                symbol=self.symbol,
                direction=self.position_side,
                exit_price=exit_price,
                pnl=pnl,
                roi=pnl_pct,
                reason=reason,
                entry_data=entry_data,
                market_data=market_data
            )
            
            # ВАЖНО: Обновляем результат решения AI для переобучения
            if hasattr(self, 'ai_decision_id') and self.ai_decision_id:
                try:
                    from bot_engine.ai.ai_integration import update_ai_decision_result
                    is_successful = pnl > 0
                    update_ai_decision_result(self.ai_decision_id, pnl, pnl_pct, is_successful)
                    logger.debug(f"[NEW_BOT_{self.symbol}] 📝 Обновлен результат решения AI: {'SUCCESS' if is_successful else 'FAILED'}")
                except Exception as ai_track_error:
                    logger.debug(f"[NEW_BOT_{self.symbol}] ⚠️ Ошибка обновления решения AI: {ai_track_error}")
            
        except Exception as e:
            logger.debug(f"[NEW_BOT_{self.symbol}] Не удалось сохранить историю: {e}")
    
    def _evaluate_ai_prediction(self, reason, close_result):
        """Оценивает предсказание ИИ и сохраняет для обучения"""
        try:
            from bot_engine.ai.smart_risk_manager import SmartRiskManager
            from bot_engine.bot_history import bot_history_manager
            
            # Получаем данные о реальном результате
            exit_price = close_result.get('price', self.entry_price) if close_result else self.entry_price
            pnl = close_result.get('realized_pnl', self.unrealized_pnl) if close_result else self.unrealized_pnl
            pnl_pct = close_result.get('roi', 0) if close_result else 0
            
            actual_outcome = {
                'entry_price': self.entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'roi': pnl_pct,
                'reason': reason
            }
            
            # Оцениваем предсказание
            smart_risk = SmartRiskManager()
            evaluation = smart_risk.evaluate_prediction(
                self.symbol,
                self._last_backtest_result,
                actual_outcome
            )
            
            logger.info(f"[NEW_BOT_{self.symbol}] 🎓 ИИ оценен: score={evaluation.get('score', 0):.2f}")
            
        except Exception as e:
            logger.debug(f"[NEW_BOT_{self.symbol}] Не удалось оценить ИИ: {e}")
    
    def to_dict(self):
        """Преобразует бота в словарь для сохранения"""
        # Получаем дополнительные данные из конфига если есть
        bot_id = self.config.get('id', f"{self.symbol}_{int(datetime.now().timestamp())}")
        
        return {
            'id': bot_id,
            'symbol': self.symbol,
            'status': self.status,
            'auto_managed': self.config.get('auto_managed', False),
            'volume_mode': self.volume_mode,
            'volume_value': self.volume_value,
            'position': None,  # Для совместимости
            'entry_price': self.entry_price,
            'entry_time': self.position_start_time.isoformat() if self.position_start_time else None,
            'position_side': self.position_side,
            'position_size': self.position_size,  # ✅ Размер позиции в монетах
            'position_size_coins': self.position_size_coins,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_usdt': self.unrealized_pnl_usdt,
            'realized_pnl': self.realized_pnl,
            'leverage': self.leverage,
            'margin_usdt': self.margin_usdt,
            'created_at': self.created_at,
            'last_signal_time': self.last_signal_time,
            'last_bar_timestamp': None,  # Для совместимости
            'max_profit_achieved': self.max_profit_achieved,
            'trailing_stop_price': self.trailing_stop_price,
            'trailing_activation_threshold': self.trailing_activation_threshold,
            'trailing_activation_profit': self.trailing_activation_profit,
            'trailing_locked_profit': self.trailing_locked_profit,
            'trailing_active': self.trailing_active,
            'trailing_max_profit_usdt': self.trailing_max_profit_usdt,
            'trailing_step_usdt': self.trailing_step_usdt,
            'trailing_step_price': self.trailing_step_price,
            'trailing_steps': self.trailing_steps,
            'trailing_take_profit_price': self.trailing_take_profit_price,
            'break_even_activated': self.break_even_activated,
            'break_even_stop_price': self.break_even_stop_price,
            'position_start_time': self.position_start_time.isoformat() if self.position_start_time else None,
            'order_id': self.order_id,
            'entry_timestamp': self.entry_timestamp,
            'opened_by_autobot': self.opened_by_autobot,
            'entry_trend': self.entry_trend,  # ✅ Сохраняем тренд при входе
            'scaling_enabled': False,  # Для совместимости
            'scaling_levels': [],  # Для совместимости
            'scaling_current_level': 0,  # Для совместимости
            'scaling_group_id': None,  # Для совместимости
            # Добавляем стопы и тейки если они есть
            'stop_loss': getattr(self, 'stop_loss', None) or self.config.get('stop_loss'),
            'take_profit': getattr(self, 'take_profit', None) or self.config.get('take_profit'),
            'current_price': getattr(self, 'current_price', None) or self.config.get('current_price')
        }

