#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка передачи RSI через API endpoint"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Имитируем запрос к API endpoint
try:
    from bots_modules.api_endpoints import get_coins_with_rsi
    from flask import Flask
    from flask.testing import FlaskClient
    
    # Создаем тестовое Flask приложение
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.add_url_rule('/api/bots/coins-with-rsi', 'get_coins_with_rsi', get_coins_with_rsi, methods=['GET'])
    
    with app.test_client() as client:
        response = client.get('/api/bots/coins-with-rsi')
        if response.status_code == 200:
            data = response.get_json()
            if data.get('success'):
                coins = data.get('coins', {})
                print(f"✅ API успешно вернул {len(coins)} монет")
                
                # Проверяем несколько монет на наличие RSI
                sample_symbols = list(coins.keys())[:5]
                for symbol in sample_symbols:
                    coin = coins[symbol]
                    print(f"\n{symbol}:")
                    print(f"  rsi: {coin.get('rsi', 'НЕТ')}")
                    print(f"  rsi1w: {coin.get('rsi1w', 'НЕТ')}")
                    print(f"  trend: {coin.get('trend', 'НЕТ')}")
                    print(f"  trend1w: {coin.get('trend1w', 'НЕТ')}")
                    print(f"  signal: {coin.get('signal', 'НЕТ')}")
            else:
                print(f"❌ API вернул ошибку: {data.get('error')}")
        else:
            print(f"❌ HTTP статус: {response.status_code}")
            
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    
    # Альтернативная проверка - напрямую из coins_rsi_data
    print("\n" + "="*60)
    print("Альтернативная проверка напрямую из coins_rsi_data:")
    print("="*60)
    try:
        from bots_modules.imports_and_globals import coins_rsi_data
        from bots_modules.filters import get_rsi_key, get_trend_key
        
        rsi_key = get_rsi_key()
        trend_key = get_trend_key()
        
        coins = coins_rsi_data.get('coins', {})
        print(f"\nВсего монет в coins_rsi_data: {len(coins)}")
        
        if coins:
            print(f"\n✅ Данные загружены!")
            sample_symbols = list(coins.keys())[:5]
            print(f"\nПроверяем {len(sample_symbols)} монет:")
            for symbol in sample_symbols:
                coin = coins[symbol]
                print(f"\n{symbol}:")
                rsi_value = coin.get(rsi_key)
                trend_value = coin.get(trend_key)
                print(f"  {rsi_key}: {rsi_value}")
                print(f"  {trend_key}: {trend_value}")
                print(f"  rsi (нормализованный): {coin.get('rsi', 'НЕТ')}")
                print(f"  trend (нормализованный): {coin.get('trend', 'НЕТ')}")
                print(f"  signal: {coin.get('signal', 'НЕТ')}")
        else:
            print("\n⚠️ coins_rsi_data пуст - данные еще не загружены")
            print("Это нормально, если система только что запустилась")
            print("Подождите следующего раунда загрузки (обычно ~5 минут)")
            
    except Exception as e2:
        print(f"❌ Ошибка альтернативной проверки: {e2}")
        import traceback
        traceback.print_exc()

