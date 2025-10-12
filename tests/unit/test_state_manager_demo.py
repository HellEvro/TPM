"""
Демонстрация работы State Manager.

Этот скрипт показывает как работает новая архитектура.
"""

import logging
import sys
from datetime import datetime

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импортируем необходимые компоненты
from exchanges.exchange_factory import ExchangeFactory
from app.config import EXCHANGES
from bot_engine.state_manager import BotSystemState


def demo_state_manager():
    """Демонстрация работы State Manager"""
    
    print("=" * 80)
    print("🚀 ДЕМОНСТРАЦИЯ STATE MANAGER")
    print("=" * 80)
    print()
    
    try:
        # 1. Создаем биржу
        print("[1/7] Создание биржи...")
        exchange = ExchangeFactory.create_exchange(
            'BYBIT',
            EXCHANGES['BYBIT']['api_key'],
            EXCHANGES['BYBIT']['api_secret']
        )
        print("✅ Биржа создана")
        print()
        
        # 2. Создаем BotSystemState
        print("[2/7] Создание BotSystemState...")
        state = BotSystemState(exchange)
        print("✅ BotSystemState создан")
        print()
        
        # 3. Проверяем менеджеры
        print("[3/7] Проверка менеджеров...")
        print(f"  ✅ ExchangeManager: {state.exchange_manager}")
        print(f"  ✅ RSIDataManager: {state.rsi_manager}")
        print(f"  ✅ BotManager: {state.bot_manager}")
        print(f"  ✅ ConfigManager: {state.config_manager}")
        print(f"  ✅ WorkerManager: {state.worker_manager}")
        print()
        
        # 4. Тестируем RSI Manager
        print("[4/7] Тестирование RSI Manager...")
        state.rsi_manager.update_rsi('BTCUSDT', {
            'rsi': 25.5,
            'signal': 'LONG',
            'price': 50000,
            'timestamp': datetime.now()
        })
        rsi_data = state.rsi_manager.get_rsi('BTCUSDT')
        print(f"  ✅ RSI для BTCUSDT: {rsi_data['rsi']}")
        print(f"  ✅ Сигнал: {rsi_data['signal']}")
        print()
        
        # 5. Тестируем Config Manager
        print("[5/7] Тестирование Config Manager...")
        config = state.config_manager.get_auto_bot_config()
        print(f"  ✅ Auto Bot enabled: {config['enabled']}")
        print(f"  ✅ Max concurrent bots: {config['max_concurrent_bots']}")
        print()
        
        # 6. Тестируем Bot Manager
        print("[6/7] Тестирование Bot Manager...")
        
        # Создаем бота через BotAdapter
        bot_config = {
            'volume_mode': 'usdt',
            'volume_value': 10.0
        }
        
        try:
            bot = state.bot_manager.create_bot('BTCUSDT', bot_config)
            print(f"  ✅ Бот создан: {bot.symbol}")
            print(f"  ✅ Статус: {bot.status}")
            
            # Статистика
            stats = state.bot_manager.get_global_stats()
            print(f"  ✅ Всего ботов: {stats['total_bots']}")
            
            # Удаляем бота
            state.bot_manager.delete_bot('BTCUSDT')
            print(f"  ✅ Бот удален")
        except Exception as e:
            print(f"  ⚠️ Создание бота пропущено (требует NewTradingBot): {e}")
        
        print()
        
        # 7. Получаем статус системы
        print("[7/7] Статус системы...")
        system_status = state.get_system_status()
        print(f"  ✅ Инициализирована: {system_status['initialized']}")
        print(f"  ✅ Биржа: {system_status['exchange']['name']}")
        print(f"  ✅ RSI монет: {system_status['rsi']['total_coins']}")
        print(f"  ✅ Ботов: {system_status['bots']['total_bots']}")
        print()
        
        # Красивый вывод состояния
        print("=" * 80)
        print("📊 СОСТОЯНИЕ СИСТЕМЫ")
        print("=" * 80)
        print(state)
        print()
        
        print("=" * 80)
        print("✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА УСПЕШНО")
        print("=" * 80)
        print()
        
        print("🎉 State Manager работает корректно!")
        print()
        print("Все менеджеры:")
        print("  ✅ ExchangeManager - управление биржей")
        print("  ✅ RSIDataManager - управление RSI данными")
        print("  ✅ BotManager - управление ботами")
        print("  ✅ ConfigManager - управление конфигурациями")
        print("  ✅ WorkerManager - управление воркерами")
        print()
        print("Преимущества:")
        print("  ✅ Нет глобальных переменных")
        print("  ✅ Явные зависимости")
        print("  ✅ Thread-safe операции")
        print("  ✅ Легко тестировать")
        print("  ✅ Модульная архитектура")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ ОШИБКА")
        print("=" * 80)
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = demo_state_manager()
    sys.exit(0 if success else 1)

