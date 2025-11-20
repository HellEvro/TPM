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
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, Tuple, List
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
    
    def _check_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Проверяет целостность БД
        
        Returns:
            Tuple[bool, Optional[str]]: (is_ok, error_message)
            is_ok = True если БД в порядке, False если есть проблемы
            error_message = описание проблемы или None
        """
        if not os.path.exists(self.db_path):
            return True, None  # Нет БД - это нормально, будет создана
        
        try:
            # Используем прямое подключение для проверки целостности (не через retry)
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            cursor = conn.cursor()
            
            # Быстрая проверка целостности (быстрее чем integrity_check)
            cursor.execute("PRAGMA quick_check")
            result = cursor.fetchone()[0]
            conn.close()
            
            if result == "ok":
                return True, None
            else:
                # Есть проблемы - делаем полную проверку для деталей
                conn = sqlite3.connect(self.db_path, timeout=60.0)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                integrity_results = cursor.fetchall()
                error_details = "; ".join([row[0] for row in integrity_results if row[0] != "ok"])
                conn.close()
                return False, error_details or result
        except Exception as e:
            return False, f"Ошибка проверки целостности: {e}"
    
    def _backup_database(self) -> Optional[str]:
        """
        Создает резервную копию БД перед удалением
        
        Returns:
            Путь к резервной копии или None если не удалось создать
        """
        if not os.path.exists(self.db_path):
            return None
        
        try:
            # Создаем имя резервной копии с timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}.backup_{timestamp}"
            
            # Копируем БД и связанные файлы
            shutil.copy2(self.db_path, backup_path)
            
            # Копируем WAL и SHM файлы если есть
            wal_file = self.db_path + '-wal'
            shm_file = self.db_path + '-shm'
            if os.path.exists(wal_file):
                shutil.copy2(wal_file, f"{backup_path}-wal")
            if os.path.exists(shm_file):
                shutil.copy2(shm_file, f"{backup_path}-shm")
            
            logger.warning(f"💾 Создана резервная копия БД: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"❌ Ошибка создания резервной копии БД: {e}")
            return None
    
    def _check_database_has_data(self) -> bool:
        """
        Проверяет, есть ли данные в БД (пытается прочитать хотя бы одну таблицу)
        
        Returns:
            True если в БД есть данные, False если БД пуста или повреждена
        """
        if not os.path.exists(self.db_path):
            return False
        
        try:
            # Пытаемся подключиться в режиме только чтения
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=10.0)
            cursor = conn.cursor()
            
            # Проверяем наличие таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            if not tables:
                conn.close()
                return False
            
            # Пытаемся посчитать записи в основных таблицах
            main_tables = ['bots_state', 'bot_positions_registry', 'individual_coin_settings', 'mature_coins']
            for table in main_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    if count > 0:
                        conn.close()
                        return True
                except:
                    continue
            
            conn.close()
            return False
        except Exception as e:
            logger.debug(f"⚠️ Не удалось проверить данные в БД: {e}")
            return False
    
    def _recreate_database(self):
        """
        Удаляет поврежденную БД и создает новую (только при явной ошибке подключения)
        
        ВАЖНО: Перед удалением создает резервную копию и проверяет наличие данных
        """
        if not os.path.exists(self.db_path):
            return
        
        try:
            # Проверяем, есть ли данные в БД
            has_data = self._check_database_has_data()
            
            if has_data:
                # Если есть данные - ОБЯЗАТЕЛЬНО создаем резервную копию
                backup_path = self._backup_database()
                if not backup_path:
                    # Не удаляем БД если не удалось создать резервную копию!
                    logger.error(f"❌ КРИТИЧНО: Не удалось создать резервную копию БД с данными!")
                    logger.error(f"❌ БД НЕ БУДЕТ УДАЛЕНА для защиты данных!")
                    raise Exception("Не удалось создать резервную копию БД с данными - удаление отменено")
                logger.warning(f"⚠️ ВНИМАНИЕ: БД содержит данные, создана резервная копия: {backup_path}")
            else:
                # Если данных нет - все равно создаем резервную копию на всякий случай
                self._backup_database()
            
            # Удаляем поврежденный файл и связанные файлы WAL/SHM
            wal_file = self.db_path + '-wal'
            shm_file = self.db_path + '-shm'
            
            if os.path.exists(wal_file):
                os.remove(wal_file)
            if os.path.exists(shm_file):
                os.remove(shm_file)
            os.remove(self.db_path)
            
            logger.warning(f"🗑️ Удалена поврежденная БД: {self.db_path}")
            if has_data:
                logger.warning(f"💾 Данные сохранены в резервной копии - можно восстановить при необходимости")
        except Exception as e:
            logger.error(f"❌ Ошибка удаления поврежденной БД: {e}")
            raise
    
    def _repair_database(self) -> bool:
        """
        Пытается исправить поврежденную БД
        
        Returns:
            True если удалось исправить, False в противном случае
        """
        try:
            logger.warning("🔧 Попытка исправления БД...")
            
            # Создаем резервную копию перед исправлением
            backup_path = self._backup_database()
            if not backup_path:
                logger.error("❌ Не удалось создать резервную копию перед исправлением")
                return False
            
            # Пытаемся использовать VACUUM для исправления
            try:
                # Подключаемся без retry для VACUUM (может быть долго)
                conn = sqlite3.connect(self.db_path, timeout=300.0)  # 5 минут для VACUUM
                cursor = conn.cursor()
                logger.info("🔧 Выполняю VACUUM для исправления БД (это может занять время)...")
                cursor.execute("VACUUM")
                conn.commit()
                conn.close()
                logger.info("✅ VACUUM выполнен")
            except Exception as vacuum_error:
                logger.warning(f"⚠️ VACUUM не помог: {vacuum_error}")
                try:
                    conn.close()
                except:
                    pass
            
            # Проверяем, исправилась ли БД
            is_ok, error_msg = self._check_integrity()
            if is_ok:
                logger.info("✅ БД успешно исправлена с помощью VACUUM")
                return True
            else:
                logger.warning(f"⚠️ БД все еще повреждена после VACUUM: {error_msg}")
                # Пытаемся восстановить из резервной копии (которая была создана ДО повреждения)
                logger.info("🔄 Попытка восстановления из резервной копии...")
                # Ищем более старую резервную копию (до текущей)
                backups = self.list_backups()
                if backups and len(backups) > 1:
                    # Используем предпоследнюю копию (последняя - это та, что мы только что создали)
                    older_backup = backups[1]['path']
                    logger.info(f"📦 Восстанавливаю из более старой резервной копии: {older_backup}")
                    return self.restore_from_backup(older_backup)
                elif backups:
                    # Только одна копия - используем её
                    logger.info(f"📦 Восстанавливаю из резервной копии: {backups[0]['path']}")
                    return self.restore_from_backup(backups[0]['path'])
                else:
                    logger.error("❌ Нет доступных резервных копий для восстановления")
                    return False
        except Exception as e:
            logger.error(f"❌ Ошибка исправления БД: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    @contextmanager
    def _get_connection(self, retry_on_locked: bool = True, max_retries: int = 5):
        """
        Контекстный менеджер для работы с БД с поддержкой retry при блокировках и автоматическим исправлением ошибок
        
        Args:
            retry_on_locked: Повторять попытки при ошибке "database is locked"
            max_retries: Максимальное количество попыток при блокировке
        
        Автоматически настраивает БД для оптимальной производительности:
        - WAL режим для параллельных операций
        - Оптимизированные настройки кеша и синхронизации
        - Автоматический commit/rollback при ошибках
        - Retry логика при блокировках (до 5 попыток с экспоненциальной задержкой)
        - Автоматическое исправление критических ошибок:
          * `database disk image is malformed` - автоматическое исправление через VACUUM/restore
          * `disk I/O error` - автоматическое исправление и повтор операции
        
        Критические ошибки обрабатываются автоматически:
        1. При обнаружении ошибки автоматически запускается `_repair_database()`
        2. После исправления операция автоматически повторяется один раз
        3. Перед исправлением создается резервная копия
        
        Использование:
        ```python
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bots_state")
            # Автоматический commit при выходе
        ```
        """
        last_error = None
        
        for attempt in range(max_retries if retry_on_locked else 1):
            try:
                # Увеличиваем timeout для операций записи при параллельном доступе
                # 60 секунд должно быть достаточно для работы через сеть
                conn = sqlite3.connect(self.db_path, timeout=60.0)
                conn.row_factory = sqlite3.Row
                
                # Включаем WAL режим для лучшей производительности (параллельные чтения)
                # WAL позволяет нескольким читателям работать одновременно с одним писателем
                conn.execute("PRAGMA journal_mode=WAL")
                # Оптимизируем для быстрых записей
                conn.execute("PRAGMA synchronous=NORMAL")  # Быстрее чем FULL, но безопаснее чем OFF
                conn.execute("PRAGMA cache_size=-64000")  # 64MB кеш
                conn.execute("PRAGMA temp_store=MEMORY")  # Временные таблицы в памяти
                
                # Успешное подключение
                try:
                    yield conn
                    conn.commit()
                    conn.close()
                    return  # Успешно выполнили операцию
                except sqlite3.OperationalError as e:
                    error_str = str(e).lower()
                    
                    # Обрабатываем ошибки блокировки
                    if "database is locked" in error_str or "locked" in error_str:
                        conn.rollback()
                        conn.close()
                        last_error = e
                        if retry_on_locked and attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 0.5  # Экспоненциальная задержка: 0.5s, 1s, 1.5s...
                            logger.debug(f"⚠️ БД заблокирована (попытка {attempt + 1}/{max_retries}), ждем {wait_time:.1f}s...")
                            time.sleep(wait_time)
                            continue  # Повторяем попытку
                        else:
                            # Превышено количество попыток
                            logger.warning(f"⚠️ БД заблокирована после {max_retries} попыток")
                            raise
                    
                    # КРИТИЧНО: Обработка ошибок I/O
                    elif "disk i/o error" in error_str or "i/o error" in error_str:
                        conn.rollback()
                        conn.close()
                        logger.error(f"❌ КРИТИЧНО: Ошибка I/O при работе с БД: {e}")
                        logger.warning("🔧 Попытка автоматического исправления...")
                        if attempt == 0:
                            # Пытаемся исправить только один раз
                            if self._repair_database():
                                logger.info("✅ БД исправлена, повторяем операцию...")
                                time.sleep(1)  # Небольшая задержка перед повтором
                                continue
                            else:
                                logger.error("❌ Не удалось исправить БД после I/O ошибки")
                                raise
                        else:
                            raise
                    else:
                        # Другие OperationalError - не повторяем
                        conn.rollback()
                        conn.close()
                        raise
                except Exception as e:
                    try:
                        conn.rollback()
                    except:
                        pass
                    try:
                        conn.close()
                    except:
                        pass
                    raise e
                    
            except sqlite3.DatabaseError as e:
                error_str = str(e).lower()
                
                # КРИТИЧНО: Обработка ошибки "database disk image is malformed"
                if "database disk image is malformed" in error_str or "malformed" in error_str:
                    logger.error(f"❌ КРИТИЧНО: БД повреждена (malformed): {self.db_path}")
                    logger.error(f"❌ Ошибка: {e}")
                    logger.warning("🔧 Попытка автоматического исправления...")
                    if attempt == 0:
                        # Пытаемся исправить только один раз
                        if self._repair_database():
                            logger.info("✅ БД исправлена, повторяем подключение...")
                            time.sleep(1)  # Небольшая задержка перед повтором
                            continue
                        else:
                            logger.error("❌ Не удалось исправить поврежденную БД")
                            raise
                    else:
                        raise
                
                # КРИТИЧНО: Обработка ошибки I/O при подключении
                elif "disk i/o error" in error_str or "i/o error" in error_str:
                    logger.error(f"❌ КРИТИЧНО: Ошибка I/O при подключении к БД: {self.db_path}")
                    logger.error(f"❌ Ошибка: {e}")
                    logger.warning("🔧 Попытка автоматического исправления...")
                    if attempt == 0:
                        # Пытаемся исправить только один раз
                        if self._repair_database():
                            logger.info("✅ БД исправлена, повторяем подключение...")
                            time.sleep(1)  # Небольшая задержка перед повтором
                            continue
                        else:
                            logger.error("❌ Не удалось исправить БД после I/O ошибки")
                            raise
                    else:
                        raise
                
                # Обработка "file is not a database"
                elif "file is not a database" in error_str or ("not a database" in error_str and "unable to open" not in error_str):
                    logger.error(f"❌ Файл БД поврежден (явная ошибка SQLite): {self.db_path}")
                    logger.error(f"❌ Ошибка: {e}")
                    # Восстанавливаем БД только при явной ошибке
                    self._recreate_database()
                    # Пытаемся подключиться снова (только один раз)
                    if attempt == 0:
                        continue
                    else:
                        raise
                
                # Обработка блокировок при подключении
                elif "database is locked" in error_str or "locked" in error_str:
                    # Ошибка блокировки при подключении
                    last_error = e
                    if retry_on_locked and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 0.5
                        logger.debug(f"⚠️ БД заблокирована при подключении (попытка {attempt + 1}/{max_retries}), ждем {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"⚠️ БД заблокирована при подключении после {max_retries} попыток")
                        raise
                else:
                    # Другие ошибки - не повторяем
                    raise
        
        # Если дошли сюда, значит все попытки исчерпаны
        if last_error:
            raise last_error
    
    def _init_database(self):
        """Создает все таблицы и индексы"""
        # Проверяем целостность БД при каждом запуске
        db_exists = os.path.exists(self.db_path)
        
        if db_exists:
            logger.info("🔍 Проверка целостности БД...")
            is_ok, error_msg = self._check_integrity()
            
            if not is_ok:
                logger.error(f"❌ Обнаружены повреждения в БД: {error_msg}")
                logger.warning("🔧 Попытка автоматического исправления...")
                
                if self._repair_database():
                    logger.info("✅ БД успешно исправлена")
                    # Проверяем еще раз после исправления
                    is_ok, error_msg = self._check_integrity()
                    if not is_ok:
                        logger.error(f"❌ БД все еще повреждена после исправления: {error_msg}")
                        logger.error("⚠️ Рекомендуется восстановить из резервной копии вручную")
                else:
                    logger.error("❌ Не удалось автоматически исправить БД")
                    logger.error("⚠️ Попробуйте восстановить из резервной копии: db.restore_from_backup()")
            else:
                logger.debug("✅ БД проверена, целостность в порядке")
        else:
            logger.info(f"📁 Создается новая база данных: {self.db_path}")
        
        # SQLite автоматически создает файл БД при первом подключении
        # Не нужно создавать пустой файл через touch() - это создает невалидную БД
        
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
            
            # ==================== ТАБЛИЦА: МЕТАДАННЫЕ БД ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS db_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для db_metadata
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_db_metadata_key ON db_metadata(key)")
            
            # Если БД новая - устанавливаем флаг что миграция не выполнена
            if not db_exists:
                now = datetime.now().isoformat()
                cursor.execute("""
                    INSERT OR IGNORE INTO db_metadata (key, value, updated_at, created_at)
                    VALUES ('json_migration_completed', '0', ?, ?)
                """, (now, now))
                logger.info("✅ Все таблицы и индексы созданы в новой базе данных")
            else:
                logger.debug("✅ Все таблицы и индексы проверены")
            
            conn.commit()
    
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
    
    def _is_migration_needed(self) -> bool:
        """
        Проверяет, нужна ли миграция из JSON файлов
        
        Использует флаг в таблице db_metadata для отслеживания статуса миграции.
        
        Returns:
            True если миграция нужна (флаг = 0 или отсутствует), False если уже выполнена (флаг = 1)
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем флаг миграции в метаданных БД
                try:
                    cursor.execute("""
                        SELECT value FROM db_metadata 
                        WHERE key = 'json_migration_completed'
                    """)
                    row = cursor.fetchone()
                    
                    if row:
                        migration_completed = row['value'] == '1'
                        if migration_completed:
                            logger.debug("ℹ️ Миграция из JSON уже выполнена (флаг в БД)")
                            return False
                        else:
                            logger.debug("ℹ️ Миграция из JSON еще не выполнена (флаг = 0)")
                            return True
                    else:
                        # Флага нет - значит БД новая, миграция нужна
                        logger.debug("ℹ️ Флаг миграции отсутствует - миграция нужна")
                        return True
                except sqlite3.OperationalError:
                    # Таблица db_metadata не существует - это старая БД без метаданных
                    # Проверяем наличие данных в основных таблицах как fallback
                    logger.debug("ℹ️ Таблица db_metadata не найдена, проверяем наличие данных...")
                    check_tables = [
                        'bots_state', 'bot_positions_registry', 'individual_coin_settings', 
                        'mature_coins', 'rsi_cache', 'process_state'
                    ]
                    
                    for table in check_tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            count = cursor.fetchone()[0]
                            if count > 0:
                                # Есть данные - считаем что миграция уже выполнена
                                logger.debug(f"ℹ️ В таблице {table} есть {count} записей - миграция не требуется")
                                return False
                        except sqlite3.OperationalError:
                            continue
                    
                    # БД пуста - миграция нужна
                    return True
        except Exception as e:
            logger.debug(f"⚠️ Ошибка проверки необходимости миграции: {e}")
            # В случае ошибки - выполняем миграцию на всякий случай
            return True
    
    def _set_migration_completed(self):
        """Устанавливает флаг что миграция из JSON выполнена"""
        self._set_metadata_flag('json_migration_completed', '1')
    
    def _set_metadata_flag(self, key: str, value: str):
        """
        Устанавливает флаг в метаданных БД
        
        Универсальный метод для установки любых флагов миграций или других метаданных.
        
        Args:
            key: Ключ флага (например, 'json_migration_completed', 'schema_v2_migrated')
            value: Значение флага (обычно '0' или '1', но может быть любое строковое значение)
        
        Example:
            ```python
            # Установить флаг миграции
            db._set_metadata_flag('json_migration_completed', '1')
            
            # Установить флаг миграции схемы
            db._set_metadata_flag('schema_v2_migrated', '1')
            
            # Установить версию БД
            db._set_metadata_flag('db_version', '2.0')
            ```
        """
        try:
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO db_metadata (key, value, updated_at, created_at)
                    VALUES (?, ?, ?, 
                            COALESCE((SELECT created_at FROM db_metadata WHERE key = ?), ?))
                """, (key, value, now, key, now))
                conn.commit()
                logger.debug(f"✅ Флаг метаданных установлен: {key} = {value}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка установки флага метаданных {key}: {e}")
    
    def _get_metadata_flag(self, key: str, default: str = None) -> Optional[str]:
        """
        Получает значение флага из метаданных БД
        
        Универсальный метод для получения любых флагов миграций или других метаданных.
        
        Args:
            key: Ключ флага
            default: Значение по умолчанию если флаг не найден
        
        Returns:
            Значение флага или default
        
        Example:
            ```python
            # Проверить флаг миграции
            if db._get_metadata_flag('json_migration_completed') == '1':
                print("Миграция выполнена")
            
            # Получить версию БД
            version = db._get_metadata_flag('db_version', '1.0')
            ```
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM db_metadata WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return row['value']
                return default
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения флага метаданных {key}: {e}")
            return default
    
    def _is_migration_flag_set(self, flag_key: str) -> bool:
        """
        Проверяет, установлен ли флаг миграции
        
        Удобный метод для проверки флагов миграций.
        
        Args:
            flag_key: Ключ флага миграции
        
        Returns:
            True если флаг установлен в '1', False в противном случае
        
        Example:
            ```python
            # Проверить выполнена ли миграция JSON
            if not db._is_migration_flag_set('json_migration_completed'):
                # Выполнить миграцию
                db.migrate_json_to_database()
            
            # Проверить выполнена ли миграция схемы v2
            if not db._is_migration_flag_set('schema_v2_migrated'):
                # Выполнить миграцию схемы
                db.migrate_schema_v2()
            ```
        """
        flag_value = self._get_metadata_flag(flag_key, '0')
        return flag_value == '1'
    
    def migrate_json_to_database(self) -> Dict[str, int]:
        """
        Мигрирует данные из JSON файлов в БД (однократно)
        
        Проверяет наличие данных в БД перед миграцией - если данные уже есть,
        миграция не выполняется.
        
        Returns:
            Словарь с количеством мигрированных записей для каждого файла
        """
        # Проверяем, нужна ли миграция
        if not self._is_migration_needed():
            logger.debug("ℹ️ Миграция не требуется - данные уже есть в БД")
            return {}
        
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
                # Устанавливаем флаг что миграция выполнена
                self._set_migration_completed()
            
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
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        Список доступных резервных копий БД
        
        Returns:
            Список словарей с информацией о резервных копиях
        """
        backups = []
        db_dir = os.path.dirname(self.db_path)
        db_name = os.path.basename(self.db_path)
        
        try:
            if not os.path.exists(db_dir):
                return backups
            
            # Ищем все файлы резервных копий
            for filename in os.listdir(db_dir):
                if filename.startswith(f"{db_name}.backup_") and not filename.endswith('-wal') and not filename.endswith('-shm'):
                    backup_path = os.path.join(db_dir, filename)
                    try:
                        file_size = os.path.getsize(backup_path)
                        # Извлекаем timestamp из имени файла
                        timestamp_str = filename.replace(f"{db_name}.backup_", "")
                        try:
                            backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        except:
                            backup_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
                        
                        backups.append({
                            'path': backup_path,
                            'filename': filename,
                            'size_mb': file_size / 1024 / 1024,
                            'created_at': backup_time.isoformat(),
                            'timestamp': timestamp_str
                        })
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка обработки резервной копии {filename}: {e}")
            
            # Сортируем по дате создания (новые первыми)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            return backups
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка резервных копий: {e}")
            return []
    
    def restore_from_backup(self, backup_path: str = None) -> bool:
        """
        Восстанавливает БД из резервной копии
        
        Args:
            backup_path: Путь к резервной копии (если None, используется последняя)
        
        Returns:
            True если восстановление успешно, False в противном случае
        """
        try:
            # Если путь не указан, используем последнюю резервную копию
            if backup_path is None:
                backups = self.list_backups()
                if not backups:
                    logger.error("❌ Нет доступных резервных копий")
                    return False
                backup_path = backups[0]['path']
                logger.info(f"📦 Используется последняя резервная копия: {backup_path}")
            
            if not os.path.exists(backup_path):
                logger.error(f"❌ Резервная копия не найдена: {backup_path}")
                return False
            
            logger.info(f"📦 Восстановление БД из резервной копии: {backup_path}")
            
            # Закрываем все соединения перед восстановлением
            # (в SQLite это не критично, но для чистоты)
            
            # Создаем резервную копию текущей БД перед восстановлением (на всякий случай)
            if os.path.exists(self.db_path):
                current_backup = self._backup_database()
                if current_backup:
                    logger.info(f"💾 Текущая БД сохранена в: {current_backup}")
            
            # Копируем резервную копию на место основной БД
            shutil.copy2(backup_path, self.db_path)
            
            # Восстанавливаем WAL и SHM файлы если есть
            wal_backup = f"{backup_path}-wal"
            shm_backup = f"{backup_path}-shm"
            wal_file = f"{self.db_path}-wal"
            shm_file = f"{self.db_path}-shm"
            
            if os.path.exists(wal_backup):
                shutil.copy2(wal_backup, wal_file)
                logger.debug("✅ Восстановлен WAL файл")
            elif os.path.exists(wal_file):
                # Удаляем старый WAL файл если нет резервной копии
                os.remove(wal_file)
                logger.debug("🗑️ Удален старый WAL файл")
            
            if os.path.exists(shm_backup):
                shutil.copy2(shm_backup, shm_file)
                logger.debug("✅ Восстановлен SHM файл")
            elif os.path.exists(shm_file):
                # Удаляем старый SHM файл если нет резервной копии
                os.remove(shm_file)
                logger.debug("🗑️ Удален старый SHM файл")
            
            # Проверяем целостность восстановленной БД
            is_ok, error_msg = self._check_integrity()
            if is_ok:
                logger.info("✅ БД успешно восстановлена из резервной копии")
                return True
            else:
                logger.error(f"❌ Восстановленная БД повреждена: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления БД из резервной копии: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False


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

