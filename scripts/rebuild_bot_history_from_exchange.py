#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт пересобирает data/bot_history.json только из реальных сделок биржи.

Алгоритм:
1. Подключаемся к активной бирже из app.config.
2. Загружаем историю закрытых позиций (exchange.get_closed_pnl).
3. Фильтруем сделки по размеру позиции (по умолчанию около 5 USDT).
4. Полностью очищаем bot_history и заполняем его импортированными сделками.

Запуск:
    python scripts/rebuild_bot_history_from_exchange.py

Параметры:
    --target-usdt   Желаемый размер позиции в USDT (по умолчанию 5).
    --tolerance     Допустимое отклонение от target-usdt (по умолчанию 0.6).
    --period        Период загрузки истории (all/day/week/month/...).
    --output        Путь к bot_history.json (по умолчанию data/bot_history.json).
    --dry-run       Только показать статистику, не изменяя файл.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bot_engine.bot_history import BotHistoryManager, ACTION_TYPES, HISTORY_FILE
from exchanges.exchange_factory import ExchangeFactory


def load_exchange():
    try:
        from app.config import EXCHANGES, ACTIVE_EXCHANGE
    except ImportError as exc:  # pragma: no cover - защитный импорт
        raise RuntimeError(
            "Не удалось импортировать app.config. Убедитесь, что config.py существует."
        ) from exc
    
    exchange_name = ACTIVE_EXCHANGE
    exchange_cfg = EXCHANGES.get(exchange_name, {})
    if not exchange_cfg or not exchange_cfg.get('enabled', True):
        raise RuntimeError(f"Для {exchange_name} нет активных API ключей в config/keys.")
    
    api_key = exchange_cfg.get('api_key')
    api_secret = exchange_cfg.get('api_secret')
    passphrase = exchange_cfg.get('passphrase')
    
    if not api_key or not api_secret:
        raise RuntimeError(f"API ключи для {exchange_name} не заполнены.")
    
    exchange = ExchangeFactory.create_exchange(exchange_name, api_key, api_secret, passphrase)
    return exchange, exchange_name


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, ''):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def ms_to_iso(ts_ms: Optional[int]) -> Optional[str]:
    if ts_ms in (None, 0):
        return None
    try:
        return datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None


def infer_direction(side: Optional[str], entry_price: float, exit_price: float, pnl: float) -> str:
    normalized = (side or '').upper()
    if normalized in ('BUY', 'LONG'):
        return 'LONG'
    if normalized in ('SELL', 'SHORT'):
        return 'SHORT'
    
    if entry_price and exit_price:
        if exit_price >= entry_price:
            return 'LONG' if pnl >= 0 else 'SHORT'
        return 'SHORT' if pnl >= 0 else 'LONG'
    
    return 'LONG' if pnl >= 0 else 'SHORT'


def fetch_and_filter_trades(exchange, period: str, target_usdt: Optional[float], tolerance: float) -> List[Dict[str, Any]]:
    raw_trades = exchange.get_closed_pnl(period=period) or []
    filtered: List[Dict[str, Any]] = []
    
    for trade in raw_trades:
        entry_price = safe_float(trade.get('entry_price'), 0.0) or 0.0
        exit_price = safe_float(trade.get('exit_price'), 0.0) or 0.0
        qty = safe_float(trade.get('qty'), 0.0) or 0.0
        position_value = safe_float(trade.get('position_value'))
        if position_value is None and entry_price and qty:
            position_value = abs(entry_price * qty)
        
        if target_usdt is not None and position_value is not None:
            if abs(position_value - target_usdt) > tolerance:
                continue
        elif target_usdt is not None:
            # Нет данных о размере позиции — пропускаем
            continue
        
        pnl = safe_float(trade.get('closed_pnl'), 0.0) or 0.0
        direction = infer_direction(trade.get('side'), entry_price, exit_price, pnl)
        roi = 0.0
        if position_value:
            roi = (pnl / position_value) * 100
        
        created_ts = trade.get('created_timestamp')
        close_ts = trade.get('close_timestamp') or trade.get('closeTime')
        filtered.append({
            'symbol': trade.get('symbol'),
            'direction': direction,
            'qty': qty,
            'position_value': position_value,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'roi': roi,
            'created_timestamp': created_ts,
            'close_timestamp': close_ts,
            'side': trade.get('side'),
            'exchange': trade.get('exchange', 'bybit'),
            'raw': trade
        })
    
    filtered.sort(key=lambda item: item.get('close_timestamp') or 0)
    return filtered


