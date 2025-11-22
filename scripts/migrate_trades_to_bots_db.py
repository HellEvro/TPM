#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция существующих сделок в bot_trades_history из различных источников
"""

import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot_engine.bots_database import get_bots_database

def migrate_from_ai_db():
    """Мигрирует сделки из ai_data.db (bot_trades, exchange_trades)"""
    print("=" * 80)
    print("МИГРАЦИЯ ИЗ ai_data.db")
    print("=" * 80)
    
    ai_db_path = PROJECT_ROOT / 'data' / 'ai_data.db'
    if not ai_db_path.exists():
        print(f"⚠️ Файл не найден: {ai_db_path}")
        return 0
    
    bots_db = get_bots_database()
    conn = sqlite3.connect(str(ai_db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    migrated = 0
    
    # Мигрируем из bot_trades
    try:
        cursor.execute("SELECT * FROM bot_trades")
        rows = cursor.fetchall()
        print(f"\n📦 Найдено {len(rows)} записей в bot_trades")
        
        for row in rows:
            row_dict = dict(row)
            trade_data = {
                'bot_id': row_dict.get('bot_id') or row_dict.get('symbol', ''),
                'symbol': row_dict.get('symbol', ''),
                'direction': row_dict.get('direction', 'LONG'),
                'entry_price': row_dict.get('entry_price', 0.0),
                'exit_price': row_dict.get('exit_price'),
                'entry_time': row_dict.get('entry_time'),
                'exit_time': row_dict.get('exit_time'),
                'entry_timestamp': row_dict.get('entry_timestamp'),
                'exit_timestamp': row_dict.get('exit_timestamp'),
                'position_size_usdt': row_dict.get('position_size_usdt'),
                'position_size_coins': row_dict.get('position_size_coins'),
                'pnl': row_dict.get('pnl'),
                'roi': row_dict.get('roi') or row_dict.get('pnl_pct'),
                'status': row_dict.get('status', 'CLOSED'),
                'close_reason': row_dict.get('exit_reason') or row_dict.get('close_reason'),
                'decision_source': row_dict.get('decision_source', 'SCRIPT'),
                'ai_decision_id': row_dict.get('ai_decision_id'),
                'ai_confidence': row_dict.get('ai_confidence'),
                'entry_rsi': row_dict.get('entry_rsi'),
                'exit_rsi': row_dict.get('exit_rsi'),
                'entry_trend': row_dict.get('entry_trend'),
                'exit_trend': row_dict.get('exit_trend'),
                'entry_volatility': row_dict.get('entry_volatility'),
                'entry_volume_ratio': row_dict.get('entry_volume_ratio'),
                'is_successful': bool(row_dict.get('is_successful', 0)) if row_dict.get('is_successful') is not None else None,
                'is_simulated': bool(row_dict.get('is_simulated', 0)) if row_dict.get('is_simulated') is not None else False,
                'source': 'ai_db_migration',
                'order_id': row_dict.get('order_id')
            }
            
            trade_id = bots_db.save_bot_trade_history(trade_data)
            if trade_id:
                migrated += 1
    except sqlite3.OperationalError as e:
        print(f"⚠️ Ошибка чтения bot_trades: {e}")
    
    # Мигрируем из exchange_trades (только те, что не являются симуляциями)
    try:
        cursor.execute("SELECT * FROM exchange_trades WHERE is_real = 1 OR is_real IS NULL")
        rows = cursor.fetchall()
        print(f"\n📦 Найдено {len(rows)} записей в exchange_trades (реальные)")
        
        for row in rows:
            row_dict = dict(row)
            # Пропускаем симуляции (проверяем source, так как is_simulated может отсутствовать)
            source = str(row_dict.get('source', '')).lower()
            if 'simulation' in source or 'backtest' in source or 'demo' in source:
                continue
            
            # Пропускаем если is_real = 0 (явно помечено как не реальная сделка)
            if row_dict.get('is_real') == 0:
                continue
            
            # Конвертируем timestamps в ISO если нужно
            # В exchange_trades entry_time и exit_time уже содержат timestamp в миллисекундах
            entry_time = None
            exit_time = None
            entry_ts = row_dict.get('entry_time')  # Уже timestamp в мс
            exit_ts = row_dict.get('exit_time')  # Уже timestamp в мс
            
            if entry_ts:
                try:
                    ts = entry_ts
                    if ts > 1e10:  # миллисекунды
                        ts = ts / 1000
                    entry_time = datetime.fromtimestamp(ts).isoformat()
                except:
                    pass
            
            if exit_ts:
                try:
                    ts = exit_ts
                    if ts > 1e10:  # миллисекунды
                        ts = ts / 1000
                    exit_time = datetime.fromtimestamp(ts).isoformat()
                except:
                    pass
            
            # Если нет entry_time, используем текущее время
            if not entry_time:
                entry_time = datetime.now().isoformat()
            
            trade_data = {
                'bot_id': row_dict.get('symbol', ''),
                'symbol': row_dict.get('symbol', ''),
                'direction': row_dict.get('direction', 'LONG'),
                'entry_price': row_dict.get('entry_price', 0.0),
                'exit_price': row_dict.get('exit_price'),
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_timestamp': entry_ts,
                'exit_timestamp': exit_ts,
                'position_size_usdt': row_dict.get('position_size_usdt'),
                'position_size_coins': row_dict.get('position_size_coins'),
                'pnl': row_dict.get('pnl'),
                'roi': row_dict.get('roi'),
                'status': 'CLOSED',
                'close_reason': 'EXCHANGE_IMPORT',
                'decision_source': 'EXCHANGE_IMPORT',
                'ai_decision_id': None,
                'ai_confidence': None,
                'entry_rsi': None,
                'exit_rsi': None,
                'entry_trend': None,
                'exit_trend': None,
                'entry_volatility': None,
                'entry_volume_ratio': None,
                'is_successful': row_dict.get('pnl', 0) > 0 if row_dict.get('pnl') else None,
                'is_simulated': False,
                'source': 'exchange_import',
                'order_id': row_dict.get('orderId')
            }
            
            trade_id = bots_db.save_bot_trade_history(trade_data)
            if trade_id:
                migrated += 1
    except sqlite3.OperationalError as e:
        print(f"⚠️ Ошибка чтения exchange_trades: {e}")
    
    conn.close()
    print(f"\n✅ Мигрировано {migrated} сделок из ai_data.db")
    return migrated

def migrate_from_app_db():
    """Мигрирует закрытые PnL из app_data.db (closed_pnl)"""
    print("\n" + "=" * 80)
    print("МИГРАЦИЯ ИЗ app_data.db (closed_pnl)")
    print("=" * 80)
    
    app_db_path = PROJECT_ROOT / 'data' / 'app_data.db'
    if not app_db_path.exists():
        print(f"⚠️ Файл не найден: {app_db_path}")
        return 0
    
    bots_db = get_bots_database()
    conn = sqlite3.connect(str(app_db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    migrated = 0
    
    try:
        cursor.execute("SELECT * FROM closed_pnl ORDER BY close_timestamp DESC")
        rows = cursor.fetchall()
        print(f"\n📦 Найдено {len(rows)} записей в closed_pnl")
        
        for row in rows:
            row_dict = dict(row)
            # Пропускаем если нет необходимых данных
            if not row_dict.get('symbol') or not row_dict.get('entry_price') or not row_dict.get('exit_price'):
                continue
            
            side = row_dict.get('side', 'BUY')
            direction = 'LONG' if side.upper() in ('BUY', 'LONG') else 'SHORT'
            
            # Конвертируем timestamps в ISO если нужно
            entry_time = None
            exit_time = None
            entry_ts = row_dict.get('entry_timestamp')
            exit_ts = row_dict.get('close_timestamp')
            
            if entry_ts:
                try:
                    ts = entry_ts
                    if ts > 1e10:  # миллисекунды
                        ts = ts / 1000
                    entry_time = datetime.fromtimestamp(ts).isoformat()
                except:
                    pass
            
            if exit_ts:
                try:
                    ts = exit_ts
                    if ts > 1e10:  # миллисекунды
                        ts = ts / 1000
                    exit_time = datetime.fromtimestamp(ts).isoformat()
                except:
                    pass
            
            # Если нет entry_time, используем текущее время
            if not entry_time:
                entry_time = datetime.now().isoformat()
            
            trade_data = {
                'bot_id': row_dict.get('symbol', ''),
                'symbol': row_dict.get('symbol', ''),
                'direction': direction,
                'entry_price': row_dict.get('entry_price', 0.0),
                'exit_price': row_dict.get('exit_price'),
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_timestamp': entry_ts,
                'exit_timestamp': exit_ts,
                'position_size_usdt': None,
                'position_size_coins': row_dict.get('size'),
                'pnl': row_dict.get('closed_pnl'),
                'roi': row_dict.get('closed_pnl_percent'),
                'status': 'CLOSED',
                'close_reason': 'CLOSED_PNL_MIGRATION',
                'decision_source': 'EXCHANGE_IMPORT',
                'ai_decision_id': None,
                'ai_confidence': None,
                'entry_rsi': None,
                'exit_rsi': None,
                'entry_trend': None,
                'exit_trend': None,
                'entry_volatility': None,
                'entry_volume_ratio': None,
                'is_successful': row_dict.get('closed_pnl', 0) > 0 if row_dict.get('closed_pnl') else None,
                'is_simulated': False,
                'source': 'app_db_closed_pnl',
                'order_id': None
            }
            
            trade_id = bots_db.save_bot_trade_history(trade_data)
            if trade_id:
                migrated += 1
    except sqlite3.OperationalError as e:
        print(f"⚠️ Ошибка чтения closed_pnl: {e}")
    
    conn.close()
    print(f"\n✅ Мигрировано {migrated} сделок из app_data.db")
    return migrated

if __name__ == '__main__':
    print("🚀 Начало миграции сделок в bot_trades_history")
    print("=" * 80)
    
    total = 0
    total += migrate_from_ai_db()
    total += migrate_from_app_db()
    
    print("\n" + "=" * 80)
    print(f"✅ МИГРАЦИЯ ЗАВЕРШЕНА: всего мигрировано {total} сделок")
    print("=" * 80)
    
    # Проверяем результат
    bots_db = get_bots_database()
    trades = bots_db.get_bot_trades_history(limit=10)
    print(f"\n📊 Проверка: в bot_trades_history теперь {len(trades)} записей (показано последние 10)")
    for trade in trades[:5]:
        print(f"   {trade['symbol']} {trade['direction']} | {trade['status']} | pnl={trade.get('pnl')} | source={trade.get('source')}")

