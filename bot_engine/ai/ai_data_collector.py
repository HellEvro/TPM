#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль сбора данных для AI системы

Собирает данные из:
- bots.py (свечи, RSI, стохастик, сигналы)
- bot_history.py (история трейдов)
- Рыночные данные
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading

logger = logging.getLogger('AI.DataCollector')


class AIDataCollector:
    """
    Сборщик данных для обучения AI
    """
    
    def __init__(self, bots_service_url: str = 'http://127.0.0.1:5001',
                 app_service_url: str = 'http://127.0.0.1:5000'):
        """
        Инициализация сборщика данных
        
        Args:
            bots_service_url: URL сервиса bots.py
            app_service_url: URL сервиса app.py
        """
        self.bots_service_url = bots_service_url
        self.app_service_url = app_service_url
        self.data_dir = 'data/ai'
        self.lock = threading.Lock()
        
        # Создаем директорию для данных
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Файлы для хранения данных
        self.market_data_file = os.path.join(self.data_dir, 'market_data.json')
        self.bots_data_file = os.path.join(self.data_dir, 'bots_data.json')
        self.history_data_file = os.path.join(self.data_dir, 'history_data.json')
        
        logger.info("✅ AIDataCollector инициализирован")
    
    def _load_data(self, filepath: str) -> Dict:
        """Загрузить данные из файла"""
        try:
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except json.JSONDecodeError as json_error:
                    # Файл поврежден - удаляем его
                    logger.warning(f"⚠️ Файл {filepath} поврежден (JSON ошибка на позиции {json_error.pos})")
                    logger.info("🗑️ Удаляем поврежденный файл")
                    try:
                        os.remove(filepath)
                        logger.info("✅ Поврежденный файл удален")
                    except Exception as del_error:
                        logger.debug(f"⚠️ Не удалось удалить файл: {del_error}")
                    return {}
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных из {filepath}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        return {}
    
    def _save_data(self, filepath: str, data: Dict):
        """Сохранить данные в файл"""
        try:
            with self.lock:
                # Сохраняем во временный файл сначала
                temp_file = f"{filepath}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # Заменяем оригинальный файл
                if os.path.exists(filepath):
                    os.remove(filepath)
                os.rename(temp_file, filepath)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных в {filepath}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _call_bots_api(self, endpoint: str, method: str = 'GET', data: Dict = None, silent: bool = False) -> Optional[Dict]:
        """
        Вызов API bots.py (неблокирующий)
        
        Args:
            endpoint: API endpoint
            method: HTTP метод
            data: Данные для POST запроса
            silent: Если True, не логирует предупреждения (для фоновых попыток)
        """
        try:
            url = f"{self.bots_service_url}{endpoint}"
            
            # Короткий таймаут для быстрого ответа
            timeout = 3 if silent else 5
            
            if method == 'GET':
                response = requests.get(url, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=timeout)
            else:
                return None
            
            if response.status_code == 200:
                return response.json()
            else:
                if not silent:
                    logger.debug(f"⚠️ API {endpoint} вернул статус {response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            # Не логируем предупреждения для фоновых попыток
            if not silent:
                logger.debug(f"⚠️ Сервис bots.py недоступен по адресу {self.bots_service_url} (продолжаем работу)")
            return None
        except requests.exceptions.Timeout:
            if not silent:
                logger.debug(f"⏳ Таймаут подключения к bots.py (продолжаем работу)")
            return None
        except Exception as e:
            if not silent:
                logger.debug(f"⚠️ Ошибка вызова API {endpoint}: {e}")
            return None
    
    def collect_bots_data(self) -> Dict:
        """
        Сбор данных из bots.py
        
        Собирает:
        - Список ботов и их статусы
        - RSI данные для всех монет
        - Свечи
        - Сигналы блокировок
        """
        logger.debug("📊 Сбор данных из bots.py...")
        
        collected_data = {
            'timestamp': datetime.now().isoformat(),
            'bots': [],
            'rsi_data': {},
            'signals': {}
        }
        
        try:
            # Получаем список ботов
            bots_response = self._call_bots_api('/api/bots/list')
            if bots_response and bots_response.get('success'):
                collected_data['bots'] = bots_response.get('bots', [])
            
            # Получаем RSI данные для монет
            rsi_response = self._call_bots_api('/api/bots/coins-with-rsi')
            if rsi_response and rsi_response.get('success'):
                collected_data['rsi_data'] = rsi_response.get('coins', {})
            
            # Получаем статус ботов
            status_response = self._call_bots_api('/api/bots/status')
            if status_response and status_response.get('success'):
                collected_data['bots_status'] = status_response.get('status', {})
            
            # Сохраняем данные
            existing_data = self._load_data(self.bots_data_file)
            if 'history' not in existing_data:
                existing_data['history'] = []
            
            existing_data['history'].append(collected_data)
            
            # Ограничиваем историю (последние 1000 записей)
            if len(existing_data['history']) > 1000:
                existing_data['history'] = existing_data['history'][-1000:]
            
            existing_data['last_update'] = datetime.now().isoformat()
            existing_data['latest'] = collected_data
            
            self._save_data(self.bots_data_file, existing_data)
            
            logger.debug(f"✅ Собрано данных: {len(collected_data.get('bots', []))} ботов, {len(collected_data.get('rsi_data', {}))} монет с RSI")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сбора данных из bots.py: {e}")
        
        return collected_data
    
    def collect_history_data(self) -> Dict:
        """
        Сбор данных из bot_history.py
        
        Собирает:
        - Историю трейдов
        - Статистику торговли
        - Закрытые позиции с PnL
        """
        logger.debug("📊 Сбор данных из bot_history...")
        
        collected_data = {
            'timestamp': datetime.now().isoformat(),
            'trades': [],
            'statistics': {}
        }
        
        # ВАЖНО: Загружаем напрямую из data/bot_history.json
        try:
            bot_history_file = os.path.join('data', 'bot_history.json')
            if os.path.exists(bot_history_file):
                with open(bot_history_file, 'r', encoding='utf-8') as f:
                    bot_history_data = json.load(f)
                
                # Извлекаем сделки из bot_history.json
                bot_trades = bot_history_data.get('trades', [])
                if bot_trades:
                    collected_data['trades'].extend(bot_trades)
                    logger.debug(f"📊 Загружено {len(bot_trades)} сделок напрямую из bot_history.json")
        except json.JSONDecodeError as json_error:
            logger.warning(f"⚠️ Файл bot_history.json поврежден (JSON ошибка на позиции {json_error.pos})")
            logger.info("🗑️ Удаляем поврежденный файл, bots.py пересоздаст его автоматически")
            try:
                os.remove(bot_history_file)
                logger.info("✅ Поврежденный файл удален")
            except Exception as del_error:
                logger.debug(f"⚠️ Не удалось удалить файл: {del_error}")
        except Exception as e:
            logger.debug(f"⚠️ Ошибка загрузки bot_history.json: {e}")
        
        try:
            # Получаем историю сделок через API (дополняем прямую загрузку)
            trades_response = self._call_bots_api('/api/bots/trades?limit=1000')
            if trades_response and trades_response.get('success'):
                api_trades = trades_response.get('trades', [])
                # Объединяем с уже загруженными из bot_history.json (избегаем дубликатов)
                existing_ids = {t.get('id') for t in collected_data['trades'] if t.get('id')}
                for trade in api_trades:
                    trade_id = trade.get('id') or trade.get('timestamp')
                    if trade_id not in existing_ids:
                        collected_data['trades'].append(trade)
            
            # Получаем статистику
            stats_response = self._call_bots_api('/api/bots/statistics')
            if stats_response and stats_response.get('success'):
                collected_data['statistics'] = stats_response.get('statistics', {})
            
            # Получаем историю действий
            history_response = self._call_bots_api('/api/bots/history?limit=500')
            if history_response and history_response.get('success'):
                collected_data['actions'] = history_response.get('history', [])
            
            # Сохраняем данные
            existing_data = self._load_data(self.history_data_file)
            if 'history' not in existing_data:
                existing_data['history'] = []
            
            existing_data['history'].append(collected_data)
            
            # Ограничиваем историю
            if len(existing_data['history']) > 1000:
                existing_data['history'] = existing_data['history'][-1000:]
            
            existing_data['last_update'] = datetime.now().isoformat()
            existing_data['latest'] = collected_data
            
            self._save_data(self.history_data_file, existing_data)
            
            trades_count = len(collected_data.get('trades', []))
            logger.debug(f"✅ Собрано данных: {trades_count} сделок")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сбора данных из bot_history: {e}")
        
        return collected_data
    
    def load_full_candles_history(self) -> bool:
        """
        Загружает ВСЕ доступные свечи для всех монет
        
        Использует AICandlesLoader для загрузки максимального количества свечей
        (до 1000 свечей на монету вместо ~1000 из candles_cache.json)
        
        Returns:
            True если успешно загружено
        """
        try:
            from bot_engine.ai.ai_candles_loader import AICandlesLoader
            from bots_modules.imports_and_globals import get_exchange
            
            logger.info("=" * 80)
            logger.info("📊 ЗАГРУЗКА ВСЕХ ДОСТУПНЫХ СВЕЧЕЙ ДЛЯ AI ОБУЧЕНИЯ")
            logger.info("=" * 80)
            
            # Пробуем получить exchange с таймаутом и повторными попытками
            exchange = None
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    exchange = get_exchange()
                    if exchange:
                        break
                except Exception as e:
                    if attempt < max_attempts - 1:
                        logger.debug(f"   ⏳ Попытка {attempt + 1}/{max_attempts} получить биржу...")
                        import time
                        time.sleep(2)  # Короткая задержка между попытками
                    else:
                        logger.debug(f"⚠️ Ошибка получения биржи после {max_attempts} попыток: {e}")
            
            if not exchange:
                logger.debug("⚠️ Не удалось получить объект биржи (возможно bots.py еще не запущен)")
                logger.debug("💡 Продолжаем попытки в фоне, используем доступные данные")
                return False
            
            loader = AICandlesLoader(exchange_obj=exchange)
            success = loader.load_all_candles_full_history(max_workers=10)
            
            if success:
                logger.info("✅ Полная история свечей загружена в data/ai/candles_full_history.json")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки полной истории свечей: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def collect_market_data(self) -> Dict:
        """
        Сбор рыночных данных напрямую из файлов bots.py
        
        Использует УЖЕ СОБРАННЫЕ данные:
        - Свечи из data/candles_cache.json (которые bots.py собирает постоянно)
        - Индикаторы из API /api/bots/coins-with-rsi (RSI, тренды, сигналы)
        
        НЕ делает дополнительных запросов к бирже - использует данные которые уже есть!
        """
        logger.info("📊 Сбор рыночных данных из файлов bots.py...")
        
        collected_data = {
            'timestamp': datetime.now().isoformat(),
            'candles': {},
            'indicators': {}
        }
        
        try:
            # 1. Пробуем читать из полной истории свечей (data/ai/candles_full_history.json)
            # Если нет - используем candles_cache.json
            full_history_file = os.path.join('data', 'ai', 'candles_full_history.json')
            candles_cache_file = os.path.join('data', 'candles_cache.json')
            candles_data = {}
            source_file = None
            is_full_history = False
            
            # Приоритет: полная история > кэш bots.py
            if os.path.exists(full_history_file):
                try:
                    logger.info(f"📖 Чтение полной истории свечей из {full_history_file}...")
                    with open(full_history_file, 'r', encoding='utf-8') as f:
                        full_data = json.load(f)
                    
                    # Извлекаем свечи из структуры с метаданными
                    if 'candles' in full_data:
                        candles_data = full_data['candles']
                        source_file = full_history_file
                        is_full_history = True
                        logger.info(f"✅ Загружено полной истории для {len(candles_data)} монет")
                    elif isinstance(full_data, dict) and not full_data.get('metadata'):
                        # Если структура плоская (без метаданных)
                        candles_data = full_data
                        source_file = full_history_file
                        is_full_history = True
                        logger.info(f"✅ Загружено полной истории для {len(candles_data)} монет")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка чтения полной истории: {e}, пробуем candles_cache.json")
            
            # Если не удалось загрузить полную историю, используем кэш bots.py
            if not candles_data and os.path.exists(candles_cache_file):
                try:
                    logger.info(f"📖 Чтение свечей из {candles_cache_file}...")
                    with open(candles_cache_file, 'r', encoding='utf-8') as f:
                        candles_data = json.load(f)
                    
                    source_file = candles_cache_file
                    is_full_history = False
                    logger.info(f"✅ Загружено свечей для {len(candles_data)} монет из кэша bots.py")
                except json.JSONDecodeError as json_error:
                    logger.warning(f"⚠️ Файл candles_cache.json поврежден (JSON ошибка на позиции {json_error.pos})")
                    logger.info("🗑️ Удаляем поврежденный файл, bots.py пересоздаст его автоматически")
                    try:
                        os.remove(candles_cache_file)
                        logger.info("✅ Поврежденный файл удален")
                    except Exception as del_error:
                        logger.debug(f"⚠️ Не удалось удалить файл: {del_error}")
                    candles_data = {}
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка чтения candles_cache.json: {e}")
                    candles_data = {}
            
            # Обрабатываем свечи
            if candles_data:
                candles_count = 0
                total_candles = 0
                
                for symbol, candle_info in candles_data.items():
                    try:
                        candles = candle_info.get('candles', [])
                        if candles and len(candles) > 0:
                            collected_data['candles'][symbol] = {
                                'candles': candles,
                                'count': len(candles),
                                'timeframe': candle_info.get('timeframe', '6h'),
                                'last_update': candle_info.get('last_update') or candle_info.get('loaded_at'),
                                'source': source_file or 'candles_cache.json',
                                'is_full_history': is_full_history
                            }
                            candles_count += 1
                            total_candles += len(candles)
                            
                            # Логируем каждые 100 монет
                            if candles_count % 100 == 0:
                                logger.debug(f"📊 Обработано свечей: {candles_count} монет...")
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка обработки свечей для {symbol}: {e}")
                        continue
                
                logger.info(f"✅ Обработано свечей: {candles_count} монет, {total_candles} свечей всего")
            else:
                logger.warning(f"⚠️ Файл {candles_cache_file} не найден")
            
            # 2. Получаем индикаторы через API (RSI, тренды, сигналы)
            rsi_response = self._call_bots_api('/api/bots/coins-with-rsi')
            if rsi_response and rsi_response.get('success'):
                coins_data = rsi_response.get('coins', {})
                
                logger.info(f"📊 Получено индикаторов для {len(coins_data)} монет")
                
                # Сохраняем индикаторы
                indicators_count = 0
                for symbol, coin_data in coins_data.items():
                    try:
                        collected_data['indicators'][symbol] = {
                            'rsi': coin_data.get('rsi6h'),
                            'trend': coin_data.get('trend6h'),
                            'signal': coin_data.get('signal'),
                            'price': coin_data.get('price'),
                            'volume': coin_data.get('volume'),
                            'stochastic': coin_data.get('stochastic'),
                            'stoch_rsi_k': coin_data.get('stoch_rsi_k'),
                            'stoch_rsi_d': coin_data.get('stoch_rsi_d'),
                            'enhanced_rsi': coin_data.get('enhanced_rsi'),
                            'trend_analysis': coin_data.get('trend_analysis'),
                            'time_filter_info': coin_data.get('time_filter_info'),
                            'exit_scam_info': coin_data.get('exit_scam_info'),
                            'source': 'coins_rsi_data'
                        }
                        indicators_count += 1
                        
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка обработки индикаторов для {symbol}: {e}")
                        continue
                
                logger.info(f"✅ Обработано индикаторов: {indicators_count} монет")
            
            # Итоговая статистика
            logger.info("=" * 80)
            logger.info(f"✅ СБОР РЫНОЧНЫХ ДАННЫХ ЗАВЕРШЕН")
            logger.info(f"   📊 Свечи: {len(collected_data['candles'])} монет из candles_cache.json")
            logger.info(f"   📈 Индикаторы: {len(collected_data['indicators'])} монет из coins_rsi_data")
            logger.info(f"   💡 Все данные уже собраны bots.py - используем без дополнительных запросов к бирже!")
            logger.info("=" * 80)
            
            # Сохраняем данные
            existing_data = self._load_data(self.market_data_file)
            if 'history' not in existing_data:
                existing_data['history'] = []
            
            existing_data['history'].append(collected_data)
            
            # Ограничиваем историю
            if len(existing_data['history']) > 500:
                existing_data['history'] = existing_data['history'][-500:]
            
            existing_data['last_update'] = datetime.now().isoformat()
            existing_data['latest'] = collected_data
            
            self._save_data(self.market_data_file, existing_data)
            
        except Exception as e:
            logger.error(f"❌ Ошибка сбора рыночных данных: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return collected_data
    
    def get_training_data(self) -> Dict:
        """
        Получить данные для обучения
        
        Returns:
            Словарь с данными для обучения
        """
        return {
            'market_data': self._load_data(self.market_data_file),
            'bots_data': self._load_data(self.bots_data_file),
            'history_data': self._load_data(self.history_data_file)
        }
    
    def get_latest_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Получить последние рыночные данные для символа
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Словарь с рыночными данными или None
        """
        market_data = self._load_data(self.market_data_file)
        latest = market_data.get('latest', {})
        
        candles = latest.get('candles', {}).get(symbol)
        indicators = latest.get('indicators', {}).get(symbol)
        
        if candles or indicators:
            return {
                'candles': candles,
                'indicators': indicators,
                'timestamp': latest.get('timestamp')
            }
        
        return None

