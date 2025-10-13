"""
WORKING VERSION - на основе старого кода с минимальными изменениями
"""

import os
import sys
import time
import signal
import threading
import atexit
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импорты
from color_logger import setup_color_logging
from exchanges.exchange_factory import ExchangeFactory
from app.config import EXCHANGES

# Настройка логирования
logger = setup_color_logging()

# Flask приложение
app = Flask(__name__)

# Глобальные переменные (как в старом коде)
exchange = None
coins_rsi_data = {
    'coins': {},
    'total_coins': 0,
    'successful_coins': 0,
    'failed_coins': 0,
    'update_in_progress': False,
    'last_update': None
}
rsi_data_lock = threading.Lock()

# Флаги состояния
system_initialized = False
graceful_shutdown = False

# ==================== API ENDPOINTS ====================

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def api_status():
    """Статус сервиса"""
    return jsonify({
        'service': 'bots',
        'status': 'online',
        'initialized': system_initialized,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/bots/coins-with-rsi', methods=['GET'])
def get_coins_with_rsi():
    """Получить все монеты с RSI данными"""
    try:
        with rsi_data_lock:
            if coins_rsi_data['update_in_progress']:
                return jsonify({
                    'success': True,
                    'coins': coins_rsi_data['coins'],
                    'update_in_progress': True,
                    'total_coins': coins_rsi_data['total_coins'],
                    'successful_coins': coins_rsi_data['successful_coins'],
                    'last_update': coins_rsi_data['last_update']
                })
            
            return jsonify({
                'success': True,
                'coins': coins_rsi_data['coins'],
                'update_in_progress': False,
                'total_coins': coins_rsi_data['total_coins'],
                'successful_coins': coins_rsi_data['successful_coins'],
                'last_update': coins_rsi_data['last_update']
            })
            
    except Exception as e:
        logger.error(f"[API] Ошибка получения RSI данных: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bots/auto-bot', methods=['GET'])
def get_auto_bot_status():
    """Статус Auto Bot"""
    return jsonify({
        'success': True,
        'enabled': True  # Пока всегда включен
    })

@app.route('/api/bots/account-info', methods=['GET'])
def get_account_info():
    """Информация об аккаунте"""
    try:
        if not exchange:
            return jsonify({
                'success': False,
                'error': 'Exchange not initialized'
            }), 500
            
        # Получаем информацию об аккаунте
        account_info = exchange.get_unified_account_info()
        
        return jsonify({
            'success': True,
            'balance': account_info.get('balance', 0),
            'unrealized_pnl': account_info.get('unrealized_pnl', 0),
            'open_positions': account_info.get('open_positions', 0)
        })
        
    except Exception as e:
        logger.error(f"[API] Ошибка получения информации об аккаунте: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== RSI LOADING ====================

def get_coin_rsi_data(symbol, exchange_obj=None):
    """Получить RSI данные для монеты"""
    try:
        if not exchange_obj:
            exchange_obj = exchange
            
        if not exchange_obj:
            logger.error(f"[RSI] Биржа не инициализирована для {symbol}")
            return None
            
        # Получаем свечи
        candles = exchange_obj.get_klines(symbol, interval='6h', limit=100)
        if not candles:
            logger.warning(f"[RSI] Нет данных свечей для {symbol}")
            return None
            
        # Простой расчет RSI (упрощенная версия)
        prices = [float(candle['close']) for candle in candles]
        
        if len(prices) < 14:
            return None
            
        # RSI расчет
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < 14:
            return None
            
        # Средние значения
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Определяем сигнал
        if rsi <= 30:
            signal = 'ENTER_LONG'
        elif rsi >= 70:
            signal = 'ENTER_SHORT'
        else:
            signal = 'NEUTRAL'
            
        return {
            'symbol': symbol,
            'rsi': round(rsi, 2),
            'signal': signal,
            'price': prices[-1],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[RSI] Ошибка получения данных для {symbol}: {e}")
        return None

def load_all_coins_rsi():
    """Загружает RSI 6H для всех доступных монет"""
    global coins_rsi_data
    
    try:
        with rsi_data_lock:
            if coins_rsi_data['update_in_progress']:
                logger.info("[RSI] Обновление RSI уже выполняется...")
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
        
        # Загружаем RSI данные
        batch_size = 10  # Небольшие пакеты для стабильности
        
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i+batch_size]
            logger.info(f"[RSI] Обрабатываем пакет {i//batch_size + 1}/{(len(pairs) + batch_size - 1)//batch_size}")
            
            for symbol in batch:
                try:
                    coin_data = get_coin_rsi_data(symbol)
                    if coin_data:
                        with rsi_data_lock:
                            coins_rsi_data['coins'][symbol] = coin_data
                            coins_rsi_data['successful_coins'] += 1
                    else:
                        with rsi_data_lock:
                            coins_rsi_data['failed_coins'] += 1
                            
                    # Небольшая задержка между запросами
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.warning(f"[RSI] Ошибка для {symbol}: {e}")
                    with rsi_data_lock:
                        coins_rsi_data['failed_coins'] += 1
            
            # Задержка между пакетами
            time.sleep(0.5)
        
        # Завершение
        with rsi_data_lock:
            coins_rsi_data['update_in_progress'] = False
            coins_rsi_data['last_update'] = datetime.now().isoformat()
        
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
        
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Ошибка загрузки RSI данных: {str(e)}")
        with rsi_data_lock:
            coins_rsi_data['update_in_progress'] = False
        return False

# ==================== INITIALIZATION ====================

def init_bot_service():
    """Инициализация сервиса ботов"""
    global exchange, system_initialized
    
    try:
        logger.info("=" * 80)
        logger.info("🚀 ЗАПУСК СИСТЕМЫ INFOBOT (WORKING VERSION)")
        logger.info("=" * 80)
        logger.info(f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info(f"🔧 Версия: WORKING")
        logger.info("=" * 80)
        
        # 1. Инициализируем биржу
        logger.info("[INIT] Шаг 1/3: Инициализация биржи...")
        exchange = ExchangeFactory.create_exchange(
            'BYBIT',
            EXCHANGES['BYBIT']['api_key'],
            EXCHANGES['BYBIT']['api_secret'],
            EXCHANGES['BYBIT']['testnet']
        )
        logger.info("[INIT] ✅ Биржа инициализирована")
        
        # 2. Запускаем загрузку RSI данных в фоне
        logger.info("[INIT] Шаг 2/3: Запуск загрузки RSI данных...")
        rsi_load_thread = threading.Thread(target=load_all_coins_rsi, daemon=True)
        rsi_load_thread.start()
        logger.info("[INIT] ✅ Загрузка RSI запущена в фоновом потоке")
        
        # 3. Завершение инициализации
        logger.info("[INIT] Шаг 3/3: Завершение инициализации...")
        system_initialized = True
        logger.info("[INIT] ✅ Система полностью инициализирована!")
        
        return True
        
    except Exception as e:
        logger.error(f"[INIT] ❌ Ошибка инициализации: {e}", exc_info=True)
        system_initialized = False
        return False

# ==================== SIGNAL HANDLERS ====================

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    global graceful_shutdown
    
    logger.info("\n" + "=" * 80)
    logger.info("🛑 Получен сигнал остановки (Ctrl+C)")
    logger.info("=" * 80)
    
    graceful_shutdown = True
    logger.info("👋 До свидания!")
    os._exit(0)

# ==================== MAIN ====================

def main():
    """Главная функция"""
    try:
        # Убиваем процесс на порту 5001
        try:
            result = subprocess.run(
                'netstat -ano | findstr :5001 | findstr LISTENING',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout:
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
        
        logger.info("=" * 80)
        logger.info("🌐 Запуск Flask сервера для ботов на 0.0.0.0:5001...")
        logger.info("📋 Этот сервис предоставляет API для торговых ботов")
        logger.info("=" * 80)
        
        # Настраиваем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Запускаем Flask сервер в отдельном потоке СРАЗУ
        def run_flask_server():
            try:
                logger.info("🚀 Запуск Flask сервера в отдельном потоке...")
                app.run(
                    host='0.0.0.0',
                    port=5001,
                    debug=False,
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
                return False
        
        service_thread = threading.Thread(target=init_service_async, daemon=True)
        service_thread.start()
        
        # Ждем завершения инициализации
        while not system_initialized and not graceful_shutdown:
            time.sleep(1)
        
        if system_initialized:
            logger.info("✅ Сервис ботов запущен и работает...")
            logger.info("💡 Для остановки нажмите Ctrl+C")
            
            # Основной цикл
            while not graceful_shutdown:
                time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("🛑 Сервис остановлен")

if __name__ == "__main__":
    import subprocess
    main()
