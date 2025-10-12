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

# Импорты новых API endpoints
from bot_engine.api.endpoints_health_new import register_health_endpoints
from bot_engine.api.endpoints_bots_new import register_bots_endpoints
from bot_engine.api.endpoints_config_new import register_config_endpoints
from bot_engine.api.endpoints_rsi_new import register_rsi_endpoints

# Настройка логирования
logger = setup_color_logging()

# Создаем Flask приложение
app = Flask(__name__)
CORS(app)

# Глобальный state (единственная "глобальная" переменная)
bot_system_state = None


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
    global bot_system_state
    
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
        
        # 2. Создаем BotSystemState
        logger.info("[INIT] Шаг 2/4: Создание BotSystemState...")
        bot_system_state = BotSystemState(exchange)
        logger.info("[INIT] ✅ BotSystemState создан")
        
        # 3. Инициализируем систему
        logger.info("[INIT] Шаг 3/4: Полная инициализация системы...")
        bot_system_state.initialize()
        logger.info("[INIT] ✅ Система инициализирована")
        
        # 4. Регистрируем API endpoints
        logger.info("[INIT] Шаг 4/4: Регистрация API endpoints...")
        register_health_endpoints(app, bot_system_state)
        register_bots_endpoints(app, bot_system_state)
        register_config_endpoints(app, bot_system_state)
        register_rsi_endpoints(app, bot_system_state)
        logger.info("[INIT] ✅ API endpoints зарегистрированы")
        
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
        
        # ПРИМЕЧАНИЕ: Не вызываем get_bots_count() так как это может вызвать deadlock
        # из-за того что воркеры уже запущены и могут держать блокировку
        logger.info(f"  - Ботов: 0 (при запуске)")
        
        logger.info("=" * 80)
        logger.info("[INIT] ✅ Возвращаем bot_system_state")
        
        return bot_system_state
        
    except Exception as e:
        logger.error(f"[INIT] ❌ Ошибка инициализации: {e}", exc_info=True)
        raise


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
    
    logger.info("=" * 80)
    logger.info("🛑 Получен сигнал остановки")
    logger.info("=" * 80)
    
    if bot_system_state:
        bot_system_state.shutdown()
    
    logger.info("👋 До свидания!")
    sys.exit(0)


# ==================== Главная функция ====================

def main():
    """Точка входа приложения"""
    global bot_system_state
    
    try:
        # Проверяем порт
        if not check_port_available(5001):
            logger.warning("⚠️ Порт 5001 занят, пытаемся освободить...")
            os.system("taskkill /F /IM python.exe /FI \"WINDOWTITLE eq *\" 2>nul")
            import time
            time.sleep(2)
            
            if not check_port_available(5001):
                logger.error("❌ Не удалось освободить порт 5001")
                logger.info("💡 Остановите другой процесс вручную")
                return
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Инициализируем сервис
        logger.info("[MAIN] 🚀 Инициализация сервиса...")
        bot_system_state = init_bot_service()
        logger.info("[MAIN] ✅ Сервис успешно инициализирован")
        
        # Выводим доступные endpoints
        logger.info("=" * 80)
        logger.info("🌐 ДОСТУПНЫЕ API ENDPOINTS:")
        logger.info("=" * 80)
        logger.info("  GET  /health                    - Проверка статуса")
        logger.info("  GET  /api/status                - Полный статус системы")
        logger.info("")
        logger.info("  GET  /api/bots/list             - Список ботов")
        logger.info("  POST /api/bots/create           - Создать бота")
        logger.info("  POST /api/bots/start            - Запустить бота")
        logger.info("  POST /api/bots/stop             - Остановить бота")
        logger.info("  POST /api/bots/pause            - Приостановить бота")
        logger.info("  POST /api/bots/delete           - Удалить бота")
        logger.info("  POST /api/bots/close-position   - Закрыть позицию")
        logger.info("")
        logger.info("  GET  /api/bots/auto-bot         - Конфигурация Auto Bot")
        logger.info("  POST /api/bots/auto-bot         - Обновить конфигурацию")
        logger.info("  POST /api/bots/auto-bot/restore - Восстановить defaults")
        logger.info("")
        logger.info("  GET  /api/bots/coins-with-rsi   - RSI всех монет")
        logger.info("  POST /api/bots/load-rsi         - Загрузить RSI")
        logger.info("  POST /api/bots/force-rsi-update - Принудительное обновление")
        logger.info("")
        logger.info("  GET  /api/bots/account-info     - Информация о счете")
        logger.info("=" * 80)
        
        # Запускаем воркеры перед Flask (они в daemon потоках - не блокируют)
        logger.info("🚀 Запуск воркеров...")
        
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
        
        logger.info("✅ Воркеры запущены")
        
        # Запускаем Flask сервер
        logger.info("🚀 Запуск Flask сервера на порту 5001...")
        app.run(
            host='0.0.0.0',
            port=5001,
            debug=APP_DEBUG,
            use_reloader=False,
            threaded=True
        )
        
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

