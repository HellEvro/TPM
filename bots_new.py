#!/usr/bin/env python3
"""
Оптимизированный сервис управления торговыми ботами с State Manager.

Использует модульную архитектуру вместо глобальных переменных.
Порт: 5001
"""

import os
import sys
import signal
import logging
from datetime import datetime
from flask import Flask, render_template
from flask_cors import CORS

# Добавляем путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импорты цветного логирования
from color_logger import setup_color_logging

# Импорты биржи и конфигурации
from exchanges.exchange_factory import ExchangeFactory
from app.config import EXCHANGES, APP_DEBUG

# Импорты State Manager
from bot_engine.state_manager import BotSystemState
from bot_engine.api import register_all_endpoints

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
        logger.info("🚀 ЗАПУСК СИСТЕМЫ INFOBOT (State Manager)")
        logger.info("=" * 80)
        logger.info(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info(f"🔧 Версия: 2.0 (State Manager)")
        logger.info("=" * 80)
        
        # 1. Создаем подключение к бирже
        logger.info("[INIT] Шаг 1: Инициализация биржи...")
        exchange = ExchangeFactory.create_exchange(
            'BYBIT',
            EXCHANGES['BYBIT']['api_key'],
            EXCHANGES['BYBIT']['api_secret']
        )
        logger.info("[INIT] ✅ Биржа инициализирована")
        
        # 2. Создаем BotSystemState
        logger.info("[INIT] Шаг 2: Создание BotSystemState...")
        bot_system_state = BotSystemState(exchange)
        logger.info("[INIT] ✅ BotSystemState создан")
        
        # 3. Инициализируем систему
        logger.info("[INIT] Шаг 3: Полная инициализация системы...")
        bot_system_state.initialize()
        logger.info("[INIT] ✅ Система инициализирована")
        
        # 4. Регистрируем API endpoints
        logger.info("[INIT] Шаг 4: Регистрация API endpoints...")
        
        # Создаем словарь для совместимости со старыми endpoints
        state_dict = {
            'state': bot_system_state,
            'get_state_func': lambda: {
                'exchange': bot_system_state.exchange_manager.get_exchange_info(),
                'bots': bot_system_state.bot_manager.get_global_stats(),
                'rsi': bot_system_state.rsi_manager.get_info(),
                'config': bot_system_state.config_manager.get_info()
            }
        }
        
        register_all_endpoints(app, state_dict)
        logger.info("[INIT] ✅ API endpoints зарегистрированы")
        
        logger.info("=" * 80)
        logger.info("✅ СИСТЕМА ПОЛНОСТЬЮ ГОТОВА К РАБОТЕ")
        logger.info("=" * 80)
        
        return bot_system_state
        
    except Exception as e:
        logger.error(f"[INIT] ❌ Ошибка инициализации: {e}", exc_info=True)
        raise


# Статические маршруты
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


def main():
    """Точка входа приложения"""
    global bot_system_state
    
    try:
        # Проверяем порт
        if not check_port_available(5001):
            logger.error("❌ Порт 5001 занят другим процессом!")
            logger.info("💡 Остановите другой процесс или измените порт")
            return
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Инициализируем сервис
        bot_system_state = init_bot_service()
        
        # Выводим информацию о доступных endpoints
        logger.info("=" * 80)
        logger.info("🌐 ДОСТУПНЫЕ API ENDPOINTS:")
        logger.info("=" * 80)
        logger.info("  GET  /health                    - Проверка статуса")
        logger.info("  GET  /api/status                - Статус системы")
        logger.info("  GET  /api/bots/list             - Список ботов")
        logger.info("  POST /api/bots/create           - Создать бота")
        logger.info("  POST /api/bots/start            - Запустить бота")
        logger.info("  POST /api/bots/stop             - Остановить бота")
        logger.info("  ... и другие")
        logger.info("=" * 80)
        
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
            bot_system_state.shutdown()
        logger.info("🛑 Сервис остановлен")


if __name__ == '__main__':
    # Проверяем и останавливаем существующие процессы
    from bots import check_and_stop_existing_bots_processes
    
    if not check_and_stop_existing_bots_processes():
        sys.exit(1)
    
    # Запускаем основной сервис
    main()

