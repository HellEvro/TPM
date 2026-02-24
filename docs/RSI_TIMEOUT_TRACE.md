# Трассировка RSI: полный ход кода

## Цепочка вызовов

```
load_all_coins_rsi()
  └─ ThreadPoolExecutor.submit(get_coin_rsi_data_for_timeframe, symbol, ...)
       └─ get_coin_rsi_data_for_timeframe(symbol, exchange, timeframe, ...)
```

## get_coin_rsi_data_for_timeframe (filters.py:912)

| Шаг | Код | Время | Примечание |
|-----|-----|-------|------------|
| 1 | candles из coins_rsi_data['candles_cache'] | ~0ms | Кэш, без API |
| 2 | if not candles && !_skip_api → get_chart_data() | **API!** | При caller_provided не вызывается |
| 3 | calculate_rsi(closes, 14) | ~1-5ms | Локально |
| 4 | analyze_trend(symbol, candles_data=candles) | ~5-20ms | candles_data передан → без API |
| 5 | **Maturity block** | см. ниже | |
| 6 | time_filter (при signal=ENTER_LONG/SHORT) | ~1-10ms | check_rsi_time_filter |
| 7 | exit_scam, loss_reentry | ~1-5ms | Локально |

## Maturity block (узкое место)

```python
maturity_tf = get_maturity_timeframe()  # = текущий ТФ (6h) или 5m
maturity_candles = candles if timeframe == maturity_tf else None
if not maturity_candles and symbol in candles_cache:
    tc = candles_cache.get(symbol, {})
    if maturity_tf in tc:
        maturity_candles = tc[maturity_tf].get('candles')

if maturity_candles and len(maturity_candles) >= 15:
    # Быстрый путь: check_coin_maturity_with_storage
    mr = check_coin_maturity_with_storage(symbol, maturity_candles, config)
else:
    # МЕДЛЕННЫЙ ПУТЬ: check_coin_maturity_stored_or_verify
    # → get_coin_candles_only(symbol, None, maturity_tf) — API вызов!
    is_mature, reason = check_coin_maturity_stored_or_verify(symbol)
```

**Когда срабатывает API:**
- `maturity_tf != timeframe` (напр. maturity=5m, текущий=6h) И нет 5m в candles_cache
- Либо `maturity_candles` пусто

**check_coin_maturity_stored_or_verify:**
1. `is_coin_mature_stored(symbol)` — быстрый просмотр mature_coins_storage
2. Если False → `get_coin_candles_only(symbol, None, maturity_tf)` — **API**

## Почему 17 символов не успевают

1. **maturity API**: 17 символов не в `is_coin_mature_stored`, для них вызывается API
2. **GIL**: 4 воркера конкурируют за CPU; при параллельной инициализации AI — голодание
3. **Порядок**: последние в батче могут ждать дольше

## Решения

1. **maturity_tf = timeframe** — свечи уже в кэше, без API
2. **batch_timeout** — увеличить до 60–90с на слабых ПК
3. **batch_size** — уменьшить до 50 при low_resource
4. **Отложенная AI init** — уже сделано (performance API)
