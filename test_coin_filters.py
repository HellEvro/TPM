#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Утилита для тестирования фильтров для конкретных монет
Использование: python test_coin_filters.py SYMBOL
Пример: python test_coin_filters.py 1000000CHEEMS
"""

import sys
import io
import requests
import json

# Исправляем кодировку для Windows консоли
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_coin_filters(symbol):
    """Тестирует все фильтры для монеты"""
    print(f"\n{'='*60}")
    print(f"🔍 ТЕСТИРОВАНИЕ ФИЛЬТРОВ ДЛЯ {symbol}")
    print(f"{'='*60}\n")
    
    # 1. Тест ExitScam фильтра
    print("📊 1. ExitScam фильтр:")
    print("-" * 60)
    try:
        response = requests.get(f'http://localhost:5001/api/bots/test-exit-scam/{symbol}', timeout=10)
        if response.status_code == 200:
            print("✅ Тест запущен, смотрите логи bots.py для детальных результатов")
        else:
            print(f"❌ Ошибка: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    print()
    
    # 2. Тест RSI временного фильтра
    print("⏰ 2. RSI временной фильтр:")
    print("-" * 60)
    try:
        response = requests.get(f'http://localhost:5001/api/bots/test-rsi-time-filter/{symbol}', timeout=10)
        if response.status_code == 200:
            print("✅ Тест запущен, смотрите логи bots.py для детальных результатов")
        else:
            print(f"❌ Ошибка: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    print()
    
    # 3. Получаем общую информацию о монете (с обновлением RSI данных)
    print("📈 3. Текущие данные монеты:")
    print("-" * 60)
    print("🔄 Обновляем RSI данные для применения новой логики...")
    try:
        response = requests.get(f'http://localhost:5001/api/bots/coins-with-rsi?refresh_symbol={symbol}', timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Обрабатываем формат ответа
            coins = data.get('coins', {})
            
            # Проверяем что coins это словарь
            if not coins or not isinstance(coins, dict):
                print(f"❌ Нет данных о монетах (возможно, еще не загружены)")
                print(f"📊 Количество монет: 0")
                print(f"💡 Подождите несколько минут пока система загрузит RSI данные")
                return
            
            print(f"📊 Всего монет в системе: {len(coins)}")
            
            # Получаем данные монеты по символу (coins это словарь {symbol: data})
            coin_data = coins.get(symbol)
            
            if coin_data:
                print(f"Символ: {coin_data['symbol']}")
                print(f"Цена: ${coin_data['price']:.4f}")
                print(f"RSI 6H: {coin_data['rsi6h']:.1f}")
                print(f"Тренд 6H: {coin_data['trend6h']}")
                print(f"Сигнал: {coin_data['signal']}")
                print(f"Изменение 24H: {coin_data['change24h']:+.2f}%")
                
                # Информация об ExitScam фильтре
                exit_scam_info = coin_data.get('exit_scam_info')
                if exit_scam_info:
                    print(f"\n🛡️ ExitScam фильтр:")
                    if exit_scam_info.get('blocked'):
                        print(f"  ❌ ЗАБЛОКИРОВАН")
                        print(f"  Причина: {exit_scam_info.get('reason')}")
                    else:
                        print(f"  ✅ ПРОЙДЕН")
                        print(f"  Причина: {exit_scam_info.get('reason')}")
                
                # Информация о временном фильтре
                time_filter_info = coin_data.get('time_filter_info')
                if time_filter_info:
                    print(f"\n⏰ RSI временной фильтр:")
                    if time_filter_info.get('allowed'):
                        print(f"  ✅ РАЗРЕШЕН")
                    else:
                        print(f"  ❌ БЛОКИРОВАН")
                    print(f"  Причина: {time_filter_info.get('reason')}")
                    if 'calm_candles' in time_filter_info and time_filter_info['calm_candles'] is not None:
                        print(f"  Спокойных свечей: {time_filter_info['calm_candles']}")
                    if 'last_extreme_candles_ago' in time_filter_info and time_filter_info['last_extreme_candles_ago'] is not None:
                        print(f"  Последний экстремум: {time_filter_info['last_extreme_candles_ago']} свечей назад")
            else:
                print(f"❌ Монета {symbol} не найдена в списке")
        else:
            print(f"❌ Ошибка получения данных: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
    
    print()
    print("="*60)
    print("💡 Для детальной информации смотрите логи bots.py")
    print("="*60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python test_coin_filters.py SYMBOL")
        print("Пример: python test_coin_filters.py 1000000CHEEMS")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    test_coin_filters(symbol)

