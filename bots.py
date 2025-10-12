#!/usr/bin/env python3
"""
Сервис управления торговыми ботами (State Manager Architecture).

Весь код вынесен в модули bot_engine/.
Этот файл только инициализирует и запускает систему.

Порт: 5001
Версия: 2.0 (State Manager)
"""

import os
import sys
import signal
import threading
import time
import logging
from datetime import datetime

# Добавляем путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импорты Flask
from flask import Flask, render_template
from flask_cors import CORS

# Импорты цветного логирования
from color_logger import setup_color_logging

# Импорты биржи
from exchanges.exchange_factory import ExchangeFactory
from app.config import EXCHANGES, APP_DEBUG

# Импорты State Manager
from bot_engine.state_manager import BotSystemState
from bot_engine.managers.exchange_manager import ExchangeManager

# Импорты новых API endpoints
from bot_engine.api.endpoints_health import register_health_endpoints
from bot_engine.api.endpoints_bots import register_bots_endpoints
from bot_engine.api.endpoints_config import register_config_endpoints
from bot_engine.api.endpoints_rsi import register_rsi_endpoints
from bot_engine.api.endpoints_positions import register_positions_endpoints
from bot_engine.api.endpoints_mature import register_mature_endpoints
from bot_engine.api.endpoints_system import register_system_endpoints

# Настройка логирования
logger = setup_color_logging()

# Создаем Flask приложение
app = Flask(__name__)
CORS(app)

# Фильтр для уменьшения HTTP спама в логах
import logging
class HTTPAccessFilter(logging.Filter):
    def filter(self, record):
        # Фильтруем все HTTP запросы (GET, POST, OPTIONS, PUT, DELETE и т.д.)
        message = record.getMessage()
        # Проверяем наличие строки с HTTP запросом
        if '" HTTP/1.1" ' in message or '" HTTP/1.0" ' in message:
            # Это HTTP запрос - не показываем
            return False
        return True

# Применяем фильтр к Flask логгеру (werkzeug)
flask_logger = logging.getLogger('werkzeug')
flask_logger.addFilter(HTTPAccessFilter())

# Также применяем фильтр ко всем обработчикам werkzeug
for handler in flask_logger.handlers:
    handler.addFilter(HTTPAccessFilter())

# Также применяем к нашему логгеру
logger.addFilter(HTTPAccessFilter())
for handler in logger.handlers:
    handler.addFilter(HTTPAccessFilter())

# Глобальный state (единственная "глобальная" переменная)
bot_system_state = None

# Флаг инициализации
system_initialized = False


# ==================== ПРОСТОЙ API ENDPOINT (как в старом коде) ====================

@app.route('/api/status', methods=['GET'])
def api_status():
    """API endpoint для проверки статуса сервиса ботов (простой, без зависимостей)"""
    from flask import jsonify
    return jsonify({
        'status': 'online',
        'service': 'bots',
        'timestamp': datetime.now().isoformat(),
        'initialized': system_initialized
    })


