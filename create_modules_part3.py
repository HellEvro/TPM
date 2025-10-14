#!/usr/bin/env python3
"""
Скрипт для создания модуля API endpoints и главного bots.py
"""

import os
import shutil
from datetime import datetime

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

# 10. Модуль с API endpoints (строки 5283 до конца)
print("\nСоздаю модуль api_endpoints.py...")
api_header = """Flask API endpoints для сервиса ботов

Все API endpoints для управления ботами, конфигурацией, позициями и т.д.
"""
api_imports = """import logging
import json
import os
import time
import threading
import sys
import importlib
from datetime import datetime
from flask import Flask, request, jsonify

logger = logging.getLogger('BotsService')

# Глобальные переменные (импортируются из главного файла)
bots_app = None
exchange = None
smart_rsi_manager = None
async_processor = None
bots_data_lock = threading.Lock()
bots_data = {}
rsi_data_lock = threading.Lock()
coins_rsi_data = {}
bots_cache_data = {}
bots_cache_lock = threading.Lock()
process_state = {}
system_initialized = False
shutdown_flag = threading.Event()
mature_coins_storage = {}
mature_coins_lock = threading.Lock()
optimal_ema_data = {}
coin_processing_locks = {}
BOT_STATUS = {}
ASYNC_AVAILABLE = False

# Заглушки для функций (будут импортированы из других модулей)
def clean_data_for_json(data):
    return data

def update_bots_cache_data():
    pass

def save_system_config(config):
    pass

def load_system_config():
    return {}

def save_auto_bot_config():
    pass

def save_bots_state():
    return True

def sync_positions_with_exchange():
    pass

def cleanup_inactive_bots():
    pass

def remove_mature_coins(symbols):
    pass

def check_trading_rules_activation():
    pass

def save_mature_coins_storage():
    pass

def load_mature_coins_storage():
    pass

def remove_mature_coin_from_storage(symbol):
    pass

def clear_mature_coins_storage():
    pass

def load_optimal_ema_data():
    pass

def save_optimal_ema_periods():
    pass

def get_optimal_ema_periods(symbol):
    return {}

def update_optimal_ema_data(data):
    return True

def restore_default_config():
    pass

def load_default_config():
    return {}

def process_auto_bot_signals(exchange_obj=None):
    pass

def test_exit_scam_filter(symbol):
    pass

def test_rsi_time_filter(symbol):
    pass

def start_async_processor():
    pass

def stop_async_processor():
    pass

"""
api_content = api_imports + extract_lines(5283, len(lines))
write_module('api_endpoints.py', api_content, api_header)

print(f"\nВсе модули созданы! Теперь создаю главный bots.py")

