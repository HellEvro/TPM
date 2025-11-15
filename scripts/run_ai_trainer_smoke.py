#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke-тест AITrainer: прогоняет обучение на 2 монетах и проверяет,
что индивидуальные настройки полностью записываются.

Запускать из корня проекта:
    python scripts/run_ai_trainer_smoke.py
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest import mock

from bot_engine.ai.ai_trainer import AITrainer

# Минимальный набор свечей/RSI — одинаков для обеих монет.
MOCK_SYMBOLS = ['TESTCOIN1', 'TESTCOIN2']
MOCK_CANDLES = [
    [1700000000000, 10.0, 11.0, 9.5, 10.5, 1200],
    [1700003600000, 10.5, 11.2, 10.3, 11.0, 1500],
    [1700007200000, 11.0, 11.5, 10.7, 11.4, 1800],
    [1700010800000, 11.4, 11.8, 11.1, 11.7, 2100],
    [1700014400000, 11.7, 12.0, 11.3, 11.2, 1900],
    [1700018000000, 11.2, 11.4, 10.8, 10.9, 1600],
    [1700021600000, 10.9, 11.3, 10.5, 11.1, 1400],
    [1700025200000, 11.1, 11.7, 10.9, 11.6, 2000],
]
MOCK_RSI = [35, 30, 25, 40, 70, 80, 60, 45]


def _mock_load_symbol_data(*_args, **_kwargs):
    return {
        'candles': MOCK_CANDLES,
        'rsi': MOCK_RSI,
        'times': [c[0] for c in MOCK_CANDLES],
        'prices': [c[4] for c in MOCK_CANDLES],
    }


def main() -> None:
    trainer = AITrainer()
    settings_written: dict[str, dict] = {}

    def fake_set_settings(symbol, settings, persist=True):
        settings_written[symbol] = settings
        print(f"[SMOKE] {symbol}: сохранено {len(settings)} полей (persist={persist})")

    with mock.patch('bot_engine.ai.ai_trainer._load_symbol_historical_data', _mock_load_symbol_data), \
         mock.patch('bots_modules.imports_and_globals.get_symbols_for_training', return_value=MOCK_SYMBOLS), \
         mock.patch('bots_modules.imports_and_globals.set_individual_coin_settings', side_effect=fake_set_settings), \
         mock.patch('bots_modules.imports_and_globals.get_individual_coin_settings', return_value={}), \
         mock.patch('bots_modules.imports_and_globals.load_individual_coin_settings', return_value={}):

        print("[SMOKE] Запуск AITrainer.train() ...")
        trainer.train()

    if not settings_written:
        print("[SMOKE] ❌ ни одна монета не сохранила индивидуальные настройки!")
        return

    for symbol in MOCK_SYMBOLS:
        payload = settings_written.get(symbol)
        if not payload:
            print(f"[SMOKE] ⚠️ {symbol}: настройки не сохранены")
            continue
        trained_at = payload.get('ai_trained_at')
        try:
            datetime.fromisoformat(trained_at) if trained_at else None
        except Exception:  # pragma: no cover
            trained_at = f"INVALID ({trained_at})"
        print(f"[SMOKE] {symbol}: {len(payload.keys())} полей, ai_trained_at={trained_at}")

    print("[SMOKE] Готово.")


if __name__ == '__main__':
    os.environ.setdefault('PYTHONUTF8', '1')
    main()

