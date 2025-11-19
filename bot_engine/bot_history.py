#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль истории торговых ботов
Логирование всех действий ботов: запуск, остановка, сигналы, открытие/закрытие позиций
"""

import os
import json
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Файл для хранения истории
HISTORY_FILE = 'data/bot_history.json'

# Ограничения на количество записей (None = без ограничений, для обучения ботов)
MAX_HISTORY_ENTRIES = None  # Ранее было 10000
MAX_TRADE_ENTRIES = None    # Ранее было 5000

# Типы действий
ACTION_TYPES = {
    'BOT_START': 'Запуск бота',
    'BOT_STOP': 'Остановка бота',
    'SIGNAL': 'Торговый сигнал',
    'POSITION_OPENED': 'Открытие позиции',
    'POSITION_CLOSED': 'Закрытие позиции',
    'LIMIT_ORDER_PLACED': 'Размещение лимитного ордера',
    'STOP_LOSS_SET': 'Установка Stop Loss',
    'STOP_LOSS_UPDATED': 'Обновление Stop Loss',
    'TAKE_PROFIT_SET': 'Установка Take Profit',
    'TAKE_PROFIT_UPDATED': 'Обновление Take Profit',
    'STOP_LOSS': 'Срабатывание Stop Loss',
    'TAKE_PROFIT': 'Срабатывание Take Profit',
    'TRAILING_STOP': 'Срабатывание Trailing Stop',
    'ERROR': 'Ошибка бота'
}


class BotHistoryManager:
    """Менеджер истории торговых ботов"""
    
    def __init__(self, history_file: str = HISTORY_FILE):
        self.history_file = history_file
        self.lock = threading.Lock()
        self.history = []
        self.trades = []
        
        # Создаем директорию data если её нет
        os.makedirs('data', exist_ok=True)
        
        # Загружаем историю из файла
        self._load_history()
    
    def _load_history(self):
        """Загружает историю из файла"""
        try:
            if os.path.exists(self.history_file):
                try:
                    with open(self.history_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.history = data.get('history', [])
                        self.trades = data.get('trades', [])
                        logger.info(f"✅ Загружено записей: {len(self.history)} действий, {len(self.trades)} сделок")
                except json.JSONDecodeError as json_error:
                    # Файл поврежден - создаем резервную копию и начинаем с пустой истории
                    import shutil
                    backup_file = f"{self.history_file}.corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup"
                    try:
                        shutil.copy2(self.history_file, backup_file)
                        logger.warning(f"⚠️ Файл истории поврежден (JSON ошибка на строке {json_error.lineno}, колонка {json_error.colno}). "
                                     f"Создана резервная копия: {backup_file}")
                        logger.warning(f"⚠️ Начинаем с пустой истории. Данные будут восстановлены при следующем сохранении.")
                    except Exception as backup_error:
                        logger.error(f"❌ Не удалось создать резервную копию поврежденного файла: {backup_error}")
                    self.history = []
                    self.trades = []
            else:
                logger.info("📝 Файл истории не найден, создается новый")
                self.history = []
                self.trades = []
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки истории: {e}")
            self.history = []
            self.trades = []
    
    def _save_history(self):
        """Сохраняет историю в файл (атомарная запись через временный файл)"""
        try:
            with self.lock:
                data = {
                    'history': self.history,
                    'trades': self.trades,
                    'last_update': datetime.now().isoformat()
                }
                # Атомарная запись через временный файл
                import tempfile
                from pathlib import Path
                temp_file = Path(self.history_file).with_suffix('.tmp')
                try:
                    # Записываем во временный файл
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    # Атомарно заменяем старый файл новым
                    temp_file.replace(self.history_file)
                except Exception as save_error:
                    # Удаляем временный файл в случае ошибки
                    if temp_file.exists():
                        try:
                            temp_file.unlink()
                        except Exception:
                            pass
                    raise save_error
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения истории: {e}")
    
    def _add_history_entry(self, entry: Dict[str, Any]):
        """Добавляет запись в историю"""
        with self.lock:
            self.history.append(entry)
            # Ограничиваем размер истории (если установлен лимит)
            if MAX_HISTORY_ENTRIES is not None and len(self.history) > MAX_HISTORY_ENTRIES:
                self.history = self.history[-MAX_HISTORY_ENTRIES:]
        self._save_history()
    
    def _add_trade_entry(self, trade: Dict[str, Any]):
        """Добавляет запись о сделке"""
        with self.lock:
            self.trades.append(trade)
            # Ограничиваем размер (если установлен лимит)
            if MAX_TRADE_ENTRIES is not None and len(self.trades) > MAX_TRADE_ENTRIES:
                self.trades = self.trades[-MAX_TRADE_ENTRIES:]
        self._save_history()
    
    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Преобразует значение timestamp в datetime"""
        if value in (None, ''):
            return None

        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except Exception:  # pragma: no cover - защитный код
                return None

        if isinstance(value, str):
            candidate = value
            # Удаляем суффикс Z для совместимости с datetime.fromisoformat
            if candidate.endswith('Z'):
                candidate = candidate[:-1]

            # Добавляем временную зону, если отсутствует
            if candidate and candidate[-1].isdigit():
                try:
                    return datetime.fromisoformat(candidate)
                except ValueError:
                    try:
                        return datetime.fromisoformat(candidate + '+00:00')
                    except ValueError:
                        return None

        return None

    def _filter_by_period(self, records: List[Dict[str, Any]], period: Optional[str],
                          timestamp_keys: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Фильтрует записи по периоду времени"""
        if not period or period.lower() == 'all':
            return records

        period = period.lower()
        now = datetime.now()

        if period == 'today':
            threshold = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            threshold = now - timedelta(days=7)
        elif period == 'month':
            threshold = now - timedelta(days=30)
        else:
            # Неизвестный период — не фильтруем
            return records

        keys_to_check = timestamp_keys or ['timestamp']

        filtered: List[Dict[str, Any]] = []
        for item in records:
            for key in keys_to_check:
                timestamp = item.get(key)
                dt = self._parse_timestamp(timestamp)
                if dt and dt >= threshold:
                    filtered.append(item)
                    break

        return filtered

    # ==================== Функции логирования ====================
    
    def log_bot_start(self, bot_id: str, symbol: str, direction: str, config: Dict = None):
        """Логирование запуска бота"""
        entry = {
            'id': f"start_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': 'BOT_START',
            'action_name': ACTION_TYPES['BOT_START'],
            'bot_id': bot_id,
            'symbol': symbol,
            'direction': direction,  # LONG или SHORT
            'config': config or {},
            'details': f"Запущен бот {direction} для {symbol}"
        }
        self._add_history_entry(entry)
        logger.info(f"🚀 {entry['details']}")
    
    def log_bot_stop(self, bot_id: str, symbol: str, reason: str = None, pnl: float = None):
        """Логирование остановки бота"""
        entry = {
            'id': f"stop_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': 'BOT_STOP',
            'action_name': ACTION_TYPES['BOT_STOP'],
            'bot_id': bot_id,
            'symbol': symbol,
            'reason': reason or 'Ручная остановка',
            'pnl': pnl,
            'details': f"Остановлен бот для {symbol}: {reason or 'Ручная остановка'}"
        }
        if pnl is not None:
            entry['details'] += f" (PnL: {pnl:.2f} USDT)"
        
        self._add_history_entry(entry)
        logger.info(f"🛑 {entry['details']}")
    
    def log_bot_signal(self, symbol: str, signal_type: str, rsi: float, price: float, details: Dict = None):
        """Логирование торгового сигнала"""
        entry = {
            'id': f"signal_{symbol}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': 'SIGNAL',
            'action_name': ACTION_TYPES['SIGNAL'],
            'symbol': symbol,
            'signal_type': signal_type,  # ENTER_LONG, ENTER_SHORT, EXIT
            'rsi': rsi,
            'price': price,
            'details_data': details or {},
            'details': f"Сигнал {signal_type} для {symbol} (RSI: {rsi:.2f}, цена: {price:.2f})"
        }
        self._add_history_entry(entry)
        logger.info(f"📊 {entry['details']}")
    
    def log_position_opened(self, bot_id: str, symbol: str, direction: str, size: float, 
                           entry_price: float, stop_loss: float = None, take_profit: float = None,
                           decision_source: str = 'SCRIPT', ai_decision_id: str = None, 
                           ai_confidence: float = None, ai_signal: str = None, rsi: float = None,
                           trend: str = None):
        """
        Логирование открытия позиции с информацией об источнике решения
        
        Args:
            bot_id: ID бота
            symbol: Символ монеты
            direction: Направление (LONG/SHORT)
            size: Размер позиции
            entry_price: Цена входа
            stop_loss: Стоп-лосс
            take_profit: Тейк-профит
            decision_source: Источник решения ('AI' или 'SCRIPT')
            ai_decision_id: ID решения AI (если использовался AI)
            ai_confidence: Уверенность AI (0.0-1.0)
            ai_signal: Сигнал AI ('LONG'/'SHORT'/'WAIT')
            rsi: RSI на момент открытия
            trend: Тренд на момент открытия
        """
        entry = {
            'id': f"open_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': 'POSITION_OPENED',
            'action_name': ACTION_TYPES['POSITION_OPENED'],
            'bot_id': bot_id,
            'symbol': symbol,
            'direction': direction,
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'decision_source': decision_source,  # 'AI' или 'SCRIPT'
            'ai_decision_id': ai_decision_id,
            'ai_confidence': ai_confidence,
            'ai_signal': ai_signal,
            'rsi': rsi,
            'trend': trend,
            'details': f"Открыта позиция {direction} для {symbol}: размер {size}, цена входа {entry_price:.4f}"
        }
        
        # Добавляем информацию об источнике решения в details
        if decision_source == 'AI' and ai_confidence:
            entry['details'] += f" [AI: {ai_confidence:.1%}]"
        elif decision_source == 'SCRIPT':
            entry['details'] += " [SCRIPT]"
        
        self._add_history_entry(entry)
        
        # Также добавляем в сделки
        trade = {
            'id': f"trade_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'bot_id': bot_id,
            'symbol': symbol,
            'direction': direction,
            'size': size,
            'entry_price': entry_price,
            'exit_price': None,
            'pnl': None,
            'status': 'OPEN',
            'decision_source': decision_source,
            'ai_decision_id': ai_decision_id,
            'ai_confidence': ai_confidence,
            'rsi': rsi,
            'trend': trend
        }
        self._add_trade_entry(trade)
        
        logger.info(f"📈 {entry['details']}")
    
    def log_limit_order_placed(self, bot_id: str, symbol: str, order_type: str, order_id: str,
                               price: float, quantity: float, side: str, percent_step: float = None):
        """Логирование размещения лимитного ордера"""
        entry = {
            'id': f"limit_order_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': 'LIMIT_ORDER_PLACED',
            'action_name': ACTION_TYPES['LIMIT_ORDER_PLACED'],
            'bot_id': bot_id,
            'symbol': symbol,
            'order_type': order_type,  # 'limit' или 'market'
            'order_id': order_id,
            'price': price,
            'quantity': quantity,
            'side': side,  # 'LONG' или 'SHORT'
            'percent_step': percent_step,
            'details': f"Размещен {order_type} ордер для {symbol}: {quantity} @ {price:.6f}"
        }
        if percent_step is not None:
            entry['details'] += f" ({percent_step}%)"
        self._add_history_entry(entry)
        logger.info(f"📋 {entry['details']}")
    
    def log_stop_loss_set(self, bot_id: str, symbol: str, stop_price: float, position_side: str, 
                         is_update: bool = False, previous_price: float = None):
        """Логирование установки/обновления Stop Loss"""
        action_type = 'STOP_LOSS_UPDATED' if is_update else 'STOP_LOSS_SET'
        entry = {
            'id': f"stop_loss_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': action_type,
            'action_name': ACTION_TYPES[action_type],
            'bot_id': bot_id,
            'symbol': symbol,
            'stop_price': stop_price,
            'position_side': position_side,
            'previous_price': previous_price,
            'details': f"{'Обновлен' if is_update else 'Установлен'} Stop Loss для {symbol}: {stop_price:.6f}"
        }
        if is_update and previous_price:
            entry['details'] += f" (было: {previous_price:.6f})"
        self._add_history_entry(entry)
        logger.info(f"🛡️ {entry['details']}")
    
    def log_take_profit_set(self, bot_id: str, symbol: str, take_profit_price: float, position_side: str,
                           is_update: bool = False, previous_price: float = None):
        """Логирование установки/обновления Take Profit"""
        action_type = 'TAKE_PROFIT_UPDATED' if is_update else 'TAKE_PROFIT_SET'
        entry = {
            'id': f"take_profit_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': action_type,
            'action_name': ACTION_TYPES[action_type],
            'bot_id': bot_id,
            'symbol': symbol,
            'take_profit_price': take_profit_price,
            'position_side': position_side,
            'previous_price': previous_price,
            'details': f"{'Обновлен' if is_update else 'Установлен'} Take Profit для {symbol}: {take_profit_price:.6f}"
        }
        if is_update and previous_price:
            entry['details'] += f" (было: {previous_price:.6f})"
        self._add_history_entry(entry)
        logger.info(f"🎯 {entry['details']}")
    
    def log_position_closed(self, bot_id: str, symbol: str, direction: str, exit_price: float, 
                           pnl: float, roi: float, reason: str = None, entry_data: Dict = None,
                           market_data: Dict = None, ai_decision_id: str = None):
        """
        Логирование закрытия позиции с дополнительными данными для обучения ИИ
        
        Args:
            bot_id: ID бота
            symbol: Символ монеты
            direction: Направление (LONG/SHORT)
            exit_price: Цена выхода
            pnl: PnL в USDT
            roi: ROI в %
            reason: Причина закрытия (STOP_LOSS, TAKE_PROFIT, TRAILING_STOP и т.д.)
            entry_data: Данные при входе (entry_price, rsi, volume, candles_before)
            market_data: Данные рынка при выходе (volatility, trend_strength, support_resistance)
            ai_decision_id: ID решения AI (если использовался AI при открытии)
        """
        # Определяем источник решения из entry_data или из сделки
        decision_source = 'SCRIPT'
        ai_confidence = None
        matching_trade_snapshot: Optional[Dict[str, Any]] = None
        
        # Пробуем найти соответствующую сделку для получения информации об источнике решения
        with self.lock:
            for trade in reversed(self.trades):
                if trade['bot_id'] == bot_id and trade['symbol'] == symbol and trade['status'] == 'OPEN':
                    decision_source = trade.get('decision_source', 'SCRIPT')
                    ai_decision_id = trade.get('ai_decision_id') or ai_decision_id
                    ai_confidence = trade.get('ai_confidence')
                    matching_trade_snapshot = trade.copy()
                    break
        
        original_pnl_input = pnl
        original_roi_input = roi
        
        def _to_float(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None
        
        # Пытаемся пересчитать PnL из цен (на случай, если передан некорректный PnL)
        calc_direction = direction or (matching_trade_snapshot or {}).get('direction')
        entry_price_for_calc = (
            _to_float(entry_data.get('entry_price')) if entry_data and entry_data.get('entry_price') is not None else None
        )
        if entry_price_for_calc is None and matching_trade_snapshot:
            entry_price_for_calc = _to_float(matching_trade_snapshot.get('entry_price'))
        
        exit_price_for_calc = _to_float(exit_price)
        if exit_price_for_calc is None and market_data:
            exit_price_for_calc = _to_float(market_data.get('exit_price'))
        if exit_price_for_calc is None and matching_trade_snapshot:
            exit_price_for_calc = _to_float(matching_trade_snapshot.get('exit_price'))
        if exit_price_for_calc is not None:
            exit_price = exit_price_for_calc
        
        position_size_usdt = None
        position_size_coins = None
        if entry_data:
            position_size_usdt = _to_float(entry_data.get('position_size_usdt'))
            position_size_coins = _to_float(entry_data.get('position_size_coins'))
        if position_size_usdt is None and matching_trade_snapshot:
            position_size_usdt = _to_float(matching_trade_snapshot.get('position_size_usdt'))
        if (position_size_coins is None or position_size_coins == 0) and matching_trade_snapshot:
            position_size_coins = _to_float(matching_trade_snapshot.get('size'))
        
        recalculated_pnl = pnl
        recalculated_roi = roi
        recalculated = False
        if entry_price_for_calc and exit_price_for_calc and entry_price_for_calc > 0 and calc_direction in ('LONG', 'SHORT'):
            if calc_direction == 'LONG':
                roi_fraction = (exit_price_for_calc - entry_price_for_calc) / entry_price_for_calc
            else:
                roi_fraction = (entry_price_for_calc - exit_price_for_calc) / entry_price_for_calc
            
            recalculated_roi = roi_fraction * 100
            position_value = position_size_usdt
            if (position_value is None or position_value == 0) and position_size_coins and position_size_coins > 0:
                position_value = position_size_coins * entry_price_for_calc
            
            if position_value is not None and position_value != 0:
                recalculated_pnl = roi_fraction * position_value
            else:
                recalculated_pnl = roi_fraction * 100  # fallback в процентах
            
            if (pnl is None) or (abs(recalculated_pnl - pnl) > 1e-9):
                logger.debug(
                    f"[BOT_HISTORY] 🔄 PnL пересчитан из цен для {symbol}: "
                    f"entry={entry_price_for_calc}, exit={exit_price_for_calc}, side={calc_direction}, "
                    f"old_pnl={pnl}, new_pnl={recalculated_pnl:.6f}"
                )
                recalculated = True
            pnl = recalculated_pnl
            roi = recalculated_roi
        
        entry = {
            'id': f"close_{bot_id}_{datetime.now().timestamp()}",
            'timestamp': datetime.now().isoformat(),
            'action_type': 'POSITION_CLOSED',
            'action_name': ACTION_TYPES['POSITION_CLOSED'],
            'bot_id': bot_id,
            'symbol': symbol,
            'direction': direction,
            'exit_price': exit_price,
            'pnl': pnl,
            'roi': roi,
            'reason': reason or 'Ручное закрытие',
            'decision_source': decision_source,
            'ai_decision_id': ai_decision_id,
            'ai_confidence': ai_confidence,
            'is_successful': pnl > 0,
            'details': f"Закрыта позиция {direction} для {symbol}: цена выхода {exit_price:.4f}, PnL: {pnl:.2f} USDT ({roi:.2f}%)"
        }
        
        # Добавляем информацию об источнике решения в details
        if decision_source == 'AI' and ai_confidence:
            entry['details'] += f" [AI: {ai_confidence:.1%}, {'✅' if pnl > 0 else '❌'}]"
        elif decision_source == 'SCRIPT':
            entry['details'] += f" [SCRIPT, {'✅' if pnl > 0 else '❌'}]"
        entry['pnl_source'] = 'recalculated' if recalculated else 'input'
        if recalculated and original_pnl_input is not None:
            entry['pnl_original'] = original_pnl_input
        if recalculated and original_roi_input is not None:
            entry['roi_original'] = original_roi_input
        
        # Добавляем данные для обучения ИИ
        if entry_data:
            entry['entry_data'] = entry_data
            entry['entry_price'] = entry_data.get('entry_price')
            entry['entry_rsi'] = entry_data.get('rsi')
            entry['entry_volatility'] = entry_data.get('volatility')
            entry['entry_trend'] = entry_data.get('trend')
        
        if market_data:
            entry['market_data'] = market_data
            entry['exit_volatility'] = market_data.get('volatility')
            entry['exit_trend'] = market_data.get('trend')
            entry['price_movement'] = market_data.get('price_movement')  # % изменения за период
        
        # Маркируем стопы для обучения
        if reason and 'STOP' in reason.upper():
            entry['is_stop'] = True
            entry['stop_analysis'] = {
                'initial_rsi': entry_data.get('rsi') if entry_data else None,
                'max_drawdown': entry_data.get('max_profit_achieved') if entry_data else None,
                'volatility_at_entry': entry_data.get('volatility') if entry_data else None,
                'days_in_position': entry_data.get('duration_hours', 0) / 24 if entry_data else 0
            }
        
        self._add_history_entry(entry)
        
        # Обновляем сделку
        with self.lock:
            for trade in reversed(self.trades):
                if trade['bot_id'] == bot_id and trade['symbol'] == symbol and trade['status'] == 'OPEN':
                    trade['exit_price'] = exit_price
                    trade['pnl'] = pnl
                    trade['roi'] = roi
                    trade['status'] = 'CLOSED'
                    trade['close_timestamp'] = datetime.now().isoformat()
                    trade['close_reason'] = reason
                    trade['is_successful'] = pnl > 0
                    if position_size_usdt:
                        trade['position_size_usdt'] = position_size_usdt
                    if position_size_coins:
                        trade['position_size_coins'] = position_size_coins
                    if entry_data:
                        trade['entry_data'] = entry_data
                    if market_data:
                        trade['exit_market_data'] = market_data
                    break
        self._save_history()
        
        logger.info(f"💰 {entry['details']}")
    
    # ==================== Методы получения данных ====================
    
    def get_bot_history(self, symbol: Optional[str] = None, action_type: Optional[str] = None,
                       limit: int = 100, period: Optional[str] = None) -> List[Dict]:
        """
        Получает историю действий ботов
        
        Args:
            symbol: Фильтр по символу (например, BTCUSDT)
            action_type: Тип действия (BOT_START, BOT_STOP, SIGNAL и т.д.)
            limit: Максимальное количество записей
        
        Returns:
            Список записей истории (от новых к старым)
        """
        with self.lock:
            filtered = self.history.copy()
            
            # Фильтр по символу
            if symbol:
                filtered = [h for h in filtered if h.get('symbol') == symbol]
            
            # Фильтр по типу действия (регистр игнорируется)
            if action_type:
                action_upper = action_type.upper()
                filtered = [
                    h for h in filtered
                    if (h.get('action_type') or '').upper() == action_upper
                ]

            # Фильтр по периоду
            filtered = self._filter_by_period(filtered, period, ['timestamp'])
            
            # Сортируем от новых к старым
            filtered.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Ограничиваем количество
            return filtered[:limit]
    
    def get_stopped_trades(self, limit: int = 100) -> List[Dict]:
        """
        Получает все сделки, закрытые по стопу (для обучения ИИ)
        
        Returns:
            Список сделок с детальным анализом стопов
        """
        with self.lock:
            stopped_trades = []
            
            # Ищем сделки, закрытые по стоп-лоссу
            for trade in self.trades:
                if trade.get('status') == 'CLOSED':
                    reason = trade.get('close_reason', '')
                    if 'STOP' in reason.upper():
                        stopped_trades.append(trade)
            
            # Сортируем от новых к старым
            stopped_trades.sort(key=lambda x: x.get('close_timestamp', x.get('timestamp', '')), reverse=True)
            
            return stopped_trades[:limit]
    
    def get_bot_trades(self, symbol: Optional[str] = None, trade_type: Optional[str] = None,
                      limit: int = 100, period: Optional[str] = None) -> List[Dict]:
        """
        Получает историю торговых сделок
        
        Args:
            symbol: Фильтр по символу
            trade_type: Фильтр по направлению (LONG/SHORT)
            limit: Максимальное количество записей
        
        Returns:
            Список сделок (от новых к старым)
        """
        with self.lock:
            filtered = self.trades.copy()
            
            # Фильтр по символу
            if symbol:
                filtered = [t for t in filtered if t.get('symbol') == symbol]
            
            # Фильтр по типу сделки
            if trade_type:
                direction_upper = trade_type.upper()
                filtered = [
                    t for t in filtered
                    if (t.get('direction') or '').upper() == direction_upper
                ]

            # Фильтр по периоду (учитываем время закрытия, затем открытия)
            filtered = self._filter_by_period(filtered, period, ['close_timestamp', 'timestamp'])
            
            # Сортируем от новых к старым
            filtered.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Ограничиваем количество
            return filtered[:limit]
    
    def get_bot_statistics(self, symbol: Optional[str] = None, period: Optional[str] = None) -> Dict:
        """Получает агрегированную статистику по истории и сделкам"""
        with self.lock:
            trades = self.trades.copy()
            history = self.history.copy()

            # Собираем список всех доступных символов
            all_symbols_set = {
                entry.get('symbol')
                for entry in self.history
                if entry.get('symbol')
            }
            all_symbols_set.update(
                trade.get('symbol')
                for trade in self.trades
                if trade.get('symbol')
            )
            all_symbols = sorted(all_symbols_set)

            # Фильтры
            if symbol:
                trades = [t for t in trades if t.get('symbol') == symbol]
                history = [h for h in history if h.get('symbol') == symbol]

            trades = self._filter_by_period(trades, period, ['close_timestamp', 'timestamp'])
            history = self._filter_by_period(history, period, ['timestamp'])

            closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
            open_trades = [t for t in trades if t.get('status') == 'OPEN']
            profitable = [t for t in closed_trades if t.get('pnl', 0) > 0]
            losing = [t for t in closed_trades if t.get('pnl', 0) < 0]

            total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
            avg_pnl = total_pnl / len(closed_trades) if closed_trades else 0
            win_rate = (len(profitable) / len(closed_trades) * 100) if closed_trades else 0

            best_trade = max(closed_trades, key=lambda x: x.get('pnl', 0)) if closed_trades else None
            worst_trade = min(closed_trades, key=lambda x: x.get('pnl', 0)) if closed_trades else None

            filtered_symbols_set = {
                entry.get('symbol')
                for entry in history
                if entry.get('symbol')
            }
            filtered_symbols_set.update(
                trade.get('symbol')
                for trade in trades
                if trade.get('symbol')
            )

            signals_count = sum(
                1 for entry in history
                if (entry.get('action_type') or '').upper() == 'SIGNAL'
            )

            return {
                'total_actions': len(history),
                'total_trades': len(closed_trades),
                'total_trades_overall': len(trades),
                'open_trades': len(open_trades),
                'signals_count': signals_count,
                'profitable_trades': len(profitable),
                'losing_trades': len(losing),
                'win_rate': win_rate,
                'success_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'best_trade': best_trade,
                'worst_trade': worst_trade,
                'symbols': all_symbols,
                'symbols_filtered': sorted(filtered_symbols_set),
                'symbol': symbol if symbol else 'ALL',
            }
    
    def clear_history(self, symbol: Optional[str] = None):
        """
        Очищает историю
        
        Args:
            symbol: Если указан, очищает только для этого символа, иначе всю историю
        """
        with self.lock:
            if symbol:
                self.history = [h for h in self.history if h.get('symbol') != symbol]
                self.trades = [t for t in self.trades if t.get('symbol') != symbol]
                logger.info(f"🗑️ Очищена история для {symbol}")
            else:
                self.history = []
                self.trades = []
                logger.info("🗑️ Вся история очищена")
        
        self._save_history()


# ==================== Глобальный экземпляр ====================

bot_history_manager = BotHistoryManager()


# ==================== Функции-обертки для удобства ====================

def log_bot_start(bot_id: str, symbol: str, direction: str, config: Dict = None):
    """Логирование запуска бота"""
    bot_history_manager.log_bot_start(bot_id, symbol, direction, config)


def log_bot_stop(bot_id: str, symbol: str, reason: str = None, pnl: float = None):
    """Логирование остановки бота"""
    bot_history_manager.log_bot_stop(bot_id, symbol, reason, pnl)


def log_bot_signal(symbol: str, signal_type: str, rsi: float, price: float, details: Dict = None):
    """Логирование торгового сигнала"""
    bot_history_manager.log_bot_signal(symbol, signal_type, rsi, price, details)


def log_position_opened(bot_id: str, symbol: str, direction: str, size: float,
                       entry_price: float, stop_loss: float = None, take_profit: float = None,
                       decision_source: str = 'SCRIPT', ai_decision_id: str = None,
                       ai_confidence: float = None, ai_signal: str = None,
                       rsi: float = None, trend: str = None):
    """Логирование открытия позиции"""
    bot_history_manager.log_position_opened(
        bot_id,
        symbol,
        direction,
        size,
        entry_price,
        stop_loss,
        take_profit,
        decision_source=decision_source,
        ai_decision_id=ai_decision_id,
        ai_confidence=ai_confidence,
        ai_signal=ai_signal,
        rsi=rsi,
        trend=trend
    )


def log_position_closed(bot_id: str, symbol: str, direction: str, exit_price: float, 
                       pnl: float, roi: float, reason: str = None, entry_data: Dict = None,
                       market_data: Optional[Dict] = None, ai_decision_id: Optional[str] = None):
    """Логирование закрытия позиции"""
    bot_history_manager.log_position_closed(
        bot_id,
        symbol,
        direction,
        exit_price,
        pnl,
        roi,
        reason,
        entry_data=entry_data,
        market_data=market_data,
        ai_decision_id=ai_decision_id,
    )


def log_limit_order_placed(bot_id: str, symbol: str, order_type: str, order_id: str,
                           price: float, quantity: float, side: str, percent_step: float = None):
    """Логирование размещения лимитного ордера"""
    bot_history_manager.log_limit_order_placed(bot_id, symbol, order_type, order_id, price, quantity, side, percent_step)


def log_stop_loss_set(bot_id: str, symbol: str, stop_price: float, position_side: str, 
                     is_update: bool = False, previous_price: float = None):
    """Логирование установки/обновления Stop Loss"""
    bot_history_manager.log_stop_loss_set(bot_id, symbol, stop_price, position_side, is_update, previous_price)


def log_take_profit_set(bot_id: str, symbol: str, take_profit_price: float, position_side: str,
                       is_update: bool = False, previous_price: float = None):
    """Логирование установки/обновления Take Profit"""
    bot_history_manager.log_take_profit_set(bot_id, symbol, take_profit_price, position_side, is_update, previous_price)


# ==================== Демо-данные ====================

def create_demo_data() -> bool:
    """Создает демо-данные для тестирования"""
    try:
        import random
        from datetime import timedelta
        try:
            from bot_engine.ai.ai_data_storage import AIDataStorage
            ai_storage = AIDataStorage()
        except ImportError:
            ai_storage = None
        
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'SOLUSDT']
        
        logger.info("📝 Создание демо-данных...")
        
        for i in range(20):
            symbol = random.choice(symbols)
            direction = random.choice(['LONG', 'SHORT'])
            trend = random.choice(['UP', 'DOWN', 'NEUTRAL'])
            bot_id = f"demo_bot_{i}"
            use_ai = random.random() < 0.5
            ai_confidence = round(random.uniform(0.55, 0.95), 2) if use_ai else None
            ai_decision_id = None
            ai_signal = direction if use_ai else None
            
            # Запуск бота
            log_bot_start(bot_id, symbol, direction, {'mode': 'demo'})
            
            # Сигнал
            rsi = random.uniform(25, 75)
            price = random.uniform(1000, 50000)
            log_bot_signal(symbol, f"ENTER_{direction}", rsi, price)

            if use_ai and ai_storage:
                ai_decision_id = f"demo_ai_{symbol}_{int(time.time() * 1000)}_{random.randint(100,999)}"
                decision_payload = {
                    'id': ai_decision_id,
                    'symbol': symbol,
                    'direction': direction,
                    'rsi': rsi,
                    'trend': trend,
                    'price': price,
                    'ai_signal': ai_signal,
                    'ai_confidence': ai_confidence,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'PENDING',
                    'market_data': {
                        'rsi': rsi,
                        'price': price,
                        'direction': direction
                    }
                }
                try:
                    ai_storage.save_ai_decision(ai_decision_id, decision_payload)
                except Exception as storage_error:
                    logger.debug(f"⚠️ Не удалось сохранить демо-решение AI: {storage_error}")
                    ai_decision_id = None
                    use_ai = False
            
            # Открытие позиции
            entry_price = price
            size = random.uniform(0.001, 0.1)
            log_position_opened(
                bot_id,
                symbol,
                direction,
                size,
                entry_price,
                decision_source='AI' if use_ai else 'SCRIPT',
                ai_decision_id=ai_decision_id,
                ai_confidence=ai_confidence,
                ai_signal=ai_signal,
                rsi=rsi,
                trend=trend
            )
            
            # Закрытие позиции (80% сделок)
            if random.random() < 0.8:
                exit_price = entry_price * random.uniform(0.95, 1.10)
                pnl = (exit_price - entry_price) * size if direction == 'LONG' else (entry_price - exit_price) * size
                roi = ((exit_price - entry_price) / entry_price * 100) if direction == 'LONG' else ((entry_price - exit_price) / entry_price * 100)
                
                log_position_closed(bot_id, symbol, direction, exit_price, pnl, roi, 
                                  random.choice(['Stop Loss', 'Take Profit', 'Ручное закрытие']),
                                  ai_decision_id=ai_decision_id)
                
                log_bot_stop(bot_id, symbol, 'Позиция закрыта', pnl)
                
                if use_ai and ai_decision_id and ai_storage:
                    try:
                        ai_storage.update_ai_decision(ai_decision_id, {
                            'status': 'SUCCESS' if pnl > 0 else 'FAILED',
                            'pnl': float(pnl),
                            'roi': float(roi),
                            'updated_at': datetime.now().isoformat(),
                            'closed_at': datetime.now().isoformat()
                        })
                    except Exception as storage_error:
                        logger.debug(f"⚠️ Не удалось обновить демо-решение AI: {storage_error}")
        
        logger.info("✅ Демо-данные созданы успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания демо-данных: {e}")
        return False


if __name__ == '__main__':
    # Тест модуля
    print("=== Test modula bot_history.py ===\n")
    
    # Очистка
    bot_history_manager.clear_history()
    
    # Создаем демо-данные
    create_demo_data()
    
    # Получаем статистику
    stats = bot_history_manager.get_bot_statistics()
    print(f"\n[STATISTIKA]")
    print(f"  Vsego sdelok: {stats['total_trades']}")
    print(f"  Pribylnyh: {stats['profitable_trades']}")
    print(f"  Ubytochnyh: {stats['losing_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.2f}%")
    print(f"  Obschiy PnL: {stats['total_pnl']:.2f} USDT")
    
    # Получаем последние действия
    history = bot_history_manager.get_bot_history(limit=5)
    print(f"\n[POSLEDNIE 5 DEYSTVIY]:")
    for h in history:
        print(f"  [{h['timestamp']}] {h['action_name']}: {h.get('symbol', 'N/A')}")

