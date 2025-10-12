"""
ConfigManager - управление конфигурациями системы.

Этот менеджер инкапсулирует всю логику работы с конфигурациями
(Auto Bot, System Config, и т.д.).
"""

import os
import json
import threading
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Менеджер для управления конфигурациями.
    
    Инкапсулирует загрузку, сохранение и доступ к конфигурациям,
    обеспечивая thread-safety.
    
    Attributes:
        config_dir: Директория с конфигурационными файлами
        auto_bot_config: Конфигурация Auto Bot
        system_config: Системная конфигурация
        _lock: Блокировка для thread-safety
    """
    
    def __init__(self, config_dir: str = 'data'):
        """
        Инициализация менеджера конфигураций.
        
        Args:
            config_dir: Путь к директории с конфигами
        """
        self.config_dir = config_dir
        self._lock = threading.Lock()
        
        # Создаем директорию если её нет
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Инициализируем конфиги дефолтными значениями
        self.auto_bot_config = self._get_default_auto_bot_config()
        self.system_config = self._get_default_system_config()
        
        logger.info(f"[ConfigManager] Инициализирован с директорией: {config_dir}")
    
    # ==================== Дефолтные конфигурации ====================
    
    def _get_default_auto_bot_config(self) -> Dict[str, Any]:
        """Получить дефолтную конфигурацию Auto Bot"""
        return {
            'enabled': False,  # ВСЕГДА выключен по умолчанию
            'max_concurrent_bots': 5,
            'rsi_oversold': 29,
            'rsi_overbought': 71,
            'rsi_time_filter_enabled': True,
            'rsi_time_filter_candles': 4,
            'exit_scam_filter_enabled': True,
            'maturity_check_enabled': True,
            'risk_per_trade': 1.0,
            'stop_loss_percent': 5.0,
            'take_profit_percent': 10.0,
            'leverage': 5
        }
    
    def _get_default_system_config(self) -> Dict[str, Any]:
        """Получить дефолтную системную конфигурацию"""
        return {
            'rsi_period': 14,
            'rsi_timeframe': '6h',
            'ema_fast': 50,
            'ema_slow': 200,
            'update_interval': 300,
            'max_retries': 3,
            'request_timeout': 30
        }
    
    # ==================== Auto Bot Config ====================
    
    def get_auto_bot_config(self) -> Dict[str, Any]:
        """
        Получить конфигурацию Auto Bot.
        
        Returns:
            Словарь с конфигурацией
        """
        with self._lock:
            return deepcopy(self.auto_bot_config)
    
    def update_auto_bot_config(self, updates: Dict[str, Any]) -> None:
        """
        Обновить конфигурацию Auto Bot.
        
        Args:
            updates: Словарь с обновлениями
        """
        with self._lock:
            self.auto_bot_config.update(updates)
            self._save_auto_bot_config()
            logger.info(f"[ConfigManager] Обновлена конфигурация Auto Bot: {list(updates.keys())}")
    
    def load_auto_bot_config(self) -> bool:
        """
        Загрузить конфигурацию Auto Bot из файла.
        
        Returns:
            True если загружена, False если файл не найден
        """
        config_file = os.path.join(self.config_dir, 'auto_bot_config.json')
        
        with self._lock:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        saved_config = json.load(f)
                        self.auto_bot_config.update(saved_config)
                        
                        # ✅ ИСПРАВЛЕНО: Сохраняем enabled из файла!
                        # self.auto_bot_config['enabled'] = False  # УДАЛЕНО!
                        
                    logger.info(f"[ConfigManager] Загружена конфигурация Auto Bot из {config_file} (enabled={self.auto_bot_config.get('enabled')})")
                    return True
                except Exception as e:
                    logger.error(f"[ConfigManager] Ошибка загрузки конфигурации Auto Bot: {e}")
                    return False
            else:
                logger.info(f"[ConfigManager] Файл {config_file} не найден, используем дефолтные настройки")
                return False
    
    def _save_auto_bot_config(self) -> None:
        """Сохранить конфигурацию Auto Bot в файл (внутренний метод)"""
        config_file = os.path.join(self.config_dir, 'auto_bot_config.json')
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.auto_bot_config, f, indent=2, ensure_ascii=False)
            logger.debug(f"[ConfigManager] Сохранена конфигурация Auto Bot в {config_file}")
        except Exception as e:
            logger.error(f"[ConfigManager] Ошибка сохранения конфигурации Auto Bot: {e}")
    
    def save_auto_bot_config(self) -> bool:
        """
        Сохранить конфигурацию Auto Bot в файл (публичный метод).
        
        Returns:
            True если сохранена успешно
        """
        with self._lock:
            try:
                self._save_auto_bot_config()
                return True
            except Exception as e:
                logger.error(f"[ConfigManager] Ошибка сохранения: {e}")
                return False
    
    def restore_default_auto_bot_config(self) -> None:
        """Восстановить дефолтную конфигурацию Auto Bot"""
        with self._lock:
            self.auto_bot_config = self._get_default_auto_bot_config()
            self._save_auto_bot_config()
            logger.info("[ConfigManager] Восстановлена дефолтная конфигурация Auto Bot")
    
    # ==================== System Config ====================
    
    def get_system_config(self) -> Dict[str, Any]:
        """
        Получить системную конфигурацию.
        
        Returns:
            Словарь с конфигурацией
        """
        with self._lock:
            return deepcopy(self.system_config)
    
    def update_system_config(self, updates: Dict[str, Any]) -> None:
        """
        Обновить системную конфигурацию.
        
        Args:
            updates: Словарь с обновлениями
        """
        with self._lock:
            self.system_config.update(updates)
            self._save_system_config()
            logger.info(f"[ConfigManager] Обновлена системная конфигурация: {list(updates.keys())}")
    
    def load_system_config(self) -> bool:
        """
        Загрузить системную конфигурацию из файла.
        
        Returns:
            True если загружена, False если файл не найден
        """
        config_file = os.path.join(self.config_dir, 'system_config.json')
        
        with self._lock:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        saved_config = json.load(f)
                        self.system_config.update(saved_config)
                    logger.info(f"[ConfigManager] Загружена системная конфигурация из {config_file}")
                    return True
                except Exception as e:
                    logger.error(f"[ConfigManager] Ошибка загрузки системной конфигурации: {e}")
                    return False
            else:
                logger.info(f"[ConfigManager] Файл {config_file} не найден, используем дефолтные настройки")
                return False
    
    def _save_system_config(self) -> None:
        """Сохранить системную конфигурацию в файл (внутренний метод)"""
        config_file = os.path.join(self.config_dir, 'system_config.json')
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.system_config, f, indent=2, ensure_ascii=False)
            logger.debug(f"[ConfigManager] Сохранена системная конфигурация в {config_file}")
        except Exception as e:
            logger.error(f"[ConfigManager] Ошибка сохранения системной конфигурации: {e}")
    
    def save_system_config(self) -> bool:
        """
        Сохранить системную конфигурацию в файл (публичный метод).
        
        Returns:
            True если сохранена успешно
        """
        with self._lock:
            try:
                self._save_system_config()
                return True
            except Exception as e:
                logger.error(f"[ConfigManager] Ошибка сохранения: {e}")
                return False
    
    # ==================== Загрузка всех конфигов ====================
    
    def load_all(self) -> Dict[str, bool]:
        """
        Загрузить все конфигурации из файлов.
        
        Returns:
            Словарь {config_name: success}
        """
        results = {
            'auto_bot_config': self.load_auto_bot_config(),
            'system_config': self.load_system_config()
        }
        logger.info(f"[ConfigManager] Загружены конфигурации: {results}")
        return results
    
    def save_all(self) -> Dict[str, bool]:
        """
        Сохранить все конфигурации в файлы.
        
        Returns:
            Словарь {config_name: success}
        """
        results = {
            'auto_bot_config': self.save_auto_bot_config(),
            'system_config': self.save_system_config()
        }
        logger.info(f"[ConfigManager] Сохранены конфигурации: {results}")
        return results
    
    # ==================== Утилиты ====================
    
    def get_config_value(self, config_name: str, key: str, default: Any = None) -> Any:
        """
        Получить значение из конфигурации.
        
        Args:
            config_name: Имя конфигурации ('auto_bot' или 'system')
            key: Ключ значения
            default: Значение по умолчанию
        
        Returns:
            Значение или default
        """
        with self._lock:
            if config_name == 'auto_bot':
                return self.auto_bot_config.get(key, default)
            elif config_name == 'system':
                return self.system_config.get(key, default)
            else:
                logger.warning(f"[ConfigManager] Неизвестная конфигурация: {config_name}")
                return default
    
    def __repr__(self) -> str:
        """Строковое представление"""
        return f"<ConfigManager(config_dir={self.config_dir})>"
    
    def get_info(self) -> Dict[str, Any]:
        """
        Получить информацию о менеджере.
        
        Returns:
            Словарь с информацией
        """
        with self._lock:
            return {
                'config_dir': self.config_dir,
                'auto_bot_enabled': self.auto_bot_config.get('enabled', False),
                'auto_bot_max_bots': self.auto_bot_config.get('max_concurrent_bots', 0),
                'system_rsi_period': self.system_config.get('rsi_period', 14),
                'system_timeframe': self.system_config.get('rsi_timeframe', '6h')
            }

