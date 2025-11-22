#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания таблицы bot_trades_history в существующей базе данных
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

def fix_bot_trades_history():
    """Создает таблицу bot_trades_history если её нет"""
    db_path = PROJECT_ROOT / 'data' / 'bots_data.db'
    
    if not db_path.exists():
        print(f"❌ Файл не найден: {db_path}")
        return False
    
    print(f"🔧 Проверка и создание таблицы bot_trades_history в {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Проверяем, существует ли таблица
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='bot_trades_history'
    """)
    
    if cursor.fetchone():
        print("✅ Таблица bot_trades_history уже существует")
        conn.close()
        return True
    
    print("📦 Создание таблицы bot_trades_history...")
    
    try:
        # Создаем таблицу
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_trades_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                entry_timestamp REAL,
                exit_timestamp REAL,
                position_size_usdt REAL,
                position_size_coins REAL,
                pnl REAL,
                roi REAL,
                status TEXT NOT NULL DEFAULT 'CLOSED',
                close_reason TEXT,
                decision_source TEXT DEFAULT 'SCRIPT',
                ai_decision_id TEXT,
                ai_confidence REAL,
                entry_rsi REAL,
                exit_rsi REAL,
                entry_trend TEXT,
                exit_trend TEXT,
                entry_volatility REAL,
                entry_volume_ratio REAL,
                is_successful INTEGER DEFAULT 0,
                is_simulated INTEGER DEFAULT 0,
                source TEXT DEFAULT 'bot',
                order_id TEXT,
                extra_data_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Создаем индексы
        print("📦 Создание индексов...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_id ON bot_trades_history(bot_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_symbol ON bot_trades_history(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_status ON bot_trades_history(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_entry_time ON bot_trades_history(entry_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_exit_time ON bot_trades_history(exit_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_decision_source ON bot_trades_history(decision_source)")
        
        conn.commit()
        print("✅ Таблица bot_trades_history успешно создана!")
        
        # Проверяем
        cursor.execute("SELECT COUNT(*) FROM bot_trades_history")
        count = cursor.fetchone()[0]
        print(f"✅ Проверка: таблица содержит {count} записей")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания таблицы: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        conn.close()
        return False

if __name__ == '__main__':
    success = fix_bot_trades_history()
    sys.exit(0 if success else 1)

