#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для очистки загруженных свечей и перезагрузки их заново
Используется для обновления структуры данных (например, добавление turnover)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots_modules.candles_db import clear_timeframe_cache, get_cached_symbols_count
from bots_modules.imports_and_globals import get_timeframe
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_and_reload_candles(timeframe=None):
    """Очищает кэш свечей для указанного таймфрейма"""
    try:
        if timeframe is None:
            timeframe = get_timeframe()
        
        logger.info(f"🗑️ Очистка свечей для таймфрейма: {timeframe}")
        
        # Проверяем текущее количество файлов
        before_count = get_cached_symbols_count(timeframe)
        logger.info(f"📊 Текущее количество монет: {before_count}")
        
        # Очищаем кэш
        cleared = clear_timeframe_cache(timeframe)
        
        if cleared:
            logger.info(f"✅ Кэш для {timeframe} очищен")
            logger.info(f"🔄 Запустите continuous_data_loader для перезагрузки свечей")
            logger.info(f"   Или просто дождитесь следующего раунда загрузки")
        else:
            logger.warning(f"⚠️ Кэш для {timeframe} уже был пуст или не существовал")
        
        return cleared
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Очистка и перезагрузка свечей')
    parser.add_argument('--timeframe', '-t', type=str, default=None,
                       help='Таймфрейм для очистки (по умолчанию из конфига)')
    parser.add_argument('--all', action='store_true',
                       help='Очистить все таймфреймы')
    
    args = parser.parse_args()
    
    if args.all:
        timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '6h', '1d', '1w']
        logger.info("🗑️ Очистка ВСЕХ таймфреймов...")
        for tf in timeframes:
            clear_and_reload_candles(tf)
    else:
        clear_and_reload_candles(args.timeframe)

