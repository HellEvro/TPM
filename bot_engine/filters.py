"""
Торговые фильтры для защиты от плохих входов
- RSI временной фильтр
- ExitScam фильтр (защита от памп/дамп)
"""

import logging

from .utils.rsi_utils import calculate_rsi_history

logger = logging.getLogger('Filters')


def check_rsi_time_filter(candles, rsi, signal, config, calculate_rsi_history_func=None):
    """
    ГИБРИДНЫЙ ВРЕМЕННОЙ ФИЛЬТР RSI
    
    Проверяет что:
    1. Последние N свечей находятся в "спокойной зоне"
    2. Перед этой зоной был экстремум
    3. С момента экстремума прошло минимум N свечей
    
    Args:
        candles: Список свечей
        rsi: Текущее значение RSI
        signal: Торговый сигнал ('ENTER_LONG' или 'ENTER_SHORT')
        config: Конфигурация фильтра
        calculate_rsi_history_func: Функция для расчета RSI истории (опционально)
    
    Returns:
        dict: {'allowed': bool, 'reason': str, 'last_extreme_candles_ago': int, 'calm_candles': int}
    """
    try:
        # Используем переданную функцию или импортированную
        calc_rsi_hist = calculate_rsi_history_func or calculate_rsi_history
        
        # Получаем настройки из конфига
        rsi_time_filter_enabled = config.get('rsi_time_filter_enabled', True)
        rsi_time_filter_candles = config.get('rsi_time_filter_candles', 8)
        rsi_time_filter_upper = config.get('rsi_time_filter_upper', 65)
        rsi_time_filter_lower = config.get('rsi_time_filter_lower', 35)
        rsi_long_threshold = config.get('rsi_long_threshold', 29)
        rsi_short_threshold = config.get('rsi_short_threshold', 71)
        
        # Если фильтр отключен
        if not rsi_time_filter_enabled:
            return {'allowed': True, 'reason': 'RSI временной фильтр отключен', 'last_extreme_candles_ago': None, 'calm_candles': None}
        
        if len(candles) < 50:
            return {'allowed': False, 'reason': 'Недостаточно свечей для анализа', 'last_extreme_candles_ago': None, 'calm_candles': 0}
        
        # Рассчитываем историю RSI
        closes = [candle['close'] for candle in candles]
        rsi_history = calc_rsi_hist(closes, 14)
        
        min_rsi_history = max(rsi_time_filter_candles * 2 + 14, 30)
        if not rsi_history or len(rsi_history) < min_rsi_history:
            return {'allowed': False, 'reason': f'Недостаточно RSI истории (требуется {min_rsi_history})', 'last_extreme_candles_ago': None, 'calm_candles': 0}
        
        current_index = len(rsi_history) - 1
        
        # Обновляем последний элемент истории переданным RSI, если он указан
        # Это важно для согласованности данных, так как переданный RSI может быть более актуальным
        if rsi is not None:
            rsi_history[current_index] = rsi
        
        if signal == 'ENTER_SHORT':
            # Проверяем, что текущая свеча действительно в зоне входа для SHORT
            current_rsi = rsi_history[current_index]
            if current_rsi < rsi_short_threshold:
                return {
                    'allowed': False,
                    'reason': f'Блокировка: текущий RSI {current_rsi:.1f} < {rsi_short_threshold} (не в зоне входа)',
                    'last_extreme_candles_ago': None,
                    'calm_candles': 0
                }
            
            # Логика для SHORT
            last_n_candles_start = max(0, current_index - rsi_time_filter_candles + 1)
            last_n_candles = rsi_history[last_n_candles_start:current_index + 1]
            
            # Ищем пики (>= 71) в последних N свечах
            peak_index = None
            for i in range(last_n_candles_start, current_index + 1):
                if rsi_history[i] >= rsi_short_threshold:
                    peak_index = i
                    break
            
            # Если не нашли пик в последних N - ищем дальше
            if peak_index is None:
                for i in range(last_n_candles_start - 1, -1, -1):
                    if rsi_history[i] >= rsi_short_threshold:
                        peak_index = i
                        break
            
            if peak_index is None:
                return {
                    'allowed': True,
                    'reason': f'Разрешено: пик RSI >= {rsi_short_threshold} не найден во всей истории',
                    'last_extreme_candles_ago': None,
                    'calm_candles': len(last_n_candles)
                }
            
            candles_since_peak = current_index - peak_index + 1
            start_check = peak_index + 1
            check_candles = rsi_history[start_check:current_index + 1]
            
            invalid_candles = [rsi_val for rsi_val in check_candles if rsi_val < rsi_time_filter_upper]
            
            if len(invalid_candles) > 0:
                return {
                    'allowed': False,
                    'reason': f'Блокировка: {len(invalid_candles)} свечей после пика провалились < {rsi_time_filter_upper}',
                    'last_extreme_candles_ago': candles_since_peak,
                    'calm_candles': len(check_candles) - len(invalid_candles)
                }
            
            if len(check_candles) < rsi_time_filter_candles:
                return {
                    'allowed': False,
                    'reason': f'Блокировка: с пика прошло только {len(check_candles)} свечей (требуется {rsi_time_filter_candles})',
                    'last_extreme_candles_ago': candles_since_peak,
                    'calm_candles': len(check_candles)
                }
            
            return {
                'allowed': True,
                'reason': f'Разрешено: с пика (свеча -{candles_since_peak}) прошло {len(check_candles)} спокойных свечей >= {rsi_time_filter_upper}',
                'last_extreme_candles_ago': candles_since_peak - 1,
                'calm_candles': len(check_candles)
            }
                
        elif signal == 'ENTER_LONG':
            # Проверяем, что текущая свеча действительно в зоне входа
            # RSI уже обновлен в начале функции из переданного параметра
            current_rsi = rsi_history[current_index]
            
            if current_rsi > rsi_long_threshold:
                return {
                    'allowed': False,
                    'reason': f'Блокировка: текущий RSI {current_rsi:.1f} > {rsi_long_threshold} (не в зоне входа)',
                    'last_extreme_candles_ago': None,
                    'calm_candles': 0
                }
            
            # Расширенный диапазон для поиска лоя (в 2 раза больше, чтобы поймать недавние лои)
            search_range = rsi_time_filter_candles * 2
            search_start = max(0, current_index - search_range + 1)
            max_search_back = min(current_index, 100)  # Максимум 100 свечей назад
            
            # Ищем последний лой в расширенном диапазоне
            low_index = None
            for i in range(current_index, search_start - 1, -1):
                if rsi_history[i] <= rsi_long_threshold:
                    low_index = i
                    break
            
            # Если лой не найден в расширенном диапазоне, ищем дальше, но ограничиваем поиск
            if low_index is None:
                for i in range(search_start - 1, max(0, current_index - max_search_back), -1):
                    if rsi_history[i] <= rsi_long_threshold:
                        low_index = i
                        break
            
            if low_index is None:
                return {
                    'allowed': True,
                    'reason': f'Разрешено: лой RSI <= {rsi_long_threshold} не найден в последних {max_search_back} свечах',
                    'last_extreme_candles_ago': None,
                    'calm_candles': 0
                }
            
            # Проверяем свечи после найденного лоя
            candles_since_low = current_index - low_index + 1
            start_check = low_index + 1
            check_candles = rsi_history[start_check:current_index + 1]
            
            # Если после лоя не было свечей, это значит текущая свеча и есть лой
            if len(check_candles) == 0:
                return {
                    'allowed': True,
                    'reason': f'Разрешено: текущая свеча является лоем (RSI {current_rsi:.1f} <= {rsi_long_threshold})',
                    'last_extreme_candles_ago': 0,
                    'calm_candles': 0
                }
            
            # Проверяем, что после лоя все свечи остались в зоне спокойствия (<= 35)
            invalid_candles = [rsi_val for rsi_val in check_candles if rsi_val > rsi_time_filter_lower]
            
            if len(invalid_candles) > 0:
                # Если после лоя были свечи > 35, проверяем, не был ли вход упущен
                # Но если текущая свеча снова в зоне входа, ищем новый лой после последнего превышения
                
                # Находим индекс последней свечи, которая превысила порог
                last_break_index = None
                for i in range(current_index, low_index, -1):
                    if rsi_history[i] > rsi_time_filter_lower:
                        last_break_index = i
                        break
                
                # Если после последнего превышения есть новый лой, используем его
                if last_break_index is not None:
                    new_low_index = None
                    for i in range(current_index, last_break_index, -1):
                        if rsi_history[i] <= rsi_long_threshold:
                            new_low_index = i
                            break
                    
                    if new_low_index is not None:
                        # Нашли новый лой после превышения - проверяем свечи после него
                        new_check_candles = rsi_history[new_low_index + 1:current_index + 1]
                        new_invalid = [rsi_val for rsi_val in new_check_candles if rsi_val > rsi_time_filter_lower]
                        
                        if len(new_invalid) == 0 and len(new_check_candles) >= rsi_time_filter_candles:
                            # Новый лой валиден - разрешаем вход
                            new_candles_since_low = current_index - new_low_index + 1
                            return {
                                'allowed': True,
                                'reason': f'Разрешено: после превышения найден новый лой (свеча -{new_candles_since_low}), прошло {len(new_check_candles)} спокойных свечей',
                                'last_extreme_candles_ago': new_candles_since_low - 1,
                                'calm_candles': len(new_check_candles)
                            }
                
                # Вход был упущен - после старого лоя цена поднялась выше 35
                return {
                    'allowed': False,
                    'reason': f'Блокировка: {len(invalid_candles)} свечей после лоя (свеча -{candles_since_low}) поднялись > {rsi_time_filter_lower} (вход упущен)',
                    'last_extreme_candles_ago': candles_since_low,
                    'calm_candles': len(check_candles) - len(invalid_candles)
                }
            
            # Проверяем, что прошло достаточно свечей после лоя
            if len(check_candles) < rsi_time_filter_candles:
                return {
                    'allowed': False,
                    'reason': f'Блокировка: с лоя прошло только {len(check_candles)} свечей (требуется {rsi_time_filter_candles})',
                    'last_extreme_candles_ago': candles_since_low,
                    'calm_candles': len(check_candles)
                }
            
            return {
                'allowed': True,
                'reason': f'Разрешено: с лоя (свеча -{candles_since_low}) прошло {len(check_candles)} спокойных свечей <= {rsi_time_filter_lower}',
                'last_extreme_candles_ago': candles_since_low - 1,
                'calm_candles': len(check_candles)
            }
        
        return {'allowed': True, 'reason': 'Неизвестный сигнал', 'last_extreme_candles_ago': None, 'calm_candles': 0}
    
    except Exception as e:
        logger.error(f"[RSI_TIME_FILTER] Ошибка проверки временного фильтра: {e}")
        return {'allowed': False, 'reason': f'Ошибка анализа: {str(e)}', 'last_extreme_candles_ago': None, 'calm_candles': 0}


