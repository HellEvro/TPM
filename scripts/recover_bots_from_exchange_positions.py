#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Восстановление записей ботов в БД (таблица bots) по открытым позициям на бирже.

Когда записи в bots_data.db были случайно стёрты (пустое сохранение), все позиции
на бирже начинают отображаться как «ручные». Этот скрипт:
1. Загружает текущие открытые позиции с биржи (get_positions).
2. Загружает уже существующие боты из bots_data.db.
3. Для каждой позиции на бирже, для которой нет записи в таблице bots,
   создаёт минимальную запись бота (in_position_long/in_position_short).
4. Сохраняет объединённый список в БД.

После запуска перезапустите bots.py — боты подхватятся из БД, позиции снова
будут отображаться как боты, а не как ручные.

Запуск (остановите bots.py перед запуском):
    python scripts/recover_bots_from_exchange_positions.py

Опции:
    --dry-run   Только показать, каких ботов не хватает, не писать в БД.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_exchange():
    try:
        from app.config import EXCHANGES, ACTIVE_EXCHANGE
    except ImportError as e:
        raise RuntimeError("Не удалось импортировать app.config. Проверьте configs.") from e
    name = ACTIVE_EXCHANGE
    cfg = EXCHANGES.get(name, {})
    if not cfg or not cfg.get('enabled', True):
        raise RuntimeError(f"Для {name} нет активных API ключей.")
    api_key = cfg.get('api_key')
    api_secret = cfg.get('api_secret')
    passphrase = cfg.get('passphrase')
    if not api_key or not api_secret:
        raise RuntimeError("API ключи для биржи не заполнены.")
    from exchanges.exchange_factory import ExchangeFactory
    exchange = ExchangeFactory.create_exchange(name, api_key, api_secret, passphrase)
    return exchange


def main():
    parser = argparse.ArgumentParser(description="Восстановление записей ботов в БД из открытых позиций на бирже")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, не записывать в БД")
    args = parser.parse_args()

    print("=" * 60)
    print("ВОССТАНОВЛЕНИЕ БОТОВ ИЗ ОТКРЫТЫХ ПОЗИЦИЙ НА БИРЖЕ")
    print("=" * 60)

    # 1. Биржа
    try:
        exchange = load_exchange()
        print("\n[1] Биржа подключена.")
    except Exception as e:
        print(f"\n[ОШИБКА] Биржа: {e}")
        return 1

    # 2. Позиции с биржи
    try:
        result = exchange.get_positions()
        if isinstance(result, tuple):
            positions_list, _ = result
        else:
            positions_list = result or []
        print(f"[2] С биржи получено позиций: {len(positions_list)}")
    except Exception as e:
        print(f"[ОШИБКА] Позиции с биржи: {e}")
        return 1

    if not positions_list:
        print("\nНет открытых позиций на бирже. Восстанавливать нечего.")
        return 0

    # 3. Текущие боты из БД
    from bot_engine.bots_database import get_bots_database
    db = get_bots_database()
    state = db.load_bots_state()
    existing_bots = state.get("bots") or {}
    print(f"[3] В БД уже записей ботов: {len(existing_bots)}")

    # 4. Строим минимальную запись бота из позиции (формат, как в load_bots_state)
    now_iso = datetime.now().isoformat()
    default_tf = "6h"
    try:
        from bot_engine.config_loader import get_current_timeframe
        default_tf = get_current_timeframe() or default_tf
    except Exception:
        pass

    to_add = {}
    for pos in positions_list:
        symbol = (pos.get("symbol") or "").replace("USDT", "").strip().upper()
        if not symbol:
            continue
        if symbol in existing_bots:
            continue
        side = (pos.get("side") or "").strip()
        if "long" in side.lower() or side == "Buy":
            status = "in_position_long"
            position_side = "LONG"
        else:
            status = "in_position_short"
            position_side = "SHORT"
        size = float(pos.get("size") or 0)
        avg_price = float(pos.get("avg_price") or pos.get("entry_price") or 0)
        pnl = float(pos.get("pnl") or pos.get("unrealisedPnl") or 0)
        mark_price = float(pos.get("mark_price") or pos.get("current_price") or avg_price)
        leverage = float(pos.get("leverage") or 10)
        margin_usdt = (avg_price * size) / leverage if leverage else 0

        to_add[symbol] = {
            "symbol": symbol,
            "status": status,
            "auto_managed": True,
            "volume_mode": "usdt",
            "volume_value": margin_usdt,
            "entry_price": avg_price,
            "entry_time": now_iso,
            "entry_timestamp": now_iso,
            "position_side": position_side,
            "position_size": margin_usdt,
            "position_size_coins": size,
            "position_start_time": now_iso,
            "unrealized_pnl": pnl,
            "unrealized_pnl_usdt": pnl,
            "realized_pnl": 0,
            "leverage": leverage,
            "margin_usdt": margin_usdt,
            "max_profit_achieved": 0,
            "trailing_stop_price": None,
            "trailing_activation_threshold": 0,
            "trailing_activation_profit": 0,
            "trailing_locked_profit": 0,
            "trailing_active": False,
            "trailing_max_profit_usdt": 0,
            "trailing_step_usdt": 0,
            "trailing_step_price": None,
            "trailing_steps": 0,
            "trailing_reference_price": None,
            "trailing_last_update_ts": 0,
            "trailing_take_profit_price": None,
            "break_even_activated": False,
            "break_even_stop_price": None,
            "break_even_stop_set": False,
            "order_id": None,
            "current_price": mark_price,
            "last_price": mark_price,
            "last_rsi": None,
            "last_trend": None,
            "last_signal_time": None,
            "last_bar_timestamp": None,
            "entry_trend": None,
            "opened_by_autobot": True,
            "entry_timeframe": default_tf,
            "created_at": now_iso,
        }

    if not to_add:
        print("\nВсе позиции с биржи уже есть в БД. Дополнительно восстанавливать нечего.")
        return 0

    print(f"\n[4] Будет добавлено записей ботов: {len(to_add)}")
    for s in sorted(to_add.keys()):
        b = to_add[s]
        print(f"    {s}: {b['position_side']} @ {b['entry_price']}")

    if args.dry_run:
        print("\n[--dry-run] В БД не записываем. Запустите без --dry-run для сохранения.")
        return 0

    # 5. Объединяем с существующими и сохраняем
    merged = dict(existing_bots)
    merged.update(to_add)
    try:
        ok = db.save_bots_state(merged, {})
        if ok:
            print(f"\n[OK] В БД сохранено ботов: {len(merged)} (добавлено {len(to_add)}).")
            print("     Перезапустите bots.py, чтобы подхватить восстановленных ботов.")
        else:
            print("\n[ОШИБКА] Сохранение в БД не удалось. Проверьте логи.")
            return 1
    except Exception as e:
        print(f"\n[ОШИБКА] Сохранение: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
