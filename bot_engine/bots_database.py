#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Реляционная база данных для хранения ВСЕХ данных bots.py

📋 Обзор:
---------
Все данные bots.py теперь хранятся в SQLite БД вместо JSON файлов.
Это обеспечивает масштабируемость, производительность и надежность.

Архитектура:
-----------
- Путь по умолчанию: data/bots_data.db
- Поддержка UNC путей (сетевые диски)
- WAL режим для параллельных операций
- Автоматическое создание при первом использовании
- Автоматическая миграция данных из JSON

Хранит:
-------
- Состояние ботов (bots_state)
- Реестр позиций (bot_positions_registry)
- RSI кэш (rsi_cache)
- Состояние процессов (process_state)
- Индивидуальные настройки монет (individual_coin_settings)
- Зрелые монеты (mature_coins)
- Кэш проверки зрелости (maturity_check_cache)
- Делистированные монеты (delisted)

Преимущества SQLite БД:
----------------------
✅ Хранит миллиарды записей
✅ Быстрый поиск по индексам
✅ WAL режим для параллельных чтений/записей
✅ Атомарные операции
✅ Поддержка UNC путей (сетевые диски)
✅ Автоматическая миграция схемы
✅ Автоматическая миграция данных из JSON

Использование:
-------------
```python
from bot_engine.bots_database import get_bots_database

# Получаем глобальный экземпляр (singleton)
db = get_bots_database()

# Сохраняем состояние ботов
db.save_bots_state(bots_data, auto_bot_config)

# Загружаем состояние ботов
state = db.load_bots_state()

# Получаем статистику
stats = db.get_database_stats()
```

Настройки производительности:
-----------------------------
- PRAGMA journal_mode=WAL - Write-Ahead Logging
- PRAGMA synchronous=NORMAL - баланс скорости/надежности
- PRAGMA cache_size=-64000 - 64MB кеш
- PRAGMA temp_store=MEMORY - временные таблицы в памяти

