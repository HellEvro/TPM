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
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных из {filepath}: {e}")
        return {}
    
    def _save_data(self, filepath: str, data: Dict):
        """Сохранить данные в файл"""
        try:
            with self.lock:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных в {filepath}: {e}")
    
    def _call_bots_api(self, endpoint: str, method: str = 'GET', data: Dict = None) -> Optional[Dict]:
        """Вызов API bots.py"""
        try:
            url = f"{self.bots_service_url}{endpoint}"
            
            if method == 'GET':
                response = requests.get(url, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=10)
            else:
                return None
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"⚠️ API {endpoint} вернул статус {response.status_code}")
                return None
                
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ Сервис bots.py недоступен по адресу {self.bots_service_url}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка вызова API {endpoint}: {e}")
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
        
        try:
            # Получаем историю сделок
            trades_response = self._call_bots_api('/api/bots/trades?limit=1000')
            if trades_response and trades_response.get('success'):
                collected_data['trades'] = trades_response.get('trades', [])
            
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
    
    def collect_market_data(self) -> Dict:
        """
        Сбор рыночных данных из bots.py
        
        Собирает:
        - Свечи для всех монет из coins_rsi_data (которые уже загружены)
        - Индикаторы (RSI, стохастик, EMA)
        - Тренды
        """
        logger.info("📊 Сбор рыночных данных из bots.py...")
        
        collected_data = {
            'timestamp': datetime.now().isoformat(),
            'candles': {},
            'indicators': {}
        }
        
        try:
            # Получаем RSI данные со свечами из bots.py
            rsi_response = self._call_bots_api('/api/bots/coins-with-rsi')
            if rsi_response and rsi_response.get('success'):
                coins_data = rsi_response.get('coins', {})
                
                logger.info(f"📊 Получено данных для {len(coins_data)} монет")
                
                # Для каждой монеты собираем свечи и индикаторы
                processed_count = 0
                for symbol, coin_data in coins_data.items():
                    try:
                        # Получаем свечи из данных монеты
                        candles = coin_data.get('candles')
                        if candles and len(candles) > 0:
                            collected_data['candles'][symbol] = {
                                'candles': candles,
                                'count': len(candles),
                                'timeframe': '6h'
                            }
                        
                        # Сохраняем индикаторы
                        collected_data['indicators'][symbol] = {
                            'rsi': coin_data.get('rsi6h'),
                            'trend': coin_data.get('trend6h'),
                            'signal': coin_data.get('signal'),
                            'price': coin_data.get('price'),
                            'volume': coin_data.get('volume'),
                            'stochastic': coin_data.get('stochastic')
                        }
                        
                        processed_count += 1
                        
                        # Логируем каждые 50 монет
                        if processed_count % 50 == 0:
                            logger.debug(f"📊 Обработано {processed_count}/{len(coins_data)} монет...")
                        
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка обработки данных для {symbol}: {e}")
                        continue
                
                logger.info(f"✅ Собрано рыночных данных: {processed_count} монет (свечи: {len(collected_data['candles'])}, индикаторы: {len(collected_data['indicators'])})")
            
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

