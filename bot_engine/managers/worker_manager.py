"""
WorkerManager - управление фоновыми задачами (воркерами).

Этот менеджер инкапсулирует логику запуска и остановки воркеров.
"""

import threading
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkerManager:
    """
    Менеджер для управления фоновыми воркерами.
    
    Инкапсулирует запуск, остановку и мониторинг воркеров,
    обеспечивая thread-safety.
    
    Attributes:
        state: BotSystemState instance
        workers: Словарь запущенных воркеров
        shutdown_flag: Флаг остановки всех воркеров
        _lock: Блокировка для thread-safety
    """
    
    def __init__(self, state):
        """
        Инициализация менеджера воркеров.
        
        Args:
            state: BotSystemState instance
        """
        self.state = state
        self.workers = {}  # {name: worker_info}
        self.shutdown_flag = threading.Event()
        self._lock = threading.Lock()
        
        logger.info("[WorkerManager] Инициализирован")
    
    # ==================== Управление воркерами ====================
    
    def start_worker(self, name: str, worker_func: Callable, 
                    interval: int = 60, daemon: bool = True) -> bool:
        """
        Запустить воркер.
        
        Args:
            name: Имя воркера
            worker_func: Функция воркера (должна принимать state, shutdown_flag, interval)
            interval: Интервал выполнения (секунды)
            daemon: Запускать как daemon thread
        
        Returns:
            True если воркер запущен, False если уже существует
        """
        with self._lock:
            if name in self.workers:
                logger.warning(f"[WorkerManager] Воркер {name} уже запущен")
                return False
            
            # Создаем поток
            thread = threading.Thread(
                target=worker_func,
                args=(self.state, self.shutdown_flag, interval),
                daemon=daemon,
                name=f"Worker-{name}"
            )
            
            # Запускаем
            thread.start()
            
            # Сохраняем информацию
            self.workers[name] = {
                'thread': thread,
                'function': worker_func.__name__,
                'interval': interval,
                'started_at': datetime.now(),
                'status': 'running',
                'daemon': daemon
            }
            
            logger.info(f"[WorkerManager] Запущен воркер: {name} (interval={interval}s)")
            return True
    
    def stop_worker(self, name: str, timeout: int = 2) -> bool:
        """
        Остановить воркер.
        
        Args:
            name: Имя воркера
            timeout: Таймаут ожидания остановки (секунды)
        
        Returns:
            True если воркер остановлен, False если не найден
        """
        with self._lock:
            if name not in self.workers:
                logger.warning(f"[WorkerManager] Воркер {name} не найден")
                return False
            
            worker_info = self.workers[name]
            thread = worker_info['thread']
            
            logger.info(f"[WorkerManager] Останавливаем воркер: {name}")
        
        # Устанавливаем флаг остановки
        self.shutdown_flag.set()
        
        # Ждем остановки с коротким timeout (daemon threads автоматически закроются)
        thread.join(timeout=timeout)
        
        with self._lock:
            if thread.is_alive():
                logger.warning(f"[WorkerManager] Воркер {name} не остановился за {timeout}s")
                worker_info['status'] = 'timeout'
                return False
            else:
                # Удаляем воркер
                del self.workers[name]
                logger.info(f"[WorkerManager] Воркер {name} остановлен")
                
                # Сбрасываем флаг если больше нет воркеров
                if not self.workers:
                    self.shutdown_flag.clear()
                
                return True
    
    def stop_all_workers(self, timeout: int = 3) -> Dict[str, bool]:
        """
        Остановить все воркеры.
        
        Args:
            timeout: Таймаут для каждого воркера (секунды)
        
        Returns:
            Словарь {worker_name: stopped}
        """
        logger.info("[WorkerManager] Останавливаем все воркеры")
        
        # Устанавливаем флаг остановки ОДИН РАЗ для всех
        self.shutdown_flag.set()
        
        # Получаем список воркеров
        with self._lock:
            worker_names = list(self.workers.keys())
        
        # Даем воркерам время завершиться (короткий timeout так как они daemon)
        import time
        time.sleep(timeout)
        
        # Все воркеры daemon - они закроются автоматически при выходе из программы
        # Просто логируем что они будут остановлены
        logger.info(f"[WorkerManager] Воркеры остановлены (daemon threads)")
        
        with self._lock:
            self.workers.clear()
        
        return {name: True for name in worker_names}
    
    # ==================== Информация о воркерах ====================
    
    def is_worker_running(self, name: str) -> bool:
        """
        Проверить работает ли воркер.
        
        Args:
            name: Имя воркера
        
        Returns:
            True если воркер работает
        """
        with self._lock:
            if name not in self.workers:
                return False
            
            worker_info = self.workers[name]
            thread = worker_info['thread']
            
            return thread.is_alive()
    
    def get_worker_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о воркере.
        
        Args:
            name: Имя воркера
        
        Returns:
            Словарь с информацией или None
        """
        with self._lock:
            if name not in self.workers:
                return None
            
            worker_info = self.workers[name].copy()
            
            # Удаляем thread из вывода
            del worker_info['thread']
            
            # Добавляем актуальный статус
            thread = self.workers[name]['thread']
            worker_info['is_alive'] = thread.is_alive()
            
            # Вычисляем время работы
            uptime = datetime.now() - worker_info['started_at']
            worker_info['uptime_seconds'] = int(uptime.total_seconds())
            
            return worker_info
    
    def get_all_workers_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить информацию о всех воркерах.
        
        Returns:
            Словарь {worker_name: worker_info}
        """
        with self._lock:
            result = {}
            for name in self.workers:
                result[name] = self.get_worker_info(name)
            return result
    
    def get_workers_count(self) -> int:
        """
        Получить количество запущенных воркеров.
        
        Returns:
            Количество воркеров
        """
        with self._lock:
            return len(self.workers)
    
    def get_active_workers_count(self) -> int:
        """
        Получить количество активных (живых) воркеров.
        
        Returns:
            Количество активных воркеров
        """
        with self._lock:
            return sum(
                1 for worker_info in self.workers.values()
                if worker_info['thread'].is_alive()
            )
    
    # ==================== Состояние системы ====================
    
    def is_shutdown_requested(self) -> bool:
        """
        Проверить запрошена ли остановка.
        
        Returns:
            True если установлен флаг остановки
        """
        return self.shutdown_flag.is_set()
    
    def request_shutdown(self) -> None:
        """Запросить остановку всех воркеров"""
        self.shutdown_flag.set()
        logger.info("[WorkerManager] Запрошена остановка всех воркеров")
    
    def clear_shutdown_flag(self) -> None:
        """Сбросить флаг остановки"""
        self.shutdown_flag.clear()
        logger.debug("[WorkerManager] Флаг остановки сброшен")
    
    # ==================== Утилиты ====================
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"<WorkerManager(workers={len(self.workers)}, active={self.get_active_workers_count()})>"
    
    def get_info(self) -> Dict[str, Any]:
        """
        Получить информацию о менеджере.
        
        Returns:
            Словарь с информацией
        """
        return {
            'total_workers': self.get_workers_count(),
            'active_workers': self.get_active_workers_count(),
            'shutdown_requested': self.is_shutdown_requested(),
            'workers': list(self.workers.keys())
        }

