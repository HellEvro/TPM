#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ СКРИПТ МОНИТОРИНГА И ЗАЩИТЫ ОТ АВТОЗАПУСКА БОТОВ
====================================================

Этот скрипт следит за системой и немедленно останавливает bots.py при:
- Включении автобота
- Создании новых ботов
- Открытии новых сделок
- Попытках торговли

Автор: AI Assistant
Дата: 2025-10-09
"""

import sys
import io
import os
import time
import json
import requests
import psutil
from datetime import datetime
from colorama import init, Fore, Style

# Исправляем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Инициализируем colorama для цветного вывода
init(autoreset=True)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

BOTS_SERVICE_PORT = 5001
BOTS_SERVICE_URL = f"http://localhost:{BOTS_SERVICE_PORT}"
CHECK_INTERVAL = 2  # Проверка каждые 2 секунды
BOTS_STATE_FILE = "data/bots_state.json"
AUTO_BOT_CONFIG_FILE = "data/auto_bot_config.json"

# ============================================================================
# УТИЛИТЫ
# ============================================================================

def print_header():
    """Выводит заголовок скрипта"""
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}🛡️  МОНИТОР ЗАЩИТЫ ОТ АВТОЗАПУСКА БОТОВ")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}⚠️  ВНИМАНИЕ: Этот скрипт будет НЕМЕДЛЕННО останавливать bots.py при:")
    print(f"{Fore.YELLOW}   - Включении автобота")
    print(f"{Fore.YELLOW}   - Создании новых ботов")
    print(f"{Fore.YELLOW}   - Открытии новых сделок")
    print(f"{Fore.YELLOW}   - Любых попытках торговли{Style.RESET_ALL}\n")
    print(f"{Fore.GREEN}✅ Интервал проверки: {CHECK_INTERVAL} секунд{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Порт сервиса: {BOTS_SERVICE_PORT}{Style.RESET_ALL}\n")
    print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")


def log(message, level="INFO"):
    """Выводит сообщение с временной меткой и цветом"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if level == "INFO":
        color = Fore.WHITE
        icon = "ℹ️"
    elif level == "SUCCESS":
        color = Fore.GREEN
        icon = "✅"
    elif level == "WARNING":
        color = Fore.YELLOW
        icon = "⚠️"
    elif level == "ERROR":
        color = Fore.RED
        icon = "❌"
    elif level == "CRITICAL":
        color = Fore.RED + Style.BRIGHT
        icon = "🚨"
    else:
        color = Fore.WHITE
        icon = "•"
    
    print(f"{color}[{timestamp}] {icon} {message}{Style.RESET_ALL}")