Документация:
------------
См. docs/AI_DATABASE_MIGRATION_GUIDE.md для подробного руководства
по архитектуре, миграции и best practices.
"""

import sqlite3
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger('Bots.Database')


class BotsDatabase:
    """
    Реляционная база данных для всех данных bots.py
    """
    
    def __init__(self, db_path: str = None):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных (если None, используется data/bots_data.db)
        """
        if db_path is None:
            # Поддержка UNC путей: используем абсолютный путь относительно текущей рабочей директории
            base_dir = os.getcwd()
            db_path = os.path.join(base_dir, 'data', 'bots_data.db')
            # Нормализуем путь (работает и с UNC путями)
            db_path = os.path.normpath(db_path)
        
        self.db_path = db_path
        self.lock = threading.RLock()
        
        # Создаем директорию если её нет (работает и с UNC путями)
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        except OSError as e:
            logger.error(f"❌ Ошибка создания директории для БД: {e}")
            raise
        
        # Инициализируем базу данных
        self._init_database()
        
        logger.info(f"✅ Bots Database инициализирована: {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """
        Контекстный менеджер для работы с БД
        
        Автоматически настраивает БД для оптимальной производительности:
        - WAL режим для параллельных операций
        - Оптимизированные настройки кеша и синхронизации
        - Автоматический commit/rollback при ошибках
        
        Использование:
        ```python
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bots_state")
            # Автоматический commit при выходе
        ```
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            
            # Включаем WAL режим для лучшей производительности (параллельные чтения/записи)
            # Преимущества WAL:
            # - Читатели не блокируют писателей
            # - Писатели не блокируют читателей
            # - Параллельная работа нескольких процессов
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Оптимизируем для быстрых записей
            # NORMAL - баланс между скоростью и надежностью (быстрее чем FULL, безопаснее чем OFF)
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # Увеличиваем кеш до 64MB для быстрого доступа к часто используемым данным
            conn.execute("PRAGMA cache_size=-64000")  # -64000 = 64MB (отрицательное значение = KB)
            
            # Временные таблицы храним в памяти для скорости
            conn.execute("PRAGMA temp_store=MEMORY")
            
            yield conn
            conn.commit()
            
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Ошибка SQLite: {e}")
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"❌ Неожиданная ошибка БД: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _init_database(self):
        """Создает все таблицы и индексы"""
        # Проверяем, создается ли база впервые
        db_exists = os.path.exists(self.db_path)
        
        # SQLite автоматически создает файл БД при первом подключении
        # Но убедимся, что файл будет создан явно
        if not db_exists:
            # Создаем пустой файл БД
            Path(self.db_path).touch()
            logger.info(f"📁 Создана новая база данных: {self.db_path}")
        else:
            logger.debug(f"📁 Используется существующая база данных: {self.db_path}")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Миграция: добавляем новые поля если их нет
            self._migrate_schema(cursor, conn)
            
            # ==================== ТАБЛИЦА: СОСТОЯНИЕ БОТОВ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bots_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для bots_state
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bots_state_key ON bots_state(key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bots_state_updated ON bots_state(updated_at)")
            
            # ==================== ТАБЛИЦА: РЕЕСТР ПОЗИЦИЙ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_positions_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    position_data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(bot_id, symbol)
                )
            """)
            
            # Индексы для bot_positions_registry
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_bot_id ON bot_positions_registry(bot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON bot_positions_registry(symbol)")
            
            # ==================== ТАБЛИЦА: RSI КЭШ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rsi_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    coins_data_json TEXT NOT NULL,
                    stats_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для rsi_cache
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rsi_cache_timestamp ON rsi_cache(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rsi_cache_created ON rsi_cache(created_at)")
            
            # ==================== ТАБЛИЦА: СОСТОЯНИЕ ПРОЦЕССОВ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS process_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для process_state
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_process_state_key ON process_state(key)")
            
            # ==================== ТАБЛИЦА: ИНДИВИДУАЛЬНЫЕ НАСТРОЙКИ МОНЕТ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS individual_coin_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    settings_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для individual_coin_settings
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_coin_settings_symbol ON individual_coin_settings(symbol)")
            
            # ==================== ТАБЛИЦА: ЗРЕЛЫЕ МОНЕТЫ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mature_coins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    timestamp REAL NOT NULL,
                    maturity_data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для mature_coins
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mature_coins_symbol ON mature_coins(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mature_coins_timestamp ON mature_coins(timestamp)")
            
            # ==================== ТАБЛИЦА: КЭШ ПРОВЕРКИ ЗРЕЛОСТИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS maturity_check_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coins_count INTEGER NOT NULL,
                    config_hash TEXT,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # ==================== ТАБЛИЦА: ДЕЛИСТИРОВАННЫЕ МОНЕТЫ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS delisted (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    delisted_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для delisted
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_delisted_symbol ON delisted(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_delisted_date ON delisted(delisted_at)")
            
            conn.commit()
            
            if not db_exists:
                logger.info("✅ Все таблицы и индексы созданы в новой базе данных")
            else:
                logger.debug("✅ Все таблицы и индексы проверены")
    
    def _migrate_schema(self, cursor, conn):
        """
        Миграция схемы БД: добавляет новые поля если их нет
        
        Это безопасная операция - она только добавляет новые поля,
        не удаляет существующие данные или таблицы.
        
        Пример использования:
        ```python
        # Проверяем наличие поля
        try:
            cursor.execute("SELECT new_field FROM bots_state LIMIT 1")
        except sqlite3.OperationalError:
            # Поля нет - добавляем
            logger.info("📦 Миграция: добавляем new_field в bots_state")
            cursor.execute("ALTER TABLE bots_state ADD COLUMN new_field TEXT")
        ```
        """
        try:
            # В будущем здесь можно добавлять новые поля в существующие таблицы
            # Пока схема новая, миграция не требуется
            
            # Пример для будущих миграций:
            # try:
            #     cursor.execute("SELECT new_field FROM bots_state LIMIT 1")
            # except sqlite3.OperationalError:
            #     logger.info("📦 Миграция: добавляем new_field в bots_state")
            #     cursor.execute("ALTER TABLE bots_state ADD COLUMN new_field TEXT")
            
            conn.commit()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка миграции схемы: {e}")
            # Не прерываем выполнение - миграция схемы не критична
    
    # ==================== МЕТОДЫ ДЛЯ СОСТОЯНИЯ БОТОВ ====================
    
    def save_bots_state(self, bots_data: Dict, auto_bot_config: Dict) -> bool:
        """
        Сохраняет состояние ботов
        
        Args:
            bots_data: Словарь с данными ботов
            auto_bot_config: Конфигурация автобота
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            state_data = {
                'bots': bots_data,
                'auto_bot_config': auto_bot_config,
                'last_saved': now,
                'version': '1.0'
            }
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO bots_state (key, value_json, updated_at, created_at)
                        VALUES (?, ?, ?, COALESCE((SELECT created_at FROM bots_state WHERE key = ?), ?))
                    """, ('main', json.dumps(state_data), now, 'main', now))
                    conn.commit()
            
            logger.debug("💾 Состояние ботов сохранено в БД")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения состояния ботов: {e}")
            return False
    
    def load_bots_state(self) -> Dict:
        """
        Загружает состояние ботов
        
        Returns:
            Словарь с состоянием или пустой словарь
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value_json FROM bots_state WHERE key = ?", ('main',))
                row = cursor.fetchone()
                
                if row:
                    return json.loads(row['value_json'])
                return {}
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки состояния ботов: {e}")
            return {}
    
    # ==================== МЕТОДЫ ДЛЯ РЕЕСТРА ПОЗИЦИЙ ====================
    
    def save_bot_positions_registry(self, registry: Dict) -> bool:
        """
        Сохраняет реестр позиций ботов
        
        Args:
            registry: Словарь {bot_id: {symbol: position_data}}
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Удаляем старые записи
                    cursor.execute("DELETE FROM bot_positions_registry")
                    
                    # Вставляем новые записи
                    for bot_id, positions in registry.items():
                        for symbol, position_data in positions.items():
                            cursor.execute("""
                                INSERT INTO bot_positions_registry 
                                (bot_id, symbol, position_data_json, updated_at, created_at)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                bot_id,
                                symbol,
                                json.dumps(position_data),
                                now,
                                now
                            ))
                    
                    conn.commit()
            
            logger.debug(f"💾 Реестр позиций сохранен в БД ({len(registry)} записей)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения реестра позиций: {e}")
            return False
    
    def load_bot_positions_registry(self) -> Dict:
        """
        Загружает реестр позиций ботов
        
        Returns:
            Словарь {bot_id: {symbol: position_data}}
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT bot_id, symbol, position_data_json FROM bot_positions_registry")
                rows = cursor.fetchall()
                
                registry = {}
                for row in rows:
                    bot_id = row['bot_id']
                    symbol = row['symbol']
                    position_data = json.loads(row['position_data_json'])
                    
                    if bot_id not in registry:
                        registry[bot_id] = {}
                    registry[bot_id][symbol] = position_data
                
                return registry
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки реестра позиций: {e}")
            return {}
    
    # ==================== МЕТОДЫ ДЛЯ RSI КЭША ====================
    
    def save_rsi_cache(self, coins_data: Dict, stats: Dict = None) -> bool:
        """
        Сохраняет RSI кэш
        
        Args:
            coins_data: Словарь с данными монет
            stats: Статистика (опционально)
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            timestamp = now
            
            cache_data = {
                'timestamp': timestamp,
                'coins': coins_data,
                'stats': stats or {}
            }
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO rsi_cache (timestamp, coins_data_json, stats_json, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        timestamp,
                        json.dumps(coins_data),
                        json.dumps(stats) if stats else None,
                        now
                    ))
                    conn.commit()
            
            logger.debug("💾 RSI кэш сохранен в БД")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения RSI кэша: {e}")
            return False
    
    def load_rsi_cache(self, max_age_hours: float = 6.0) -> Optional[Dict]:
        """
        Загружает последний RSI кэш (если не старше max_age_hours)
        
        Args:
            max_age_hours: Максимальный возраст кэша в часах
        
        Returns:
            Словарь с данными кэша или None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT timestamp, coins_data_json, stats_json, created_at
                    FROM rsi_cache
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # Проверяем возраст кэша
                cache_time = datetime.fromisoformat(row['timestamp'])
                age_hours = (datetime.now() - cache_time).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    logger.debug(f"⚠️ RSI кэш устарел ({age_hours:.1f} часов)")
                    return None
                
                return {
                    'timestamp': row['timestamp'],
                    'coins': json.loads(row['coins_data_json']),
                    'stats': json.loads(row['stats_json']) if row['stats_json'] else {}
                }
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки RSI кэша: {e}")
            return None
    
    def clear_rsi_cache(self) -> bool:
        """Очищает RSI кэш"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM rsi_cache")
                    conn.commit()
            logger.info("✅ RSI кэш очищен в БД")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки RSI кэша: {e}")
            return False
    
    # ==================== МЕТОДЫ ДЛЯ СОСТОЯНИЯ ПРОЦЕССОВ ====================
    
    def save_process_state(self, process_state: Dict) -> bool:
        """
        Сохраняет состояние процессов
        
        Args:
            process_state: Словарь с состоянием процессов
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Удаляем старые записи
                    cursor.execute("DELETE FROM process_state")
                    
                    # Сохраняем как одну запись
                    state_data = {
                        'process_state': process_state,
                        'last_saved': now,
                        'version': '1.0'
                    }
                    
                    cursor.execute("""
                        INSERT INTO process_state (key, value_json, updated_at, created_at)
                        VALUES (?, ?, ?, ?)
                    """, ('main', json.dumps(state_data), now, now))
                    
                    conn.commit()
            
            logger.debug("💾 Состояние процессов сохранено в БД")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения состояния процессов: {e}")
            return False
    
    def load_process_state(self) -> Dict:
        """
        Загружает состояние процессов
        
        Returns:
            Словарь с состоянием процессов или пустой словарь
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value_json FROM process_state WHERE key = ?", ('main',))
                row = cursor.fetchone()
                
                if row:
                    data = json.loads(row['value_json'])
                    return data.get('process_state', {})
                return {}
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки состояния процессов: {e}")
            return {}
    
    # ==================== МЕТОДЫ ДЛЯ ИНДИВИДУАЛЬНЫХ НАСТРОЕК ====================
    
    def save_individual_coin_settings(self, settings: Dict) -> bool:
        """
        Сохраняет индивидуальные настройки монет
        
        Args:
            settings: Словарь {symbol: settings_dict}
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Удаляем старые записи
                    cursor.execute("DELETE FROM individual_coin_settings")
                    
                    # Вставляем новые записи
                    for symbol, symbol_settings in settings.items():
                        cursor.execute("""
                            INSERT INTO individual_coin_settings 
                            (symbol, settings_json, updated_at, created_at)
                            VALUES (?, ?, ?, ?)
                        """, (
                            symbol,
                            json.dumps(symbol_settings),
                            now,
                            now
                        ))
                    
                    conn.commit()
            
            logger.debug(f"💾 Индивидуальные настройки сохранены в БД ({len(settings)} монет)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения индивидуальных настроек: {e}")
            return False
    
    def load_individual_coin_settings(self) -> Dict:
        """
        Загружает индивидуальные настройки монет
        
        Returns:
            Словарь {symbol: settings_dict}
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT symbol, settings_json FROM individual_coin_settings")
                rows = cursor.fetchall()
                
                settings = {}
                for row in rows:
                    symbol = row['symbol']
                    settings[symbol] = json.loads(row['settings_json'])
                
                return settings
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки индивидуальных настроек: {e}")
            return {}
    
    def remove_all_individual_coin_settings(self) -> bool:
        """Удаляет все индивидуальные настройки"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM individual_coin_settings")
                    conn.commit()
            logger.info("✅ Все индивидуальные настройки удалены из БД")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления индивидуальных настроек: {e}")
            return False
    
    # ==================== МЕТОДЫ ДЛЯ ЗРЕЛЫХ МОНЕТ ====================
    
    def save_mature_coins(self, mature_coins: Dict) -> bool:
        """
        Сохраняет зрелые монеты
        
        Args:
            mature_coins: Словарь {symbol: {timestamp: float, maturity_data: dict}}
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Удаляем старые записи
                    cursor.execute("DELETE FROM mature_coins")
                    
                    # Вставляем новые записи
                    for symbol, coin_data in mature_coins.items():
                        timestamp = coin_data.get('timestamp', 0.0)
                        maturity_data = coin_data.get('maturity_data', {})
                        
                        cursor.execute("""
                            INSERT INTO mature_coins 
                            (symbol, timestamp, maturity_data_json, updated_at, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            symbol,
                            timestamp,
                            json.dumps(maturity_data),
                            now,
                            now
                        ))
                    
                    conn.commit()
            
            logger.debug(f"💾 Зрелые монеты сохранены в БД ({len(mature_coins)} монет)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения зрелых монет: {e}")
            return False
    
    def load_mature_coins(self) -> Dict:
        """
        Загружает зрелые монеты
        
        Returns:
            Словарь {symbol: {timestamp: float, maturity_data: dict}}
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT symbol, timestamp, maturity_data_json FROM mature_coins")
                rows = cursor.fetchall()
                
                mature_coins = {}
                for row in rows:
                    symbol = row['symbol']
                    mature_coins[symbol] = {
                        'timestamp': row['timestamp'],
                        'maturity_data': json.loads(row['maturity_data_json'])
                    }
                
                return mature_coins
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки зрелых монет: {e}")
            return {}
    
    # ==================== МЕТОДЫ ДЛЯ КЭША ПРОВЕРКИ ЗРЕЛОСТИ ====================
    
    def save_maturity_check_cache(self, coins_count: int, config_hash: str = None) -> bool:
        """
        Сохраняет кэш проверки зрелости
        
        Args:
            coins_count: Количество монет
            config_hash: Хеш конфигурации (опционально)
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Удаляем старые записи
                    cursor.execute("DELETE FROM maturity_check_cache")
                    
                    # Вставляем новую запись
                    cursor.execute("""
                        INSERT INTO maturity_check_cache 
                        (coins_count, config_hash, updated_at, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (coins_count, config_hash, now, now))
                    
                    conn.commit()
            
            logger.debug("💾 Кэш проверки зрелости сохранен в БД")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша проверки зрелости: {e}")
            return False
    
    def load_maturity_check_cache(self) -> Dict:
        """
        Загружает кэш проверки зрелости
        
        Returns:
            Словарь {coins_count: int, config_hash: str}
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT coins_count, config_hash
                    FROM maturity_check_cache
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                
                if row:
                    return {
                        'coins_count': row['coins_count'],
                        'config_hash': row['config_hash']
                    }
                return {'coins_count': 0, 'config_hash': None}
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кэша проверки зрелости: {e}")
            return {'coins_count': 0, 'config_hash': None}
    
    # ==================== МЕТОДЫ ДЛЯ ДЕЛИСТИРОВАННЫХ МОНЕТ ====================
    
    def save_delisted_coins(self, delisted: list) -> bool:
        """
        Сохраняет делистированные монеты
        
        Args:
            delisted: Список символов монет
        
        Returns:
            True если успешно сохранено
        """
        try:
            now = datetime.now().isoformat()
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Удаляем старые записи
                    cursor.execute("DELETE FROM delisted")
                    
                    # Вставляем новые записи
                    for symbol in delisted:
                        cursor.execute("""
                            INSERT INTO delisted (symbol, delisted_at, created_at)
                            VALUES (?, ?, ?)
                        """, (symbol, now, now))
                    
                    conn.commit()
            
            logger.debug(f"💾 Делистированные монеты сохранены в БД ({len(delisted)} монет)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения делистированных монет: {e}")
            return False
    
    def load_delisted_coins(self) -> list:
        """
        Загружает делистированные монеты
        
        Returns:
            Список символов монет
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT symbol FROM delisted")
                rows = cursor.fetchall()
                
                return [row['symbol'] for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки делистированных монет: {e}")
            return []
    
    def is_coin_delisted(self, symbol: str) -> bool:
        """Проверяет, делистирована ли монета"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM delisted WHERE symbol = ?", (symbol,))
                return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(f"❌ Ошибка проверки делистирования: {e}")
            return False
    
    # ==================== МЕТОДЫ МИГРАЦИИ ====================
    
    def migrate_json_to_database(self) -> Dict[str, int]:
        """
        Мигрирует данные из JSON файлов в БД (однократно)
        
        Returns:
            Словарь с количеством мигрированных записей для каждого файла
        """
        migration_stats = {}
        
        try:
            # Миграция bots_state.json
            bots_state_file = 'data/bots_state.json'
            if os.path.exists(bots_state_file):
                try:
                    with open(bots_state_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data:
                            bots_data = data.get('bots', {})
                            auto_bot_config = data.get('auto_bot_config', {})
                            if self.save_bots_state(bots_data, auto_bot_config):
                                migration_stats['bots_state'] = 1
                                logger.info("📦 Мигрирован bots_state.json в БД")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции bots_state.json: {e}")
            
            # Миграция bot_positions_registry.json
            positions_file = 'data/bot_positions_registry.json'
            if os.path.exists(positions_file):
                try:
                    with open(positions_file, 'r', encoding='utf-8') as f:
                        registry = json.load(f)
                        if registry:
                            if self.save_bot_positions_registry(registry):
                                migration_stats['bot_positions_registry'] = len(registry)
                                logger.info(f"📦 Мигрирован bot_positions_registry.json в БД ({len(registry)} записей)")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции bot_positions_registry.json: {e}")
            
            # Миграция rsi_cache.json
            rsi_cache_file = 'data/rsi_cache.json'
            if os.path.exists(rsi_cache_file):
                try:
                    with open(rsi_cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        if cache_data:
                            coins_data = cache_data.get('coins', {})
                            stats = cache_data.get('stats', {})
                            if self.save_rsi_cache(coins_data, stats):
                                migration_stats['rsi_cache'] = 1
                                logger.info("📦 Мигрирован rsi_cache.json в БД")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции rsi_cache.json: {e}")
            
            # Миграция process_state.json
            process_state_file = 'data/process_state.json'
            if os.path.exists(process_state_file):
                try:
                    with open(process_state_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data:
                            process_state = data.get('process_state', {})
                            if self.save_process_state(process_state):
                                migration_stats['process_state'] = 1
                                logger.info("📦 Мигрирован process_state.json в БД")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции process_state.json: {e}")
            
            # Миграция individual_coin_settings.json
            settings_file = 'data/individual_coin_settings.json'
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        if settings:
                            if self.save_individual_coin_settings(settings):
                                migration_stats['individual_coin_settings'] = len(settings)
                                logger.info(f"📦 Мигрирован individual_coin_settings.json в БД ({len(settings)} записей)")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции individual_coin_settings.json: {e}")
            
            # Миграция mature_coins.json
            mature_coins_file = 'data/mature_coins.json'
            if os.path.exists(mature_coins_file):
                try:
                    with open(mature_coins_file, 'r', encoding='utf-8') as f:
                        mature_coins = json.load(f)
                        if mature_coins:
                            if self.save_mature_coins(mature_coins):
                                migration_stats['mature_coins'] = len(mature_coins)
                                logger.info(f"📦 Мигрирован mature_coins.json в БД ({len(mature_coins)} записей)")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции mature_coins.json: {e}")
            
            # Миграция maturity_check_cache.json
            maturity_cache_file = 'data/maturity_check_cache.json'
            if os.path.exists(maturity_cache_file):
                try:
                    with open(maturity_cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                        if cache_data:
                            coins_count = cache_data.get('coins_count', 0)
                            config_hash = cache_data.get('config_hash')
                            if self.save_maturity_check_cache(coins_count, config_hash):
                                migration_stats['maturity_check_cache'] = 1
                                logger.info("📦 Мигрирован maturity_check_cache.json в БД")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции maturity_check_cache.json: {e}")
            
            # Миграция delisted.json
            delisted_file = 'data/delisted.json'
            if os.path.exists(delisted_file):
                try:
                    with open(delisted_file, 'r', encoding='utf-8') as f:
                        delisted = json.load(f)
                        if delisted and isinstance(delisted, list):
                            if self.save_delisted_coins(delisted):
                                migration_stats['delisted'] = len(delisted)
                                logger.info(f"📦 Мигрирован delisted.json в БД ({len(delisted)} записей)")
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка миграции delisted.json: {e}")
            
            if migration_stats:
                logger.info(f"✅ Миграция завершена: {sum(migration_stats.values())} записей мигрировано")
            
        except Exception as e:
            logger.error(f"❌ Ошибка миграции JSON в БД: {e}")
        
        return migration_stats
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Получает общую статистику базы данных
        
        Returns:
            Словарь со статистикой:
            {
                'bots_state_count': int,
                'bot_positions_registry_count': int,
                'rsi_cache_count': int,
                'process_state_count': int,
                'individual_coin_settings_count': int,
                'mature_coins_count': int,
                'maturity_check_cache_count': int,
                'delisted_count': int,
                'database_size_mb': float
            }
        
        Example:
            ```python
            db = get_bots_database()
            stats = db.get_database_stats()
            print(f"Ботов в БД: {stats['bots_state_count']}")
            print(f"Размер БД: {stats['database_size_mb']:.2f} MB")
            ```
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Подсчеты по таблицам
                tables = [
                    'bots_state', 'bot_positions_registry', 'rsi_cache', 
                    'process_state', 'individual_coin_settings', 'mature_coins',
                    'maturity_check_cache', 'delisted'
                ]
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        stats[f"{table}_count"] = cursor.fetchone()[0]
                    except sqlite3.Error as e:
                        logger.debug(f"⚠️ Ошибка подсчета записей в {table}: {e}")
                        stats[f"{table}_count"] = 0
                
                # Размер базы данных (включая WAL файлы)
                db_size = 0
                if os.path.exists(self.db_path):
                    db_size += os.path.getsize(self.db_path)
                # Добавляем размер WAL файла если есть
                wal_path = f"{self.db_path}-wal"
                if os.path.exists(wal_path):
                    db_size += os.path.getsize(wal_path)
                # Добавляем размер SHM файла если есть
                shm_path = f"{self.db_path}-shm"
                if os.path.exists(shm_path):
                    db_size += os.path.getsize(shm_path)
                
                stats['database_size_mb'] = db_size / 1024 / 1024
                
                return stats
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики БД: {e}")
            return {}


# Глобальный экземпляр базы данных
_bots_database_instance = None
_bots_database_lock = threading.Lock()


def get_bots_database(db_path: str = None) -> BotsDatabase:
    """
    Получает глобальный экземпляр базы данных Bots
    
    База данных создается автоматически при первом вызове, если её еще нет.
    Все таблицы создаются автоматически. При первом запуске выполняется
    автоматическая миграция данных из JSON файлов в БД.
    
    Args:
        db_path: Путь к файлу базы данных (если None, используется data/bots_data.db)
    
    Returns:
        Экземпляр BotsDatabase
    """
    global _bots_database_instance
    
    with _bots_database_lock:
        if _bots_database_instance is None:
            logger.info("🔧 Инициализация Bots Database...")
            _bots_database_instance = BotsDatabase(db_path)
            
            # Автоматическая миграция при первом запуске (данные из JSON в БД)
            try:
                migration_stats = _bots_database_instance.migrate_json_to_database()
                if migration_stats:
                    logger.info(f"✅ Автоматическая миграция выполнена: {migration_stats}")
                else:
                    logger.debug("ℹ️ Миграция не требуется (нет данных в JSON или уже мигрировано)")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка автоматической миграции: {e}")
                # Продолжаем работу, даже если миграция не удалась
        
        return _bots_database_instance

