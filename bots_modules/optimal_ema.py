"""Функции работы с оптимальными EMA периодами

Включает:
- load_optimal_ema_data - загрузка данных об оптимальных EMA
- get_optimal_ema_periods - получение оптимальных периодов для монеты
- update_optimal_ema_data - обновление данных
- save_optimal_ema_periods - сохранение данных
"""

import os
import json
import logging
import time

logger = logging.getLogger('BotsService')

# Глобальные переменные
optimal_ema_data = {}
OPTIMAL_EMA_FILE = 'data/optimal_ema.json'

def load_optimal_ema_data():
    """Загружает данные об оптимальных EMA из файла"""
    global optimal_ema_data
    try:
        if os.path.exists(OPTIMAL_EMA_FILE):
            with open(OPTIMAL_EMA_FILE, 'r', encoding='utf-8') as f:
                optimal_ema_data = json.load(f)
                logger.info(f"[OPTIMAL_EMA] Загружено {len(optimal_ema_data)} записей об оптимальных EMA")
        else:
            optimal_ema_data = {}
            logger.info("[OPTIMAL_EMA] Файл с оптимальными EMA не найден")
    except Exception as e:
        logger.error(f"[OPTIMAL_EMA] Ошибка загрузки данных об оптимальных EMA: {e}")
        optimal_ema_data = {}

def get_optimal_ema_periods(symbol):
    """Получает оптимальные EMA периоды для монеты (поддержка отдельных LONG и SHORT EMA)"""
    global optimal_ema_data
    if symbol in optimal_ema_data:
        data = optimal_ema_data[symbol]
        
        # ✅ НОВЫЙ ФОРМАТ: Отдельные EMA для LONG и SHORT
        if 'long' in data and 'short' in data:
            return {
                'long': {
                    'ema_short_period': data['long'].get('ema_short_period', 50),
                    'ema_long_period': data['long'].get('ema_long_period', 200),
                    'accuracy': data['long'].get('accuracy', 0),
                    'total_signals': data['long'].get('total_signals', 0),
                    'correct_signals': data['long'].get('correct_signals', 0)
                },
                'short': {
                    'ema_short_period': data['short'].get('ema_short_period', 50),
                    'ema_long_period': data['short'].get('ema_long_period', 200),
                    'accuracy': data['short'].get('accuracy', 0),
                    'total_signals': data['short'].get('total_signals', 0),
                    'correct_signals': data['short'].get('correct_signals', 0)
                },
                # Для обратной совместимости
                'ema_short': data.get('ema_short_period', data['long'].get('ema_short_period', 50)),
                'ema_long': data.get('ema_long_period', data['long'].get('ema_long_period', 200)),
                'accuracy': data.get('accuracy', 0),
                'long_signals': data.get('long_signals', 0),
                'short_signals': data.get('short_signals', 0),
                'analysis_method': data.get('analysis_method', 'separate_long_short')
            }
        # Поддержка формата (ema_short_period, ema_long_period)
        elif 'ema_short_period' in data and 'ema_long_period' in data:
            return {
                'ema_short': data['ema_short_period'],
                'ema_long': data['ema_long_period'],
                'accuracy': data.get('accuracy', 0),
                'long_signals': data.get('long_signals', 0),
                'short_signals': data.get('short_signals', 0),
                'analysis_method': data.get('analysis_method', 'unknown')
            }
        # Поддержка старого формата (ema_short, ema_long)
        elif 'ema_short' in data and 'ema_long' in data:
            return {
                'ema_short': data['ema_short'],
                'ema_long': data['ema_long'],
                'accuracy': data.get('accuracy', 0),
                'long_signals': 0,
                'short_signals': 0,
                'analysis_method': 'legacy'
            }
        else:
            # Неизвестный формат данных
            logger.warning(f"[OPTIMAL_EMA] Неизвестный формат данных для {symbol}")
            return {
                'ema_short': 50,
                'ema_long': 200,
                'accuracy': 0,
                'long_signals': 0,
                'short_signals': 0,
                'analysis_method': 'default'
            }
    else:
        # Возвращаем дефолтные значения
        return {
            'ema_short': 50,
            'ema_long': 200,
            'accuracy': 0,
            'long_signals': 0,
            'short_signals': 0,
            'analysis_method': 'default'
        }

# ❌ ОТКЛЮЧЕНО: Функция больше не используется (EMA фильтр убран)
# Скрипт optimal_ema.py перемещен в backup
# def calculate_all_coins_optimal_ema(mode='auto', force_symbols=None):
#     """📊 ПАКЕТНЫЙ расчет Optimal EMA через скрипт с параметрами
#     
#     Args:
#         mode (str): Режим работы
#             - 'auto': --all (только новые монеты)
#             - 'force': --force (все монеты принудительно)
#             - 'symbols': --force --coins LIST (конкретные монеты)
#         force_symbols (list): Список монет для принудительного расчета (если mode='symbols')
#     """
#     logger.warning("[OPTIMAL_EMA_BATCH] ❌ Функция отключена - EMA фильтр больше не используется")
#     return False

def update_optimal_ema_data(new_data):
    """Обновляет данные об оптимальных EMA из внешнего источника"""
    global optimal_ema_data
    try:
        if isinstance(new_data, dict):
            optimal_ema_data.update(new_data)
            logger.info(f"[OPTIMAL_EMA] Обновлено {len(new_data)} записей об оптимальных EMA")
            return True
        else:
            logger.error("[OPTIMAL_EMA] Неверный формат данных для обновления")
            return False
    except Exception as e:
        logger.error(f"[OPTIMAL_EMA] Ошибка обновления данных: {e}")
        return False

