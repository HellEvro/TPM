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
            
            # Загружаем существующий кэш
            existing_candles = self._load_existing_candles()
            
            # Загружаем свечи параллельно
            candles_data = {}
            loaded_count = 0
            failed_count = 0
            total_candles = 0
            
            # Определяем максимальный период для биржи
            exchange_type = self._detect_exchange_type(exchange)
            max_period = self._get_max_period_for_exchange(exchange_type)
            
            logger.info(f"📊 Используем период: {max_period} для биржи {exchange_type}")
            
            def load_symbol_candles(symbol):
                """Загружает свечи для одного символа с максимальным limit"""
                try:
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
                            
                            # Начинаем с текущего времени и идем в прошлое
                            end_time = int(time.time() * 1000)  # Текущее время в миллисекундах
                            max_candles_per_request = 2000  # Максимум свечей за запрос
                            request_count = 0
                            max_requests = 20  # Ограничиваем количество запросов (до ~10,000 дней истории)
                            
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
                                        for k in klines:
                                            candle = {
                                                'time': int(k[0]),
                                                'open': float(k[1]),
                                                'high': float(k[2]),
                                                'low': float(k[3]),
                                                'close': float(k[4]),
                                                'volume': float(k[5])
                                            }
                                            all_candles.append(candle)
                                        
                                        # Обновляем end_time для следующего запроса (берем timestamp самой старой свечи)
                                        oldest_timestamp = int(klines[-1][0])  # Последняя свеча в списке - самая старая
                                        end_time = oldest_timestamp - 1  # Минус 1 мс чтобы не получить ту же свечу
                                        
                                        request_count += 1
                                        
                                        # Если получили меньше чем лимит, значит данных больше нет
                                        if len(klines) < max_candles_per_request:
                                            break
                                        
                                        # Небольшая задержка между запросами
                                        time.sleep(0.2)
                                    else:
                                        # Ошибка API - прекращаем загрузку для этого символа
                                        break
                                        
                                except Exception as e:
                                    logger.debug(f"⚠️ Ошибка запроса свечей для {symbol} (запрос {request_count + 1}): {e}")
                                    break
                            
                            # Сортируем от старых к новым
                            all_candles.sort(key=lambda x: x['time'])
                            
                            if request_count > 0:
                                logger.debug(f"📊 {symbol}: Загружено {len(all_candles)} свечей за {request_count} запросов")
                        except Exception as e:
                            logger.debug(f"⚠️ Ошибка пагинации для {symbol}: {e}")
                            # Fallback: используем один запрос с limit=1000
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
                                    for k in klines:
                                        candle = {
                                            'time': int(k[0]),
                                            'open': float(k[1]),
                                            'high': float(k[2]),
                                            'low': float(k[3]),
                                            'close': float(k[4]),
                                            'volume': float(k[5])
                                        }
                                        all_candles.append(candle)
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
                            'timeframe': '6h',
                            'loaded_at': datetime.now().isoformat(),
                            'source': 'ai_full_history_loader',
                            'exchange_type': exchange_type,
                            'requests_made': request_count if exchange_type == 'bybit' else 1
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
                            candles_data[result['symbol']] = result
                            loaded_count += 1
                            total_candles += result['count']
                            
                            # Логируем прогресс каждые 50 монет
                            if loaded_count % 50 == 0:
                                logger.info(f"📊 Прогресс: {loaded_count}/{len(pairs)} монет, {total_candles} свечей...")
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
            logger.info(f"   ⚠️ Ошибок: {failed_count}")
            logger.info(f"   💾 Сохранено в: {self.candles_file}")
            logger.info("=" * 80)
            
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
        # Используем максимальный limit=1000 для получения максимума свечей
        # Для 6H свечей это даст ~250 дней истории (1000 * 6 часов = 6000 часов = ~250 дней)
        
        if exchange_type == 'bybit':
            # Bybit поддерживает limit=1000, но period='200' дает максимум за один запрос
            # Для получения всех свечей используем специальный метод с limit=1000
            return '1000'  # Используем максимальный limit
        elif exchange_type == 'binance':
            return '1000'  # До 1000 свечей
        elif exchange_type == 'okx':
            return '1000'  # До 1000 свечей
        
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
        """Сохранить свечи в файл"""
        try:
            # Сохраняем с метаданными
            data_to_save = {
                'metadata': {
                    'total_symbols': len(candles_data),
                    'total_candles': sum(info.get('count', 0) for info in candles_data.values()),
                    'timeframe': '6h',
                    'last_update': datetime.now().isoformat(),
                    'source': 'ai_full_history_loader'
                },
                'candles': candles_data
            }
            
            # Сохраняем во временный файл сначала
            temp_file = self.candles_file.with_suffix('.json.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            
            # Заменяем оригинальный файл
            if self.candles_file.exists():
                self.candles_file.unlink()
            temp_file.rename(self.candles_file)
            
            logger.info(f"✅ Свечи сохранены в {self.candles_file}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения свечей: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_candles_for_symbol(self, symbol: str) -> Optional[List[Dict]]:
        """Получить свечи для символа из файла"""
        candles_data = self._load_existing_candles()
        symbol_data = candles_data.get(symbol, {})
        return symbol_data.get('candles', [])

