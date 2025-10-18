#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПРОСТАЯ СИСТЕМА ТОРГОВЛИ
========================

Простая и понятная система для запуска ботов и входа в сделки
со ВСЕМИ существующими фильтрами и ИИ модулями.

Автор: AI Assistant
Дата: 2025-10-18
"""

import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s 📝 [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class SimpleTradingSystem:
    """
    ПРОСТАЯ СИСТЕМА ТОРГОВЛИ
    
    Принципы:
    1. ✅ Простота - минимум кода, максимум результата
    2. ✅ Надежность - все фильтры и ИИ включены
    3. ✅ Понятность - каждый шаг логируется
    4. ✅ Эффективность - быстрый вход/выход из позиций
    """
    
    def __init__(self):
        """Инициализация простой системы торговли"""
        self.running = False
        self.thread = None
        self.check_interval = 30  # Проверяем каждые 30 секунд
        
        # Импортируем все необходимые модули
        self._import_modules()
        
        # Инициализируем компоненты
        self._init_components()
        
        logger.info("🚀 ПРОСТАЯ СИСТЕМА ТОРГОВЛИ ИНИЦИАЛИЗИРОВАНА")
        logger.info("=" * 60)
    
    def _import_modules(self):
        """Импорт всех необходимых модулей"""
        try:
            # Основные модули
            from bots_modules.imports_and_globals import (
                bots_data, bots_data_lock, coins_rsi_data, rsi_data_lock,
                get_exchange, BOT_STATUS
            )
            self.bots_data = bots_data
            self.bots_data_lock = bots_data_lock
            self.coins_rsi_data = coins_rsi_data
            self.rsi_data_lock = rsi_data_lock
            self.get_exchange = get_exchange
            self.BOT_STATUS = BOT_STATUS
            
            # Фильтры
            from bots_modules.filters import (
                check_rsi_time_filter, test_exit_scam_filter,
                is_coin_mature_stored, get_coin_rsi_data
            )
            self.check_rsi_time_filter = check_rsi_time_filter
            self.test_exit_scam_filter = test_exit_scam_filter
            self.is_coin_mature_stored = is_coin_mature_stored
            self.get_coin_rsi_data = get_coin_rsi_data
            
            # ИИ модули
            from bot_engine.ai.ai_manager import AIManager
            self.ai_manager = AIManager()
            
            # Создание ботов
            from bots_modules.bot_class import NewTradingBot
            self.NewTradingBot = NewTradingBot
            
            logger.info("✅ Все модули успешно импортированы")
            
        except ImportError as e:
            logger.error(f"❌ Ошибка импорта модулей: {e}")
            raise
    
    def _init_components(self):
        """Инициализация компонентов системы"""
        try:
            # ИИ модули уже инициализированы при создании
            logger.info("✅ ИИ модули готовы к работе")
            
            # Инициализируем систему ботов
            from bots_modules.init_functions import init_bot_service
            init_bot_service()
            logger.info("✅ Система ботов инициализирована")
            
            # Получаем биржу
            self.exchange = self.get_exchange()
            if not self.exchange:
                raise Exception("Биржа не инициализирована")
            logger.info("✅ Биржа подключена")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации компонентов: {e}")
            raise
    
    def start(self):
        """Запуск системы торговли"""
        if self.running:
            logger.warning("⚠️ Система уже запущена")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._main_loop, daemon=True)
        self.thread.start()
        
        logger.info("🚀 ПРОСТАЯ СИСТЕМА ТОРГОВЛИ ЗАПУЩЕНА")
        logger.info(f"⏰ Проверка сигналов каждые {self.check_interval} секунд")
    
    def stop(self):
        """Остановка системы торговли"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹️ ПРОСТАЯ СИСТЕМА ТОРГОВЛИ ОСТАНОВЛЕНА")
    
    def _main_loop(self):
        """Основной цикл системы"""
        logger.info("🔄 Начинаем основной цикл торговли...")
        
        while self.running:
            try:
                # Проверяем Auto Bot статус
                if not self._is_auto_bot_enabled():
                    logger.debug("⏹️ Auto Bot выключен, пропускаем проверку")
                    time.sleep(self.check_interval)
                    continue
                
                # Обрабатываем сигналы
                self._process_trading_signals()
                
                # Ждем следующую проверку
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                time.sleep(self.check_interval)
    
    def _is_auto_bot_enabled(self) -> bool:
        """Проверяет включен ли Auto Bot"""
        try:
            with self.bots_data_lock:
                return self.bots_data.get('auto_bot_config', {}).get('enabled', False)
        except:
            return False
    
    def _process_trading_signals(self):
        """Обработка торговых сигналов"""
        logger.info("🔍 Проверяем торговые сигналы...")
        
        try:
            # Получаем все монеты с RSI данными
            coins_to_check = self._get_coins_with_signals()
            
            if not coins_to_check:
                logger.debug("📭 Нет монет с сигналами")
                return
            
            logger.info(f"📊 Найдено {len(coins_to_check)} монет с сигналами")
            
            # Проверяем каждую монету
            for symbol, signal_data in coins_to_check.items():
                try:
                    self._check_coin_signal(symbol, signal_data)
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки {symbol}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сигналов: {e}")
    
    def _get_coins_with_signals(self) -> Dict:
        """Получает монеты с торговыми сигналами"""
        coins_with_signals = {}
        
        try:
            with self.rsi_data_lock:
                for symbol, rsi_data in self.coins_rsi_data.get('coins', {}).items():
                    rsi = rsi_data.get('rsi6h')
                    trend = rsi_data.get('trend6h', 'NEUTRAL')
                    
                    if not rsi:
                        continue
                    
                    # Определяем сигнал
                    signal = self._determine_signal(rsi, trend)
                    
                    if signal in ['ENTER_LONG', 'ENTER_SHORT']:
                        coins_with_signals[symbol] = {
                            'rsi': rsi,
                            'trend': trend,
                            'signal': signal,
                            'price': rsi_data.get('price', 0)
                        }
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения сигналов: {e}")
        
        return coins_with_signals
    
    def _determine_signal(self, rsi: float, trend: str) -> str:
        """Определяет торговый сигнал на основе RSI и тренда"""
        try:
            with self.bots_data_lock:
                config = self.bots_data.get('auto_bot_config', {})
                rsi_long_threshold = config.get('rsi_long_threshold', 29)
                rsi_short_threshold = config.get('rsi_short_threshold', 71)
            
            if rsi <= rsi_long_threshold:
                return 'ENTER_LONG'
            elif rsi >= rsi_short_threshold:
                return 'ENTER_SHORT'
            else:
                return 'NEUTRAL'
                
        except:
            return 'NEUTRAL'
    
    def _check_coin_signal(self, symbol: str, signal_data: Dict):
        """Проверяет сигнал для конкретной монеты"""
        signal = signal_data['signal']
        rsi = signal_data['rsi']
        price = signal_data['price']
        
        logger.info(f"🎯 {symbol}: {signal} (RSI={rsi}, Price=${price:.6f})")
        
        # Проверяем все фильтры
        if not self._check_all_filters(symbol, signal, rsi, price):
            logger.info(f"❌ {symbol}: Фильтры не пройдены")
            return
        
        # Проверяем лимиты
        if not self._check_limits():
            logger.info(f"❌ {symbol}: Достигнут лимит ботов")
            return
        
        # Создаем бота
        self._create_bot(symbol, signal_data)
    
    def _check_all_filters(self, symbol: str, signal: str, rsi: float, price: float) -> bool:
        """Проверяет ВСЕ фильтры для монеты"""
        logger.info(f"🔍 {symbol}: Проверяем все фильтры...")
        
        try:
            # 1. RSI Time Filter
            if not self._check_rsi_time_filter(symbol, signal):
                logger.info(f"❌ {symbol}: RSI Time Filter не пройден")
                return False
            
            # 2. Exit Scam Filter
            if not self._check_exit_scam_filter(symbol):
                logger.info(f"❌ {symbol}: Exit Scam Filter не пройден")
                return False
            
            # 3. Maturity Check
            if not self._check_maturity(symbol):
                logger.info(f"❌ {symbol}: Maturity Check не пройден")
                return False
            
            # 4. Whitelist/Blacklist
            if not self._check_whitelist_blacklist(symbol):
                logger.info(f"❌ {symbol}: Whitelist/Blacklist не пройден")
                return False
            
            # 5. ИИ фильтры
            if not self._check_ai_filters(symbol, signal, rsi, price):
                logger.info(f"❌ {symbol}: ИИ фильтры не пройдены")
                return False
            
            logger.info(f"✅ {symbol}: Все фильтры пройдены!")
            return True
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Ошибка проверки фильтров: {e}")
            return False
    
    def _check_rsi_time_filter(self, symbol: str, signal: str) -> bool:
        """Проверяет RSI Time Filter"""
        try:
            with self.bots_data_lock:
                config = self.bots_data.get('auto_bot_config', {})
                rsi_time_filter_enabled = config.get('rsi_time_filter_enabled', True)
            
            if not rsi_time_filter_enabled:
                return True
            
            # Получаем RSI данные для проверки фильтра
            rsi_data = self.get_coin_rsi_data(symbol)
            if not rsi_data:
                logger.warning(f"⚠️ {symbol}: Нет RSI данных для проверки фильтра")
                return False
            
            # Проверяем фильтр
            result = self.check_rsi_time_filter(symbol, signal, rsi_data)
            logger.info(f"🔍 {symbol}: RSI Time Filter = {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Ошибка RSI Time Filter: {e}")
            return False
    
    def _check_exit_scam_filter(self, symbol: str) -> bool:
        """Проверяет Exit Scam Filter"""
        try:
            with self.bots_data_lock:
                config = self.bots_data.get('auto_bot_config', {})
                exit_scam_enabled = config.get('exit_scam_enabled', True)
            
            if not exit_scam_enabled:
                return True
            
            # Получаем свечи для анализа
            chart_response = self.exchange.get_chart_data(symbol, '6h', '30d')
            if not chart_response or not chart_response.get('success'):
                logger.warning(f"⚠️ {symbol}: Не удалось получить свечи")
                return False
            
            candles = chart_response.get('data', {}).get('candles', [])
            if len(candles) < 8:
                logger.warning(f"⚠️ {symbol}: Недостаточно свечей ({len(candles)})")
                return False
            
            # Анализируем последние 8 свечей
            recent_candles = candles[-8:]
            
            # Проверяем каждую свечу на аномальный рост
            for i, candle in enumerate(recent_candles):
                open_price = candle['open']
                close_price = candle['close']
                high_price = candle['high']
                
                # Проверяем рост за свечу
                candle_change = ((close_price - open_price) / open_price) * 100
                
                # Если рост больше 15% - подозрительно
                if candle_change > 15:
                    logger.warning(f"⚠️ {symbol}: Подозрительный рост {candle_change:.1f}% в свече {i+1}")
                    return False
            
            logger.info(f"✅ {symbol}: Exit Scam Filter пройден")
            return True
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Ошибка Exit Scam Filter: {e}")
            return False
    
    def _check_maturity(self, symbol: str) -> bool:
        """Проверяет зрелость монеты"""
        try:
            with self.bots_data_lock:
                config = self.bots_data.get('auto_bot_config', {})
                enable_maturity_check = config.get('enable_maturity_check', True)
            
            if not enable_maturity_check:
                return True
            
            # Проверяем зрелость
            is_mature = self.is_coin_mature_stored(symbol)
            logger.info(f"🔍 {symbol}: Maturity Check = {is_mature}")
            return is_mature
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Ошибка Maturity Check: {e}")
            return False
    
    def _check_whitelist_blacklist(self, symbol: str) -> bool:
        """Проверяет Whitelist/Blacklist"""
        try:
            with self.bots_data_lock:
                config = self.bots_data.get('auto_bot_config', {})
                whitelist = config.get('whitelist', [])
                blacklist = config.get('blacklist', [])
                scope = config.get('scope', 'all')
            
            # Проверяем blacklist
            if symbol in blacklist:
                logger.info(f"❌ {symbol}: В blacklist")
                return False
            
            # Проверяем whitelist
            if scope == 'whitelist' and symbol not in whitelist:
                logger.info(f"❌ {symbol}: Не в whitelist")
                return False
            
            logger.info(f"✅ {symbol}: Whitelist/Blacklist пройден")
            return True
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Ошибка Whitelist/Blacklist: {e}")
            return False
    
    def _check_ai_filters(self, symbol: str, signal: str, rsi: float, price: float) -> bool:
        """Проверяет ИИ фильтры"""
        try:
            # Получаем свечи для ИИ анализа
            chart_response = self.exchange.get_chart_data(symbol, '6h', '30d')
            if not chart_response or not chart_response.get('success'):
                logger.warning(f"⚠️ {symbol}: Не удалось получить свечи для ИИ")
                return True  # Пропускаем ИИ если нет данных
            
            candles = chart_response.get('data', {}).get('candles', [])
            if len(candles) < 20:
                logger.warning(f"⚠️ {symbol}: Недостаточно свечей для ИИ ({len(candles)})")
                return True  # Пропускаем ИИ если мало данных
            
            # 1. Anomaly Detector
            anomaly_score = self.ai_manager.anomaly_detector.detect_anomaly(candles)
            if anomaly_score > 0.8:  # Высокий риск аномалии
                logger.warning(f"⚠️ {symbol}: Высокий риск аномалии ({anomaly_score:.2f})")
                return False
            
            # 2. LSTM Predictor
            prediction = self.ai_manager.lstm_predictor.predict_price_movement(candles)
            if prediction and signal == 'ENTER_LONG' and prediction < 0:
                logger.warning(f"⚠️ {symbol}: LSTM предсказывает падение ({prediction:.2f})")
                return False
            
            # 3. Pattern Detector
            pattern_result = self.ai_manager.pattern_detector.detect_patterns(candles)
            if pattern_result and pattern_result.get('risk_level', 'low') == 'high':
                logger.warning(f"⚠️ {symbol}: Высокий риск по паттернам")
                return False
            
            # 4. Risk Manager
            risk_assessment = self.ai_manager.risk_manager.assess_risk(symbol, signal, price, candles)
            if risk_assessment and risk_assessment.get('risk_level', 'low') == 'high':
                logger.warning(f"⚠️ {symbol}: Высокий риск по Risk Manager")
                return False
            
            logger.info(f"✅ {symbol}: Все ИИ фильтры пройдены")
            return True
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Ошибка ИИ фильтров: {e}")
            return True  # Пропускаем ИИ при ошибке
    
    def _check_limits(self) -> bool:
        """Проверяет лимиты ботов"""
        try:
            with self.bots_data_lock:
                config = self.bots_data.get('auto_bot_config', {})
                max_concurrent = config.get('max_concurrent', 10)
                
                # Считаем активных ботов
                active_bots = sum(1 for bot in self.bots_data.get('bots', {}).values() 
                               if bot.get('status') not in [self.BOT_STATUS['IDLE'], self.BOT_STATUS['PAUSED']])
            
            if active_bots >= max_concurrent:
                logger.info(f"❌ Достигнут лимит ботов ({active_bots}/{max_concurrent})")
                return False
            
            logger.info(f"✅ Лимит ботов OK ({active_bots}/{max_concurrent})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки лимитов: {e}")
            return False
    
    def _create_bot(self, symbol: str, signal_data: Dict):
        """Создает бота и входит в позицию"""
        try:
            logger.info(f"🤖 {symbol}: Создаем бота...")
            
            # Получаем конфигурацию
            with self.bots_data_lock:
                config = self.bots_data.get('auto_bot_config', {})
                default_position_size = config.get('default_position_size', 5)
            
            # Создаем бота
            bot_config = {
                'position_size': default_position_size,
                'auto_managed': True,
                'opened_by_autobot': True
            }
            
            # Создаем объект бота
            trading_bot = self.NewTradingBot(symbol, self.exchange, bot_config)
            
            # Входим в позицию
            signal = signal_data['signal']
            rsi = signal_data['rsi']
            price = signal_data['price']
            
            if signal == 'ENTER_LONG':
                result = trading_bot.enter_long_position(price)
            elif signal == 'ENTER_SHORT':
                result = trading_bot.enter_short_position(price)
            else:
                logger.warning(f"⚠️ {symbol}: Неизвестный сигнал {signal}")
                return
            
            if result:
                logger.info(f"✅ {symbol}: Бот создан и вошел в позицию!")
                
                # Сохраняем бота
                bot_data = trading_bot.to_dict()
                with self.bots_data_lock:
                    self.bots_data['bots'][symbol] = bot_data
                
                # Сохраняем состояние
                from bots_modules.sync_and_cache import save_bots_state
                save_bots_state()
                
            else:
                logger.error(f"❌ {symbol}: Не удалось войти в позицию")
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Ошибка создания бота: {e}")


def main():
    """Главная функция для тестирования"""
    print("SIMPLE TRADING SYSTEM")
    print("=" * 50)
    
    try:
        # Создаем и запускаем систему
        system = SimpleTradingSystem()
        system.start()
        
        # Ждем
        print("System started. Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping system...")
        system.stop()
        print("System stopped")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
