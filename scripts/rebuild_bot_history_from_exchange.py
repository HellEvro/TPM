#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ЭКСТРЕННЫЙ скрипт для восстановления потерянных сделок с биржи в БД.

ВАЖНО: Этот скрипт используется ТОЛЬКО в экстренных случаях для восстановления
потерянных сделок с биржи. В обычной работе сделки ботов сохраняются через bot_history.py.

Алгоритм:
1. Подключаемся к активной бирже из app.config.
2. Загружаем историю закрытых позиций (exchange.get_closed_pnl).
3. Фильтруем сделки по размеру позиции (по умолчанию около 5 USDT).
4. Сохраняет сделки с биржи в БД (таблица exchange_trades в ai_data.db).
5. Опционально сохраняет закрытые PnL в app_database (таблица closed_pnl).

Запуск:
    python scripts/rebuild_bot_history_from_exchange.py

Параметры:
    --target-usdt   Желаемый размер позиции в USDT (по умолчанию 5).
    --tolerance     Допустимое отклонение от target-usdt (по умолчанию 0.6).
    --period        Период загрузки истории (all/day/week/month/...).
    --save-closed-pnl Сохранять также в таблицу closed_pnl (по умолчанию False).
    --dry-run       Только показать статистику, не изменяя БД.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Гарантируем, что можно запускать из любого каталога/сервера
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bot_engine.ai.ai_database import get_ai_database
from bot_engine.app_database import AppDatabase
from exchanges.exchange_factory import ExchangeFactory


def load_exchange():
    try:
        from app.config import EXCHANGES, ACTIVE_EXCHANGE  # type: ignore
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


