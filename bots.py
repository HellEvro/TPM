#!/usr/bin/env python3
"""
Отдельный сервис для управления торговыми ботами
Независимый от основного InfoBot приложения
Порт: 5001
"""

import os
import sys
import signal
import threading
import time
import logging
import json
import atexit
import asyncio
import requests
import socket
import psutil
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import concurrent.futures

# Импортируем асинхронный процессор
try:
    from bot_engine.async_processor import AsyncMainProcessor
    ASYNC_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Асинхронный процессор недоступен: {e}")
    ASYNC_AVAILABLE = False

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_and_stop_existing_bots_processes():
    """
    Проверяет порт 5001 и останавливает процесс который его занимает.
    
    Returns:
        bool: True если можно продолжать запуск, False если нужно остановиться
    """
    try:
        print("=" * 80)
        print("🔍 ПРОВЕРКА ПОРТА 5001 (BOTS SERVICE)")
        print("=" * 80)
        
        current_pid = os.getpid()
        print(f"📍 Текущий PID: {current_pid}")
        
        # ГЛАВНАЯ ПРОВЕРКА: Проверяем порт 5001
        port_occupied = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 5001))
            sock.close()
            
            if result == 0:
                port_occupied = True
                print("⚠️  Порт 5001 уже занят!")
            else:
                print("✅ Порт 5001 свободен")
        except Exception as e:
            print(f"⚠️  Ошибка проверки порта: {e}")
        
        # Если порт свободен - сразу выходим
        if not port_occupied:
            print("=" * 80)
            print()
            return True
        
        # Если порт занят - останавливаем процесс
        if port_occupied:
            print("\n⚠️  ПОРТ 5001 ЗАНЯТ - ищем процесс который его использует...")
            
            # Ищем процесс который слушает порт 5001
            process_to_stop = None
            
            try:
                # Ищем ВСЕ процессы python с bots.py в командной строке
                python_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['name'] and 'python' in proc.info['name'].lower():
                            cmdline = proc.info['cmdline']
                            if cmdline and any('bots.py' in arg for arg in cmdline):
                                if proc.info['pid'] != current_pid:
                                    python_processes.append(proc.info['pid'])
                                    print(f"🎯 Найден процесс bots.py: PID {proc.info['pid']}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                
                # Также проверяем порт 5001
                port_process = None
                for conn in psutil.net_connections(kind='inet'):
                    if conn.laddr.port == 5001 and conn.status == 'LISTEN':
                        port_process = conn.pid
                        if port_process != current_pid and port_process not in python_processes:
                            python_processes.append(port_process)
                            print(f"🎯 Найден процесс на порту 5001: PID {port_process}")
                        break
                
                if python_processes:
                    process_to_stop = python_processes[0]  # Останавливаем первый найденный
                else:
                    process_to_stop = None
                
                if process_to_stop and process_to_stop != current_pid:
                    try:
                        proc = psutil.Process(process_to_stop)
                        proc_info = proc.as_dict(attrs=['pid', 'name', 'cmdline', 'create_time'])
                        
                        print(f"🎯 Найден процесс на порту 5001:")
                        print(f"   PID: {proc_info['pid']}")
                        print(f"   Команда: {' '.join(proc_info['cmdline'][:3]) if proc_info['cmdline'] else 'N/A'}...")
                        print()
                        
                        print(f"🔧 Останавливаем процесс {process_to_stop}...")
                        proc.terminate()
                        
                        try:
                            proc.wait(timeout=5)
                            print(f"✅ Процесс {process_to_stop} остановлен")
                        except psutil.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                            print(f"🔴 Процесс {process_to_stop} принудительно остановлен")
                        
                        print("\n⏳ Ожидание освобождения порта 5001...")
                        for i in range(10):
                            time.sleep(1)
                            try:
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.settimeout(1)
                                result = sock.connect_ex(('127.0.0.1', 5001))
                                sock.close()
                                
                                if result != 0:
                                    print("✅ Порт 5001 освобожден")
                                    break
                            except:
                                pass
                            
                            if i == 9:
                                print("❌ Порт 5001 все еще занят!")
                                print("⚠️  Возможно нужно вручную остановить процесс")
                                print("=" * 80)
                                return False
                        
                    except Exception as e:
                        print(f"❌ Ошибка остановки процесса {process_to_stop}: {e}")
                        print("=" * 80)
                        return False
                
                elif not process_to_stop:
                    print("⚠️  Не удалось найти процесс на порту 5001")
                    print("=" * 80)
                    return False
                        
            except Exception as e:
                print(f"⚠️  Ошибка поиска процесса на порту: {e}")
                print("=" * 80)
                return False
            
            print("=" * 80)
            print("✅ ПРОВЕРКА ЗАВЕРШЕНА - ПРОДОЛЖАЕМ ЗАПУСК")
            print("=" * 80)
            print()
            return True
            
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРОВЕРКИ: {e}")
        import traceback
        traceback.print_exc()
        print("⚠️  Продолжаем запуск без проверки...")
        print("=" * 80)
        print()
        return True

# Импорт цветного логирования
from color_logger import setup_color_logging

# Импорт системы истории ботов
from bot_history import (
    bot_history_manager, log_bot_start, log_bot_stop, log_bot_signal,
    log_position_opened, log_position_closed
)

# Импорты для бот-движка
from exchanges.exchange_factory import ExchangeFactory
from app.config import EXCHANGES, APP_DEBUG
from bot_engine.bot_config import (
    SystemConfig, RiskConfig, FilterConfig, ExchangeConfig,
    RSI_EXTREME_ZONE_TIMEOUT, RSI_EXTREME_OVERSOLD, RSI_EXTREME_OVERBOUGHT,
    RSI_VOLUME_CONFIRMATION_MULTIPLIER, RSI_DIVERGENCE_LOOKBACK,
    DEFAULT_AUTO_BOT_CONFIG as BOT_ENGINE_DEFAULT_CONFIG
)
from bot_engine.smart_rsi_manager import SmartRSIManager
from bot_engine.trading_bot import TradingBot as RealTradingBot

# Константы для файлов состояния
BOTS_STATE_FILE = 'data/bots_state.json'
AUTO_BOT_CONFIG_FILE = 'data/auto_bot_config.json'

# Константы для обновления позиций
BOT_STATUS_UPDATE_INTERVAL = 3  # 3 секунды - интервал обновления детальной информации о состоянии ботов
STOP_LOSS_SETUP_INTERVAL = 300  # 5 минут - интервал установки недостающих стоп-лоссов
POSITION_SYNC_INTERVAL = 30  # 10 минут - интервал синхронизации позиций с биржей
INACTIVE_BOT_CLEANUP_INTERVAL = 600  # 10 минут - интервал проверки и удаления неактивных ботов
INACTIVE_BOT_TIMEOUT = 600  # 10 минут - время ожидания перед удалением бота без реальных позиций на бирже

# Глобальные переменные для кэшированных данных (как в app.py)
bots_cache_data = {
    'bots': [],
    'account_info': {},
    'last_update': None
}
bots_cache_lock = threading.Lock()

# Кэш для подавления повторяющихся логов
log_suppression_cache = {
    'auto_bot_signals': {'count': 0, 'last_log': 0, 'message': ''},
    'position_sync': {'count': 0, 'last_log': 0, 'message': ''},
    'cache_update': {'count': 0, 'last_log': 0, 'message': ''},
    'exchange_positions': {'count': 0, 'last_log': 0, 'message': ''}
}
RSI_CACHE_FILE = 'data/rsi_cache.json'
DEFAULT_CONFIG_FILE = 'data/default_auto_bot_config.json'
PROCESS_STATE_FILE = 'data/process_state.json'
SYSTEM_CONFIG_FILE = 'data/system_config.json'

# Константы для фильтрации зрелости монет
MIN_CANDLES_FOR_MATURITY = 200  # Минимум свечей для зрелой монеты (50 дней на 6H)
MIN_RSI_LOW = 35   # Минимальный достигнутый RSI
MAX_RSI_HIGH = 65  # Максимальный достигнутый RSI
MIN_VOLATILITY_THRESHOLD = 0.05  # Минимальная волатильность (5%)

# Создаем папку для данных если её нет
os.makedirs('data', exist_ok=True)

# Дефолтная конфигурация Auto Bot (для восстановления)
# ✅ ИСПОЛЬЗУЕМ КОНФИГ ИЗ bot_engine/bot_config.py
# Импортирован как BOT_ENGINE_DEFAULT_CONFIG
DEFAULT_AUTO_BOT_CONFIG = BOT_ENGINE_DEFAULT_CONFIG

# Состояние процессов системы
process_state = {
    'smart_rsi_manager': {
        'active': False,
        'last_update': None,
        'update_count': 0,
        'last_error': None
    },
    'auto_bot_worker': {
        'active': False,
        'last_check': None,
        'check_count': 0,
        'last_error': None
    },
    'auto_save_worker': {
        'active': False,
        'last_save': None,
        'save_count': 0,
        'last_error': None
    },
    'exchange_connection': {
        'initialized': False,
        'last_sync': None,
        'connection_count': 0,
        'last_error': None
    },
    'auto_bot_signals': {
        'last_check': None,
        'signals_processed': 0,
        'bots_created': 0,
        'last_error': None
    }
}

# Настройка цветного логирования
setup_color_logging()

# Добавляем файловый логгер для сохранения в файл
file_handler = logging.FileHandler('logs/bots.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('[BOTS] %(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Получаем корневой логгер и добавляем файловый обработчик
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

# Настройка кодировки для stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def should_log_message(category, message, interval_seconds=60):
    """
    Определяет, нужно ли логировать сообщение или подавить его из-за частоты
    
    Args:
        category: Категория сообщения (auto_bot_signals, position_sync, etc.)
        message: Текст сообщения
        interval_seconds: Минимальный интервал между одинаковыми сообщениями
    
    Returns:
        tuple: (should_log: bool, summary_message: str or None)
    """
    import time
    
    current_time = time.time()
    
    if category not in log_suppression_cache:
        log_suppression_cache[category] = {'count': 0, 'last_log': 0, 'message': ''}
    
    cache_entry = log_suppression_cache[category]
    
    # Если это то же самое сообщение
    if cache_entry['message'] == message:
        cache_entry['count'] += 1
        
        # Если прошло достаточно времени, логируем с счетчиком
        if current_time - cache_entry['last_log'] >= interval_seconds:
            cache_entry['last_log'] = current_time
            
            if cache_entry['count'] > 1:
                summary_message = f"{message} (повторилось {cache_entry['count']} раз за {int(current_time - cache_entry['last_log'] + interval_seconds)}с)"
                cache_entry['count'] = 0
                return True, summary_message
            else:
                cache_entry['count'] = 0
                return True, message
        else:
            # Подавляем сообщение
            return False, None
    else:
        # Новое сообщение
        if cache_entry['count'] > 0:
            # Логируем сводку по предыдущему сообщению
            summary = f"[SUMMARY] Предыдущее сообщение повторилось {cache_entry['count']} раз"
            logger.info(f"[{category.upper()}] {summary}")
        
        cache_entry['message'] = message
        cache_entry['count'] = 1
        cache_entry['last_log'] = current_time
        return True, message

logger = logging.getLogger('BotsService')

# Отключаем HTTP логи Werkzeug для чистоты консоли
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)  # Показывать только warnings и errors

# Создаем Flask приложение для API ботов
bots_app = Flask(__name__)
CORS(bots_app)

# API endpoint для проверки статуса сервиса ботов
@bots_app.route('/api/status', methods=['GET'])
def api_status():
    """API endpoint для проверки статуса сервиса ботов"""
    return jsonify({
        'status': 'online',
        'service': 'bots',
        'timestamp': datetime.now().isoformat(),
        'test': 'simple_endpoint'
    })

# Добавляем обработчик ошибок JSON сериализации
@bots_app.errorhandler(TypeError)
def handle_json_error(e):
    """Обрабатывает ошибки JSON сериализации"""
    if "not JSON serializable" in str(e):
        logger.error(f"[JSON_ERROR] Ошибка JSON сериализации: {e}")
        return jsonify({'success': False, 'error': 'JSON serialization error'}), 500
    return jsonify({'success': False, 'error': str(e)}), 500

# Глобальные переменные
exchange = None
shutdown_flag = threading.Event()
graceful_shutdown = False  # Флаг для graceful shutdown
system_initialized = False  # КРИТИЧЕСКИ ВАЖНО: Флаг полной инициализации системы
smart_rsi_manager = None  # Умный менеджер RSI
async_processor = None  # Асинхронный процессор
async_processor_task = None  # Задача асинхронного процессора

# БЛОКИРОВКИ для предотвращения race conditions
coin_processing_locks = {}  # Блокировки для обработки каждой монеты
coin_processing_lock = threading.Lock()  # Блокировка для управления coin_processing_locks

def get_coin_processing_lock(symbol):
    """Получает блокировку для обработки конкретной монеты"""
    with coin_processing_lock:
        if symbol not in coin_processing_locks:
            coin_processing_locks[symbol] = threading.Lock()
        return coin_processing_locks[symbol]

# Инициализируем биржу при импорте модуля
def init_exchange():
    """Инициализация биржи"""
    global exchange
    try:
        logger.info("[INIT] Инициализация биржи...")
        exchange = ExchangeFactory.create_exchange(
            'BYBIT', 
            EXCHANGES['BYBIT']['api_key'], 
            EXCHANGES['BYBIT']['api_secret']
        )
        logger.info("[INIT] ✅ Биржа инициализирована успешно")
    except Exception as e:
        logger.error(f"[INIT] ❌ Ошибка инициализации биржи: {e}")
        exchange = None

# Инициализация биржи будет выполнена в init_bot_service()

# Торговые параметры RSI согласно техзаданию (настраиваемые)
RSI_OVERSOLD = 29  # Зона покупки (LONG при RSI <= 29)
RSI_OVERBOUGHT = 71  # Зона продажи (SHORT при RSI >= 71)
RSI_EXIT_LONG = 65  # Выход из лонга (при RSI >= 65)
RSI_EXIT_SHORT = 35  # Выход из шорта (при RSI <= 35)

# EMA параметры для анализа тренда 6H
EMA_FAST = 50
EMA_SLOW = 200
TREND_CONFIRMATION_BARS = 3

# Возможные статусы ботов
BOT_STATUS = {
    'IDLE': 'idle',
    'RUNNING': 'running',
    'ARMED_UP': 'armed_up', 
    'ARMED_DOWN': 'armed_down',
    'IN_POSITION_LONG': 'in_position_long',
    'IN_POSITION_SHORT': 'in_position_short',
    'PAUSED': 'paused'
}

# Глобальная модель данных для всех монет с RSI 6H
coins_rsi_data = {
    'coins': {},  # Словарь всех монет с RSI данными
    'last_update': None,
    'update_in_progress': False,
    'total_coins': 0,
    'successful_coins': 0,
    'failed_coins': 0
}

# Модель данных для ботов
bots_data = {
    'bots': {},  # {symbol: bot_config}
    'auto_bot_config': DEFAULT_AUTO_BOT_CONFIG.copy(),  # Используем дефолтную конфигурацию
    'global_stats': {
        'active_bots': 0,
        'bots_in_position': 0,
        'total_pnl': 0.0
    }
}

# Блокировки для данных
rsi_data_lock = threading.Lock()
bots_data_lock = threading.Lock()

# Загружаем сохраненную конфигурацию Auto Bot
def load_auto_bot_config():
    """Загружает конфигурацию Auto Bot из файла"""
    try:
        config_file = 'data/auto_bot_config.json'
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                with bots_data_lock:
                    bots_data['auto_bot_config'].update(saved_config)
                    # ВАЖНО: Всегда отключаем автобот при запуске!
                    bots_data['auto_bot_config']['enabled'] = False
                logger.info(f"[CONFIG] ✅ Загружена конфигурация Auto Bot из {config_file}")
                logger.info(f"[CONFIG] 🔒 Auto Bot принудительно выключен при запуске")
        else:
            logger.info(f"[CONFIG] 📁 Файл конфигурации {config_file} не найден, используем дефолтные настройки")
            # Auto Bot уже выключен в дефолтной конфигурации
    except Exception as e:
        logger.error(f"[CONFIG] ❌ Ошибка загрузки конфигурации: {e}")

# ВАЖНО: load_auto_bot_config() теперь вызывается в if __name__ == '__main__'
# чтобы check_and_stop_existing_bots_processes() мог вывести свои сообщения первым

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

# Постоянное хранилище зрелых монет
mature_coins_storage = {}
MATURE_COINS_FILE = 'data/mature_coins.json'
mature_coins_lock = threading.Lock()

# Оптимальные EMA для определения тренда
optimal_ema_data = {}
OPTIMAL_EMA_FILE = 'data/optimal_ema.json'

def load_mature_coins_storage():
    """Загружает постоянное хранилище зрелых монет из файла"""
    global mature_coins_storage
    try:
        if os.path.exists(MATURE_COINS_FILE):
            with open(MATURE_COINS_FILE, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            # ✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем блокировку при обновлении глобального хранилища
            with mature_coins_lock:
                mature_coins_storage = loaded_data
            
            logger.info(f"[MATURITY_STORAGE] ✅ Загружено {len(mature_coins_storage)} зрелых монет из файла")
        else:
            with mature_coins_lock:
                mature_coins_storage = {}
            logger.info("[MATURITY_STORAGE] Файл хранилища не найден, создаем новый")
    except Exception as e:
        logger.error(f"[MATURITY_STORAGE] Ошибка загрузки хранилища: {e}")
        with mature_coins_lock:
            mature_coins_storage = {}

def save_mature_coins_storage():
    """Сохраняет постоянное хранилище зрелых монет в файл"""
    try:
        with mature_coins_lock:
            # Создаем копию для безопасной сериализации
            storage_copy = mature_coins_storage.copy()
        
        os.makedirs(os.path.dirname(MATURE_COINS_FILE), exist_ok=True)
        
        # Создаем временный файл для атомарной записи
        temp_file = MATURE_COINS_FILE + '.tmp'
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(storage_copy, f, ensure_ascii=False, indent=2)
                
                # Атомарно заменяем оригинальный файл
                if os.name == 'nt':  # Windows
                    if os.path.exists(MATURE_COINS_FILE):
                        os.remove(MATURE_COINS_FILE)
                    os.rename(temp_file, MATURE_COINS_FILE)
                else:  # Unix/Linux
                    os.rename(temp_file, MATURE_COINS_FILE)
                    
                logger.debug(f"[MATURITY_STORAGE] Хранилище сохранено: {len(storage_copy)} монет")
                break  # Успешно сохранили, выходим из цикла
                
            except (OSError, IOError) as temp_error:
                if attempt < max_retries - 1:
                    logger.warning(f"[MATURITY_STORAGE] Попытка {attempt + 1} неудачна, повторяем через {retry_delay}с: {temp_error}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Увеличиваем задержку
                    continue
                else:
                    # Удаляем временный файл в случае ошибки
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    raise temp_error
            except Exception as temp_error:
                # Удаляем временный файл в случае ошибки
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                raise temp_error
            
    except Exception as e:
        logger.error(f"[MATURITY_STORAGE] Ошибка сохранения хранилища: {e}")
        # Попробуем создать резервную копию
        try:
            backup_file = MATURE_COINS_FILE + '.backup'
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(storage_copy, f, ensure_ascii=False, indent=2)
            logger.info(f"[MATURITY_STORAGE] Создана резервная копия: {backup_file}")
        except Exception as backup_error:
            logger.error(f"[MATURITY_STORAGE] Не удалось создать резервную копию: {backup_error}")

def is_coin_mature_stored(symbol):
    """Проверяет, есть ли монета в постоянном хранилище зрелых монет"""
    with mature_coins_lock:
        return symbol in mature_coins_storage

def add_mature_coin_to_storage(symbol, maturity_data, auto_save=True):
    """Добавляет монету в постоянное хранилище зрелых монет (только если её там еще нет)"""
    global mature_coins_storage
    
    with mature_coins_lock:
        # Проверяем, есть ли уже монета в хранилище
        if symbol in mature_coins_storage:
            # Обновляем только время последней проверки
            mature_coins_storage[symbol]['last_verified'] = time.time()
            logger.debug(f"[MATURITY_STORAGE] {symbol}: обновлено время последней проверки")
            return
        
        # Добавляем новую монету в хранилище
        mature_coins_storage[symbol] = {
            'timestamp': time.time(),
            'maturity_data': maturity_data,
            'last_verified': time.time()
        }
    
    if auto_save:
        save_mature_coins_storage()
        logger.info(f"[MATURITY_STORAGE] Монета {symbol} добавлена в постоянное хранилище зрелых монет")
    else:
        logger.debug(f"[MATURITY_STORAGE] Монета {symbol} добавлена в хранилище (без автосохранения)")

def remove_mature_coin_from_storage(symbol):
    """Удаляет монету из постоянного хранилища зрелых монет"""
    global mature_coins_storage
    if symbol in mature_coins_storage:
        del mature_coins_storage[symbol]
        # Отключаем автоматическое сохранение - будет сохранено пакетно
        logger.debug(f"[MATURITY_STORAGE] Монета {symbol} удалена из хранилища (без автосохранения)")

def update_mature_coin_verification(symbol):
    """Обновляет время последней проверки зрелости монеты"""
    global mature_coins_storage
    if symbol in mature_coins_storage:
        mature_coins_storage[symbol]['last_verified'] = time.time()
        # Отключаем автоматическое сохранение - будет сохранено пакетно
        logger.debug(f"[MATURITY_STORAGE] Обновлено время проверки для {symbol} (без автосохранения)")

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
    """Получает оптимальные EMA периоды для монеты"""
    global optimal_ema_data
    if symbol in optimal_ema_data:
        data = optimal_ema_data[symbol]
        
        # Поддержка нового формата (ema_short_period, ema_long_period)
        if 'ema_short_period' in data and 'ema_long_period' in data:
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

def check_coin_maturity_with_storage(symbol, candles):
    """Проверяет зрелость монеты с использованием постоянного хранилища"""
    # Сначала проверяем постоянное хранилище
    if is_coin_mature_stored(symbol):
        logger.debug(f"[MATURITY_STORAGE] {symbol}: найдена в постоянном хранилище зрелых монет")
        # Обновляем время последней проверки
        update_mature_coin_verification(symbol)
        return {
            'is_mature': True,
            'reason': 'Монета зрелая (из постоянного хранилища)',
            'details': {'stored': True, 'from_storage': True}
        }
    
    # Если не в хранилище, выполняем полную проверку
    maturity_result = check_coin_maturity(symbol, candles)
    
    # Если монета зрелая, добавляем в постоянное хранилище (без автосохранения)
    if maturity_result['is_mature']:
        add_mature_coin_to_storage(symbol, maturity_result, auto_save=False)
    
    return maturity_result

def check_coin_maturity(symbol, candles):
    """Проверяет зрелость монеты для торговли"""
    try:
        # Получаем настройки зрелости из конфигурации
        with bots_data_lock:
            config = bots_data.get('auto_bot_config', {})
        
        min_candles = config.get('min_candles_for_maturity', MIN_CANDLES_FOR_MATURITY)
        min_rsi_low = config.get('min_rsi_low', MIN_RSI_LOW)
        max_rsi_high = config.get('max_rsi_high', MAX_RSI_HIGH)
        # Убрали min_volatility - больше не проверяем волатильность
        
        if not candles or len(candles) < min_candles:
            return {
                'is_mature': False,
                'reason': f'Недостаточно свечей: {len(candles) if candles else 0}/{min_candles}',
                'details': {
                    'candles_count': len(candles) if candles else 0,
                    'min_required': min_candles
                }
            }
        
        # Извлекаем цены закрытия
        closes = [candle['close'] for candle in candles]
        
        # Рассчитываем историю RSI
        rsi_history = calculate_rsi_history(closes, 14)
        if not rsi_history:
            return {
                'is_mature': False,
                'reason': 'Не удалось рассчитать историю RSI',
                'details': {}
            }
        
        # Анализируем диапазон RSI
        rsi_min = min(rsi_history)
        rsi_max = max(rsi_history)
        rsi_range = rsi_max - rsi_min
        
        # Проверяем критерии зрелости (убрали проверку волатильности)
        maturity_checks = {
            'sufficient_candles': len(candles) >= min_candles,
            'rsi_reached_low': rsi_min <= min_rsi_low,
            'rsi_reached_high': rsi_max >= max_rsi_high
        }
        
        # Убрали проверку волатильности - она была слишком строгой
        volatility = 0  # Для совместимости с детальной информацией
        
        # Определяем общую зрелость
        # Монета зрелая, если достаточно свечей И RSI достигал низких И высоких значений (полный цикл)
        is_mature = maturity_checks['sufficient_candles'] and maturity_checks['rsi_reached_low'] and maturity_checks['rsi_reached_high']
        
        # Детальное логирование для отладки (отключено для уменьшения спама)
        # logger.info(f"[MATURITY_DEBUG] {symbol}: свечи={maturity_checks['sufficient_candles']} ({len(candles)}/{min_candles}), RSI_low={maturity_checks['rsi_reached_low']} (min={rsi_min:.1f}<=>{min_rsi_low}), RSI_high={maturity_checks['rsi_reached_high']} (max={rsi_max:.1f}>={max_rsi_high}), зрелая={is_mature}")
        
        # Формируем детальную информацию
        details = {
            'candles_count': len(candles),
            'min_required': min_candles,
            'rsi_min': rsi_min,
            'rsi_max': rsi_max,
            'rsi_range': rsi_range,
            'checks': maturity_checks
        }
        
        # Определяем причину незрелости
        if not is_mature:
            failed_checks = [check for check, passed in maturity_checks.items() if not passed]
            reason = f'Не пройдены проверки: {", ".join(failed_checks)}'
        else:
            reason = 'Монета зрелая для торговли'
        
        logger.debug(f"[MATURITY] {symbol}: {reason}")
        logger.debug(f"[MATURITY] {symbol}: Свечи={len(candles)}, RSI={rsi_min:.1f}-{rsi_max:.1f}")
        
        return {
            'is_mature': is_mature,
            'reason': reason,
            'details': details
        }
        
    except Exception as e:
        logger.error(f"[MATURITY] Ошибка проверки зрелости {symbol}: {e}")
        return {
            'is_mature': False,
            'reason': f'Ошибка анализа: {str(e)}',
            'details': {}
        }

def calculate_ema(prices, period):
    """Рассчитывает EMA для массива цен"""
    if len(prices) < period:
        return None
    
    # Первое значение EMA = SMA
    sma = sum(prices[:period]) / period
    ema = sma
    multiplier = 2 / (period + 1)
    
    # Рассчитываем EMA для остальных значений
    for price in prices[period:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    
    return ema

def analyze_trend_6h(symbol, exchange_obj=None):
    """Анализирует тренд 6H с использованием оптимальных EMA периодов"""
    try:
        # Получаем оптимальные EMA периоды для монеты
        ema_periods = get_optimal_ema_periods(symbol)
        ema_short_period = ema_periods['ema_short']
        ema_long_period = ema_periods['ema_long']
        
        # Получаем свечи 6H для анализа тренда (нужно больше данных для длинной EMA)
        # Используем переданную биржу или глобальную переменную
        exchange_to_use = exchange_obj if exchange_obj else exchange
        if not exchange_to_use:
            logger.error(f"[TREND] ❌ Биржа не доступна для анализа тренда {symbol}")
            return None
            
        chart_response = exchange_to_use.get_chart_data(symbol, '6h', '60d')
        
        if not chart_response or not chart_response.get('success'):
            return None
        
        candles = chart_response['data']['candles']
        min_candles = max(ema_long_period + 50, 210)  # Минимум для длинной EMA + запас
        if not candles or len(candles) < min_candles:
            return None
        
        # Извлекаем цены закрытия
        closes = [candle['close'] for candle in candles]
        
        # Рассчитываем оптимальные EMA
        ema_short = calculate_ema(closes, ema_short_period)
        ema_long = calculate_ema(closes, ema_long_period)
        
        if ema_short is None or ema_long is None:
            return None
        
        current_close = closes[-1]
        
        # Проверяем наклон длинной EMA (сравниваем с предыдущим значением)
        if len(closes) >= ema_long_period + 1:
            prev_ema_long = calculate_ema(closes[:-1], ema_long_period)
            ema_long_slope = ema_long - prev_ema_long if prev_ema_long else 0
        else:
            ema_long_slope = 0
        
        # Проверяем минимум 3 закрытия подряд относительно длинной EMA
        recent_closes = closes[-TREND_CONFIRMATION_BARS:]
        all_above_ema_long = all(close > ema_long for close in recent_closes)
        all_below_ema_long = all(close < ema_long for close in recent_closes)
        
        # Определяем тренд согласно техзаданию
        trend = 'NEUTRAL'
        
        # UP: Close > EMA_long, EMA_short > EMA_long, наклон EMA_long > 0, минимум 3 закрытия > EMA_long
        if (current_close > ema_long and 
            ema_short > ema_long and 
            ema_long_slope > 0 and 
            all_above_ema_long):
            trend = 'UP'
        
        # DOWN: Close < EMA_long, EMA_short < EMA_long, наклон EMA_long < 0, минимум 3 закрытия < EMA_long
        elif (current_close < ema_long and 
              ema_short < ema_long and 
              ema_long_slope < 0 and 
              all_below_ema_long):
            trend = 'DOWN'
        
        return {
            'trend': trend,
            'ema_short': ema_short,
            'ema_long': ema_long,
            'ema_short_period': ema_short_period,
            'ema_long_period': ema_long_period,
            'ema_long_slope': ema_long_slope,
            'current_close': current_close,
            'confirmations': TREND_CONFIRMATION_BARS,
            'accuracy': ema_periods['accuracy']
        }
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка анализа тренда для {symbol}: {e}")
        return None

def perform_enhanced_rsi_analysis(candles, current_rsi, symbol):
    """Выполняет улучшенный анализ RSI для монеты"""
    try:
        # Проверяем, включена ли улучшенная система
        if not SystemConfig.ENHANCED_RSI_ENABLED:
            return {
                'enabled': False,
                'warning_type': None,
                'warning_message': None,
                'extreme_duration': 0,
                'adaptive_levels': None,
                'confirmations': {},
                'enhanced_signal': None
            }
        
        # Импортируем SignalGenerator для использования улучшенной логики
        from bot_engine.indicators import SignalGenerator, TechnicalIndicators
        
        # Создаем объект для анализа
        signal_generator = SignalGenerator()
        
        # Форматируем данные свечей для анализа
        # Bybit отправляет свечи в правильном порядке для анализа
        formatted_candles = []
        for candle in candles:  # Используем оригинальный порядок
            formatted_candles.append({
                'timestamp': candle.get('time', 0),
                'open': float(candle.get('open', 0)),
                'high': float(candle.get('high', 0)),
                'low': float(candle.get('low', 0)),
                'close': float(candle.get('close', 0)),
                'volume': float(candle.get('volume', 0))
            })
        
        # Получаем полный анализ
        if len(formatted_candles) >= 50:
            try:
                analysis_result = signal_generator.generate_signals(formatted_candles)
                
                # Получаем базовые данные для анализа
                closes = [candle['close'] for candle in formatted_candles]
                volumes = [candle['volume'] for candle in formatted_candles]
                
                # Рассчитываем дополнительные индикаторы
                rsi_history = TechnicalIndicators.calculate_rsi_history(formatted_candles)
                adaptive_levels = TechnicalIndicators.calculate_adaptive_rsi_levels(formatted_candles)
                divergence = TechnicalIndicators.detect_rsi_divergence(closes, rsi_history)
                volume_confirmation = TechnicalIndicators.confirm_with_volume(volumes)
                
                # Для Stochastic RSI используем ВСЮ историю RSI
                # Параметры Bybit: stoch_period=14, k_smooth=3, d_smooth=3
                stoch_rsi_result = TechnicalIndicators.calculate_stoch_rsi(
                    rsi_history, 
                    stoch_period=14, 
                    k_smooth=3,
                    d_smooth=3
                )
                stoch_rsi = stoch_rsi_result['k'] if stoch_rsi_result else None
                stoch_rsi_d = stoch_rsi_result['d'] if stoch_rsi_result else None
                
                
                # Определяем продолжительность в экстремальной зоне
                extreme_duration = 0
                if rsi_history:
                    for rsi_val in reversed(rsi_history):
                        if rsi_val <= RSI_EXTREME_OVERSOLD or rsi_val >= RSI_EXTREME_OVERBOUGHT:
                            extreme_duration += 1
                        else:
                            break
                
                # Определяем тип предупреждения
                warning_type = None
                warning_message = None
            
                # Проверяем экстремальные условия
                if current_rsi <= RSI_EXTREME_OVERSOLD:
                    if extreme_duration > RSI_EXTREME_ZONE_TIMEOUT:
                        warning_type = 'EXTREME_OVERSOLD_LONG'
                        warning_message = f'RSI в экстремальной зоне {extreme_duration} свечей'
                    else:
                        warning_type = 'OVERSOLD'
                        warning_message = 'Возможная зона для LONG'
                        
                elif current_rsi >= RSI_EXTREME_OVERBOUGHT:
                    if extreme_duration > RSI_EXTREME_ZONE_TIMEOUT:
                        warning_type = 'EXTREME_OVERBOUGHT_LONG'
                        warning_message = f'RSI в экстремальной зоне {extreme_duration} свечей'
                    else:
                        warning_type = 'OVERBOUGHT'
                        warning_message = 'Возможная зона для SHORT'
                
                # Анализ подтверждений (явно преобразуем в стандартные Python типы)
                confirmations = {
                    'volume': bool(volume_confirmation) if volume_confirmation is not None else False,
                    'divergence': bool(divergence) if divergence is not None else False,
                    'stoch_rsi_k': float(stoch_rsi) if stoch_rsi is not None else None,
                    'stoch_rsi_d': float(stoch_rsi_d) if stoch_rsi_d is not None else None
                }
                
                return {
                    'enabled': True,
                    'warning_type': warning_type,
                    'warning_message': warning_message,
                    'extreme_duration': int(extreme_duration),
                    'adaptive_levels': adaptive_levels,
                    'confirmations': confirmations,
                    'enhanced_signal': analysis_result.get('signal', 'WAIT'),
                    'enhanced_reason': analysis_result.get('reason', 'enhanced_analysis')
                }
                
            except Exception as e:
                logger.error(f"[ENHANCED_RSI] Ошибка анализа для {symbol}: {e}")
                return {
                    'enabled': True,
                    'warning_type': 'ERROR',
                    'warning_message': f'Ошибка анализа: {str(e)}',
                    'extreme_duration': 0,
                    'adaptive_levels': [29, 71],
                    'confirmations': {
                        'volume': False,
                        'divergence': False,
                        'stoch_rsi_k': None,
                        'stoch_rsi_d': None
                    },
                    'enhanced_signal': 'WAIT'
                }
        else:
            # Недостаточно данных для полного анализа
            return {
                'enabled': True,
                'warning_type': None,
                'warning_message': 'Недостаточно данных для анализа',
                'extreme_duration': 0,
                'adaptive_levels': [29, 71],
                'confirmations': {
                    'volume': False,
                    'divergence': False,
                    'stoch_rsi_k': None,
                    'stoch_rsi_d': None
                },
                'enhanced_signal': 'WAIT'
            }
            
    except Exception as e:
        logger.error(f"[ENHANCED_RSI] Ошибка анализа для {symbol}: {e}")
        return {
            'enabled': False,
            'warning_type': 'ERROR',
            'warning_message': f'Ошибка анализа: {str(e)}',
            'extreme_duration': 0,
            'adaptive_levels': [29, 71],
            'confirmations': {},
            'enhanced_signal': 'WAIT'
        }

def check_rsi_time_filter(candles, rsi, signal):
    """
    Проверяет сложный временной фильтр для RSI сигналов.
    
    СЛОЖНАЯ ЛОГИКА:
    1. Найти последнюю свечу где RSI был в экстремальной зоне (≥71 для SHORT, ≤29 для LONG)
    2. Отсчитать N свечей после неё (из конфига)
    3. Проверить ВСЕ N свечей - должны быть в разрешенной зоне (≥65 для SHORT, ≤35 для LONG)
    4. Если хотя бы одна свеча не в зоне → искать заново
    
    Args:
        candles: Список свечей
        rsi: Текущее значение RSI
        signal: Торговый сигнал ('ENTER_LONG' или 'ENTER_SHORT')
    
    Returns:
        dict: {'allowed': bool, 'reason': str, 'last_extreme_candles_ago': int}
    """
    try:
        # Получаем настройки из конфига
        with bots_data_lock:
            rsi_time_filter_enabled = bots_data.get('auto_bot_config', {}).get('rsi_time_filter_enabled', True)
            rsi_time_filter_candles = bots_data.get('auto_bot_config', {}).get('rsi_time_filter_candles', 8)
            rsi_time_filter_upper = bots_data.get('auto_bot_config', {}).get('rsi_time_filter_upper', 65)  # Граница для SHORT
            rsi_time_filter_lower = bots_data.get('auto_bot_config', {}).get('rsi_time_filter_lower', 35)  # Граница для LONG
            rsi_long_threshold = bots_data.get('auto_bot_config', {}).get('rsi_long_threshold', 29)  # Экстремум для LONG
            rsi_short_threshold = bots_data.get('auto_bot_config', {}).get('rsi_short_threshold', 71)  # Экстремум для SHORT
        
        # Если фильтр отключен - разрешаем сделку
        if not rsi_time_filter_enabled:
            return {'allowed': True, 'reason': 'RSI временной фильтр отключен', 'last_extreme_candles_ago': None}
        
        if len(candles) < 50:  # Нужно больше свечей для сложного анализа
            return {'allowed': False, 'reason': 'Недостаточно свечей для анализа', 'last_extreme_candles_ago': None}
        
        # Рассчитываем историю RSI
        closes = [candle['close'] for candle in candles]
        rsi_history = calculate_rsi_history(closes, 14)
        
        min_rsi_history = max(rsi_time_filter_candles * 2 + 14, 30)  # Минимум для анализа
        if not rsi_history or len(rsi_history) < min_rsi_history:
            return {'allowed': False, 'reason': f'Недостаточно RSI истории (требуется {min_rsi_history})', 'last_extreme_candles_ago': None}
        
        if signal == 'ENTER_SHORT':
            # ИСПРАВЛЕННАЯ ЛОГИКА ДЛЯ SHORT:
            # 1. Найти САМУЮ ПОСЛЕДНЮЮ свечу где RSI был >= 71
            # 2. От этой свечи отсчитать 8 свечей ВПЕРЕД
            # 3. Проверить что ВСЕ 8 свечей после неё имеют RSI >= 65
            
            # Ищем САМУЮ ПОСЛЕДНЮЮ свечу с RSI >= 71
            last_extreme_index = None
            for i in range(len(rsi_history) - 1, -1, -1):  # Идем с конца к началу
                if rsi_history[i] >= rsi_short_threshold:
                    last_extreme_index = i
                    break  # Нашли самую последнюю - выходим
            
            if last_extreme_index is None:
                # Не найдено свечей с RSI >= 71 - разрешаем
                return {
                    'allowed': True, 
                    'reason': f'Разрешено: не найдено свечей с RSI >= {rsi_short_threshold}', 
                    'last_extreme_candles_ago': None
                }
            
            # Проверяем, что после экстремума есть достаточно свечей для проверки
            candles_after_extreme = len(rsi_history) - 1 - last_extreme_index
            
            if candles_after_extreme < rsi_time_filter_candles:
                # Недостаточно свечей после экстремума - блокируем
                return {
                    'allowed': False, 
                    'reason': f'Блокировка: после последнего RSI >= {rsi_short_threshold} прошло только {candles_after_extreme} свечей (требуется {rsi_time_filter_candles})', 
                    'last_extreme_candles_ago': candles_after_extreme
                }
            
            # Проверяем N свечей НАЧИНАЯ С экстремума (включая его)
            # Берем свечи от экстремума до экстремума + N
            start_index = last_extreme_index
            end_index = last_extreme_index + rsi_time_filter_candles
            
            if end_index >= len(rsi_history):
                # Недостаточно свечей для проверки - блокируем
                return {
                    'allowed': False, 
                    'reason': f'Блокировка: недостаточно свечей для проверки после экстремума', 
                    'last_extreme_candles_ago': candles_after_extreme
                }
            
            # Проверяем все N свечей начиная с экстремума
            check_candles = rsi_history[start_index:end_index + 1]
            valid_candles = sum(1 for rsi_val in check_candles if rsi_val >= rsi_time_filter_upper)
            
            if valid_candles >= rsi_time_filter_candles:
                # Все N свечей (включая экстремум) >= 65 - разрешаем
                return {
                    'allowed': True, 
                    'reason': f'Разрешено: {rsi_time_filter_candles} свечей начиная с последнего RSI >= {rsi_short_threshold} все >= {rsi_time_filter_upper}', 
                    'last_extreme_candles_ago': candles_after_extreme
                }
            else:
                # Не все свечи соответствуют - блокируем
                return {
                    'allowed': False, 
                    'reason': f'Блокировка: в последних {rsi_time_filter_candles} свечах только {valid_candles}/{rsi_time_filter_candles} были >= {rsi_time_filter_upper}', 
                    'last_extreme_candles_ago': candles_since_extreme
                }
                
        elif signal == 'ENTER_LONG':
            # ИСПРАВЛЕННАЯ ЛОГИКА ДЛЯ LONG:
            # 1. Найти САМУЮ ПОСЛЕДНЮЮ свечу где RSI был <= 29
            # 2. От этой свечи отсчитать 8 свечей ВПЕРЕД
            # 3. Проверить что ВСЕ 8 свечей после неё имеют RSI <= 35
            
            # Ищем САМУЮ ПОСЛЕДНЮЮ свечу с RSI <= 29
            last_extreme_index = None
            for i in range(len(rsi_history) - 1, -1, -1):  # Идем с конца к началу
                if rsi_history[i] <= rsi_long_threshold:
                    last_extreme_index = i
                    break  # Нашли самую последнюю - выходим
            
            if last_extreme_index is None:
                # Не найдено свечей с RSI <= 29 - разрешаем
                return {
                    'allowed': True, 
                    'reason': f'Разрешено: не найдено свечей с RSI <= {rsi_long_threshold}', 
                    'last_extreme_candles_ago': None
                }
            
            # Проверяем, что после экстремума есть достаточно свечей для проверки
            candles_after_extreme = len(rsi_history) - 1 - last_extreme_index
            
            if candles_after_extreme < rsi_time_filter_candles:
                # Недостаточно свечей после экстремума - блокируем
                return {
                    'allowed': False, 
                    'reason': f'Блокировка: после последнего RSI <= {rsi_long_threshold} прошло только {candles_after_extreme} свечей (требуется {rsi_time_filter_candles})', 
                    'last_extreme_candles_ago': candles_after_extreme
                }
            
            # Проверяем N свечей НАЧИНАЯ С экстремума (включая его)
            # Берем свечи от экстремума до экстремума + N
            start_index = last_extreme_index
            end_index = last_extreme_index + rsi_time_filter_candles
            
            if end_index >= len(rsi_history):
                # Недостаточно свечей для проверки - блокируем
                return {
                    'allowed': False, 
                    'reason': f'Блокировка: недостаточно свечей для проверки после экстремума', 
                    'last_extreme_candles_ago': candles_after_extreme
                }
            
            # Проверяем все N свечей начиная с экстремума
            check_candles = rsi_history[start_index:end_index + 1]
            valid_candles = sum(1 for rsi_val in check_candles if rsi_val <= rsi_time_filter_lower)
            
            if valid_candles >= rsi_time_filter_candles:
                # Все N свечей (включая экстремум) <= 35 - разрешаем
                return {
                    'allowed': True, 
                    'reason': f'Разрешено: {rsi_time_filter_candles} свечей начиная с последнего RSI <= {rsi_long_threshold} все <= {rsi_time_filter_lower}', 
                    'last_extreme_candles_ago': candles_after_extreme
                }
            else:
                # Не все свечи соответствуют - блокируем
                return {
                    'allowed': False, 
                    'reason': f'Блокировка: в последних {rsi_time_filter_candles} свечах только {valid_candles}/{rsi_time_filter_candles} были <= {rsi_time_filter_lower}', 
                    'last_extreme_candles_ago': candles_after_extreme
                }
        
        return {'allowed': True, 'reason': 'Неизвестный сигнал', 'last_extreme_candles_ago': None}
    
    except Exception as e:
        logger.error(f"[RSI_TIME_FILTER] Ошибка проверки временного фильтра: {e}")
        return {'allowed': False, 'reason': f'Ошибка анализа: {str(e)}', 'last_extreme_candles_ago': None}

def get_coin_rsi_data(symbol, exchange_obj=None):
    """Получает RSI данные для одной монеты (6H таймфрейм)"""
    try:
        # Минимальная задержка для избежания API Rate Limit
        time.sleep(0.1)  # Было 0.5 сек, стало 0.1 сек
        
        # logger.debug(f"[DEBUG] Обработка {symbol}...")  # Отключено для ускорения
        
        # Используем переданную биржу или глобальную
        exchange_to_use = exchange_obj if exchange_obj is not None else exchange
        
        # Проверяем, что биржа доступна
        if exchange_to_use is None:
            logger.error(f"[ERROR] Ошибка получения данных для {symbol}: 'NoneType' object has no attribute 'get_chart_data'")
            return None
        
        # Получаем свечи 6H для расчета RSI
        chart_response = exchange_to_use.get_chart_data(symbol, '6h', '30d')
        
        if not chart_response or not chart_response.get('success'):
            logger.debug(f"[WARNING] Не удалось получить данные для {symbol}: {chart_response.get('error', 'Неизвестная ошибка') if chart_response else 'Нет ответа'}")
            return None
        
        candles = chart_response['data']['candles']
        if not candles or len(candles) < 15:  # Базовая проверка для RSI(14)
            logger.debug(f"[WARNING] Недостаточно свечей для {symbol}: {len(candles) if candles else 0}/15")
            return None
        
        # Рассчитываем RSI для 6H
        # Bybit отправляет свечи в правильном порядке для RSI (от старой к новой)
        closes = [candle['close'] for candle in candles]
        
        rsi = calculate_rsi(closes, 14)
        
        if rsi is None:
            logger.warning(f"[WARNING] Не удалось рассчитать RSI для {symbol}")
            return None
        
        # Получаем полный анализ тренда 6H
        trend_analysis = analyze_trend_6h(symbol, exchange_obj=exchange_obj)
        trend = trend_analysis['trend'] if trend_analysis else 'NEUTRAL'
        
        # Рассчитываем изменение за 24h (примерно 4 свечи 6H)
        change_24h = 0
        if len(closes) >= 5:
            change_24h = round(((closes[-1] - closes[-5]) / closes[-5]) * 100, 2)
        
        # Выполняем улучшенный анализ RSI
        enhanced_analysis = perform_enhanced_rsi_analysis(candles, rsi, symbol)
        
        # Определяем RSI зоны согласно техзаданию
        rsi_zone = 'NEUTRAL'
        signal = 'WAIT'
        
        # Проверяем временной фильтр для потенциальных сигналов
        time_filter_info = None
        if rsi <= RSI_OVERSOLD:
            time_filter_result = check_rsi_time_filter(candles, rsi, 'ENTER_LONG')
            time_filter_info = {
                'allowed': time_filter_result['allowed'],
                'reason': time_filter_result['reason'],
                'last_extreme_candles_ago': time_filter_result.get('last_extreme_candles_ago')
            }
            # ОТЛАДКА: Логируем результат временного фильтра для LONG
            if symbol in ['BAT']:  # Только для BAT для отладки
                logger.info(f"[DEBUG_TIME_FILTER] {symbol}: LONG - allowed={time_filter_result['allowed']}, reason='{time_filter_result['reason']}', last_extreme={time_filter_result.get('last_extreme_candles_ago')}")
        elif rsi >= RSI_OVERBOUGHT:
            time_filter_result = check_rsi_time_filter(candles, rsi, 'ENTER_SHORT')
            time_filter_info = {
                'allowed': time_filter_result['allowed'],
                'reason': time_filter_result['reason'],
                'last_extreme_candles_ago': time_filter_result.get('last_extreme_candles_ago')
            }
            # ОТЛАДКА: Логируем результат временного фильтра для SHORT
            if symbol in ['BAT']:  # Только для BAT для отладки
                logger.info(f"[DEBUG_TIME_FILTER] {symbol}: SHORT - allowed={time_filter_result['allowed']}, reason='{time_filter_result['reason']}', last_extreme={time_filter_result.get('last_extreme_candles_ago')}")
        
        # Логика с опциональным учетом тренда
        # Получаем настройки фильтров по тренду (по умолчанию включены)
        with bots_data_lock:
            avoid_down_trend = bots_data.get('auto_bot_config', {}).get('avoid_down_trend', True)
            avoid_up_trend = bots_data.get('auto_bot_config', {}).get('avoid_up_trend', True)
        
        # Восстанавливаем правильную логику фильтров по тренду
        # avoid_down_trend = False  # УБРАНО - используем настройки
        # avoid_up_trend = False    # УБРАНО - используем настройки
        
        if rsi <= RSI_OVERSOLD:  # RSI ≤ 29 
            rsi_zone = 'BUY_ZONE'
            # Проверяем нужно ли избегать DOWN тренда для LONG
            if avoid_down_trend and trend == 'DOWN':
                signal = 'WAIT'  # Ждем улучшения тренда
            else:
                signal = 'ENTER_LONG'  # Входим независимо от тренда или при хорошем тренде
        elif rsi >= RSI_OVERBOUGHT:  # RSI ≥ 71
            rsi_zone = 'SELL_ZONE'
            # Проверяем нужно ли избегать UP тренда для SHORT
            if avoid_up_trend and trend == 'UP':
                signal = 'WAIT'  # Ждем ослабления тренда
            else:
                signal = 'ENTER_SHORT'  # Входим независимо от тренда или при хорошем тренде
        # RSI между 30 и 70 - нейтральная зона
        
        # Проверяем зрелость монеты ДЛЯ ВСЕХ МОНЕТ при каждой загрузке
        with bots_data_lock:
            enable_maturity_check = bots_data.get('auto_bot_config', {}).get('enable_maturity_check', True)
        
        # Проверяем зрелость монеты (БЕЗ добавления в хранилище при загрузке RSI!)
        if enable_maturity_check:
            # ✅ ИСПРАВЛЕНИЕ: Используем check_coin_maturity напрямую (без хранилища)
            # Добавление в хранилище только при создании бота!
            maturity_check = check_coin_maturity(symbol, candles)
            
            if maturity_check['is_mature']:
                logger.debug(f"[MATURITY] {symbol}: Монета зрелая - {maturity_check['reason']}")
            else:
                logger.debug(f"[MATURITY] {symbol}: Монета незрелая - {maturity_check['reason']}")
            
            # Блокируем сигналы только для незрелых монет
            if not maturity_check['is_mature'] and signal in ['ENTER_LONG', 'ENTER_SHORT']:
                logger.debug(f"[MATURITY] {symbol}: {maturity_check['reason']} - сигнал {signal} заблокирован")
                # Меняем сигнал на WAIT, но не исключаем монету из списка
                signal = 'WAIT'
                rsi_zone = 'NEUTRAL'
        
        # Получаем оптимальные EMA периоды для монеты
        ema_periods = get_optimal_ema_periods(symbol)
        
        # closes[-1] - это самая НОВАЯ цена (последняя свеча в массиве)
        current_price = closes[-1]
        
        result = {
            'symbol': symbol,
            'rsi6h': round(rsi, 1),
            'trend6h': trend,
            'rsi_zone': rsi_zone,
            'signal': signal,
            'price': current_price,
            'change24h': change_24h,
            'last_update': datetime.now().isoformat(),
            'trend_analysis': trend_analysis,
            'ema_periods': {
                'ema_short': ema_periods['ema_short'],
                'ema_long': ema_periods['ema_long'],
                'accuracy': ema_periods['accuracy'],
                'analysis_method': ema_periods['analysis_method']
            },
            # Добавляем результаты улучшенного анализа RSI
            'enhanced_rsi': enhanced_analysis,
            # Добавляем информацию о временном фильтре
            'time_filter_info': time_filter_info
        }
        
        # Логируем торговые сигналы и блокировки тренда
        trend_emoji = '📈' if trend == 'UP' else '📉' if trend == 'DOWN' else '➡️'
        
        if signal in ['ENTER_LONG', 'ENTER_SHORT']:
            logger.info(f"[SIGNAL] 🎯 {symbol}: RSI={rsi:.1f} {trend_emoji}{trend} (${current_price:.4f}) → {signal}")
        elif signal == 'WAIT' and rsi <= RSI_OVERSOLD and trend == 'DOWN' and avoid_down_trend:
            logger.debug(f"[FILTER] 🚫 {symbol}: RSI={rsi:.1f} {trend_emoji}{trend} LONG заблокирован (фильтр DOWN тренда)")
        elif signal == 'WAIT' and rsi >= RSI_OVERBOUGHT and trend == 'UP' and avoid_up_trend:
            logger.debug(f"[FILTER] 🚫 {symbol}: RSI={rsi:.1f} {trend_emoji}{trend} SHORT заблокирован (фильтр UP тренда)")
        
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка получения данных для {symbol}: {e}")
        return None

def load_all_coins_rsi():
    """Загружает RSI 6H для всех доступных монет"""
    global coins_rsi_data
    
    try:
        with rsi_data_lock:
            if coins_rsi_data['update_in_progress']:
                logger.info("Обновление RSI уже выполняется...")
                return False
            coins_rsi_data['update_in_progress'] = True
        
        logger.info("[RSI] 🔄 Начинаем загрузку RSI 6H для всех монет...")
        
        # Получаем список всех пар
        if not exchange:
            logger.error("[RSI] ❌ Биржа не инициализирована")
            return False
            
        pairs = exchange.get_all_pairs()
        logger.info(f"[RSI] 🔍 Получено пар с биржи: {len(pairs) if pairs else 0}")
        
        if not pairs or not isinstance(pairs, list):
            logger.error("[RSI] ❌ Не удалось получить список пар с биржи")
            return False
        
        logger.info(f"[RSI] 📊 Найдено {len(pairs)} торговых пар для анализа")
        
        # Обновляем счетчики
        with rsi_data_lock:
            coins_rsi_data['total_coins'] = len(pairs)
            coins_rsi_data['successful_coins'] = 0
            coins_rsi_data['failed_coins'] = 0
        
        # Получаем RSI данные для всех пар пакетно с инкрементальным обновлением
        batch_size = 50  # Увеличиваем размер пакета для ускорения загрузки
        
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(pairs) + batch_size - 1)//batch_size
            
            logger.info(f"[BATCH] Обработка пакета {batch_num}/{total_batches} ({len(batch)} монет)")
            
            # Параллельная загрузка RSI для пакета (3 воркера для ускорения)
            batch_coins_data = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_symbol = {executor.submit(get_coin_rsi_data, symbol): symbol for symbol in batch}
                
                # Уменьшаем таймауты для ускорения (2 минуты для пакета, 15 секунд на монету)
                try:
                    for future in concurrent.futures.as_completed(future_to_symbol, timeout=120):
                        try:
                            result = future.result(timeout=15)  # Уменьшаем до 15 секунд
                            if result:
                                batch_coins_data[result['symbol']] = result
                                
                                # ✅ ДОБАВЛЕНИЕ В ХРАНИЛИЩЕ: Если монета зрелая, добавляем в mature_coins_storage
                                symbol = result['symbol']
                                signal = result.get('signal', 'WAIT')
                                
                                # Проверяем, что монета прошла проверку зрелости (сигнал не WAIT из-за незрелости)
                                # Если сигнал ENTER_LONG или ENTER_SHORT - монета точно зрелая
                                if signal in ['ENTER_LONG', 'ENTER_SHORT']:
                                    add_mature_coin_to_storage(symbol, signal)
                                
                                with rsi_data_lock:
                                    coins_rsi_data['successful_coins'] += 1
                            else:
                                with rsi_data_lock:
                                    coins_rsi_data['failed_coins'] += 1
                        except concurrent.futures.TimeoutError:
                            symbol = future_to_symbol[future]
                            # logger.warning(f"⏰ Таймаут для {symbol} (пропускаем)")  # Отключено для чистоты логов
                            with rsi_data_lock:
                                coins_rsi_data['failed_coins'] += 1
                        except Exception as e:
                            symbol = future_to_symbol[future]
                            # logger.warning(f"[WARNING] Ошибка обработки {symbol}: {e}")  # Отключено для чистоты логов
                            with rsi_data_lock:
                                coins_rsi_data['failed_coins'] += 1
                except concurrent.futures.TimeoutError:
                    # Обработка таймаута всего пакета
                    unfinished = len([f for f in future_to_symbol.keys() if not f.done()])
                    logger.warning(f"⏰ Таймаут пакета! Не завершено: {unfinished} из {len(batch)} монет")
                    with rsi_data_lock:
                        coins_rsi_data['failed_coins'] += unfinished
            
            # ИНКРЕМЕНТАЛЬНОЕ ОБНОВЛЕНИЕ: Обновляем данные после каждого пакета
            with rsi_data_lock:
                coins_rsi_data['coins'].update(batch_coins_data)
                coins_rsi_data['last_update'] = datetime.now().isoformat()
                logger.info(f"[INCREMENTAL] Обновлено {len(batch_coins_data)} монет из пакета {batch_num}")
            
            # Пауза между пакетами для предотвращения rate limiting
            time.sleep(2.0)  # 2 секунды между пакетами (было 10 сек)
            
            # Логируем прогресс каждые 5 пакетов (чаще для инкрементального обновления)
            if batch_num % 5 == 0:
                with rsi_data_lock:
                    success_count = coins_rsi_data['successful_coins']
                    failed_count = coins_rsi_data['failed_coins']
                    total_processed = success_count + failed_count
                    progress_percent = round((total_processed / len(pairs)) * 100, 1)
                    coins_count = len(coins_rsi_data['coins'])
                    logger.info(f"[RSI] ⏳ Прогресс: {progress_percent}% ({total_processed}/{len(pairs)}) - В UI доступно {coins_count} монет")
        
        # Финальное обновление флага
        with rsi_data_lock:
            coins_rsi_data['update_in_progress'] = False
        
        logger.info(f"[RSI] ✅ Обновление завершено, флаг update_in_progress сброшен")
        
        # Финальный отчет
        with rsi_data_lock:
            success_count = coins_rsi_data['successful_coins']
            failed_count = coins_rsi_data['failed_coins']
            
        # Подсчитываем сигналы
        with rsi_data_lock:
            enter_long_count = sum(1 for coin in coins_rsi_data['coins'].values() if coin.get('signal') == 'ENTER_LONG')
            enter_short_count = sum(1 for coin in coins_rsi_data['coins'].values() if coin.get('signal') == 'ENTER_SHORT')
        
        logger.info(f"[RSI] ✅ Загрузка завершена: {success_count}/{len(pairs)} монет | Сигналы: {enter_long_count} LONG + {enter_short_count} SHORT")
        
        if failed_count > 0:
            logger.warning(f"[RSI] ⚠️ Ошибок: {failed_count} монет")
        
        # Сохраняем RSI данные в кэш
        save_rsi_cache()
        
        # Обрабатываем торговые сигналы для существующих ботов
        process_trading_signals_for_all_bots(exchange_obj=exchange)
        
        # Проверяем автобот сигналы для создания новых ботов
        process_auto_bot_signals(exchange_obj=exchange)  # ВКЛЮЧЕНО!
        
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка загрузки RSI данных: {str(e)}")
        with rsi_data_lock:
            coins_rsi_data['update_in_progress'] = False
    finally:
        # Гарантированно сбрасываем флаг обновления
        with rsi_data_lock:
            if coins_rsi_data['update_in_progress']:
                logger.warning(f"[RSI] ⚠️ Принудительный сброс флага update_in_progress")
                coins_rsi_data['update_in_progress'] = False
        return False

def get_effective_signal(coin):
    """
    Универсальная функция для определения эффективного сигнала монеты
    
    ЛОГИКА ПРОВЕРКИ ТРЕНДОВ (упрощенная):
    - НЕ открываем SHORT если RSI > 71 И тренд = UP
    - НЕ открываем LONG если RSI < 29 И тренд = DOWN
    - NEUTRAL тренд разрешает любые сделки
    - Тренд только усиливает возможность, но не блокирует полностью
    
    Args:
        coin (dict): Данные монеты
        
    Returns:
        str: Эффективный сигнал (ENTER_LONG, ENTER_SHORT, WAIT)
    """
    symbol = coin.get('symbol', 'UNKNOWN')
    
    # Получаем настройки автобота
    with bots_data_lock:
        auto_config = bots_data.get('auto_bot_config', {})
        avoid_down_trend = auto_config.get('avoid_down_trend', True)
        avoid_up_trend = auto_config.get('avoid_up_trend', True)
        rsi_long_threshold = auto_config.get('rsi_long_threshold', 29)
        rsi_short_threshold = auto_config.get('rsi_short_threshold', 71)
        
    # Получаем данные монеты
    rsi = coin.get('rsi6h', 50)
    trend = coin.get('trend', coin.get('trend6h', 'NEUTRAL'))
    
    # ✅ КРИТИЧЕСКАЯ ПРОВЕРКА: Если базовый сигнал WAIT (из-за незрелости) - возвращаем сразу
    # Это блокирует Enhanced RSI от переопределения сигнала для незрелых монет
    base_signal = coin.get('signal', 'WAIT')
    if base_signal == 'WAIT':
            return 'WAIT'
        
    # Проверяем Enhanced RSI сигнал (приоритет только для зрелых монет)
    enhanced_rsi = coin.get('enhanced_rsi', {})
    if enhanced_rsi.get('enabled') and enhanced_rsi.get('enhanced_signal'):
        signal = enhanced_rsi.get('enhanced_signal')
    else:
        # Используем базовый сигнал
        signal = base_signal
    
    # Если сигнал WAIT - возвращаем сразу
    if signal == 'WAIT':
        return signal
    
    # УПРОЩЕННАЯ ПРОВЕРКА ТРЕНДОВ - только экстремальные случаи
    if signal == 'ENTER_SHORT' and avoid_up_trend and rsi >= rsi_short_threshold and trend == 'UP':
        logger.debug(f"[SIGNAL] {symbol}: ❌ SHORT заблокирован (RSI={rsi:.1f} >= {rsi_short_threshold} + UP тренд)")
        return 'WAIT'
    
    if signal == 'ENTER_LONG' and avoid_down_trend and rsi <= rsi_long_threshold and trend == 'DOWN':
        logger.debug(f"[SIGNAL] {symbol}: ❌ LONG заблокирован (RSI={rsi:.1f} <= {rsi_long_threshold} + DOWN тренд)")
        return 'WAIT'
    
    # Все проверки пройдены
    logger.debug(f"[SIGNAL] {symbol}: ✅ {signal} разрешен (RSI={rsi:.1f}, Trend={trend})")
    return signal

def process_auto_bot_signals(exchange_obj=None):
    """Новая логика автобота согласно требованиям"""
    try:
        # Проверяем, включен ли автобот
        with bots_data_lock:
            auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            
            if not auto_bot_enabled:
                logger.debug("[NEW_AUTO] ⏹️ Автобот выключен")
                return
            
            max_concurrent = bots_data['auto_bot_config']['max_concurrent']
            current_active = sum(1 for bot in bots_data['bots'].values() 
                               if bot['status'] not in [BOT_STATUS['IDLE'], BOT_STATUS['PAUSED']])
            
            if current_active >= max_concurrent:
                logger.debug(f"[NEW_AUTO] 🚫 Достигнут лимит активных ботов ({current_active}/{max_concurrent})")
                return
        
        logger.info("[NEW_AUTO] 🔍 Проверка сигналов для создания новых ботов...")
        
        # Получаем монеты с сигналами
        potential_coins = []
        with rsi_data_lock:
            for symbol, coin_data in coins_rsi_data['coins'].items():
                rsi = coin_data.get('rsi6h')
                trend = coin_data.get('trend6h', 'NEUTRAL')
                
                if rsi is None:
                    continue
                
                # Проверяем сигналы
                with bots_data_lock:
                    auto_config = bots_data['auto_bot_config']
                    rsi_long_threshold = auto_config.get('rsi_long_threshold', 29)
                    rsi_short_threshold = auto_config.get('rsi_short_threshold', 71)
                
                signal = None
                if rsi <= rsi_long_threshold:
                    signal = 'ENTER_LONG'
                elif rsi >= rsi_short_threshold:
                    signal = 'ENTER_SHORT'
                
                if signal:
                    # Проверяем дополнительные условия
                    if check_new_autobot_filters(symbol, signal, coin_data):
                        potential_coins.append({
                            'symbol': symbol,
                            'rsi': rsi,
                            'trend': trend,
                            'signal': signal,
                            'coin_data': coin_data
                        })
        
        logger.info(f"[NEW_AUTO] 🎯 Найдено {len(potential_coins)} потенциальных сигналов")
        
        # Создаем ботов для найденных сигналов
        created_bots = 0
        for coin in potential_coins[:max_concurrent - current_active]:
            symbol = coin['symbol']
            
            # Проверяем, нет ли уже бота для этого символа
            with bots_data_lock:
                if symbol in bots_data['bots']:
                    logger.debug(f"[NEW_AUTO] ⚠️ Бот для {symbol} уже существует")
                    continue
            
            # Создаем нового бота
            try:
                logger.info(f"[NEW_AUTO] 🚀 Создаем бота для {symbol} ({coin['signal']}, RSI: {coin['rsi']:.1f})")
                create_new_bot(symbol, exchange_obj=exchange_obj)
                created_bots += 1
                
            except Exception as e:
                logger.error(f"[NEW_AUTO] ❌ Ошибка создания бота для {symbol}: {e}")
        
        if created_bots > 0:
            logger.info(f"[NEW_AUTO] ✅ Создано {created_bots} новых ботов")
        
    except Exception as e:
        logger.error(f"[NEW_AUTO] ❌ Ошибка обработки сигналов: {e}")

def process_trading_signals_for_all_bots(exchange_obj=None):
    """Обрабатывает торговые сигналы для всех активных ботов с новым классом"""
    try:
        # Проверяем, инициализирована ли система
        if not system_initialized:
            logger.warning("[NEW_BOT_SIGNALS] ⏳ Система еще не инициализирована - пропускаем обработку")
            return
        
        with bots_data_lock:
            # Фильтруем только активных ботов (исключаем IDLE и PAUSED)
            active_bots = {symbol: bot for symbol, bot in bots_data['bots'].items() 
                          if bot['status'] not in [BOT_STATUS['IDLE'], BOT_STATUS['PAUSED']]}
        
        if not active_bots:
            logger.debug("[NEW_BOT_SIGNALS] ⏳ Нет активных ботов для обработки")
            return
        
        logger.info(f"[NEW_BOT_SIGNALS] 🔍 Обрабатываем {len(active_bots)} активных ботов: {list(active_bots.keys())}")
        
        for symbol, bot_data in active_bots.items():
            try:
                logger.debug(f"[NEW_BOT_SIGNALS] 🔍 Обрабатываем бота {symbol}...")
                
                # Используем переданную биржу или глобальную переменную
                exchange_to_use = exchange_obj if exchange_obj else exchange
                
                # Создаем экземпляр нового бота из сохраненных данных
                trading_bot = NewTradingBot(symbol, bot_data, exchange_to_use)
                
                # Получаем RSI данные для монеты
                rsi_data = None
                with rsi_data_lock:
                    rsi_data = coins_rsi_data['coins'].get(symbol)
                
                if not rsi_data:
                    logger.debug(f"[NEW_BOT_SIGNALS] ❌ {symbol}: RSI данные не найдены")
                    continue
                
                logger.debug(f"[NEW_BOT_SIGNALS] ✅ {symbol}: RSI={rsi_data.get('rsi6h')}, Trend={rsi_data.get('trend6h')}")
                
                # Обрабатываем торговые сигналы через метод update
                external_signal = rsi_data.get('signal')
                external_trend = rsi_data.get('trend6h')
                
                signal_result = trading_bot.update(
                    force_analysis=True, 
                    external_signal=external_signal, 
                    external_trend=external_trend
                )
                
                logger.debug(f"[NEW_BOT_SIGNALS] 🔄 {symbol}: Результат update: {signal_result}")
                
                # Обновляем данные бота в хранилище если есть изменения
                if signal_result and signal_result.get('success', False):
                    with bots_data_lock:
                        bots_data['bots'][symbol] = trading_bot.to_dict()
                    
                    # Логируем торговые действия
                    action = signal_result.get('action')
                    if action in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE_LONG', 'CLOSE_SHORT']:
                        logger.info(f"[NEW_BOT_SIGNALS] 🎯 {symbol}: {action} выполнено")
                else:
                    logger.debug(f"[NEW_BOT_SIGNALS] ⏳ {symbol}: Нет торговых сигналов")
                        
            except Exception as e:
                logger.error(f"[NEW_BOT_SIGNALS] ❌ Ошибка обработки сигналов для {symbol}: {e}")
                
    except Exception as e:
        logger.error(f"[NEW_BOT_SIGNALS] ❌ Ошибка обработки торговых сигналов: {str(e)}")

def check_new_autobot_filters(symbol, signal, coin_data):
    """Проверяет фильтры для нового автобота"""
    try:
        # 1. Проверка зрелости монеты
        if not check_coin_maturity_stored_or_verify(symbol):
            logger.debug(f"[NEW_AUTO_FILTER] {symbol}: Монета незрелая")
            return False
        
        # 2. Проверка антислива (сливные/памп свечи за последние 20 свечей)
        if not check_anti_dump_pump(symbol, coin_data):
            logger.warning(f"[NEW_AUTO_FILTER] {symbol}: ❌ БЛОКИРОВКА: Обнаружены сливные/памп свечи")
            return False
        else:
            logger.info(f"[NEW_AUTO_FILTER] {symbol}: ✅ Антипамп фильтр пройден")
        
        # 3. Проверка тренда
        trend = coin_data.get('trend6h', 'NEUTRAL')
        with bots_data_lock:
            auto_config = bots_data['auto_bot_config']
            avoid_down_trend = auto_config.get('avoid_down_trend', True)
            avoid_up_trend = auto_config.get('avoid_up_trend', True)
        
        if signal == 'ENTER_LONG' and avoid_down_trend and trend == 'DOWN':
            logger.debug(f"[NEW_AUTO_FILTER] {symbol}: DOWN тренд - не открываем LONG")
            return False
        
        if signal == 'ENTER_SHORT' and avoid_up_trend and trend == 'UP':
            logger.debug(f"[NEW_AUTO_FILTER] {symbol}: UP тренд - не открываем SHORT")
            return False
        
        # 4. Проверка существующих позиций на бирже
        if not check_no_existing_position(symbol, signal):
            logger.debug(f"[NEW_AUTO_FILTER] {symbol}: Уже есть позиция на бирже")
            return False
        
        logger.debug(f"[NEW_AUTO_FILTER] {symbol}: ✅ Все фильтры пройдены")
        return True
        
    except Exception as e:
        logger.error(f"[NEW_AUTO_FILTER] {symbol}: Ошибка проверки фильтров: {e}")
        return False

def check_coin_maturity_stored_or_verify(symbol):
    """Проверяет зрелость монеты из хранилища или выполняет проверку"""
    try:
        # Сначала проверяем хранилище
        if is_coin_mature_stored(symbol):
            return True
        
        # Если нет в хранилище, выполняем проверку
        if not ensure_exchange_initialized():
            logger.warning(f"[MATURITY_CHECK] {symbol}: Биржа не инициализирована")
            return False
        
        chart_response = exchange.get_chart_data(symbol, '6h', '30d')
        if not chart_response or not chart_response.get('success'):
            logger.warning(f"[MATURITY_CHECK] {symbol}: Не удалось получить свечи")
            return False
        
        candles = chart_response.get('data', {}).get('candles', [])
        if not candles:
            logger.warning(f"[MATURITY_CHECK] {symbol}: Нет свечей")
            return False
        
        maturity_result = check_coin_maturity_with_storage(symbol, candles)
        return maturity_result['is_mature']
        
    except Exception as e:
        logger.error(f"[MATURITY_CHECK] {symbol}: Ошибка проверки зрелости: {e}")
        return False

def check_anti_dump_pump(symbol, coin_data):
    """Проверяет на сливные/памп свечи за последние 20 свечей"""
    try:
        # Получаем свечи
        if not ensure_exchange_initialized():
            return False
        
        chart_response = exchange.get_chart_data(symbol, '6h', '30d')
        if not chart_response or not chart_response.get('success'):
            return False
        
        candles = chart_response.get('data', {}).get('candles', [])
        if len(candles) < 20:
            return False
        
        # Проверяем последние 20 свечей
        recent_candles = candles[-20:]
        
        # 1. Проверка на экстремальные движения отдельных свечей
        extreme_moves = 0
        for candle in recent_candles:
            open_price = candle['open']
            close_price = candle['close']
            high_price = candle['high']
            low_price = candle['low']
            
            # Вычисляем процент изменения от открытия до закрытия
            price_change = abs((close_price - open_price) / open_price) * 100
            
            # Вычисляем общий диапазон свечи (high - low)
            candle_range = ((high_price - low_price) / open_price) * 100
            
            # Проверяем на экстремальные движения (>15% изменение или >20% диапазон)
            if price_change > 15 or candle_range > 20:
                extreme_moves += 1
                logger.debug(f"[ANTI_DUMP_PUMP] {symbol}: Экстремальная свеча: изменение {price_change:.1f}%, диапазон {candle_range:.1f}%")
        
        # 2. Проверка на совокупные пампы/сливы за несколько свечей
        total_change = 0
        consecutive_moves = 0
        max_consecutive = 0
        
        for i, candle in enumerate(recent_candles):
            open_price = candle['open']
            close_price = candle['close']
            
            # Процент изменения свечи
            candle_change = ((close_price - open_price) / open_price) * 100
            
            # Если движение в том же направлении что и предыдущее
            if i > 0:
                prev_candle = recent_candles[i-1]
                prev_change = ((prev_candle['close'] - prev_candle['open']) / prev_candle['open']) * 100
                
                # Если оба движения в одну сторону (оба положительные или оба отрицательные)
                if (candle_change > 0 and prev_change > 0) or (candle_change < 0 and prev_change < 0):
                    consecutive_moves += 1
                else:
                    consecutive_moves = 1
            else:
                consecutive_moves = 1
            
            max_consecutive = max(max_consecutive, consecutive_moves)
            
            # Суммируем общее изменение
            total_change += abs(candle_change)
        
        # 3. Проверка на резкие пампы/сливы
        # Если общее изменение за 20 свечей > 200% - это подозрительно
        if total_change > 200:
            logger.warning(f"[ANTI_DUMP_PUMP] {symbol}: Подозрительно высокое общее изменение: {total_change:.1f}% за 20 свечей")
            return False
        
        # Если больше 3 экстремальных движений - блокируем
        if extreme_moves > 3:
            logger.warning(f"[ANTI_DUMP_PUMP] {symbol}: Слишком много экстремальных движений: {extreme_moves}")
            return False
        
        # Если есть последовательные движения в одну сторону (>5 свечей подряд)
        if max_consecutive > 5:
            logger.warning(f"[ANTI_DUMP_PUMP] {symbol}: Подозрительная последовательность: {max_consecutive} свечей в одну сторону")
            return False
        
        # 4. Проверка на резкий памп за последние 5 свечей (30 часов)
        last_5_candles = recent_candles[-5:]
        if len(last_5_candles) >= 5:
            first_price = last_5_candles[0]['open']
            last_price = last_5_candles[-1]['close']
            five_candle_change = abs((last_price - first_price) / first_price) * 100
            
            # Если изменение за 5 свечей > 50% - это памп/слив
            if five_candle_change > 50:
                logger.warning(f"[ANTI_DUMP_PUMP] {symbol}: Резкий памп/слив за 5 свечей: {five_candle_change:.1f}%")
                return False
        
        logger.debug(f"[ANTI_DUMP_PUMP] {symbol}: ✅ Фильтр пройден (экстремальных: {extreme_moves}, общее изменение: {total_change:.1f}%)")
        return True
        
    except Exception as e:
        logger.error(f"[ANTI_DUMP_PUMP] {symbol}: Ошибка проверки: {e}")
        return False

def check_no_existing_position(symbol, signal):
    """Проверяет, что нет существующих позиций на бирже"""
    try:
        if not ensure_exchange_initialized():
            return False
        
        exchange_positions = exchange.get_positions()
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

def create_new_bot(symbol, config=None, exchange_obj=None):
    """Создает нового бота"""
    try:
        exchange_to_use = exchange_obj if exchange_obj else exchange
        
        # Создаем конфигурацию бота
        bot_config = {
            'symbol': symbol,
            'status': BOT_STATUS['IDLE'],
            'created_at': datetime.now().isoformat(),
            'opened_by_autobot': True,
            'volume_mode': 'usdt',
            'volume_value': 10.0  # Будет браться из конфига
        }
        
        # Получаем размер позиции из конфига
        with bots_data_lock:
            bot_config['volume_value'] = bots_data['auto_bot_config'].get('default_position_size', 10.0)
        
        # Создаем бота
        new_bot = NewTradingBot(symbol, bot_config, exchange_to_use)
        
        # Сохраняем в bots_data
        with bots_data_lock:
            bots_data['bots'][symbol] = new_bot.to_dict()
        
        logger.info(f"[CREATE_BOT] ✅ Бот для {symbol} создан успешно")
        return new_bot
        
    except Exception as e:
        logger.error(f"[CREATE_BOT] ❌ Ошибка создания бота для {symbol}: {e}")
        raise

def check_auto_bot_filters(symbol):
    """Старая функция - оставлена для совместимости"""
    return False  # Блокируем все

def test_anti_pump_filter(symbol):
    """Тестирует антипамп фильтр для конкретной монеты"""
    try:
        logger.info(f"[TEST_ANTI_PUMP] 🔍 Тестируем антипамп фильтр для {symbol}")
        
        # Получаем свечи
        if not ensure_exchange_initialized():
            logger.error(f"[TEST_ANTI_PUMP] {symbol}: Биржа не инициализирована")
            return
        
        chart_response = exchange.get_chart_data(symbol, '6h', '30d')
        if not chart_response or not chart_response.get('success'):
            logger.error(f"[TEST_ANTI_PUMP] {symbol}: Не удалось получить свечи")
            return
        
        candles = chart_response.get('data', {}).get('candles', [])
        if len(candles) < 20:
            logger.error(f"[TEST_ANTI_PUMP] {symbol}: Недостаточно свечей ({len(candles)})")
            return
        
        # Анализируем последние 20 свечей
        recent_candles = candles[-20:]
        
        logger.info(f"[TEST_ANTI_PUMP] {symbol}: Анализ последних 20 свечей (6H каждая)")
        
        # Показываем детали каждой свечи
        for i, candle in enumerate(recent_candles):
            open_price = candle['open']
            close_price = candle['close']
            high_price = candle['high']
            low_price = candle['low']
            
            price_change = ((close_price - open_price) / open_price) * 100
            candle_range = ((high_price - low_price) / open_price) * 100
            
            logger.info(f"[TEST_ANTI_PUMP] {symbol}: Свеча {i+1}: O={open_price:.4f} C={close_price:.4f} H={high_price:.4f} L={low_price:.4f} | Изменение: {price_change:+.1f}% | Диапазон: {candle_range:.1f}%")
        
        # Тестируем фильтр
        result = check_anti_dump_pump(symbol, {})
        logger.info(f"[TEST_ANTI_PUMP] {symbol}: Результат фильтра: {'✅ ПРОЙДЕН' if result else '❌ ЗАБЛОКИРОВАН'}")
        
    except Exception as e:
        logger.error(f"[TEST_ANTI_PUMP] {symbol}: Ошибка тестирования: {e}")

def test_rsi_time_filter(symbol):
    """Тестирует RSI временной фильтр для конкретной монеты"""
    try:
        logger.info(f"[TEST_RSI_TIME] 🔍 Тестируем RSI временной фильтр для {symbol}")
        
        # Получаем свечи
        if not ensure_exchange_initialized():
            logger.error(f"[TEST_RSI_TIME] {symbol}: Биржа не инициализирована")
            return
        
        chart_response = exchange.get_chart_data(symbol, '6h', '30d')
        if not chart_response or not chart_response.get('success'):
            logger.error(f"[TEST_RSI_TIME] {symbol}: Не удалось получить свечи")
            return
        
        candles = chart_response.get('data', {}).get('candles', [])
        if len(candles) < 50:
            logger.error(f"[TEST_RSI_TIME] {symbol}: Недостаточно свечей ({len(candles)})")
            return
        
        # Получаем текущий RSI
        with rsi_data_lock:
            coin_data = coins_rsi_data['coins'].get(symbol)
            if not coin_data:
                logger.error(f"[TEST_RSI_TIME] {symbol}: Нет RSI данных")
                return
            
            current_rsi = coin_data.get('rsi6h', 0)
            signal = coin_data.get('signal', 'WAIT')
        
        logger.info(f"[TEST_RSI_TIME] {symbol}: Текущий RSI={current_rsi:.1f}, Сигнал={signal}")
        
        # Тестируем временной фильтр
        time_filter_result = check_rsi_time_filter(candles, current_rsi, signal)
        
        logger.info(f"[TEST_RSI_TIME] {symbol}: Результат временного фильтра:")
        logger.info(f"[TEST_RSI_TIME] {symbol}: Разрешено: {time_filter_result['allowed']}")
        logger.info(f"[TEST_RSI_TIME] {symbol}: Причина: {time_filter_result['reason']}")
        if 'last_extreme_candles_ago' in time_filter_result:
            logger.info(f"[TEST_RSI_TIME] {symbol}: Последний экстремум: {time_filter_result['last_extreme_candles_ago']} свечей назад")
        
        # Показываем историю RSI для анализа
        closes = [candle['close'] for candle in candles]
        rsi_history = calculate_rsi_history(closes, 14)
        
        if rsi_history:
            logger.info(f"[TEST_RSI_TIME] {symbol}: Последние 10 значений RSI:")
            for i, rsi_val in enumerate(rsi_history[-10:]):
                logger.info(f"[TEST_RSI_TIME] {symbol}: RSI {i+1}: {rsi_val:.1f}")
        
    except Exception as e:
        logger.error(f"[TEST_RSI_TIME] {symbol}: Ошибка тестирования: {e}")

class NewTradingBot:
    """Новый торговый бот согласно требованиям"""
    
    def __init__(self, symbol, config=None, exchange=None):
        self.symbol = symbol
        self.config = config or {}
        self.exchange = exchange
        
        logger.info(f"[NEW_BOT_{symbol}] 🤖 Инициализация нового торгового бота")
        
        # Параметры сделки из конфига
        self.volume_mode = self.config.get('volume_mode', 'usdt')
        self.volume_value = self.config.get('volume_value', 10.0)
        
        # Состояние бота
        self.status = self.config.get('status', BOT_STATUS['IDLE'])
        self.entry_price = self.config.get('entry_price', None)
        self.position_side = self.config.get('position_side', None)
        self.unrealized_pnl = self.config.get('unrealized_pnl', 0.0)
        self.created_at = self.config.get('created_at', datetime.now().isoformat())
        self.last_signal_time = self.config.get('last_signal_time', None)
        
        # Защитные механизмы
        self.max_profit_achieved = self.config.get('max_profit_achieved', 0.0)
        self.trailing_stop_price = self.config.get('trailing_stop_price', None)
        self.break_even_activated = bool(self.config.get('break_even_activated', False))
        
        # Время входа в позицию
        position_start_str = self.config.get('position_start_time', None)
        if position_start_str:
            try:
                self.position_start_time = datetime.fromisoformat(position_start_str)
            except:
                self.position_start_time = None
        else:
            self.position_start_time = None
        
        # Отслеживание позиций
        self.order_id = self.config.get('order_id', None)
        self.entry_timestamp = self.config.get('entry_timestamp', None)
        self.opened_by_autobot = self.config.get('opened_by_autobot', False)
        
        logger.info(f"[NEW_BOT_{symbol}] ✅ Бот инициализирован (статус: {self.status})")
    
    def update_status(self, new_status, entry_price=None, position_side=None):
        """Обновляет статус бота"""
        old_status = self.status
        self.status = new_status
        
        if entry_price is not None:
            self.entry_price = entry_price
        if position_side is not None:
            self.position_side = position_side
            
        # Инициализируем защитные механизмы при входе в позицию
        if new_status in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
            self.position_start_time = datetime.now()
            self.max_profit_achieved = 0.0
            self.trailing_stop_price = None
            self.break_even_activated = False
            
        logger.info(f"[NEW_BOT_{self.symbol}] 📊 Статус изменен: {old_status} → {new_status}")
    
    def should_open_long(self, rsi, trend, candles):
        """Проверяет, нужно ли открывать LONG позицию"""
        try:
            # Получаем настройки из конфига
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                rsi_long_threshold = auto_config.get('rsi_long_threshold', 29)
                avoid_down_trend = auto_config.get('avoid_down_trend', True)
                rsi_time_filter_enabled = auto_config.get('rsi_time_filter_enabled', True)
                rsi_time_filter_candles = auto_config.get('rsi_time_filter_candles', 8)
                rsi_time_filter_lower = auto_config.get('rsi_time_filter_lower', 35)
            
            # 1. Проверка RSI
            if rsi > rsi_long_threshold:
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ RSI {rsi:.1f} > {rsi_long_threshold} - не открываем LONG")
                return False
            
            # 2. Проверка тренда
            if avoid_down_trend and trend == 'DOWN':
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ DOWN тренд - не открываем LONG")
                return False
            
            # 3. RSI временной фильтр
            if rsi_time_filter_enabled:
                time_filter_result = self.check_rsi_time_filter_for_long(candles, rsi, rsi_time_filter_candles, rsi_time_filter_lower)
                if not time_filter_result['allowed']:
                    logger.info(f"[NEW_BOT_{self.symbol}] ❌ RSI Time Filter блокирует LONG: {time_filter_result['reason']}")
                    return False
            
            logger.info(f"[NEW_BOT_{self.symbol}] ✅ Все проверки пройдены - открываем LONG (RSI: {rsi:.1f}, Trend: {trend})")
            return True
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки LONG: {e}")
            return False
    
    def should_open_short(self, rsi, trend, candles):
        """Проверяет, нужно ли открывать SHORT позицию"""
        try:
            # Получаем настройки из конфига
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                rsi_short_threshold = auto_config.get('rsi_short_threshold', 71)
                avoid_up_trend = auto_config.get('avoid_up_trend', True)
                rsi_time_filter_enabled = auto_config.get('rsi_time_filter_enabled', True)
                rsi_time_filter_candles = auto_config.get('rsi_time_filter_candles', 8)
                rsi_time_filter_upper = auto_config.get('rsi_time_filter_upper', 65)
            
            # 1. Проверка RSI
            if rsi < rsi_short_threshold:
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ RSI {rsi:.1f} < {rsi_short_threshold} - не открываем SHORT")
                return False
            
            # 2. Проверка тренда
            if avoid_up_trend and trend == 'UP':
                logger.debug(f"[NEW_BOT_{self.symbol}] ❌ UP тренд - не открываем SHORT")
                return False
            
            # 3. RSI временной фильтр
            if rsi_time_filter_enabled:
                time_filter_result = self.check_rsi_time_filter_for_short(candles, rsi, rsi_time_filter_candles, rsi_time_filter_upper)
                if not time_filter_result['allowed']:
                    logger.info(f"[NEW_BOT_{self.symbol}] ❌ RSI Time Filter блокирует SHORT: {time_filter_result['reason']}")
                    return False
            
            logger.info(f"[NEW_BOT_{self.symbol}] ✅ Все проверки пройдены - открываем SHORT (RSI: {rsi:.1f}, Trend: {trend})")
            return True
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки SHORT: {e}")
            return False
    
    def check_rsi_time_filter_for_long(self, candles, rsi, filter_candles, filter_lower):
        """Проверяет RSI временной фильтр для LONG (использует сложную логику)"""
        try:
            # Используем старую сложную логику временного фильтра
            return check_rsi_time_filter(candles, rsi, 'ENTER_LONG')
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка RSI Time Filter для LONG: {e}")
            return {'allowed': False, 'reason': f'Ошибка анализа: {str(e)}'}
    
    def check_rsi_time_filter_for_short(self, candles, rsi, filter_candles, filter_upper):
        """Проверяет RSI временной фильтр для SHORT (использует сложную логику)"""
        try:
            # Используем старую сложную логику временного фильтра
            return check_rsi_time_filter(candles, rsi, 'ENTER_SHORT')
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка RSI Time Filter для SHORT: {e}")
            return {'allowed': False, 'reason': f'Ошибка анализа: {str(e)}'}
    
    def should_close_long(self, rsi, current_price):
        """Проверяет, нужно ли закрывать LONG позицию"""
        try:
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                rsi_long_exit = auto_config.get('rsi_long_exit', 65)
            
            if rsi >= rsi_long_exit:
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ Закрываем LONG: RSI {rsi:.1f} >= {rsi_long_exit}")
                return True, 'RSI_EXIT'
            
            return False, None
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки закрытия LONG: {e}")
            return False, None
    
    def should_close_short(self, rsi, current_price):
        """Проверяет, нужно ли закрывать SHORT позицию"""
        try:
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                rsi_short_exit = auto_config.get('rsi_short_exit', 35)
            
            if rsi <= rsi_short_exit:
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ Закрываем SHORT: RSI {rsi:.1f} <= {rsi_short_exit}")
                return True, 'RSI_EXIT'
            
            return False, None
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки закрытия SHORT: {e}")
            return False, None
    
    def update(self, force_analysis=False, external_signal=None, external_trend=None):
        """Основной метод обновления бота"""
        try:
            if not self.exchange:
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Биржа не инициализирована")
                return {'success': False, 'error': 'Exchange not initialized'}
            
            # Получаем текущие данные
            current_price = None
            current_rsi = None
            current_trend = external_trend
            
            # Получаем RSI данные
            with rsi_data_lock:
                coin_data = coins_rsi_data['coins'].get(self.symbol)
                if coin_data:
                    current_rsi = coin_data.get('rsi6h')
                    current_price = coin_data.get('price')
                    if not current_trend:
                        current_trend = coin_data.get('trend6h', 'NEUTRAL')
            
            if current_rsi is None or current_price is None:
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Нет RSI данных")
                return {'success': False, 'error': 'No RSI data'}
            
            # Получаем свечи для анализа
            chart_response = self.exchange.get_chart_data(self.symbol, '6h', '30d')
            if not chart_response or not chart_response.get('success'):
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Не удалось получить свечи")
                return {'success': False, 'error': 'No candles data'}
            
            candles = chart_response.get('data', {}).get('candles', [])
            if not candles:
                logger.warning(f"[NEW_BOT_{self.symbol}] ❌ Нет свечей")
                return {'success': False, 'error': 'Empty candles'}
            
            # Обрабатываем в зависимости от статуса
            if self.status == BOT_STATUS['IDLE']:
                return self._handle_idle_state(current_rsi, current_trend, candles, current_price)
            elif self.status in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
                return self._handle_position_state(current_rsi, current_trend, candles, current_price)
            else:
                logger.debug(f"[NEW_BOT_{self.symbol}] ⏳ Статус {self.status} - ждем")
                return {'success': True, 'status': self.status}
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка обновления: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_idle_state(self, rsi, trend, candles, price):
        """Обрабатывает состояние IDLE (ожидание сигнала)"""
        try:
            # Проверяем, включен ли автобот
            with bots_data_lock:
                auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            
            if not auto_bot_enabled:
                logger.debug(f"[NEW_BOT_{self.symbol}] ⏹️ Автобот выключен - не открываем позицию")
                return {'success': True, 'status': self.status}
            
            # Проверяем возможность открытия LONG
            if self.should_open_long(rsi, trend, candles):
                logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Открываем LONG позицию (RSI: {rsi:.1f})")
                if self._open_position_on_exchange('LONG', price):
                    self.update_status(BOT_STATUS['IN_POSITION_LONG'], price, 'LONG')
                    return {'success': True, 'action': 'OPEN_LONG', 'status': self.status}
                else:
                    logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось открыть LONG позицию")
                    return {'success': False, 'error': 'Failed to open LONG position'}
            
            # Проверяем возможность открытия SHORT
            if self.should_open_short(rsi, trend, candles):
                logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Открываем SHORT позицию (RSI: {rsi:.1f})")
                if self._open_position_on_exchange('SHORT', price):
                    self.update_status(BOT_STATUS['IN_POSITION_SHORT'], price, 'SHORT')
                    return {'success': True, 'action': 'OPEN_SHORT', 'status': self.status}
                else:
                    logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось открыть SHORT позицию")
                    return {'success': False, 'error': 'Failed to open SHORT position'}
            
            logger.debug(f"[NEW_BOT_{self.symbol}] ⏳ Ждем сигнал (RSI: {rsi:.1f}, Trend: {trend})")
            return {'success': True, 'status': self.status}
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка в idle состоянии: {e}")
            return {'success': False, 'error': str(e)}
    
    def _handle_position_state(self, rsi, trend, candles, price):
        """Обрабатывает состояние в позиции"""
        try:
            if not self.entry_price:
                logger.warning(f"[NEW_BOT_{self.symbol}] ⚠️ Нет цены входа - обновляем из биржи")
                self._sync_position_with_exchange()
            
            # 1. Проверяем защитные механизмы
            protection_result = self.check_protection_mechanisms(price)
            if protection_result['should_close']:
                logger.info(f"[NEW_BOT_{self.symbol}] 🛡️ Закрываем позицию: {protection_result['reason']}")
                self._close_position_on_exchange(protection_result['reason'])
                return {'success': True, 'action': f"CLOSE_{self.position_side}", 'reason': protection_result['reason']}
            
            # 2. Проверяем условия закрытия по RSI
            if self.position_side == 'LONG':
                should_close, reason = self.should_close_long(rsi, price)
                if should_close:
                    logger.info(f"[NEW_BOT_{self.symbol}] 🔴 Закрываем LONG позицию: {reason}")
                    self._close_position_on_exchange(reason)
                    return {'success': True, 'action': 'CLOSE_LONG', 'reason': reason}
            
            elif self.position_side == 'SHORT':
                should_close, reason = self.should_close_short(rsi, price)
                if should_close:
                    logger.info(f"[NEW_BOT_{self.symbol}] 🔴 Закрываем SHORT позицию: {reason}")
                    self._close_position_on_exchange(reason)
                    return {'success': True, 'action': 'CLOSE_SHORT', 'reason': reason}
            
            # 3. Обновляем защитные механизмы
            self._update_protection_mechanisms(price)
            
            logger.debug(f"[NEW_BOT_{self.symbol}] 📊 В позиции {self.position_side} (RSI: {rsi:.1f}, Цена: {price})")
            return {'success': True, 'status': self.status, 'position_side': self.position_side}
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка в позиции: {e}")
            return {'success': False, 'error': str(e)}
    
    def check_protection_mechanisms(self, current_price):
        """Проверяет все защитные механизмы"""
        try:
            if not self.entry_price or not current_price:
                return {'should_close': False, 'reason': None}
            
            # Получаем настройки из конфига
            with bots_data_lock:
                auto_config = bots_data.get('auto_bot_config', {})
                stop_loss_percent = auto_config.get('stop_loss_percent', 15.0)
                trailing_activation_percent = auto_config.get('trailing_activation_percent', 300.0)
                trailing_distance_percent = auto_config.get('trailing_distance_percent', 150.0)
                break_even_trigger_percent = auto_config.get('break_even_trigger_percent', 100.0)
            
            # Вычисляем текущую прибыль в процентах
            if self.position_side == 'LONG':
                profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
            else:  # SHORT
                profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100
            
            # 1. Проверка стоп-лосса
            if profit_percent <= -stop_loss_percent:
                logger.warning(f"[NEW_BOT_{self.symbol}] 💀 Стоп-лосс! Убыток: {profit_percent:.2f}%")
                return {'should_close': True, 'reason': f'STOP_LOSS_{profit_percent:.2f}%'}
            
            # 2. Обновляем максимальную прибыль
            if profit_percent > self.max_profit_achieved:
                self.max_profit_achieved = profit_percent
                logger.debug(f"[NEW_BOT_{self.symbol}] 📈 Новая максимальная прибыль: {profit_percent:.2f}%")
            
            # 3. Проверка безубыточности
            if not self.break_even_activated and profit_percent >= break_even_trigger_percent:
                self.break_even_activated = True
                logger.info(f"[NEW_BOT_{self.symbol}] 🛡️ Активирована защита безубыточности при {profit_percent:.2f}%")
            
            if self.break_even_activated and profit_percent <= 0:
                logger.info(f"[NEW_BOT_{self.symbol}] 🛡️ Закрываем по безубыточности (было {self.max_profit_achieved:.2f}%, сейчас {profit_percent:.2f}%)")
                return {'should_close': True, 'reason': f'BREAK_EVEN_MAX_{self.max_profit_achieved:.2f}%'}
            
            # 4. Проверка trailing stop
            if self.max_profit_achieved >= trailing_activation_percent:
                # Рассчитываем trailing stop цену
                if self.position_side == 'LONG':
                    # Для LONG trailing stop ниже максимальной цены
                    max_price = self.entry_price * (1 + self.max_profit_achieved / 100)
                    trailing_stop = max_price * (1 - trailing_distance_percent / 100)
                    
                    if current_price <= trailing_stop:
                        logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Trailing Stop! Макс: {self.max_profit_achieved:.2f}%, Текущ: {profit_percent:.2f}%")
                        return {'should_close': True, 'reason': f'TRAILING_STOP_MAX_{self.max_profit_achieved:.2f}%'}
                else:  # SHORT
                    # Для SHORT trailing stop выше минимальной цены
                    min_price = self.entry_price * (1 - self.max_profit_achieved / 100)
                    trailing_stop = min_price * (1 + trailing_distance_percent / 100)
                    
                    if current_price >= trailing_stop:
                        logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Trailing Stop! Макс: {self.max_profit_achieved:.2f}%, Текущ: {profit_percent:.2f}%")
                        return {'should_close': True, 'reason': f'TRAILING_STOP_MAX_{self.max_profit_achieved:.2f}%'}
            
            return {'should_close': False, 'reason': None}
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка проверки защитных механизмов: {e}")
            return {'should_close': False, 'reason': None}
    
    def _update_protection_mechanisms(self, current_price):
        """Обновляет защитные механизмы"""
        try:
            if not self.entry_price or not current_price:
                return
            
            # Вычисляем текущую прибыль
            if self.position_side == 'LONG':
                profit_percent = ((current_price - self.entry_price) / self.entry_price) * 100
            else:  # SHORT
                profit_percent = ((self.entry_price - current_price) / self.entry_price) * 100
            
            # Обновляем максимальную прибыль
            if profit_percent > self.max_profit_achieved:
                self.max_profit_achieved = profit_percent
                logger.debug(f"[NEW_BOT_{self.symbol}] 📈 Обновлена максимальная прибыль: {profit_percent:.2f}%")
            
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка обновления защитных механизмов: {e}")
    
    def _sync_position_with_exchange(self):
        """Синхронизирует данные бота с позицией на бирже"""
        try:
            if not self.exchange:
                return
            
            exchange_positions = self.exchange.get_positions()
            if isinstance(exchange_positions, tuple):
                positions_list = exchange_positions[0] if exchange_positions else []
            else:
                positions_list = exchange_positions if exchange_positions else []
            
            for pos in positions_list:
                if pos.get('symbol') == self.symbol and abs(float(pos.get('size', 0))) > 0:
                    self.entry_price = float(pos.get('entry_price', 0))
                    self.position_side = pos.get('side', 'UNKNOWN')
                    self.unrealized_pnl = float(pos.get('unrealized_pnl', 0))
                    logger.info(f"[NEW_BOT_{self.symbol}] 🔄 Синхронизировано с биржей: {self.position_side} @ {self.entry_price}")
                    break
                    
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка синхронизации с биржей: {e}")
    
    def _open_position_on_exchange(self, side, price):
        """Открывает позицию на бирже"""
        try:
            if not self.exchange:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Биржа не инициализирована")
                return False
            
            logger.info(f"[NEW_BOT_{self.symbol}] 🚀 Открываем позицию {side} @ {price}")
            
            # Открываем позицию на бирже
            order_result = self.exchange.place_market_order(
                symbol=self.symbol,
                side=side,
                qty=None,  # Будет рассчитано по volume_value
                qty_in_usdt=self.volume_value
            )
            
            if order_result and order_result.get('success'):
                self.order_id = order_result.get('order_id')
                self.entry_timestamp = datetime.now().isoformat()
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ Позиция {side} открыта: Order ID {self.order_id}")
                return True
            else:
                error = order_result.get('error', 'Unknown error') if order_result else 'No response'
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось открыть позицию: {error}")
                return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка открытия позиции: {e}")
            return False
    
    def _close_position_on_exchange(self, reason):
        """Закрывает позицию на бирже"""
        try:
            if not self.exchange:
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Биржа не инициализирована")
                return False
            
            logger.info(f"[NEW_BOT_{self.symbol}] 🔴 Закрываем позицию {self.position_side} (причина: {reason})")
            
            # Закрываем позицию на бирже
            close_result = self.exchange.close_position(
                symbol=self.symbol,
                side=self.position_side
            )
            
            if close_result and close_result.get('success'):
                logger.info(f"[NEW_BOT_{self.symbol}] ✅ Позиция закрыта успешно")
                self.update_status(BOT_STATUS['IDLE'])
                return True
            else:
                error = close_result.get('error', 'Unknown error') if close_result else 'No response'
                logger.error(f"[NEW_BOT_{self.symbol}] ❌ Не удалось закрыть позицию: {error}")
                return False
                
        except Exception as e:
            logger.error(f"[NEW_BOT_{self.symbol}] ❌ Ошибка закрытия позиции: {e}")
            return False
    
    def to_dict(self):
        """Преобразует бота в словарь для сохранения"""
        return {
            'symbol': self.symbol,
            'status': self.status,
            'entry_price': self.entry_price,
            'position_side': self.position_side,
            'unrealized_pnl': self.unrealized_pnl,
            'created_at': self.created_at,
            'last_signal_time': self.last_signal_time,
            'max_profit_achieved': self.max_profit_achieved,
            'trailing_stop_price': self.trailing_stop_price,
            'break_even_activated': self.break_even_activated,
            'position_start_time': self.position_start_time.isoformat() if self.position_start_time else None,
            'order_id': self.order_id,
            'entry_timestamp': self.entry_timestamp,
            'opened_by_autobot': self.opened_by_autobot
        }

def get_rsi_cache():
    """Получить кэшированные RSI данные"""
    global coins_rsi_data
    with rsi_data_lock:
        return coins_rsi_data.get('coins', {})

def save_rsi_cache():
    """Сохранить кэш RSI данных в файл"""
    try:
        with rsi_data_lock:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'coins': coins_rsi_data.get('coins', {}),
                'stats': {
                    'total_coins': len(coins_rsi_data.get('coins', {})),
                    'successful_coins': coins_rsi_data.get('successful_coins', 0),
                    'failed_coins': coins_rsi_data.get('failed_coins', 0)
                }
            }
        
        with open(RSI_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"[CACHE] RSI данные для {len(cache_data['coins'])} монет сохранены в кэш")
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка сохранения RSI кэша: {str(e)}")

def load_rsi_cache():
    """Загрузить кэш RSI данных из файла"""
    global coins_rsi_data
    
    try:
        if not os.path.exists(RSI_CACHE_FILE):
            logger.info("[CACHE] Файл RSI кэша не найден, будет создан при первом обновлении")
            return False
            
        with open(RSI_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Проверяем возраст кэша (не старше 6 часов)
        cache_timestamp = datetime.fromisoformat(cache_data['timestamp'])
        age_hours = (datetime.now() - cache_timestamp).total_seconds() / 3600
        
        if age_hours > 6:
            logger.warning(f"[CACHE] RSI кэш устарел ({age_hours:.1f} часов), будет обновлен")
            return False
        
        # Загружаем данные из кэша
        cached_coins = cache_data.get('coins', {})
        
        # Проверяем формат кэша (старый массив или новый словарь)
        if isinstance(cached_coins, list):
            # Старый формат - преобразуем массив в словарь
            coins_dict = {}
            for coin in cached_coins:
                if 'symbol' in coin:
                    coins_dict[coin['symbol']] = coin
            cached_coins = coins_dict
            logger.info("[CACHE] Преобразован старый формат кэша (массив -> словарь)")
        
        with rsi_data_lock:
            coins_rsi_data.update({
                'coins': cached_coins,
                'successful_coins': cache_data.get('stats', {}).get('successful_coins', len(cached_coins)),
                'failed_coins': cache_data.get('stats', {}).get('failed_coins', 0),
                'total_coins': len(cached_coins),
                'last_update': datetime.now().isoformat(),  # Всегда используем текущее время
                'update_in_progress': False
            })
        
        logger.info(f"[CACHE] Загружено {len(cached_coins)} монет из RSI кэша (возраст: {age_hours:.1f}ч)")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка загрузки RSI кэша: {str(e)}")
        return False

def save_default_config():
    """Сохраняет дефолтную конфигурацию в файл для восстановления"""
    try:
        with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_AUTO_BOT_CONFIG, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[DEFAULT_CONFIG] ✅ Дефолтная конфигурация сохранена в {DEFAULT_CONFIG_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"[DEFAULT_CONFIG] ❌ Ошибка сохранения дефолтной конфигурации: {e}")
        return False

def load_default_config():
    """Загружает дефолтную конфигурацию из файла"""
    try:
        if os.path.exists(DEFAULT_CONFIG_FILE):
            with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Если файла нет, создаем его с текущими дефолтными значениями
            save_default_config()
            return DEFAULT_AUTO_BOT_CONFIG.copy()
            
    except Exception as e:
        logger.error(f"[DEFAULT_CONFIG] ❌ Ошибка загрузки дефолтной конфигурации: {e}")
        return DEFAULT_AUTO_BOT_CONFIG.copy()

def restore_default_config():
    """Восстанавливает дефолтную конфигурацию Auto Bot"""
    try:
        default_config = load_default_config()
        
        with bots_data_lock:
            # Сохраняем критически важные значения (не сбрасываем их при восстановлении)
            current_enabled = bots_data['auto_bot_config'].get('enabled', False)
            current_trading_enabled = bots_data['auto_bot_config'].get('trading_enabled', True)
            
            # Восстанавливаем дефолтные значения
            bots_data['auto_bot_config'] = default_config.copy()
            
            # Возвращаем текущие состояния важных настроек
            bots_data['auto_bot_config']['enabled'] = current_enabled
            bots_data['auto_bot_config']['trading_enabled'] = current_trading_enabled
        
        # Сохраняем состояние
        save_result = save_bots_state()
        
        logger.info("[DEFAULT_CONFIG] ✅ Дефолтная конфигурация восстановлена")
        return save_result
        
    except Exception as e:
        logger.error(f"[DEFAULT_CONFIG] ❌ Ошибка восстановления дефолтной конфигурации: {e}")
        return False

def update_process_state(process_name, status_update):
    """Обновляет состояние процесса"""
    try:
        if process_name in process_state:
            process_state[process_name].update(status_update)
            
            # Автоматически сохраняем состояние процессов
            save_process_state()
            
    except Exception as e:
        logger.error(f"[PROCESS_STATE] ❌ Ошибка обновления состояния {process_name}: {e}")

def save_process_state():
    """Сохраняет состояние всех процессов"""
    try:
        state_data = {
            'process_state': process_state.copy(),
            'last_saved': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        with open(PROCESS_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        logger.error(f"[PROCESS_STATE] ❌ Ошибка сохранения состояния процессов: {e}")
        return False

def load_process_state():
    """Загружает состояние процессов из файла"""
    try:
        if not os.path.exists(PROCESS_STATE_FILE):
            logger.info(f"[PROCESS_STATE] 📁 Файл состояния процессов не найден, начинаем с дефолтного")
            save_process_state()  # Создаем файл
            return False
        
        with open(PROCESS_STATE_FILE, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        if 'process_state' in state_data:
            # Обновляем глобальное состояние
            for process_name, process_info in state_data['process_state'].items():
                if process_name in process_state:
                    process_state[process_name].update(process_info)
            
            last_saved = state_data.get('last_saved', 'неизвестно')
            logger.info(f"[PROCESS_STATE] ✅ Состояние процессов восстановлено (сохранено: {last_saved})")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"[PROCESS_STATE] ❌ Ошибка загрузки состояния процессов: {e}")
        return False

def save_system_config(config_data):
    """Сохраняет системные настройки в файл"""
    try:
        with open(SYSTEM_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[SYSTEM_CONFIG] ✅ Системные настройки сохранены в {SYSTEM_CONFIG_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"[SYSTEM_CONFIG] ❌ Ошибка сохранения системных настроек: {e}")
        return False

def load_system_config():
    """Загружает системные настройки из файла"""
    try:
        logger.info(f"[SYSTEM_CONFIG] 🔄 Начинаем загрузку конфигурации из {SYSTEM_CONFIG_FILE}")
        if os.path.exists(SYSTEM_CONFIG_FILE):
            with open(SYSTEM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
                logger.info(f"[SYSTEM_CONFIG] 📁 Загружен файл: {SYSTEM_CONFIG_FILE}")
                logger.info(f"[SYSTEM_CONFIG] 📊 Содержимое: {config_data}")
                
                # Применяем загруженные настройки к SystemConfig
                if 'rsi_update_interval' in config_data:
                    old_value = SystemConfig.RSI_UPDATE_INTERVAL
                    SystemConfig.RSI_UPDATE_INTERVAL = int(config_data['rsi_update_interval'])
                    logger.info(f"[SYSTEM_CONFIG] 🔄 RSI интервал изменен: {old_value} → {SystemConfig.RSI_UPDATE_INTERVAL}")
                else:
                    logger.info(f"[SYSTEM_CONFIG] 📝 rsi_update_interval не найден в конфигурации, используется значение по умолчанию: {SystemConfig.RSI_UPDATE_INTERVAL}")
                
                if 'auto_save_interval' in config_data:
                    SystemConfig.AUTO_SAVE_INTERVAL = int(config_data['auto_save_interval'])
                
                if 'debug_mode' in config_data:
                    SystemConfig.DEBUG_MODE = bool(config_data['debug_mode'])
                
                if 'auto_refresh_ui' in config_data:
                    SystemConfig.AUTO_REFRESH_UI = bool(config_data['auto_refresh_ui'])
                
                if 'refresh_interval' in config_data:
                    SystemConfig.UI_REFRESH_INTERVAL = int(config_data['refresh_interval'])
                
                # Загружаем интервалы синхронизации и очистки
                global STOP_LOSS_SETUP_INTERVAL, POSITION_SYNC_INTERVAL, INACTIVE_BOT_CLEANUP_INTERVAL, INACTIVE_BOT_TIMEOUT
                
                if 'stop_loss_setup_interval' in config_data:
                    old_value = STOP_LOSS_SETUP_INTERVAL
                    STOP_LOSS_SETUP_INTERVAL = int(config_data['stop_loss_setup_interval'])
                    logger.info(f"[SYSTEM_CONFIG] 🔄 Stop Loss интервал изменен: {old_value} → {STOP_LOSS_SETUP_INTERVAL}")
                
                if 'position_sync_interval' in config_data:
                    old_value = POSITION_SYNC_INTERVAL
                    POSITION_SYNC_INTERVAL = int(config_data['position_sync_interval'])
                    logger.info(f"[SYSTEM_CONFIG] 🔄 Position Sync интервал изменен: {old_value} → {POSITION_SYNC_INTERVAL}")
                
                if 'inactive_bot_cleanup_interval' in config_data:
                    old_value = INACTIVE_BOT_CLEANUP_INTERVAL
                    INACTIVE_BOT_CLEANUP_INTERVAL = int(config_data['inactive_bot_cleanup_interval'])
                    logger.info(f"[SYSTEM_CONFIG] 🔄 Inactive Bot Cleanup интервал изменен: {old_value} → {INACTIVE_BOT_CLEANUP_INTERVAL}")
                
                if 'inactive_bot_timeout' in config_data:
                    old_value = INACTIVE_BOT_TIMEOUT
                    INACTIVE_BOT_TIMEOUT = int(config_data['inactive_bot_timeout'])
                    logger.info(f"[SYSTEM_CONFIG] 🔄 Inactive Bot Timeout изменен: {old_value} → {INACTIVE_BOT_TIMEOUT}")
                
                # Настройки улучшенного RSI
                if 'enhanced_rsi_enabled' in config_data:
                    SystemConfig.ENHANCED_RSI_ENABLED = bool(config_data['enhanced_rsi_enabled'])
                
                if 'enhanced_rsi_require_volume_confirmation' in config_data:
                    SystemConfig.ENHANCED_RSI_REQUIRE_VOLUME_CONFIRMATION = bool(config_data['enhanced_rsi_require_volume_confirmation'])
                
                if 'enhanced_rsi_require_divergence_confirmation' in config_data:
                    SystemConfig.ENHANCED_RSI_REQUIRE_DIVERGENCE_CONFIRMATION = bool(config_data['enhanced_rsi_require_divergence_confirmation'])
                
                if 'enhanced_rsi_use_stoch_rsi' in config_data:
                    SystemConfig.ENHANCED_RSI_USE_STOCH_RSI = bool(config_data['enhanced_rsi_use_stoch_rsi'])
                
                logger.info(f"[SYSTEM_CONFIG] ✅ Системные настройки загружены из {SYSTEM_CONFIG_FILE}")
                logger.info(f"[SYSTEM_CONFIG] RSI интервал: {SystemConfig.RSI_UPDATE_INTERVAL} сек")
                
                # Обновляем интервал в SmartRSIManager если он уже инициализирован
                if 'smart_rsi_manager' in globals() and smart_rsi_manager:
                    smart_rsi_manager.update_monitoring_interval(SystemConfig.RSI_UPDATE_INTERVAL)
                    logger.info(f"[SYSTEM_CONFIG] ✅ SmartRSIManager обновлен с загруженным интервалом")
                
                return True
        else:
            # Если файла нет, создаем его с текущими дефолтными значениями
            default_config = {
                'rsi_update_interval': SystemConfig.RSI_UPDATE_INTERVAL,
                'auto_save_interval': SystemConfig.AUTO_SAVE_INTERVAL,
                'debug_mode': SystemConfig.DEBUG_MODE,
                'auto_refresh_ui': SystemConfig.AUTO_REFRESH_UI,
                'refresh_interval': SystemConfig.UI_REFRESH_INTERVAL
            }
            save_system_config(default_config)
            logger.info(f"[SYSTEM_CONFIG] 📁 Создан новый файл системных настроек с дефолтными значениями")
            return True
    except Exception as e:
        logger.error(f"[SYSTEM_CONFIG] ❌ Ошибка загрузки системных настроек: {e}")
        return False

def save_bots_state():
    """Сохраняет состояние всех ботов в файл"""
    try:
        state_data = {
            'bots': {},
            'auto_bot_config': {},
            'last_saved': datetime.now().isoformat(),
            'version': '1.0'
        }
        
        # Сохраняем состояние всех ботов
        with bots_data_lock:
            for symbol, bot_data in bots_data['bots'].items():
                state_data['bots'][symbol] = bot_data
            
            # Сохраняем конфигурацию Auto Bot
            state_data['auto_bot_config'] = bots_data['auto_bot_config'].copy()
        
        # Записываем в файл
        with open(BOTS_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        
        total_bots = len(state_data['bots'])
        logger.info(f"[SAVE_STATE] ✅ Состояние {total_bots} ботов сохранено в {BOTS_STATE_FILE}")
        
        return True
        
    except Exception as e:
        logger.error(f"[SAVE_STATE] ❌ Ошибка сохранения состояния: {e}")
        return False

def save_auto_bot_config():
    """Сохраняет конфигурацию автобота"""
    try:
        with bots_data_lock:
            config_data = bots_data['auto_bot_config'].copy()
        
        with open(AUTO_BOT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[SAVE_CONFIG] ✅ Конфигурация автобота сохранена в {AUTO_BOT_CONFIG_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"[SAVE_CONFIG] ❌ Ошибка сохранения конфигурации автобота: {e}")
        return False

def save_optimal_ema_periods():
    """Сохраняет оптимальные EMA периоды"""
    try:
        global optimal_ema_data
        
        # Проверяем, что есть данные для сохранения
        if not optimal_ema_data:
            logger.warning("[SAVE_EMA] ⚠️ Нет данных об оптимальных EMA для сохранения")
            return False
        
        with open(OPTIMAL_EMA_FILE, 'w', encoding='utf-8') as f:
            json.dump(optimal_ema_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[SAVE_EMA] ✅ Оптимальные EMA периоды сохранены в {OPTIMAL_EMA_FILE} ({len(optimal_ema_data)} записей)")
        return True
        
    except Exception as e:
        logger.error(f"[SAVE_EMA] ❌ Ошибка сохранения EMA периодов: {e}")
        return False

def load_bots_state():
    """Загружает состояние ботов из файла"""
    try:
        if not os.path.exists(BOTS_STATE_FILE):
            logger.info(f"[LOAD_STATE] 📁 Файл состояния {BOTS_STATE_FILE} не найден, начинаем с пустого состояния")
            return False
        
        logger.info(f"[LOAD_STATE] 📂 Загрузка состояния ботов из {BOTS_STATE_FILE}...")
        
        with open(BOTS_STATE_FILE, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        version = state_data.get('version', '1.0')
        last_saved = state_data.get('last_saved', 'неизвестно')
        
        logger.info(f"[LOAD_STATE] 📊 Версия состояния: {version}, последнее сохранение: {last_saved}")
        
        # Восстанавливаем конфигурацию Auto Bot
        if 'auto_bot_config' in state_data:
            with bots_data_lock:
                # КРИТИЧЕСКИ ВАЖНО: Сохраняем текущее состояние enabled (оно всегда False при старте)
                current_enabled = bots_data['auto_bot_config'].get('enabled', False)
                
                # Восстанавливаем остальные настройки
                bots_data['auto_bot_config'].update(state_data['auto_bot_config'])
                
                # ПРИНУДИТЕЛЬНО устанавливаем enabled = False (автобот должен запускаться ТОЛЬКО вручную!)
                bots_data['auto_bot_config']['enabled'] = False
                
            logger.info(f"[LOAD_STATE] ⚙️ Конфигурация Auto Bot восстановлена")
            logger.info(f"[LOAD_STATE] 🔒 Auto Bot принудительно выключен (запуск только вручную)")
        
        # Восстанавливаем ботов
        restored_bots = 0
        failed_bots = 0
        
        if 'bots' in state_data:
            with bots_data_lock:
                for symbol, bot_data in state_data['bots'].items():
                    try:
                        # Проверяем валидность данных бота
                        if not isinstance(bot_data, dict) or 'status' not in bot_data:
                            logger.warning(f"[LOAD_STATE] ⚠️ Некорректные данные бота {symbol}, пропускаем")
                            failed_bots += 1
                            continue
                        
                        # ВАЖНО: НЕ проверяем зрелость при восстановлении!
                        # Причины:
                        # 1. Биржа еще не инициализирована (нет данных свечей)
                        # 2. Если бот был сохранен - он уже прошел проверку зрелости при создании
                        # 3. Проверка зрелости будет выполнена позже при обработке сигналов
                        
                        # Восстанавливаем бота
                        bots_data['bots'][symbol] = bot_data
                        restored_bots += 1
                        
                        logger.info(f"[LOAD_STATE] 🤖 Восстановлен бот {symbol}: статус={bot_data.get('status', 'UNKNOWN')}")
                        
                    except Exception as e:
                        logger.error(f"[LOAD_STATE] ❌ Ошибка восстановления бота {symbol}: {e}")
                        failed_bots += 1
        
        logger.info(f"[LOAD_STATE] ✅ Восстановлено ботов: {restored_bots}, ошибок: {failed_bots}")
        
        return restored_bots > 0
        
    except Exception as e:
        logger.error(f"[LOAD_STATE] ❌ Ошибка загрузки состояния: {e}")
        return False

def update_bots_cache_data():
    """Обновляет кэшированные данные ботов (как background_update в app.py)"""
    global bots_cache_data
    
    try:
        if not ensure_exchange_initialized():
            return False
        
        # Подавляем частые сообщения об обновлении кэша
        should_log, log_message = should_log_message(
            'cache_update', 
            "🔄 Обновление кэшированных данных ботов...",
            interval_seconds=300  # Логируем раз в 5 минут
        )
        if should_log:
            logger.info(f"[BOTS_CACHE] {log_message}")
        
        # Добавляем таймаут для предотвращения зависания (Windows-совместимый)
        import threading
        import time
        
        timeout_occurred = threading.Event()
        
        def timeout_worker():
            time.sleep(30)  # 30 секунд таймаут
            timeout_occurred.set()
        
        timeout_thread = threading.Thread(target=timeout_worker, daemon=True)
        timeout_thread.start()
        
        # Получаем актуальные данные ботов
        with bots_data_lock:
            bots_list = []
            for symbol, bot_data in bots_data['bots'].items():
                # Проверяем таймаут
                if timeout_occurred.is_set():
                    logger.warning("[BOTS_CACHE] ⚠️ Таймаут достигнут, прерываем обновление")
                    break
                # Обновляем данные бота в реальном времени
                if bot_data.get('status') in ['in_position_long', 'in_position_short']:
                    try:
                        # Получаем текущую цену
                        ticker_data = exchange.get_ticker(symbol)
                        if ticker_data and 'last_price' in ticker_data:
                            current_price = float(ticker_data['last_price'])
                            entry_price = bot_data.get('entry_price')
                            position_side = bot_data.get('position_side')
                            
                            if entry_price and position_side:
                                # Рассчитываем PnL
                                if position_side == 'LONG':
                                    pnl_percent = ((current_price - entry_price) / entry_price) * 100
                                else:  # SHORT
                                    pnl_percent = ((entry_price - current_price) / entry_price) * 100
                                
                                # Обновляем данные бота
                                bot_data['unrealized_pnl'] = pnl_percent
                                bot_data['position_details'] = {
                                    'current_price': current_price,
                                    'pnl_percent': pnl_percent,
                                    'price_change': pnl_percent
                                }
                                bot_data['last_update'] = datetime.now().isoformat()
                    except Exception as e:
                        logger.error(f"[BOTS_CACHE] Ошибка обновления данных для {symbol}: {e}")
                
                # Добавляем RSI данные к боту (используем кэшированные данные)
                try:
                    # Используем кэшированные RSI данные вместо повторного вычисления
                    rsi_cache = get_rsi_cache()
                    if symbol in rsi_cache:
                        rsi_data = rsi_cache[symbol]
                        bot_data['rsi_data'] = rsi_data
                    else:
                        bot_data['rsi_data'] = {'rsi': 'N/A', 'signal': 'N/A'}
                except Exception as e:
                    logger.error(f"[BOTS_CACHE] Ошибка получения RSI для {symbol}: {e}")
                    bot_data['rsi_data'] = {'rsi': 'N/A', 'signal': 'N/A'}
                
                # Добавляем информацию о позиции с биржи (будет добавлено позже для всех ботов сразу)
                # Стоп-лоссы будут получены вместе с позициями
                
                # Добавляем бота в список
                bots_list.append(bot_data)
        
        # Получаем информацию о позициях с биржи один раз для всех ботов
        try:
            position_info = get_exchange_positions()
            if position_info and 'positions' in position_info:
                # Создаем словарь позиций для быстрого поиска
                positions_dict = {pos.get('symbol'): pos for pos in position_info['positions']}
                
                # Добавляем информацию о позициях к ботам (включая стоп-лоссы)
                for bot_data in bots_list:
                    symbol = bot_data.get('symbol')
                    if symbol in positions_dict and bot_data.get('status') in ['in_position_long', 'in_position_short']:
                        pos = positions_dict[symbol]
                        bot_data['exchange_position'] = {
                            'size': pos.get('size', 0),
                            'side': pos.get('side', ''),
                            'unrealized_pnl': pos.get('unrealizedPnl', 0),
                            'mark_price': pos.get('markPrice', 0),
                            'entry_price': pos.get('avgPrice', 0),
                            'leverage': pos.get('leverage', 1),
                            'stop_loss': pos.get('stopLoss', ''),  # Стоп-лосс с биржи
                            'take_profit': pos.get('takeProfit', '')  # Тейк-профит с биржи
                        }
                        
                        # Синхронизируем все данные позиции с биржей
                        exchange_stop_loss = pos.get('stopLoss', '')
                        exchange_take_profit = pos.get('takeProfit', '')
                        exchange_entry_price = float(pos.get('avgPrice', 0))
                        exchange_size = float(pos.get('size', 0))
                        exchange_unrealized_pnl = float(pos.get('unrealisedPnl', 0))
                        
                        # Синхронизируем стоп-лосс
                        current_stop_loss = bot_data.get('trailing_stop_price')
                        if exchange_stop_loss:
                            # Есть стоп-лосс на бирже - обновляем данные бота
                            new_stop_loss = float(exchange_stop_loss)
                            if not current_stop_loss or abs(current_stop_loss - new_stop_loss) > 0.001:
                                bot_data['trailing_stop_price'] = new_stop_loss
                                logger.debug(f"[POSITION_SYNC] Обновлен стоп-лосс для {symbol}: {new_stop_loss}")
                        else:
                            # Нет стоп-лосса на бирже - очищаем данные бота
                            if current_stop_loss:
                                bot_data['trailing_stop_price'] = None
                                logger.info(f"[POSITION_SYNC] ⚠️ Стоп-лосс отменен на бирже для {symbol}")
                        
                        # Синхронизируем тейк-профит
                        if exchange_take_profit:
                            bot_data['take_profit_price'] = float(exchange_take_profit)
                        else:
                            bot_data['take_profit_price'] = None
                        
                        # Синхронизируем цену входа (может измениться при добавлении к позиции)
                        if exchange_entry_price and exchange_entry_price > 0:
                            current_entry_price = bot_data.get('entry_price')
                            if not current_entry_price or abs(current_entry_price - exchange_entry_price) > 0.001:
                                bot_data['entry_price'] = exchange_entry_price
                                logger.debug(f"[POSITION_SYNC] Обновлена цена входа для {symbol}: {exchange_entry_price}")
                        
                        # Синхронизируем размер позиции
                        if exchange_size > 0:
                            bot_data['position_size'] = exchange_size
                        
                        # Обновляем время последнего обновления
                        bot_data['last_update'] = datetime.now().isoformat()
        except Exception as e:
            logger.error(f"[BOTS_CACHE] Ошибка получения позиций с биржи: {e}")
        
        # Обновляем кэш (только данные ботов, account_info больше не кэшируется)
        with bots_cache_lock:
            bots_cache_data.update({
                'bots': bots_list,
                'last_update': datetime.now().isoformat()
            })
        
        logger.info(f"[BOTS_CACHE] ✅ Кэш обновлен: {len(bots_list)} ботов")
        return True
        
    except Exception as e:
        logger.error(f"[BOTS_CACHE] ❌ Ошибка обновления кэша: {e}")
        return False

def update_bot_positions_status():
    """Обновляет статус позиций ботов (цена, PnL, ликвидация) каждые BOT_STATUS_UPDATE_INTERVAL секунд"""
    try:
        if not ensure_exchange_initialized():
            return False
        
        with bots_data_lock:
            updated_count = 0
            
            for symbol, bot_data in bots_data['bots'].items():
                # Обновляем только ботов в позиции
                if bot_data.get('status') not in ['in_position_long', 'in_position_short']:
                    continue
                
                try:
                    # Получаем текущую цену
                    ticker_data = exchange.get_ticker(symbol)
                    if not ticker_data or 'last_price' not in ticker_data:
                        continue
                    current_price = float(ticker_data['last_price'])
                    
                    entry_price = bot_data.get('entry_price')
                    position_side = bot_data.get('position_side')
                    
                    if not entry_price or not position_side:
                        continue
                    
                    # Рассчитываем PnL
                    if position_side == 'LONG':
                        pnl_percent = ((current_price - entry_price) / entry_price) * 100
                    else:  # SHORT
                        pnl_percent = ((entry_price - current_price) / entry_price) * 100
                    
                    # Обновляем данные бота
                    old_pnl = bot_data.get('unrealized_pnl', 0)
                    bot_data['unrealized_pnl'] = pnl_percent
                    bot_data['current_price'] = current_price
                    bot_data['last_update'] = datetime.now().isoformat()
                    
                    # Рассчитываем цену ликвидации (примерно)
                    volume_value = bot_data.get('volume_value', 10)
                    leverage = 10  # Предполагаем плечо 10x
                    
                    if position_side == 'LONG':
                        # Для LONG: ликвидация при падении цены
                        liquidation_price = entry_price * (1 - (100 / leverage) / 100)
                    else:  # SHORT
                        # Для SHORT: ликвидация при росте цены
                        liquidation_price = entry_price * (1 + (100 / leverage) / 100)
                    
                    bot_data['liquidation_price'] = liquidation_price
                    
                    # Расстояние до ликвидации
                    if position_side == 'LONG':
                        distance_to_liq = ((current_price - liquidation_price) / liquidation_price) * 100
                    else:  # SHORT
                        distance_to_liq = ((liquidation_price - current_price) / liquidation_price) * 100
                    
                    bot_data['distance_to_liquidation'] = distance_to_liq
                    
                    updated_count += 1
                    
                    # Логируем только если PnL изменился значительно
                    if abs(pnl_percent - old_pnl) > 0.1:
                        logger.info(f"[POSITION_UPDATE] 📊 {symbol} {position_side}: ${current_price:.6f} | PnL: {pnl_percent:+.2f}% | Ликвидация: ${liquidation_price:.6f} ({distance_to_liq:.1f}%)")
                
                except Exception as e:
                    logger.error(f"[POSITION_UPDATE] ❌ Ошибка обновления {symbol}: {e}")
                    continue
        
        if updated_count > 0:
            logger.debug(f"[POSITION_UPDATE] ✅ Обновлено {updated_count} позиций")
        
        return True
        
    except Exception as e:
        logger.error(f"[POSITION_UPDATE] ❌ Ошибка обновления позиций: {e}")
        return False

def get_exchange_positions():
    """Получает реальные позиции с биржи с retry логикой"""
    max_retries = 3
    retry_delay = 2  # секунды
    
    for attempt in range(max_retries):
        try:
            if not ensure_exchange_initialized():
                logger.warning(f"[EXCHANGE_POSITIONS] Биржа не инициализирована (попытка {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return []

            # Получаем СЫРЫЕ данные напрямую от API Bybit
            response = exchange.client.get_positions(
                category="linear",
                settleCoin="USDT",
                limit=100
            )

            if response['retCode'] != 0:
                error_msg = response['retMsg']
                logger.warning(f"[EXCHANGE_POSITIONS] ⚠️ Ошибка API (попытка {attempt + 1}/{max_retries}): {error_msg}")
                
                # Если это Rate Limit, увеличиваем задержку
                if "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
                    retry_delay = min(retry_delay * 2, 10)  # Увеличиваем задержку до максимум 10 сек
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"[EXCHANGE_POSITIONS] ❌ Не удалось получить позиции после {max_retries} попыток")
                    return []
            
            raw_positions = response['result']['list']
            # ✅ Не логируем частые запросы позиций (только при изменениях)
            
            # Обрабатываем сырые позиции
            processed_positions = []
            for position in raw_positions:
                symbol = position.get('symbol', '').replace('USDT', '')  # Убираем USDT
                size = float(position.get('size', 0))
                side = position.get('side', '')  # 'Buy' или 'Sell'
                entry_price = float(position.get('avgPrice', 0))
                unrealized_pnl = float(position.get('unrealisedPnl', 0))
                mark_price = float(position.get('markPrice', 0))
                
                if abs(size) > 0:  # Только активные позиции
                    processed_positions.append({
                        'symbol': symbol,
                        'size': size,
                        'side': side,
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl,
                        'mark_price': mark_price,
                        'position_side': 'LONG' if side == 'Buy' else 'SHORT'
                    })
            
            # ✅ Не логируем частые запросы (только при изменениях)
            
            # Возвращаем ВСЕ позиции с биржи, не фильтруя по наличию ботов в системе
            # Это нужно для правильной работы синхронизации и очистки неактивных ботов
            filtered_positions = []
            ignored_positions = []
            
            for pos in processed_positions:
                symbol = pos['symbol']
                # Добавляем все позиции без фильтрации
                filtered_positions.append(pos)
            
            # ✅ Не логируем частые запросы (только при изменениях)
            return filtered_positions
            
        except Exception as api_error:
            logger.error(f"[EXCHANGE_POSITIONS] ❌ Ошибка прямого обращения к API: {api_error}")
            # Fallback к существующему методу
            positions, _ = exchange.get_positions()
            logger.info(f"[EXCHANGE_POSITIONS] Fallback: получено {len(positions) if positions else 0} позиций")
            
            if not positions:
                return []
            
            # Обрабатываем fallback позиции
            processed_positions = []
            for position in positions:
                # Позиции уже обработаны в exchange.get_positions()
                symbol = position.get('symbol', '')
                size = position.get('size', 0)
                side = position.get('side', '')  # 'Long' или 'Short'
                
                if abs(size) > 0:
                    processed_positions.append({
                        'symbol': symbol,
                        'size': size,
                        'side': side,
                        'entry_price': 0.0,  # Нет данных в обработанном формате
                        'unrealized_pnl': position.get('pnl', 0),
                        'mark_price': 0.0,
                        'position_side': side
                    })
            
            # КРИТИЧЕСКИ ВАЖНО: Фильтруем fallback позиции тоже
            with bots_data_lock:
                system_bot_symbols = set(bots_data['bots'].keys())
            
            filtered_positions = []
            ignored_positions = []
            
            for pos in processed_positions:
                symbol = pos['symbol']
                if symbol in system_bot_symbols:
                    filtered_positions.append(pos)
                else:
                    ignored_positions.append(pos)
            
            if ignored_positions:
                logger.info(f"[EXCHANGE_POSITIONS] 🚫 Fallback: Игнорируем {len(ignored_positions)} позиций без ботов в системе")
            
            logger.info(f"[EXCHANGE_POSITIONS] ✅ Fallback: Возвращаем {len(filtered_positions)} позиций с ботами в системе")
            return filtered_positions
            
        except Exception as e:
            logger.error(f"[EXCHANGE_POSITIONS] ❌ Ошибка в попытке {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"[EXCHANGE_POSITIONS] ❌ Не удалось получить позиции после {max_retries} попыток")
                return []
    
    # Если мы дошли сюда, значит все попытки исчерпаны
    logger.error(f"[EXCHANGE_POSITIONS] ❌ Все попытки исчерпаны")
    return []

def compare_bot_and_exchange_positions():
    """Сравнивает позиции ботов в системе с реальными позициями на бирже"""
    try:
        # Получаем позиции с биржи
        exchange_positions = get_exchange_positions()
        
        # Получаем ботов в позиции из системы
        with bots_data_lock:
            bot_positions = []
            for symbol, bot_data in bots_data['bots'].items():
                if bot_data.get('status') in ['in_position_long', 'in_position_short']:
                    bot_positions.append({
                        'symbol': symbol,
                        'position_side': bot_data.get('position_side'),
                        'entry_price': bot_data.get('entry_price'),
                        'status': bot_data.get('status')
                    })
        
        # Создаем словари для удобного сравнения
        exchange_dict = {pos['symbol']: pos for pos in exchange_positions}
        bot_dict = {pos['symbol']: pos for pos in bot_positions}
        
        # Находим расхождения
        discrepancies = {
            'missing_in_bot': [],  # Есть на бирже, нет в боте (НЕ создаем ботов!)
            'missing_in_exchange': [],  # Есть в боте, нет на бирже (обновляем статус)
            'side_mismatch': []  # Есть в обоих, но стороны не совпадают (исправляем)
        }
        
        # Проверяем позиции на бирже
        for symbol, exchange_pos in exchange_dict.items():
            if symbol not in bot_dict:
                discrepancies['missing_in_bot'].append({
                    'symbol': symbol,
                    'exchange_side': exchange_pos['position_side'],
                    'exchange_entry_price': exchange_pos['entry_price'],
                    'exchange_pnl': exchange_pos['unrealized_pnl']
                })
            else:
                bot_pos = bot_dict[symbol]
                if bot_pos['position_side'] != exchange_pos['position_side']:
                    discrepancies['side_mismatch'].append({
                        'symbol': symbol,
                        'bot_side': bot_pos['position_side'],
                        'exchange_side': exchange_pos['position_side'],
                        'bot_entry_price': bot_pos['entry_price'],
                        'exchange_entry_price': exchange_pos['entry_price']
                    })
        
        # Проверяем позиции в боте
        for symbol, bot_pos in bot_dict.items():
            if symbol not in exchange_dict:
                discrepancies['missing_in_exchange'].append({
                    'symbol': symbol,
                    'bot_side': bot_pos['position_side'],
                    'bot_entry_price': bot_pos['entry_price'],
                    'bot_status': bot_pos['status']
                })
        
        # Логируем результаты
        total_discrepancies = (len(discrepancies['missing_in_bot']) + 
                             len(discrepancies['missing_in_exchange']) + 
                             len(discrepancies['side_mismatch']))
        
        if total_discrepancies > 0:
            logger.warning(f"[POSITION_SYNC] ⚠️ Обнаружено {total_discrepancies} расхождений между ботом и биржей")
            
            if discrepancies['missing_in_bot']:
                logger.info(f"[POSITION_SYNC] 📊 Позиции на бирже без бота в системе: {len(discrepancies['missing_in_bot'])} (игнорируем - не создаем ботов)")
                for pos in discrepancies['missing_in_bot']:
                    logger.info(f"[POSITION_SYNC]   - {pos['symbol']}: {pos['exchange_side']} ${pos['exchange_entry_price']:.6f} (PnL: {pos['exchange_pnl']:.2f}) - НЕ создаем бота")
            
            if discrepancies['missing_in_exchange']:
                logger.warning(f"[POSITION_SYNC] 🤖 Боты без позиций на бирже: {len(discrepancies['missing_in_exchange'])}")
                for pos in discrepancies['missing_in_exchange']:
                    logger.warning(f"[POSITION_SYNC]   - {pos['symbol']}: {pos['bot_side']} ${pos['bot_entry_price']:.6f} (статус: {pos['bot_status']})")
            
            if discrepancies['side_mismatch']:
                logger.warning(f"[POSITION_SYNC] 🔄 Несовпадение сторон: {len(discrepancies['side_mismatch'])}")
                for pos in discrepancies['side_mismatch']:
                    logger.warning(f"[POSITION_SYNC]   - {pos['symbol']}: бот={pos['bot_side']}, биржа={pos['exchange_side']}")
        else:
            logger.info(f"[POSITION_SYNC] ✅ Синхронизация позиций: все {len(bot_positions)} ботов соответствуют бирже")
        
        return discrepancies
        
    except Exception as e:
        logger.error(f"[POSITION_SYNC] ❌ Ошибка сравнения позиций: {e}")
        return None

def sync_positions_with_exchange():
    """Умная синхронизация позиций ботов с реальными позициями на бирже"""
    try:
        # ✅ Не логируем частые синхронизации (только результаты при изменениях)
        
        # Получаем позиции с биржи с retry логикой
        exchange_positions = get_exchange_positions()
        
        # Если не удалось получить позиции с биржи, НЕ сбрасываем ботов
        if not exchange_positions:
            logger.warning("[POSITION_SYNC] ⚠️ Не удалось получить позиции с биржи - пропускаем синхронизацию")
            return False
        
        # Получаем ботов в позиции из системы
        with bots_data_lock:
            bot_positions = []
            for symbol, bot_data in bots_data['bots'].items():
                if bot_data.get('status') in ['in_position_long', 'in_position_short']:
                    bot_positions.append({
                        'symbol': symbol,
                        'position_side': bot_data.get('position_side'),
                        'entry_price': bot_data.get('entry_price'),
                        'status': bot_data.get('status'),
                        'unrealized_pnl': bot_data.get('unrealized_pnl', 0)
                    })
        
        # ✅ Логируем только если есть БОТЫ (несоответствия важны)
        if len(bot_positions) > 0:
            logger.info(f"[POSITION_SYNC] 📊 Биржа: {len(exchange_positions)}, Боты: {len(bot_positions)}")
        
        # Создаем словари для удобного сравнения
        exchange_dict = {pos['symbol']: pos for pos in exchange_positions}
        bot_dict = {pos['symbol']: pos for pos in bot_positions}
        
        synced_count = 0
        errors_count = 0
        
        # Обрабатываем ботов без позиций на бирже
        for symbol, bot_data in bot_dict.items():
            if symbol not in exchange_dict:
                logger.warning(f"[POSITION_SYNC] ⚠️ Бот {symbol} без позиции на бирже (статус: {bot_data['status']})")
                
                # ВАЖНО: Проверяем, действительно ли позиция закрылась
                # Не сбрасываем ботов сразу - даем им время на восстановление
                try:
                    # Проверяем, есть ли активные ордера для этого символа
                    has_active_orders = check_active_orders(symbol)
                    
                    if not has_active_orders:
                        # Только если нет активных ордеров, сбрасываем бота
                        with bots_data_lock:
                            if symbol in bots_data['bots']:
                                bots_data['bots'][symbol]['status'] = 'idle'
                                bots_data['bots'][symbol]['position_side'] = None
                                bots_data['bots'][symbol]['entry_price'] = None
                                bots_data['bots'][symbol]['unrealized_pnl'] = 0
                                bots_data['bots'][symbol]['last_update'] = datetime.now().isoformat()
                                synced_count += 1
                                logger.info(f"[POSITION_SYNC] ✅ Сброшен статус бота {symbol} на 'idle' (позиция закрыта)")
                    else:
                        logger.info(f"[POSITION_SYNC] ⏳ Бот {symbol} имеет активные ордера - оставляем в позиции")
                        
                except Exception as check_error:
                    logger.error(f"[POSITION_SYNC] ❌ Ошибка проверки ордеров для {symbol}: {check_error}")
                    errors_count += 1
        
        # Обрабатываем несовпадения сторон - исправляем данные бота в соответствии с биржей
        for symbol, exchange_pos in exchange_dict.items():
            if symbol in bot_dict:
                bot_data = bot_dict[symbol]
                exchange_side = exchange_pos['position_side']
                bot_side = bot_data['position_side']
                
                if exchange_side != bot_side:
                    logger.warning(f"[POSITION_SYNC] 🔄 Исправление стороны позиции: {symbol} {bot_side} -> {exchange_side}")
                    
                    try:
                        with bots_data_lock:
                            if symbol in bots_data['bots']:
                                bots_data['bots'][symbol]['position_side'] = exchange_side
                                bots_data['bots'][symbol]['entry_price'] = exchange_pos['entry_price']
                                bots_data['bots'][symbol]['status'] = f'in_position_{exchange_side.lower()}'
                                bots_data['bots'][symbol]['unrealized_pnl'] = exchange_pos['unrealized_pnl']
                                bots_data['bots'][symbol]['last_update'] = datetime.now().isoformat()
                                synced_count += 1
                                logger.info(f"[POSITION_SYNC] ✅ Исправлены данные бота {symbol} в соответствии с биржей")
                    except Exception as update_error:
                        logger.error(f"[POSITION_SYNC] ❌ Ошибка обновления бота {symbol}: {update_error}")
                        errors_count += 1
        
        # Логируем результаты
        if synced_count > 0:
            logger.info(f"[POSITION_SYNC] ✅ Синхронизировано {synced_count} ботов")
        if errors_count > 0:
            logger.warning(f"[POSITION_SYNC] ⚠️ Ошибок при синхронизации: {errors_count}")
        
        return synced_count > 0
        
    except Exception as e:
        logger.error(f"[POSITION_SYNC] ❌ Критическая ошибка синхронизации позиций: {e}")
        return False

def check_active_orders(symbol):
    """Проверяет, есть ли активные ордера для символа"""
    try:
        if not ensure_exchange_initialized():
            return False
        
        # Получаем активные ордера для символа
        orders = exchange.get_open_orders(symbol)
        return len(orders) > 0
        
    except Exception as e:
        logger.error(f"[ORDER_CHECK] ❌ Ошибка проверки ордеров для {symbol}: {e}")
        return False

def cleanup_inactive_bots():
    """Удаляет ботов, которые не имеют реальных позиций на бирже в течение INACTIVE_BOT_TIMEOUT секунд"""
    try:
        current_time = time.time()
        removed_count = 0
        
        # Получаем реальные позиции с биржи
        exchange_positions = get_exchange_positions()
        
        # КРИТИЧЕСКИ ВАЖНО: Если не удалось получить позиции с биржи, НЕ УДАЛЯЕМ ботов!
        if not exchange_positions:
            logger.warning(f"[INACTIVE_CLEANUP] ⚠️ Не удалось получить позиции с биржи - пропускаем очистку для безопасности")
            return False
        
        exchange_symbols = {pos['symbol'] for pos in exchange_positions}
        
        # Добавляем символы с USDT суффиксом для проверки
        exchange_symbols_with_usdt = set()
        for symbol in exchange_positions:
            clean_symbol = symbol['symbol']  # Уже без USDT
            exchange_symbols_with_usdt.add(clean_symbol)
            exchange_symbols_with_usdt.add(f"{clean_symbol}USDT")
        exchange_symbols = exchange_symbols_with_usdt
        
        logger.info(f"[INACTIVE_CLEANUP] 🔍 Проверка {len(bots_data['bots'])} ботов на неактивность")
        logger.info(f"[INACTIVE_CLEANUP] 📊 Найдено {len(exchange_symbols)} активных позиций на бирже: {sorted(exchange_symbols)}")
        
        with bots_data_lock:
            bots_to_remove = []
            
            for symbol, bot_data in bots_data['bots'].items():
                bot_status = bot_data.get('status', 'idle')
                last_update_str = bot_data.get('last_update')
                
                # КРИТИЧЕСКИ ВАЖНО: НЕ УДАЛЯЕМ ботов, которые находятся в позиции!
                if bot_status in ['in_position_long', 'in_position_short']:
                    logger.info(f"[INACTIVE_CLEANUP] 🛡️ Бот {symbol} в позиции {bot_status} - НЕ УДАЛЯЕМ")
                    continue
                
                # Пропускаем ботов, которые имеют реальные позиции на бирже
                if symbol in exchange_symbols:
                    continue
                
                # Убрали хардкод - теперь проверяем только реальные позиции на бирже
                
                # Пропускаем ботов в статусе 'idle' - они могут быть в ожидании
                if bot_status == 'idle':
                    continue
                
                # КРИТИЧЕСКИ ВАЖНО: Не удаляем ботов, которые только что загружены
                # Проверяем, что бот был создан недавно (в течение последних 5 минут)
                created_time_str = bot_data.get('created_time')
                if created_time_str:
                    try:
                        created_time = datetime.fromisoformat(created_time_str.replace('Z', '+00:00'))
                        time_since_creation = current_time - created_time.timestamp()
                        if time_since_creation < 300:  # 5 минут
                            logger.info(f"[INACTIVE_CLEANUP] ⏳ Бот {symbol} создан {time_since_creation//60:.0f} мин назад, пропускаем удаление")
                            continue
                    except Exception as e:
                        logger.warning(f"[INACTIVE_CLEANUP] ⚠️ Ошибка парсинга времени создания для {symbol}: {e}")
                
                # Проверяем время последнего обновления
                if last_update_str:
                    try:
                        last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
                        time_since_update = current_time - last_update.timestamp()
                        
                        if time_since_update >= INACTIVE_BOT_TIMEOUT:
                            logger.warning(f"[INACTIVE_CLEANUP] ⏰ Бот {symbol} неактивен {time_since_update//60:.0f} мин (статус: {bot_status})")
                            bots_to_remove.append(symbol)
                            
                            # Логируем удаление неактивного бота в историю
                            log_bot_stop(symbol, f"Неактивен {time_since_update//60:.0f} мин (статус: {bot_status})")
                        else:
                            logger.info(f"[INACTIVE_CLEANUP] ⏳ Бот {symbol} неактивен {time_since_update//60:.0f} мин, ждем до {INACTIVE_BOT_TIMEOUT//60} мин")
                    except Exception as e:
                        logger.error(f"[INACTIVE_CLEANUP] ❌ Ошибка парсинга времени для {symbol}: {e}")
                        # Если не можем распарсить время, считаем бота неактивным
                        bots_to_remove.append(symbol)
                else:
                    # Если нет времени последнего обновления, считаем бота неактивным
                    logger.warning(f"[INACTIVE_CLEANUP] ⚠️ Бот {symbol} без времени последнего обновления")
                    bots_to_remove.append(symbol)
            
            # Удаляем неактивных ботов
            for symbol in bots_to_remove:
                bot_data = bots_data['bots'][symbol]
                logger.info(f"[INACTIVE_CLEANUP] 🗑️ Удаление неактивного бота {symbol} (статус: {bot_data.get('status')})")
                del bots_data['bots'][symbol]
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"[INACTIVE_CLEANUP] ✅ Удалено {removed_count} неактивных ботов")
            # Сохраняем состояние
            save_bots_state()
        else:
            logger.info(f"[INACTIVE_CLEANUP] ✅ Неактивных ботов для удаления не найдено")
        
        return removed_count > 0
        
    except Exception as e:
        logger.error(f"[INACTIVE_CLEANUP] ❌ Ошибка очистки неактивных ботов: {e}")
        return False

# УДАЛЕНО: cleanup_mature_coins_without_trades()
# Зрелость монеты необратима - если монета стала зрелой, она не может стать незрелой!
# Файл зрелых монет можно только дополнять новыми, но не очищать от старых

def remove_mature_coins(coins_to_remove):
    """
    Удаляет конкретные монеты из файла зрелых монет
    
    Args:
        coins_to_remove: список символов монет для удаления (например: ['ARIA', 'AVNT'])
    
    Returns:
        dict: результат операции с количеством удаленных монет
    """
    try:
        if not isinstance(coins_to_remove, list):
            coins_to_remove = [coins_to_remove]
        
        removed_count = 0
        not_found = []
        
        logger.info(f"[MATURE_REMOVE] 🗑️ Запрос на удаление монет: {coins_to_remove}")
        
        with mature_coins_lock:
            for symbol in coins_to_remove:
                if symbol in mature_coins_storage:
                    del mature_coins_storage[symbol]
                    removed_count += 1
                    logger.info(f"[MATURE_REMOVE] ✅ Удалена монета {symbol} из зрелых")
                else:
                    not_found.append(symbol)
                    logger.warning(f"[MATURE_REMOVE] ⚠️ Монета {symbol} не найдена в зрелых")
        
        # Сохраняем изменения
        if removed_count > 0:
            save_mature_coins_storage()
            logger.info(f"[MATURE_REMOVE] 💾 Сохранено состояние зрелых монет")
        
        return {
            'success': True,
            'removed_count': removed_count,
            'removed_coins': [coin for coin in coins_to_remove if coin not in not_found],
            'not_found': not_found,
            'message': f'Удалено {removed_count} монет из зрелых'
        }
        
    except Exception as e:
        logger.error(f"[MATURE_REMOVE] ❌ Ошибка удаления монет: {e}")
        return {
            'success': False,
            'error': str(e),
            'removed_count': 0
        }

def check_trading_rules_activation():
    """Проверяет и активирует правила торговли для зрелых монет"""
    try:
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Auto Bot должен быть включен для автоматического создания ботов
        with bots_data_lock:
            auto_bot_enabled = bots_data.get('auto_bot_config', {}).get('enabled', False)
        
        if not auto_bot_enabled:
            logger.info(f"[TRADING_RULES] ⏹️ Auto Bot выключен - пропускаем активацию правил торговли")
            return False
        
        current_time = time.time()
        activated_count = 0
        
        logger.info(f"[TRADING_RULES] 🔍 Проверка активации правил торговли для зрелых монет")
        
        with mature_coins_lock:
            for symbol, coin_data in mature_coins_storage.items():
                last_verified = coin_data.get('last_verified', 0)
                time_since_verification = current_time - last_verified
                
                # Если монета зрелая и не проверялась более 5 минут, активируем правила торговли
                if time_since_verification > 300:  # 5 минут
                    logger.info(f"[TRADING_RULES] 🎯 Активация правил торговли для {symbol} (не проверялась {time_since_verification//60:.0f} мин)")
                    
                    # КРИТИЧЕСКИ ВАЖНО: Проверяем, нет ли уже позиции на бирже для этого символа
                    has_existing_position = False
                    try:
                        if ensure_exchange_initialized():
                            # Проверяем позиции на бирже для этого символа
                            positions_response = exchange.client.get_positions(
                                category="linear",
                                symbol=f"{symbol}USDT"
                            )
                            
                            if positions_response.get('retCode') == 0:
                                positions = positions_response['result']['list']
                                for pos in positions:
                                    pos_symbol = pos.get('symbol', '')
                                    if pos_symbol == f"{symbol}USDT":
                                        size = float(pos.get('size', 0))
                                        if abs(size) > 0:  # Есть активная позиция
                                            has_existing_position = True
                                            side = 'LONG' if pos.get('side') == 'Buy' else 'SHORT'
                                            logger.warning(f"[TRADING_RULES] 🚫 {symbol}: НА БИРЖЕ УЖЕ ЕСТЬ ПОЗИЦИЯ {side} размер {size} - НЕ СОЗДАЕМ БОТА!")
                                            break
                    except Exception as check_error:
                        logger.error(f"[TRADING_RULES] ⚠️ {symbol}: Ошибка проверки позиций на бирже: {check_error}")
                        # В случае ошибки проверки - НЕ создаем бота для безопасности
                        has_existing_position = True
                    
                    if has_existing_position:
                        logger.info(f"[TRADING_RULES] ⏭️ {symbol}: Пропускаем создание бота - есть позиция на бирже")
                        continue
                    
                    # Создаем бота для этой монеты, если его еще нет
                if symbol not in bots_data['bots']:
                    # КРИТИЧЕСКИ ВАЖНО: Блокируем обработку этой монеты чтобы избежать race conditions
                    coin_lock = get_coin_processing_lock(symbol)
                    with coin_lock:
                        # Двойная проверка после получения блокировки
                        if symbol not in bots_data['bots']:
                            try:
                                # Получаем конфигурацию автобота
                                with bots_data_lock:
                                    auto_bot_config = bots_data.get('auto_bot_config', {})
                                
                                # Создаем бота с базовой конфигурацией
                                bot_config = {
                                    'symbol': symbol,
                                    'status': 'running',
                                    'volume_mode': 'usdt',
                                    'volume_value': auto_bot_config.get('default_position_size', 20.0),
                                    'created_at': datetime.now().isoformat(),
                                    'last_signal_time': None
                                }
                                
                                bots_data['bots'][symbol] = bot_config
                                logger.info(f"[TRADING_RULES] ✅ Создан бот для {symbol}")
                                activated_count += 1
                                
                            except Exception as e:
                                logger.error(f"[TRADING_RULES] ❌ Ошибка создания бота для {symbol}: {e}")
                        else:
                            logger.debug(f"[TRADING_RULES] ⏳ Бот для {symbol} уже существует")
        
        if activated_count > 0:
            logger.info(f"[TRADING_RULES] ✅ Активированы правила торговли для {activated_count} монет")
            # Сохраняем состояние
            save_bots_state()
        else:
            logger.info(f"[TRADING_RULES] ✅ Нет зрелых монет для активации правил торговли")
        
        return activated_count > 0
        
    except Exception as e:
        logger.error(f"[TRADING_RULES] ❌ Ошибка активации правил торговли: {e}")
        return False

def check_missing_stop_losses():
    """Проверяет и устанавливает недостающие стоп-лоссы и трейлинг стопы для ботов"""
    try:
        if not ensure_exchange_initialized():
            return False
        
        with bots_data_lock:
            # Получаем конфигурацию трейлинг стопа
            trailing_activation = bots_data.get('trailing_stop_activation', 300)  # 3% по умолчанию
            trailing_distance = bots_data.get('trailing_stop_distance', 150)      # 1.5% по умолчанию
            
            # Получаем все позиции с биржи
            try:
                positions_response = exchange.client.get_positions(
                    category="linear",
                    settleCoin="USDT"
                )
                
                if positions_response.get('retCode') != 0:
                    logger.warning(f"[STOP_LOSS_SETUP] ⚠️ Ошибка получения позиций: {positions_response.get('retMsg')}")
                    return False
                
                exchange_positions = positions_response.get('result', {}).get('list', [])
                
            except Exception as e:
                logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка получения позиций с биржи: {e}")
                return False
            
            updated_count = 0
            failed_count = 0
            
            # Обрабатываем каждого бота в позиции
            for symbol, bot_data in bots_data['bots'].items():
                if bot_data.get('status') not in ['in_position_long', 'in_position_short']:
                    continue
                try:
                    # Ищем позицию на бирже для этого символа
                    pos = None
                    for position in exchange_positions:
                        pos_symbol = position.get('symbol', '').replace('USDT', '')
                        if pos_symbol == symbol:
                            pos = position
                            break
                    
                    if not pos:
                        logger.warning(f"[STOP_LOSS_SETUP] ⚠️ Позиция {symbol} не найдена на бирже")
                        continue
                    
                    position_size = float(pos.get('size', 0))
                    if position_size <= 0:
                        logger.warning(f"[STOP_LOSS_SETUP] ⚠️ Позиция {symbol} закрыта на бирже")
                        continue
                    
                    # Получаем данные позиции
                    entry_price = float(pos.get('avgPrice', 0))
                    current_price = float(pos.get('markPrice', 0))
                    unrealized_pnl = float(pos.get('unrealisedPnl', 0))
                    side = pos.get('side', '')
                    position_idx = pos.get('positionIdx', 0)
                    existing_stop_loss = pos.get('stopLoss', '')
                    existing_trailing_stop = pos.get('trailingStop', '')
                    
                    # Рассчитываем процент прибыли/убытка
                    if side == 'Buy':  # LONG позиция
                        profit_percent = ((current_price - entry_price) / entry_price) * 100
                    else:  # SHORT позиция
                        profit_percent = ((entry_price - current_price) / entry_price) * 100
                    
                    logger.info(f"[STOP_LOSS_SETUP] 📊 {symbol}: PnL {profit_percent:.2f}%, текущая цена {current_price}, вход {entry_price}")
                    
                    # Синхронизируем существующие стопы с биржи
                    if existing_stop_loss:
                        bot_data['stop_loss_price'] = float(existing_stop_loss)
                        logger.info(f"[STOP_LOSS_SETUP] ✅ Синхронизирован стоп-лосс для {symbol}: {existing_stop_loss}")
                    
                    if existing_trailing_stop:
                        bot_data['trailing_stop_price'] = float(existing_trailing_stop)
                        logger.info(f"[STOP_LOSS_SETUP] ✅ Синхронизирован трейлинг стоп для {symbol}: {existing_trailing_stop}")
                    
                    # Логика установки стоп-лоссов
                    if not existing_stop_loss:
                        # Устанавливаем обычный стоп-лосс
                        if side == 'Buy':  # LONG
                            stop_price = entry_price * 0.95  # 5% стоп-лосс
                        else:  # SHORT
                            stop_price = entry_price * 1.05  # 5% стоп-лосс
                        
                        try:
                            stop_result = exchange.client.set_trading_stop(
                                category="linear",
                                symbol=pos.get('symbol'),
                                positionIdx=position_idx,
                                stopLoss=str(stop_price)
                            )
                            
                            if stop_result and stop_result.get('retCode') == 0:
                                bot_data['stop_loss_price'] = stop_price
                                updated_count += 1
                                logger.info(f"[STOP_LOSS_SETUP] ✅ Установлен стоп-лосс для {symbol}: {stop_price}")
                            else:
                                logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка установки стоп-лосса для {symbol}: {stop_result.get('retMsg')}")
                                failed_count += 1
                        except Exception as e:
                            logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка API для {symbol}: {e}")
                            failed_count += 1
                    
                    # Логика трейлинг стопа (только при прибыли)
                    elif profit_percent >= (trailing_activation / 100):  # Прибыль больше порога активации
                        if not existing_trailing_stop:
                            # Устанавливаем трейлинг стоп
                            try:
                                trailing_result = exchange.client.set_trading_stop(
                                    category="linear",
                                    symbol=pos.get('symbol'),
                                    positionIdx=position_idx,
                                    trailingStop=str(trailing_distance / 100)  # Конвертируем в десятичную дробь
                                )
                                
                                if trailing_result and trailing_result.get('retCode') == 0:
                                    bot_data['trailing_stop_price'] = trailing_distance / 100
                                    updated_count += 1
                                    logger.info(f"[STOP_LOSS_SETUP] ✅ Установлен трейлинг стоп для {symbol}: {trailing_distance/100}%")
                                else:
                                    logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка установки трейлинг стопа для {symbol}: {trailing_result.get('retMsg')}")
                                    failed_count += 1
                            except Exception as e:
                                logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка API трейлинг стопа для {symbol}: {e}")
                                failed_count += 1
                        else:
                            logger.info(f"[STOP_LOSS_SETUP] ✅ Трейлинг стоп уже активен для {symbol}")
                    
                    # Обновляем время последнего обновления
                    bot_data['last_update'] = datetime.now().isoformat()
                        
                except Exception as e:
                    logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка обработки {symbol}: {e}")
                    failed_count += 1
                    continue
            
            if updated_count > 0 or failed_count > 0:
                logger.info(f"[STOP_LOSS_SETUP] ✅ Установка завершена: установлено {updated_count}, ошибок {failed_count}")
                
                # Сохраняем обновленные данные ботов в файл
                if updated_count > 0:
                    try:
                        save_bots_state()
                        logger.info(f"[STOP_LOSS_SETUP] 💾 Сохранено состояние ботов в файл")
                    except Exception as save_error:
                        logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка сохранения состояния ботов: {save_error}")
            
            return True
            
    except Exception as e:
        logger.error(f"[STOP_LOSS_SETUP] ❌ Ошибка установки стоп-лоссов: {e}")
        return False

def check_startup_position_conflicts():
    """Проверяет конфликты позиций при запуске системы и принудительно останавливает проблемные боты"""
    try:
        if not ensure_exchange_initialized():
            logger.warning("[STARTUP_CONFLICTS] ⚠️ Биржа не инициализирована, пропускаем проверку конфликтов")
            return False
        
        logger.info("[STARTUP_CONFLICTS] 🔍 Проверка конфликтов...")
        
        conflicts_found = 0
        bots_paused = 0
        
        with bots_data_lock:
            for symbol, bot_data in bots_data['bots'].items():
                try:
                    bot_status = bot_data.get('status')
                    
                    # Проверяем только активные боты (не idle/paused)
                    if bot_status in [BOT_STATUS['IDLE'], BOT_STATUS['PAUSED']]:
                        continue
                    
                    # Проверяем позицию на бирже
                    positions_response = exchange.client.get_positions(
                        category="linear",
                        symbol=f"{symbol}USDT"
                    )
                    
                    if positions_response.get('retCode') == 0:
                        positions = positions_response['result']['list']
                        has_position = False
                        
                        # Фильтруем позиции только для нужного символа
                        target_symbol = f"{symbol}USDT"
                        for pos in positions:
                            pos_symbol = pos.get('symbol', '')
                            if pos_symbol == target_symbol:  # Проверяем только нужный символ
                                size = float(pos.get('size', 0))
                                if abs(size) > 0:  # Есть активная позиция
                                    has_position = True
                                    side = 'LONG' if pos.get('side') == 'Buy' else 'SHORT'
                                    break
                        
                        # Проверяем конфликт
                        if has_position:
                            # Есть позиция на бирже
                            if bot_status in [BOT_STATUS['RUNNING'], BOT_STATUS['ARMED_UP'], BOT_STATUS['ARMED_DOWN']]:
                                # КОНФЛИКТ: бот активен, но позиция уже есть на бирже
                                logger.warning(f"[STARTUP_CONFLICTS] 🚨 {symbol}: КОНФЛИКТ! Бот {bot_status}, но позиция {side} уже есть на бирже!")
                                
                                # Принудительно останавливаем бота
                                bot_data['status'] = BOT_STATUS['PAUSED']
                                bot_data['last_update'] = datetime.now().isoformat()
                                
                                conflicts_found += 1
                                bots_paused += 1
                                
                                logger.warning(f"[STARTUP_CONFLICTS] 🔴 {symbol}: Бот принудительно остановлен (PAUSED)")
                                
                            elif bot_status in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
                                # Корректное состояние - бот в позиции
                                logger.debug(f"[STARTUP_CONFLICTS] ✅ {symbol}: Статус корректный - бот в позиции")
                        else:
                            # Нет позиции на бирже
                            if bot_status in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
                                # КОНФЛИКТ: бот думает что в позиции, но позиции нет на бирже
                                logger.warning(f"[STARTUP_CONFLICTS] 🚨 {symbol}: КОНФЛИКТ! Бот показывает позицию, но на бирже её нет!")
                                
                                # Сбрасываем статус бота
                                bot_data['status'] = BOT_STATUS['IDLE']
                                bot_data['entry_price'] = None
                                bot_data['position_side'] = None
                                bot_data['unrealized_pnl'] = 0.0
                                bot_data['last_update'] = datetime.now().isoformat()
                                
                                conflicts_found += 1
                                
                                logger.warning(f"[STARTUP_CONFLICTS] 🔄 {symbol}: Статус сброшен в IDLE")
                            else:
                                # Корректное состояние - нет позиций
                                logger.debug(f"[STARTUP_CONFLICTS] ✅ {symbol}: Статус корректный - нет позиций")
                    else:
                        logger.warning(f"[STARTUP_CONFLICTS] ❌ {symbol}: Ошибка получения позиций: {positions_response.get('retMsg', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"[STARTUP_CONFLICTS] ❌ Ошибка проверки {symbol}: {e}")
        
        if conflicts_found > 0:
            logger.warning(f"[STARTUP_CONFLICTS] 🚨 Найдено {conflicts_found} конфликтов, остановлено {bots_paused} ботов")
            # Сохраняем обновленное состояние
            save_bots_state()
        else:
            logger.info("[STARTUP_CONFLICTS] ✅ Конфликтов позиций не найдено")
        
        return conflicts_found > 0
        
    except Exception as e:
        logger.error(f"[STARTUP_CONFLICTS] ❌ Общая ошибка проверки конфликтов: {e}")
        return False

def sync_bots_with_exchange():
    """Синхронизирует состояние ботов с открытыми позициями на бирже"""
    try:
        if not ensure_exchange_initialized():
            logger.warning("[SYNC_EXCHANGE] ⚠️ Биржа не инициализирована, пропускаем синхронизацию")
            return False
        
        logger.info("[SYNC_EXCHANGE] 🔄 Синхронизация с биржей...")
        
        # Получаем ВСЕ открытые позиции с биржи (с пагинацией)
        try:
            exchange_positions = {}
            cursor = ""
            total_positions = 0
            
            while True:
                # Запрашиваем позиции с cursor для получения всех страниц
                params = {
                    "category": "linear", 
                    "settleCoin": "USDT",
                    "limit": 200  # Максимум за запрос
                }
                if cursor:
                    params["cursor"] = cursor
                    
                positions_response = exchange.client.get_positions(**params)
                
                if positions_response["retCode"] != 0:
                    logger.error(f"[SYNC_EXCHANGE] ❌ Ошибка получения позиций: {positions_response['retMsg']}")
                    return False
                
                # Обрабатываем позиции на текущей странице
                for position in positions_response["result"]["list"]:
                    symbol = position.get("symbol")
                    size = float(position.get("size", 0))
                    
                    if abs(size) > 0:  # Любые открытые позиции (LONG или SHORT)
                        # Убираем USDT из символа для сопоставления с ботами
                        clean_symbol = symbol.replace('USDT', '')
                        exchange_positions[clean_symbol] = {
                            'size': abs(size),
                            'side': position.get("side"),
                            'avg_price': float(position.get("avgPrice", 0)),
                            'unrealized_pnl': float(position.get("unrealisedPnl", 0)),
                            'position_value': float(position.get("positionValue", 0))
                        }
                        total_positions += 1
                        # logger.info(f"[SYNC_EXCHANGE] 📊 Найдена позиция: {symbol} -> {clean_symbol}, размер={abs(size)}, сторона={position.get('side')}, PnL=${float(position.get('unrealisedPnl', 0)):.2f}")
                
                # Проверяем есть ли еще страницы
                next_page_cursor = positions_response["result"].get("nextPageCursor", "")
                if not next_page_cursor:
                    break
                cursor = next_page_cursor
            
            # ✅ Не логируем общее количество (избыточно)
            
            # Получаем символы ботов в системе для фильтрации
            with bots_data_lock:
                system_bot_symbols = set(bots_data['bots'].keys())
            
            # Разделяем позиции на бирже на "с ботом" и "без бота"
            positions_with_bots = {}
            positions_without_bots = {}
            
            for symbol, pos_data in exchange_positions.items():
                # Проверяем как символ без USDT, так и с USDT
                if symbol in system_bot_symbols or f"{symbol}USDT" in system_bot_symbols:
                    positions_with_bots[symbol] = pos_data
                else:
                    positions_without_bots[symbol] = pos_data
            
            # ✅ Одна информативная строка вместо двух
            if positions_without_bots:
                logger.info(f"[SYNC_EXCHANGE] 🚫 Игнорируем {len(positions_without_bots)} позиций без ботов (всего на бирже: {len(exchange_positions)})")
            
            # ✅ Логируем только если есть позиции С ботами
            if positions_with_bots:
                logger.info(f"[SYNC_EXCHANGE] ✅ Обрабатываем {len(positions_with_bots)} позиций с ботами")
            
            # Синхронизируем только с позициями, для которых есть боты
            synchronized_bots = 0
            
            with bots_data_lock:
                for symbol, bot_data in bots_data['bots'].items():
                    try:
                        if symbol in positions_with_bots:
                            # Есть позиция на бирже - обновляем данные бота
                            exchange_pos = positions_with_bots[symbol]
                            
                            # Обновляем данные бота согласно позиции на бирже
                            old_status = bot_data.get('status', 'UNKNOWN')
                            old_pnl = bot_data.get('unrealized_pnl', 0)
                            
                            bot_data['entry_price'] = exchange_pos['avg_price']
                            bot_data['unrealized_pnl'] = exchange_pos['unrealized_pnl']
                            bot_data['position_side'] = 'LONG' if exchange_pos['side'] == 'Buy' else 'SHORT'
                            
                            # Определяем статус на основе наличия позиции
                            if exchange_pos['side'] == 'Buy':
                                bot_data['status'] = BOT_STATUS['IN_POSITION_LONG']
                            else:
                                bot_data['status'] = BOT_STATUS['IN_POSITION_SHORT']
                            
                            synchronized_bots += 1
                            
                            # Добавляем детали позиции
                            entry_price = exchange_pos['avg_price']
                            current_price = exchange_pos.get('mark_price', entry_price)
                            position_size = exchange_pos.get('size', 0)
                            
                            # logger.info(f"[SYNC_EXCHANGE] 🔄 {symbol}: {old_status}→{bot_data['status']}, PnL: ${old_pnl:.2f}→${exchange_pos['unrealized_pnl']:.2f}")
                            # logger.info(f"[SYNC_EXCHANGE] 📊 {symbol}: Вход=${entry_price:.4f} | Текущая=${current_price:.4f} | Размер={position_size}")
                            
                        else:
                            # Нет позиции на бирже - если бот думает что в позиции, сбрасываем
                            if bot_data.get('status') in [BOT_STATUS['IN_POSITION_LONG'], BOT_STATUS['IN_POSITION_SHORT']]:
                                old_status = bot_data['status']
                                bot_data['status'] = BOT_STATUS['IDLE']
                                bot_data['entry_price'] = None
                                bot_data['position_side'] = None
                                bot_data['unrealized_pnl'] = 0.0
                                
                                synchronized_bots += 1
                                # logger.info(f"[SYNC_EXCHANGE] 🔄 {symbol}: {old_status}→IDLE (позиция закрыта на бирже)")
                        
                    except Exception as e:
                        logger.error(f"[SYNC_EXCHANGE] ❌ Ошибка синхронизации бота {symbol}: {e}")
            
            logger.info(f"[SYNC_EXCHANGE] ✅ Синхронизировано {synchronized_bots} ботов")
            
            # Сохраняем обновленное состояние
            save_bots_state()
            
            return True
            
        except Exception as e:
            logger.error(f"[SYNC_EXCHANGE] ❌ Ошибка получения позиций с биржи: {e}")
            return False
        
    except Exception as e:
        logger.error(f"[SYNC_EXCHANGE] ❌ Общая ошибка синхронизации: {e}")
        return False

def auto_save_worker():
    """Воркер для автоматического сохранения состояния согласно конфигурации"""
    interval = SystemConfig.AUTO_SAVE_INTERVAL
    logger.info(f"[AUTO_SAVE] 💾 Запуск Auto Save Worker (сохранение каждые {interval} секунд)")
    
    while not shutdown_flag.is_set():
        try:
            # Ждем согласно конфигурации
            if shutdown_flag.wait(interval):
                break
            
            # Сохраняем состояние
            with bots_data_lock:
                bots_count = len(bots_data['bots'])
            
            if bots_count > 0:
                # Логируем только при первом сохранении или если прошло 5 минут
                should_log = (getattr(auto_save_worker, '_last_log_time', 0) + 300 < time.time())
                if should_log:
                    logger.info(f"[AUTO_SAVE] 💾 Автосохранение состояния {bots_count} ботов...")
                    auto_save_worker._last_log_time = time.time()
                save_result = save_bots_state()
                
                # Обновляем статистику
                update_process_state('auto_save_worker', {
                    'last_save': datetime.now().isoformat(),
                    'save_count': process_state['auto_save_worker']['save_count'] + 1,
                    'last_error': None if save_result else 'Save failed'
                })
            
        except Exception as e:
            logger.error(f"[AUTO_SAVE] ❌ Ошибка автосохранения: {e}")
    
    logger.info("[AUTO_SAVE] 💾 Auto Save Worker остановлен")

def auto_bot_worker():
    """Воркер для регулярной проверки Auto Bot сигналов - УДАЛЕНО!"""
    logger.info("[AUTO_BOT] 🚫 Auto Bot Worker отключен!")
    return
    
    # КРИТИЧЕСКИ ВАЖНО: Ждем полной инициализации системы!
    logger.info("[AUTO_BOT] ⏳ Ожидание полной инициализации системы...")
    wait_start = time.time()
    while not system_initialized and not shutdown_flag.is_set():
        if time.time() - wait_start > 60:  # Таймаут 60 секунд
            logger.error("[AUTO_BOT] ❌ Таймаут ожидания инициализации!")
            return
        time.sleep(1)
    
    if not system_initialized:
        logger.error("[AUTO_BOT] ❌ Система не инициализирована, воркер остановлен!")
        return
    
    # КРИТИЧЕСКИ ВАЖНО: Проверяем, что автобот выключен при запуске!
    with bots_data_lock:
        auto_bot_enabled = bots_data['auto_bot_config']['enabled']
    
    if auto_bot_enabled:
        logger.warning("[AUTO_BOT] ⚠️ Автобот включен при запуске! Принудительно выключаем для безопасности...")
        with bots_data_lock:
            bots_data['auto_bot_config']['enabled'] = False
            save_auto_bot_config()  # Сохраняем изменение
        logger.warning("[AUTO_BOT] 🔒 Автобот выключен. Включите его вручную через UI.")
    
    logger.info("[AUTO_BOT] ✅ Система инициализирована, автобот выключен - воркер запущен в режиме ожидания")
    
    last_position_update = time.time() - BOT_STATUS_UPDATE_INTERVAL  # Время последнего обновления позиций
    last_stop_loss_setup = time.time() - STOP_LOSS_SETUP_INTERVAL  # Время последней установки стоп-лоссов
    last_position_sync = time.time() - POSITION_SYNC_INTERVAL  # Время последней синхронизации позиций
    last_inactive_cleanup = time.time() - INACTIVE_BOT_CLEANUP_INTERVAL  # Время последней очистки неактивных ботов
    
    logger.info("[AUTO_BOT] 🔄 Входим в основной цикл...")
    while not shutdown_flag.is_set():
        try:
            # Получаем интервал проверки из конфигурации (в секундах)
            with bots_data_lock:
                check_interval_seconds = bots_data['auto_bot_config']['check_interval']
                auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            
            # Ждем согласно конфигурации
            if shutdown_flag.wait(check_interval_seconds):
                break
            
            # Проверяем сигналы только если Auto Bot включен
            if auto_bot_enabled:
                # Подавляем частые сообщения о проверке сигналов
                should_log, log_message = should_log_message(
                    'auto_bot_signals', 
                    f"🔍 Регулярная проверка Auto Bot сигналов (каждые {check_interval_seconds} сек)",
                    interval_seconds=300  # Логируем раз в 5 минут
                )
                if should_log:
                    logger.info(f"[AUTO_BOT] {log_message}")
                
                logger.info(f"[AUTO_BOT] 🚀 Вызываем process_auto_bot_signals...")
                # process_auto_bot_signals(exchange_obj=exchange)  # ОТКЛЮЧЕНО!
                logger.info(f"[AUTO_BOT] ✅ process_auto_bot_signals завершена")
                
                # Обновляем статистику
                current_count = process_state.get('auto_bot_worker', {}).get('check_count', 0)
                update_process_state('auto_bot_worker', {
                    'last_check': datetime.now().isoformat(),
                    'check_count': current_count + 1,
                    'interval_seconds': check_interval_seconds,
                    'enabled': True
                })
            else:
                logger.info(f"[AUTO_BOT] ⏹️ Auto Bot выключен, пропускаем проверку (следующая через {check_interval_seconds} сек)")
                update_process_state('auto_bot_worker', {
                    'last_check': datetime.now().isoformat(),
                    'enabled': False,
                    'interval_seconds': check_interval_seconds
                })
            
            # Обновляем статус позиций каждые BOT_STATUS_UPDATE_INTERVAL секунд (независимо от Auto Bot)
            current_time = time.time()
            time_since_last_update = current_time - last_position_update
            # Подавляем частые сообщения о времени обновления
            should_log_time, log_time_message = should_log_message(
                'position_update_time', 
                f"Время с последнего обновления: {time_since_last_update:.1f}с (нужно {BOT_STATUS_UPDATE_INTERVAL}с)",
                interval_seconds=300  # Логируем раз в 5 минут
            )
            if should_log_time:
                logger.info(f"[POSITION_UPDATE] {log_time_message}")
            
            if time_since_last_update >= BOT_STATUS_UPDATE_INTERVAL:
                # Подавляем частые сообщения об обновлении кэша
                should_log, log_message = should_log_message(
                    'position_update', 
                    f"🔄 Обновление кэшированных данных ботов (каждые {BOT_STATUS_UPDATE_INTERVAL} сек)",
                    interval_seconds=300  # Логируем раз в 5 минут
                )
                if should_log:
                    logger.info(f"[BOTS_CACHE] {log_message}")
                
                update_bots_cache_data()
                last_position_update = current_time
            
            # Устанавливаем недостающие стоп-лоссы каждые STOP_LOSS_SETUP_INTERVAL секунд
            time_since_stop_setup = current_time - last_stop_loss_setup
            if time_since_stop_setup >= STOP_LOSS_SETUP_INTERVAL:
                logger.info(f"[STOP_LOSS_SETUP] 🔧 Установка недостающих стоп-лоссов (каждые {STOP_LOSS_SETUP_INTERVAL//60} мин)")
                check_missing_stop_losses()
                last_stop_loss_setup = current_time
            
            # Умная синхронизация позиций с биржей каждые POSITION_SYNC_INTERVAL секунд - ВРЕМЕННО ОТКЛЮЧЕНА
            # time_since_sync = current_time - last_position_sync
            # if time_since_sync >= POSITION_SYNC_INTERVAL:
            #     logger.info(f"[POSITION_SYNC] 🔄 Синхронизация позиций с биржей (каждые {POSITION_SYNC_INTERVAL//60} мин)")
            #     sync_positions_with_exchange()
            #     last_position_sync = current_time
            
            # Очищаем неактивные боты каждые INACTIVE_BOT_CLEANUP_INTERVAL секунд
            time_since_cleanup = current_time - last_inactive_cleanup
            if time_since_cleanup >= INACTIVE_BOT_CLEANUP_INTERVAL:
                logger.info(f"[INACTIVE_CLEANUP] 🧹 Очистка неактивных ботов (каждые {INACTIVE_BOT_CLEANUP_INTERVAL//60} мин)")
                cleanup_inactive_bots()
                
                # УДАЛЕНО: Очистка зрелых монет - зрелость необратима!
                
                # Активируем правила торговли для зрелых монет
                check_trading_rules_activation()
                
                last_inactive_cleanup = current_time
            
        except Exception as e:
            logger.error(f"[AUTO_BOT] ❌ Ошибка Auto Bot Worker: {e}")
            update_process_state('auto_bot_worker', {
                'last_error': str(e),
                'last_check': datetime.now().isoformat()
            })
    
    logger.info("[AUTO_BOT] 🛑 Auto Bot Worker остановлен")

def init_bot_service():
    """Инициализация сервиса ботов с полным восстановлением состояния"""
    try:
        # ✅ Красивый баннер запуска
        logger.info("=" * 80)
        logger.info("🚀 ЗАПУСК СИСТЕМЫ INFOBOT")
        logger.info("=" * 80)
        logger.info(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info(f"🔧 Версия: 1.0")
        logger.info("=" * 80)
        
        # 0. Загружаем постоянное хранилище зрелых монет
        load_mature_coins_storage()
        
        # 0.1. Загружаем данные об оптимальных EMA
        load_optimal_ema_data()
        
        # 1. Создаем дефолтную конфигурацию если её нет
        save_default_config()
        
        # 2. Загружаем системные настройки
        load_system_config()
        
        # 3. Загружаем состояние процессов
        load_process_state()
        
        # 4. Загружаем сохраненное состояние ботов
        load_bots_state()
        
        
        # 5. Запускаем загрузку RSI данных в отдельном потоке (не блокируем инициализацию!)
        logger.info("[INIT] 🔄 Запускаем загрузку RSI данных в фоновом режиме...")
        rsi_load_thread = threading.Thread(target=load_all_coins_rsi, daemon=True)
        rsi_load_thread.start()
        logger.info("[INIT] ✅ Загрузка RSI запущена в фоновом потоке")
        
        update_process_state('smart_rsi_manager', {
            'last_update': datetime.now().isoformat(),
            'update_count': process_state['smart_rsi_manager']['update_count'] + 1
        })
        
        # 5. Инициализируем биржу
        if init_exchange_sync():
            pass  # Успешно инициализирована
            update_process_state('exchange_connection', {
                'initialized': True,
                'last_sync': datetime.now().isoformat(),
                'connection_count': process_state['exchange_connection']['connection_count'] + 1
            })
            
            # 5.1. Инициализируем загруженных ботов (после инициализации биржи)
            with bots_data_lock:
                for symbol, bot_data in bots_data['bots'].items():
                    try:
                        # Создаем объект бота из сохраненных данных
                        bot_config = {
                            'volume_mode': bot_data.get('volume_mode', 'usdt'),
                            'volume_value': bot_data.get('volume_value', 10),
                            'status': bot_data.get('status', 'paused')
                        }
                        
                        trading_bot = RealTradingBot(
                            symbol=bot_data['symbol'],
                            exchange=exchange,
                            config=bot_config
                        )
                        
                        # Восстанавливаем состояние бота
                        trading_bot.status = bot_data.get('status', 'paused')
                        trading_bot.created_at = bot_data.get('created_at', datetime.now().isoformat())
                        trading_bot.entry_price = bot_data.get('entry_price', '')
                        trading_bot.last_price = bot_data.get('last_price', '')
                        trading_bot.last_rsi = bot_data.get('last_rsi', '')
                        trading_bot.last_signal_time = bot_data.get('last_signal_time', '')
                        trading_bot.last_trend = bot_data.get('last_trend', '')
                        trading_bot.position_side = bot_data.get('position_side', '')
                        trading_bot.position_start_time = bot_data.get('position_start_time', '')
                        trading_bot.unrealized_pnl = bot_data.get('unrealized_pnl', 0)
                        trading_bot.max_profit_achieved = bot_data.get('max_profit_achieved', 0)
                        trading_bot.trailing_stop_price = bot_data.get('trailing_stop_price', '')
                        trading_bot.break_even_activated = bot_data.get('break_even_activated', False)
                        trading_bot.rsi_data = bot_data.get('rsi_data', {})
                        
                        # Обновляем данные в bots_data
                        bots_data['bots'][symbol] = trading_bot.to_dict()
                        
                    except Exception as e:
                        logger.error(f"[INIT] ❌ Ошибка инициализации бота {symbol}: {e}")
                        # Удаляем некорректного бота
                        if symbol in bots_data['bots']:
                            del bots_data['bots'][symbol]
            
            # 6. Запускаем Smart RSI Manager
            global smart_rsi_manager
            smart_rsi_manager = SmartRSIManager(
                rsi_update_callback=load_all_coins_rsi,
                trading_signal_callback=process_trading_signals_on_candle_close,
                exchange_obj=exchange
            )
            smart_rsi_manager.start()
            
            update_process_state('smart_rsi_manager', {
                'active': True,
                'last_update': datetime.now().isoformat()
            })
        else:
            logger.error("[INIT] ❌ Не удалось инициализировать биржу")
            update_process_state('exchange_connection', {
                'initialized': False,
                'last_error': 'Initialization failed'
            })
        
        # 7. Синхронизируем с биржей (после загрузки состояния)
        sync_bots_with_exchange()
        
        # 7.1. КРИТИЧЕСКИ ВАЖНО: Проверяем конфликты позиций при запуске
        check_startup_position_conflicts()
        
        # 8. Запускаем воркеры
        autosave_thread = threading.Thread(target=auto_save_worker, daemon=True)
        autosave_thread.start()
        update_process_state('auto_save_worker', {
            'active': True,
            'last_save': datetime.now().isoformat()
        })
        
        try:
            # Auto Bot Worker отключен
            logger.info("[INIT] 🚫 Auto Bot Worker отключен!")
            
            update_process_state('auto_bot_worker', {
                'active': False,
                'last_check': datetime.now().isoformat(),
                'check_count': 0
            })
        except Exception as e:
            logger.error(f"[INIT] ❌ Ошибка запуска Auto Bot Worker: {e}")
            import traceback
            logger.error(f"[INIT] Traceback: {traceback.format_exc()}")
        
        # Запускаем асинхронный процессор для улучшения производительности
        if start_async_processor():
            pass  # Успешно запущен
        else:
            logger.warning("[INIT] ⚠️ Асинхронный процессор не запущен, работаем в синхронном режиме")
        
        # КРИТИЧЕСКИ ВАЖНО: Устанавливаем флаг инициализации ПОСЛЕ всех загрузок
        global system_initialized
        system_initialized = True
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем Auto Bot при старте - он ДОЛЖЕН быть выключен!
        with bots_data_lock:
            auto_bot_enabled = bots_data['auto_bot_config']['enabled']
        auto_bot_config = bots_data['auto_bot_config']
        bots_count = len(bots_data['bots'])
        
        # ПРИНУДИТЕЛЬНО выключаем автобот при старте системы для безопасности!
        if auto_bot_enabled:
            logger.warning("[INIT] ⚠️ Автобот включен при старте! Принудительно выключаем для безопасности...")
            bots_data['auto_bot_config']['enabled'] = False
            auto_bot_enabled = False
            save_auto_bot_config()  # Сохраняем изменение
        
        # ✅ ИТОГОВАЯ ИНФОРМАЦИЯ О ЗАПУСКЕ
        logger.info("=" * 80)
        logger.info("✅ СИСТЕМА УСПЕШНО ЗАПУЩЕНА!")
        logger.info("=" * 80)
        logger.info(f"📊 Статус компонентов:")
        logger.info(f"  🔗 Exchange: {'✅ Инициализирован' if exchange else '❌ Не инициализирован'}")
        logger.info(f"  📊 Smart RSI Manager: {'✅ Запущен' if smart_rsi_manager else '❌ Не запущен'}")
        logger.info(f"  🤖 Auto Bot: {'❌ ВКЛЮЧЕН!' if auto_bot_enabled else '✅ Выключен (безопасно)'}")
        logger.info(f"  💾 Auto Save: ✅ Запущен")
        logger.info(f"  🔄 Async Processor: ✅ Запущен")
        logger.info("")
        logger.info(f"📈 Данные:")
        logger.info(f"  🤖 Загружено ботов: {bots_count}")
        logger.info(f"  ✅ Зрелых монет: {len(mature_coins_storage)}")
        logger.info(f"  📊 Optimal EMA: {len(optimal_ema_data)}")
        logger.info("")
        logger.info(f"⚙️ Конфигурация Auto Bot:")
        logger.info(f"  📊 RSI: LONG≤{auto_bot_config.get('rsi_long_threshold')}, SHORT≥{auto_bot_config.get('rsi_short_threshold')}")
        logger.info(f"  ⏰ RSI Time Filter: {'✅ ON' if auto_bot_config.get('rsi_time_filter_enabled') else '❌ OFF'} ({auto_bot_config.get('rsi_time_filter_candles')} свечей)")
        logger.info(f"  ✅ Maturity Check: {'✅ ON' if auto_bot_config.get('enable_maturity_check') else '❌ OFF'}")
        logger.info(f"  🛡️ Stop-Loss: {auto_bot_config.get('max_loss_percent')}%, Trailing: {auto_bot_config.get('trailing_stop_activation')}%")
        logger.info(f"  👥 Max Concurrent: {auto_bot_config.get('max_concurrent')}")
        logger.info("=" * 80)
        logger.info("🎯 СИСТЕМА ГОТОВА К РАБОТЕ!")
        logger.info("💡 Логи будут показывать только важные события")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"[INIT] ❌ Ошибка инициализации сервиса: {e}")
        return False

def start_async_processor():
    """Запускает асинхронный процессор"""
    global async_processor, async_processor_task
    
    if not ASYNC_AVAILABLE:
        logger.warning("[ASYNC] ⚠️ Асинхронный процессор недоступен")
        return False
    
    try:
        logger.info("[ASYNC] 🚀 Запуск асинхронного процессора...")
        
        # Конфигурация для асинхронного процессора
        async_config = {
            'max_rsi_requests': 15,  # Увеличиваем количество одновременных запросов
            'max_concurrent_bots': 8,  # Увеличиваем количество ботов
            'max_concurrent_signals': 20,  # Увеличиваем количество сигналов
            'max_concurrent_saves': 5,  # Увеличиваем количество сохранений
            'rsi_update_interval': SystemConfig.RSI_UPDATE_INTERVAL,
            'position_sync_interval': 60,  # Синхронизация позиций каждую минуту
            'bot_processing_interval': 10,  # Обработка ботов каждые 10 секунд
            'signal_processing_interval': 5,  # Обработка сигналов каждые 5 секунд
            'data_saving_interval': 30  # Сохранение данных каждые 30 секунд
        }
        
        # Создаем асинхронный процессор
        # Используем глобальную переменную exchange
        global exchange
        logger.info(f"[ASYNC] 🔍 Проверяем глобальную переменную exchange: {type(exchange)}")
        logger.info(f"[ASYNC] 🔍 exchange is None: {exchange is None}")
        logger.info(f"[ASYNC] 🔍 exchange == None: {exchange == None}")
        
        if exchange is None:
            logger.error("[ASYNC] ❌ Биржа не инициализирована, пропускаем асинхронный процессор")
            return False
        
        logger.info(f"[ASYNC] ✅ Биржа найдена, создаем AsyncMainProcessor с типом: {type(exchange)}")
        async_processor = AsyncMainProcessor(exchange, async_config)
        logger.info(f"[ASYNC] ✅ AsyncMainProcessor создан успешно")
        
        # Запускаем в отдельном потоке
        def run_async_processor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_processor.start())
            except Exception as e:
                logger.error(f"[ASYNC] ❌ Ошибка в асинхронном процессоре: {e}")
            finally:
                loop.close()
        
        async_processor_task = threading.Thread(target=run_async_processor, daemon=True)
        async_processor_task.start()
        
        # Немедленная синхронизация позиций при запуске - ВРЕМЕННО ОТКЛЮЧЕНА
        # logger.info("[ASYNC] 🔄 Немедленная синхронизация позиций при запуске...")
        # try:
        #     result = sync_positions_with_exchange()
        #     logger.info(f"[ASYNC] ✅ Синхронизация завершена: {result}")
        # except Exception as e:
        #     logger.error(f"[ASYNC] ❌ Ошибка синхронизации: {e}")
        
        logger.info("[ASYNC] ✅ Асинхронный процессор запущен")
        return True
        
    except Exception as e:
        logger.error(f"[ASYNC] ❌ Ошибка запуска асинхронного процессора: {e}")
        return False

def stop_async_processor():
    """Останавливает асинхронный процессор"""
    global async_processor, async_processor_task
    
    if async_processor:
        try:
            logger.info("[ASYNC] 🛑 Остановка асинхронного процессора...")
            async_processor.stop()
            async_processor = None
            async_processor_task = None
            logger.info("[ASYNC] ✅ Асинхронный процессор остановлен")
        except Exception as e:
            logger.error(f"[ASYNC] ❌ Ошибка остановки асинхронного процессора: {e}")

def create_bot(symbol, config=None, exchange_obj=None):
    """Создает нового бота для символа"""
    if config is None:
        # Получаем default_position_size из конфигурации Auto Bot
        with bots_data_lock:
            auto_bot_config = bots_data['auto_bot_config']
            default_volume = auto_bot_config.get('default_position_size', 20.0)
        
        config = {
            'volume_mode': 'usdt',
            'volume_value': default_volume,
            'status': BOT_STATUS['RUNNING'],
            'entry_price': None,
            'position_side': None,
            'unrealized_pnl': 0.0,
            'created_at': datetime.now().isoformat(),
            'last_signal_time': None
        }
    
    # Применяем настройки из конфигурации Auto Bot как базовые
    with bots_data_lock:
        auto_bot_config = bots_data['auto_bot_config']
        base_config = {
            'volume_mode': 'usdt',
            'volume_value': auto_bot_config.get('default_position_size', 20.0),
            'status': BOT_STATUS['RUNNING'],
            'entry_price': None,
            'position_side': None,
            'unrealized_pnl': 0.0,
            'created_at': datetime.now().isoformat(),
            'last_signal_time': None,
            # Настройки RSI и защитных механизмов
            'rsi_long_threshold': auto_bot_config.get('rsi_long_threshold', 29),
            'rsi_short_threshold': auto_bot_config.get('rsi_short_threshold', 71),
            'rsi_exit_long': auto_bot_config.get('rsi_exit_long', 65),
            'rsi_exit_short': auto_bot_config.get('rsi_exit_short', 35),
            'max_loss_percent': auto_bot_config.get('max_loss_percent', 15.0),
            'trailing_stop_activation': auto_bot_config.get('trailing_stop_activation', 300.0),
            'trailing_stop_distance': auto_bot_config.get('trailing_stop_distance', 150.0),
            'max_position_hours': auto_bot_config.get('max_position_hours', 48),
            'break_even_protection': auto_bot_config.get('break_even_protection', True),
            'break_even_trigger': auto_bot_config.get('break_even_trigger', 100.0),
            'avoid_down_trend': auto_bot_config.get('avoid_down_trend', True),
            'avoid_up_trend': auto_bot_config.get('avoid_up_trend', True),
            'enable_maturity_check': auto_bot_config.get('enable_maturity_check', True)
        }
        
        # Объединяем базовую конфигурацию с переданной (переданная имеет приоритет)
        full_config = {**base_config, **config}
        config = full_config
    
    logger.info(f"[BOT_INIT] Инициализация бота для {symbol}")
    logger.info(f"[BOT_INIT] 🔍 Детальная отладка конфигурации бота:")
    logger.info(f"[BOT_INIT] 🔍 {symbol}: config = {config}")
    logger.info(f"[BOT_INIT] 🔍 {symbol}: volume_mode = {config.get('volume_mode')}")
    logger.info(f"[BOT_INIT] 🔍 {symbol}: volume_value = {config.get('volume_value')}")
    logger.info(f"[BOT_INIT] Объем торговли: {config.get('volume_mode')} = {config.get('volume_value')}")
    logger.info(f"[BOT_INIT] RSI пороги: Long<={config.get('rsi_long_threshold')}, Short>={config.get('rsi_short_threshold')}")
    
    # Создаем экземпляр торгового бота
    logger.info(f"[BOT_INIT] Создание экземпляра TradingBot для {symbol}...")
    # Используем переданную биржу или глобальную переменную
    exchange_to_use = exchange_obj if exchange_obj else exchange
    trading_bot = RealTradingBot(symbol, exchange_to_use, config)
    
    with bots_data_lock:
        # Обновляем существующую запись или создаем новую
        if symbol in bots_data['bots']:
            # Если есть временная запись с статусом 'creating', обновляем её
            if bots_data['bots'][symbol].get('status') == 'creating':
                logger.info(f"[BOT_ACTIVE] 🔄 Обновляем временную запись бота {symbol}")
            else:
                logger.info(f"[BOT_ACTIVE] ⚠️ Бот {symbol} уже существует, перезаписываем")
        
        bots_data['bots'][symbol] = trading_bot.to_dict()
        total_bots = len(bots_data['bots'])
        logger.info(f"[BOT_ACTIVE] ✅ Бот {symbol} добавлен в список активных")
        logger.info(f"[BOT_ACTIVE] Всего активных ботов: {total_bots}")
        logger.info(f"[BOT_ACTIVE] Статус {symbol}: {trading_bot.status}")
    
    # Логируем создание бота в историю
    log_bot_start(symbol, config)
    
    # Автоматически сохраняем состояние после создания бота
    save_bots_state()
    
    return trading_bot.to_dict()

# Старый rsi_update_worker удален - заменен на SmartRSIManager

def process_trading_signals_on_candle_close(candle_timestamp: int, exchange_obj=None):
    """
    Обрабатывает торговые сигналы при закрытии свечи 6H
    
    Args:
        candle_timestamp: Timestamp закрытой свечи
        exchange_obj: Объект биржи (если None, используется глобальная переменная)
    """
    try:
        logger.info(f"[TRADING] 🎯 Обработка торговых сигналов для свечи {candle_timestamp}")
        
        # КРИТИЧЕСКИ ВАЖНО: Обрабатываем торговые сигналы для всех ботов в основном процессе
        logger.info("[TRADING] 🔄 Вызываем process_trading_signals_for_all_bots...")
        process_trading_signals_for_all_bots(exchange_obj=exchange_obj)
        logger.info("[TRADING] ✅ process_trading_signals_for_all_bots завершен")
        
        # Получаем список активных ботов
        with bots_data_lock:
            active_bots = {symbol: bot for symbol, bot in bots_data['bots'].items() 
                          if bot['status'] not in [BOT_STATUS['IDLE'], BOT_STATUS['PAUSED']]}
        
        if not active_bots:
            logger.info("[TRADING] 📭 Нет активных ботов для обработки сигналов")
            # Но все равно проверяем Auto Bot сигналы!
            logger.info("[TRADING] 🤖 Проверяем Auto Bot сигналы (нет активных ботов)...")
            # process_auto_bot_signals(exchange_obj=exchange_obj)  # ОТКЛЮЧЕНО!
            return
        
        logger.info(f"[TRADING] 🤖 Обработка сигналов для {len(active_bots)} активных ботов")
        
        # Обрабатываем каждого бота
        for symbol, bot_data in active_bots.items():
            try:
                # Получаем актуальные RSI данные для монеты
                with rsi_data_lock:
                    coin_rsi_data = coins_rsi_data['coins'].get(symbol)
                
                if not coin_rsi_data:
                    logger.warning(f"[TRADING] ⚠️ Нет RSI данных для {symbol}")
                    continue
                
                rsi = coin_rsi_data.get('rsi6h')
                trend = coin_rsi_data.get('trend6h', 'NEUTRAL')
                price = coin_rsi_data.get('price', 0)
                
                if not rsi or not price:
                    logger.warning(f"[TRADING] ⚠️ Неполные данные для {symbol}: RSI={rsi}, Price={price}")
                    continue
                
                logger.info(f"[TRADING] 📊 {symbol}: RSI={rsi}, Trend={trend}, Price={price}")
                
                # Создаем объект торгового бота для обработки сигнала
                # Используем переданную биржу или глобальную переменную
                exchange_to_use = exchange_obj if exchange_obj else exchange
                trading_bot = RealTradingBot(symbol, exchange_to_use, bot_data)
                
                # Обрабатываем торговый сигнал при закрытии свечи
                result = trading_bot.process_trading_signals(trend, rsi, price, on_candle_close=True)
                
                if result:
                    logger.info(f"[TRADING] ✅ {symbol}: Обработан сигнал при закрытии свечи")
                    
                    # Обновляем данные бота
                    with bots_data_lock:
                        bots_data['bots'][symbol] = trading_bot.to_dict()
                else:
                    logger.debug(f"[TRADING] 💤 {symbol}: Нет активных сигналов")
                    
            except Exception as bot_error:
                logger.error(f"[TRADING] ❌ Ошибка обработки бота {symbol}: {bot_error}")
        
        # КРИТИЧЕСКИ ВАЖНО: Обрабатываем Auto Bot сигналы при закрытии свечи только если Auto Bot включен
        with bots_data_lock:
            auto_bot_enabled = bots_data['auto_bot_config']['enabled']
        if auto_bot_enabled:
            logger.info("[TRADING]  Проверяем Auto Bot сигналы после обработки существующих ботов...")
            # process_auto_bot_signals(exchange_obj=exchange_obj)  # ОТКЛЮЧЕНО!
        
        # Сохраняем состояние после обработки сигналов
        save_bots_state()
        logger.info(f"[TRADING] 💾 Состояние ботов сохранено после обработки сигналов")
        
    except Exception as e:
        logger.error(f"[TRADING] ❌ Критическая ошибка обработки торговых сигналов: {e}")

# Эта функция удалена - используется основная init_bot_service() выше

def delayed_exchange_init():
    """Отложенная инициализация биржи"""
    global exchange
    
    try:
        logger.info("[INIT] Начало отложенной инициализации биржи...")
        
        # Даем время Flask серверу запуститься
        time.sleep(2)
        
        logger.info("[INIT] Подключение к бирже...")
        logger.info(f"[INIT] Используем ключи: api_key={EXCHANGES['BYBIT']['api_key'][:10]}...")
        
        exchange = ExchangeFactory.create_exchange(
            'BYBIT', 
            EXCHANGES['BYBIT']['api_key'], 
            EXCHANGES['BYBIT']['api_secret']
        )
        
        if not exchange:
            raise Exception("ExchangeFactory вернул None")
        
        logger.info("[INIT] ✅ Биржа подключена успешно!")
        
        # Тестируем подключение
        try:
            account_info = exchange.get_unified_account_info()
            logger.info(f"[INIT] ✅ Тест подключения успешен, баланс: {account_info.get('totalWalletBalance', 'N/A')}")
        except Exception as test_e:
            logger.warning(f"[INIT] ⚠️ Тест подключения не удался: {str(test_e)}")
        
        # RSI Worker теперь запускается через SmartRSIManager в init_bot_service()
        logger.info("[INIT] ✅ Биржа инициализирована")
        
    except Exception as e:
        logger.error(f"[INIT] ❌ Критическая ошибка инициализации биржи: {str(e)}")
        import traceback
        logger.error(f"[INIT] Traceback: {traceback.format_exc()}")

def init_exchange_sync():
    """Синхронная инициализация биржи"""
    global exchange
    
    try:
        logger.info("[SYNC] 🔗 Подключение к бирже...")
        
        exchange = ExchangeFactory.create_exchange(
            'BYBIT', 
            EXCHANGES['BYBIT']['api_key'], 
            EXCHANGES['BYBIT']['api_secret']
        )
        
        logger.info(f"[SYNC] 🔍 ExchangeFactory создал биржу: {type(exchange)}")
        logger.info(f"[SYNC] 🔍 exchange is None: {exchange is None}")
        
        if not exchange:
            logger.error("[SYNC] ❌ ExchangeFactory вернул None")
            return False
        
        # Тестируем подключение
        try:
            account_info = exchange.get_unified_account_info()
            logger.info(f"[SYNC] ✅ Подключение успешно, баланс: {account_info.get('totalWalletBalance', 'N/A')}")
        except Exception as test_e:
            logger.warning(f"[SYNC] ⚠️ Тест подключения не удался: {str(test_e)}")
        
        logger.info(f"[SYNC] 🔍 В конце init_exchange_sync exchange: {type(exchange)}")
        logger.info(f"[SYNC] 🔍 В конце init_exchange_sync exchange is None: {exchange is None}")
        
        return True
        
    except Exception as e:
        logger.error(f"[SYNC] ❌ Критическая ошибка инициализации биржи: {str(e)}")
        import traceback
        logger.error(f"[SYNC] Traceback: {traceback.format_exc()}")
        return False
        
def ensure_exchange_initialized():
    """Проверяет что биржа инициализирована"""
    global exchange
    if exchange is None:
        logger.warning("[WARNING] Биржа не инициализирована, попытка переподключения...")
        try:
            logger.info(f"[DEBUG] Создание exchange с ключами: api_key={EXCHANGES['BYBIT']['api_key'][:10]}...")
            exchange = ExchangeFactory.create_exchange(
                'BYBIT', 
                EXCHANGES['BYBIT']['api_key'], 
                EXCHANGES['BYBIT']['api_secret']
            )
            if exchange:
                logger.info("[OK] Биржа переподключена успешно")
                return True
            else:
                logger.error("[ERROR] ExchangeFactory вернул None")
                return False
        except Exception as e:
            logger.error(f"[ERROR] Не удалось переподключиться к бирже: {str(e)}")
            return False
    logger.debug("[DEBUG] Exchange уже инициализирован")
    return True

# API endpoints
@bots_app.route('/health', methods=['GET'])
def health_check():
    """Проверка состояния сервиса"""
    try:
        return jsonify({
            'status': 'ok',
            'service': 'bots',
            'timestamp': datetime.now().isoformat(),
            'exchange_connected': exchange is not None,
            'coins_loaded': len(coins_rsi_data.get('coins', {})),
            'bots_active': len(bots_data.get('bots', {}))
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'service': 'bots',
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/async-status', methods=['GET'])
def get_async_status():
    """Получает статус асинхронного процессора"""
    try:
        global async_processor, async_processor_task
        
        status = {
            'available': ASYNC_AVAILABLE,
            'running': async_processor is not None and async_processor.is_running,
            'task_active': async_processor_task is not None and async_processor_task.is_alive(),
            'last_update': async_processor.last_update if async_processor else 0,
            'active_tasks': len(async_processor.active_tasks) if async_processor else 0
        }
        
        return jsonify({
            'success': True,
            'async_status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/async-control', methods=['POST'])
def control_async_processor():
    """Управляет асинхронным процессором"""
    try:
        data = request.get_json()
        action = data.get('action')
        
        if action == 'start':
            if async_processor is None:
                success = start_async_processor()
                return jsonify({
                    'success': success,
                    'message': 'Асинхронный процессор запущен' if success else 'Ошибка запуска'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Асинхронный процессор уже запущен'
                })
        
        elif action == 'stop':
            if async_processor is not None:
                stop_async_processor()
                return jsonify({
                    'success': True,
                    'message': 'Асинхронный процессор остановлен'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Асинхронный процессор не запущен'
                })
        
        elif action == 'restart':
            stop_async_processor()
            time.sleep(1)  # Небольшая пауза
            success = start_async_processor()
            return jsonify({
                'success': success,
                'message': 'Асинхронный процессор перезапущен' if success else 'Ошибка перезапуска'
            })
        
        else:
            return jsonify({
                'success': False,
                'error': 'Неизвестное действие'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/account-info', methods=['GET'])
def get_account_info():
    """Получает информацию о едином торговом счете (напрямую с биржи)"""
    try:
        # Получаем данные напрямую с биржи (без кэширования)
        if not ensure_exchange_initialized():
            return jsonify({
                'success': False,
                'error': 'Exchange not initialized'
            }), 500
        
        # Получаем актуальные данные с биржи
        account_info = exchange.get_unified_account_info()
        if not account_info.get("success"):
            account_info = {
                'success': False,
                'error': 'Failed to get account info from exchange'
            }
        
        # Добавляем информацию о ботах из актуальных данных
        with bots_data_lock:
            bots_list = list(bots_data['bots'].values())
            account_info["bots_count"] = len(bots_list)
            account_info["active_bots"] = sum(1 for bot in bots_list 
                                            if bot.get('status') not in ['idle', 'paused'])
        
        response = jsonify(account_info)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка получения информации о счете: {str(e)}")
        response = jsonify({
            "success": False,
            "error": str(e)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@bots_app.route('/api/bots/manual-positions/refresh', methods=['POST'])
def refresh_manual_positions():
    """Обновить список монет с ручными позициями на бирже"""
    try:
        manual_positions = []
        if exchange:
            exchange_positions = exchange.get_positions()
            if isinstance(exchange_positions, tuple):
                positions_list = exchange_positions[0] if exchange_positions else []
            else:
                positions_list = exchange_positions if exchange_positions else []
            
            # Извлекаем символы с активными позициями
            for pos in positions_list:
                if abs(float(pos.get('size', 0))) > 0:
                    symbol = pos.get('symbol', '')
                    # Убираем USDT из символа для сопоставления с coins_rsi_data
                    clean_symbol = symbol.replace('USDT', '') if symbol else ''
                    if clean_symbol and clean_symbol not in manual_positions:
                        manual_positions.append(clean_symbol)
            
            logger.info(f"[MANUAL_POSITIONS] ✋ Обновлено {len(manual_positions)} монет с позициями")
            
        return jsonify({
            'success': True,
            'count': len(manual_positions),
            'positions': manual_positions
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка обновления ручных позиций: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/coins-with-rsi', methods=['GET'])
def get_coins_with_rsi():
    """Получить все монеты с RSI 6H данными"""
    try:
        with rsi_data_lock:
            # Проверяем возраст кэша
            cache_age = None
            if os.path.exists(RSI_CACHE_FILE):
                try:
                    cache_stat = os.path.getmtime(RSI_CACHE_FILE)
                    cache_age = (time.time() - cache_stat) / 60  # в минутах
                except:
                    cache_age = None
            
            # Очищаем данные от несериализуемых объектов
            cleaned_coins = {}
            for symbol, coin_data in coins_rsi_data['coins'].items():
                # ✅ ИСПРАВЛЕНИЕ: НЕ фильтруем монеты по зрелости для UI!
                # Фильтр зрелости применяется в get_coin_rsi_data() через изменение сигнала на WAIT
                # Здесь показываем ВСЕ монеты, независимо от зрелости
                    
                cleaned_coin = coin_data.copy()
                
                # Очищаем enhanced_rsi от numpy типов и других несериализуемых объектов
                if 'enhanced_rsi' in cleaned_coin and cleaned_coin['enhanced_rsi']:
                    enhanced_rsi = cleaned_coin['enhanced_rsi'].copy()
                    
                    # Конвертируем numpy типы в Python типы
                    if 'confirmations' in enhanced_rsi:
                        confirmations = enhanced_rsi['confirmations'].copy()
                        for key, value in confirmations.items():
                            if hasattr(value, 'item'):  # numpy scalar
                                confirmations[key] = value.item()
                            elif value is None:
                                confirmations[key] = None
                        enhanced_rsi['confirmations'] = confirmations
                    
                    # Конвертируем adaptive_levels если это tuple
                    if 'adaptive_levels' in enhanced_rsi and enhanced_rsi['adaptive_levels']:
                        if isinstance(enhanced_rsi['adaptive_levels'], tuple):
                            enhanced_rsi['adaptive_levels'] = list(enhanced_rsi['adaptive_levels'])
                    
                    cleaned_coin['enhanced_rsi'] = enhanced_rsi
                
                # Добавляем эффективный сигнал для единообразия с фронтендом
                # Вычисляем эффективный сигнал после очистки от numpy типов
                effective_signal = get_effective_signal(cleaned_coin)
                cleaned_coin['effective_signal'] = effective_signal
                
                cleaned_coins[symbol] = cleaned_coin
            
            # Получаем список монет с ручными позициями на бирже
            manual_positions = []
            try:
                if exchange:
                    exchange_positions = exchange.get_positions()
                    if isinstance(exchange_positions, tuple):
                        positions_list = exchange_positions[0] if exchange_positions else []
                    else:
                        positions_list = exchange_positions if exchange_positions else []
                    
                    # Извлекаем символы с активными позициями
                    for pos in positions_list:
                        if abs(float(pos.get('size', 0))) > 0:
                            symbol = pos.get('symbol', '')
                            # Убираем USDT из символа для сопоставления с coins_rsi_data
                            clean_symbol = symbol.replace('USDT', '') if symbol else ''
                            if clean_symbol and clean_symbol not in manual_positions:
                                manual_positions.append(clean_symbol)
                    
                    # ✅ Логируем только если есть изменения
                    if len(manual_positions) > 0:
                        logger.debug(f"[MANUAL_POSITIONS] ✋ {len(manual_positions)} монет с позициями")
            except Exception as e:
                logger.error(f"[ERROR] Ошибка получения ручных позиций: {str(e)}")
            
            result = {
                'success': True,
                'coins': cleaned_coins,
                'total': len(cleaned_coins),
                'last_update': coins_rsi_data['last_update'],
                'update_in_progress': coins_rsi_data['update_in_progress'],
                'manual_positions': manual_positions,  # Добавляем список ручных позиций
                'cache_info': {
                    'cache_exists': os.path.exists(RSI_CACHE_FILE),
                    'cache_age_minutes': round(cache_age, 1) if cache_age else None,
                    'data_source': 'cache' if cache_age and cache_age < 360 else 'live'  # 6 часов
                },
                'stats': {
                    'total_coins': coins_rsi_data['total_coins'],
                    'successful_coins': coins_rsi_data['successful_coins'],
                    'failed_coins': coins_rsi_data['failed_coins']
                }
            }
        
        # Убираем спам-лог, только в debug режиме
        if SystemConfig.DEBUG_MODE:
            logger.debug(f"[API] Возврат RSI данных для {len(result['coins'])} монет")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка получения монет с RSI: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def clean_data_for_json(data):
    """Очищает данные от numpy типов для JSON сериализации"""
    if data is None:
        return None
    elif isinstance(data, dict):
        return {k: clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif hasattr(data, 'tolist'):  # numpy array
        return data.tolist()
    elif hasattr(data, 'item'):  # numpy scalar
        return data.item()
    elif hasattr(data, 'dtype'):  # numpy тип
        # Обрабатываем все numpy типы
        if data.dtype.kind == 'b':  # boolean
            return bool(data)
        elif data.dtype.kind in ['i', 'u']:  # integer
            return int(data)
        elif data.dtype.kind == 'f':  # float
            return float(data)
        else:
            return str(data)
    else:
        return data

@bots_app.route('/api/bots/list', methods=['GET'])
def get_bots_list():
    """Получить список всех ботов (использует bots_data напрямую)"""
    try:
        # Используем bots_data напрямую для актуальности
        with bots_data_lock:
            bots_list = list(bots_data['bots'].values())
            auto_bot_enabled = bots_data.get('auto_bot_config', {}).get('enabled', False)
            last_update = bots_data.get('last_update', 'Неизвестно')
        
        # Подсчитываем статистику
        active_bots = sum(1 for bot in bots_list if bot.get('status') not in ['idle', 'paused'])
        
        response_data = {
            'success': True,
            'bots': bots_list,
            'count': len(bots_list),
            'auto_bot_enabled': auto_bot_enabled,
            'last_update': last_update,
            'stats': {
                'active_bots': active_bots,
                'total_bots': len(bots_list)
            }
        }
        
        # ✅ Не логируем частые запросы списка ботов
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"[API] ❌ Ошибка получения списка ботов: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'bots': [],
            'count': 0
        }), 500

@bots_app.route('/api/bots/create', methods=['POST'])
def create_bot_endpoint():
    """Создать нового бота"""
    try:
        # Проверяем что биржа инициализирована
        if not ensure_exchange_initialized():
            return jsonify({
                'success': False, 
                'error': 'Биржа не инициализирована. Попробуйте позже.'
            }), 503
        
        data = request.get_json()
        if not data or not data.get('symbol'):
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        symbol = data['symbol']
        config = data.get('config', {})
        
        logger.info(f"[BOT_CREATE] Запрос на создание бота для {symbol}")
        logger.info(f"[BOT_CREATE] Конфигурация: {config}")
        
        # Проверяем зрелость монеты (если включена проверка для этой монеты)
        enable_maturity_check_coin = config.get('enable_maturity_check', True)
        if enable_maturity_check_coin:
            # Получаем данные свечей для проверки зрелости
            chart_response = exchange.get_chart_data(symbol, '6h', '30d')
            if chart_response and chart_response.get('success'):
                candles = chart_response['data']['candles']
                if candles and len(candles) >= 15:
                    maturity_check = check_coin_maturity_with_storage(symbol, candles)
                    if not maturity_check['is_mature']:
                        logger.warning(f"[BOT_CREATE] {symbol}: Монета не прошла проверку зрелости - {maturity_check['reason']}")
                        return jsonify({
                            'success': False, 
                            'error': f'Монета {symbol} не прошла проверку зрелости: {maturity_check["reason"]}',
                            'maturity_details': maturity_check['details']
                        }), 400
                else:
                    logger.warning(f"[BOT_CREATE] {symbol}: Недостаточно данных для проверки зрелости")
                    return jsonify({
                        'success': False, 
                        'error': f'Недостаточно данных для проверки зрелости монеты {symbol}'
                    }), 400
            else:
                logger.warning(f"[BOT_CREATE] {symbol}: Не удалось получить данные для проверки зрелости")
                return jsonify({
                    'success': False, 
                    'error': f'Не удалось получить данные для проверки зрелости монеты {symbol}'
                }), 400
        
        # Создаем бота
        bot_config = create_bot(symbol, config, exchange_obj=exchange)
        
        logger.info(f"[BOT_CREATE] ✅ Бот для {symbol} создан и запущен")
        logger.info(f"[BOT_CREATE] Статус: {bot_config.get('status', 'UNKNOWN')}")
        logger.info(f"[BOT_CREATE] ID бота: {bot_config.get('id', 'UNKNOWN')}")
        
        return jsonify({
            'success': True,
            'message': f'Бот для {symbol} создан успешно',
            'bot': bot_config
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка создания бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/start', methods=['POST'])
def start_bot_endpoint():
    """Запустить бота"""
    try:
        data = request.get_json()
        if not data or not data.get('symbol'):
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        symbol = data['symbol']
        
        with bots_data_lock:
            if symbol not in bots_data['bots']:
                return jsonify({'success': False, 'error': 'Bot not found'}), 404
            
            bot_data = bots_data['bots'][symbol]
            if bot_data['status'] in [BOT_STATUS['PAUSED'], BOT_STATUS['IDLE']]:
                bot_data['status'] = BOT_STATUS['RUNNING']
                logger.info(f"[BOT] {symbol}: Бот запущен (снята пауза)")
            else:
                logger.info(f"[BOT] {symbol}: Бот уже активен")
        
        return jsonify({
            'success': True,
            'message': f'Бот для {symbol} запущен'
        })
            
    except Exception as e:
        logger.error(f"[ERROR] Ошибка запуска бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/stop', methods=['POST'])
def stop_bot_endpoint():
    """Остановить бота"""
    try:
        logger.info(f"[API] 📥 Получен запрос остановки бота: {request.get_data()}")
        
        # Пробуем разные способы получения данных
        try:
            data = request.get_json()
        except Exception as json_error:
            logger.error(f"[API] ❌ Ошибка парсинга JSON: {json_error}")
            # Пробуем получить данные как form data
            data = request.form.to_dict()
            if not data:
                # Пробуем получить данные из args
                data = request.args.to_dict()
        
        logger.info(f"[API] 📊 Распарсенные данные: {data}")
        
        if not data or not data.get('symbol'):
            logger.error(f"[API] ❌ Отсутствует symbol в данных: {data}")
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        symbol = data['symbol']
        reason = data.get('reason', 'Остановлен пользователем')
        
        # Проверяем, есть ли открытая позиция у бота
        position_to_close = None
        with bots_data_lock:
            if symbol not in bots_data['bots']:
                return jsonify({'success': False, 'error': 'Bot not found'}), 404
            
            bot_data = bots_data['bots'][symbol]
            old_status = bot_data['status']
            
            # Проверяем, есть ли открытая позиция
            if bot_data.get('position_side') in ['LONG', 'SHORT']:
                position_to_close = bot_data['position_side']
                logger.info(f"[BOT] {symbol}: Найдена открытая позиция {position_to_close}, будет закрыта при остановке")
            
            bot_data['status'] = BOT_STATUS['PAUSED']
            # Не сбрасываем entry_price для возможности возобновления
            bot_data['position_side'] = None
            bot_data['unrealized_pnl'] = 0.0
            logger.info(f"[BOT] {symbol}: Бот остановлен и сброшен в IDLE")
            
            # Обновляем глобальную статистику
            bots_data['global_stats']['active_bots'] = len([bot for bot in bots_data['bots'].values() if bot.get('status') in ['running', 'idle']])
            bots_data['global_stats']['bots_in_position'] = len([bot for bot in bots_data['bots'].values() if bot.get('position_side')])
        
        # Закрываем позицию на бирже, если она была открыта
        if position_to_close and exchange:
            try:
                logger.info(f"[BOT] {symbol}: Закрываем позицию {position_to_close} на бирже...")
                
                # Получаем текущие позиции для определения размера
                positions_response = exchange.get_positions()
                if positions_response and positions_response.get('success'):
                    positions = positions_response.get('data', [])
                    
                    # Ищем нашу позицию
                    our_position = None
                    for pos in positions:
                        if (pos['symbol'] == f"{symbol}USDT" and 
                            pos['side'] == position_to_close and 
                            float(pos.get('size', 0)) > 0):
                            our_position = pos
                            break
                    
                    if our_position:
                        # Закрываем позицию через exchange.close_position
                        close_result = exchange.close_position(
                            symbol=symbol,
                            size=float(our_position['size']),
                            side=position_to_close,
                            order_type="Market"
                        )
                        
                        if close_result and close_result.get('success'):
                            logger.info(f"[BOT] {symbol}: ✅ Позиция {position_to_close} успешно закрыта на бирже")
                        else:
                            logger.error(f"[BOT] {symbol}: ❌ Ошибка закрытия позиции на бирже: {close_result.get('message', 'Unknown error') if close_result else 'No response'}")
                    else:
                        logger.warning(f"[BOT] {symbol}: Позиция {position_to_close} не найдена на бирже для закрытия")
                else:
                    logger.error(f"[BOT] {symbol}: Не удалось получить позиции с биржи для закрытия")
                    
            except Exception as e:
                logger.error(f"[BOT] {symbol}: Ошибка при закрытии позиции на бирже: {str(e)}")
        elif position_to_close and not exchange:
            logger.error(f"[BOT] {symbol}: Биржа не инициализирована, позиция {position_to_close} не может быть закрыта")
        
        # Логируем остановку бота в историю
        log_bot_stop(symbol, reason)
        
        # Сохраняем состояние после остановки
        save_bots_state()
        
        # Обновляем кэш после остановки
        update_bots_cache_data()
        
        return jsonify({
            'success': True, 
            'message': f'Бот для {symbol} остановлен'
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка остановки бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/pause', methods=['POST'])
def pause_bot_endpoint():
    """Приостановить бота"""
    try:
        data = request.get_json()
        if not data or not data.get('symbol'):
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        symbol = data['symbol']
        
        # Проверяем, есть ли открытая позиция у бота
        position_to_close = None
        with bots_data_lock:
            if symbol not in bots_data['bots']:
                return jsonify({'success': False, 'error': 'Bot not found'}), 404
            
            bot_data = bots_data['bots'][symbol]
            old_status = bot_data['status']
            
            # Проверяем, есть ли открытая позиция
            if bot_data.get('position_side') in ['LONG', 'SHORT']:
                position_to_close = bot_data['position_side']
                logger.info(f"[BOT] {symbol}: Найдена открытая позиция {position_to_close}, будет закрыта при приостановке")
            
            bot_data['status'] = BOT_STATUS['PAUSED']
            logger.info(f"[BOT] {symbol}: Бот приостановлен (был: {old_status})")
        
        # Закрываем позицию на бирже, если она была открыта
        if position_to_close and exchange:
            try:
                logger.info(f"[BOT] {symbol}: Закрываем позицию {position_to_close} на бирже...")
                
                # Получаем текущие позиции для определения размера
                positions_response = exchange.get_positions()
                if positions_response and positions_response.get('success'):
                    positions = positions_response.get('data', [])
                    
                    # Ищем нашу позицию
                    our_position = None
                    for pos in positions:
                        if (pos['symbol'] == f"{symbol}USDT" and 
                            pos['side'] == position_to_close and 
                            float(pos.get('size', 0)) > 0):
                            our_position = pos
                            break
                    
                    if our_position:
                        # Закрываем позицию через exchange.close_position
                        close_result = exchange.close_position(
                            symbol=symbol,
                            size=float(our_position['size']),
                            side=position_to_close,
                            order_type="Market"
                        )
                        
                        if close_result and close_result.get('success'):
                            logger.info(f"[BOT] {symbol}: ✅ Позиция {position_to_close} успешно закрыта на бирже")
                        else:
                            logger.error(f"[BOT] {symbol}: ❌ Ошибка закрытия позиции на бирже: {close_result.get('message', 'Unknown error') if close_result else 'No response'}")
                    else:
                        logger.warning(f"[BOT] {symbol}: Позиция {position_to_close} не найдена на бирже для закрытия")
                else:
                    logger.error(f"[BOT] {symbol}: Не удалось получить позиции с биржи для закрытия")
                    
            except Exception as e:
                logger.error(f"[BOT] {symbol}: Ошибка при закрытии позиции на бирже: {str(e)}")
        elif position_to_close and not exchange:
            logger.error(f"[BOT] {symbol}: Биржа не инициализирована, позиция {position_to_close} не может быть закрыта")
        
        return jsonify({
            'success': True,
            'message': f'Бот для {symbol} приостановлен'
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка приостановки бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/delete', methods=['POST'])
def delete_bot_endpoint():
    """Удалить бота"""
    try:
        logger.info(f"[API] 📥 Получен запрос удаления бота: {request.get_data()}")
        
        # Пробуем разные способы получения данных
        try:
            data = request.get_json()
        except Exception as json_error:
            logger.error(f"[API] ❌ Ошибка парсинга JSON: {json_error}")
            # Пробуем получить данные как form data
            data = request.form.to_dict()
            if not data:
                # Пробуем получить данные из args
                data = request.args.to_dict()
        
        logger.info(f"[API] 📊 Распарсенные данные: {data}")
        
        if not data or not data.get('symbol'):
            logger.error(f"[API] ❌ Отсутствует symbol в данных: {data}")
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        symbol = data['symbol']
        reason = data.get('reason', 'Удален пользователем')
        
        with bots_data_lock:
            logger.info(f"[API] 🔍 Ищем бота {symbol} в bots_data. Доступные боты: {list(bots_data['bots'].keys())}")
            if symbol not in bots_data['bots']:
                logger.error(f"[API] ❌ Бот {symbol} не найден в bots_data")
                return jsonify({'success': False, 'error': 'Bot not found'}), 404
            
            # Получаем данные бота перед удалением для истории
            bot_data = bots_data['bots'][symbol]
            del bots_data['bots'][symbol]
            logger.info(f"[BOT] {symbol}: Бот удален")
            
            # Обновляем глобальную статистику
            bots_data['global_stats']['active_bots'] = len([bot for bot in bots_data['bots'].values() if bot.get('status') in ['running', 'idle']])
            bots_data['global_stats']['bots_in_position'] = len([bot for bot in bots_data['bots'].values() if bot.get('position_side')])
        
        # Логируем удаление бота в историю
        log_bot_stop(symbol, f"Удален: {reason}")
        
        # Сохраняем состояние после удаления
        save_bots_state()
        
        # Обновляем кэш после удаления
        update_bots_cache_data()
        
        return jsonify({
            'success': True,
            'message': f'Бот для {symbol} удален'
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка удаления бота: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/close-position', methods=['POST'])
def close_position_endpoint():
    """Принудительно закрыть позицию бота"""
    try:
        logger.info(f"[API] 📥 Получен запрос закрытия позиции: {request.get_data()}")
        
        # Пробуем разные способы получения данных
        try:
            data = request.get_json()
        except Exception as json_error:
            logger.error(f"[API] ❌ Ошибка парсинга JSON: {json_error}")
            # Пробуем получить данные как form data
            data = request.form.to_dict()
            if not data:
                # Пробуем получить данные из args
                data = request.args.to_dict()
        
        logger.info(f"[API] 📊 Распарсенные данные: {data}")
        
        if not data or not data.get('symbol'):
            logger.error(f"[API] ❌ Отсутствует symbol в данных: {data}")
            return jsonify({'success': False, 'error': 'Symbol required'}), 400
        
        symbol = data['symbol']
        force_close = data.get('force', False)  # Принудительное закрытие даже если бот не в позиции
        
        if not exchange:
            logger.error(f"[API] ❌ Биржа не инициализирована")
            return jsonify({'success': False, 'error': 'Exchange not initialized'}), 500
        
        # Получаем текущие позиции с биржи
        positions_response = exchange.get_positions()
        if not positions_response or not positions_response.get('success'):
            logger.error(f"[API] ❌ Не удалось получить позиции с биржи")
            return jsonify({'success': False, 'error': 'Failed to get positions from exchange'}), 500
        
        positions = positions_response.get('data', [])
        
        # Ищем позиции для данного символа
        symbol_positions = []
        for pos in positions:
            if pos['symbol'] == f"{symbol}USDT" and float(pos.get('size', 0)) > 0:
                symbol_positions.append(pos)
        
        if not symbol_positions:
            logger.warning(f"[API] ⚠️ Позиции для {symbol} не найдены на бирже")
            return jsonify({
                'success': False, 
                'message': f'Позиции для {symbol} не найдены на бирже'
            }), 404
        
        # Закрываем все найденные позиции
        closed_positions = []
        errors = []
        
        for pos in symbol_positions:
            try:
                position_side = 'LONG' if pos['side'] == 'Buy' else 'SHORT'
                position_size = float(pos['size'])
                
                logger.info(f"[API] 🔄 Закрываем позицию {position_side} размером {position_size} для {symbol}")
                
                close_result = exchange.close_position(
                    symbol=symbol,
                    size=position_size,
                    side=position_side,
                    order_type="Market"
                )
                
                if close_result and close_result.get('success'):
                    closed_positions.append({
                        'side': position_side,
                        'size': position_size,
                        'order_id': close_result.get('order_id')
                    })
                    logger.info(f"[API] ✅ Позиция {position_side} для {symbol} успешно закрыта")
                else:
                    error_msg = close_result.get('message', 'Unknown error') if close_result else 'No response'
                    errors.append(f"Позиция {position_side}: {error_msg}")
                    logger.error(f"[API] ❌ Ошибка закрытия позиции {position_side} для {symbol}: {error_msg}")
                    
            except Exception as e:
                error_msg = f"Позиция {pos['side']}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[API] ❌ Исключение при закрытии позиции {pos['side']} для {symbol}: {str(e)}")
        
        # Обновляем данные бота, если он существует
        with bots_data_lock:
            if symbol in bots_data['bots']:
                bot_data = bots_data['bots'][symbol]
                if closed_positions:
                    bot_data['position_side'] = None
                    bot_data['unrealized_pnl'] = 0.0
                    bot_data['status'] = BOT_STATUS['IDLE']
                    logger.info(f"[API] 🔄 Обновлены данные бота {symbol} после закрытия позиций")
                
                # Обновляем глобальную статистику
                bots_data['global_stats']['bots_in_position'] = len([bot for bot in bots_data['bots'].values() if bot.get('position_side')])
        
        # Сохраняем состояние
        save_bots_state()
        update_bots_cache_data()
        
        if closed_positions:
            return jsonify({
                'success': True,
                'message': f'Закрыто {len(closed_positions)} позиций для {symbol}',
                'closed_positions': closed_positions,
                'errors': errors if errors else None
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Не удалось закрыть позиции для {symbol}',
                'errors': errors
            }), 500
            
    except Exception as e:
        logger.error(f"[ERROR] Ошибка закрытия позиций: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/system-config', methods=['GET', 'POST'])
def system_config():
    """Получить или обновить системные настройки"""
    global STOP_LOSS_SETUP_INTERVAL, POSITION_SYNC_INTERVAL, INACTIVE_BOT_CLEANUP_INTERVAL, INACTIVE_BOT_TIMEOUT
    try:
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'config': {
                    'rsi_update_interval': SystemConfig.RSI_UPDATE_INTERVAL,
                    'auto_save_interval': SystemConfig.AUTO_SAVE_INTERVAL,
                    'debug_mode': SystemConfig.DEBUG_MODE,
                    'auto_refresh_ui': SystemConfig.AUTO_REFRESH_UI,
                    'refresh_interval': SystemConfig.UI_REFRESH_INTERVAL,
                    # Интервалы синхронизации и очистки
                    'position_sync_interval': POSITION_SYNC_INTERVAL,
                    'inactive_bot_cleanup_interval': INACTIVE_BOT_CLEANUP_INTERVAL,
                    'inactive_bot_timeout': INACTIVE_BOT_TIMEOUT,
                    'stop_loss_setup_interval': STOP_LOSS_SETUP_INTERVAL,
                    # Настройки улучшенного RSI
                    'enhanced_rsi_enabled': SystemConfig.ENHANCED_RSI_ENABLED,
                    'enhanced_rsi_require_volume_confirmation': SystemConfig.ENHANCED_RSI_REQUIRE_VOLUME_CONFIRMATION,
                    'enhanced_rsi_require_divergence_confirmation': SystemConfig.ENHANCED_RSI_REQUIRE_DIVERGENCE_CONFIRMATION,
                    'enhanced_rsi_use_stoch_rsi': SystemConfig.ENHANCED_RSI_USE_STOCH_RSI,
                    'rsi_extreme_zone_timeout': RSI_EXTREME_ZONE_TIMEOUT,
                    'rsi_extreme_oversold': RSI_EXTREME_OVERSOLD,
                    'rsi_extreme_overbought': RSI_EXTREME_OVERBOUGHT,
                    'rsi_volume_confirmation_multiplier': RSI_VOLUME_CONFIRMATION_MULTIPLIER,
                    'rsi_divergence_lookback': RSI_DIVERGENCE_LOOKBACK
                }
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            logger.info(f"[CONFIG] Обновление системных настроек: {data}")
            
            # Обновляем настройки
            if 'rsi_update_interval' in data:
                SystemConfig.RSI_UPDATE_INTERVAL = int(data['rsi_update_interval'])
                logger.info(f"[CONFIG] RSI интервал обновлен: {SystemConfig.RSI_UPDATE_INTERVAL} сек")
                
                # Обновляем интервал в SmartRSIManager если он активен
                if 'smart_rsi_manager' in globals() and smart_rsi_manager:
                    smart_rsi_manager.update_monitoring_interval(SystemConfig.RSI_UPDATE_INTERVAL)
                    logger.info(f"[CONFIG] ✅ SmartRSIManager обновлен с новым интервалом")
            
            if 'auto_save_interval' in data:
                SystemConfig.AUTO_SAVE_INTERVAL = int(data['auto_save_interval'])
                logger.info(f"[CONFIG] Автосохранение интервал обновлен: {SystemConfig.AUTO_SAVE_INTERVAL} сек")
            
            if 'debug_mode' in data:
                SystemConfig.DEBUG_MODE = bool(data['debug_mode'])
                logger.info(f"[CONFIG] Режим отладки: {SystemConfig.DEBUG_MODE}")
            
            if 'auto_refresh_ui' in data:
                SystemConfig.AUTO_REFRESH_UI = bool(data['auto_refresh_ui'])
                logger.info(f"[CONFIG] Автообновление UI: {SystemConfig.AUTO_REFRESH_UI}")
            
            if 'refresh_interval' in data:
                SystemConfig.UI_REFRESH_INTERVAL = int(data['refresh_interval'])
                logger.info(f"[CONFIG] Интервал обновления UI: {SystemConfig.UI_REFRESH_INTERVAL} сек")
            
            # Интервалы синхронизации и очистки
            if 'stop_loss_setup_interval' in data:
                old_value = STOP_LOSS_SETUP_INTERVAL
                STOP_LOSS_SETUP_INTERVAL = int(data['stop_loss_setup_interval'])
                logger.info(f"[CONFIG] Stop Loss интервал обновлен: {old_value} → {STOP_LOSS_SETUP_INTERVAL} сек")
            
            if 'position_sync_interval' in data:
                old_value = POSITION_SYNC_INTERVAL
                POSITION_SYNC_INTERVAL = int(data['position_sync_interval'])
                logger.info(f"[CONFIG] Position Sync интервал обновлен: {old_value} → {POSITION_SYNC_INTERVAL} сек")
            
            if 'inactive_bot_cleanup_interval' in data:
                old_value = INACTIVE_BOT_CLEANUP_INTERVAL
                INACTIVE_BOT_CLEANUP_INTERVAL = int(data['inactive_bot_cleanup_interval'])
                logger.info(f"[CONFIG] Inactive Bot Cleanup интервал обновлен: {old_value} → {INACTIVE_BOT_CLEANUP_INTERVAL} сек")
            
            if 'inactive_bot_timeout' in data:
                old_value = INACTIVE_BOT_TIMEOUT
                INACTIVE_BOT_TIMEOUT = int(data['inactive_bot_timeout'])
                logger.info(f"[CONFIG] Inactive Bot Timeout обновлен: {old_value} → {INACTIVE_BOT_TIMEOUT} сек")
            
            # Настройки улучшенного RSI
            if 'enhanced_rsi_enabled' in data:
                SystemConfig.ENHANCED_RSI_ENABLED = bool(data['enhanced_rsi_enabled'])
                logger.info(f"[CONFIG] Улучшенная система RSI: {SystemConfig.ENHANCED_RSI_ENABLED}")
            
            if 'enhanced_rsi_require_volume_confirmation' in data:
                SystemConfig.ENHANCED_RSI_REQUIRE_VOLUME_CONFIRMATION = bool(data['enhanced_rsi_require_volume_confirmation'])
                logger.info(f"[CONFIG] Подтверждение объемом: {SystemConfig.ENHANCED_RSI_REQUIRE_VOLUME_CONFIRMATION}")
            
            if 'enhanced_rsi_require_divergence_confirmation' in data:
                SystemConfig.ENHANCED_RSI_REQUIRE_DIVERGENCE_CONFIRMATION = bool(data['enhanced_rsi_require_divergence_confirmation'])
                logger.info(f"[CONFIG] Строгий режим (дивергенции): {SystemConfig.ENHANCED_RSI_REQUIRE_DIVERGENCE_CONFIRMATION}")
            
            if 'enhanced_rsi_use_stoch_rsi' in data:
                SystemConfig.ENHANCED_RSI_USE_STOCH_RSI = bool(data['enhanced_rsi_use_stoch_rsi'])
                logger.info(f"[CONFIG] Использовать Stochastic RSI: {SystemConfig.ENHANCED_RSI_USE_STOCH_RSI}")
        
            # КРИТИЧЕСКИ ВАЖНО: Сохраняем системные настройки в файл
            # Сначала загружаем существующие настройки, чтобы не потерять другие поля
            existing_config = {}
            if os.path.exists(SYSTEM_CONFIG_FILE):
                try:
                    with open(SYSTEM_CONFIG_FILE, 'r', encoding='utf-8') as f:
                        existing_config = json.load(f)
                except Exception as e:
                    logger.warning(f"[CONFIG] ⚠️ Не удалось загрузить существующую конфигурацию: {e}")
            
            # Обновляем только измененные поля
            system_config_data = existing_config.copy()
            system_config_data.update({
                'rsi_update_interval': SystemConfig.RSI_UPDATE_INTERVAL,
                'auto_save_interval': SystemConfig.AUTO_SAVE_INTERVAL,
                'debug_mode': SystemConfig.DEBUG_MODE,
                'auto_refresh_ui': SystemConfig.AUTO_REFRESH_UI,
                'refresh_interval': SystemConfig.UI_REFRESH_INTERVAL,
                # Интервалы синхронизации и очистки
                'position_sync_interval': POSITION_SYNC_INTERVAL,
                'inactive_bot_cleanup_interval': INACTIVE_BOT_CLEANUP_INTERVAL,
                'inactive_bot_timeout': INACTIVE_BOT_TIMEOUT,
                'stop_loss_setup_interval': STOP_LOSS_SETUP_INTERVAL,
                # Настройки улучшенного RSI
                'enhanced_rsi_enabled': SystemConfig.ENHANCED_RSI_ENABLED,
                'enhanced_rsi_require_volume_confirmation': SystemConfig.ENHANCED_RSI_REQUIRE_VOLUME_CONFIRMATION,
                'enhanced_rsi_require_divergence_confirmation': SystemConfig.ENHANCED_RSI_REQUIRE_DIVERGENCE_CONFIRMATION,
                'enhanced_rsi_use_stoch_rsi': SystemConfig.ENHANCED_RSI_USE_STOCH_RSI
            })
            
            saved_to_file = save_system_config(system_config_data)
            if saved_to_file:
                logger.info("[CONFIG] ✅ Системные настройки сохранены в файл")
                # Перезагружаем конфигурацию, чтобы применить изменения
                logger.info("[CONFIG] 🔄 Перезагружаем конфигурацию из файла...")
                load_system_config()
                logger.info("[CONFIG] ✅ Конфигурация успешно перезагружена")
            else:
                logger.error("[CONFIG] ❌ Ошибка сохранения системных настроек")
        
        return jsonify({
            'success': True,
                'message': 'Системные настройки обновлены и сохранены',
                'config': system_config_data,
                'saved_to_file': saved_to_file
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка настройки системы: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/sync-positions', methods=['POST'])
def sync_positions_manual():
    """Принудительная синхронизация позиций с биржей"""
    try:
        # ✅ Не логируем частые вызовы (только результаты)
        result = sync_positions_with_exchange()
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Синхронизация позиций выполнена успешно',
                'synced': True
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Синхронизация не потребовалась - все позиции актуальны',
                'synced': False
            })
            
    except Exception as e:
        logger.error(f"[MANUAL_SYNC] ❌ Ошибка принудительной синхронизации: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/cleanup-inactive', methods=['POST'])
def cleanup_inactive_manual():
    """Принудительная очистка неактивных ботов"""
    try:
        logger.info("[MANUAL_CLEANUP] 🧹 Запуск принудительной очистки неактивных ботов")
        result = cleanup_inactive_bots()
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Очистка неактивных ботов выполнена успешно',
                'cleaned': True
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Неактивных ботов для удаления не найдено',
                'cleaned': False
            })
            
    except Exception as e:
        logger.error(f"[MANUAL_CLEANUP] ❌ Ошибка принудительной очистки: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# УДАЛЕНО: API endpoint cleanup-mature
# Зрелость монеты необратима - нет смысла в API для удаления зрелых монет

@bots_app.route('/api/bots/mature-coins-list', methods=['GET'])
def get_mature_coins_list():
    """Получить список всех зрелых монет"""
    try:
        with mature_coins_lock:
            mature_coins_list = list(mature_coins_storage.keys())
        
            return jsonify({
                'success': True,
            'mature_coins': mature_coins_list,
            'total_count': len(mature_coins_list)
        })
        
    except Exception as e:
        logger.error(f"[API_MATURE_LIST] ❌ Ошибка получения списка зрелых монет: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/remove-mature-coins', methods=['POST'])
def remove_mature_coins_api():
    """API для удаления конкретных монет из зрелых"""
    try:
        data = request.get_json()
        if not data or 'coins' not in data:
            return jsonify({
                'success': False,
                'error': 'Не указаны монеты для удаления'
            }), 400
        
        coins_to_remove = data['coins']
        if not isinstance(coins_to_remove, list):
            return jsonify({
                'success': False,
                'error': 'Параметр coins должен быть массивом'
            }), 400
        
        result = remove_mature_coins(coins_to_remove)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'removed_count': result['removed_count'],
                'removed_coins': result['removed_coins'],
                'not_found': result['not_found']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"[API_REMOVE_MATURE] ❌ Ошибка API удаления монет: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/smart-rsi-status', methods=['GET'])
def get_smart_rsi_status():
    """Получить статус Smart RSI Manager"""
    try:
        global smart_rsi_manager
        if not smart_rsi_manager:
            return jsonify({
                'success': False,
                'error': 'Smart RSI Manager не инициализирован'
            }), 500
        
        status = smart_rsi_manager.get_status()
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"[API] ❌ Ошибка получения статуса Smart RSI Manager: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/force-rsi-update', methods=['POST'])
def force_rsi_update():
    """Принудительно обновить RSI данные"""
    try:
        logger.info("[API] 🔄 Принудительное обновление RSI данных...")
        
        # Запускаем обновление RSI данных в отдельном потоке
        import threading
        def update_rsi():
            try:
                load_all_coins_rsi()
                logger.info("[API] ✅ RSI данные обновлены принудительно")
            except Exception as e:
                logger.error(f"[API] ❌ Ошибка принудительного обновления RSI: {e}")
        
        thread = threading.Thread(target=update_rsi)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Обновление RSI данных запущено'
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка принудительного обновления RSI: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/test-anti-pump/<symbol>', methods=['GET'])
def test_anti_pump_endpoint(symbol):
    """Тестирует антипамп фильтр для конкретной монеты"""
    try:
        test_anti_pump_filter(symbol)
        return jsonify({'success': True, 'message': f'Тест антипамп фильтра для {symbol} выполнен'})
    except Exception as e:
        logger.error(f"[API] Ошибка тестирования антипамп фильтра для {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/test-rsi-time-filter/<symbol>', methods=['GET'])
def test_rsi_time_filter_endpoint(symbol):
    """Тестирует RSI временной фильтр для конкретной монеты"""
    try:
        test_rsi_time_filter(symbol)
        return jsonify({'success': True, 'message': f'Тест RSI временного фильтра для {symbol} выполнен'})
    except Exception as e:
        logger.error(f"[API] Ошибка тестирования RSI временного фильтра для {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/process-trading-signals', methods=['POST'])
def process_trading_signals_endpoint():
    """Принудительно обработать торговые сигналы для всех ботов"""
    try:
        logger.info("[API] 🔄 Принудительная обработка торговых сигналов...")
        
        # Вызываем process_trading_signals_for_all_bots в основном процессе
        process_trading_signals_for_all_bots(exchange_obj=exchange)
        
        # Получаем количество активных ботов для отчета
        with bots_data_lock:
            active_bots = {symbol: bot for symbol, bot in bots_data['bots'].items() 
                          if bot['status'] not in [BOT_STATUS['IDLE'], BOT_STATUS['PAUSED']]}
        
        logger.info(f"[API] ✅ Обработка торговых сигналов завершена для {len(active_bots)} ботов")
        
        return jsonify({
            'success': True,
            'message': f'Обработка торговых сигналов завершена для {len(active_bots)} ботов',
            'active_bots_count': len(active_bots)
        })
        
    except Exception as e:
        logger.error(f"[API] ❌ Ошибка обработки торговых сигналов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/reset-update-flag', methods=['POST'])
def reset_update_flag():
    """Принудительно сбросить флаг update_in_progress"""
    try:
        with rsi_data_lock:
            was_in_progress = coins_rsi_data['update_in_progress']
            coins_rsi_data['update_in_progress'] = False
            
        logger.info(f"[API] 🔄 Флаг update_in_progress сброшен (был: {was_in_progress})")
        return jsonify({
            'success': True,
            'message': 'Флаг update_in_progress сброшен',
            'was_in_progress': was_in_progress
        })
        
    except Exception as e:
        logger.error(f"[API] ❌ Ошибка сброса флага update_in_progress: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/test-stop', methods=['POST'])
def test_stop_bot():
    """Тестовый endpoint для остановки бота"""
    try:
        logger.info(f"[API] 🧪 Тестовый запрос остановки бота")
        logger.info(f"[API] 📥 Raw data: {request.get_data()}")
        logger.info(f"[API] 📥 Headers: {dict(request.headers)}")
        
        # Пробуем получить данные разными способами
        json_data = None
        form_data = None
        args_data = None
        
        try:
            json_data = request.get_json()
            logger.info(f"[API] 📊 JSON data: {json_data}")
        except Exception as e:
            logger.error(f"[API] ❌ JSON error: {e}")
        
        try:
            form_data = request.form.to_dict()
            logger.info(f"[API] 📊 Form data: {form_data}")
        except Exception as e:
            logger.error(f"[API] ❌ Form error: {e}")
        
        try:
            args_data = request.args.to_dict()
            logger.info(f"[API] 📊 Args data: {args_data}")
        except Exception as e:
            logger.error(f"[API] ❌ Args error: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Тестовый запрос получен',
            'json_data': json_data,
            'form_data': form_data,
            'args_data': args_data
        })
        
    except Exception as e:
        logger.error(f"[API] ❌ Ошибка тестового запроса: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/activate-trading-rules', methods=['POST'])
def activate_trading_rules_manual():
    """Активация правил торговли для зрелых монет"""
    try:
        logger.info("[MANUAL_CLEANUP] 🎯 Запуск активации правил торговли")
        result = check_trading_rules_activation()
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Правила торговли активированы успешно',
                'activated': True
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Нет зрелых монет для активации правил торговли',
                'activated': False
            })
            
    except Exception as e:
        logger.error(f"[MANUAL_CLEANUP] ❌ Ошибка активации правил торговли: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/auto-bot', methods=['GET', 'POST'])
def auto_bot_config():
    """Получить или обновить конфигурацию Auto Bot"""
    try:
        # ✅ Логируем только POST (изменения), GET не логируем (слишком часто)
        if request.method == 'POST':
            logger.info(f"[CONFIG_API] 📝 Изменение конфигурации Auto Bot")
        
        if request.method == 'GET':
            with bots_data_lock:
                config = bots_data['auto_bot_config'].copy()
                return jsonify({
                    'success': True,
                    'config': config
                })
        
        elif request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            logger.info(f"[CONFIG] Обновление конфигурации Auto Bot: {data}")
            
            with bots_data_lock:
                for key, value in data.items():
                    if key in bots_data['auto_bot_config']:
                        old_value = bots_data['auto_bot_config'][key]
                        bots_data['auto_bot_config'][key] = value
                        logger.info(f"[CONFIG] {key}: {old_value} → {value}")
                        
                        # Специальное логирование для фильтров тренда
                        if key == 'avoid_down_trend':
                            trend_status = "включен" if value else "выключен"
                            logger.info(f"[TREND_FILTER] 🔻 Фильтр DOWN тренда для LONG позиций: {trend_status}")
                        elif key == 'avoid_up_trend':
                            trend_status = "включен" if value else "выключен"
                            logger.info(f"[TREND_FILTER] 📈 Фильтр UP тренда для SHORT позиций: {trend_status}")
            
            # КРИТИЧЕСКИ ВАЖНО: Сохраняем конфигурацию в файл!
            save_result = save_auto_bot_config()
            if save_result:
                logger.info("[CONFIG] ✅ Конфигурация Auto Bot сохранена в файл")
            else:
                logger.error("[CONFIG] ❌ Ошибка сохранения конфигурации Auto Bot")
            
            # КРИТИЧЕСКИ ВАЖНО: При включении Auto Bot запускаем немедленную проверку
            auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            if 'enabled' in data and data['enabled'] is True and auto_bot_enabled:
                # ✅ ЯРКИЙ ЛОГ ВКЛЮЧЕНИЯ (ЗЕЛЕНЫЙ)
                logger.info("=" * 80)
                logger.info("\033[92m🟢 AUTO BOT ВКЛЮЧЕН! 🟢\033[0m")
                logger.info("=" * 80)
                logger.info("⚠️  ВНИМАНИЕ: Автобот будет автоматически создавать ботов!")
                logger.info(f"⚙️  Макс. одновременных ботов: {bots_data['auto_bot_config'].get('max_concurrent', 5)}")
                logger.info(f"📊 RSI пороги: LONG≤{bots_data['auto_bot_config'].get('rsi_long_threshold')}, SHORT≥{bots_data['auto_bot_config'].get('rsi_short_threshold')}")
                logger.info(f"⏰ RSI Time Filter: {'ON' if bots_data['auto_bot_config'].get('rsi_time_filter_enabled') else 'OFF'} ({bots_data['auto_bot_config'].get('rsi_time_filter_candles')} свечей)")
                logger.info("=" * 80)
                
                try:
                    # process_auto_bot_signals(exchange_obj=exchange)  # ОТКЛЮЧЕНО!
                    logger.info("[CONFIG] ✅ Немедленная проверка Auto Bot завершена")
                except Exception as e:
                    logger.error(f"[CONFIG] ❌ Ошибка немедленной проверки Auto Bot: {e}")
            
            # КРИТИЧЕСКИ ВАЖНО: При отключении Auto Bot НЕ удаляем ботов!
            if 'enabled' in data and data['enabled'] is False:
                # ✅ ЯРКИЙ ЛОГ ВЫКЛЮЧЕНИЯ (КРАСНЫЙ)
                logger.info("=" * 80)
                logger.info("\033[91m🔴 AUTO BOT ВЫКЛЮЧЕН! 🔴\033[0m")
                logger.info("=" * 80)
                
                with bots_data_lock:
                    bots_count = len(bots_data['bots'])
                    bots_in_position = sum(1 for bot in bots_data['bots'].values() 
                                          if bot.get('status') in ['IN_POSITION_LONG', 'IN_POSITION_SHORT'])
                
                if bots_count > 0:
                    logger.info(f"💾 Сохранено {bots_count} ботов:")
                    logger.info(f"   📊 В позиции: {bots_in_position}")
                    logger.info(f"   🔄 Остальные: {bots_count - bots_in_position}")
                    logger.info("")
                    logger.info("✅ ЧТО БУДЕТ ДАЛЬШЕ:")
                    logger.info("   🔄 Существующие боты продолжат работать")
                    logger.info("   🛡️ Защитные механизмы активны (стоп-лосс, RSI выход)")
                    logger.info("   ❌ Новые боты НЕ будут создаваться")
                    logger.info("   🗑️ Для удаления используйте кнопку 'Удалить всё'")
                else:
                    logger.info("ℹ️  Нет активных ботов")
                
                logger.info("=" * 80)
                logger.info("✅ АВТОБОТ ОСТАНОВЛЕН (боты сохранены)")
                logger.info("=" * 80)
        
        return jsonify({
            'success': True,
            'message': 'Конфигурация Auto Bot обновлена и сохранена',
            'config': bots_data['auto_bot_config'].copy(),
            'saved_to_file': save_result
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка конфигурации Auto Bot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/sync-positions', methods=['POST'])
def sync_positions_api():
    """Синхронизирует позиции с биржей"""
    try:
        logger.info("[API] 🔄 Запрос синхронизации позиций с биржи")
        result = sync_positions_with_exchange()
        
        return jsonify({
            'success': result,
            'message': 'Синхронизация позиций завершена' if result else 'Ошибка синхронизации позиций'
        })
    except Exception as e:
        logger.error(f"[API] ❌ Ошибка синхронизации позиций: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/auto-bot/restore-defaults', methods=['POST'])
def restore_auto_bot_defaults():
    """Восстанавливает дефолтную конфигурацию Auto Bot"""
    try:
        logger.info("[API] 🔄 Запрос на восстановление дефолтной конфигурации Auto Bot")
        
        # Восстанавливаем дефолтные настройки
        result = restore_default_config()
        
        if result:
            with bots_data_lock:
                current_config = bots_data['auto_bot_config'].copy()
            
            return jsonify({
                'success': True,
                'message': 'Дефолтная конфигурация Auto Bot восстановлена',
                'config': current_config,
                'restored_to_defaults': True
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Ошибка восстановления дефолтной конфигурации'
            }), 500
            
    except Exception as e:
        logger.error(f"[ERROR] Ошибка восстановления дефолтной конфигурации: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/debug-init', methods=['GET'])
def debug_init_status():
    """Отладочный эндпоинт для проверки инициализации"""
    try:
        return jsonify({
            'success': True,
            'init_bot_service_called': 'init_bot_service' in globals(),
            'smart_rsi_manager_exists': smart_rsi_manager is not None,
            'exchange_exists': exchange is not None,
            'bots_data_keys': list(bots_data.keys()) if 'bots_data' in globals() else 'not_initialized'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bots_app.route('/api/bots/process-state', methods=['GET'])
def get_process_state():
    """Получить состояние всех процессов системы"""
    try:
        return jsonify({
            'success': True,
            'process_state': process_state.copy(),
            'system_info': {
                'smart_rsi_manager_running': smart_rsi_manager is not None and not smart_rsi_manager.shutdown_flag.is_set(),
                'exchange_initialized': exchange is not None,
                'total_bots': len(bots_data['bots']),
                'auto_bot_enabled': bots_data['auto_bot_config']['enabled'],
                'mature_coins_storage_size': len(mature_coins_storage),
                'optimal_ema_count': len(optimal_ema_data)
            }
                })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка получения состояния процессов: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/mature-coins', methods=['GET'])
def get_mature_coins():
    """Получение списка зрелых монет из постоянного хранилища"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'mature_coins': list(mature_coins_storage.keys()),
                'count': len(mature_coins_storage),
                'storage_details': mature_coins_storage
            }
        })
    except Exception as e:
        logger.error(f"[API] Ошибка получения зрелых монет: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/mature-coins/reload', methods=['POST'])
def reload_mature_coins():
    """Перезагрузить список зрелых монет из файла"""
    try:
        load_mature_coins_storage()
        logger.info(f"[MATURITY_STORAGE] Перезагружено {len(mature_coins_storage)} зрелых монет")
        return jsonify({
            'success': True,
            'message': f'Перезагружено {len(mature_coins_storage)} зрелых монет',
            'data': {
                'mature_coins': list(mature_coins_storage.keys()),
                'count': len(mature_coins_storage)
            }
        })
    except Exception as e:
        logger.error(f"[ERROR] Ошибка перезагрузки зрелых монет: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/mature-coins/<symbol>', methods=['DELETE'])
def remove_mature_coin(symbol):
    """Удаление монеты из постоянного хранилища зрелых монет"""
    try:
        if symbol in mature_coins_storage:
            remove_mature_coin_from_storage(symbol)
            return jsonify({
                'success': True,
                'message': f'Монета {symbol} удалена из постоянного хранилища зрелых монет'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Монета {symbol} не найдена в постоянном хранилище зрелых монет'
            }), 404
    except Exception as e:
        logger.error(f"[API] Ошибка удаления монеты {symbol} из хранилища: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/mature-coins/clear', methods=['POST'])
def clear_mature_coins_storage():
    """Очистка всего постоянного хранилища зрелых монет"""
    try:
        global mature_coins_storage
        mature_coins_storage = {}
        save_mature_coins_storage()
        logger.info("[API] Постоянное хранилище зрелых монет очищено")
        return jsonify({
            'success': True,
            'message': 'Постоянное хранилище зрелых монет очищено'
        })
    except Exception as e:
        logger.error(f"[API] Ошибка очистки хранилища зрелых монет: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/optimal-ema', methods=['GET'])
def get_optimal_ema():
    """Получение списка оптимальных EMA из хранилища"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'optimal_ema': optimal_ema_data,
                'count': len(optimal_ema_data)
            }
        })
    except Exception as e:
        logger.error(f"[API] Ошибка получения оптимальных EMA: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/optimal-ema/<symbol>', methods=['GET'])
def get_optimal_ema_for_symbol(symbol):
    """Получение оптимальных EMA для конкретной монеты"""
    try:
        if symbol in optimal_ema_data:
            return jsonify({
                'success': True,
                'data': optimal_ema_data[symbol]
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Оптимальные EMA для {symbol} не найдены'
            }), 404
    except Exception as e:
        logger.error(f"[API] Ошибка получения оптимальных EMA для {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/optimal-ema/<symbol>/rescan', methods=['POST'])
def rescan_optimal_ema(symbol):
    """Принудительное пересканирование оптимальных EMA для монеты"""
    try:
        # Здесь можно добавить логику для запуска пересканирования
        # Пока просто возвращаем сообщение
        return jsonify({
            'success': True,
            'message': f'Запущено пересканирование оптимальных EMA для {symbol}. Используйте скрипт optimal_ema.py для выполнения.'
        })
    except Exception as e:
        logger.error(f"[API] Ошибка пересканирования EMA для {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/optimal-ema-worker/status', methods=['GET'])
def get_optimal_ema_worker_status():
    """Получает статус воркера оптимальных EMA"""
    try:
        from bot_engine.optimal_ema_worker import get_optimal_ema_worker
        
        worker = get_optimal_ema_worker()
        if worker:
            status = worker.get_status()
            return jsonify({
                'success': True,
                'data': status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Воркер оптимальных EMA не инициализирован'
            }), 404
    except Exception as e:
        logger.error(f"[API] Ошибка получения статуса воркера: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/optimal-ema-worker/force-update', methods=['POST'])
def force_optimal_ema_update():
    """Принудительно запускает обновление оптимальных EMA"""
    try:
        from bot_engine.optimal_ema_worker import get_optimal_ema_worker
        
        worker = get_optimal_ema_worker()
        if worker:
            success = worker.force_update()
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Принудительное обновление оптимальных EMA запущено'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Обновление уже выполняется'
                }), 409
        else:
            return jsonify({
                'success': False,
                'error': 'Воркер оптимальных EMA не инициализирован'
            }), 404
    except Exception as e:
        logger.error(f"[API] Ошибка принудительного обновления: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/optimal-ema-worker/set-interval', methods=['POST'])
def set_optimal_ema_interval():
    """Устанавливает интервал обновления воркера оптимальных EMA"""
    try:
        from bot_engine.optimal_ema_worker import get_optimal_ema_worker
        
        data = request.get_json()
        if not data or 'interval' not in data:
            return jsonify({
                'success': False,
                'error': 'Не указан интервал обновления'
            }), 400
        
        interval = int(data['interval'])
        if interval < 300:  # Минимум 5 минут
            return jsonify({
                'success': False,
                'error': 'Интервал не может быть меньше 300 секунд (5 минут)'
            }), 400
        
        worker = get_optimal_ema_worker()
        if worker:
            success = worker.set_update_interval(interval)
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Интервал обновления изменен на {interval} секунд'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Не удалось изменить интервал'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Воркер оптимальных EMA не инициализирован'
            }), 404
    except Exception as e:
        logger.error(f"[API] Ошибка изменения интервала: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/default-config', methods=['GET'])
def get_default_config():
    """Получить дефолтную конфигурацию Auto Bot"""
    try:
        default_config = load_default_config()
        
        return jsonify({
            'success': True,
            'default_config': default_config,
            'message': 'Дефолтная конфигурация загружена'
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка загрузки дефолтной конфигурации: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/auto-bot/test-signals', methods=['POST'])
def test_auto_bot_signals():
    """Тестовый эндпоинт для принудительной обработки Auto Bot сигналов - УДАЛЕНО!"""
    return jsonify({'success': False, 'message': 'Auto Bot отключен!'})
    try:
        logger.info("[TEST] 🧪 Принудительная обработка Auto Bot сигналов...")
        
        # Принудительно вызываем обработку сигналов
        # process_auto_bot_signals(exchange_obj=exchange)  # ОТКЛЮЧЕНО!
        
        # Получаем статистику
        with bots_data_lock:
            auto_bot_enabled = bots_data['auto_bot_config']['enabled']
            total_bots = len(bots_data['bots'])
            max_concurrent = bots_data['auto_bot_config']['max_concurrent']
            
        with rsi_data_lock:
            signals = [c for c in coins_rsi_data['coins'].values() 
                      if c['signal'] in ['ENTER_LONG', 'ENTER_SHORT']]
        
        return jsonify({
            'success': True,
            'message': 'Auto Bot сигналы обработаны принудительно',
            'stats': {
                'auto_bot_enabled': auto_bot_enabled,
                'available_signals': len(signals),
                'current_bots': total_bots,
                'max_concurrent': max_concurrent,
                'signals_details': signals[:5]  # Первые 5 для примера
            }
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка тестирования Auto Bot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@bots_app.errorhandler(500)
def internal_error(error):
    logger.error(f"[ERROR] Внутренняя ошибка сервера: {str(error)}")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

def signal_handler(signum, frame):
    """Обработчик сигналов завершения с принудительным завершением"""
    global graceful_shutdown
    print(f"\n[SHUTDOWN] 🛑 Получен сигнал {signum}, начинаем graceful shutdown...")
    logger.info(f"[SHUTDOWN] 🛑 Получен сигнал {signum}, начинаем graceful shutdown...")
    graceful_shutdown = True
    shutdown_flag.set()
    
    # Запускаем принудительное завершение через таймер
    def force_exit():
        time.sleep(2.0)  # Даём 2 секунды на graceful shutdown
        print("[SHUTDOWN] ⏱️ Таймаут graceful shutdown, принудительное завершение...")
        logger.info("[SHUTDOWN] ⏱️ Таймаут graceful shutdown, принудительное завершение...")
        os._exit(0)
    
    force_exit_thread = threading.Thread(target=force_exit, daemon=True)
    force_exit_thread.start()
    
    # Пытаемся выполнить graceful shutdown
    try:
        cleanup_bot_service()
        print("[SHUTDOWN] ✅ Graceful shutdown завершен")
        logger.info("[SHUTDOWN] ✅ Graceful shutdown завершен")
        sys.exit(0)
    except Exception as e:
        print(f"[SHUTDOWN] ⚠️ Ошибка при graceful shutdown: {e}")
        logger.error(f"[SHUTDOWN] ⚠️ Ошибка при graceful shutdown: {e}")
        os._exit(1)

def cleanup_bot_service():
    """Очистка ресурсов при завершении сервиса"""
    global smart_rsi_manager, system_initialized
    
    # КРИТИЧЕСКИ ВАЖНО: Сбрасываем флаг, чтобы остановить торговлю
    system_initialized = False
    logger.info("[CLEANUP] 🛑 Флаг system_initialized сброшен - торговля остановлена")
    
    try:
        logger.info("[CLEANUP] 🧹 Очистка ресурсов сервиса ботов...")
        
        # Останавливаем асинхронный процессор
        stop_async_processor()
        
        # Останавливаем умный менеджер RSI
        if smart_rsi_manager:
            logger.info("[CLEANUP] 🛑 Остановка Smart RSI Manager...")
            smart_rsi_manager.stop()
            smart_rsi_manager = None
        
        # Останавливаем воркер оптимальных EMA
        try:
            from bot_engine.optimal_ema_worker import stop_optimal_ema_worker
            stop_optimal_ema_worker()
            logger.info("[CLEANUP] 🛑 Остановка воркера оптимальных EMA...")
        except Exception as e:
            logger.error(f"[CLEANUP] Ошибка остановки воркера оптимальных EMA: {e}")
        
        # Сохраняем все важные данные
        logger.info("[CLEANUP] 💾 Финальное сохранение всех данных...")
        
        # 1. Сохраняем состояние ботов
        logger.info("[CLEANUP] 📊 Сохранение состояния ботов...")
        save_bots_state()
        
        # 2. Сохраняем конфигурацию автобота
        logger.info("[CLEANUP] ⚙️ Сохранение конфигурации автобота...")
        save_auto_bot_config()
        
        # 3. Сохраняем системную конфигурацию
        logger.info("[CLEANUP] 🔧 Сохранение системной конфигурации...")
        system_config_data = {
            'bot_status_update_interval': BOT_STATUS_UPDATE_INTERVAL,
            'position_sync_interval': POSITION_SYNC_INTERVAL,
            'inactive_bot_cleanup_interval': INACTIVE_BOT_CLEANUP_INTERVAL,
            'inactive_bot_timeout': INACTIVE_BOT_TIMEOUT,
            'stop_loss_setup_interval': STOP_LOSS_SETUP_INTERVAL
        }
        save_system_config(system_config_data)
        
        # 4. Сохраняем кэш RSI данных
        logger.info("[CLEANUP] 📈 Сохранение кэша RSI данных...")
        save_rsi_cache()
        
        # 5. Сохраняем состояние процессов
        logger.info("[CLEANUP] 🔄 Сохранение состояния процессов...")
        save_process_state()
        
        # 6. Сохраняем данные о зрелости монет
        logger.info("[CLEANUP] 🪙 Сохранение данных о зрелости монет...")
        save_mature_coins_storage()
        
        # 7. Сохраняем оптимальные EMA периоды
        logger.info("[CLEANUP] 📊 Сохранение оптимальных EMA периодов...")
        save_optimal_ema_periods()
        
        logger.info("[CLEANUP] ✅ Все данные сохранены, очистка завершена")
        
    except Exception as e:
        logger.error(f"[CLEANUP] ❌ Ошибка при очистке: {e}")
        import traceback
        logger.error(f"[CLEANUP] Traceback: {traceback.format_exc()}")

def run_bots_service():
    """Запуск сервиса ботов"""
    print("[RUN_SERVICE] 🚀 Запуск run_bots_service...")
    try:
        # Создаем директорию для логов
        os.makedirs('logs', exist_ok=True)
        print("[RUN_SERVICE] 📁 Директория логов создана")
        
        # Очищаем старые логи при запуске
        log_files = ['logs/bots.log', 'logs/app.log', 'logs/error.log']
        for log_file in log_files:
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                if file_size > 2 * 1024 * 1024:  # 2MB
                    print(f"[RUN_SERVICE] 🗑️ Очищаем большой лог файл: {log_file} ({file_size / 1024 / 1024:.1f}MB)")
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write(f"# Лог файл очищен при запуске - {datetime.now().isoformat()}\n")
                else:
                    print(f"[RUN_SERVICE] 📝 Лог файл в порядке: {log_file} ({file_size / 1024:.1f}KB)")
        
        # Временно отключаем обработчики сигналов до полной инициализации
        # signal.signal(signal.SIGINT, signal_handler)
        # signal.signal(signal.SIGTERM, signal_handler)
        
        # Регистрируем функцию очистки для автоматического вызова при завершении
        atexit.register(cleanup_bot_service)
        
        logger.info(f"🌐 Запуск Flask сервера для ботов на {SystemConfig.BOTS_SERVICE_HOST}:{SystemConfig.BOTS_SERVICE_PORT}...")
        logger.info("📋 Этот сервис предоставляет API для торговых ботов")
        
        # Запускаем Flask сервер в отдельном потоке СРАЗУ
        def run_flask_server():
            try:
                logger.info("🚀 Запуск Flask сервера в отдельном потоке...")
                bots_app.run(
                    debug=SystemConfig.DEBUG_MODE,
                    host=SystemConfig.BOTS_SERVICE_HOST,
                    port=SystemConfig.BOTS_SERVICE_PORT,
                    use_reloader=False,
                    threaded=True
                )
            except Exception as e:
                logger.error(f"❌ Ошибка запуска Flask сервера: {e}")
        
        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        
        # Ждем, пока Flask сервер запустится
        import time
        time.sleep(3)
        logger.info("✅ Flask сервер запущен в фоновом режиме")
        
        # Теперь инициализируем сервис в отдельном потоке
        def init_service_async():
            try:
                logger.info("[INIT_THREAD] 🚀 Запуск инициализации в отдельном потоке...")
                result = init_bot_service()
                if result:
                    logger.info("[INIT_THREAD] ✅ Инициализация завершена успешно")
                    return True
                else:
                    logger.error("[INIT_THREAD] ❌ Инициализация завершена с ошибкой")
                    return False
            except Exception as e:
                logger.error(f"[INIT_THREAD] ❌ Исключение при инициализации: {e}")
                import traceback
                logger.error(f"[INIT_THREAD] Traceback: {traceback.format_exc()}")
                return False
        
        service_thread = threading.Thread(target=init_service_async, daemon=True)
        service_thread.start()
        
        # Ждем завершения инициализации сервиса
        logger.info("⏳ Ожидание инициализации сервиса ботов...")
        service_thread.join(timeout=30)  # Ждем максимум 30 секунд
        
        if service_thread.is_alive():
            logger.warning("⚠️ Инициализация сервиса ботов занимает больше времени, продолжаем...")
        else:
            logger.info("✅ Сервис ботов инициализирован")
        
        # ДОПОЛНИТЕЛЬНО: Ждем установки флага system_initialized
        logger.info("⏳ Ожидание установки флага system_initialized...")
        max_wait_time = 60  # Максимум 60 секунд
        wait_start = time.time()
        
        while not system_initialized and (time.time() - wait_start) < max_wait_time:
            time.sleep(1)
            if int(time.time() - wait_start) % 10 == 0:  # Каждые 10 секунд
                logger.info(f"⏳ Ожидание system_initialized... ({int(time.time() - wait_start)}s)")
        
        if system_initialized:
            logger.info("✅ Флаг system_initialized установлен - система готова к работе")
        else:
            logger.error("❌ Флаг system_initialized не установлен за {max_wait_time}s - возможны проблемы")
        
        # Теперь настраиваем обработчики сигналов после полной инициализации
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("✅ Обработчики сигналов настроены")
        
        # Запускаем воркер для обновления оптимальных EMA
        try:
            from bot_engine.optimal_ema_worker import start_optimal_ema_worker
            optimal_ema_worker = start_optimal_ema_worker(update_interval=21600)  # 6 часов
            if optimal_ema_worker:
                logger.info("✅ Воркер оптимальных EMA запущен")
            else:
                logger.warning("⚠️ Не удалось запустить воркер оптимальных EMA")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска воркера оптимальных EMA: {e}")
        
        # Основной поток
        logger.info("🔄 Сервис ботов запущен и работает...")
        last_bot_processing = 0
        bot_processing_interval = 30  # Обрабатываем ботов каждые 30 секунд
        
        while True:
            try:
                current_time = time.time()
                
                # Обрабатываем ботов каждые 30 секунд
                if current_time - last_bot_processing >= bot_processing_interval:
                    logger.info("[MAIN_LOOP] 🤖 Обработка ботов...")
                    process_trading_signals_for_all_bots(exchange_obj=exchange)
                    last_bot_processing = current_time
                    logger.info("[MAIN_LOOP] ✅ Обработка ботов завершена")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"[MAIN_LOOP] ❌ Ошибка в основном цикле: {e}")
                time.sleep(5)  # Ждем 5 секунд при ошибке
        
    except KeyboardInterrupt:
        logger.info("[STOP] Получен сигнал прерывания...")
        cleanup_bot_service()
        os._exit(0)
    except Exception as e:
        logger.error(f"[ERROR] Ошибка запуска сервиса ботов: {str(e)}")
        cleanup_bot_service()
        os._exit(1)
    finally:
        cleanup_bot_service()

@bots_app.route('/api/bots/active-detailed', methods=['GET'])
def get_active_bots_detailed():
    """Получает детальную информацию о активных ботах для мониторинга"""
    try:
        with bots_data_lock:
            active_bots = []
            for symbol, bot_data in bots_data['bots'].items():
                if bot_data.get('status') in ['armed_up', 'armed_down', 'in_position_long', 'in_position_short']:
                    # Получаем текущую цену из RSI данных
                    current_price = None
                    with rsi_data_lock:
                        coin_data = coins_rsi_data['coins'].get(symbol)
                        if coin_data:
                            current_price = coin_data.get('price')
                    
                    # Определяем направление позиции
                    position_side = None
                    if bot_data.get('status') in ['in_position_long']:
                        position_side = 'Long'
                    elif bot_data.get('status') in ['in_position_short']:
                        position_side = 'Short'
                    
                    # Получаем настройки бота
                    config = bot_data.get('config', {})
                    
                    # Рассчитываем потенциальный убыток по стоп-лоссу
                    stop_loss_pnl = 0
                    if current_price and position_side and bot_data.get('entry_price'):
                        entry_price = bot_data.get('entry_price')
                        max_loss_percent = config.get('max_loss_percent', 15.0)
                        
                        if position_side == 'Long':
                            stop_loss_price = entry_price * (1 - max_loss_percent / 100)
                            stop_loss_pnl = (stop_loss_price - entry_price) / entry_price * 100
                        else:  # Short
                            stop_loss_price = entry_price * (1 + max_loss_percent / 100)
                            stop_loss_pnl = (entry_price - stop_loss_price) / entry_price * 100
                    
                    active_bots.append({
                        'symbol': symbol,
                        'status': bot_data.get('status', 'unknown'),
                        'position_size': bot_data.get('position_size', 0),
                        'pnl': bot_data.get('pnl', 0),
                        'current_price': current_price,
                        'position_side': position_side,
                        'entry_price': bot_data.get('entry_price'),
                        'trailing_stop_active': bot_data.get('trailing_stop_active', False),
                        'stop_loss_price': bot_data.get('stop_loss_price'),
                        'stop_loss_pnl': stop_loss_pnl,
                        'position_start_time': bot_data.get('position_start_time'),
                        'max_position_hours': config.get('max_position_hours', 48),
                        'created_at': bot_data.get('created_at'),
                        'last_update': bot_data.get('last_update')
                    })
            
            return jsonify({
                'success': True,
                'bots': active_bots,
                'total': len(active_bots)
            })
            
    except Exception as e:
        logger.error(f"[API] ❌ Ошибка получения детальной информации о ботах: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/bots/history', methods=['GET'])
def get_bot_history():
    """Получает историю действий ботов"""
    try:
        symbol = request.args.get('symbol')
        action_type = request.args.get('action_type')
        limit = int(request.args.get('limit', 100))
        
        history = bot_history_manager.get_bot_history(symbol, action_type, limit)
        
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"[API] Ошибка получения истории ботов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/trades', methods=['GET'])
def get_bot_trades():
    """Получает историю торговых сделок ботов"""
    try:
        symbol = request.args.get('symbol')
        trade_type = request.args.get('trade_type')
        limit = int(request.args.get('limit', 100))
        
        trades = bot_history_manager.get_bot_trades(symbol, trade_type, limit)
        
        return jsonify({
            'success': True,
            'trades': trades,
            'count': len(trades)
        })
        
    except Exception as e:
        logger.error(f"[API] Ошибка получения сделок ботов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/statistics', methods=['GET'])
def get_bot_statistics():
    """Получает статистику по ботам"""
    try:
        symbol = request.args.get('symbol')
        
        statistics = bot_history_manager.get_bot_statistics(symbol)
        
        return jsonify({
            'success': True,
            'statistics': statistics
        })
        
    except Exception as e:
        logger.error(f"[API] Ошибка получения статистики ботов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/history/clear', methods=['POST'])
def clear_bot_history():
    """Очищает историю ботов"""
    try:
        data = request.get_json() or {}
        symbol = data.get('symbol')
        
        bot_history_manager.clear_history(symbol)
        
        message = f"История для {symbol} очищена" if symbol else "Вся история очищена"
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"[API] Ошибка очистки истории ботов: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bots_app.route('/api/bots/history/demo', methods=['POST'])
def create_demo_history():
    """Создает демо-данные для истории ботов"""
    try:
        from bot_history import create_demo_data
        
        success = create_demo_data()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Демо-данные созданы успешно'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Ошибка создания демо-данных'
            }), 500
        
    except Exception as e:
        logger.error(f"[API] Ошибка создания демо-данных: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # КРИТИЧЕСКИ ВАЖНО: Проверяем и останавливаем старые процессы bots.py САМЫМ ПЕРВЫМ!
    print()  # Пустая строка для читаемости
    if not check_and_stop_existing_bots_processes():
        print("❌ Запуск отменен")
        sys.exit(0)
    
    # Загружаем конфигурацию Auto Bot после проверки процессов
    load_auto_bot_config()
    
    print("=" * 60)
    print("INFOBOT - Trading Bots Service")
    print("=" * 60)
    
    # Инициализация биржи будет выполнена в init_bot_service()
    print("*** ОСНОВНЫЕ ФУНКЦИИ:")
    print("  - Постоянный мониторинг RSI 6H для всех монет")
    print("  - Анализ тренда 6H (EMA50/EMA200)")
    print("  - Торговые боты с Auto Bot режимом")
    print("  - Автовход: RSI ≤29 = LONG, RSI ≥71 = SHORT")
    print()
    print(f"*** Порт: {SystemConfig.BOTS_SERVICE_PORT}")
    print("*** API Эндпоинты:")
    print("  GET  /health                    - Проверка статуса")
    print("  GET  /api/bots/coins-with-rsi   - Все монеты с RSI 6H")
    print("  GET  /api/bots/list             - Список ботов")
    print("  POST /api/bots/create           - Создать бота")
    print("  GET  /api/bots/auto-bot         - Конфигурация Auto Bot")
    print("  POST /api/bots/auto-bot         - Обновить Auto Bot")
    print("  GET  /api/bots/optimal-ema      - Оптимальные EMA периоды")
    print("  GET  /api/bots/optimal-ema-worker/status - Статус воркера EMA")
    print("  POST /api/bots/optimal-ema-worker/force-update - Принудительное обновление")
    print("=" * 60)
    print("*** Запуск...")
    
    run_bots_service()