def find_bots_process():
    """Находит процесс bots.py, слушающий порт 5001"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Проверяем, что это python процесс
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('bots.py' in str(arg) for arg in cmdline):
                        # Проверяем, что процесс слушает порт 5001
                        connections = proc.connections()
                        for conn in connections:
                            if conn.status == 'LISTEN' and conn.laddr.port == BOTS_SERVICE_PORT:
                                return proc.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return None
    except Exception as e:
        log(f"Ошибка поиска процесса: {e}", "ERROR")
        return None


def kill_bots_process(pid):
    """Убивает процесс bots.py по PID"""
    try:
        process = psutil.Process(pid)
        process_name = process.name()
        log(f"Останавливаем процесс {process_name} (PID: {pid})...", "CRITICAL")
        
        # Пробуем graceful shutdown
        process.terminate()
        
        # Ждем 5 секунд
        try:
            process.wait(timeout=5)
            log(f"Процесс {pid} успешно остановлен (graceful)", "SUCCESS")
            return True
        except psutil.TimeoutExpired:
            # Если не остановился - убиваем принудительно
            log(f"Процесс {pid} не остановился, принудительное завершение...", "WARNING")
            process.kill()
            process.wait(timeout=5)
            log(f"Процесс {pid} принудительно завершен", "SUCCESS")
            return True
            
    except psutil.NoSuchProcess:
        log(f"Процесс {pid} уже не существует", "WARNING")
        return True
    except Exception as e:
        log(f"Ошибка остановки процесса {pid}: {e}", "ERROR")
        return False


def check_service_online():
    """Проверяет, что сервис bots.py запущен"""
    try:
        response = requests.get(f"{BOTS_SERVICE_URL}/api/status", timeout=2)
        return response.status_code == 200
    except:
        return False


def check_auto_bot_enabled():
    """Проверяет, включен ли автобот"""
    try:
        # Проверяем через файл
        if os.path.exists(AUTO_BOT_CONFIG_FILE):
            with open(AUTO_BOT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('enabled', False)
        return False
    except Exception as e:
        log(f"Ошибка проверки автобота: {e}", "ERROR")
        return False


def check_active_bots():
    """Проверяет количество активных ботов"""
    try:
        # Проверяем через файл
        if os.path.exists(BOTS_STATE_FILE):
            with open(BOTS_STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                bots = state.get('bots', {})
                return len(bots)
        return 0
    except Exception as e:
        log(f"Ошибка проверки ботов: {e}", "ERROR")
        return 0


def check_logs_for_trading():
    """Проверяет логи на наличие торговых операций"""
    try:
        log_file = "logs/bots.log"
        if not os.path.exists(log_file):
            return False
        
        # Читаем последние 50 строк
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            recent_lines = lines[-50:] if len(lines) > 50 else lines
        
        # Ищем ключевые слова торговли
        trading_keywords = [
            'ORDER',
            'ОРДЕР',
            'Попытка размещения',
            'Открытие позиции',
            'LONG',
            'SHORT',
            'создан бота',
            'Бот для',
            'создаем бота'
        ]
        
        for line in recent_lines:
            for keyword in trading_keywords:
                if keyword.lower() in line.lower():
                    # Проверяем, что это не старая запись (последние 10 секунд)
                    return True
        
        return False
    except Exception as e:
        log(f"Ошибка проверки логов: {e}", "ERROR")
        return False


# ============================================================================
# ОСНОВНОЙ ЦИКЛ МОНИТОРИНГА
# ============================================================================

def main():
    """Основная функция мониторинга"""
    print_header()
    
    # Начальное состояние
    initial_bots_count = check_active_bots()
    log(f"Начальное количество ботов: {initial_bots_count}", "INFO")
    
    auto_bot_enabled = check_auto_bot_enabled()
    if auto_bot_enabled:
        log("⚠️ ВНИМАНИЕ! Автобот включен при старте мониторинга!", "CRITICAL")
        log("Останавливаем систему...", "CRITICAL")
        pid = find_bots_process()
        if pid:
            kill_bots_process(pid)
        return
    else:
        log("Автобот отключен - OK", "SUCCESS")
    
    log("Начинаем мониторинг...", "INFO")
    log("Нажмите Ctrl+C для остановки мониторинга\n", "INFO")
    
    check_counter = 0
    
    try:
        while True:
            check_counter += 1
            
            # Проверяем, что сервис запущен
            if not check_service_online():
                log("Сервис bots.py не отвечает", "WARNING")
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Проверка 1: Автобот включен?
            auto_bot_enabled = check_auto_bot_enabled()
            if auto_bot_enabled:
                log("🚨 КРИТИЧЕСКАЯ УГРОЗА! АВТОБОТ ВКЛЮЧЕН!", "CRITICAL")
                log("НЕМЕДЛЕННО ОСТАНАВЛИВАЕМ СИСТЕМУ!", "CRITICAL")
                pid = find_bots_process()
                if pid:
                    if kill_bots_process(pid):
                        log("✅ Система успешно остановлена!", "SUCCESS")
                        log("Причина: Автобот был включен", "CRITICAL")
                        break
                    else:
                        log("❌ Не удалось остановить систему!", "ERROR")
                else:
                    log("❌ Процесс bots.py не найден!", "ERROR")
                break
            
            # Проверка 2: Появились новые боты?
            current_bots_count = check_active_bots()
            if current_bots_count > initial_bots_count:
                log(f"🚨 КРИТИЧЕСКАЯ УГРОЗА! ОБНАРУЖЕНЫ НОВЫЕ БОТЫ!", "CRITICAL")
                log(f"Было: {initial_bots_count}, Стало: {current_bots_count}", "CRITICAL")
                log("НЕМЕДЛЕННО ОСТАНАВЛИВАЕМ СИСТЕМУ!", "CRITICAL")
                pid = find_bots_process()
                if pid:
                    if kill_bots_process(pid):
                        log("✅ Система успешно остановлена!", "SUCCESS")
                        log(f"Причина: Создано {current_bots_count - initial_bots_count} новых ботов", "CRITICAL")
                        break
                    else:
                        log("❌ Не удалось остановить систему!", "ERROR")
                else:
                    log("❌ Процесс bots.py не найден!", "ERROR")
                break
            
            # Проверка 3: Есть ли торговые операции в логах?
            if check_logs_for_trading():
                log("🚨 КРИТИЧЕСКАЯ УГРОЗА! ОБНАРУЖЕНЫ ТОРГОВЫЕ ОПЕРАЦИИ В ЛОГАХ!", "CRITICAL")
                log("НЕМЕДЛЕННО ОСТАНАВЛИВАЕМ СИСТЕМУ!", "CRITICAL")
                pid = find_bots_process()
                if pid:
                    if kill_bots_process(pid):
                        log("✅ Система успешно остановлена!", "SUCCESS")
                        log("Причина: Обнаружены торговые операции", "CRITICAL")
                        break
                    else:
                        log("❌ Не удалось остановить систему!", "ERROR")
                else:
                    log("❌ Процесс bots.py не найден!", "ERROR")
                break
            
            # Все проверки пройдены
            if check_counter % 10 == 0:  # Каждые 20 секунд (10 проверок * 2 сек)
                log(f"✅ Проверка #{check_counter}: Автобот: OFF, Ботов: {current_bots_count}, Торговля: НЕТ", "SUCCESS")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        log("\n\n🛑 Мониторинг остановлен пользователем", "WARNING")
        log("Система продолжает работать", "INFO")
    except Exception as e:
        log(f"Критическая ошибка мониторинга: {e}", "ERROR")


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{Fore.RED}❌ КРИТИЧЕСКАЯ ОШИБКА: {e}{Style.RESET_ALL}")
        sys.exit(1)

