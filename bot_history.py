#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для управления историей ботов
Логирует все действия ботов, сделки и торговые решения
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading

# Глобальные переменные для хранения истории
bot_history_data = {
    'actions': [],  # Действия ботов (запуск, остановка, сигналы)
    'trades': [],   # Торговые сделки (открытие, закрытие позиций)
    'statistics': {
        'total_actions': 0,
        'total_trades': 0,
        'total_pnl': 0.0,
        'successful_trades': 0,
        'failed_trades': 0,
        'last_update': None
    }
}

# Блокировка для потокобезопасности
history_lock = threading.Lock()

# Пути к файлам
HISTORY_FILE = 'data/bot_history.json'
TRADES_FILE = 'data/bot_trades.json'

def ensure_data_directory():
    """Создает директорию data если её нет"""
    if not os.path.exists('data'):
        os.makedirs('data')

def load_history_data():
    """Загружает историю из файлов"""
    global bot_history_data
    
    ensure_data_directory()
    
    # Загружаем действия ботов
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                actions_data = json.load(f)
                if isinstance(actions_data, list):
                    bot_history_data['actions'] = actions_data
        except Exception as e:
            print(f"[HISTORY] Ошибка загрузки истории действий: {e}")
    
    # Загружаем торговые сделки
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, 'r', encoding='utf-8') as f:
                trades_data = json.load(f)
                if isinstance(trades_data, list):
                    bot_history_data['trades'] = trades_data
        except Exception as e:
            print(f"[HISTORY] Ошибка загрузки истории сделок: {e}")
    
    # Обновляем статистику
    update_statistics()

def save_history_data():
    """Сохраняет историю в файлы"""
    global bot_history_data
    
    ensure_data_directory()
    
    try:
        # Сохраняем действия ботов
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_history_data['actions'], f, ensure_ascii=False, indent=2)
        
        # Сохраняем торговые сделки
        with open(TRADES_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_history_data['trades'], f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"[HISTORY] Ошибка сохранения истории: {e}")

def update_statistics():
    """Обновляет статистику истории"""
    global bot_history_data
    
    with history_lock:
        actions_count = len(bot_history_data['actions'])
        trades_count = len(bot_history_data['trades'])
        
        # Подсчитываем успешные и неудачные сделки
        successful = 0
        failed = 0
        total_pnl = 0.0
        
        for trade in bot_history_data['trades']:
            if trade.get('type') == 'position_closed':
                pnl = trade.get('pnl', 0.0)
                total_pnl += pnl
                if pnl > 0:
                    successful += 1
                else:
                    failed += 1
        
        bot_history_data['statistics'] = {
            'total_actions': actions_count,
            'total_trades': trades_count,
            'total_pnl': total_pnl,
            'successful_trades': successful,
            'failed_trades': failed,
            'last_update': datetime.now().isoformat()
        }

def log_bot_action(action_type: str, symbol: str, details: Dict[str, Any], reason: str = ""):
    """Логирует действие бота"""
    global bot_history_data
    
    action = {
        'id': f"{symbol}_{action_type}_{int(datetime.now().timestamp())}",
        'timestamp': datetime.now().isoformat(),
        'action_type': action_type,
        'symbol': symbol,
        'details': details,
        'reason': reason
    }
    
    with history_lock:
        bot_history_data['actions'].append(action)
        # Ограничиваем количество записей (последние 1000)
        if len(bot_history_data['actions']) > 1000:
            bot_history_data['actions'] = bot_history_data['actions'][-1000:]
        
        update_statistics()
        save_history_data()
    
    print(f"[HISTORY] 📝 {action_type.upper()}: {symbol} - {reason}")

def log_bot_start(symbol: str, config: Dict[str, Any]):
    """Логирует запуск бота"""
    details = {
        'config': config,
        'volume_mode': config.get('volume_mode', 'usdt'),
        'volume_value': config.get('volume_value', 10),
        'rsi_long': config.get('rsi_long_threshold', 29),
        'rsi_short': config.get('rsi_short_threshold', 71)
    }
    
    log_bot_action('bot_start', symbol, details, f"Бот запущен с настройками: {config.get('volume_mode', 'usdt')} {config.get('volume_value', 10)}")

def log_bot_stop(symbol: str, reason: str):
    """Логирует остановку бота"""
    details = {
        'reason': reason,
        'stop_type': 'manual' if 'пользователем' in reason else 'automatic'
    }
    
    log_bot_action('bot_stop', symbol, details, f"Бот остановлен: {reason}")

