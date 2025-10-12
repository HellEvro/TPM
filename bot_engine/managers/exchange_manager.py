"""
ExchangeManager - управление подключением к бирже и торговыми операциями.

Этот менеджер инкапсулирует всю логику работы с биржей,
заменяя глобальную переменную exchange.
"""

import threading
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ExchangeManager:
    """
    Менеджер для работы с биржей.
    
    Инкапсулирует подключение к бирже и обеспечивает thread-safe доступ
    ко всем операциям с биржей.
    
    Attributes:
        exchange: Объект биржи (из ExchangeFactory)
        _lock: Блокировка для thread-safety
        _initialized: Флаг инициализации
    """
    
    def __init__(self, exchange):
        """
        Инициализация менеджера биржи.
        
        Args:
            exchange: Объект биржи (из ExchangeFactory.create_exchange)
        """
        self.exchange = exchange
        self._lock = threading.Lock()
        self._initialized = True
        logger.info(f"[ExchangeManager] Инициализирован для биржи: {exchange.__class__.__name__}")
    
    def is_initialized(self) -> bool:
        """Проверка инициализации"""
        return self._initialized and self.exchange is not None
    
    # ==================== Получение данных ====================
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[List]:
        """
        Получить свечи (klines) для символа.
        
        Args:
            symbol: Символ монеты (например, 'BTCUSDT')
            interval: Интервал ('1m', '5m', '15m', '1h', '6h', '1d')
            limit: Количество свечей
        
        Returns:
            Список свечей [[timestamp, open, high, low, close, volume], ...]
        
        Raises:
            Exception: Если не удалось получить данные
        """
        with self._lock:
            try:
                klines = self.exchange.fetch_klines(symbol, interval, limit)
                logger.debug(f"[ExchangeManager] Получено {len(klines)} свечей для {symbol} {interval}")
                return klines
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка получения klines для {symbol}: {e}")
                raise
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Получить текущую цену символа.
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Словарь с данными тикера (last, bid, ask, volume, etc.)
        """
        with self._lock:
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка получения ticker для {symbol}: {e}")
                raise
    
    def get_balance(self) -> Dict[str, Any]:
        """
        Получить баланс счета.
        
        Returns:
            Словарь с балансами {'USDT': {'free': 1000, 'used': 0, 'total': 1000}, ...}
        """
        with self._lock:
            try:
                balance = self.exchange.fetch_balance()
                logger.debug(f"[ExchangeManager] Получен баланс счета")
                return balance
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка получения баланса: {e}")
                raise
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получить позицию по символу.
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Словарь с данными позиции или None если позиции нет
        """
        with self._lock:
            try:
                positions = self.exchange.fetch_positions([symbol])
                if positions:
                    # Фильтруем позиции с ненулевым размером
                    active_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]
                    if active_positions:
                        return active_positions[0]
                return None
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка получения позиции для {symbol}: {e}")
                raise
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """
        Получить все открытые позиции.
        
        Returns:
            Список позиций
        """
        with self._lock:
            try:
                # Используем метод биржи get_positions (а не fetch_positions)
                if hasattr(self.exchange, 'get_positions'):
                    result = self.exchange.get_positions()
                    # Может вернуть tuple или list
                    if isinstance(result, tuple):
                        positions = result[0] if result and result[0] else []
                    else:
                        positions = result if result else []
                elif hasattr(self.exchange, 'fetch_positions'):
                    positions = self.exchange.fetch_positions()
                else:
                    logger.warning("[ExchangeManager] Метод получения позиций не найден")
                    return []
                
                # Возвращаем только активные позиции
                if positions:
                    active_positions = [p for p in positions if abs(float(p.get('size', 0))) > 0 or abs(float(p.get('contracts', 0))) > 0]
                    logger.debug(f"[ExchangeManager] Получено {len(active_positions)} активных позиций")
                    return active_positions
                return []
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка получения позиций: {e}")
                return []  # Возвращаем пустой список вместо raise
    
    def get_all_tickers(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить тикеры всех символов.
        
        Returns:
            Словарь {symbol: ticker_data}
        """
        with self._lock:
            try:
                tickers = self.exchange.fetch_tickers()
                logger.debug(f"[ExchangeManager] Получено {len(tickers)} тикеров")
                return tickers
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка получения всех тикеров: {e}")
                raise
    
    # ==================== Торговые операции ====================
    
    def create_order(self, symbol: str, side: str, order_type: str, 
                    amount: float, price: Optional[float] = None,
                    params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Создать ордер.
        
        Args:
            symbol: Символ монеты
            side: Сторона ('buy' или 'sell')
            order_type: Тип ордера ('market', 'limit')
            amount: Количество
            price: Цена (для limit ордеров)
            params: Дополнительные параметры
        
        Returns:
            Данные созданного ордера
        """
        with self._lock:
            try:
                logger.info(f"[ExchangeManager] Создание ордера: {symbol} {side} {order_type} {amount}")
                
                if params is None:
                    params = {}
                
                order = self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=amount,
                    price=price,
                    params=params
                )
                
                logger.info(f"[ExchangeManager] Ордер создан: ID={order.get('id')}, Status={order.get('status')}")
                return order
                
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка создания ордера {symbol}: {e}")
                raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Отменить ордер.
        
        Args:
            order_id: ID ордера
            symbol: Символ монеты
        
        Returns:
            Данные отмененного ордера
        """
        with self._lock:
            try:
                logger.info(f"[ExchangeManager] Отмена ордера: {order_id} для {symbol}")
                result = self.exchange.cancel_order(order_id, symbol)
                logger.info(f"[ExchangeManager] Ордер {order_id} отменен")
                return result
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка отмены ордера {order_id}: {e}")
                raise
    
    def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Закрыть позицию по рынку.
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Результат закрытия
        """
        with self._lock:
            try:
                logger.info(f"[ExchangeManager] Закрытие позиции: {symbol}")
                
                # Получаем текущую позицию
                position = self.get_position(symbol)
                if not position:
                    logger.warning(f"[ExchangeManager] Позиция {symbol} не найдена")
                    return {'success': False, 'error': 'Position not found'}
                
                # Определяем сторону закрытия (противоположную позиции)
                position_side = position.get('side', '').lower()
                close_side = 'sell' if position_side == 'long' else 'buy'
                
                # Получаем размер позиции
                amount = abs(float(position.get('contracts', 0)))
                
                # Создаем рыночный ордер на закрытие
                order = self.create_order(
                    symbol=symbol,
                    side=close_side,
                    order_type='market',
                    amount=amount,
                    params={'reduceOnly': True}
                )
                
                logger.info(f"[ExchangeManager] Позиция {symbol} закрыта")
                return {'success': True, 'order': order}
                
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка закрытия позиции {symbol}: {e}")
                raise
    
    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Установить плечо для символа.
        
        Args:
            symbol: Символ монеты
            leverage: Размер плеча (1-125)
        
        Returns:
            Результат установки
        """
        with self._lock:
            try:
                logger.info(f"[ExchangeManager] Установка плеча {leverage}x для {symbol}")
                result = self.exchange.set_leverage(leverage, symbol)
                return result
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка установки плеча для {symbol}: {e}")
                raise
    
    # ==================== Утилиты ====================
    
    def get_trading_symbols(self) -> List[str]:
        """
        Получить список всех доступных торговых символов.
        
        Returns:
            Список символов ['BTCUSDT', 'ETHUSDT', ...]
        """
        with self._lock:
            try:
                markets = self.exchange.load_markets()
                # Фильтруем только USDT пары на спотовом/фьючерсном рынке
                symbols = [
                    symbol for symbol, market in markets.items()
                    if market.get('quote') == 'USDT' and market.get('active', True)
                ]
                logger.debug(f"[ExchangeManager] Найдено {len(symbols)} торговых пар")
                return sorted(symbols)
            except Exception as e:
                logger.error(f"[ExchangeManager] Ошибка получения символов: {e}")
                raise
    
    def get_exchange(self):
        """
        Получить объект биржи.
        
        Returns:
            Объект биржи или None
        """
        return self.exchange
    
    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Получить информацию о бирже.
        
        Returns:
            Словарь с информацией о бирже
        """
        return {
            'name': self.exchange.__class__.__name__ if self.exchange else 'None',
            'initialized': self._initialized and self.exchange is not None,
            'has_fetch_klines': hasattr(self.exchange, 'fetch_klines') if self.exchange else False,
            'has_create_order': hasattr(self.exchange, 'create_order') if self.exchange else False,
            'has_fetch_balance': hasattr(self.exchange, 'fetch_balance') if self.exchange else False,
            'has_fetch_positions': hasattr(self.exchange, 'fetch_positions') if self.exchange else False,
        }
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"<ExchangeManager(exchange={self.exchange.__class__.__name__}, initialized={self._initialized})>"

