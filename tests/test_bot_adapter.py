"""
Тест для BotAdapter.

Упрощенная версия - проверяем основной функционал без реального NewTradingBot.
"""

import unittest
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestBotAdapter(unittest.TestCase):
    """Тесты для BotAdapter"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        # Создаем mock state
        self.mock_state = Mock()
        self.mock_state.exchange_manager = Mock()
        self.mock_state.exchange_manager.exchange = Mock()
        self.mock_state.rsi_manager = Mock()
    
    def test_initialization(self):
        """Тест инициализации"""
        config = {'volume_mode': 'usdt', 'volume_value': 10.0}
        adapter = BotAdapter('BTCUSDT', config, self.mock_state)
        
        # Проверяем что адаптер создан
        self.assertEqual(adapter.symbol, 'BTCUSDT')
        self.assertEqual(adapter.config, config)
        self.assertIsNotNone(adapter.bot)
        
        # Проверяем что NewTradingBot был вызван с правильными аргументами
        self.mock_new_trading_bot_class.assert_called_once()
    
    def test_status_property(self):
        """Тест свойства status"""
        adapter = BotAdapter('BTCUSDT', {}, self.mock_state)
        
        # Получение status
        status = adapter.status
        self.assertEqual(status, 'idle')
        
        # Установка status
        adapter.status = 'running'
        self.assertEqual(self.mock_trading_bot.status, 'running')
    
    def test_delegation(self):
        """Тест делегирования методов"""
        adapter = BotAdapter('BTCUSDT', {}, self.mock_state)
        
        # update_status должен делегироваться к bot
        self.mock_trading_bot.update_status = Mock()
        adapter.update_status('running')
        self.mock_trading_bot.update_status.assert_called_once_with('running')
    
    def test_update_with_rsi_data(self):
        """Тест update с RSI данными"""
        # Настраиваем RSI данные
        self.mock_state.rsi_manager.get_rsi.return_value = {
            'rsi': 25.5,
            'signal': 'LONG',
            'trend': 'UP'
        }
        
        self.mock_trading_bot.update = Mock(return_value={'success': True})
        
        adapter = BotAdapter('BTCUSDT', {}, self.mock_state)
        result = adapter.update()
        
        # Проверяем что RSI данные были получены
        self.mock_state.rsi_manager.get_rsi.assert_called_once_with('BTCUSDT')
        
        # Проверяем что update был вызван с правильными параметрами
        self.mock_trading_bot.update.assert_called_once()
        call_args = self.mock_trading_bot.update.call_args
        self.assertEqual(call_args.kwargs['external_signal'], 'LONG')
        self.assertEqual(call_args.kwargs['external_trend'], 'UP')
    
    def test_has_position(self):
        """Тест проверки наличия позиции"""
        adapter = BotAdapter('BTCUSDT', {}, self.mock_state)
        
        # Без позиции
        self.mock_trading_bot.status = 'idle'
        self.assertFalse(adapter.has_position())
        
        # С long позицией
        self.mock_trading_bot.status = 'in_position_long'
        self.assertTrue(adapter.has_position())
        
        # С short позицией
        self.mock_trading_bot.status = 'in_position_short'
        self.assertTrue(adapter.has_position())
    
    def test_is_active(self):
        """Тест проверки активности"""
        adapter = BotAdapter('BTCUSDT', {}, self.mock_state)
        
        self.mock_trading_bot.status = 'idle'
        self.assertFalse(adapter.is_active())
        
        self.mock_trading_bot.status = 'running'
        self.assertTrue(adapter.is_active())
    
    def test_to_dict(self):
        """Тест сериализации"""
        self.mock_trading_bot.to_dict = Mock(return_value={'symbol': 'BTCUSDT', 'status': 'idle'})
        
        adapter = BotAdapter('BTCUSDT', {}, self.mock_state)
        data = adapter.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertIn('symbol', data)
        self.mock_trading_bot.to_dict.assert_called_once()


def run_tests():
    """Запуск тестов"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestBotAdapter)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

