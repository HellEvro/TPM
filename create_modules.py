#!/usr/bin/env python3
"""
Скрипт для создания модулей из bots.py
"""

import os

# Читаем весь файл
with open('bots.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Всего строк: {len(lines)}")

# Создаем папку для модулей
os.makedirs('bots_modules', exist_ok=True)

def extract_lines(start, end):
    """Извлекает строки из диапазона"""
    return ''.join(lines[start-1:end])

def write_module(filename, content, header=""):
    """Записывает модуль"""
    with open(f'bots_modules/{filename}', 'w', encoding='utf-8') as f:
        if header:
            f.write(f'"""{header}"""\n\n')
        f.write(content)
    print(f"Создан: bots_modules/{filename}")

# 1. Модуль с импортами и глобальными переменными (строки 8-542)
print("\nСоздаю модуль imports_and_globals.py...")
imports_content = extract_lines(8, 542)
write_module('imports_and_globals.py', imports_content, 
             "Импорты, константы и глобальные переменные для bots.py")

# 2. Модуль с RSI/EMA функциями (строки 543-984)
print("\nСоздаю модуль calculations.py...")
calc_header = """Функции расчета RSI, EMA и анализа тренда

Включает:
- calculate_rsi - расчет RSI
- calculate_rsi_history - история RSI
- calculate_ema - расчет EMA
- analyze_trend_6h - анализ тренда
- perform_enhanced_rsi_analysis - расширенный анализ RSI
"""
calc_imports = """import logging
from datetime import datetime
import time

# Импорты из bot_engine
try:
    from bot_engine.indicators import SignalGenerator, TechnicalIndicators
    from bot_engine.bot_config import (
        RSI_EXTREME_ZONE_TIMEOUT, RSI_EXTREME_OVERSOLD, RSI_EXTREME_OVERBOUGHT,
        SystemConfig
    )
except ImportError:
    pass

logger = logging.getLogger('BotsService')

"""
calc_content = calc_imports + extract_lines(543, 1221)
write_module('calculations.py', calc_content, calc_header)

# 3. Модуль с функциями зрелости (строки 643-968)  
print("\nСоздаю модуль maturity.py...")
maturity_header = """Функции проверки зрелости монет

Включает:
- load_mature_coins_storage - загрузка хранилища зрелых монет
- save_mature_coins_storage - сохранение хранилища
- is_coin_mature_stored - проверка наличия в хранилище
- add_mature_coin_to_storage - добавление в хранилище
- remove_mature_coin_from_storage - удаление из хранилища
- update_mature_coin_verification - обновление времени проверки
- check_coin_maturity_with_storage - проверка зрелости с хранилищем
- check_coin_maturity - проверка зрелости
"""
maturity_imports = """import os
import json
import time
import threading
import logging
from datetime import datetime

logger = logging.getLogger('BotsService')

# Глобальные переменные (будут импортированы из главного файла)
mature_coins_storage = {}
MATURE_COINS_FILE = 'data/mature_coins.json'
mature_coins_lock = threading.Lock()

# Константы для зрелости
MIN_CANDLES_FOR_MATURITY = 200
MIN_RSI_LOW = 35
MAX_RSI_HIGH = 65

"""
# Извлекаем строки 643-968 (функции зрелости и check_coin_maturity)
maturity_content = maturity_imports + extract_lines(643, 968)
write_module('maturity.py', maturity_content, maturity_header)

# 4. Модуль с Optimal EMA (строки 775-852)
print("\nСоздаю модуль optimal_ema.py...")
opt_ema_header = """Функции работы с оптимальными EMA периодами

Включает:
- load_optimal_ema_data - загрузка данных об оптимальных EMA
- get_optimal_ema_periods - получение оптимальных периодов для монеты
- update_optimal_ema_data - обновление данных
- save_optimal_ema_periods - сохранение данных
"""
opt_ema_imports = """import os
import json
import logging

logger = logging.getLogger('BotsService')

# Глобальные переменные
optimal_ema_data = {}
OPTIMAL_EMA_FILE = 'data/optimal_ema.json'

"""
opt_ema_content = opt_ema_imports + extract_lines(775, 852)
write_module('optimal_ema.py', opt_ema_content, opt_ema_header)

# 5. Модуль с фильтрами (строки 1222-2180)
print("\nСоздаю модуль filters.py...")
filters_header = """Фильтры для торговых сигналов

Включает:
- check_rsi_time_filter - временной фильтр RSI
- check_exit_scam_filter - фильтр exit scam
- check_no_existing_position - проверка отсутствия позиции
- check_auto_bot_filters - проверка всех фильтров автобота
- test_exit_scam_filter - тестирование exit scam фильтра
- test_rsi_time_filter - тестирование временного фильтра
"""
filters_imports = """import logging
import time
import threading

logger = logging.getLogger('BotsService')

# Глобальные переменные (импортируются из главного файла)
bots_data_lock = threading.Lock()
bots_data = {}
rsi_data_lock = threading.Lock()
coins_rsi_data = {}

"""
filters_content = filters_imports + extract_lines(1222, 2371)
write_module('filters.py', filters_content, filters_header)

print(f"\nСоздано 5 модулей в bots_modules/")
print("Следующий шаг: создать модули для bot_class, sync, workers, API")

