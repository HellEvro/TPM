#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Быстрый перезапуск bots.py через API
"""

import sys
import io
import requests
import json
import time

# Исправляем кодировку для Windows
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def restart_bots_service():
    """Перезапускает сервис ботов через API"""
    try:
        print("🔄 Перезапускаем сервис ботов...")
        
        # Отправляем запрос на перезапуск
        response = requests.post(
            'http://localhost:5001/api/bots/restart-service',
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result.get('message', 'Сервис перезапущен')}")
            return True
        else:
            print(f"❌ Ошибка перезапуска: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Сервис ботов недоступен на порту 5001")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def reload_modules():
    """Перезагружает модули"""
    try:
        print("🔄 Перезагружаем модули...")
        
        response = requests.post(
            'http://localhost:5001/api/bots/reload-modules',
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result.get('message', 'Модули перезагружены')}")
            return True
        else:
            print(f"❌ Ошибка перезагрузки модулей: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    """Основная функция"""
    print("🚀 Быстрый перезапуск bots.py")
    print("-" * 40)
    
    # Сначала пробуем перезагрузить модули
    if reload_modules():
        print("\n⏳ Ждем 3 секунды...")
        time.sleep(3)
        
        # Проверяем, работает ли сервис
        try:
            response = requests.get('http://localhost:5001/health', timeout=5)
            if response.status_code == 200:
                print("✅ Сервис работает корректно")
                return
        except:
            pass
    
    # Если модули не помогли, перезапускаем сервис
    print("\n🔄 Перезагружаем полный сервис...")
    restart_bots_service()

if __name__ == '__main__':
    main()