def build_history_payload(trades: List[Dict[str, Any]], batch_label: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    history_entries: List[Dict[str, Any]] = []
    trade_entries: List[Dict[str, Any]] = []
    
    for idx, trade in enumerate(trades, start=1):
        symbol = trade['symbol']
        direction = trade['direction']
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        qty = trade['qty']
        pnl = trade['pnl']
        roi = trade['roi']
        position_value = trade['position_value']
        
        close_ts = trade.get('close_timestamp')
        entry_ts = trade.get('created_timestamp') or close_ts
        entry_iso = ms_to_iso(entry_ts) or datetime.now(timezone.utc).isoformat()
        close_iso = ms_to_iso(close_ts) or entry_iso
        
        bot_id = f"exchange_import_{symbol}"
        trade_id = f"exchange_trade_{idx}_{int(close_ts or idx)}"
        
        entry_data = {
            'entry_price': entry_price,
            'position_size_usdt': position_value,
            'position_size_coins': qty,
            'source': 'exchange_api_import',
            'batch': batch_label
        }
        market_data = {
            'exit_price': exit_price,
            'close_timestamp': close_iso,
            'source': 'exchange_api_import',
            'batch': batch_label
        }
        
        open_entry = {
            'id': f"{trade_id}_open",
            'timestamp': entry_iso,
            'action_type': 'POSITION_OPENED',
            'action_name': ACTION_TYPES['POSITION_OPENED'],
            'bot_id': bot_id,
            'symbol': symbol,
            'direction': direction,
            'size': qty,
            'entry_price': entry_price,
            'stop_loss': None,
            'take_profit': None,
            'decision_source': 'EXCHANGE_IMPORT',
            'ai_decision_id': None,
            'ai_confidence': None,
            'ai_signal': None,
            'rsi': None,
            'trend': None,
            'details': f"Импортирована позиция {direction} для {symbol}: размер {qty:.6f}, вход {entry_price:.6f} [EXCHANGE_IMPORT]",
            'source': 'exchange_api_import',
            'batch': batch_label
        }
        
        close_entry = {
            'id': f"{trade_id}_close",
            'timestamp': close_iso,
            'action_type': 'POSITION_CLOSED',
            'action_name': ACTION_TYPES['POSITION_CLOSED'],
            'bot_id': bot_id,
            'symbol': symbol,
            'direction': direction,
            'exit_price': exit_price,
            'pnl': pnl,
            'roi': roi,
            'reason': 'EXCHANGE_IMPORT',
            'decision_source': 'EXCHANGE_IMPORT',
            'ai_decision_id': None,
            'ai_confidence': None,
            'is_successful': pnl > 0,
            'details': f"Закрыта позиция {direction} для {symbol}: выход {exit_price:.6f}, PnL {pnl:.4f} USDT ({roi:.2f}%) [EXCHANGE_IMPORT]",
            'entry_data': entry_data,
            'market_data': market_data,
            'source': 'exchange_api_import',
            'batch': batch_label
        }
        
        trade_entry = {
            'id': trade_id,
            'timestamp': entry_iso,
            'bot_id': bot_id,
            'symbol': symbol,
            'direction': direction,
            'size': qty,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'roi': roi,
            'status': 'CLOSED',
            'decision_source': 'EXCHANGE_IMPORT',
            'ai_decision_id': None,
            'ai_confidence': None,
            'is_simulated': False,
            'is_real': True,
            'entry_data': entry_data,
            'exit_market_data': market_data,
            'close_timestamp': close_iso,
            'close_reason': 'EXCHANGE_IMPORT',
            'source': 'exchange_api_import',
            'position_size_usdt': position_value,
            'position_size_coins': qty,
            'batch': batch_label
        }
        
        history_entries.extend([open_entry, close_entry])
        trade_entries.append(trade_entry)
    
    return history_entries, trade_entries


def backup_history_file(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".backup_{timestamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser(description="Пересборка bot_history.json из истории биржи")
    parser.add_argument('--target-usdt', type=float, default=5.0, help="Размер позиции (USDT), который считаем реальным (default=5)")
    parser.add_argument('--tolerance', type=float, default=0.6, help="Допустимое отклонение размера (default=0.6)")
    parser.add_argument('--period', type=str, default='all', help="Период загрузки истории (all/day/week/month/...)")
    parser.add_argument('--output', type=str, default=HISTORY_FILE, help="Путь к bot_history.json")
    parser.add_argument('--dry-run', action='store_true', help="Только показать статистику, не записывая файл")
    args = parser.parse_args()
    
    exchange, exchange_name = load_exchange()
    trades = fetch_and_filter_trades(exchange, args.period, args.target_usdt, args.tolerance)
    
    if not trades:
        print("⚠️ Не найдено ни одной сделки, подходящей под фильтр.")
        sys.exit(1)
    
    print(f"✅ Получено {len(trades)} сделок с биржи {exchange_name} (период: {args.period})")
    
    history_entries, trade_entries = build_history_payload(trades, batch_label=datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    if args.dry_run:
        print("ℹ️ DRY-RUN: файл bot_history.json не изменён.")
        print(json.dumps({
            'history_entries': len(history_entries),
            'trade_entries': len(trade_entries),
            'sample_trade': trade_entries[0] if trade_entries else {}
        }, ensure_ascii=False, indent=2))
        return
    
    output_path = Path(args.output)
    backup_path = backup_history_file(output_path)
    if backup_path:
        print(f"💾 Создан бэкап: {backup_path}")
    
    manager = BotHistoryManager(history_file=str(output_path))
    manager.history = history_entries
    manager.trades = trade_entries
    manager._save_history()
    
    print(f"🎉 bot_history.json обновлён: {len(trade_entries)} сделок, {len(history_entries)} записей истории.")


if __name__ == '__main__':
    main()

