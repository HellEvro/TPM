"""
RSIDataManager - управление RSI данными всех монет.

Этот менеджер инкапсулирует всю логику работы с RSI данными,
заменяя глобальную переменную coins_rsi_data.
"""

import threading
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)


class RSIDataManager:
    """
    Менеджер для управления RSI данными всех монет.
    
    Инкапсулирует хранение и доступ к RSI данным,
    обеспечивая thread-safety для всех операций.
    
    Attributes:
        _data: Словарь с RSI данными
        _lock: Блокировка для thread-safety
    """
    
    def __init__(self):
        """Инициализация менеджера RSI данных"""
        self._data = {
            'coins': {},  # {symbol: {rsi, signal, timestamp, ...}}
            'last_update': None,
            'update_in_progress': False,
            'total_coins': 0,
            'successful_coins': 0,
            'failed_coins': 0
        }
        self._lock = threading.Lock()
        logger.info("[RSIDataManager] Инициализирован")
    
    # ==================== Основные операции ====================
    
    def get_rsi(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получить RSI данные для символа.
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Словарь с RSI данными или None
            {
                'rsi': float,
                'signal': str,  # 'LONG', 'SHORT', 'WAIT'
                'timestamp': datetime,
                'price': float,
                'volume': float,
                ...
            }
        """
        with self._lock:
            return deepcopy(self._data['coins'].get(symbol))
    
    def update_rsi(self, symbol: str, rsi_data: Dict[str, Any]) -> None:
        """
        Обновить RSI данные для символа.
        
        Args:
            symbol: Символ монеты
            rsi_data: Словарь с RSI данными
        """
        with self._lock:
            self._data['coins'][symbol] = rsi_data
            logger.debug(f"[RSIDataManager] Обновлены RSI данные для {symbol}: RSI={rsi_data.get('rsi')}, Signal={rsi_data.get('signal')}")
    
    def get_all_coins(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить RSI данные всех монет.
        
        Returns:
            Словарь {symbol: rsi_data}
        """
        with self._lock:
            return deepcopy(self._data['coins'])
    
    def get_coins_count(self) -> int:
        """
        Получить количество монет.
        
        Returns:
            Количество монет с RSI данными
        """
        with self._lock:
            return len(self._data['coins'])
    
    # ==================== Фильтрация ====================
    
    def get_coins_with_signal(self, signal_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Получить монеты с определенным сигналом.
        
        Args:
            signal_type: Тип сигнала ('LONG', 'SHORT', 'WAIT')
        
        Returns:
            Словарь {symbol: rsi_data} для монет с данным сигналом
        """
        with self._lock:
            filtered = {
                symbol: data
                for symbol, data in self._data['coins'].items()
                if data.get('signal') == signal_type
            }
            logger.debug(f"[RSIDataManager] Найдено {len(filtered)} монет с сигналом {signal_type}")
            return deepcopy(filtered)
    
    def get_coins_by_rsi_range(self, min_rsi: float, max_rsi: float) -> Dict[str, Dict[str, Any]]:
        """
        Получить монеты с RSI в заданном диапазоне.
        
        Args:
            min_rsi: Минимальное значение RSI
            max_rsi: Максимальное значение RSI
        
        Returns:
            Словарь {symbol: rsi_data}
        """
        with self._lock:
            filtered = {
                symbol: data
                for symbol, data in self._data['coins'].items()
                if min_rsi <= data.get('rsi', 0) <= max_rsi
            }
            return deepcopy(filtered)
    
    # ==================== Статистика обновления ====================
    
    def start_update(self) -> bool:
        """
        Начать процесс обновления RSI.
        
        Returns:
            True если обновление началось, False если уже идет
        """
        with self._lock:
            if self._data['update_in_progress']:
                logger.warning("[RSIDataManager] Обновление уже идет")
                return False
            
            self._data['update_in_progress'] = True
            self._data['total_coins'] = 0
            self._data['successful_coins'] = 0
            self._data['failed_coins'] = 0
            logger.info("[RSIDataManager] Начато обновление RSI")
            return True
    
    def finish_update(self, success_count: int, failed_count: int) -> None:
        """
        Завершить процесс обновления RSI.
        
        Args:
            success_count: Количество успешно обновленных монет
            failed_count: Количество монет с ошибками
        """
        with self._lock:
            self._data['update_in_progress'] = False
            self._data['last_update'] = datetime.now()
            self._data['successful_coins'] = success_count
            self._data['failed_coins'] = failed_count
            self._data['total_coins'] = success_count + failed_count
            logger.info(f"[RSIDataManager] Обновление завершено: успех={success_count}, ошибок={failed_count}")
    
    def is_update_in_progress(self) -> bool:
        """
        Проверить идет ли обновление.
        
        Returns:
            True если обновление в процессе
        """
        with self._lock:
            return self._data['update_in_progress']
    
    def get_last_update_time(self) -> Optional[datetime]:
        """
        Получить время последнего обновления.
        
        Returns:
            Datetime последнего обновления или None
        """
        with self._lock:
            return self._data['last_update']
    
    def get_update_stats(self) -> Dict[str, Any]:
        """
        Получить статистику обновления.
        
        Returns:
            Словарь со статистикой
        """
        with self._lock:
            return {
                'update_in_progress': self._data['update_in_progress'],
                'last_update': self._data['last_update'],
                'total_coins': self._data['total_coins'],
                'successful_coins': self._data['successful_coins'],
                'failed_coins': self._data['failed_coins'],
                'current_coins_count': len(self._data['coins'])
            }
    
    # ==================== Сохранение/загрузка ====================
    
    def get_all_data(self) -> Dict[str, Any]:
        """
        Получить все данные для сохранения.
        
        Returns:
            Полный словарь данных
        """
        with self._lock:
            return deepcopy(self._data)
    
    def restore_data(self, data: Dict[str, Any]) -> None:
        """
        Восстановить данные из сохранения.
        
        Args:
            data: Словарь с данными для восстановления
        """
        with self._lock:
            self._data = data
            logger.info(f"[RSIDataManager] Восстановлено {len(self._data['coins'])} монет из сохранения")
    
    def clear_all_data(self) -> None:
        """Очистить все данные"""
        with self._lock:
            self._data['coins'].clear()
            self._data['total_coins'] = 0
            self._data['successful_coins'] = 0
            self._data['failed_coins'] = 0
            logger.info("[RSIDataManager] Все данные очищены")
    
    # ==================== Расширенные операции ====================
    
    def get_top_oversold_coins(self, limit: int = 10) -> List[tuple]:
        """
        Получить топ перепроданных монет (самые низкие RSI).
        
        Args:
            limit: Количество монет
        
        Returns:
            Список кортежей [(symbol, rsi_value), ...]
        """
        with self._lock:
            # Фильтруем монеты с RSI
            coins_with_rsi = [
                (symbol, data.get('rsi', 100))
                for symbol, data in self._data['coins'].items()
                if 'rsi' in data
            ]
            # Сортируем по RSI (от меньшего к большему)
            sorted_coins = sorted(coins_with_rsi, key=lambda x: x[1])
            return sorted_coins[:limit]
    
    def get_top_overbought_coins(self, limit: int = 10) -> List[tuple]:
        """
        Получить топ перекупленных монет (самые высокие RSI).
        
        Args:
            limit: Количество монет
        
        Returns:
            Список кортежей [(symbol, rsi_value), ...]
        """
        with self._lock:
            # Фильтруем монеты с RSI
            coins_with_rsi = [
                (symbol, data.get('rsi', 0))
                for symbol, data in self._data['coins'].items()
                if 'rsi' in data
            ]
            # Сортируем по RSI (от большего к меньшему)
            sorted_coins = sorted(coins_with_rsi, key=lambda x: x[1], reverse=True)
            return sorted_coins[:limit]
    
    def get_signal_distribution(self) -> Dict[str, int]:
        """
        Получить распределение сигналов.
        
        Returns:
            Словарь {'LONG': count, 'SHORT': count, 'WAIT': count}
        """
        with self._lock:
            distribution = {'LONG': 0, 'SHORT': 0, 'WAIT': 0}
            for data in self._data['coins'].values():
                signal = data.get('signal', 'WAIT')
                if signal in distribution:
                    distribution[signal] += 1
            return distribution
    
    # ==================== История RSI ====================
    
    def get_rsi_history(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Получить историю RSI для символа (если хранится).
        
        Args:
            symbol: Символ монеты
        
        Returns:
            Список исторических данных RSI или None
        """
        with self._lock:
            coin_data = self._data['coins'].get(symbol, {})
            return deepcopy(coin_data.get('history', []))
    
    def update_rsi_history(self, symbol: str, history: List[Dict[str, Any]]) -> None:
        """
        Обновить историю RSI для символа.
        
        Args:
            symbol: Символ монеты
            history: Список исторических данных
        """
        with self._lock:
            if symbol in self._data['coins']:
                self._data['coins'][symbol]['history'] = history
                logger.debug(f"[RSIDataManager] Обновлена история RSI для {symbol}: {len(history)} записей")
    
    # ==================== Утилиты ====================
    
    def __repr__(self) -> str:
        """Строковое представление"""
        with self._lock:
            return f"<RSIDataManager(coins={len(self._data['coins'])}, update_in_progress={self._data['update_in_progress']})>"
    
    def get_info(self) -> Dict[str, Any]:
        """
        Получить информацию о менеджере.
        
        Returns:
            Словарь с информацией
        """
        with self._lock:
            signal_dist = self.get_signal_distribution()
            return {
                'total_coins': len(self._data['coins']),
                'update_in_progress': self._data['update_in_progress'],
                'last_update': self._data['last_update'].isoformat() if self._data['last_update'] else None,
                'signals': signal_dist,
                'successful_coins': self._data['successful_coins'],
                'failed_coins': self._data['failed_coins']
            }

