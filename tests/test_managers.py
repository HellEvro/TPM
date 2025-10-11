"""
Тесты для всех менеджеров State Manager.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time

# Импортируем менеджеры
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot_engine.managers.exchange_manager import ExchangeManager
from bot_engine.managers.rsi_manager import RSIDataManager
from bot_engine.managers.bot_manager import BotManager
from bot_engine.managers.config_manager import ConfigManager
from bot_engine.managers.worker_manager import WorkerManager


class TestExchangeManager(unittest.TestCase):
    """Тесты для ExchangeManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.mock_exchange = Mock()
        self.manager = ExchangeManager(self.mock_exchange)
    
    def test_initialization(self):
        """Тест инициализации"""
        self.assertTrue(self.manager.is_initialized())
        self.assertEqual(self.manager.exchange, self.mock_exchange)
    
    def test_get_klines(self):
        """Тест получения свечей"""
        # Настраиваем mock
        self.mock_exchange.fetch_klines.return_value = [
            [1234567890, 100, 110, 90, 105, 1000]
        ]
        
        # Вызываем метод
        klines = self.manager.get_klines('BTCUSDT', '6h', 100)
        
        # Проверяем
        self.assertEqual(len(klines), 1)
        self.mock_exchange.fetch_klines.assert_called_once_with('BTCUSDT', '6h', 100)
    
    def test_get_balance(self):
        """Тест получения баланса"""
        # Настраиваем mock
        self.mock_exchange.fetch_balance.return_value = {
            'USDT': {'free': 1000, 'used': 0, 'total': 1000}
        }
        
        # Вызываем метод
        balance = self.manager.get_balance()
        
        # Проверяем
        self.assertIn('USDT', balance)
        self.assertEqual(balance['USDT']['free'], 1000)
    
    def test_thread_safety(self):
        """Тест thread-safety"""
        results = []
        
        def fetch():
            klines = self.manager.get_klines('BTCUSDT', '6h', 10)
            results.append(len(klines))
        
        # Настраиваем mock
        self.mock_exchange.fetch_klines.return_value = [[1, 2, 3, 4, 5, 6]]
        
        # Запускаем несколько потоков
        threads = [threading.Thread(target=fetch) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Все потоки должны успешно завершиться
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r == 1 for r in results))


class TestRSIDataManager(unittest.TestCase):
    """Тесты для RSIDataManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.manager = RSIDataManager()
    
    def test_initialization(self):
        """Тест инициализации"""
        self.assertEqual(self.manager.get_coins_count(), 0)
        self.assertFalse(self.manager.is_update_in_progress())
    
    def test_update_and_get_rsi(self):
        """Тест обновления и получения RSI"""
        # Обновляем RSI
        rsi_data = {
            'rsi': 25.5,
            'signal': 'LONG',
            'price': 50000
        }
        self.manager.update_rsi('BTCUSDT', rsi_data)
        
        # Получаем обратно
        retrieved = self.manager.get_rsi('BTCUSDT')
        
        # Проверяем
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['rsi'], 25.5)
        self.assertEqual(retrieved['signal'], 'LONG')
        self.assertEqual(self.manager.get_coins_count(), 1)
    
    def test_get_coins_with_signal(self):
        """Тест фильтрации по сигналу"""
        # Добавляем несколько монет
        self.manager.update_rsi('BTC', {'rsi': 25, 'signal': 'LONG'})
        self.manager.update_rsi('ETH', {'rsi': 75, 'signal': 'SHORT'})
        self.manager.update_rsi('BNB', {'rsi': 50, 'signal': 'WAIT'})
        self.manager.update_rsi('SOL', {'rsi': 28, 'signal': 'LONG'})
        
        # Получаем монеты с сигналом LONG
        long_coins = self.manager.get_coins_with_signal('LONG')
        
        # Проверяем
        self.assertEqual(len(long_coins), 2)
        self.assertIn('BTC', long_coins)
        self.assertIn('SOL', long_coins)
    
    def test_update_flow(self):
        """Тест процесса обновления"""
        # Начинаем обновление
        self.assertTrue(self.manager.start_update())
        self.assertTrue(self.manager.is_update_in_progress())
        
        # Пытаемся начать еще раз (должно вернуть False)
        self.assertFalse(self.manager.start_update())
        
        # Завершаем обновление
        self.manager.finish_update(success_count=10, failed_count=2)
        self.assertFalse(self.manager.is_update_in_progress())
        
        # Проверяем статистику
        stats = self.manager.get_update_stats()
        self.assertEqual(stats['successful_coins'], 10)
        self.assertEqual(stats['failed_coins'], 2)
        self.assertEqual(stats['total_coins'], 12)


class TestBotManager(unittest.TestCase):
    """Тесты для BotManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.mock_exchange_mgr = Mock()
        self.mock_rsi_mgr = Mock()
        self.manager = BotManager(self.mock_exchange_mgr, self.mock_rsi_mgr)
    
    def test_initialization(self):
        """Тест инициализации"""
        self.assertEqual(self.manager.get_bots_count(), 0)
        self.assertEqual(self.manager.get_active_bots_count(), 0)
    
    def test_create_bot(self):
        """Тест создания бота"""
        # Создаем mock класс бота
        mock_bot = Mock()
        mock_bot.symbol = 'BTCUSDT'
        mock_bot.status = 'idle'
        
        mock_bot_class = Mock(return_value=mock_bot)
        
        # Создаем бота
        bot = self.manager.create_bot('BTCUSDT', {}, mock_bot_class)
        
        # Проверяем
        self.assertIsNotNone(bot)
        self.assertEqual(self.manager.get_bots_count(), 1)
    
    def test_duplicate_bot(self):
        """Тест попытки создать дубликат бота"""
        mock_bot_class = Mock(return_value=Mock(symbol='BTCUSDT', status='idle'))
        
        # Создаем первого бота
        self.manager.create_bot('BTCUSDT', {}, mock_bot_class)
        
        # Пытаемся создать дубликат
        with self.assertRaises(ValueError):
            self.manager.create_bot('BTCUSDT', {}, mock_bot_class)
    
    def test_get_and_delete_bot(self):
        """Тест получения и удаления бота"""
        mock_bot = Mock(symbol='BTCUSDT', status='idle')
        mock_bot_class = Mock(return_value=mock_bot)
        
        # Создаем бота
        self.manager.create_bot('BTCUSDT', {}, mock_bot_class)
        
        # Получаем бота
        bot = self.manager.get_bot('BTCUSDT')
        self.assertIsNotNone(bot)
        
        # Удаляем бота
        result = self.manager.delete_bot('BTCUSDT')
        self.assertTrue(result)
        self.assertEqual(self.manager.get_bots_count(), 0)
        
        # Проверяем что бота нет
        self.assertIsNone(self.manager.get_bot('BTCUSDT'))


