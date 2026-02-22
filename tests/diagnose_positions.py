#!/usr/bin/env python3
"""Диагностика позиций и баланса — прямой вызов Bybit API"""
import sys
import os
import importlib.util
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
# Загружаем app.py (не пакет app/)
_spec = importlib.util.spec_from_file_location("main_app", os.path.join(_root, "app.py"))
_main_app = importlib.util.module_from_spec(_spec)
sys.modules["main_app"] = _main_app
_spec.loader.exec_module(_main_app)

def main():
    current_exchange = _main_app.current_exchange
    DEMO_MODE = getattr(_main_app, 'DEMO_MODE', False)
    ACTIVE_EXCHANGE = getattr(_main_app, 'ACTIVE_EXCHANGE', '?')
    
    print("=== ДИАГНОСТИКА ПОЗИЦИЙ И БАЛАНСА ===\n")
    print(f"ACTIVE_EXCHANGE: {ACTIVE_EXCHANGE}")
    print(f"DEMO_MODE: {DEMO_MODE}")
    
    ex = current_exchange
    if not ex:
        print("Биржа не инициализирована")
        return
    
    # 1. Позиции
    print("\n--- Позиции (exchange.get_positions) ---")
    try:
        pos_list, rapid = ex.get_positions()
        print(f"Позиций: {len(pos_list or [])}")
        if pos_list:
            for p in (pos_list or [])[:5]:
                print(f"  {p.get('symbol')}: pnl={p.get('pnl')}, side={p.get('side')}")
        else:
            print("  (пусто)")
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. Баланс
    print("\n--- Баланс (exchange.get_wallet_balance) ---")
    try:
        w = ex.get_wallet_balance()
        print(f"total_balance: {w.get('total_balance')}")
        print(f"available_balance: {w.get('available_balance')}")
        print(f"realized_pnl: {w.get('realized_pnl')}")
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Margin mode (Bybit)
    if hasattr(ex, '_get_account_margin_mode'):
        print("\n--- Margin mode ---")
        try:
            mm = ex._get_account_margin_mode()
            print(f"margin_mode: {mm}")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    print("\n=== КОНЕЦ ===")

if __name__ == "__main__":
    main()
