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

def save_candles(symbol, timeframe, candles, update_mode='replace', rsi_value=None):
    """Сохраняет свечи в отдельный файл для монеты
    
    Args:
        symbol: Символ монеты
        timeframe: Таймфрейм
        candles: Список свечей для сохранения
        update_mode: 'replace' - заменить все, 'append' - добавить новые (по времени)
        rsi_value: Текущее значение RSI (опционально, сохраняется в файл для быстрого доступа)
    """
    try:
        with _cache_lock:
            candle_file = get_candle_file(symbol, timeframe)
            
            # Создаем директорию если её нет
            os.makedirs(os.path.dirname(candle_file), exist_ok=True)
            
            # Если режим обновления - читаем существующие свечи и объединяем
            old_rsi = None  # Сохраняем старый RSI если он был
            if update_mode == 'append' and os.path.exists(candle_file):
                try:
                    with open(candle_file, 'r', encoding='utf-8') as f:
                        old_data = json.load(f)
                    old_candles = old_data.get('candles', [])
                    old_rsi = old_data.get('rsi_last_candle')  # Сохраняем старый RSI
                    
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
            
            # ✅ Сохраняем RSI: новый имеет приоритет, если не передан - используем старый
            final_rsi = rsi_value if rsi_value is not None else old_rsi
            
            # Сохраняем данные с метаданными
            data = {
                'symbol': symbol,
                'timeframe': timeframe,
                'candles': candles,
                'count': len(candles),
                'last_update': datetime.now().isoformat()
            }
            
            # ✅ Добавляем RSI в файл если он есть
            if final_rsi is not None:
                data['rsi_last_candle'] = final_rsi
            
            with open(candle_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            if len(candles) > 1000:  # Для больших файлов логируем на INFO
                logger.info(f"[CANDLES_DB] 💾 Сохранено: {symbol} ({timeframe}): {len(candles)} свечей" + (f", RSI={final_rsi:.2f}" if final_rsi is not None else ""))
            else:
                logger.debug(f"[CANDLES_DB] 💾 Сохранено: {symbol} ({timeframe}): {len(candles)} свечей" + (f", RSI={final_rsi:.2f}" if final_rsi is not None else ""))
            return True
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка сохранения {symbol}: {e}")
        return False

def save_candles_batch(timeframe, all_candles_dict, update_mode='replace'):
    """ПАКЕТНАЯ запись - сохраняет ВСЕ символы по отдельности"""
    try:
        total = len(all_candles_dict)
        logger.info(f"[CANDLES_DB] 💾💾 Начинаем пакетное сохранение: {total} символов ({timeframe})")
        saved = 0
        
        for idx, (symbol, candles) in enumerate(all_candles_dict.items(), 1):
            if save_candles(symbol, timeframe, candles, update_mode=update_mode):
                saved += 1
                # Логируем каждые 50 монет для прогресса
                if saved % 50 == 0 or saved == total:
                    logger.info(f"[CANDLES_DB] 💾 Прогресс сохранения: {saved}/{total} символов ({saved*100//total}%)")
        
        logger.info(f"[CANDLES_DB] 💾💾 ПАКЕТНО сохранено: {saved}/{total} символов ({timeframe})")
        return True
    except Exception as e:
        logger.error(f"[CANDLES_DB] ❌ Ошибка пакетного сохранения: {e}")
        import traceback
        logger.error(f"[CANDLES_DB] ❌ Traceback: {traceback.format_exc()}")
        return False

def get_candles(symbol, timeframe, return_rsi=False):
    """Читает свечи из файла монеты
    
    Args:
        symbol: Символ монеты
        timeframe: Таймфрейм
        return_rsi: Если True, возвращает также RSI из файла (если есть)
    
    Returns:
        Если return_rsi=False: список свечей
        Если return_rsi=True: кортеж (candles, rsi_value) где rsi_value может быть None
    """
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
            
            # ✅ Если запрошен RSI - возвращаем кортеж
            if return_rsi:
                rsi_value = data.get('rsi_last_candle')
                if rsi_value is not None:
                    logger.debug(f"[CANDLES_DB] 📊 {symbol}: RSI из файла = {rsi_value:.2f}")
                return (candles, rsi_value)
            
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