class TestConfigManager(unittest.TestCase):
    """Тесты для ConfigManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.manager = ConfigManager(config_dir='test_data')
    
    def tearDown(self):
        """Очистка после теста"""
        import shutil
        if os.path.exists('test_data'):
            shutil.rmtree('test_data')
    
    def test_initialization(self):
        """Тест инициализации"""
        self.assertIsNotNone(self.manager.auto_bot_config)
        self.assertIsNotNone(self.manager.system_config)
        self.assertFalse(self.manager.auto_bot_config['enabled'])
    
    def test_get_and_update_auto_bot_config(self):
        """Тест получения и обновления Auto Bot конфига"""
        # Получаем конфиг
        config = self.manager.get_auto_bot_config()
        self.assertIn('max_concurrent_bots', config)
        
        # Обновляем
        self.manager.update_auto_bot_config({'max_concurrent_bots': 10})
        
        # Проверяем обновление
        updated_config = self.manager.get_auto_bot_config()
        self.assertEqual(updated_config['max_concurrent_bots'], 10)
    
    def test_save_and_load(self):
        """Тест сохранения и загрузки"""
        # Изменяем конфиг
        self.manager.update_auto_bot_config({'max_concurrent_bots': 15})
        
        # Создаем новый менеджер (загрузит из файла)
        new_manager = ConfigManager(config_dir='test_data')
        new_manager.load_auto_bot_config()
        
        # Проверяем что загрузились изменения
        loaded_config = new_manager.get_auto_bot_config()
        self.assertEqual(loaded_config['max_concurrent_bots'], 15)


class TestWorkerManager(unittest.TestCase):
    """Тесты для WorkerManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.mock_state = Mock()
        self.manager = WorkerManager(self.mock_state)
    
    def test_initialization(self):
        """Тест инициализации"""
        self.assertEqual(self.manager.get_workers_count(), 0)
        self.assertFalse(self.manager.is_shutdown_requested())
    
    def test_start_and_stop_worker(self):
        """Тест запуска и остановки воркера"""
        # Создаем простую функцию воркера
        def simple_worker(state, shutdown_flag, interval):
            while not shutdown_flag.is_set():
                time.sleep(0.1)
        
        # Запускаем воркер
        result = self.manager.start_worker('test_worker', simple_worker, interval=1)
        self.assertTrue(result)
        self.assertEqual(self.manager.get_workers_count(), 1)
        
        # Даем время запуститься
        time.sleep(0.2)
        
        # Останавливаем воркер
        stop_result = self.manager.stop_worker('test_worker', timeout=2)
        self.assertTrue(stop_result)
        self.assertEqual(self.manager.get_workers_count(), 0)
    
    def test_duplicate_worker(self):
        """Тест попытки запустить дубликат воркера"""
        def simple_worker(state, shutdown_flag, interval):
            time.sleep(0.1)
        
        # Запускаем первого
        self.manager.start_worker('test_worker', simple_worker)
        
        # Пытаемся запустить дубликат
        result = self.manager.start_worker('test_worker', simple_worker)
        self.assertFalse(result)


def run_tests():
    """Запуск всех тестов"""
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем все тесты
    suite.addTests(loader.loadTestsFromTestCase(TestExchangeManager))
    suite.addTests(loader.loadTestsFromTestCase(TestRSIDataManager))
    suite.addTests(loader.loadTestsFromTestCase(TestBotManager))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManager))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkerManager))
    
    # Запускаем
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Возвращаем результат
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

