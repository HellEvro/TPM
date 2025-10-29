"""
Модуль загрузки свечей для всех монет

Включает:
- load_all_coins_candles_fast - быстрая загрузка свечей для всех монет
- Повторные попытки для неудачных монет
- Настраиваемые параметры через SystemConfig
"""

import logging
import concurrent.futures
import time
from datetime import datetime

logger = logging.getLogger('BotsService')


def load_all_coins_candles_fast():
    """⚡ БЫСТРАЯ загрузка ТОЛЬКО свечей для всех монет БЕЗ расчетов
    
    Использует настройки из SystemConfig:
    - CANDLE_LOADER_BATCH_SIZE - размер пакета
    - CANDLE_LOADER_MAX_WORKERS - количество потоков
    - CANDLE_LOADER_BATCH_TIMEOUT - таймаут пакета
    - CANDLE_LOADER_SINGLE_TIMEOUT - таймаут для одной монеты
    - CANDLE_LOADER_RETRY_ENABLED - включить повторные попытки
    - CANDLE_LOADER_BATCH_DELAY - задержка между пакетами
    """
    try:
        logger.debug("[CANDLES_FAST] Загрузка свечей...")
        
        # Импортируем из другого модуля
        from bots_modules.imports_and_globals import get_exchange, coins_rsi_data, get_timeframe
        from bot_engine.bot_config import SystemConfig
        from bots_modules.filters import get_coin_candles_only
        from bots_modules.candles_db import save_candles, save_candles_batch, init_candles_db, get_all_candles, get_cached_symbols_count
        
        # ✅ Инициализируем БД
        init_candles_db()
        
        # Получаем текущий таймфрейм
        current_tf = get_timeframe()
        
        # ✅ ПРОВЕРЯЕМ: есть ли уже данные в БД?
        # Сначала получаем биржу и список пар
        current_exchange = get_exchange()
        if not current_exchange:
            logger.error("[CANDLES_FAST] ❌ Биржа не инициализирована")
            return False
        
        pairs = current_exchange.get_all_pairs()
        if not pairs:
            logger.error("[CANDLES_FAST] ❌ Не удалось получить список пар")
            return False
        
        cached_count = get_cached_symbols_count(current_tf)
        
        # ✅ ВСЕГДА загружаем свежие данные с биржи для обновления свечей (включая незакрытые)
        logger.info(f"[CANDLES_FAST] 📊 Будет загрузка свежих данных с биржи для {len(pairs)} монет (в БД: {cached_count})")
        
        # Получаем настройки из конфига
        batch_size = SystemConfig.CANDLE_LOADER_BATCH_SIZE
        max_workers = SystemConfig.CANDLE_LOADER_MAX_WORKERS
        batch_timeout = SystemConfig.CANDLE_LOADER_BATCH_TIMEOUT
        single_timeout = SystemConfig.CANDLE_LOADER_SINGLE_TIMEOUT
        retry_enabled = SystemConfig.CANDLE_LOADER_RETRY_ENABLED
        batch_delay = SystemConfig.CANDLE_LOADER_BATCH_DELAY
        
        # ✅ Загружаем свечи с биржи для ВСЕХ монет (обновление данных)
        candles_cache = {}
        
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i:i + batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(pairs) + batch_size - 1)//batch_size
            
            # ✅ Загружаем ВСЕ монеты для обновления данных (включая уже загруженные)
            batch_to_load = batch
            
            logger.debug(f"[CANDLES_FAST] Пакет {batch_num}/{total_batches}: загрузка {len(batch_to_load)} монет...")
            
            # 🔄 ПОВТОРНЫЕ ПОПЫТКИ ДЛЯ ВСЕГО ПАКЕТА (до 5 раз)
            batch_attempt = 0
            max_batch_retries = 5
            batch_success_threshold = 0.8  # 80% успешных загрузок - приемлемо!
            
            while batch_attempt < max_batch_retries:
                batch_attempt += 1
                logger.info(f"[CANDLES_FAST] Пакет {batch_num}, попытка {batch_attempt}/{max_batch_retries}...")
                
                # Очищаем результаты текущей попытки (но не кэш уже загруженных)
                batch_candles = {}
                batch_failed_symbols = []
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_symbol = {
                        executor.submit(get_coin_candles_only, symbol, current_exchange): symbol 
                        for symbol in batch_to_load
                    }
                    
                    completed = 0
                    total_futures = len(future_to_symbol)
                    processed_futures = 0
                    
                    for future in concurrent.futures.as_completed(future_to_symbol, timeout=batch_timeout):
                        processed_futures += 1
                        symbol = future_to_symbol.get(future, 'UNKNOWN')
                        try:
                            result = future.result(timeout=single_timeout)
                            if result:
                                batch_candles[result['symbol']] = result
                                completed += 1
                                logger.debug(f"[CANDLES_FAST] ✅ {symbol}: Загружено")
                            else:
                                batch_failed_symbols.append(symbol)
                                logger.warning(f"[CANDLES_FAST] ⚠️ {symbol}: Результат None")
                        except Exception as e:
                            batch_failed_symbols.append(symbol)
                            logger.error(f"[CANDLES_FAST] ❌ {symbol}: Ошибка: {str(e)[:100]}")
                    
                    # Учитываем все необработанные фьючерсы (таймаут)
                    if processed_futures < total_futures:
                        logger.error(f"[CANDLES_FAST] ⚠️ Обработано только {processed_futures}/{total_futures} фьючерсов (таймаут?)")
                        for sym, fut in future_to_symbol.items():
                            if sym not in batch_candles and sym not in batch_failed_symbols:
                                batch_failed_symbols.append(sym)
                                logger.warning(f"[CANDLES_FAST] ❌ {sym}: Таймаут загрузки")
                    
                    # 🔄 ПОВТОРНЫЕ ПОПЫТКИ для отдельных неудачных монет в пакете
                    if batch_failed_symbols and retry_enabled:
                        logger.warning(f"[CANDLES_FAST] 🔄 Повтор для {len(batch_failed_symbols)} монет: {batch_failed_symbols[:5]}...")
                        for symbol in batch_failed_symbols:
                            try:
                                result = get_coin_candles_only(symbol, current_exchange)
                                if result:
                                    batch_candles[symbol] = result
                                    completed += 1
                                    logger.info(f"[CANDLES_FAST] ✅ {symbol}: Загружен при повторе")
                            except Exception as e:
                                logger.error(f"[CANDLES_FAST] ❌ {symbol}: Ошибка при повторе: {e}")
                
                # Проверяем успешность пакета
                success_rate = completed / len(batch)
                
                # Обновляем общий кэш
                candles_cache.update(batch_candles)
                
                if success_rate >= batch_success_threshold:
                    logger.info(f"[CANDLES_FAST] ✅ Пакет {batch_num}: загружено {completed}/{len(batch)} монет ({success_rate*100:.1f}%)")
                    break  # Успешно - переходим к следующему пакету
                else:
                    failed_count = len(batch) - completed
                    logger.warning(f"[CANDLES_FAST] ⚠️ Пакет {batch_num}: низкая успешность {completed}/{len(batch)} ({success_rate*100:.1f}%), неудач: {failed_count}")
                    
                    if batch_attempt < max_batch_retries:
                        logger.info(f"[CANDLES_FAST] 🔄 Повтор пакета {batch_num}... (попытка {batch_attempt + 1}/{max_batch_retries})")
                        time.sleep(1)  # Пауза перед повторной попыткой
                    else:
                        logger.error(f"[CANDLES_FAST] ❌ Пакет {batch_num}: не удалось загрузить после {max_batch_retries} попыток. Пропускаем.")
                        logger.error(f"[CANDLES_FAST] ❌ Неудачные монеты: {batch_failed_symbols[:10]}")
            
            # Пауза между пакетами
            time.sleep(batch_delay)
        
        # Итоговый отчет
        total_requested = len(pairs)
        total_loaded = len(candles_cache)
        missing = total_requested - total_loaded
        logger.info(f"[CANDLES_FAST] ✅ Загрузка завершена: {total_loaded}/{total_requested} монет (не загружено: {missing})")
        
        # ✅ ПАКЕТНОЕ сохранение - САМОЕ БЫСТРОЕ!
        current_tf = get_timeframe()
        
        # Формируем словарь {symbol: candles_list} для БД
        db_data = {}
        for symbol, candle_data in candles_cache.items():
            # candle_data может быть либо {'candles': [...]}, либо уже [...]
            if isinstance(candle_data, dict) and 'candles' in candle_data:
                db_data[symbol] = candle_data['candles']
            elif isinstance(candle_data, list):
                db_data[symbol] = candle_data
            else:
                logger.warning(f"[CANDLES_FAST] ⚠️ Неизвестный формат для {symbol}: {type(candle_data)}")
        
        # Сохраняем одним запросом в режиме append
        # Это обновляет существующие свечи и добавляет новые, включая последнюю незакрытую
        save_candles_batch(current_tf, db_data, update_mode='append')
        
        # ⚡ КРИТИЧНО: Сохраняем В ТОМ ЖЕ ФОРМАТЕ {symbol: [candles]} в память!
        try:
            # Преобразуем candles_cache из {symbol: {candles: [...]}} в {symbol: [...]}
            memory_cache = {}
            for symbol, candle_data in candles_cache.items():
                if isinstance(candle_data, dict) and 'candles' in candle_data:
                    memory_cache[symbol] = candle_data['candles']
                elif isinstance(candle_data, list):
                    memory_cache[symbol] = candle_data
                else:
                    memory_cache[symbol] = candle_data  # Fallback
            
            coins_rsi_data['candles_cache'] = memory_cache
            coins_rsi_data['last_candles_update'] = datetime.now().isoformat()
            logger.info(f"[CANDLES_FAST] ✅ Кэш сохранен: {len(memory_cache)} монет")
        except Exception as cache_error:
            logger.warning(f"[CANDLES_FAST] ⚠️ Ошибка сохранения кэша: {cache_error}")
        
        return True
        
    except Exception as e:
        logger.error(f"[CANDLES_FAST] ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

