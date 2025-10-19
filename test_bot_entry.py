#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Тестирование входа бота в позицию"""

import requests
import json
import time

print("=" * 80)
print("ТЕСТИРОВАНИЕ ВХОДА БОТА В ПОЗИЦИЮ")
print("=" * 80)

# 1. Получаем данные о монете AWE
print("\n[1] Получаем данные о монете AWE...")
response = requests.get("http://localhost:5001/api/bots/coins-with-rsi")
if response.status_code == 200:
    data = response.json()
    print(f"   [DEBUG] Ключи в ответе: {list(data.keys())}")
    coins_data = data.get('coins', {})
    print(f"   [DEBUG] Тип coins: {type(coins_data)}")
    
    if isinstance(coins_data, dict):
        print(f"   [DEBUG] Количество монет в словаре: {len(coins_data)}")
        print(f"   [DEBUG] Первые 5 ключей: {list(coins_data.keys())[:5]}")
        # coins - это словарь {symbol: data}, ищем AWE
        awe_coin = coins_data.get('AWE')
    elif isinstance(coins_data, list):
        print(f"   [DEBUG] Количество монет в списке: {len(coins_data)}")
        awe_coin = next((c for c in coins_data if isinstance(c, dict) and c.get('symbol') == 'AWE'), None)
    else:
        print(f"   [DEBUG] coins неизвестного типа")
        awe_coin = None
    
    if awe_coin:
        print(f"   [OK] AWE найдена")
        print(f"   Сигнал: {awe_coin.get('signal')}")
        print(f"   RSI: {awe_coin.get('rsi6h')}")
        print(f"   Цена: ${awe_coin.get('price')}")
    else:
        print("   [ERROR] AWE не найдена")
        exit(1)
else:
    print(f"   [ERROR] Ошибка запроса: {response.status_code}")
    exit(1)

# 2. Проверяем существующих ботов
print("\n[2] Проверяем существующих ботов...")
response = requests.get("http://localhost:5001/api/bots/list")
if response.status_code == 200:
    data = response.json()
    bots = data.get('bots', [])
    awe_bot = next((b for b in bots if b['symbol'] == 'AWE'), None)
    
    if awe_bot:
        print(f"   [WARN] Бот AWE уже существует")
        print(f"   Статус: {awe_bot.get('status')}")
        print(f"   Entry Price: {awe_bot.get('entry_price')}")
        print(f"   Position: {awe_bot.get('position')}")
        
        # Удаляем бота
        print("\n   [DELETE] Удаляем существующего бота...")
        del_response = requests.delete(f"http://localhost:5001/api/bots/AWE")
        if del_response.status_code == 200:
            print("   [OK] Бот удален")
            time.sleep(2)  # Ждем сохранения
        else:
            print(f"   [ERROR] Не удалось удалить: {del_response.status_code}")
    else:
        print("   [OK] Нет существующего бота AWE")

# 3. Создаем нового бота
print("\n[3] Создаем нового бота для AWE...")
create_payload = {
    "symbol": "AWE",
    "config": {
        "volume_mode": "usdt",
        "volume_value": 5
    }
}

response = requests.post(
    "http://localhost:5001/api/bots/create",
    json=create_payload,
    headers={"Content-Type": "application/json"}
)

print(f"   [RESPONSE] Статус ответа: {response.status_code}")
print(f"   Ответ сервера:")
try:
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
except:
    print(f"   [ERROR] Не JSON: {response.text}")

# 4. Ждем немного и проверяем состояние
print("\n[4] Ждем 3 секунды и проверяем состояние бота...")
time.sleep(3)

response = requests.get("http://localhost:5001/api/bots/list")
if response.status_code == 200:
    data = response.json()
    bots = data.get('bots', [])
    awe_bot = next((b for b in bots if b['symbol'] == 'AWE'), None)
    
    if awe_bot:
        print(f"   [OK] Бот создан")
        print(f"   Статус: {awe_bot.get('status')}")
        print(f"   Entry Price: {awe_bot.get('entry_price')}")
        print(f"   Position: {awe_bot.get('position')}")
        print(f"   Volume: {awe_bot.get('volume_value')} {awe_bot.get('volume_mode')}")
        
        if awe_bot.get('entry_price'):
            print("\n   [SUCCESS] УСПЕХ! Бот вошел в позицию!")
        else:
            print("\n   [PROBLEM] ПРОБЛЕМА: Бот создан, но НЕ ВОШЕЛ в позицию")
    else:
        print("   [ERROR] Бот не найден")

print("\n" + "=" * 80)
print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
print("=" * 80)

