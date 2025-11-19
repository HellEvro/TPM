#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мониторинг изменений в bot_history.json в реальном времени"""

import json
import time
import sys
import io
import os
import argparse
from pathlib import Path
from datetime import datetime

# Исправляем кодировку для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_args():
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(
        description='Мониторинг изменений в bot_history.json в реальном времени'
    )
    parser.add_argument(
        '--file',
        '-f',
        type=str,
        default=None,
        help='Путь к файлу для мониторинга (по умолчанию: data/bot_history.json)'
    )
    return parser.parse_args()

def load_history(file_path):
    """Загружает историю из файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        return None

def get_stats(data):
    """Получает статистику из данных"""
    if not data:
        return None
    
    history = data.get('history', [])
    trades = data.get('trades', [])
    
    return {
        'history_count': len(history),
        'trades_count': len(trades),
        'simulated_history': len([x for x in history if x.get('is_simulated') == True]),
        'simulated_trades': len([x for x in trades if x.get('is_simulated') == True]),
        'real_history': len([x for x in history if x.get('is_simulated') == False]),
        'real_trades': len([x for x in trades if x.get('is_simulated') == False]),
        'ai_history': len([x for x in history if x.get('decision_source') == 'AI']),
        'ai_trades': len([x for x in trades if x.get('decision_source') == 'AI']),
        'script_history': len([x for x in history if x.get('decision_source') == 'SCRIPT']),
        'script_trades': len([x for x in trades if x.get('decision_source') == 'SCRIPT']),
        'exchange_history': len([x for x in history if x.get('decision_source') == 'EXCHANGE_IMPORT']),
        'exchange_trades': len([x for x in trades if x.get('decision_source') == 'EXCHANGE_IMPORT']),
    }

def get_new_entries(data, prev_data):
    """Получает новые записи по сравнению с предыдущими данными"""
    if not prev_data:
        return [], []
    
    prev_history_ids = {e.get('id') for e in prev_data.get('history', [])}
    prev_trade_ids = {t.get('id') for t in prev_data.get('trades', [])}
    
    new_history = [e for e in data.get('history', []) if e.get('id') not in prev_history_ids]
    new_trades = [t for t in data.get('trades', []) if t.get('id') not in prev_trade_ids]
    
    return new_history, new_trades

def print_stats(stats, prev_stats=None, data=None, prev_data=None):
    """Выводит статистику"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] СТАТИСТИКА bot_history.json:")
    print("="*70)
    print(f"История (history): {stats['history_count']} записей")
    print(f"  - Реальных: {stats['real_history']} (is_simulated=False)")
    print(f"  - Симулированных: {stats['simulated_history']} (is_simulated=True)")
    print(f"  - decision_source=AI: {stats['ai_history']}")
    print(f"  - decision_source=SCRIPT: {stats['script_history']}")
    print(f"  - decision_source=EXCHANGE_IMPORT: {stats['exchange_history']}")
    print(f"")
    print(f"Сделки (trades): {stats['trades_count']} сделок")
    print(f"  - Реальных: {stats['real_trades']} (is_simulated=False)")
    print(f"  - Симулированных: {stats['simulated_trades']} (is_simulated=True)")
    print(f"  - decision_source=AI: {stats['ai_trades']}")
    print(f"  - decision_source=SCRIPT: {stats['script_trades']}")
    print(f"  - decision_source=EXCHANGE_IMPORT: {stats['exchange_trades']}")
    
    if prev_stats and data and prev_data:
        history_diff = stats['history_count'] - prev_stats['history_count']
        trades_diff = stats['trades_count'] - prev_stats['trades_count']
        simulated_diff = stats['simulated_trades'] - prev_stats['simulated_trades']
        
        if history_diff != 0 or trades_diff != 0:
            print(f"\nИЗМЕНЕНИЯ:")
            if history_diff != 0:
                print(f"  История: {history_diff:+d} записей")
            if trades_diff != 0:
                print(f"  Сделки: {trades_diff:+d} сделок")
            if simulated_diff != 0:
                print(f"  ⚠️ Симулированных сделок: {simulated_diff:+d}")
                if simulated_diff > 0:
                    print(f"  ❌ ВНИМАНИЕ: Добавлены симулированные сделки!")
            
            # Показываем новые записи
            new_history, new_trades = get_new_entries(data, prev_data)
            if new_history or new_trades:
                print(f"\nНОВЫЕ ЗАПИСИ:")
                for entry in new_history[:5]:  # Показываем первые 5
                    bot_id = entry.get('bot_id', 'N/A')
                    decision_source = entry.get('decision_source', 'N/A')
                    is_simulated = entry.get('is_simulated', 'N/A')
                    action_type = entry.get('action_type', 'N/A')
                    print(f"  [HISTORY] bot_id={bot_id}, source={decision_source}, simulated={is_simulated}, type={action_type}")
                if len(new_history) > 5:
                    print(f"  ... и еще {len(new_history) - 5} записей истории")
                
                for trade in new_trades[:5]:  # Показываем первые 5
                    bot_id = trade.get('bot_id', 'N/A')
                    decision_source = trade.get('decision_source', 'N/A')
                    is_simulated = trade.get('is_simulated', 'N/A')
                    symbol = trade.get('symbol', 'N/A')
                    print(f"  [TRADE] bot_id={bot_id}, symbol={symbol}, source={decision_source}, simulated={is_simulated}")
                if len(new_trades) > 5:
                    print(f"  ... и еще {len(new_trades) - 5} сделок")
    
    print("="*70)

def main():
    """Основная функция мониторинга"""
    args = parse_args()
    
    # Определяем путь к файлу
    if args.file:
        file_path_str = args.file
        # Проверяем, является ли путь абсолютным (включая UNC пути Windows)
        if os.path.isabs(file_path_str) or file_path_str.startswith('\\\\'):
            # Абсолютный путь (включая UNC пути типа \\server\share\path)
            history_file = Path(file_path_str)
        else:
            # Относительный путь - относительно корня проекта
            root_dir = Path(__file__).parent.parent
            history_file = root_dir / file_path_str
    else:
        # По умолчанию
        root_dir = Path(__file__).parent.parent
        history_file = root_dir / 'data' / 'bot_history.json'
    
    print(f"МОНИТОРИНГ: {history_file}")
    print("Нажмите Ctrl+C для остановки")
    print("="*70)
    
    prev_stats = None
    prev_data = None
    prev_mtime = 0
    
    try:
        while True:
            # Проверяем, изменился ли файл
            try:
                current_mtime = history_file.stat().st_mtime
            except FileNotFoundError:
                print(f"Файл {history_file} не найден, ожидание...")
                time.sleep(2)
                continue
            
            if current_mtime != prev_mtime:
                # Файл изменился, загружаем данные
                data = load_history(history_file)
                if data:
                    stats = get_stats(data)
                    if stats:
                        print_stats(stats, prev_stats, data, prev_data)
                        prev_stats = stats
                        prev_data = data
                    prev_mtime = current_mtime
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка загрузки данных")
            
            time.sleep(1)  # Проверяем каждую секунду
            
    except KeyboardInterrupt:
        print("\n\nМониторинг остановлен")

if __name__ == '__main__':
    main()

