#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль загрузки ВСЕХ доступных свечей для AI обучения

Загружает максимально возможное количество свечей для всех монет
и сохраняет в отдельный файл data/ai/candles_full_history.json
"""

import os
import json
import logging
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import concurrent.futures

logger = logging.getLogger('AI.CandlesLoader')


class AICandlesLoader:
    """
    Загрузчик свечей для AI обучения
    
    Загружает ВСЕ доступные свечи для всех монет (максимальный период)
    """
    
    def __init__(self, exchange_obj=None):
        """
        Инициализация загрузчика
        
        Args:
            exchange_obj: Объект биржи (если None, получает через API)
        """
        self.exchange = exchange_obj
        self.candles_file = Path('data/ai/candles_full_history.json')
        self.candles_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Максимальные периоды для разных бирж
        self.max_periods = {
            'bybit': '200',  # Bybit поддерживает до 200 свечей за раз, но можно запрашивать несколько раз
            'binance': '1000',  # Binance до 1000 свечей
            'okx': '1000'  # OKX до 1000 свечей
        }
        
        logger.info("✅ AICandlesLoader инициализирован")
    
    def get_exchange(self):
        """Получить объект биржи"""
        if self.exchange:
            return self.exchange
        
        try:
            # Пробуем получить через API bots.py
            import requests
            response = requests.get('http://127.0.0.1:5001/api/bots/exchange-info', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    exchange_type = data.get('exchange_type', 'bybit')
                    # Здесь можно создать объект биржи, но проще использовать API
                    return None
        except:
            pass
        
        # Пробуем импортировать напрямую
        try:
            from bots_modules.imports_and_globals import get_exchange
            return get_exchange()
        except:
            return None
    
    def load_all_candles_full_history(self, max_workers: int = 10) -> bool:
        """
        Загружает ВСЕ доступные свечи для всех монет
        
        Использует максимальный период для получения максимального количества свечей
        
        Args:
            max_workers: Количество параллельных потоков
        
        Returns:
            True если успешно загружено
        """
        logger.info("=" * 80)
        logger.info("📊 ЗАГРУЗКА ВСЕХ ДОСТУПНЫХ СВЕЧЕЙ ДЛЯ AI")
        logger.info("=" * 80)
        
        try:
            exchange = self.get_exchange()
            if not exchange:
                logger.error("❌ Не удалось получить объект биржи")
                return False
            
            # Получаем список всех пар
            pairs = exchange.get_all_pairs()
            if not pairs:
                logger.error("❌ Не удалось получить список пар")
                return False
            
            logger.info(f"📊 Найдено {len(pairs)} монет для загрузки")
            logger.info(f"📈 Загружаем максимально доступное количество свечей для каждой монеты...")
            
            # Загружаем существующий кэш для инкрементального обновления
            existing_candles_data = self._load_existing_candles()
            existing_candles = {}
            if existing_candles_data:
                if 'candles' in existing_candles_data:
                    existing_candles = existing_candles_data['candles']
                elif isinstance(existing_candles_data, dict) and not existing_candles_data.get('metadata'):
                    existing_candles = existing_candles_data
            
            if existing_candles:
                logger.info(f"📊 Найдено существующих данных для {len(existing_candles)} монет")
                logger.info("💡 Используем инкрементальное обновление: загружаем только новые свечи")
            else:
                logger.info("📊 Полная загрузка: файл не найден, загружаем все свечи с нуля")
            
            # Загружаем свечи параллельно (инкрементально или полностью)
            candles_data = {}
            loaded_count = 0
            updated_count = 0
            new_count = 0
            failed_count = 0
            total_candles = 0
            total_new_candles = 0
            
            # Определяем максимальный период для биржи
            exchange_type = self._detect_exchange_type(exchange)
            max_period = self._get_max_period_for_exchange(exchange_type)
            
            logger.info(f"📊 Используем период: {max_period} для биржи {exchange_type}")
            
            def load_symbol_candles(symbol):
                """Загружает свечи для одного символа (инкрементально или полностью)"""
                try:
                    # Проверяем существующие свечи для этого символа
                    existing_symbol_data = existing_candles.get(symbol, {})
                    existing_candles_list = existing_symbol_data.get('candles', []) if isinstance(existing_symbol_data, dict) else []
                    
                    # Определяем последнюю загруженную свечу
                    last_candle_time = None
                    if existing_candles_list:
                        # Сортируем по времени и берем самую новую
                        sorted_existing = sorted(existing_candles_list, key=lambda x: x.get('time', 0))
                        if sorted_existing:
                            last_candle_time = sorted_existing[-1].get('time', 0)
                            logger.debug(f"   📊 {symbol}: найдено {len(existing_candles_list)} существующих свечей, последняя: {datetime.fromtimestamp(last_candle_time/1000).strftime('%Y-%m-%d %H:%M')}")
                    
                    # Используем тот же метод что и bots.py, но с максимальным limit
                    # Для Bybit: используем прямой вызов API с limit=1000
                    all_candles = []
                    
                    # Определяем тип биржи и используем соответствующий метод
                    exchange_type = self._detect_exchange_type(exchange)
                    
                    if exchange_type == 'bybit':
                        # Для Bybit используем пагинацию для получения ВСЕХ доступных свечей
                        # Биржа может выдать максимум 2000 свечей за раз, поэтому делаем несколько запросов
                        try:
                            clean_sym = symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol
                            
                            # ИНКРЕМЕНТАЛЬНАЯ ЗАГРУЗКА: начинаем с последней загруженной свечи или с текущего времени
                            if last_candle_time:
                                # Загружаем только новые свечи (после последней загруженной)
                                end_time = int(time.time() * 1000)  # Текущее время
                                start_from_time = last_candle_time  # Начинаем с последней загруженной
                                logger.debug(f"   🔄 {symbol}: инкрементальное обновление (после {datetime.fromtimestamp(start_from_time/1000).strftime('%Y-%m-%d %H:%M')})")
                                incremental_mode = True
                            else:
                                # Полная загрузка: начинаем с текущего времени и идем в прошлое
                                end_time = int(time.time() * 1000)  # Текущее время в миллисекундах
                                start_from_time = None
                                logger.debug(f"   📊 {symbol}: полная загрузка истории")
                                incremental_mode = False
                            
                            max_candles_per_request = 1000  # Максимум свечей за запрос (лимит биржи)
                            request_count = 0
                            # ВАЖНО: Для качественного обучения нужно БОЛЬШЕ данных
                            # При полной загрузке: увеличиваем количество запросов для большего объема данных
                            # При инкрементальном обновлении: загружаем только новые свечи
                            if incremental_mode:
                                max_requests = 10  # Для инкрементального обновления достаточно 10 запросов
                                target_min_candles = 0  # Не проверяем минимум при обновлении
                            else:
                                max_requests = 50  # До 50,000 свечей (~12.5 лет истории на 6H)
                                target_min_candles = 2000  # Минимум свечей для качественного обучения
                            
                            # Делаем запросы пока не получим все доступные свечи
                            while request_count < max_requests:
                                try:
                                    response = exchange.client.get_kline(
                                        category="linear",
                                        symbol=f"{clean_sym}USDT",
                                        interval='360',  # 6H свечи
                                        limit=max_candles_per_request,
                                        end=str(end_time)  # Получаем свечи ДО этого времени
                                    )
                                    
                                    # Проверка rate limiting
                                    if response.get('retCode') == 10006:
                                        logger.debug(f"⚠️ Rate limit для {symbol}, ждем 1 секунду...")
                                        time.sleep(1)
                                        continue
                                    
                                    if response and response.get('retCode') == 0:
                                        klines = response['result']['list']
                                        
                                        if not klines or len(klines) == 0:
                                            # Больше нет свечей
                                            break
                                        
                                        # Добавляем свечи (они уже отсортированы от новых к старым)
                                        # При инкрементальном обновлении фильтруем только новые свечи
                                        new_candles_in_batch = 0
                                        for k in klines:
                                            candle_time = int(k[0])
                                            
                                            # При инкрементальном обновлении пропускаем старые свечи
                                            if incremental_mode and start_from_time and candle_time <= start_from_time:
                                                continue  # Эта свеча уже есть в базе
                                            
                                            candle = {
                                                'time': candle_time,
                                                'open': float(k[1]),
                                                'high': float(k[2]),
                                                'low': float(k[3]),
                                                'close': float(k[4]),
                                                'volume': float(k[5])
                                            }
                                            all_candles.append(candle)
                                            new_candles_in_batch += 1
                                        
                                        # Если в инкрементальном режиме не получили новых свечей - прекращаем
                                        if incremental_mode and new_candles_in_batch == 0:
                                            logger.debug(f"   ✅ {symbol}: новых свечей нет, данные актуальны")
                                            break
                                        
                                        # Обновляем end_time для следующего запроса (берем timestamp самой старой свечи)
                                        oldest_timestamp = int(klines[-1][0])  # Последняя свеча в списке - самая старая
                                        end_time = oldest_timestamp - 1  # Минус 1 мс чтобы не получить ту же свечу
                                        
                                        request_count += 1
                                        
                                        # Если получили меньше чем лимит, значит данных больше нет
                                        if len(klines) < max_candles_per_request:
                                            # Если получили меньше чем запросили - это конец истории
                                            break
                                        
                                        # Проверяем достигли ли минимума для качественного обучения
                                        if len(all_candles) >= target_min_candles and request_count >= 2:
                                            # Имеем достаточно данных, но продолжаем если можем получить больше
                                            logger.debug(f"   ✅ {symbol}: загружено {len(all_candles)} свечей (минимум {target_min_candles} достигнут)")
                                        
                                        # Небольшая задержка между запросами (уменьшаем для быстрой загрузки)
                                        time.sleep(0.1)
                                    else:
                                        # Ошибка API - прекращаем загрузку для этого символа
                                        break
                                        
                                except Exception as e:
                                    logger.debug(f"⚠️ Ошибка запроса свечей для {symbol} (запрос {request_count + 1}): {e}")
                                    break
                            
                            # Объединяем существующие и новые свечи
                            if existing_candles_list and all_candles:
                                # Объединяем и удаляем дубликаты
                                all_candles_dict = {c['time']: c for c in existing_candles_list}
                                for new_candle in all_candles:
                                    all_candles_dict[new_candle['time']] = new_candle
                                
                                # Преобразуем обратно в список и сортируем
                                all_candles = sorted(all_candles_dict.values(), key=lambda x: x['time'])
                                new_candles_count = len(all_candles) - len(existing_candles_list)
                            elif existing_candles_list:
                                # Только существующие свечи (новых нет)
                                all_candles = existing_candles_list
                                new_candles_count = 0
                            else:
                                # Только новые свечи (полная загрузка)
                                new_candles_count = len(all_candles)
                            
                            # Сортируем от старых к новым
                            all_candles.sort(key=lambda x: x['time'])
                            
                            if request_count > 0 or new_candles_count > 0:
                                total_candles_count = len(all_candles)
                                days_history = total_candles_count * 6 / 24  # Примерно дней истории для 6H свечей
                                
                                if incremental_mode and new_candles_count > 0:
                                    logger.debug(f"📊 {symbol}: Обновлено! Добавлено {new_candles_count} новых свечей (всего {total_candles_count}, ~{days_history:.0f} дней истории)")
                                elif incremental_mode:
                                    logger.debug(f"📊 {symbol}: Данные актуальны ({total_candles_count} свечей, ~{days_history:.0f} дней истории)")
                                else:
                                    logger.debug(f"📊 {symbol}: Загружено {total_candles_count} свечей за {request_count} запросов (~{days_history:.0f} дней истории)")
                                    
                                    # Предупреждение если недостаточно данных
                                    if total_candles_count < target_min_candles:
                                        logger.debug(f"   ⚠️ {symbol}: недостаточно свечей для качественного обучения ({total_candles_count} < {target_min_candles})")
                                    else:
                                        logger.debug(f"   ✅ {symbol}: достаточно свечей для качественного обучения")
                        except Exception as e:
                            logger.debug(f"⚠️ Ошибка пагинации для {symbol}: {e}")
                            # Fallback: используем один запрос с limit=1000 (тоже с инкрементальным обновлением)
                            try:
                                clean_sym = symbol.replace('USDT', '') if symbol.endswith('USDT') else symbol
                                response = exchange.client.get_kline(
                                    category="linear",
                                    symbol=f"{clean_sym}USDT",
                                    interval='360',
                                    limit=1000
                                )
                                if response and response.get('retCode') == 0:
                                    klines = response['result']['list']
                                    fallback_new_candles = []
                                    for k in klines:
                                        candle_time = int(k[0])
                                        
                                        # При инкрементальном обновлении пропускаем старые свечи
                                        if incremental_mode and start_from_time and candle_time <= start_from_time:
                                            continue
                                        
                                        candle = {
                                            'time': candle_time,
                                            'open': float(k[1]),
                                            'high': float(k[2]),
                                            'low': float(k[3]),
                                            'close': float(k[4]),
                                            'volume': float(k[5])
                                        }
                                        fallback_new_candles.append(candle)
                                    
                                    # Объединяем с существующими
                                    if existing_candles_list and fallback_new_candles:
                                        all_candles_dict = {c['time']: c for c in existing_candles_list}
                                        for new_candle in fallback_new_candles:
                                            all_candles_dict[new_candle['time']] = new_candle
                                        all_candles = sorted(all_candles_dict.values(), key=lambda x: x['time'])
                                        new_candles_count = len(all_candles) - len(existing_candles_list)
                                    elif existing_candles_list:
                                        all_candles = existing_candles_list
                                        new_candles_count = 0
                                    else:
                                        all_candles = fallback_new_candles
                                        new_candles_count = len(fallback_new_candles)
                                    
                                    all_candles.sort(key=lambda x: x['time'])
                            except:
                                pass
                    else:
                        # Для других бирж используем стандартный метод
                        chart_response = exchange.get_chart_data(symbol, '6h', max_period)
                        if chart_response and chart_response.get('success'):
                            candles = chart_response['data'].get('candles', [])
                            if candles:
                                all_candles.extend(candles)
                    
                    if all_candles:
                        return {
                            'symbol': symbol,
                            'candles': all_candles,
                            'count': len(all_candles),
                            'new_count': new_candles_count if 'new_candles_count' in locals() else len(all_candles),
                            'timeframe': '6h',
                            'loaded_at': datetime.now().isoformat(),
                            'last_candle_time': max(c['time'] for c in all_candles) if all_candles else None,
                            'source': 'ai_full_history_loader',
                            'exchange_type': exchange_type,
                            'requests_made': request_count if exchange_type == 'bybit' else 1,
                            'incremental': incremental_mode if 'incremental_mode' in locals() else False
                        }
                    return None
                    
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка загрузки свечей для {symbol}: {e}")
                    return None
            
            # Загружаем параллельно
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(load_symbol_candles, symbol): symbol for symbol in pairs}
                
                for future in concurrent.futures.as_completed(futures):
                    symbol = futures[future]
                    try:
                        result = future.result()
                        if result:
                            symbol = result['symbol']
                            candles_data[symbol] = result
                            loaded_count += 1
                            total_candles += result['count']
                            total_new_candles += result.get('new_count', 0)
                            
                            if result.get('incremental', False):
                                updated_count += 1
                            else:
                                new_count += 1
                            
                            # Логируем прогресс каждые 50 монет
                            if loaded_count % 50 == 0:
                                logger.info(f"📊 Прогресс: {loaded_count}/{len(pairs)} монет, {total_candles} свечей (новых: {total_new_candles})...")
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка для {symbol}: {e}")
                        failed_count += 1
            
            # Объединяем с существующими данными
            if existing_candles:
                logger.info(f"📊 Объединяем с существующими данными ({len(existing_candles)} монет)...")
                for symbol, data in existing_candles.items():
                    if symbol not in candles_data:
                        candles_data[symbol] = data
            
            # Сохраняем в файл
            self._save_candles(candles_data)
            
            logger.info("=" * 80)
            logger.info("✅ ЗАГРУЗКА СВЕЧЕЙ ЗАВЕРШЕНА")
            logger.info(f"   📊 Монет загружено: {loaded_count}")
            logger.info(f"   📈 Всего свечей: {total_candles}")
            logger.info(f"   ✅ Новых свечей добавлено: {total_new_candles}")
            logger.info(f"   🔄 Обновлено монет: {updated_count}")
            logger.info(f"   📊 Новых монет загружено: {new_count}")
            logger.info(f"   ⚠️ Ошибок: {failed_count}")
            logger.info(f"   💾 Сохранено в: {self.candles_file}")
            logger.info("=" * 80)
            
            if updated_count > 0:
                logger.info("💡 Инкрементальное обновление работает! При следующем запуске будут загружены только новые свечи.")
            
            return loaded_count > 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки свечей: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _detect_exchange_type(self, exchange) -> str:
        """Определяет тип биржи"""
        exchange_class = type(exchange).__name__.lower()
        if 'bybit' in exchange_class:
            return 'bybit'
        elif 'binance' in exchange_class:
            return 'binance'
        elif 'okx' in exchange_class:
            return 'okx'
        return 'bybit'  # По умолчанию
    
    def _get_max_period_for_exchange(self, exchange_type: str) -> str:
        """Получить максимальный период для биржи"""
        # ВАЖНО: Для качественного обучения нужно БОЛЬШЕ данных
        # Используем максимальный limit=2000 для получения максимума свечей за запрос
        # Для 6H свечей это даст ~500 дней истории за запрос (2000 * 6 часов = 12000 часов = ~500 дней)
        # С пагинацией можем загрузить до 20,000 свечей (~5 лет истории)
        
        if exchange_type == 'bybit':
            # Bybit поддерживает limit=1000 за запрос, но с пагинацией можем получить больше
            return '1000'  # Максимум за один запрос, но используем пагинацию
        elif exchange_type == 'binance':
            return '1000'  # До 1000 свечей за запрос
        elif exchange_type == 'okx':
            return '1000'  # До 1000 свечей за запрос
        
        return '1000'  # По умолчанию максимум
    
    def _load_existing_candles(self) -> Dict:
        """Загрузить существующие свечи из файла"""
        if not self.candles_file.exists():
            return {}
        
        try:
            with open(self.candles_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки существующих свечей: {e}")
            return {}
    
    def _save_candles(self, candles_data: Dict):
        """Сохранить свечи в файл (безопасно с retry логикой)"""
        import time
        import uuid
        max_retries = 5
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                # Сохраняем с метаданными
                data_to_save = {
                    'metadata': {
                        'total_symbols': len(candles_data),
                        'total_candles': sum(info.get('count', 0) if isinstance(info, dict) else 0 for info in candles_data.values()),
                        'timeframe': '6h',
                        'last_update': datetime.now().isoformat(),
                        'source': 'ai_full_history_loader'
                    },
                    'candles': candles_data
                }
                
                # Создаем уникальное имя временного файла
                temp_file = self.candles_file.with_suffix(f'.json.tmp.{uuid.uuid4().hex[:8]}')
                
                # Сохраняем во временный файл сначала
                try:
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                except Exception as write_error:
                    try:
                        if temp_file.exists():
                            temp_file.unlink()
                    except:
                        pass
                    raise write_error
                
                # Заменяем оригинальный файл атомарно
                if self.candles_file.exists():
                    try:
                        self.candles_file.unlink()
                    except PermissionError:
                        if attempt < max_retries - 1:
                            try:
                                if temp_file.exists():
                                    temp_file.unlink()
                            except:
                                pass
                            time.sleep(retry_delay * (attempt + 1))
                            continue
                        else:
                            raise
                
                # Переименовываем временный файл
                try:
                    temp_file.rename(self.candles_file)
                except PermissionError:
                    if attempt < max_retries - 1:
                        try:
                            if temp_file.exists():
                                temp_file.unlink()
                        except:
                            pass
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    else:
                        raise
                
                logger.info(f"✅ Свечи сохранены в {self.candles_file}")
                return
                
            except (PermissionError, OSError) as file_error:
                if attempt < max_retries - 1:
                    logger.debug(f"⚠️ Файл {self.candles_file} занят, повторная попытка {attempt + 1}/{max_retries}...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.warning(f"⚠️ Не удалось сохранить свечи после {max_retries} попыток (файл занят)")
                    logger.debug(f"   Ошибка: {file_error}")
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения свечей: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return
    
    def get_candles_for_symbol(self, symbol: str) -> Optional[List[Dict]]:
        """Получить свечи для символа из файла"""
        candles_data = self._load_existing_candles()
        symbol_data = candles_data.get(symbol, {})
        return symbol_data.get('candles', [])