def check_exit_scam_filter(symbol, coin_data, config, exchange_obj, ensure_exchange_func):
    """
    EXIT SCAM ФИЛЬТР
    
    Защита от резких движений цены (памп/дамп/скам):
    1. Одна свеча превысила максимальный % изменения
    2. N свечей суммарно превысили максимальный % изменения
    
    Args:
        symbol: Символ монеты
        coin_data: Данные монеты (не используется пока)
        config: Конфигурация фильтра
        exchange_obj: Объект биржи
        ensure_exchange_func: Функция проверки инициализации биржи
    """
    try:
        # Получаем настройки из конфига
        exit_scam_enabled = config.get('exit_scam_enabled', True)
        exit_scam_candles = config.get('exit_scam_candles', 10)
        single_candle_percent = config.get('exit_scam_single_candle_percent', 15.0)
        multi_candle_count = config.get('exit_scam_multi_candle_count', 4)
        multi_candle_percent = config.get('exit_scam_multi_candle_percent', 50.0)
        
        # Если фильтр отключен
        if not exit_scam_enabled:
            logger.debug(f"[EXIT_SCAM] {symbol}: Фильтр отключен")
            return True
        
        # Проверяем биржу
        if not ensure_exchange_func():
            return False
        
        chart_response = exchange_obj.get_chart_data(symbol, '6h', '30d')
        if not chart_response or not chart_response.get('success'):
            return False
        
        candles = chart_response.get('data', {}).get('candles', [])
        if len(candles) < exit_scam_candles:
            return False
        
        # Проверяем последние N свечей
        recent_candles = candles[-exit_scam_candles:]
        
        logger.info(f"[EXIT_SCAM] {symbol}: Анализ последних {exit_scam_candles} свечей")
        logger.info(f"[EXIT_SCAM] {symbol}: Настройки - одна свеча: {single_candle_percent}%, {multi_candle_count} свечей: {multi_candle_percent}%")
        
        # 1. Проверка отдельных свечей
        for i, candle in enumerate(recent_candles):
            open_price = candle['open']
            close_price = candle['close']
            
            price_change = abs((close_price - open_price) / open_price) * 100
            
            if price_change > single_candle_percent:
                logger.warning(f"[EXIT_SCAM] {symbol}: ❌ БЛОКИРОВКА: Свеча #{i+1} превысила лимит {single_candle_percent}% (было {price_change:.1f}%)")
                logger.info(f"[EXIT_SCAM] {symbol}: Свеча: O={open_price:.4f} C={close_price:.4f} H={candle['high']:.4f} L={candle['low']:.4f}")
                return False
        
        # 2. Проверка суммарного изменения
        if len(recent_candles) >= multi_candle_count:
            multi_candles = recent_candles[-multi_candle_count:]
            
            first_open = multi_candles[0]['open']
            last_close = multi_candles[-1]['close']
            
            total_change = abs((last_close - first_open) / first_open) * 100
            
            if total_change > multi_candle_percent:
                logger.warning(f"[EXIT_SCAM] {symbol}: ❌ БЛОКИРОВКА: {multi_candle_count} свечей превысили суммарный лимит {multi_candle_percent}% (было {total_change:.1f}%)")
                logger.info(f"[EXIT_SCAM] {symbol}: Первая свеча: {first_open:.4f}, Последняя свеча: {last_close:.4f}")
                return False
        
        logger.info(f"[EXIT_SCAM] {symbol}: ✅ РЕЗУЛЬТАТ: ПРОЙДЕН")
        return True
        
    except Exception as e:
        logger.error(f"[EXIT_SCAM] {symbol}: Ошибка проверки: {e}")
        return False


def check_no_existing_position(symbol, signal, exchange_obj, ensure_exchange_func):
    """Проверяет, что нет существующих позиций на бирже"""
    try:
        if not ensure_exchange_func():
            return False
        
        exchange_positions = exchange_obj.get_positions()
        if isinstance(exchange_positions, tuple):
            positions_list = exchange_positions[0] if exchange_positions else []
        else:
            positions_list = exchange_positions if exchange_positions else []
        
        expected_side = 'LONG' if signal == 'ENTER_LONG' else 'SHORT'
        
        # Проверяем, есть ли позиция той же стороны
        for pos in positions_list:
            if pos.get('symbol') == symbol and abs(float(pos.get('size', 0))) > 0:
                existing_side = pos.get('side', 'UNKNOWN')
                if existing_side == expected_side:
                    logger.debug(f"[POSITION_CHECK] {symbol}: Уже есть позиция {existing_side}")
                    return False
        
        return True
        
    except Exception as e:
        logger.error(f"[POSITION_CHECK] {symbol}: Ошибка проверки позиций: {e}")
        return False

