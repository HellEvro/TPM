#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диагностический скрипт для проверки работы AI обучения

Проверяет:
1. Инициализацию AITrainer
2. Загрузку сделок из БД
3. Количество сделок для обучения
4. Доступность моделей
"""

import sys
import os
from pathlib import Path

# Настройка кодировки для Windows консоли
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 80)
print("ДИАГНОСТИКА AI ОБУЧЕНИЯ")
print("=" * 80)

# 1. Проверка инициализации AITrainer
print("\n[1] Проверка инициализации AITrainer...")
try:
    from bot_engine.ai.ai_trainer import AITrainer
    trainer = AITrainer()
    print("   [OK] AITrainer успешно инициализирован")
except Exception as e:
    print(f"   [ERROR] Ошибка инициализации AITrainer: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. Проверка загрузки сделок
print("\n[2] Проверка загрузки сделок из БД...")
try:
    trades_count = trainer.get_trades_count()
    print(f"   [OK] Количество сделок для обучения: {trades_count}")
    
    if trades_count == 0:
        print("   [WARNING] ВНИМАНИЕ: Нет сделок для обучения!")
        print("   [INFO] Проверьте:")
        print("      - Есть ли сделки в bots_data.db -> bot_trades_history")
        print("      - Есть ли сделки в ai_data.db -> bot_trades, exchange_trades")
    elif trades_count < 10:
        print(f"   [WARNING] Мало сделок для обучения (нужно >= 10, есть {trades_count})")
    else:
        print(f"   [OK] Достаточно сделок для обучения ({trades_count} >= 10)")
except Exception as e:
    print(f"   [ERROR] Ошибка загрузки сделок: {e}")
    import traceback
    traceback.print_exc()

# 3. Проверка загрузки истории напрямую
print("\n[3] Проверка _load_history_data()...")
try:
    trades = trainer._load_history_data()
    print(f"   [OK] Загружено {len(trades)} сделок через _load_history_data()")
    
    if trades:
        sample = trades[0]
        print(f"   [INFO] Пример сделки:")
        print(f"      - Symbol: {sample.get('symbol')}")
        print(f"      - PnL: {sample.get('pnl')}")
        print(f"      - RSI: {sample.get('rsi')}")
        print(f"      - Trend: {sample.get('trend')}")
        print(f"      - Source: {sample.get('decision_source', 'UNKNOWN')}")
except Exception as e:
    print(f"   [ERROR] Ошибка _load_history_data(): {e}")
    import traceback
    traceback.print_exc()

# 4. Проверка БД напрямую
print("\n[4] Проверка БД напрямую...")
try:
    from bot_engine.ai.ai_database import get_ai_database
    ai_db = get_ai_database()
    
    # Проверяем сделки из разных источников
    db_trades = ai_db.get_trades_for_training(
        include_simulated=False,
        include_real=True,
        include_exchange=True,
        min_trades=0,
        limit=None
    )
    print(f"   [OK] get_trades_for_training(): {len(db_trades)} сделок")
    
    # Проверяем bots_data.db
    from bot_engine.bots_database import get_bots_database
    bots_db = get_bots_database()
    bots_trades = bots_db.get_bot_trades_history(
        status='CLOSED',
        limit=None
    )
    print(f"   [OK] bots_data.db -> bot_trades_history: {len(bots_trades)} сделок")
    
except Exception as e:
    print(f"   [ERROR] Ошибка проверки БД: {e}")
    import traceback
    traceback.print_exc()

# 5. Проверка моделей
print("\n[5] Проверка моделей...")
try:
    models_dir = Path('data/ai/models')
    if not models_dir.exists():
        print(f"   [WARNING] Директория моделей не найдена: {models_dir}")
    else:
        signal_model = models_dir / 'signal_predictor.pkl'
        profit_model = models_dir / 'profit_predictor.pkl'
        
        if signal_model.exists():
            print(f"   [OK] Модель сигналов найдена: {signal_model}")
        else:
            print(f"   [WARNING] Модель сигналов не найдена: {signal_model}")
        
        if profit_model.exists():
            print(f"   [OK] Модель прибыли найдена: {profit_model}")
        else:
            print(f"   [WARNING] Модель прибыли не найдена: {profit_model}")
except Exception as e:
    print(f"   [ERROR] Ошибка проверки моделей: {e}")

# 6. Проверка лицензии (если доступна)
print("\n[6] Проверка лицензии...")
try:
    # Пытаемся импортировать через sys.path
    import importlib.util
    license_path = PROJECT_ROOT / 'license_generator' / 'source' / '@source' / 'ai_launcher_source.py'
    if license_path.exists():
        spec = importlib.util.spec_from_file_location("ai_launcher_source", str(license_path))
        ai_launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ai_launcher)
        
        license_status = ai_launcher.ensure_license_available()
        if license_status.get('valid'):
            print("   [OK] Лицензия валидна")
            features = license_status.get('info', {}).get('features', {})
            if features.get('ai_training'):
                print("   [OK] Функция 'ai_training' включена в лицензию")
            else:
                print("   [WARNING] Функция 'ai_training' НЕ включена в лицензию")
        else:
            print("   [WARNING] Лицензия невалидна или отсутствует")
    else:
        print(f"   [WARNING] Файл лицензии не найден: {license_path}")
except Exception as e:
    print(f"   [WARNING] Не удалось проверить лицензию: {e}")

print("\n" + "=" * 80)
print("[OK] ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 80)

