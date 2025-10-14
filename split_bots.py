#!/usr/bin/env python3
"""
Скрипт для разбиения bots.py на модули
"""

import re

# Читаем весь файл
with open('bots.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

print(f"Всего строк: {len(lines)}")

# Определяем границы секций
# Функция для поиска функций и классов
def find_functions_and_classes():
    """Находит все функции и классы с их границами"""
    items = []
    current_item = None
    indent_stack = []
    
    for i, line in enumerate(lines, 1):
        # Пропускаем пустые строки и комментарии
        if not line.strip() or line.strip().startswith('#'):
            continue
            
        # Определяем уровень отступа
        indent = len(line) - len(line.lstrip())
        
        # Ищем определения функций и классов
        if re.match(r'^(def |class )', line):
            # Если есть текущий item, закрываем его
            if current_item:
                current_item['end_line'] = i - 1
                items.append(current_item)
            
            # Определяем тип (функция или класс)
            if line.startswith('def '):
                item_type = 'function'
                match = re.match(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
            else:
                item_type = 'class'
                match = re.match(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
            
            if match:
                name = match.group(1)
                current_item = {
                    'type': item_type,
                    'name': name,
                    'start_line': i,
                    'indent': indent
                }
    
    # Закрываем последний item
    if current_item:
        current_item['end_line'] = len(lines)
        items.append(current_item)
    
    return items

items = find_functions_and_classes()

# Группируем функции по логическим блокам
rsi_ema_functions = ['calculate_rsi', 'calculate_rsi_history', 'calculate_ema']
maturity_functions = [
    'load_mature_coins_storage', 'save_mature_coins_storage',
    'is_coin_mature_stored', 'add_mature_coin_to_storage',
    'remove_mature_coin_from_storage', 'update_mature_coin_verification',
    'check_coin_maturity_with_storage', 'check_coin_maturity'
]
optimal_ema_functions = [
    'load_optimal_ema_data', 'get_optimal_ema_periods', 'update_optimal_ema_data',
    'save_optimal_ema_periods'
]
trend_functions = ['analyze_trend_6h', 'perform_enhanced_rsi_analysis']
filter_functions = ['check_rsi_time_filter', 'check_exit_scam_filter', 'check_no_existing_position']
signal_functions = [
    'get_coin_rsi_data', 'load_all_coins_rsi', 'get_effective_signal',
    'process_auto_bot_signals', 'process_trading_signals_for_all_bots',
    'check_new_autobot_filters', 'check_coin_maturity_stored_or_verify',
    'check_auto_bot_filters', 'test_exit_scam_filter', 'test_rsi_time_filter'
]
bot_class = ['NewTradingBot']
cache_functions = [
    'get_rsi_cache', 'save_rsi_cache', 'load_rsi_cache',
    'save_default_config', 'load_default_config', 'restore_default_config',
    'update_process_state', 'save_process_state', 'load_process_state',
    'save_system_config', 'load_system_config',
    'save_bots_state', 'save_auto_bot_config', 'load_bots_state'
]
sync_functions = [
    'update_bots_cache_data', 'update_bot_positions_status',
    'get_exchange_positions', 'compare_bot_and_exchange_positions',
    'sync_positions_with_exchange', 'check_active_orders',
    'cleanup_inactive_bots', 'remove_mature_coins',
    'check_trading_rules_activation', 'check_missing_stop_losses',
    'check_startup_position_conflicts', 'sync_bots_with_exchange'
]
worker_functions = ['auto_save_worker', 'auto_bot_worker']
init_functions = [
    'init_bot_service', 'start_async_processor', 'stop_async_processor',
    'create_bot', 'process_trading_signals_on_candle_close',
    'delayed_exchange_init', 'init_exchange_sync', 'ensure_exchange_initialized'
]

# Выводим статистику
print(f"\nВсего найдено элементов: {len(items)}")
print(f"Функций: {len([i for i in items if i['type'] == 'function'])}")
print(f"Классов: {len([i for i in items if i['type'] == 'class'])}")

# Показываем группировку
groups = {
    'RSI/EMA': rsi_ema_functions,
    'Maturity': maturity_functions,
    'Optimal EMA': optimal_ema_functions,
    'Trend': trend_functions,
    'Filters': filter_functions,
    'Signals': signal_functions,
    'Bot Class': bot_class,
    'Cache': cache_functions,
    'Sync': sync_functions,
    'Workers': worker_functions,
    'Init': init_functions
}

print("\n=== ГРУППИРОВКА ФУНКЦИЙ ===")
for group_name, func_list in groups.items():
    found = [item for item in items if item['name'] in func_list]
    print(f"\n{group_name}: {len(found)}/{len(func_list)}")
    for item in found[:3]:  # Показываем первые 3
        print(f"  - {item['name']} (строки {item['start_line']}-{item['end_line']})")

# Находим API endpoints (все функции после строки 5280)
api_items = [item for item in items if item['start_line'] > 5280 and item['type'] == 'function']
print(f"\nAPI Endpoints: {len(api_items)}")

