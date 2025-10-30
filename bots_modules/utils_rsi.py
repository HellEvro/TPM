"""
Утилиты для расчета RSI с учетом закрытых свечей
"""
import time
from datetime import datetime, timedelta

def get_timeframe_seconds(timeframe):
    """Преобразует таймфрейм в секунды"""
    timeframe_map = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '4h': 14400,
        '6h': 21600,
        '12h': 43200,
        '1d': 86400,
        '1w': 604800,
        '1M': 2592000
    }
    return timeframe_map.get(timeframe, 3600)  # По умолчанию 1 час

def is_candle_closed(candle_time, timeframe, current_time=None):
    """Проверяет, закрыта ли свеча
    
    Args:
        candle_time: Время открытия свечи (timestamp в миллисекундах)
        timeframe: Таймфрейм свечи
        current_time: Текущее время (timestamp в секундах), если None - используется текущее время
    
    Returns:
        bool: True если свеча закрыта, False если еще открыта
    """
    if current_time is None:
        current_time = int(time.time())
    else:
        current_time = int(current_time)
    
    # Преобразуем время свечи из миллисекунд в секунды
    candle_time_sec = int(candle_time / 1000) if candle_time > 1000000000000 else int(candle_time)
    
    # Получаем длительность таймфрейма в секундах
    timeframe_sec = get_timeframe_seconds(timeframe)
    
    # Время закрытия свечи = время открытия + длительность таймфрейма
    candle_close_time = candle_time_sec + timeframe_sec
    
    # Свеча закрыта если текущее время >= времени закрытия
    return current_time >= candle_close_time

def filter_closed_candles(candles, timeframe):
    """Фильтрует только закрытые свечи
    
    Args:
        candles: Список свечей
        timeframe: Таймфрейм свечей
    
    Returns:
        list: Список только закрытых свечей
    """
    if not candles:
        return []
    
    closed_candles = []
    for candle in candles:
        candle_time = candle.get('time', 0)
        if is_candle_closed(candle_time, timeframe):
            closed_candles.append(candle)
    
    return closed_candles

def get_closes_for_rsi(candles, timeframe):
    """Получает массив цен закрытия только для закрытых свечей для расчета RSI
    
    Args:
        candles: Список свечей (отсортированные от старых к новым)
        timeframe: Таймфрейм свечей
    
    Returns:
        list: Массив цен закрытия закрытых свечей
    """
    closed_candles = filter_closed_candles(candles, timeframe)
    return [candle['close'] for candle in closed_candles]

