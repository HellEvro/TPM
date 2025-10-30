#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест/утилита: точное сравнение RSI по файлу и по свечам Bybit

Запуск:
  python -m tests.test_trx_rsi_compare --symbol TRX --timeframe 1d
"""
import os
import sys
import json
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots_modules.candles_db import get_candles, save_candles
from bots_modules.calculations import calculate_rsi
from bots_modules.imports_and_globals import get_exchange

try:
    from bots_modules.api_endpoints import ensure_exchange_initialized
except Exception:
    ensure_exchange_initialized = None


def compare(symbol: str, timeframe: str) -> dict:
    # Инициализация биржи (если доступна)
    if ensure_exchange_initialized:
        try:
            ensure_exchange_initialized()
        except Exception:
            pass

    # 1) Из файла
    candles, rsi_file = get_candles(symbol, timeframe, return_rsi=True)
    closes_file = [c['close'] for c in candles] if candles else []
    rsi_calc_file = calculate_rsi(closes_file, 14) if len(closes_file) >= 15 else None

    # 2) Из Bybit API
    tf_map = {'1d': 'D', '1h': '60', '4h': '240', '6h': '360', '1w': 'W', '1m': '1', '5m': '5', '15m': '15', '30m': '30'}
    interval = tf_map.get(timeframe, 'D')
    api_supported = True
    rsi_calc_api = None
    closes_api = []
    try:
        ex = get_exchange()
        if not ex or not hasattr(ex, 'client'):
            api_supported = False
        else:
            r = ex.client.get_kline(category='linear', symbol=f'{symbol}USDT', interval=interval, limit=1000)
            kl = r['result']['list'] if r.get('retCode') == 0 else []
            kl = list(reversed(kl))  # старые -> новые
            closes_api = [float(k[4]) for k in kl]
            if len(closes_api) >= 15:
                rsi_calc_api = calculate_rsi(closes_api, 14)
    except Exception as e:
        api_supported = False

    result = {
        'symbol': symbol,
        'timeframe': timeframe,
        'file': {
            'candles': len(closes_file),
            'last_close': closes_file[-1] if closes_file else None,
            'rsi_cached': rsi_file,
            'rsi_recalc': rsi_calc_file,
        },
        'api': {
            'available': api_supported,
            'candles': len(closes_api),
            'last_close': closes_api[-1] if closes_api else None,
            'rsi_recalc': rsi_calc_api,
        },
        'last5_file': closes_file[-5:],
        'last5_api': closes_api[-5:],
    }

    # Если кэш в файле отличается от пересчёта — синхронизируем
    if candles and rsi_calc_file is not None and rsi_calc_file != rsi_file:
        save_candles(symbol, timeframe, candles, update_mode='append', rsi_value=rsi_calc_file)
        result['synced'] = True
    else:
        result['synced'] = False

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='TRX')
    parser.add_argument('--timeframe', default='1d')
    args = parser.parse_args()

    out = compare(args.symbol, args.timeframe)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()


