#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 Диагностика таймаутов RSI на слабом ПК

Запуск: python scripts/diagnose_rsi_timeout.py

Симулирует батч RSI как в production: 2 воркера, батч 25, timeout 90с.
Проверяет, успевает ли батч завершиться без таймаута.
"""
import os
import sys
import time
import concurrent.futures

if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

# Тестовые настройки — как aggressive (2 воркера, батч 25, timeout 90)
RSI_WORKERS = 2
RSI_BATCH_SIZE = 25
RSI_BATCH_TIMEOUT = 90

PROBLEM_SYMBOLS = ['BANK', 'BERA', 'BB', 'ATH', 'BARD', 'BABY', 'BAND', 'BEAM']

def run_diagnostic():
    print("=" * 70)
    print("🔍 ДИАГНОСТИКА RSI TIMEOUT (слабый ПК)")
    print("=" * 70)
    t0 = time.time()

    from bot_engine.config_loader import get_current_timeframe, reload_config
    reload_config()
    tf = get_current_timeframe() or '6h'
    print(f"Таймфрейм: {tf}")

    from bots_modules.imports_and_globals import coins_rsi_data, bots_data, get_exchange
    from bots_modules.maturity import get_maturity_timeframe
    maturity_tf = get_maturity_timeframe()
    print(f"Maturity TF: {maturity_tf} (при != {tf} → API для незрелых)")
    print()

    # 1. Загрузка свечей для тестовых символов
    candles_cache = coins_rsi_data.get('candles_cache') or {}
    exch = get_exchange()
    if not exch:
        print("⚠️ Биржа не инициализирована.")
        print("   Вариант 1: Запустите bots.py, дождитесь загрузки свечей, затем в другом окне:")
        print("   python scripts/diagnose_rsi_timeout.py")
        print("   Вариант 2: Инициализируйте exchange (init_bot_service)")
        try:
            from bots_modules.init_functions import init_bot_service
            init_bot_service()
            exch = get_exchange()
        except Exception as e:
            print(f"   init_bot_service: {e}")
    if not exch:
        return

    from bots_modules.filters import get_coin_candles_only
    symbols_to_load = PROBLEM_SYMBOLS
    if len(candles_cache) < RSI_BATCH_SIZE:
        try:
            all_pairs = exch.get_all_pairs()
            if all_pairs and len(all_pairs) >= RSI_BATCH_SIZE:
                symbols_to_load = [s for s in all_pairs[:RSI_BATCH_SIZE] if s and str(s).upper() != 'ALL']
                print(f"Загружаем свечи для {len(symbols_to_load)} символов (симуляция батча)...")
        except Exception as e:
            print(f"get_all_pairs: {e}, используем {len(PROBLEM_SYMBOLS)} символов")
    for sym in symbols_to_load:
        if sym not in candles_cache or tf not in candles_cache.get(sym, {}):
            t = time.time()
            r = get_coin_candles_only(sym, exch, tf, bulk_mode=True, bulk_limit=400)
            ms = (time.time() - t) * 1000
            if len(symbols_to_load) <= 12:
                print(f"Загрузка {sym}: {ms:.0f}ms, candles={len(r.get('candles', [])) if r else 0}")
            if r and r.get('candles'):
                if sym not in candles_cache:
                    candles_cache[sym] = {}
                candles_cache[sym][tf] = {'candles': r['candles'], 'timeframe': tf}
    coins_rsi_data['candles_cache'] = candles_cache
    print(f"В кэше: {len([s for s in candles_cache if tf in candles_cache.get(s, {})])} символов\n")

    import bots_modules.filters as filters_mod

    copy_auto = (bots_data.get('auto_bot_config') or {}).copy()
    copy_ind = (bots_data.get('individual_coin_settings') or {}).copy()

    # 3. ПАРАЛЛЕЛЬНЫЙ батч как в production (2 воркера, timeout 90с)
    symbols_to_test = [s for s in candles_cache if tf in candles_cache.get(s, {})][:RSI_BATCH_SIZE]

    print(f"\n{'=' * 70}")
    print(f"🔥 ТЕСТ БАТЧА: {RSI_WORKERS} воркеров, {len(symbols_to_test)} символов, timeout {RSI_BATCH_TIMEOUT}с")
    print("=" * 70)

    done_set = set()
    remaining = set()
    deadline = time.time() + RSI_BATCH_TIMEOUT

    def _process(sym):
        return filters_mod.get_coin_rsi_data_for_timeframe(
            sym, exch, tf,
            _auto_config=copy_auto,
            _individual_settings_cache=copy_ind,
            _skip_api_if_no_cache=True
        )

    batch_start = time.time()
    last_log = batch_start
    with concurrent.futures.ThreadPoolExecutor(max_workers=RSI_WORKERS) as ex:
        future_to_sym = {ex.submit(_process, s): s for s in symbols_to_test}
        remaining = set(future_to_sym.keys())
        while remaining and time.time() < deadline:
            partial_done, remaining = concurrent.futures.wait(
                remaining, timeout=1, return_when=concurrent.futures.FIRST_COMPLETED
            )
            done_set |= partial_done
            now = time.time()
            if now - last_log >= 5:
                print(f"   Готово {len(done_set)}/{len(symbols_to_test)}, осталось {len(remaining)} ({now - batch_start:.0f}с)")
                last_log = now

    batch_elapsed = time.time() - batch_start
    ok_count = 0
    for fut in done_set:
        try:
            if fut.result(timeout=1):
                ok_count += 1
        except Exception:
            pass

    timeout_count = len(remaining)
    print(f"\nРезультат: {ok_count} ok, {timeout_count} timeout за {batch_elapsed:.1f}с")
    if remaining:
        pending_syms = [future_to_sym[f] for f in remaining if f in future_to_sym]
        print(f"⚠️ TIMEOUT: не завершено {timeout_count} — {pending_syms[:8]}")
    else:
        print("✅ Батч завершён без таймаута")

    # 4. Итоговый отчёт
    print("\n" + "=" * 70)
    print("📊 ИТОГ")
    print("=" * 70)
    print(f"Время: {(time.time() - t0):.1f}с")
    if timeout_count > 0:
        print("→ Включи RSI_AGGRESSIVE_LOW_RESOURCE = True в bot_config (2 воркера, батч 25, timeout 90с)")

if __name__ == '__main__':
    run_diagnostic()
