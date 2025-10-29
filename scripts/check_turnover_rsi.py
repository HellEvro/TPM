#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка turnover в свечах и передачи RSI на фронтенд"""

import json
import os
import glob
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("Проверка 1: Turnover в свечах")
print("=" * 60)

# Проверяем несколько файлов свечей
candle_files = glob.glob('data/candles_cache/1w/*.json')[:5]
print(f"Найдено файлов: {len(candle_files)}")

if candle_files:
    for file_path in candle_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            candles = data.get('candles', [])
            if not candles:
                continue
            
            symbol = os.path.basename(file_path).replace('.json', '')
            last_candle = candles[-1]
            
            has_turnover = 'turnover' in last_candle
            turnover_value = last_candle.get('turnover', 'НЕТ')
            
            print(f"\n{symbol}:")
            print(f"  Свечей: {len(candles)}")
            print(f"  Turnover: {'ЕСТЬ' if has_turnover else 'НЕТ'}")
            if has_turnover:
                print(f"  Значение turnover: {turnover_value}")
            print(f"  Поля свечи: {list(last_candle.keys())}")
            
        except Exception as e:
            print(f"Ошибка при чтении {file_path}: {e}")

print("\n" + "=" * 60)
print("Проверка 2: RSI данные и ключи")
print("=" * 60)

try:
    from bots_modules.imports_and_globals import coins_rsi_data
    from bots_modules.filters import get_rsi_key, get_trend_key
    
    rsi_key = get_rsi_key()
    trend_key = get_trend_key()
    print(f"Динамический RSI ключ: {rsi_key}")
    print(f"Динамический Trend ключ: {trend_key}")
    
    coins = coins_rsi_data.get('coins', {})
    print(f"\nВсего монет в coins_rsi_data: {len(coins)}")
    
    # Проверяем несколько монет
    sample_symbols = list(coins.keys())[:5]
    for symbol in sample_symbols:
        coin_data = coins[symbol]
        print(f"\n{symbol}:")
        print(f"  Ключи: {list(coin_data.keys())[:10]}...")
        
        # Проверяем динамический ключ RSI
        if rsi_key in coin_data:
            rsi_value = coin_data[rsi_key]
            print(f"  {rsi_key}: {rsi_value}")
        else:
            print(f"  {rsi_key}: НЕТ")
        
        # Проверяем нормализованный ключ 'rsi'
        if 'rsi' in coin_data:
            rsi_normalized = coin_data['rsi']
            print(f"  rsi (нормализованный): {rsi_normalized}")
        else:
            print(f"  rsi (нормализованный): НЕТ")
        
        # Проверяем trend
        if trend_key in coin_data:
            trend_value = coin_data[trend_key]
            print(f"  {trend_key}: {trend_value}")
        if 'trend' in coin_data:
            trend_normalized = coin_data['trend']
            print(f"  trend (нормализованный): {trend_normalized}")
        
except Exception as e:
    print(f"Ошибка при проверке RSI данных: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Проверка завершена")
print("=" * 60)

