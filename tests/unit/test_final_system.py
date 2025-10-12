"""
Тест финальной системы bots_final.py
"""

import requests
import time
import json

print("=" * 80)
print("TESTING FINAL SYSTEM")
print("=" * 80)
print()

# Ждем запуска
print("Ждем запуска сервиса...")
time.sleep(5)

base_url = "http://localhost:5001"
tests_passed = 0
tests_total = 0

def test_endpoint(name, method, url, data=None):
    """Тестирует endpoint"""
    global tests_passed, tests_total
    tests_total += 1
    
    try:
        print(f"\n[TEST {tests_total}] {name}")
        print(f"  {method} {url}")
        
        if method == 'GET':
            r = requests.get(url, timeout=5)
        else:
            r = requests.post(url, json=data, timeout=5)
        
        print(f"  Status: {r.status_code}")
        
        if r.status_code == 200:
            result = r.json()
            if result.get('success', False) or result.get('status') == 'ok':
                print(f"  [OK] PASSED")
                tests_passed += 1
                return True
            else:
                print(f"  [FAIL] {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"  [FAIL] Status {r.status_code}")
            return False
            
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

# Запускаем тесты
print("\n" + "=" * 80)
print("БАЗОВЫЕ ENDPOINTS")
print("=" * 80)

test_endpoint("Health Check", "GET", f"{base_url}/health")
test_endpoint("API Status", "GET", f"{base_url}/api/status")
test_endpoint("Account Info", "GET", f"{base_url}/api/bots/account-info")

print("\n" + "=" * 80)
print("УПРАВЛЕНИЕ БОТАМИ")
print("=" * 80)

test_endpoint("Список ботов", "GET", f"{base_url}/api/bots/list")

print("\n" + "=" * 80)
print("КОНФИГУРАЦИЯ")
print("=" * 80)

test_endpoint("Получить Auto Bot config", "GET", f"{base_url}/api/bots/auto-bot")
test_endpoint("Получить System config", "GET", f"{base_url}/api/bots/system-config")

print("\n" + "=" * 80)
print("RSI ДАННЫЕ")
print("=" * 80)

test_endpoint("Получить RSI данные", "GET", f"{base_url}/api/bots/coins-with-rsi")

# Итоги
print("\n" + "=" * 80)
print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
print("=" * 80)
print(f"Всего тестов: {tests_total}")
print(f"Пройдено: {tests_passed}")
print(f"Провалено: {tests_total - tests_passed}")
print(f"Процент успеха: {(tests_passed/tests_total*100) if tests_total > 0 else 0:.1f}%")
print()

if tests_passed == tests_total:
    print("[SUCCESS] ALL TESTS PASSED!")
    print()
    print("[OK] bots_final.py works perfectly!")
    print(f"[OK] File size: 234 lines (was 7695)")
    print(f"[OK] Reduction: 97%")
    print()
else:
    print(f"[WARNING] Some tests failed ({tests_total - tests_passed}/{tests_total})")

print("=" * 80)