def check_port_available(port=5001):
    """Проверка доступности порта"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result != 0
    except:
        return True


def init_bot_service():
    """Инициализация сервиса ботов с State Manager"""
    global bot_system_state, system_initialized
    
    try:
        logger.info("=" * 80)
        logger.info("🚀 ЗАПУСК СИСТЕМЫ INFOBOT (State Manager 2.0)")
        logger.info("=" * 80)
        logger.info(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info(f"🔧 Версия: 2.0 (State Manager Architecture)")
        logger.info("=" * 80)
        
        # 1. Создаем подключение к бирже
        logger.info("[INIT] Шаг 1/4: Инициализация биржи...")
        exchange = ExchangeFactory.create_exchange(
            'BYBIT',
            EXCHANGES['BYBIT']['api_key'],
            EXCHANGES['BYBIT']['api_secret']
        )
        logger.info("[INIT] ✅ Биржа инициализирована")
        
        # 2. Обновляем exchange в существующем BotSystemState
        logger.info("[INIT] Шаг 2/4: Установка биржи в BotSystemState...")
        bot_system_state.exchange_manager = ExchangeManager(exchange)
        logger.info("[INIT] ✅ Биржа установлена в BotSystemState")
        
        # 3. Инициализируем систему
        logger.info("[INIT] Шаг 3/4: Полная инициализация системы...")
        bot_system_state.initialize()
        logger.info("[INIT] ✅ Система инициализирована")
        
        # 3.5. Запускаем загрузку RSI через RSIDataManager
        logger.info("[INIT] 🔄 Запускаем загрузку RSI данных (в фоне)...")
        bot_system_state.rsi_manager.load_all_coins_async(exchange)
        logger.info("[INIT] ✅ Загрузка RSI запущена")
        
        # 4. Запускаем воркеры
        logger.info("[INIT] Шаг 4/4: Запуск воркеров...")
        from bot_engine.workers.state_aware_worker import (
            create_auto_bot_worker,
            create_sync_positions_worker,
            create_cache_update_worker
        )
        
        bot_system_state.worker_manager.start_worker(
            'auto_bot',
            create_auto_bot_worker,
            interval=60
        )
        
        bot_system_state.worker_manager.start_worker(
            'sync_positions',
            create_sync_positions_worker,
            interval=30
        )
        
        bot_system_state.worker_manager.start_worker(
            'cache_update',
            create_cache_update_worker,
            interval=30
        )
        
        logger.info("[INIT] ✅ Воркеры запущены")
        
        logger.info("=" * 80)
        logger.info("✅ СИСТЕМА ПОЛНОСТЬЮ ГОТОВА К РАБОТЕ")
        logger.info("=" * 80)
        logger.info("")
        logger.info("📊 Статистика:")
        logger.info(f"  - Менеджеров: 5")
        logger.info(f"  - Биржа: {exchange.__class__.__name__}")
        try:
            rsi_count = bot_system_state.rsi_manager.get_coins_count()
            logger.info(f"  - RSI данных: {rsi_count}")
        except Exception as e:
            logger.error(f"  - RSI данных: ERROR - {e}")
        
        logger.info(f"  - Ботов: 0 (при запуске)")
        logger.info("=" * 80)
        
        # Устанавливаем флаг инициализации
        system_initialized = True
        logger.info("[INIT] ✅ Флаг system_initialized установлен")
        
        return True
        
    except Exception as e:
        logger.error(f"[INIT] ❌ Ошибка инициализации: {e}", exc_info=True)
        system_initialized = False
        return False


# ==================== Статические маршруты ====================

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


@app.route('/bots')
def bots_page():
    """Страница управления ботами"""
    return render_template('pages/bots.html')


@app.route('/positions')
def positions_page():
    """Страница позиций"""
    return render_template('pages/positions.html')


@app.route('/closed_pnl')
def closed_pnl_page():
    """Страница закрытых позиций"""
    return render_template('pages/closed_pnl.html')


# ==================== Обработчики сигналов ====================

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    global bot_system_state
    
    logger.info("\n" + "=" * 80)
    logger.info("🛑 Получен сигнал остановки (Ctrl+C)")
    logger.info("=" * 80)
    
    try:
        if bot_system_state:
            logger.info("🔄 Выполняем graceful shutdown...")
            bot_system_state.shutdown()
        logger.info("✅ Shutdown завершен")
    except Exception as e:
        logger.error(f"❌ Ошибка при shutdown: {e}")
    finally:
        logger.info("👋 До свидания!")
        # Принудительно завершаем процесс
        os._exit(0)


# ==================== Главная функция ====================

def main():
    """Точка входа приложения"""
    global bot_system_state, system_initialized
    
    try:
        # Проверяем порт
        if not check_port_available(5001):
            logger.warning("⚠️ Порт 5001 занят, пытаемся освободить...")
            
            # Убиваем ТОЛЬКО процесс на порту 5001
            import subprocess
            try:
                # Находим PID процесса на порту 5001
                result = subprocess.run(
                    'netstat -ano | findstr :5001 | findstr LISTENING',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout:
                    # Извлекаем PID из вывода
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            logger.info(f"🔫 Убиваем процесс на порту 5001 (PID: {pid})")
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True, timeout=5)
                            break
            except Exception as e:
                logger.warning(f"⚠️ Не удалось освободить порт: {e}")
            
            time.sleep(2)
            
            if not check_port_available(5001):
                logger.error("❌ Порт 5001 всё ещё занят")
                logger.info("💡 Выполните вручную: netstat -ano | findstr :5001")
                logger.info("💡 Затем: taskkill /F /PID <номер_процесса>")
                return
        
        logger.info("=" * 80)
        logger.info("🌐 Запуск Flask сервера для ботов на 0.0.0.0:5001...")
        logger.info("📋 Этот сервис предоставляет API для торговых ботов")
        logger.info("=" * 80)
        
        # ✅ КРИТИЧЕСКИ ВАЖНО: Создаем минимальный bot_system_state ДО запуска Flask
        # Endpoints будут работать с этим объектом
        logger.info("📌 Создание минимального BotSystemState...")
        bot_system_state = BotSystemState()
        logger.info("✅ Минимальный BotSystemState создан")
        
        # Регистрируем endpoints
        logger.info("📌 Регистрация API endpoints...")
        register_health_endpoints(app, bot_system_state)
        register_bots_endpoints(app, bot_system_state)
        register_config_endpoints(app, bot_system_state)
        register_rsi_endpoints(app, bot_system_state)
        register_positions_endpoints(app, bot_system_state)
        register_mature_endpoints(app, bot_system_state)
        register_system_endpoints(app, bot_system_state)
        logger.info("✅ Все API endpoints зарегистрированы (7 модулей)")
        
        # ✅ Запускаем Flask сервер в отдельном потоке СРАЗУ
        def run_flask_server():
            try:
                logger.info("🚀 Запуск Flask сервера в отдельном потоке...")
                app.run(
                    host='0.0.0.0',
                    port=5001,
                    debug=APP_DEBUG,
                    use_reloader=False,
                    threaded=True
                )
            except Exception as e:
                logger.error(f"❌ Ошибка запуска Flask сервера: {e}")
        
        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        
        # Ждем, пока Flask сервер запустится
        time.sleep(3)
        logger.info("✅ Flask сервер запущен в фоновом режиме")
        
        # ✅ Теперь инициализируем сервис в отдельном потоке
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
        
        # Ждем установки флага system_initialized
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
            logger.error(f"❌ Флаг system_initialized не установлен за {max_wait_time}s - возможны проблемы")
        
        # Теперь настраиваем обработчики сигналов после полной инициализации
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("✅ Обработчики сигналов настроены")
        
        # Основной поток
        logger.info("🔄 Сервис ботов запущен и работает...")
        logger.info("💡 Для остановки нажмите Ctrl+C")
        
        # Ждем завершения Flask сервера (бесконечный цикл)
        try:
            flask_thread.join()
        except KeyboardInterrupt:
            logger.info("\n👋 Получен сигнал остановки (Ctrl+C)")
        
    except KeyboardInterrupt:
        logger.info("\n👋 Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        # Graceful shutdown
        if bot_system_state:
            logger.info("🔄 Graceful shutdown...")
            bot_system_state.shutdown()
        logger.info("🛑 Сервис остановлен")


if __name__ == '__main__':
    main()
