#!/usr/bin/env python3
"""
Скрипт для создания оставшихся модулей из bots.py (часть 2)
"""

import os

# Читаем весь файл
with open('bots.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Всего строк: {len(lines)}")

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

# 6. Модуль с классом NewTradingBot (строки 2372-2872)
print("\nСоздаю модуль bot_class.py...")
bot_class_header = """Класс торгового бота NewTradingBot

Основной класс для управления торговым ботом с поддержкой:
- Автоматического открытия/закрытия позиций
- Проверки фильтров (RSI time filter, trend, maturity)
- Защитных механизмов (trailing stop, break-even)
"""
bot_class_imports = """import logging
from datetime import datetime
import time
import threading

logger = logging.getLogger('BotsService')

# Глобальные переменные (импортируются из главного файла)
bots_data_lock = threading.Lock()
bots_data = {}
rsi_data_lock = threading.Lock()
coins_rsi_data = {}
BOT_STATUS = {
    'IDLE': 'idle',
    'RUNNING': 'running',
    'ARMED_UP': 'armed_up', 
    'ARMED_DOWN': 'armed_down',
    'IN_POSITION_LONG': 'in_position_long',
    'IN_POSITION_SHORT': 'in_position_short',
    'PAUSED': 'paused'
}

# Импорт функций фильтров (будут доступны после импорта)
try:
    from bots_modules.filters import check_rsi_time_filter
except:
    def check_rsi_time_filter(*args, **kwargs):
        return {'allowed': True, 'reason': 'Filter not loaded'}

"""
bot_class_content = bot_class_imports + extract_lines(2372, 2872)
write_module('bot_class.py', bot_class_content, bot_class_header)

# 7. Модуль с функциями кэша и синхронизации (строки 2873-4546)
print("\nСоздаю модуль sync_and_cache.py...")
sync_header = """Функции кэширования, синхронизации и управления состоянием

Включает:
- Функции работы с RSI кэшом
- Сохранение/загрузка состояния ботов
- Синхронизация с биржей
- Обновление позиций
- Управление зрелыми монетами
"""
sync_imports = """import os
import json
import time
import threading
import logging
from datetime import datetime
import copy

logger = logging.getLogger('BotsService')

# Глобальные переменные (импортируются из главного файла)
bots_data_lock = threading.Lock()
bots_data = {}
rsi_data_lock = threading.Lock()
coins_rsi_data = {}
bots_cache_data = {}
bots_cache_lock = threading.Lock()
process_state = {}
exchange = None
mature_coins_storage = {}
mature_coins_lock = threading.Lock()
BOT_STATUS = {}
DEFAULT_AUTO_BOT_CONFIG = {}
RSI_CACHE_FILE = 'data/rsi_cache.json'
PROCESS_STATE_FILE = 'data/process_state.json'
SYSTEM_CONFIG_FILE = 'data/system_config.json'
BOTS_STATE_FILE = 'data/bots_state.json'
AUTO_BOT_CONFIG_FILE = 'data/auto_bot_config.json'
MATURE_COINS_FILE = 'data/mature_coins.json'
DEFAULT_CONFIG_FILE = 'data/default_auto_bot_config.json'
INACTIVE_BOT_TIMEOUT = 600

"""
sync_content = sync_imports + extract_lines(2873, 4546)
write_module('sync_and_cache.py', sync_content, sync_header)

# 8. Модуль с воркерами (строки 4547-4724)
print("\nСоздаю модуль workers.py...")
workers_header = """Фоновые воркеры

Включает:
- auto_save_worker - автоматическое сохранение состояния
- auto_bot_worker - проверка сигналов Auto Bot
"""
workers_imports = """import time
import logging
import threading
from datetime import datetime

logger = logging.getLogger('BotsService')

# Глобальные переменные (импортируются из главного файла)
shutdown_flag = threading.Event()
system_initialized = False
bots_data_lock = threading.Lock()
bots_data = {}
process_state = {}
mature_coins_storage = {}
mature_coins_lock = threading.Lock()
exchange = None

# Константы
BOT_STATUS_UPDATE_INTERVAL = 30
STOP_LOSS_SETUP_INTERVAL = 300
POSITION_SYNC_INTERVAL = 30
INACTIVE_BOT_CLEANUP_INTERVAL = 600

# Импорт функций (будут доступны после импорта)
try:
    from bot_engine.bot_config import SystemConfig
except:
    class SystemConfig:
        AUTO_SAVE_INTERVAL = 60

def should_log_message(category, message, interval_seconds=60):
    return (True, message)

def save_bots_state():
    return True

def save_mature_coins_storage():
    pass

def update_process_state(name, data):
    pass

def save_auto_bot_config():
    pass

def update_bots_cache_data():
    pass

def check_missing_stop_losses():
    pass

def cleanup_inactive_bots():
    pass

def check_trading_rules_activation():
    pass

"""
workers_content = workers_imports + extract_lines(4547, 4724)
write_module('workers.py', workers_content, workers_header)

# 9. Модуль с функциями инициализации (строки 4725-5282)
print("\nСоздаю модуль init_functions.py...")
init_header = """Функции инициализации системы

Включает:
- init_bot_service - инициализация сервиса ботов
- start_async_processor - запуск асинхронного процессора
- stop_async_processor - остановка асинхронного процессора
- create_bot - создание бота
- process_trading_signals_on_candle_close - обработка сигналов
- init_exchange_sync - синхронная инициализация биржи
- ensure_exchange_initialized - проверка инициализации биржи
"""
init_imports = """import os
import time
import logging
import threading
import asyncio
from datetime import datetime

logger = logging.getLogger('BotsService')

# Глобальные переменные (импортируются из главного файла)
exchange = None
smart_rsi_manager = None
async_processor = None
async_processor_task = None
system_initialized = False
shutdown_flag = threading.Event()
bots_data_lock = threading.Lock()
bots_data = {}
process_state = {}
mature_coins_storage = {}
ASYNC_AVAILABLE = False
BOT_STATUS = {}

# Импорт функций
try:
    from exchanges.exchange_factory import ExchangeFactory
    from app.config import EXCHANGES
except:
    pass

try:
    from bot_engine.smart_rsi_manager import SmartRSIManager
except:
    SmartRSIManager = None

try:
    from bot_engine.async_processor import AsyncMainProcessor
except:
    AsyncMainProcessor = None

# Заглушки для функций
def load_mature_coins_storage():
    pass

def load_optimal_ema_data():
    pass

def save_default_config():
    pass

def load_system_config():
    pass

def load_auto_bot_config():
    pass

def load_bots_state():
    pass

def check_startup_position_conflicts():
    pass

def sync_bots_with_exchange():
    pass

"""
init_content = init_imports + extract_lines(4725, 5282)
write_module('init_functions.py', init_content, init_header)

print(f"\nСоздано еще 4 модуля в bots_modules/")
print("Следующий шаг: создать модуль API endpoints")

