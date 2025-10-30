#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сравнение RSI TRX (1d) из файла и по прямым свечам Bybit"""
import os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots_modules.candles_db import get_candles, save_candles
from bots_modules.calculations import calculate_rsi
from bots_modules.imports_and_globals import get_exchange
try:
    from bots_modules.api_endpoints import ensure_exchange_initialized
except Exception:
    ensure_exchange_initialized = None

def run(symbol='TRX', timeframe='1d'):
    result = {'symbol': symbol, 'timeframe': timeframe}

    # 1) Файл
    candles, rsi_file = get_candles(symbol, timeframe, return_rsi=True)
    closes_file = [c['close'] for c in candles] if candles else []
    rsi_calc_file = calculate_rsi(closes_file, 14) if len(closes_file) >= 15 else None

    # 2) Bybit API
    if ensure_exchange_initialized:
        try:
            ensure_exchange_initialized()
        except Exception:
            pass
    ex = get_exchange()
    if not ex or not hasattr(ex, 'client'):
        print(json.dumps({'error': 'exchange_not_initialized'}, ensure_ascii=False))
        return
    tf_map = {'1d':'D','1h':'60','4h':'240','6h':'360','1w':'W','1m':'1','5m':'5','15m':'15','30m':'30'}
    interval = tf_map.get(timeframe, 'D')
    r = ex.client.get_kline(category='linear', symbol=f'{symbol}USDT', interval=interval, limit=1000)
    kl = r['result']['list'] if r.get('retCode') == 0 else []
    kl = list(reversed(kl))
    closes_api = [float(k[4]) for k in kl]
    rsi_calc_api = calculate_rsi(closes_api, 14) if len(closes_api) >= 15 else None

    result.update({
        'rsi_file_cached': rsi_file,
        'rsi_file_recalc': rsi_calc_file,
        'rsi_api_recalc': rsi_calc_api,
        'last_price_file': closes_file[-1] if closes_file else None,
        'last_price_api': closes_api[-1] if closes_api else None,
        'counts': {'file': len(closes_file), 'api': len(closes_api)},
        'last5_file': closes_file[-5:],
        'last5_api': closes_api[-5:],
    })

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    run()