def log_bot_signal(symbol: str, signal: str, rsi_data: Dict[str, Any], decision: str, reason: str):
    """Логирует получение торгового сигнала"""
    details = {
        'signal': signal,
        'rsi_value': rsi_data.get('rsi6h', 0),
        'trend': rsi_data.get('trend', 'UNKNOWN'),
        'decision': decision,
        'enhanced_reason': rsi_data.get('enhanced_reason', 'N/A')
    }
    
    log_bot_action('signal_received', symbol, details, f"Сигнал {signal}: RSI {rsi_data.get('rsi6h', 0):.1f}, решение: {decision}")

def log_position_opened(symbol: str, side: str, entry_price: float, volume: float, config: Dict[str, Any]):
    """Логирует открытие позиции"""
    trade = {
        'id': f"{symbol}_{side}_{int(datetime.now().timestamp())}",
        'timestamp': datetime.now().isoformat(),
        'type': 'position_opened',
        'symbol': symbol,
        'side': side,
        'entry_price': entry_price,
        'volume': volume,
        'config': config,
        'status': 'open'
    }
    
    with history_lock:
        bot_history_data['trades'].append(trade)
        # Ограничиваем количество записей (последние 500)
        if len(bot_history_data['trades']) > 500:
            bot_history_data['trades'] = bot_history_data['trades'][-500:]
        
        update_statistics()
        save_history_data()
    
    print(f"[HISTORY] 📈 ПОЗИЦИЯ ОТКРЫТА: {symbol} {side} @ {entry_price}")

def log_position_closed(symbol: str, side: str, entry_price: float, exit_price: float, volume: float, pnl: float, reason: str):
    """Логирует закрытие позиции"""
    trade = {
        'id': f"{symbol}_{side}_closed_{int(datetime.now().timestamp())}",
        'timestamp': datetime.now().isoformat(),
        'type': 'position_closed',
        'symbol': symbol,
        'side': side,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'volume': volume,
        'pnl': pnl,
        'reason': reason,
        'status': 'closed'
    }
    
    with history_lock:
        bot_history_data['trades'].append(trade)
        # Ограничиваем количество записей (последние 500)
        if len(bot_history_data['trades']) > 500:
            bot_history_data['trades'] = bot_history_data['trades'][-500:]
        
        update_statistics()
        save_history_data()
    
    pnl_emoji = "💰" if pnl > 0 else "💸"
    print(f"[HISTORY] 📉 ПОЗИЦИЯ ЗАКРЫТА: {symbol} {side} @ {exit_price} | PnL: {pnl_emoji} {pnl:.2f}")

