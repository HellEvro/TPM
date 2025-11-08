"""
RSI (Relative Strength Index) и EMA (Exponential Moving Average) расчеты
Wilder's RSI алгоритм
"""

def calculate_rsi(prices, period=14):
    """Рассчитывает RSI на основе массива цен (Wilder's RSI алгоритм)"""
    if len(prices) < period + 1:
        return None
    
    # Рассчитываем изменения цен
    changes = []
    for i in range(1, len(prices)):
        changes.append(prices[i] - prices[i-1])
    
    if len(changes) < period:
        return None
    
    # Разделяем на прибыли и убытки
    gains = []
    losses = []
    
    for change in changes:
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0) 
            losses.append(-change)
    
    # Первоначальные средние значения (простое среднее для первого периода)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Рассчитываем RSI используя сглаживание Wilder's
    # (это тип экспоненциального сглаживания)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    # Избегаем деления на ноль
    if avg_loss == 0:
        return 100.0
    
    # Рассчитываем RS и RSI
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    return round(rsi, 2)


def calculate_rsi_history(prices, period=14):
    """Рассчитывает полную историю RSI для анализа зрелости монеты"""
    if len(prices) < period + 1:
        return None
    
    # Рассчитываем изменения цен
    changes = []
    for i in range(1, len(prices)):
        changes.append(prices[i] - prices[i-1])
    
    if len(changes) < period:
        return None
    
    # Разделяем на прибыли и убытки
    gains = []
    losses = []
    
    for change in changes:
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0) 
            losses.append(-change)
    
    # Первоначальные средние значения
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Рассчитываем полную историю RSI
    rsi_history = []
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        rsi_history.append(round(rsi, 2))
    
    return rsi_history


def calculate_ema(prices, period, return_list=False):
    """
    Рассчитывает EMA для массива цен
    
    Args:
        prices: Список цен закрытия
        period: Период EMA
        return_list: Если True, возвращает список всех значений EMA, иначе только последнее значение
    
    Returns:
        Если return_list=False: последнее значение EMA или None если недостаточно данных
        Если return_list=True: список значений EMA или None если недостаточно данных
    """
    if len(prices) < period:
        return None if not return_list else []
    
    # Первое значение EMA = SMA
    sma = sum(prices[:period]) / period
    ema = sma
    multiplier = 2 / (period + 1)
    
    if return_list:
        # Возвращаем список значений EMA
        ema_values = []
        # Добавляем None для первых period-1 значений (где EMA еще не определен)
        ema_values.extend([None] * (period - 1))
        ema_values.append(ema)
        
        # Рассчитываем EMA для остальных значений
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
            ema_values.append(ema)
        
        return ema_values
    else:
        # Возвращаем только последнее значение EMA
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema

