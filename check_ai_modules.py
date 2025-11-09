#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт проверки установки AI модулей
"""

import sys
import os

# Настройка кодировки для Windows
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

print("=" * 80)
print("Проверка установки AI модулей")
print("=" * 80)

# Проверка основных зависимостей
modules_to_check = [
    ('numpy', 'numpy'),
    ('pandas', 'pandas'),
    ('sklearn', 'scikit-learn'),
    ('joblib', 'joblib'),
    ('requests', 'requests'),
]

print("\n1. Проверка основных зависимостей:")
all_ok = True
for module_name, package_name in modules_to_check:
    try:
        mod = __import__(module_name)
        version = getattr(mod, '__version__', 'unknown')
        print(f"   ✓ {package_name}: {version}")
    except ImportError:
        print(f"   ✗ {package_name}: НЕ УСТАНОВЛЕН")
        all_ok = False

# Проверка AI модулей
print("\n2. Проверка AI модулей:")
ai_modules = [
    ('bot_engine.ai.ai_data_collector', 'AIDataCollector'),
    ('bot_engine.ai.ai_trainer', 'AITrainer'),
    ('bot_engine.ai.ai_backtester_new', 'AIBacktester'),
    ('bot_engine.ai.ai_strategy_optimizer', 'AIStrategyOptimizer'),
    ('bot_engine.ai.ai_bot_manager', 'AIBotManager'),
    ('bot_engine.ai.ai_integration', 'ai_integration'),
]

for module_path, module_name in ai_modules:
    try:
        __import__(module_path)
        print(f"   ✓ {module_name}")
    except ImportError as e:
        print(f"   ✗ {module_name}: {e}")
        all_ok = False

# Проверка главного модуля
print("\n3. Проверка главного модуля:")
try:
    from ai import get_ai_system
    ai_system = get_ai_system()
    print(f"   ✓ ai.py: OK")
    print(f"   ✓ AI система инициализирована")
    
    # Проверка статуса
    status = ai_system.get_status()
    print(f"\n4. Статус AI системы:")
    print(f"   - Запущена: {status.get('running', False)}")
    print(f"   - Включена: {status.get('enabled', False)}")
    print(f"   - Модули:")
    for module, available in status.get('modules', {}).items():
        status_symbol = "✓" if available else "✗"
        print(f"     {status_symbol} {module}: {available}")
    
except Exception as e:
    print(f"   ✗ ai.py: {e}")
    all_ok = False

print("\n" + "=" * 80)
if all_ok:
    print("✓ Все модули установлены и работают!")
else:
    print("✗ Есть проблемы с установкой модулей")
print("=" * 80)

