"""
Модуль для управления кэшем свечей
Использует отдельные JSON файлы для каждой монеты
"""

import json
import os
import logging
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)

# Директории для кэша свечей (по таймфреймам)
CANDLES_CACHE_DIR = 'data/candles_cache'
_cache_lock = Lock()

# Создаем базовую директорию при импорте
os.makedirs(CANDLES_CACHE_DIR, exist_ok=True)

def get_cache_dir(timeframe):
    """Возвращает директорию для кэша таймфрейма"""
    return os.path.join(CANDLES_CACHE_DIR, timeframe)

def get_candle_file(symbol, timeframe):
    """Возвращает путь к файлу свечей для конкретной монеты"""
    return os.path.join(get_cache_dir(timeframe), f'{symbol}.json')

def init_candles_db():
    """Создает директории для каждого таймфрейма"""
    try:
        timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '6h', '1d', '1w']
        
        for tf in timeframes:
            cache_dir = get_cache_dir(tf)
            os.makedirs(cache_dir, exist_ok=True)
            logger.debug(f"[CANDLES_DB] ✅ Создана директория: {cache_dir}")
        
        logger.info(f"[CANDLES_DB] ✅ Кэш инициализирован: {CANDLES_CACHE_DIR}")
        return True
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка инициализации: {e}")
        return False

def save_candles(symbol, timeframe, candles, update_mode='replace'):
    """Сохраняет свечи в отдельный файл для монеты
    
    Args:
        symbol: Символ монеты
        timeframe: Таймфрейм
        candles: Список свечей для сохранения
        update_mode: 'replace' - заменить все, 'append' - добавить новые (по времени)
    """
    try:
        with _cache_lock:
            candle_file = get_candle_file(symbol, timeframe)
            
            # Создаем директорию если её нет
            os.makedirs(os.path.dirname(candle_file), exist_ok=True)
            
            # Если режим обновления - читаем существующие свечи и объединяем
            if update_mode == 'append' and os.path.exists(candle_file):
                try:
                    with open(candle_file, 'r', encoding='utf-8') as f:
                        old_data = json.load(f)
                    old_candles = old_data.get('candles', [])
                    
                    # Если старые свечи есть - мержим
                    if old_candles:
                        # Создаем словарь по времени для быстрого поиска
                        old_times = {c['time']: c for c in old_candles}
                        new_times = {c['time']: c for c in candles}
                        
                        # Объединяем, новые перезаписывают старые
                        merged_times = {**old_times, **new_times}
                        candles = sorted(merged_times.values(), key=lambda x: x['time'])
                        
                        # Находим новые свечи (которых не было в старом файле)
                        new_count = len(set(new_times.keys()) - set(old_times.keys()))
                        updated_count = len(new_times) - new_count
                        
                        logger.debug(f"[CANDLES_DB] 🔄 {symbol}: +{new_count} новых, обновлено {updated_count}, всего {len(candles)}")
                except Exception as e:
                    logger.warning(f"[CANDLES_DB] ⚠️ Ошибка чтения старых свечей для {symbol}: {e}")
            
            # Сохраняем данные с метаданными
            data = {
                'symbol': symbol,
                'timeframe': timeframe,
                'candles': candles,
                'count': len(candles),
                'last_update': datetime.now().isoformat()
            }
            
            with open(candle_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"[CANDLES_DB] 💾 Сохранено: {symbol} ({timeframe}): {len(candles)} свечей")
            return True
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка сохранения {symbol}: {e}")
        return False

def save_candles_batch(timeframe, all_candles_dict, update_mode='replace'):
    """ПАКЕТНАЯ запись - сохраняет ВСЕ символы по отдельности"""
    try:
        saved = 0
        for symbol, candles in all_candles_dict.items():
            if save_candles(symbol, timeframe, candles, update_mode=update_mode):
                saved += 1
        
        logger.info(f"[CANDLES_DB] 💾💾 ПАКЕТНО сохранено: {saved}/{len(all_candles_dict)} символов ({timeframe})")
        return True
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка пакетного сохранения: {e}")
        return False

def get_candles(symbol, timeframe):
    """Читает свечи из файла монеты"""
    try:
        with _cache_lock:
            candle_file = get_candle_file(symbol, timeframe)
            
            if not os.path.exists(candle_file):
                logger.error(f"[CANDLES_DB] ❌ {symbol}: Файл НЕ существует: {candle_file}")
                return None
            
            with open(candle_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            candles = data.get('candles', [])
            if candles:
                logger.debug(f"[CANDLES_DB] 📖 {symbol}: {len(candles)} свечей")
            else:
                logger.warning(f"[CANDLES_DB] ⚠️ {symbol}: Пустой файл!")
            return candles
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка чтения {symbol}: {e}")
        return None

def get_all_candles(timeframe):
    """Получает все свечи для указанного таймфрейма - читает все файлы в директории"""
    try:
        cache_dir = get_cache_dir(timeframe)
        
        if not os.path.exists(cache_dir):
            return {}
        
        result = {}
        files = os.listdir(cache_dir)
        
        for filename in files:
            if filename.endswith('.json'):
                symbol = filename[:-5]  # Убираем .json
                candle_file = os.path.join(cache_dir, filename)
                
                try:
                    with open(candle_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    candles = data.get('candles', [])
                    result[symbol] = candles
                except Exception as e:
                    logger.error(f"[CANDLES_DB] ⚠️ Ошибка чтения {symbol}: {e}")
        
        logger.info(f"[CANDLES_DB] 📊 Загружено {len(result)} монет для {timeframe}")
        return result
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка чтения всех свечей: {e}")
        return {}

def clear_timeframe_cache(timeframe):
    """Очищает кэш для указанного таймфрейма - удаляет все файлы"""
    try:
        import shutil
        cache_dir = get_cache_dir(timeframe)
        
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"[CANDLES_DB] 🗑️ Очищен кэш для {timeframe}")
            return 1
        
        return 0
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка очистки: {e}")
        return 0

def get_cached_symbols_count(timeframe):
    """Возвращает количество уникальных монет для таймфрейма - считает файлы в директории"""
    try:
        cache_dir = get_cache_dir(timeframe)
        
        if not os.path.exists(cache_dir):
            return 0
        
        files = os.listdir(cache_dir)
        count = len([f for f in files if f.endswith('.json')])
        return count
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка подсчета: {e}")
        return 0