def get_bot_history(symbol: Optional[str] = None, action_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """Получает историю действий ботов"""
    with history_lock:
        actions = bot_history_data['actions'].copy()
    
    # Фильтруем по символу
    if symbol:
        actions = [action for action in actions if action.get('symbol') == symbol]
    
    # Фильтруем по типу действия
    if action_type:
        actions = [action for action in actions if action.get('action_type') == action_type]
    
    # Сортируем по времени (новые сначала)
    actions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Ограничиваем количество
    return actions[:limit]

def get_bot_trades(symbol: Optional[str] = None, trade_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """Получает историю торговых сделок"""
    with history_lock:
        trades = bot_history_data['trades'].copy()
    
    # Фильтруем по символу
    if symbol:
        trades = [trade for trade in trades if trade.get('symbol') == symbol]
    
    # Фильтруем по типу сделки
    if trade_type:
        trades = [trade for trade in trades if trade.get('type') == trade_type]
    
    # Сортируем по времени (новые сначала)
    trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Ограничиваем количество
    return trades[:limit]

def get_bot_statistics(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Получает статистику по ботам"""
    with history_lock:
        stats = bot_history_data['statistics'].copy()
    
    if symbol:
        # Фильтруем статистику по конкретному боту
        symbol_actions = [action for action in bot_history_data['actions'] if action.get('symbol') == symbol]
        symbol_trades = [trade for trade in bot_history_data['trades'] if trade.get('symbol') == symbol]
        
        successful = 0
        failed = 0
        total_pnl = 0.0
        
        for trade in symbol_trades:
            if trade.get('type') == 'position_closed':
                pnl = trade.get('pnl', 0.0)
                total_pnl += pnl
                if pnl > 0:
                    successful += 1
                else:
                    failed += 1
        
        stats = {
            'total_actions': len(symbol_actions),
            'total_trades': len(symbol_trades),
            'total_pnl': total_pnl,
            'successful_trades': successful,
            'failed_trades': failed,
            'success_rate': (successful / (successful + failed) * 100) if (successful + failed) > 0 else 0,
            'last_update': datetime.now().isoformat()
        }
    
    return stats

def clear_history(symbol: Optional[str] = None):
    """Очищает историю"""
    global bot_history_data
    
    with history_lock:
        if symbol:
            # Очищаем историю конкретного бота
            bot_history_data['actions'] = [action for action in bot_history_data['actions'] if action.get('symbol') != symbol]
            bot_history_data['trades'] = [trade for trade in bot_history_data['trades'] if trade.get('symbol') != symbol]
        else:
            # Очищаем всю историю
            bot_history_data['actions'] = []
            bot_history_data['trades'] = []
        
        update_statistics()
        save_history_data()
    
    message = f"История для {symbol} очищена" if symbol else "Вся история очищена"
    print(f"[HISTORY] 🗑️ {message}")

# Инициализация при импорте
load_history_data()

# Класс для управления историей (для совместимости с API)
class BotHistoryManager:
    def __init__(self):
        self.load_data()
    
    def load_data(self):
        load_history_data()
    
    def save_data(self):
        save_history_data()
    
    def get_bot_history(self, symbol=None, action_type=None, limit=100):
        return get_bot_history(symbol, action_type, limit)
    
    def get_bot_trades(self, symbol=None, trade_type=None, limit=100):
        return get_bot_trades(symbol, trade_type, limit)
    
    def get_bot_statistics(self, symbol=None):
        return get_bot_statistics(symbol)
    
    def clear_history(self, symbol=None):
        clear_history(symbol)

# Глобальный экземпляр менеджера
bot_history_manager = BotHistoryManager()

def create_test_history_data():
    """Создает тестовые данные для демонстрации истории ботов"""
    from datetime import datetime, timedelta
    import random
    
    # Очищаем существующие данные
    clear_history()
    
    # Создаем тестовые боты
    test_bots = ['BTC', 'ETH', 'ADA', 'SOL', 'DOT']
    
    # Создаем тестовые действия за последние 7 дней
    for i in range(50):
        bot = random.choice(test_bots)
        action_type = random.choice(['bot_start', 'bot_stop', 'signal_received'])
        
        # Создаем случайную дату в последние 7 дней
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        
        timestamp = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
        
        if action_type == 'bot_start':
            config = {
                'volume_mode': random.choice(['usdt', 'qty', 'percent']),
                'volume_value': random.uniform(10, 100),
                'rsi_long_threshold': random.randint(25, 35),
                'rsi_short_threshold': random.randint(65, 75)
            }
            log_bot_start(bot, config)
            
        elif action_type == 'bot_stop':
            reasons = ['Остановлен пользователем', 'Достигнут стоп-лосс', 'Неактивен 30 мин', 'Ошибка API']
            reason = random.choice(reasons)
            log_bot_stop(bot, reason)
            
        elif action_type == 'signal_received':
            rsi_data = {
                'rsi6h': random.uniform(20, 80),
                'trend': random.choice(['UP', 'DOWN', 'SIDEWAYS']),
                'enhanced_reason': random.choice(['Volume confirmation', 'Divergence detected', 'Trend strength'])
            }
            signal = random.choice(['LONG', 'SHORT', 'HOLD'])
            decision = random.choice(['bot_created', 'signal_ignored', 'waiting_for_confirmation'])
            reason = f"RSI: {rsi_data['rsi6h']:.1f}, Enhanced: {rsi_data['enhanced_reason']}"
            log_bot_signal(bot, signal, rsi_data, decision, reason)
    
    # Создаем тестовые сделки
    for i in range(30):
        bot = random.choice(test_bots)
        side = random.choice(['LONG', 'SHORT'])
        
        # Создаем случайную дату
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        
        timestamp = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
        
        entry_price = random.uniform(100, 50000)
        volume = random.uniform(0.1, 10)
        
        # Открытие позиции
        config = {
            'volume_mode': 'usdt',
            'volume_value': volume,
            'rsi_long_threshold': 29,
            'rsi_short_threshold': 71
        }
        log_position_opened(bot, side, entry_price, volume, config)
        
        # Закрытие позиции (через некоторое время)
        exit_price = entry_price * random.uniform(0.95, 1.15)  # ±15% от цены входа
        pnl = (exit_price - entry_price) / entry_price * 100 if side == 'LONG' else (entry_price - exit_price) / entry_price * 100
        pnl = pnl * volume  # Учитываем объем
        
        reasons = ['RSI выход', 'Стоп-лосс', 'Трейлинг стоп', 'Ручное закрытие']
        reason = random.choice(reasons)
        log_position_closed(bot, side, entry_price, exit_price, volume, pnl, reason)
    
    print("[HISTORY] ✅ Тестовые данные созданы!")
    print(f"[HISTORY] 📊 Создано {len(bot_history_data['actions'])} действий")
    print(f"[HISTORY] 💼 Создано {len(bot_history_data['trades'])} сделок")

# Функция для создания тестовых данных (можно вызвать из API)
def create_demo_data():
    """Создает демо-данные для истории ботов"""
    try:
        create_test_history_data()
        return True
    except Exception as e:
        print(f"[HISTORY] ❌ Ошибка создания демо-данных: {e}")
        return False
