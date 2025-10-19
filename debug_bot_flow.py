#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Пошаговая диагностика входа бота в позицию"""

import requests
import json

print("="*80)
print("ПОШАГОВАЯ ДИАГНОСТИКА ВХОДА БОТА")
print("="*80)

# ШАГ 1: Проверяем данные о монете AWE
print("\n[ШАГ 1] Получаем данные о монете AWE из RSI...")
r = requests.get("http://localhost:5001/api/bots/coins-with-rsi")
data = r.json()
coins = data.get('coins', {})
awe = coins.get('AWE')

if awe:
    print(f"  [OK] AWE найдена")
    print(f"  Сигнал: {awe.get('signal')}")
    print(f"  RSI: {awe.get('rsi6h')}")
    print(f"  Цена: ${awe.get('price')}")
    print(f"  Тренд: {awe.get('trend6h')}")
else:
    print("  [ERROR] AWE не найдена, выход")
    exit(1)

# ШАГ 2: Проверяем существующих ботов
print("\n[ШАГ 2] Проверяем существующих ботов...")
r = requests.get("http://localhost:5001/api/bots/list")
bots = r.json().get('bots', [])
awe_bot = next((b for b in bots if b['symbol'] == 'AWE'), None)

if awe_bot:
    print(f"  [WARN] Бот уже существует, удаляем...")
    requests.delete("http://localhost:5001/api/bots/AWE")
    print("  [OK] Удалили")
else:
    print("  [OK] Бота нет")

# ШАГ 3: Создаем бота
print("\n[ШАГ 3] Создаем бота через API...")
payload = {"symbol": "AWE", "config": {"volume_mode": "usdt", "volume_value": 5}}
print(f"  Отправляем: {json.dumps(payload)}")

r = requests.post("http://localhost:5001/api/bots/create", json=payload)
print(f"  Ответ [{r.status_code}]: {json.dumps(r.json(), indent=2, ensure_ascii=False)[:500]}")

# ШАГ 4: Проверяем результат
print("\n[ШАГ 4] Проверяем результат создания...")
import time
time.sleep(2)

r = requests.get("http://localhost:5001/api/bots/list")
bots = r.json().get('bots', [])
awe_bot = next((b for b in bots if b['symbol'] == 'AWE'), None)

if awe_bot:
    print(f"  [OK] Бот создан!")
    print(f"    - Статус: {awe_bot.get('status')}")
    print(f"    - Entry Price: {awe_bot.get('entry_price')}")
    print(f"    - Position: {awe_bot.get('position')}")
    
    if awe_bot.get('entry_price'):
        print("\n  [SUCCESS] БОТ ВОШЕЛ В ПОЗИЦИЮ!")
    else:
        print("\n  [PROBLEM] БОТ НЕ ВОШЕЛ В ПОЗИЦИЮ")
        print("\n  ВОЗМОЖНЫЕ ПРИЧИНЫ:")
        print("    1. Сигнала нет в момент создания")
        print("    2. Ошибка в exchange.place_order()")
        print("    3. Недостаточно баланса")
        print("    4. Проблема с биржей")
else:
    print("  [ERROR] Бот не создан")

print("\n" + "="*80)