# Создаем новый главный bots.py
main_bots_content = """#!/usr/bin/env python3
\"\"\"
Главный файл bots.py - импортирует все модули
\"\"\"

# Базовые импорты
import os
import sys
import signal
import threading
import time
import logging
import json
from datetime import datetime
from flask import Flask
from flask_cors import CORS

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Функция проверки порта (должна быть до всех импортов)
from bots_modules.imports_and_globals import check_and_stop_existing_bots_processes

# КРИТИЧЕСКИ ВАЖНО: Проверяем порт 5001 ПЕРЕД загрузкой остальных модулей
if __name__ == '__main__':
    # Эта проверка должна быть ПЕРВОЙ при запуске
    can_continue = check_and_stop_existing_bots_processes()
    if not can_continue:
        print("Не удалось освободить порт 5001, завершаем работу")
        sys.exit(1)

# Импорт цветного логирования
from color_logger import setup_color_logging

# Импорт системы истории ботов
try:
    from bot_history import (
        bot_history_manager, log_bot_start, log_bot_stop, log_bot_signal,
        log_position_opened, log_position_closed
    )
    BOT_HISTORY_AVAILABLE = True
except ImportError as e:
    print(f"Модуль bot_history недоступен: {e}")
    # Создаем заглушки
    class DummyHistoryManager:
        def get_bot_history(self, *args, **kwargs): return []
        def get_bot_trades(self, *args, **kwargs): return []
        def get_bot_statistics(self, *args, **kwargs): return {}
        def clear_history(self, *args, **kwargs): pass
    
    bot_history_manager = DummyHistoryManager()
    def log_bot_start(*args, **kwargs): pass
    def log_bot_stop(*args, **kwargs): pass
    def log_bot_signal(*args, **kwargs): pass
    def log_position_opened(*args, **kwargs): pass
    def log_position_closed(*args, **kwargs): pass
    BOT_HISTORY_AVAILABLE = False

# Импортируем все модули
print("Загрузка модулей...")
from bots_modules.imports_and_globals import *
from bots_modules.calculations import *
from bots_modules.maturity import *
from bots_modules.optimal_ema import *
from bots_modules.filters import *
from bots_modules.bot_class import *
from bots_modules.sync_and_cache import *
from bots_modules.workers import *
from bots_modules.init_functions import *
from bots_modules.api_endpoints import *

print("Все модули загружены!")

# Настройка логирования
setup_color_logging()

# Добавляем файловый логгер
file_handler = logging.FileHandler('logs/bots.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('[BOTS] %(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

# Настройка кодировки для stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logger = logging.getLogger('BotsService')

# Отключаем HTTP логи Werkzeug
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)

# Создаем Flask приложение
bots_app = Flask(__name__)
CORS(bots_app)

# Регистрируем API endpoints (они уже определены в api_endpoints.py)
# Flask автоматически найдет все @bots_app.route декораторы

# Signal handlers
def signal_handler(signum, frame):
    \"\"\"Обработчик сигналов для graceful shutdown\"\"\"
    global graceful_shutdown
    logger.warning(f"Получен сигнал {signum}, начинаем graceful shutdown...")
    graceful_shutdown = True
    shutdown_flag.set()

def cleanup_bot_service():
    \"\"\"Очистка ресурсов перед остановкой\"\"\"
    logger.info("=" * 80)
    logger.info("ОСТАНОВКА СИСТЕМЫ INFOBOT")
    logger.info("=" * 80)
    
    try:
        # Останавливаем асинхронный процессор
        if async_processor:
            logger.info("Остановка асинхронного процессора...")
            stop_async_processor()
        
        # Сохраняем состояние
        logger.info("Сохранение состояния ботов...")
        save_bots_state()
        
        # Сохраняем хранилище зрелых монет
        logger.info("Сохранение хранилища зрелых монет...")
        save_mature_coins_storage()
        
        logger.info("Система остановлена")
        logger.info("=" * 80)
    except Exception as e:
        logger.error(f"Ошибка при очистке: {e}")

def run_bots_service():
    \"\"\"Запуск Flask сервера для API ботов\"\"\"
    try:
        logger.info("=" * 80)
        logger.info("ЗАПУСК BOTS SERVICE API (Порт 5001)")
        logger.info("=" * 80)
        
        # Запускаем сервер
        bots_app.run(
            host='0.0.0.0',
            port=5001,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Ошибка запуска Flask сервера: {e}")
        raise

if __name__ == '__main__':
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Регистрируем cleanup при выходе
    import atexit
    atexit.register(cleanup_bot_service)
    
    try:
        # Загружаем конфигурацию
        load_auto_bot_config()
        
        # Инициализируем сервис
        init_bot_service()
        
        # Запускаем фоновые воркеры
        auto_save_thread = threading.Thread(target=auto_save_worker, daemon=True)
        auto_save_thread.start()
        logger.info("Auto Save Worker запущен")
        
        auto_bot_thread = threading.Thread(target=auto_bot_worker, daemon=True)
        auto_bot_thread.start()
        logger.info("Auto Bot Worker запущен")
        
        # Запускаем Flask сервер (блокирующий вызов)
        run_bots_service()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_bot_service()
"""

# Создаем резервную копию старого bots.py
print("\nСоздаю резервную копию bots.py...")
backup_path = f"backups/bots/bots_before_split_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
os.makedirs(os.path.dirname(backup_path), exist_ok=True)
shutil.copy2('bots.py', backup_path)
print(f"Резервная копия: {backup_path}")

# Записываем новый bots.py
print("\nСоздаю новый bots.py...")
with open('bots.py', 'w', encoding='utf-8') as f:
    f.write(main_bots_content)
print("Новый bots.py создан!")

print("\n" + "=" * 60)
print("ГОТОВО!")
print("=" * 60)
print(f"Создано модулей: 10")
print("Модули находятся в: bots_modules/")
print("Новый bots.py импортирует все модули используя 'from module import *'")
print("\nТеперь можно запустить: python bots.py")
print("=" * 60)

