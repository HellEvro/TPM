#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔍 Диагностика таймаутов RSI на слабом ПК

Запуск: python scripts/diagnose_rsi_timeout.py

Трассирует полный путь get_coin_rsi_data_for_timeframe для проблемных символов,
замеряет время каждого этапа и выявляет узкие места (maturity API, trend, time_filter).
"""
import os
import sys
import time

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

PROBLEM_SYMBOLS = ['BANK', 'BERA', 'BB', 'ATH', 'BARD', 'BABY', 'BAND', 'BEAM']
TRACE = {}  # symbol -> {step: ms}

def _trace(symbol, step, ms, extra=''):
    if symbol not in TRACE:
        TRACE[symbol] = {}
    TRACE[symbol][step] = ms
    print(f"    [{step}] {ms:.0f}ms {extra}")

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
    for sym in PROBLEM_SYMBOLS:
        if sym not in candles_cache or tf not in candles_cache.get(sym, {}):
            t = time.time()
            r = get_coin_candles_only(sym, exch, tf, bulk_mode=True, bulk_limit=400)
            ms = (time.time() - t) * 1000
            print(f"Загрузка {sym}: {ms:.0f}ms, candles={len(r.get('candles', [])) if r else 0}")
            if r and r.get('candles'):
                if sym not in candles_cache:
                    candles_cache[sym] = {}
                candles_cache[sym][tf] = {'candles': r['candles'], 'timeframe': tf}
    coins_rsi_data['candles_cache'] = candles_cache
    print()

    # 2. Трассировка через monkey-patch
    import bots_modules.filters as filters_mod
    from bots_modules.maturity import check_coin_maturity_with_storage

    _orig_check_stored = filters_mod.check_coin_maturity_stored_or_verify
    _orig_analyze = None
    try:
        from bots_modules import calculations
        _orig_analyze = calculations.analyze_trend
    except Exception:
        pass

    def traced_check_stored(symbol):
        t = time.time()
        try:
            res = _orig_check_stored(symbol)
            ms = (time.time() - t) * 1000
            if symbol in TRACE:
                TRACE[symbol]['maturity_api'] = ms
                print(f"    [maturity_api] {ms:.0f}ms {symbol} → stored_or_verify (API!)")
            return res
        except Exception as e:
            if symbol in TRACE:
                TRACE[symbol]['maturity_api_err'] = str(e)
            raise

    filters_mod.check_coin_maturity_stored_or_verify = traced_check_stored

    if _orig_analyze:
        def traced_analyze(symbol, exchange_obj=None, candles_data=None, timeframe=None, config=None):
            t = time.time()
            res = _orig_analyze(symbol, exchange_obj, candles_data, timeframe, config)
            ms = (time.time() - t) * 1000
            if symbol in TRACE:
                TRACE[symbol]['analyze_trend'] = ms
                from_api = "API" if candles_data is None else "cache"
                print(f"    [analyze_trend] {ms:.0f}ms {symbol} ({from_api})")
            return res
        calculations.analyze_trend = traced_analyze

    copy_auto = (bots_data.get('auto_bot_config') or {}).copy()
    copy_ind = (bots_data.get('individual_coin_settings') or {}).copy()

    # 3. Прогон каждого символа с пошаговой трассировкой
    for symbol in PROBLEM_SYMBOLS:
        if symbol not in candles_cache or tf not in candles_cache.get(symbol, {}):
            continue
        TRACE[symbol] = {}
        print(f"\n--- {symbol} ---")
        t_start = time.time()
        try:
            result = filters_mod.get_coin_rsi_data_for_timeframe(
                symbol, exch, tf,
                _auto_config=copy_auto,
                _individual_settings_cache=copy_ind,
                _skip_api_if_no_cache=True
            )
            total = (time.time() - t_start) * 1000
            TRACE[symbol]['total'] = total
            TRACE[symbol]['ok'] = result is not None
            print(f"  ИТОГО: {total:.0f}ms, ok={result is not None}")
        except Exception as e:
            total = (time.time() - t_start) * 1000
            TRACE[symbol]['total'] = total
            TRACE[symbol]['error'] = str(e)
            print(f"  ИТОГО: {total:.0f}ms, ОШИБКА: {e}")

    # 4. Итоговый отчёт
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 70)

    slow_total = [(s, TRACE[s]['total']) for s in TRACE if TRACE[s].get('total', 0) > 2000]
    api_calls = [(s, TRACE[s]['maturity_api']) for s in TRACE if 'maturity_api' in TRACE[s]]
    trend_slow = [(s, TRACE[s]['analyze_trend']) for s in TRACE if TRACE[s].get('analyze_trend', 0) > 500]

    if api_calls:
        print("\n⚠️ MATURITY API (check_coin_maturity_stored_or_verify → get_coin_candles_only):")
        for s, ms in sorted(api_calls, key=lambda x: -x[1]):
            print(f"   {s}: {ms:.0f}ms — символ НЕ в is_coin_mature_stored, загружаются свечи {maturity_tf}")
        print("   → Узкое место: API вызов для незрелых монет при maturity_tf != timeframe")

    if trend_slow:
        print("\n⚠️ Анализ тренда (analyze_trend) > 500ms:")
        for s, ms in trend_slow:
            print(f"   {s}: {ms:.0f}ms")

    if slow_total:
        print("\n⚠️ Медленные символы (total > 2s):")
        for s, ms in sorted(slow_total, key=lambda x: -x[1]):
            print(f"   {s}: {ms:.0f}ms")

    print("\n📌 РЕКОМЕНДАЦИИ:")
    if api_calls:
        print("   1. maturity_tf = timeframe (6h) в конфиге — свечи уже в кэше, без API")
    print("   2. Либо увеличить batch_timeout RSI (сейчас 40с)")
    print("   3. Либо уменьшить batch_size до 50 на слабых ПК")
    print(f"\nВремя диагностики: {(time.time() - t0):.1f}с")

if __name__ == '__main__':
    run_diagnostic()
