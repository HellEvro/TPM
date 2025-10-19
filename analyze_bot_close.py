#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Анализ: почему бот закрыл позицию"""

import json

print("="*80)
print("АНАЛИЗ: ПОЧЕМУ БОТ ЗАКРЫЛ ПОЗИЦИЮ AWE")
print("="*80)

# Читаем состояние бота
with open('data/bots_state.json', 'r', encoding='utf-8') as f:
    bots_state = json.load(f)

awe_bot = bots_state['bots'].get('AWE')
config = bots_state.get('auto_bot_config', {})

print("\n[ТЕКУЩЕЕ СОСТОЯНИЕ БОТА AWE]")
print(f"  Статус: {awe_bot.get('status')}")
print(f"  Entry Price: {awe_bot.get('entry_price')}")
print(f"  Position Side: {awe_bot.get('position_side')}")
print(f"  Order ID: {awe_bot.get('order_id')}")
print(f"  Создан: {awe_bot.get('created_at')}")
print(f"  Opened by Autobot: {awe_bot.get('opened_by_autobot')}")

print("\n[КОНФИГУРАЦИЯ AUTO BOT]")
print(f"  Max Loss %: {config.get('max_loss_percent')}")
print(f"  RSI Exit Long: {config.get('rsi_exit_long')}")
print(f"  RSI Exit Short: {config.get('rsi_exit_short')}")
print(f"  Avoid Down Trend: {config.get('avoid_down_trend')}")
print(f"  Avoid Up Trend: {config.get('avoid_up_trend')}")

print("\n[ВОЗМОЖНЫЕ ПРИЧИНЫ ЗАКРЫТИЯ]")
print("  1. Stop-Loss сработал (max_loss_percent=15%)")
print("  2. RSI вышел из зоны (exit_long=55)")
print("  3. Тренд изменился (avoid_down_trend=True)")
print("  4. Inactive Cleanup (бот посчитали неактивным)")
print("  5. Синхронизация с биржей (позиции не было на бирже)")

print("\n[РЕКОМЕНДАЦИИ]")
print("  🔍 ПРОВЕРЬТЕ ЛОГИ СЕРВЕРА на момент 04:52:39-04:52:41")
print("  🔍 Ищите сообщения:")
print("     - [BOT_CREATE] или [NEW_BOT_AWE]")
print("     - [TRADING] или [POSITION_UPDATE]")
print("     - [INACTIVE_CLEANUP]")
print("     - [SYNC_EXCHANGE]")

print("\n" + "="*80)
print("ОСНОВНАЯ ПРОБЛЕМА:")
print("="*80)
print("""
Бот ВХОДИТ в позицию (это подтверждает телеграм), но затем:
1. Либо позиция закрывается слишком быстро (стоп-лосс?)
2. Либо бот не обновляет свое состояние корректно
3. Либо синхронизация с биржей перезаписывает данные

РЕШЕНИЕ:
- Нужно добавить ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ в enter_position()
- Нужно проверить логику закрытия позиции
- Нужно убедиться что inactive_cleanup не удаляет свежие боты
""")
print("="*80)