def load_active_bots() -> Dict[str, Dict[str, Any]]:
    """Загружает список активных ботов из bots_state.json"""
    bots_state_path = PROJECT_ROOT / 'data' / 'bots_state.json'
    if not bots_state_path.exists():
        return {}
    
    try:
        with open(bots_state_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            bots = data.get('bots', {})
            # Возвращаем словарь: symbol -> bot_data
            return {symbol: bot_data for symbol, bot_data in bots.items() if bot_data}
    except Exception as e:
        print(f"⚠️ Не удалось загрузить bots_state.json: {e}")
        return {}


def fetch_and_filter_trades(exchange, period: str, target_usdt: Optional[float], tolerance: float, exclude_active_bots: bool = True) -> List[Dict[str, Any]]:
    """
    Загружает и фильтрует сделки с биржи.
    
    Args:
        exclude_active_bots: Если True, исключает сделки для символов, которые есть в bots_state.json
    """
    raw_trades = exchange.get_closed_pnl(period=period) or []
    filtered: List[Dict[str, Any]] = []
    
    # Загружаем активных ботов для исключения
    active_bots = {}
    if exclude_active_bots:
        active_bots = load_active_bots()
        if active_bots:
            print(f"📋 Найдено {len(active_bots)} активных ботов в bots_state.json - их сделки будут исключены")
    
    for trade in raw_trades:
        symbol = trade.get('symbol')
        
        # КРИТИЧНО: Исключаем сделки для символов, которые есть в активных ботах
        # Эти сделки будут добавлены самим bots.py при запуске
        if exclude_active_bots and symbol and symbol in active_bots:
            continue
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


def build_exchange_trades_payload(trades: List[Dict[str, Any]], exchange_name: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Строит данные для сохранения в БД:
    - exchange_trades: для ai_database.save_exchange_trades()
    - closed_pnl: для app_database.save_closed_pnl()
    """
    exchange_trades: List[Dict[str, Any]] = []
    closed_pnl_list: List[Dict[str, Any]] = []
    
    for idx, trade in enumerate(trades, start=1):
        symbol = trade['symbol']
        direction = trade['direction']
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        qty = trade['qty']
        pnl = trade['pnl']
        roi = trade['roi']
        position_value = trade['position_value']
        
        close_ts = trade.get('close_timestamp') or 0
        entry_ts = trade.get('created_timestamp') or close_ts
        
        # Генерируем уникальный trade_id
        trade_id = f"exchange_import_{symbol}_{int(close_ts or idx)}_{idx}"
        
        # Данные для exchange_trades (ai_database)
        exchange_trade = {
            'id': trade_id,
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'timestamp': entry_ts,  # entry_time (timestamp в миллисекундах)
            'close_timestamp': close_ts,  # exit_time (timestamp в миллисекундах)
            'pnl': pnl,
            'roi': roi,
            'position_size_usdt': position_value,
            'position_size_coins': qty,
            'orderId': trade.get('raw', {}).get('orderId'),
            'source': 'exchange_api_import',
            'saved_timestamp': datetime.now(timezone.utc).isoformat(),
            'is_real': True
        }
        exchange_trades.append(exchange_trade)
        
        # Данные для closed_pnl (app_database)
        side = trade.get('side', 'BUY' if direction == 'LONG' else 'SELL')
        duration_seconds = None
        if entry_ts and close_ts and entry_ts > 0 and close_ts > 0:
            duration_seconds = int((close_ts - entry_ts) / 1000)  # Конвертируем из мс в секунды
        
        closed_pnl_entry = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'size': qty,
            'closed_pnl': pnl,
            'closed_pnl_percent': roi,
            'fee': trade.get('raw', {}).get('fee', 0),
            'close_timestamp': close_ts,
            'entry_timestamp': entry_ts if entry_ts > 0 else None,
            'duration_seconds': duration_seconds,
            'exchange': exchange_name
        }
        closed_pnl_list.append(closed_pnl_entry)
    
    return exchange_trades, closed_pnl_list


# Функция backup_history_file больше не нужна, так как мы пишем в БД


def main():
    parser = argparse.ArgumentParser(description="Импорт сделок с биржи в БД")
    parser.add_argument('--target-usdt', type=float, default=5.0, help="Размер позиции (USDT), который считаем реальным (default=5)")
    parser.add_argument('--tolerance', type=float, default=0.6, help="Допустимое отклонение размера (default=0.6)")
    parser.add_argument('--period', type=str, default='all', help="Период загрузки истории (all/day/week/month/...)")
    parser.add_argument('--save-closed-pnl', action='store_true', help="Также сохранять в таблицу closed_pnl")
    parser.add_argument('--dry-run', action='store_true', help="Только показать статистику, не записывая в БД")
    args = parser.parse_args()
    
    exchange, exchange_name = load_exchange()
    trades = fetch_and_filter_trades(exchange, args.period, args.target_usdt, args.tolerance, exclude_active_bots=True)
    
    if not trades:
        print("⚠️ Не найдено ни одной сделки, подходящей под фильтр.")
        sys.exit(1)
    
    print(f"✅ Получено {len(trades)} сделок с биржи {exchange_name} (период: {args.period})")
    
    # Строим данные для БД
    exchange_trades, closed_pnl_list = build_exchange_trades_payload(trades, exchange_name)
    
    if args.dry_run:
        print("ℹ️ DRY-RUN: БД не изменена.")
        print(json.dumps({
            'exchange_trades': len(exchange_trades),
            'closed_pnl_entries': len(closed_pnl_list),
            'sample_exchange_trade': exchange_trades[0] if exchange_trades else {},
            'sample_closed_pnl': closed_pnl_list[0] if closed_pnl_list else {}
        }, ensure_ascii=False, indent=2))
        return
    
    # Подключаемся к БД
    try:
        ai_db = get_ai_database()
        print("✅ Подключено к AI Database")
    except Exception as e:
        print(f"❌ Ошибка подключения к AI Database: {e}")
        sys.exit(1)
    
    # Сохраняем сделки в exchange_trades
    print(f"💾 Сохранение {len(exchange_trades)} сделок в таблицу exchange_trades...")
    saved_count = ai_db.save_exchange_trades(exchange_trades)
    print(f"✅ Сохранено {saved_count} сделок в exchange_trades (всего в БД: {ai_db.count_exchange_trades()})")
    
    # Опционально сохраняем в closed_pnl
    if args.save_closed_pnl:
        try:
            app_db = AppDatabase()
            print(f"💾 Сохранение {len(closed_pnl_list)} записей в таблицу closed_pnl...")
            success = app_db.save_closed_pnl(closed_pnl_list, exchange=exchange_name)
            if success:
                print(f"✅ Сохранено {len(closed_pnl_list)} записей в closed_pnl")
            else:
                print(f"⚠️ Ошибка сохранения в closed_pnl")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения в closed_pnl: {e}")
    
    print(f"🎉 Импорт завершён:")
    print(f"   📥 Сделки с биржи: {saved_count} сохранено в exchange_trades")
    if args.save_closed_pnl:
        print(f"   📊 Закрытые PnL: {len(closed_pnl_list)} сохранено в closed_pnl")


if __name__ == '__main__':
    main()

