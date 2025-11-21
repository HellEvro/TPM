#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Реляционная база данных для хранения ВСЕХ данных AI модуля

Хранит:
- AI симуляции (simulated_trades)
- Реальные сделки ботов (bot_trades)
- История биржи (exchange_trades)
- Решения AI (ai_decisions)
- Сессии обучения (training_sessions)
- Метрики производительности (performance_metrics)
- Связи между данными для сложных запросов

Позволяет:
- Хранить миллиарды записей
- Делать JOIN запросы между таблицами
- Сравнивать данные из разных источников
- Анализировать паттерны
- Обучать ИИ на огромных объемах данных
"""

import sqlite3
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager
from functools import wraps
import logging

logger = logging.getLogger('AI.Database')


class AIDatabase:
    """
    Реляционная база данных для всех данных AI модуля
    """
    
    def __init__(self, db_path: str = None):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных (если None, используется data/ai/ai_data.db)
        """
        if db_path is None:
            # Поддержка UNC путей: используем абсолютный путь относительно текущей рабочей директории
            base_dir = os.getcwd()
            db_path = os.path.join(base_dir, 'data', 'ai', 'ai_data.db')
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
        
        logger.info(f"✅ AI Database инициализирована: {db_path}")
    
    def _is_likely_corrupted(self) -> bool:
        """
        Проверяет, вероятно ли файл поврежден (только для очень очевидных случаев)
        НЕ удаляет БД автоматически - только предупреждает
        
        ВАЖНО: Не проверяем заголовок SQLite, так как это может давать ложные срабатывания
        при работе с удаленными БД, WAL режиме или когда файл открыт другим процессом.
        Полагаемся только на явную ошибку SQLite при подключении.
        """
        if not os.path.exists(self.db_path):
            return False
        
        try:
            # Проверяем только размер файла - если меньше 100 байт, это точно не БД
            # Это единственная безопасная проверка, которая не дает ложных срабатываний
            file_size = os.path.getsize(self.db_path)
            if file_size < 100:
                logger.warning(f"⚠️ Файл БД слишком маленький ({file_size} байт) - возможно поврежден")
                return True
            
            # НЕ проверяем заголовок - это может давать ложные срабатывания
            # SQLite сам проверит валидность при подключении
            
            return False
        except Exception as e:
            # Если не можем прочитать файл, не считаем его поврежденным
            # Возможно, он заблокирован другим процессом или на удаленном диске
            logger.debug(f"⚠️ Не удалось проверить файл БД: {e}")
            return False
    
    def _backup_database(self, max_retries: int = 3) -> Optional[str]:
        """
        Создает резервную копию БД перед удалением
        
        Args:
            max_retries: Максимальное количество попыток при блокировке файла
        
        Returns:
            Путь к резервной копии или None если не удалось создать
        """
        if not os.path.exists(self.db_path):
            return None
        
        import shutil
        from datetime import datetime
        
        # Создаем имя резервной копии с timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.db_path}.backup_{timestamp}"
        
        # Пытаемся создать резервную копию с retry логикой
        for attempt in range(max_retries):
            try:
                # Пытаемся закрыть все соединения перед копированием
                # Это может помочь освободить файл
                if attempt > 0:
                    logger.debug(f"🔄 Попытка создания резервной копии {attempt + 1}/{max_retries}...")
                    time.sleep(1.0 * attempt)  # Увеличиваем задержку с каждой попыткой
                
                # Копируем БД и связанные файлы
                shutil.copy2(self.db_path, backup_path)
                
                # Копируем WAL и SHM файлы если есть
                wal_file = self.db_path + '-wal'
                shm_file = self.db_path + '-shm'
                if os.path.exists(wal_file):
                    try:
                        shutil.copy2(wal_file, f"{backup_path}-wal")
                    except Exception as e:
                        logger.debug(f"⚠️ Не удалось скопировать WAL файл: {e}")
                if os.path.exists(shm_file):
                    try:
                        shutil.copy2(shm_file, f"{backup_path}-shm")
                    except Exception as e:
                        logger.debug(f"⚠️ Не удалось скопировать SHM файл: {e}")
                
                logger.warning(f"💾 Создана резервная копия БД: {backup_path}")
                return backup_path
            except PermissionError as e:
                # Файл заблокирован другим процессом
                if attempt < max_retries - 1:
                    logger.debug(f"⚠️ Файл БД заблокирован, повторяем попытку через {1.0 * (attempt + 1)}s...")
                    continue
                else:
                    logger.error(f"❌ Не удалось создать резервную копию БД после {max_retries} попыток: {e}")
                    return None
            except Exception as e:
                error_str = str(e).lower()
                if "процесс не может получить доступ к файлу" in error_str or "file is locked" in error_str or "access" in error_str:
                    # Файл заблокирован
                    if attempt < max_retries - 1:
                        logger.debug(f"⚠️ Файл БД заблокирован, повторяем попытку через {1.0 * (attempt + 1)}s...")
                        continue
                    else:
                        logger.error(f"❌ Не удалось создать резервную копию БД после {max_retries} попыток: {e}")
                        return None
                else:
                    # Другая ошибка - не повторяем
                    logger.error(f"❌ Ошибка создания резервной копии БД: {e}")
                    return None
        
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
            main_tables = ['simulated_trades', 'bot_trades', 'exchange_trades', 'candles_history']
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
    
    @contextmanager
    def _get_connection(self, retry_on_locked: bool = True, max_retries: int = 5):
        """
        Контекстный менеджер для работы с БД с поддержкой retry при блокировках
        
        Args:
            retry_on_locked: Повторять попытки при ошибке "database is locked"
            max_retries: Максимальное количество попыток при блокировке
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
                    elif "disk i/o error" in error_str or "i/o error" in error_str:
                        # Критическая ошибка I/O - БД может быть повреждена
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
                # Восстанавливаем БД при критических ошибках повреждения
                if "file is not a database" in error_str or ("not a database" in error_str and "unable to open" not in error_str):
                    logger.error(f"❌ Файл БД поврежден (явная ошибка SQLite): {self.db_path}")
                    logger.error(f"❌ Ошибка: {e}")
                    # Восстанавливаем БД только при явной ошибке
                    self._recreate_database()
                    # Пытаемся подключиться снова (только один раз)
                    if attempt == 0:
                        continue
                    else:
                        raise
                elif "database disk image is malformed" in error_str or "malformed" in error_str:
                    # Критическая ошибка - БД повреждена
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
                elif "disk i/o error" in error_str or "i/o error" in error_str:
                    # Критическая ошибка I/O
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
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Быстрая проверка целостности (быстрее чем integrity_check)
                cursor.execute("PRAGMA quick_check")
                result = cursor.fetchone()[0]
                
                if result == "ok":
                    return True, None
                else:
                    # Есть проблемы - делаем полную проверку для деталей
                    cursor.execute("PRAGMA integrity_check")
                    integrity_results = cursor.fetchall()
                    error_details = "; ".join([row[0] for row in integrity_results if row[0] != "ok"])
                    return False, error_details or result
        except Exception as e:
            return False, f"Ошибка проверки целостности: {e}"
    
    def _repair_database(self) -> bool:
        """
        Пытается исправить поврежденную БД
        
        Returns:
            True если удалось исправить, False в противном случае
        """
        try:
            logger.warning("🔧 Попытка исправления БД...")
            
            # Пытаемся создать резервную копию перед исправлением
            backup_path = self._backup_database(max_retries=3)
            backup_created = backup_path is not None
            
            if not backup_created:
                logger.warning("⚠️ Не удалось создать резервную копию перед исправлением (файл может быть заблокирован)")
                logger.info("💡 Попробую использовать существующие резервные копии для восстановления...")
            
            # Пытаемся использовать VACUUM для исправления (только если БД не слишком повреждена)
            vacuum_tried = False
            try:
                # Подключаемся без retry для VACUUM (может быть долго)
                conn = sqlite3.connect(self.db_path, timeout=300.0)  # 5 минут для VACUUM
                cursor = conn.cursor()
                logger.info("🔧 Выполняю VACUUM для исправления БД (это может занять время)...")
                cursor.execute("VACUUM")
                conn.commit()
                conn.close()
                logger.info("✅ VACUUM выполнен")
                vacuum_tried = True
            except Exception as vacuum_error:
                error_str = str(vacuum_error).lower()
                if "malformed" in error_str or "disk i/o error" in error_str:
                    logger.warning(f"⚠️ VACUUM невозможен из-за критического повреждения: {vacuum_error}")
                    logger.info("💡 Пропускаю VACUUM, пытаюсь восстановить из резервной копии...")
                else:
                    logger.warning(f"⚠️ VACUUM не помог: {vacuum_error}")
                try:
                    conn.close()
                except:
                    pass
            
            # Проверяем, исправилась ли БД (только если VACUUM был выполнен)
            if vacuum_tried:
                is_ok, error_msg = self._check_integrity()
                if is_ok:
                    logger.info("✅ БД успешно исправлена с помощью VACUUM")
                    return True
                else:
                    logger.warning(f"⚠️ БД все еще повреждена после VACUUM: {error_msg[:200]}...")
            
            # Пытаемся восстановить из резервной копии
            logger.info("🔄 Попытка восстановления из резервной копии...")
            backups = self.list_backups()
            
            if backups:
                # Если мы создали резервную копию только что, используем более старую
                if backup_created and len(backups) > 1:
                    # Используем предпоследнюю копию (последняя - это та, что мы только что создали)
                    older_backup = backups[1]['path']
                    logger.info(f"📦 Восстанавливаю из более старой резервной копии: {older_backup}")
                    if self.restore_from_backup(older_backup):
                        return True
                else:
                    # Используем последнюю доступную копию
                    latest_backup = backups[0]['path']
                    logger.info(f"📦 Восстанавливаю из резервной копии: {latest_backup}")
                    if self.restore_from_backup(latest_backup):
                        return True
            
            # Если не удалось восстановить из резервной копии
            if not backups:
                logger.error("❌ Нет доступных резервных копий для восстановления")
                if not backup_created:
                    logger.error("❌ КРИТИЧНО: Не удалось создать резервную копию и нет существующих копий!")
                    logger.error("⚠️ БД останется поврежденной. Рекомендуется:")
                    logger.error("   1. Закрыть все процессы, использующие БД")
                    logger.error("   2. Попробовать восстановить вручную: db.restore_from_backup()")
                    logger.error("   3. Или создать новую БД (данные будут потеряны)")
            else:
                logger.error("❌ Не удалось восстановить БД из резервной копии")
            
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка исправления БД: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _init_database(self):
        """Создает все таблицы и индексы"""
        # Проверяем целостность БД при каждом запуске
        if os.path.exists(self.db_path):
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
        
        # SQLite автоматически создает файл БД при первом подключении
        # Не нужно создавать пустой файл через touch() - это создает невалидную БД
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Миграция: добавляем новые поля если их нет
            self._migrate_schema(cursor, conn)
            
            # ==================== ТАБЛИЦА: AI СИМУЛЯЦИИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulated_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    entry_time INTEGER NOT NULL,
                    exit_time INTEGER NOT NULL,
                    entry_rsi REAL,
                    exit_rsi REAL,
                    entry_trend TEXT,
                    exit_trend TEXT,
                    entry_volatility REAL,
                    entry_volume_ratio REAL,
                    pnl REAL NOT NULL,
                    pnl_pct REAL NOT NULL,
                    roi REAL,
                    exit_reason TEXT,
                    is_successful INTEGER NOT NULL DEFAULT 0,
                    duration_candles INTEGER,
                    entry_idx INTEGER,
                    exit_idx INTEGER,
                    simulation_timestamp TEXT NOT NULL,
                    training_session_id INTEGER,
                    rsi_params_json TEXT,
                    risk_params_json TEXT,
                    config_params_json TEXT,
                    filters_params_json TEXT,
                    entry_conditions_json TEXT,
                    exit_conditions_json TEXT,
                    restrictions_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (training_session_id) REFERENCES training_sessions(id)
                )
            """)
            
            # Индексы для simulated_trades
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_symbol ON simulated_trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_entry_time ON simulated_trades(entry_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_exit_time ON simulated_trades(exit_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_pnl ON simulated_trades(pnl)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_successful ON simulated_trades(is_successful)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sim_trades_session ON simulated_trades(training_session_id)")
            
            # ==================== ТАБЛИЦА: РЕАЛЬНЫЕ СДЕЛКИ БОТОВ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    bot_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    pnl REAL,
                    roi REAL,
                    status TEXT NOT NULL,
                    decision_source TEXT NOT NULL,
                    ai_decision_id TEXT,
                    ai_confidence REAL,
                    entry_rsi REAL,
                    exit_rsi REAL,
                    entry_trend TEXT,
                    exit_trend TEXT,
                    entry_volatility REAL,
                    entry_volume_ratio REAL,
                    close_reason TEXT,
                    position_size_usdt REAL,
                    position_size_coins REAL,
                    entry_data_json TEXT,
                    exit_market_data_json TEXT,
                    config_params_json TEXT,
                    filters_params_json TEXT,
                    entry_conditions_json TEXT,
                    exit_conditions_json TEXT,
                    restrictions_json TEXT,
                    is_simulated INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Индексы для bot_trades
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_symbol ON bot_trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_bot_id ON bot_trades(bot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_status ON bot_trades(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_decision_source ON bot_trades(decision_source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_pnl ON bot_trades(pnl)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_entry_time ON bot_trades(entry_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_trades_ai_decision ON bot_trades(ai_decision_id)")
            
            # ==================== ТАБЛИЦА: ИСТОРИЯ БИРЖИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exchange_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    pnl REAL NOT NULL,
                    roi REAL NOT NULL,
                    position_size_usdt REAL,
                    position_size_coins REAL,
                    order_id TEXT,
                    source TEXT NOT NULL,
                    saved_timestamp TEXT NOT NULL,
                    is_real INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для exchange_trades
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_symbol ON exchange_trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_entry_time ON exchange_trades(entry_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_exit_time ON exchange_trades(exit_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_pnl ON exchange_trades(pnl)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_exchange_trades_order_id ON exchange_trades(order_id)")
            
            # ==================== ТАБЛИЦА: РЕШЕНИЯ AI ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    confidence REAL,
                    rsi REAL,
                    trend TEXT,
                    price REAL,
                    market_data_json TEXT,
                    decision_params_json TEXT,
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    result_pnl REAL,
                    result_successful INTEGER
                )
            """)
            
            # Индексы для ai_decisions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol ON ai_decisions(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_decision_id ON ai_decisions(decision_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_created_at ON ai_decisions(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_result ON ai_decisions(result_successful)")
            
            # ==================== ТАБЛИЦА: СЕССИИ ОБУЧЕНИЯ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type TEXT NOT NULL,
                    training_seed INTEGER,
                    coins_processed INTEGER DEFAULT 0,
                    models_saved INTEGER DEFAULT 0,
                    candles_processed INTEGER DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    successful_trades INTEGER DEFAULT 0,
                    failed_trades INTEGER DEFAULT 0,
                    win_rate REAL,
                    total_pnl REAL,
                    accuracy REAL,
                    mse REAL,
                    params_used INTEGER DEFAULT 0,
                    params_total INTEGER DEFAULT 0,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'RUNNING',
                    metadata_json TEXT
                )
            """)
            
            # Индексы для training_sessions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_sessions_type ON training_sessions(session_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_sessions_started_at ON training_sessions(started_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_sessions_status ON training_sessions(status)")
            
            # ==================== ТАБЛИЦА: МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_data_json TEXT,
                    recorded_at TEXT NOT NULL,
                    training_session_id INTEGER,
                    FOREIGN KEY (training_session_id) REFERENCES training_sessions(id)
                )
            """)
            
            # Индексы для performance_metrics
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_symbol ON performance_metrics(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_type ON performance_metrics(metric_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_recorded_at ON performance_metrics(recorded_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_metrics_session ON performance_metrics(training_session_id)")
            
            # ==================== ТАБЛИЦА: ОБРАЗЦЫ ДЛЯ ОБУЧЕНИЯ ПРЕДСКАЗАТЕЛЯ КАЧЕСТВА ПАРАМЕТРОВ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parameter_training_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rsi_params_json TEXT NOT NULL,
                    risk_params_json TEXT,
                    win_rate REAL NOT NULL,
                    total_pnl REAL NOT NULL,
                    trades_count INTEGER NOT NULL,
                    quality REAL NOT NULL,
                    blocked INTEGER NOT NULL DEFAULT 0,
                    rsi_entered_zones INTEGER DEFAULT 0,
                    filters_blocked INTEGER DEFAULT 0,
                    block_reasons_json TEXT,
                    symbol TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для parameter_training_samples
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_samples_symbol ON parameter_training_samples(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_samples_quality ON parameter_training_samples(quality)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_samples_blocked ON parameter_training_samples(blocked)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_samples_created_at ON parameter_training_samples(created_at)")
            
            # ==================== ТАБЛИЦА: ИСПОЛЬЗОВАННЫЕ ПАРАМЕТРЫ ОБУЧЕНИЯ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS used_training_parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    param_hash TEXT UNIQUE NOT NULL,
                    rsi_params_json TEXT NOT NULL,
                    training_seed INTEGER,
                    win_rate REAL DEFAULT 0.0,
                    total_pnl REAL DEFAULT 0.0,
                    signal_accuracy REAL DEFAULT 0.0,
                    trades_count INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    symbol TEXT,
                    used_at TEXT NOT NULL,
                    update_count INTEGER DEFAULT 1
                )
            """)
            
            # Индексы для used_training_parameters
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_used_params_hash ON used_training_parameters(param_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_used_params_symbol ON used_training_parameters(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_used_params_rating ON used_training_parameters(rating)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_used_params_win_rate ON used_training_parameters(win_rate)")
            
            # ==================== ТАБЛИЦА: ЛУЧШИЕ ПАРАМЕТРЫ ДЛЯ МОНЕТ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS best_params_per_symbol (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    rsi_params_json TEXT NOT NULL,
                    rating REAL NOT NULL,
                    win_rate REAL NOT NULL,
                    total_pnl REAL NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Индексы для best_params_per_symbol
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_best_params_symbol ON best_params_per_symbol(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_best_params_rating ON best_params_per_symbol(rating)")
            
            # ==================== ТАБЛИЦА: ЗАБЛОКИРОВАННЫЕ ПАРАМЕТРЫ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocked_params (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    param_hash TEXT,
                    rsi_params_json TEXT NOT NULL,
                    block_reasons_json TEXT,
                    blocked_attempts INTEGER DEFAULT 0,
                    blocked_long INTEGER DEFAULT 0,
                    blocked_short INTEGER DEFAULT 0,
                    symbol TEXT,
                    blocked_at TEXT NOT NULL
                )
            """)
            
            # Индексы для blocked_params
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocked_params_symbol ON blocked_params(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocked_params_blocked_at ON blocked_params(blocked_at)")
            
            # ==================== ТАБЛИЦА: ЦЕЛЕВЫЕ ЗНАЧЕНИЯ WIN RATE ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS win_rate_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT UNIQUE NOT NULL,
                    target_win_rate REAL NOT NULL,
                    current_win_rate REAL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Индексы для win_rate_targets
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_win_rate_targets_symbol ON win_rate_targets(symbol)")
            
            # ==================== ТАБЛИЦА: БЛОКИРОВКИ ДЛЯ ПАРАЛЛЕЛЬНОЙ ОБРАБОТКИ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    process_id TEXT NOT NULL,
                    hostname TEXT,
                    locked_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PROCESSING',
                    UNIQUE(symbol)
                )
            """)
            
            # Индексы для training_locks
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_locks_symbol ON training_locks(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_locks_expires_at ON training_locks(expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_training_locks_status ON training_locks(status)")
            
            # ==================== ТАБЛИЦА: ИСТОРИЯ СВЕЧЕЙ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candles_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL DEFAULT '6h',
                    candle_time INTEGER NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, timeframe, candle_time)
                )
            """)
            
            # Индексы для candles_history
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_symbol ON candles_history(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_timeframe ON candles_history(timeframe)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_time ON candles_history(candle_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles_history(symbol, candle_time)")
            
            # ==================== ТАБЛИЦА: ВЕРСИИ МОДЕЛЕЙ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT UNIQUE NOT NULL,
                    model_type TEXT NOT NULL,
                    version_number TEXT,
                    model_path TEXT,
                    accuracy REAL,
                    mse REAL,
                    win_rate REAL,
                    total_pnl REAL,
                    training_samples INTEGER,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для model_versions
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_versions_model_id ON model_versions(model_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_versions_model_type ON model_versions(model_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_versions_created_at ON model_versions(created_at)")
            
            # ==================== ТАБЛИЦА: СНИМКИ ДАННЫХ БОТОВ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bots_data_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_time TEXT NOT NULL,
                    bots_json TEXT,
                    rsi_data_json TEXT,
                    signals_json TEXT,
                    bots_status_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для bots_data_snapshots
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bots_snapshots_time ON bots_data_snapshots(snapshot_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bots_snapshots_created ON bots_data_snapshots(created_at)")
            
            # ==================== ТАБЛИЦА: АНАЛИЗ СТРАТЕГИЙ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS strategy_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_type TEXT NOT NULL,
                    symbol TEXT,
                    results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Индексы для strategy_analysis
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy_analysis_type ON strategy_analysis(analysis_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy_analysis_symbol ON strategy_analysis(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy_analysis_created_at ON strategy_analysis(created_at)")
            
            # ==================== ТАБЛИЦА: ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS optimized_params (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    params_json TEXT NOT NULL,
                    optimization_type TEXT,
                    win_rate REAL,
                    total_pnl REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Индексы для optimized_params
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_optimized_params_symbol ON optimized_params(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_optimized_params_type ON optimized_params(optimization_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_optimized_params_created_at ON optimized_params(created_at)")
            
            # ==================== ТАБЛИЦА: СТАТУС СЕРВИСА ДАННЫХ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_service_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT NOT NULL,
                    status_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(service_name)
                )
            """)
            
            # Индексы для data_service_status
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_service_name ON data_service_status(service_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_service_updated_at ON data_service_status(updated_at)")
            
            # ==================== ТАБЛИЦА: ПАТТЕРНЫ И ИНСАЙТЫ ====================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trading_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    symbol TEXT,
                    rsi_range TEXT,
                    trend_condition TEXT,
                    volatility_range TEXT,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    avg_pnl REAL,
                    avg_duration REAL,
                    pattern_data_json TEXT,
                    discovered_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)
            
            # Индексы для trading_patterns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type ON trading_patterns(pattern_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_symbol ON trading_patterns(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_rsi_range ON trading_patterns(rsi_range)")
            
            conn.commit()
            
            logger.debug("✅ Все таблицы и индексы созданы")
    
    def _migrate_schema(self, cursor, conn):
        """Миграция схемы БД: добавляет новые поля если их нет"""
        try:
            # Проверяем и добавляем entry_volatility и entry_volume_ratio в simulated_trades
            try:
                cursor.execute("SELECT entry_volatility FROM simulated_trades LIMIT 1")
            except sqlite3.OperationalError:
                logger.info("📦 Миграция: добавляем entry_volatility и entry_volume_ratio в simulated_trades")
                cursor.execute("ALTER TABLE simulated_trades ADD COLUMN entry_volatility REAL")
                cursor.execute("ALTER TABLE simulated_trades ADD COLUMN entry_volume_ratio REAL")
            
            # Проверяем и добавляем entry_volatility и entry_volume_ratio в bot_trades
            try:
                cursor.execute("SELECT entry_volatility FROM bot_trades LIMIT 1")
            except sqlite3.OperationalError:
                logger.info("📦 Миграция: добавляем entry_volatility и entry_volume_ratio в bot_trades")
                cursor.execute("ALTER TABLE bot_trades ADD COLUMN entry_volatility REAL")
                cursor.execute("ALTER TABLE bot_trades ADD COLUMN entry_volume_ratio REAL")
            
            # Проверяем и добавляем параметры конфига в simulated_trades
            new_fields_sim = [
                ('config_params_json', 'TEXT'),
                ('filters_params_json', 'TEXT'),
                ('entry_conditions_json', 'TEXT'),
                ('exit_conditions_json', 'TEXT'),
                ('restrictions_json', 'TEXT')
            ]
            for field_name, field_type in new_fields_sim:
                try:
                    cursor.execute(f"SELECT {field_name} FROM simulated_trades LIMIT 1")
                except sqlite3.OperationalError:
                    logger.info(f"📦 Миграция: добавляем {field_name} в simulated_trades")
                    cursor.execute(f"ALTER TABLE simulated_trades ADD COLUMN {field_name} {field_type}")
            
            # Проверяем и добавляем параметры конфига в bot_trades
            new_fields_bot = [
                ('config_params_json', 'TEXT'),
                ('filters_params_json', 'TEXT'),
                ('entry_conditions_json', 'TEXT'),
                ('exit_conditions_json', 'TEXT'),
                ('restrictions_json', 'TEXT')
            ]
            for field_name, field_type in new_fields_bot:
                try:
                    cursor.execute(f"SELECT {field_name} FROM bot_trades LIMIT 1")
                except sqlite3.OperationalError:
                    logger.info(f"📦 Миграция: добавляем {field_name} в bot_trades")
                    cursor.execute(f"ALTER TABLE bot_trades ADD COLUMN {field_name} {field_type}")
            
            # Проверяем и добавляем поля в blocked_params
            new_fields_blocked = [
                ('param_hash', 'TEXT'),
                ('blocked_attempts', 'INTEGER DEFAULT 0'),
                ('blocked_long', 'INTEGER DEFAULT 0'),
                ('blocked_short', 'INTEGER DEFAULT 0')
            ]
            for field_name, field_type in new_fields_blocked:
                try:
                    cursor.execute(f"SELECT {field_name} FROM blocked_params LIMIT 1")
                except sqlite3.OperationalError:
                    logger.info(f"📦 Миграция: добавляем {field_name} в bot_trades")
                    cursor.execute(f"ALTER TABLE bot_trades ADD COLUMN {field_name} {field_type}")
            
            # Проверяем и добавляем поля в blocked_params
            new_fields_blocked = [
                ('param_hash', 'TEXT'),
                ('blocked_attempts', 'INTEGER DEFAULT 0'),
                ('blocked_long', 'INTEGER DEFAULT 0'),
                ('blocked_short', 'INTEGER DEFAULT 0')
            ]
            for field_name, field_type in new_fields_blocked:
                try:
                    cursor.execute(f"SELECT {field_name} FROM blocked_params LIMIT 1")
                except sqlite3.OperationalError:
                    logger.info(f"📦 Миграция: добавляем {field_name} в blocked_params")
                    cursor.execute(f"ALTER TABLE blocked_params ADD COLUMN {field_name} {field_type}")
            
            conn.commit()
        except Exception as e:
            logger.debug(f"⚠️ Ошибка миграции схемы: {e}")
    
    # ==================== МЕТОДЫ ДЛЯ СИМУЛЯЦИЙ ====================
    
    def save_simulated_trades(self, trades: List[Dict[str, Any]], training_session_id: Optional[int] = None) -> int:
        """
        Сохраняет симулированные сделки в БД
        
        Args:
            trades: Список симулированных сделок
            training_session_id: ID сессии обучения (опционально)
        
        Returns:
            Количество сохраненных сделок
        """
        if not trades:
            return 0
        
        saved_count = 0
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                for trade in trades:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO simulated_trades (
                                symbol, direction, entry_price, exit_price,
                                entry_time, exit_time, entry_rsi, exit_rsi,
                                entry_trend, exit_trend, entry_volatility, entry_volume_ratio,
                                pnl, pnl_pct, roi,
                                exit_reason, is_successful, duration_candles,
                                entry_idx, exit_idx, simulation_timestamp,
                                training_session_id, rsi_params_json, risk_params_json,
                                config_params_json, filters_params_json, entry_conditions_json,
                                exit_conditions_json, restrictions_json,
                                created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            trade.get('symbol'),
                            trade.get('direction'),
                            trade.get('entry_price'),
                            trade.get('exit_price'),
                            trade.get('entry_time'),
                            trade.get('exit_time'),
                            trade.get('entry_rsi'),
                            trade.get('exit_rsi'),
                            trade.get('entry_trend'),
                            trade.get('exit_trend'),
                            trade.get('entry_volatility'),
                            trade.get('entry_volume_ratio'),
                            trade.get('pnl'),
                            trade.get('pnl_pct'),
                            trade.get('roi'),
                            trade.get('exit_reason'),
                            1 if trade.get('is_successful', False) else 0,
                            trade.get('duration_candles'),
                            trade.get('entry_idx'),
                            trade.get('exit_idx'),
                            trade.get('simulation_timestamp', now),
                            training_session_id,
                            json.dumps(trade.get('rsi_params')) if trade.get('rsi_params') else None,
                            json.dumps(trade.get('risk_params')) if trade.get('risk_params') else None,
                            json.dumps(trade.get('config_params')) if trade.get('config_params') else None,
                            json.dumps(trade.get('filters_params')) if trade.get('filters_params') else None,
                            json.dumps(trade.get('entry_conditions')) if trade.get('entry_conditions') else None,
                            json.dumps(trade.get('exit_conditions')) if trade.get('exit_conditions') else None,
                            json.dumps(trade.get('restrictions')) if trade.get('restrictions') else None,
                            now
                        ))
                        if cursor.rowcount > 0:
                            saved_count += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка сохранения симуляции: {e}")
                        continue
                
                conn.commit()
        
        if saved_count > 0:
            logger.debug(f"💾 Сохранено {saved_count} симулированных сделок в БД")
        
        return saved_count
    
    def get_simulated_trades(self, 
                            symbol: Optional[str] = None,
                            min_pnl: Optional[float] = None,
                            max_pnl: Optional[float] = None,
                            is_successful: Optional[bool] = None,
                            limit: Optional[int] = None,
                            offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получает симулированные сделки с фильтрацией
        
        Args:
            symbol: Фильтр по символу
            min_pnl: Минимальный PnL
            max_pnl: Максимальный PnL
            is_successful: Фильтр по успешности
            limit: Лимит записей
            offset: Смещение
        
        Returns:
            Список сделок
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM simulated_trades WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if min_pnl is not None:
                query += " AND pnl >= ?"
                params.append(min_pnl)
            
            if max_pnl is not None:
                query += " AND pnl <= ?"
                params.append(max_pnl)
            
            if is_successful is not None:
                query += " AND is_successful = ?"
                params.append(1 if is_successful else 0)
            
            query += " ORDER BY entry_time DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            if offset:
                query += " OFFSET ?"
                params.append(offset)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def count_simulated_trades(self, symbol: Optional[str] = None) -> int:
        """Подсчитывает количество симуляций"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("SELECT COUNT(*) FROM simulated_trades WHERE symbol = ?", (symbol,))
            else:
                cursor.execute("SELECT COUNT(*) FROM simulated_trades")
            
            return cursor.fetchone()[0]
    
    # ==================== МЕТОДЫ ДЛЯ РЕАЛЬНЫХ СДЕЛОК БОТОВ ====================
    
    def save_bot_trade(self, trade: Dict[str, Any]) -> Optional[int]:
        """Сохраняет или обновляет сделку бота"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Проверяем, существует ли сделка
                trade_id = trade.get('id') or trade.get('trade_id')
                if trade_id:
                    cursor.execute("SELECT id FROM bot_trades WHERE trade_id = ?", (trade_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Извлекаем volatility и volume_ratio из entry_data если есть
                        entry_data = trade.get('entry_data', {})
                        if isinstance(entry_data, str):
                            try:
                                entry_data = json.loads(entry_data)
                            except:
                                entry_data = {}
                        elif not isinstance(entry_data, dict):
                            entry_data = {}
                        
                        entry_volatility = trade.get('entry_volatility') or entry_data.get('volatility')
                        entry_volume_ratio = trade.get('entry_volume_ratio') or entry_data.get('volume_ratio')
                        
                        # Обновляем существующую
                        cursor.execute("""
                            UPDATE bot_trades SET
                                symbol = ?, direction = ?, entry_price = ?, exit_price = ?,
                                pnl = ?, roi = ?, status = ?, exit_rsi = ?, exit_trend = ?,
                                entry_volatility = ?, entry_volume_ratio = ?,
                                close_reason = ?, exit_market_data_json = ?, updated_at = ?
                            WHERE trade_id = ?
                        """, (
                            trade.get('symbol'),
                            trade.get('direction'),
                            trade.get('entry_price'),
                            trade.get('exit_price'),
                            trade.get('pnl'),
                            trade.get('roi'),
                            trade.get('status'),
                            trade.get('exit_rsi'),
                            trade.get('exit_trend'),
                            entry_volatility,
                            entry_volume_ratio,
                            trade.get('close_reason'),
                            json.dumps(trade.get('exit_market_data')) if trade.get('exit_market_data') else None,
                            now,
                            trade_id
                        ))
                        return existing[0]
                
                # Создаем новую
                # Извлекаем volatility и volume_ratio из entry_data если есть
                entry_data = trade.get('entry_data', {})
                if isinstance(entry_data, str):
                    try:
                        entry_data = json.loads(entry_data)
                    except:
                        entry_data = {}
                elif not isinstance(entry_data, dict):
                    entry_data = {}
                
                entry_volatility = trade.get('entry_volatility') or entry_data.get('volatility')
                entry_volume_ratio = trade.get('entry_volume_ratio') or entry_data.get('volume_ratio')
                
                # Извлекаем все параметры конфига из trade или entry_data
                config_params = trade.get('config_params') or trade.get('config') or entry_data.get('config')
                filters_params = trade.get('filters_params') or trade.get('filters') or entry_data.get('filters')
                entry_conditions = trade.get('entry_conditions') or entry_data.get('entry_conditions')
                exit_market_data = trade.get('exit_market_data') or trade.get('market_data', {})
                if isinstance(exit_market_data, str):
                    try:
                        exit_market_data = json.loads(exit_market_data)
                    except:
                        exit_market_data = {}
                elif not isinstance(exit_market_data, dict):
                    exit_market_data = {}
                exit_conditions = trade.get('exit_conditions') or exit_market_data.get('exit_conditions')
                restrictions = trade.get('restrictions') or entry_data.get('restrictions')
                
                cursor.execute("""
                    INSERT OR IGNORE INTO bot_trades (
                        trade_id, bot_id, symbol, direction, entry_price, exit_price,
                        entry_time, exit_time, pnl, roi, status, decision_source,
                        ai_decision_id, ai_confidence, entry_rsi, exit_rsi,
                        entry_trend, exit_trend, entry_volatility, entry_volume_ratio,
                        close_reason,
                        position_size_usdt, position_size_coins,
                        entry_data_json, exit_market_data_json,
                        config_params_json, filters_params_json, entry_conditions_json,
                        exit_conditions_json, restrictions_json,
                        is_simulated,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id,
                    trade.get('bot_id'),
                    trade.get('symbol'),
                    trade.get('direction'),
                    trade.get('entry_price'),
                    trade.get('exit_price'),
                    trade.get('timestamp') or trade.get('entry_time'),
                    trade.get('close_timestamp') or trade.get('exit_time'),
                    trade.get('pnl'),
                    trade.get('roi'),
                    trade.get('status', 'CLOSED'),
                    trade.get('decision_source', 'SCRIPT'),
                    trade.get('ai_decision_id'),
                    trade.get('ai_confidence'),
                    trade.get('entry_rsi') or entry_data.get('rsi'),
                    trade.get('exit_rsi') or exit_market_data.get('rsi'),
                    trade.get('entry_trend') or entry_data.get('trend'),
                    trade.get('exit_trend') or exit_market_data.get('trend'),
                    entry_volatility,
                    entry_volume_ratio,
                    trade.get('close_reason'),
                    trade.get('position_size_usdt'),
                    trade.get('position_size_coins'),
                    json.dumps(trade.get('entry_data')) if trade.get('entry_data') else None,
                    json.dumps(trade.get('exit_market_data') or trade.get('market_data')) if (trade.get('exit_market_data') or trade.get('market_data')) else None,
                    json.dumps(config_params) if config_params else None,
                    json.dumps(filters_params) if filters_params else None,
                    json.dumps(entry_conditions) if entry_conditions else None,
                    json.dumps(exit_conditions) if exit_conditions else None,
                    json.dumps(restrictions) if restrictions else None,
                    1 if trade.get('is_simulated', False) else 0,
                    now,
                    now
                ))
                
                return cursor.lastrowid
    
    def get_bot_trades(self,
                       symbol: Optional[str] = None,
                       bot_id: Optional[str] = None,
                       status: Optional[str] = None,
                       decision_source: Optional[str] = None,
                       min_pnl: Optional[float] = None,
                       max_pnl: Optional[float] = None,
                       limit: Optional[int] = None,
                       offset: int = 0) -> List[Dict[str, Any]]:
        """Получает сделки ботов с фильтрацией"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM bot_trades WHERE is_simulated = 0"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if bot_id:
                query += " AND bot_id = ?"
                params.append(bot_id)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if decision_source:
                query += " AND decision_source = ?"
                params.append(decision_source)
            
            if min_pnl is not None:
                query += " AND pnl >= ?"
                params.append(min_pnl)
            
            if max_pnl is not None:
                query += " AND pnl <= ?"
                params.append(max_pnl)
            
            query += " ORDER BY entry_time DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            if offset:
                query += " OFFSET ?"
                params.append(offset)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                trade = dict(row)
                # Восстанавливаем JSON поля
                if trade.get('entry_data_json'):
                    trade['entry_data'] = json.loads(trade['entry_data_json'])
                if trade.get('exit_market_data_json'):
                    trade['exit_market_data'] = json.loads(trade['exit_market_data_json'])
                result.append(trade)
            
            return result
    
    # ==================== МЕТОДЫ ДЛЯ ИСТОРИИ БИРЖИ ====================
    
    def save_exchange_trades(self, trades: List[Dict[str, Any]]) -> int:
        """Сохраняет сделки с биржи"""
        if not trades:
            return 0
        
        saved_count = 0
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                for trade in trades:
                    try:
                        trade_id = trade.get('id') or trade.get('orderId') or f"exchange_{trade.get('symbol')}_{trade.get('timestamp')}"
                        cursor.execute("""
                            INSERT OR IGNORE INTO exchange_trades (
                                trade_id, symbol, direction, entry_price, exit_price,
                                entry_time, exit_time, pnl, roi,
                                position_size_usdt, position_size_coins,
                                order_id, source, saved_timestamp, is_real, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            trade_id,
                            trade.get('symbol'),
                            trade.get('direction'),
                            trade.get('entry_price'),
                            trade.get('exit_price'),
                            trade.get('timestamp'),
                            trade.get('close_timestamp'),
                            trade.get('pnl'),
                            trade.get('roi'),
                            trade.get('position_size_usdt'),
                            trade.get('position_size_coins'),
                            trade.get('orderId'),
                            trade.get('source', 'exchange_api'),
                            trade.get('saved_timestamp', now),
                            1,
                            now
                        ))
                        if cursor.rowcount > 0:
                            saved_count += 1
                    except Exception as e:
                        logger.debug(f"⚠️ Ошибка сохранения сделки биржи: {e}")
                        continue
                
                conn.commit()
        
        return saved_count
    
    def count_exchange_trades(self) -> int:
        """Подсчитывает количество сделок биржи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM exchange_trades")
            return cursor.fetchone()[0]
    
    def count_bot_trades(self, symbol: Optional[str] = None, is_simulated: Optional[bool] = None) -> int:
        """Подсчитывает количество сделок ботов"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT COUNT(*) FROM bot_trades WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if is_simulated is not None:
                query += " AND is_simulated = ?"
                params.append(1 if is_simulated else 0)
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    
    # ==================== МЕТОДЫ ДЛЯ РЕШЕНИЙ AI ====================
    
    def save_ai_decision(self, decision: Dict[str, Any]) -> int:
        """Сохраняет решение AI"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO ai_decisions (
                        decision_id, symbol, decision_type, signal, confidence,
                        rsi, trend, price, market_data_json, decision_params_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    decision.get('decision_id'),
                    decision.get('symbol'),
                    decision.get('decision_type', 'SIGNAL'),
                    decision.get('signal'),
                    decision.get('confidence'),
                    decision.get('rsi'),
                    decision.get('trend'),
                    decision.get('price'),
                    json.dumps(decision.get('market_data')) if decision.get('market_data') else None,
                    json.dumps(decision.get('params')) if decision.get('params') else None,
                    now
                ))
                
                return cursor.lastrowid
    
    def update_ai_decision_result(self, decision_id: str, pnl: float, is_successful: bool):
        """Обновляет результат решения AI"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    UPDATE ai_decisions SET
                        result_pnl = ?, result_successful = ?, executed_at = ?
                    WHERE decision_id = ?
                """, (pnl, 1 if is_successful else 0, now, decision_id))
    
    def get_ai_decisions(self, status: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict]:
        """Получает решения AI с фильтрацией"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM ai_decisions WHERE 1=1"
            params = []
            
            if status:
                query += " AND result_successful = ?"
                params.append(1 if status == 'SUCCESS' else 0)
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                decision = dict(row)
                if decision.get('market_data_json'):
                    decision['market_data'] = json.loads(decision['market_data_json'])
                if decision.get('decision_params_json'):
                    decision['params'] = json.loads(decision['decision_params_json'])
                decision['status'] = 'SUCCESS' if decision.get('result_successful') else 'FAILED' if decision.get('result_successful') is not None else 'PENDING'
                result.append(decision)
            
            return result
    
    # ==================== МЕТОДЫ ДЛЯ СЕССИЙ ОБУЧЕНИЯ ====================
    
    def create_training_session(self, session_type: str, training_seed: Optional[int] = None, metadata: Optional[Dict] = None) -> int:
        """Создает новую сессию обучения"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO training_sessions (
                        session_type, training_seed, started_at, status, metadata_json
                    ) VALUES (?, ?, ?, 'RUNNING', ?)
                """, (
                    session_type,
                    training_seed,
                    now,
                    json.dumps(metadata) if metadata else None
                ))
                
                return cursor.lastrowid
    
    def update_training_session(self, session_id: int, **kwargs):
        """Обновляет сессию обучения"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                updates = []
                params = []
                
                for key, value in kwargs.items():
                    if key == 'metadata' and isinstance(value, dict):
                        updates.append("metadata_json = ?")
                        params.append(json.dumps(value))
                    elif key in ('coins_processed', 'models_saved', 'candles_processed', 
                                'total_trades', 'successful_trades', 'failed_trades',
                                'params_used', 'params_total'):
                        updates.append(f"{key} = ?")
                        params.append(value)
                    elif key in ('win_rate', 'total_pnl', 'accuracy', 'mse'):
                        updates.append(f"{key} = ?")
                        params.append(value)
                    elif key == 'status':
                        updates.append("status = ?")
                        params.append(value)
                        if value in ('COMPLETED', 'FAILED'):
                            updates.append("completed_at = ?")
                            params.append(now)
                
                if updates:
                    params.append(session_id)
                    cursor.execute(f"""
                        UPDATE training_sessions SET {', '.join(updates)}
                        WHERE id = ?
                    """, params)
    
    # ==================== СЛОЖНЫЕ ЗАПРОСЫ И АНАЛИЗ ====================
    
    def compare_simulated_vs_real(self, symbol: Optional[str] = None, limit: int = 1000) -> Dict[str, Any]:
        """
        Сравнивает симулированные и реальные сделки
        
        Returns:
            Статистика сравнения
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Статистика симуляций
            sim_query = "SELECT AVG(pnl) as avg_pnl, COUNT(*) as count, AVG(CASE WHEN is_successful = 1 THEN 1.0 ELSE 0.0 END) as win_rate FROM simulated_trades"
            sim_params = []
            if symbol:
                sim_query += " WHERE symbol = ?"
                sim_params.append(symbol)
            
            cursor.execute(sim_query, sim_params)
            sim_stats = dict(cursor.fetchone())
            
            # Статистика реальных сделок
            real_query = "SELECT AVG(pnl) as avg_pnl, COUNT(*) as count FROM bot_trades WHERE is_simulated = 0 AND status = 'CLOSED' AND pnl IS NOT NULL"
            real_params = []
            if symbol:
                real_query += " AND symbol = ?"
                real_params.append(symbol)
            
            cursor.execute(real_query, real_params)
            real_stats = dict(cursor.fetchone())
            
            return {
                'simulated': sim_stats,
                'real': real_stats,
                'comparison': {
                    'pnl_diff': (sim_stats.get('avg_pnl') or 0) - (real_stats.get('avg_pnl') or 0),
                    'count_ratio': (sim_stats.get('count') or 0) / max(real_stats.get('count') or 1, 1)
                }
            }
    
    def get_trades_for_training(self,
                               include_simulated: bool = True,
                               include_real: bool = True,
                               include_exchange: bool = True,
                               min_trades: int = 10,
                               limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Получает все сделки для обучения ИИ (объединенные из разных источников)
        
        Args:
            include_simulated: Включить симуляции
            include_real: Включить реальные сделки ботов
            include_exchange: Включить сделки с биржи
            min_trades: Минимальное количество сделок для символа
            limit: Лимит на общее количество
        
        Returns:
            Список сделок для обучения
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Объединяем все источники через UNION
            queries = []
            params = []
            
            if include_simulated:
                queries.append("""
                    SELECT 
                        'SIMULATED' as source,
                        symbol, direction, entry_price, exit_price,
                        entry_rsi as rsi, entry_trend as trend,
                        entry_volatility, entry_volume_ratio,
                        pnl, pnl_pct as roi, is_successful,
                        entry_time as timestamp, exit_time as close_timestamp,
                        exit_reason as close_reason,
                        NULL as ai_decision_id, NULL as ai_confidence
                    FROM simulated_trades
                    WHERE exit_price IS NOT NULL
                """)
            
            if include_real:
                queries.append("""
                    SELECT 
                        'BOT' as source,
                        symbol, direction, entry_price, exit_price,
                        entry_rsi as rsi, entry_trend as trend,
                        entry_volatility, entry_volume_ratio,
                        pnl, roi, CASE WHEN pnl > 0 THEN 1 ELSE 0 END as is_successful,
                        entry_time as timestamp, exit_time as close_timestamp,
                        close_reason, ai_decision_id, ai_confidence
                    FROM bot_trades
                    WHERE is_simulated = 0 AND status = 'CLOSED' AND pnl IS NOT NULL
                """)
            
            if include_exchange:
                queries.append("""
                    SELECT 
                        'EXCHANGE' as source,
                        symbol, direction, entry_price, exit_price,
                        NULL as rsi, NULL as trend,
                        NULL as entry_volatility, NULL as entry_volume_ratio,
                        pnl, roi, CASE WHEN pnl > 0 THEN 1 ELSE 0 END as is_successful,
                        entry_time as timestamp, exit_time as close_timestamp,
                        NULL as close_reason, NULL as ai_decision_id, NULL as ai_confidence
                    FROM exchange_trades
                    WHERE pnl IS NOT NULL
                """)
            
            if not queries:
                return []
            
            # Объединяем запросы
            union_query = " UNION ALL ".join(queries)
            
            # Группируем по символам и фильтруем по минимальному количеству
            final_query = f"""
                WITH all_trades AS ({union_query})
                SELECT * FROM all_trades
                WHERE symbol IN (
                    SELECT symbol FROM all_trades
                    GROUP BY symbol
                    HAVING COUNT(*) >= ?
                )
                ORDER BY timestamp DESC
            """
            params.append(min_trades)
            
            if limit:
                final_query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(final_query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def analyze_patterns(self, 
                         symbol: Optional[str] = None,
                         rsi_range: Optional[Tuple[float, float]] = None,
                         min_trades: int = 10) -> List[Dict[str, Any]]:
        """
        Анализирует паттерны в сделках
        
        Args:
            symbol: Фильтр по символу
            rsi_range: Диапазон RSI (min, max)
            min_trades: Минимальное количество сделок для паттерна
        
        Returns:
            Список паттернов с метриками
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    symbol,
                    CASE 
                        WHEN entry_rsi <= 25 THEN '<=25'
                        WHEN entry_rsi <= 30 THEN '26-30'
                        WHEN entry_rsi <= 35 THEN '31-35'
                        WHEN entry_rsi >= 70 THEN '>=70'
                        WHEN entry_rsi >= 65 THEN '65-69'
                        ELSE 'OTHER'
                    END as rsi_range,
                    entry_trend as trend,
                    COUNT(*) as trade_count,
                    AVG(pnl) as avg_pnl,
                    SUM(CASE WHEN is_successful = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
                    AVG(duration_candles) as avg_duration
                FROM simulated_trades
                WHERE entry_rsi IS NOT NULL
            """
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if rsi_range:
                query += " AND entry_rsi >= ? AND entry_rsi <= ?"
                params.extend(rsi_range)
            
            query += """
                GROUP BY symbol, rsi_range, trend
                HAVING trade_count >= ?
                ORDER BY win_rate DESC, avg_pnl DESC
            """
            params.append(min_trades)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_ai_decision_performance(self, 
                                    symbol: Optional[str] = None,
                                    min_confidence: Optional[float] = None) -> Dict[str, Any]:
        """
        Анализирует производительность решений AI
        
        Returns:
            Статистика по решениям AI
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    COUNT(*) as total_decisions,
                    AVG(confidence) as avg_confidence,
                    SUM(CASE WHEN result_successful = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate,
                    AVG(result_pnl) as avg_pnl,
                    COUNT(DISTINCT symbol) as symbols_count
                FROM ai_decisions
                WHERE result_pnl IS NOT NULL
            """
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if min_confidence:
                query += " AND confidence >= ?"
                params.append(min_confidence)
            
            cursor.execute(query, params)
            result = dict(cursor.fetchone())
            
            return result
    
    def get_training_statistics(self, session_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает статистику по сессиям обучения"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM training_sessions WHERE 1=1"
            params = []
            
            if session_type:
                query += " AND session_type = ?"
                params.append(session_type)
            
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                session = dict(row)
                if session.get('metadata_json'):
                    session['metadata'] = json.loads(session['metadata_json'])
                result.append(session)
            
            return result
    
    def save_parameter_training_sample(self, sample: Dict[str, Any]) -> Optional[int]:
        """
        Сохраняет образец для обучения предсказателя качества параметров
        
        Args:
            sample: Словарь с данными образца:
                - rsi_params: Dict - параметры RSI
                - risk_params: Optional[Dict] - параметры риск-менеджмента
                - win_rate: float - Win Rate (0-100)
                - total_pnl: float - Total PnL
                - trades_count: int - Количество сделок
                - quality: float - Качество (вычисленное)
                - blocked: bool - Были ли входы заблокированы
                - rsi_entered_zones: int - Сколько раз RSI входил в зоны
                - filters_blocked: int - Сколько раз фильтры заблокировали вход
                - block_reasons: Optional[Dict] - Причины блокировок
                - symbol: Optional[str] - Символ монеты
        
        Returns:
            ID сохраненного образца или None при ошибке
        """
        try:
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO parameter_training_samples (
                        rsi_params_json, risk_params_json, win_rate, total_pnl,
                        trades_count, quality, blocked, rsi_entered_zones,
                        filters_blocked, block_reasons_json, symbol, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    json.dumps(sample.get('rsi_params', {})),
                    json.dumps(sample.get('risk_params', {})) if sample.get('risk_params') else None,
                    sample.get('win_rate', 0.0),
                    sample.get('total_pnl', 0.0),
                    sample.get('trades_count', 0),
                    sample.get('quality', 0.0),
                    1 if sample.get('blocked', False) else 0,
                    sample.get('rsi_entered_zones', 0),
                    sample.get('filters_blocked', 0),
                    json.dumps(sample.get('block_reasons', {})) if sample.get('block_reasons') else None,
                    sample.get('symbol'),
                    now
                ))
                sample_id = cursor.lastrowid
                conn.commit()
                return sample_id
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения образца параметров: {e}")
            return None
    
    def get_parameter_training_samples(self, limit: Optional[int] = None, 
                                       order_by: str = 'created_at DESC') -> List[Dict[str, Any]]:
        """
        Получает образцы для обучения предсказателя качества параметров
        
        Args:
            limit: Максимальное количество образцов (None = все)
            order_by: Поле для сортировки (по умолчанию: created_at DESC)
        
        Returns:
            Список словарей с данными образцов
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = f"SELECT * FROM parameter_training_samples ORDER BY {order_by}"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                samples = []
                for row in rows:
                    sample = {
                        'id': row['id'],
                        'rsi_params': json.loads(row['rsi_params_json']) if row['rsi_params_json'] else {},
                        'risk_params': json.loads(row['risk_params_json']) if row['risk_params_json'] else {},
                        'win_rate': row['win_rate'],
                        'total_pnl': row['total_pnl'],
                        'trades_count': row['trades_count'],
                        'quality': row['quality'],
                        'blocked': bool(row['blocked']),
                        'rsi_entered_zones': row['rsi_entered_zones'],
                        'filters_blocked': row['filters_blocked'],
                        'block_reasons': json.loads(row['block_reasons_json']) if row['block_reasons_json'] else {},
                        'symbol': row['symbol'],
                        'timestamp': row['created_at']
                    }
                    samples.append(sample)
                
                return samples
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки образцов параметров: {e}")
            return []
    
    def count_parameter_training_samples(self) -> int:
        """Возвращает количество сохраненных образцов параметров"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM parameter_training_samples")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"❌ Ошибка подсчета образцов параметров: {e}")
            return 0
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ИСПОЛЬЗОВАННЫМИ ПАРАМЕТРАМИ ====================
    
    def save_used_training_parameter(self, param_hash: str, rsi_params: Dict, training_seed: int,
                                     win_rate: float = 0.0, total_pnl: float = 0.0,
                                     signal_accuracy: float = 0.0, trades_count: int = 0,
                                     rating: float = 0.0, symbol: Optional[str] = None) -> Optional[int]:
        """
        Сохраняет или обновляет использованные параметры обучения
        
        Returns:
            ID записи или None при ошибке
        """
        try:
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Используем INSERT OR REPLACE для атомарной операции (быстрее чем SELECT + UPDATE)
                # Но сначала проверяем рейтинг, чтобы обновлять только если лучше
                cursor.execute("SELECT rating FROM used_training_parameters WHERE param_hash = ?", (param_hash,))
                existing = cursor.fetchone()
                
                if existing and rating <= existing['rating']:
                    # Не обновляем если рейтинг не лучше
                    cursor.execute("SELECT id FROM used_training_parameters WHERE param_hash = ?", (param_hash,))
                    return cursor.fetchone()['id']
                
                # Обновляем или вставляем
                cursor.execute("""
                    INSERT INTO used_training_parameters (
                        param_hash, rsi_params_json, training_seed, win_rate,
                        total_pnl, signal_accuracy, trades_count, rating, symbol, used_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(param_hash) DO UPDATE SET
                        rsi_params_json = excluded.rsi_params_json,
                        training_seed = excluded.training_seed,
                        win_rate = excluded.win_rate,
                        total_pnl = excluded.total_pnl,
                        signal_accuracy = excluded.signal_accuracy,
                        trades_count = excluded.trades_count,
                        rating = excluded.rating,
                        symbol = excluded.symbol,
                        used_at = excluded.used_at,
                        update_count = update_count + 1
                    WHERE excluded.rating > used_training_parameters.rating
                """, (
                    param_hash, json.dumps(rsi_params), training_seed, win_rate,
                    total_pnl, signal_accuracy, trades_count, rating, symbol, now
                ))
                param_id = cursor.lastrowid
                conn.commit()
                return param_id
        except Exception as e:
            logger.debug(f"⚠️ Ошибка сохранения использованных параметров: {e}")
            return None
    
    def get_used_training_parameter(self, param_hash: str) -> Optional[Dict[str, Any]]:
        """Получает использованные параметры по хешу"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM used_training_parameters WHERE param_hash = ?", (param_hash,))
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'param_hash': row['param_hash'],
                        'rsi_params': json.loads(row['rsi_params_json']),
                        'training_seed': row['training_seed'],
                        'win_rate': row['win_rate'],
                        'total_pnl': row['total_pnl'],
                        'signal_accuracy': row['signal_accuracy'],
                        'trades_count': row['trades_count'],
                        'rating': row['rating'],
                        'symbol': row['symbol'],
                        'used_at': row['used_at'],
                        'update_count': row['update_count']
                    }
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки использованных параметров: {e}")
            return None
    
    def count_used_training_parameters(self) -> int:
        """Возвращает количество использованных параметров"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM used_training_parameters")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"❌ Ошибка подсчета использованных параметров: {e}")
            return 0
    
    def get_best_used_parameters(self, limit: int = 10, min_win_rate: float = 80.0) -> List[Dict[str, Any]]:
        """Получает лучшие использованные параметры"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM used_training_parameters
                    WHERE win_rate >= ?
                    ORDER BY rating DESC
                    LIMIT ?
                """, (min_win_rate, limit))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    result.append({
                        'rsi_params': json.loads(row['rsi_params_json']),
                        'training_seed': row['training_seed'],
                        'win_rate': row['win_rate'],
                        'total_pnl': row['total_pnl'],
                        'signal_accuracy': row['signal_accuracy'],
                        'trades_count': row['trades_count'],
                        'rating': row['rating'],
                        'symbol': row['symbol'],
                        'used_at': row['used_at']
                    })
                return result
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки лучших параметров: {e}")
            return []
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ЛУЧШИМИ ПАРАМЕТРАМИ ДЛЯ МОНЕТ ====================
    
    def save_best_params_for_symbol(self, symbol: str, rsi_params: Dict, rating: float,
                                    win_rate: float, total_pnl: float) -> Optional[int]:
        """Сохраняет или обновляет лучшие параметры для монеты"""
        try:
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO best_params_per_symbol (
                        symbol, rsi_params_json, rating, win_rate, total_pnl, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    symbol, json.dumps(rsi_params), rating, win_rate, total_pnl, now
                ))
                param_id = cursor.lastrowid
                conn.commit()
                return param_id
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения лучших параметров для {symbol}: {e}")
            return None
    
    def get_best_params_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получает лучшие параметры для монеты"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM best_params_per_symbol WHERE symbol = ?", (symbol,))
                row = cursor.fetchone()
                if row:
                    return {
                        'symbol': row['symbol'],
                        'rsi_params': json.loads(row['rsi_params_json']),
                        'rating': row['rating'],
                        'win_rate': row['win_rate'],
                        'total_pnl': row['total_pnl'],
                        'updated_at': row['updated_at']
                    }
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки лучших параметров для {symbol}: {e}")
            return None
    
    def get_all_best_params_per_symbol(self) -> Dict[str, Dict[str, Any]]:
        """Получает лучшие параметры для всех монет"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM best_params_per_symbol")
                rows = cursor.fetchall()
                result = {}
                for row in rows:
                    result[row['symbol']] = {
                        'rsi_params': json.loads(row['rsi_params_json']),
                        'rating': row['rating'],
                        'win_rate': row['win_rate'],
                        'total_pnl': row['total_pnl'],
                        'updated_at': row['updated_at']
                    }
                return result
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки лучших параметров: {e}")
            return {}
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ЗАБЛОКИРОВАННЫМИ ПАРАМЕТРАМИ ====================
    
    def save_blocked_params(self, rsi_params: Dict, block_reasons: Optional[Dict] = None,
                           symbol: Optional[str] = None, blocked_attempts: int = 0,
                           blocked_long: int = 0, blocked_short: int = 0) -> Optional[int]:
        """Сохраняет заблокированные параметры"""
        try:
            now = datetime.now().isoformat()
            # Вычисляем hash параметров для уникальности
            import hashlib
            params_str = json.dumps(rsi_params, sort_keys=True)
            param_hash = hashlib.md5(params_str.encode()).hexdigest()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Используем INSERT OR IGNORE чтобы не дублировать одинаковые параметры
                cursor.execute("""
                    INSERT OR IGNORE INTO blocked_params (
                        param_hash, rsi_params_json, block_reasons_json, 
                        blocked_attempts, blocked_long, blocked_short,
                        symbol, blocked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    param_hash,
                    json.dumps(rsi_params),
                    json.dumps(block_reasons) if block_reasons else None,
                    blocked_attempts,
                    blocked_long,
                    blocked_short,
                    symbol,
                    now
                ))
                param_id = cursor.lastrowid
                conn.commit()
                return param_id
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения заблокированных параметров: {e}")
            return None
    
    def get_blocked_params(self, limit: Optional[int] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получает заблокированные параметры"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM blocked_params WHERE 1=1"
                params = []
                
                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol)
                
                query += " ORDER BY blocked_at DESC"
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    # Конвертируем sqlite3.Row в словарь для работы с .get()
                    row_dict = dict(row)
                    result.append({
                        'rsi_params': json.loads(row_dict['rsi_params_json']),
                        'block_reasons': json.loads(row_dict['block_reasons_json']) if row_dict.get('block_reasons_json') else {},
                        'blocked_at': row_dict['blocked_at'],
                        'blocked_attempts': row_dict.get('blocked_attempts', 0),
                        'blocked_long': row_dict.get('blocked_long', 0),
                        'blocked_short': row_dict.get('blocked_short', 0),
                        'symbol': row_dict.get('symbol'),
                        'timestamp': row_dict.get('blocked_at')  # Для совместимости
                    })
                return result
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки заблокированных параметров: {e}")
            return []
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ЦЕЛЕВЫМИ ЗНАЧЕНИЯМИ WIN RATE ====================
    
    def save_win_rate_target(self, symbol: str, target_win_rate: float,
                             current_win_rate: Optional[float] = None) -> Optional[int]:
        """Сохраняет или обновляет целевое значение win rate для монеты"""
        try:
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO win_rate_targets (
                        symbol, target_win_rate, current_win_rate, updated_at
                    ) VALUES (?, ?, ?, ?)
                """, (symbol, target_win_rate, current_win_rate, now))
                target_id = cursor.lastrowid
                conn.commit()
                return target_id
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения целевого win rate для {symbol}: {e}")
            return None
    
    def get_win_rate_target(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получает целевое значение win rate для монеты"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM win_rate_targets WHERE symbol = ?", (symbol,))
                row = cursor.fetchone()
                if row:
                    return {
                        'symbol': row['symbol'],
                        'target_win_rate': row['target_win_rate'],
                        'current_win_rate': row['current_win_rate'],
                        'updated_at': row['updated_at']
                    }
                return None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки целевого win rate для {symbol}: {e}")
            return None
    
    def get_all_win_rate_targets(self) -> Dict[str, Dict[str, Any]]:
        """Получает все целевые значения win rate"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM win_rate_targets")
                rows = cursor.fetchall()
                result = {}
                for row in rows:
                    result[row['symbol']] = {
                        'target_win_rate': row['target_win_rate'],
                        'current_win_rate': row['current_win_rate'],
                        'updated_at': row['updated_at']
                    }
                return result
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки целевых win rate: {e}")
            return {}
    
    # ==================== МЕТОДЫ ДЛЯ КООРДИНАЦИИ ПАРАЛЛЕЛЬНОЙ ОБРАБОТКИ ====================
    
    def try_lock_symbol(self, symbol: str, process_id: str, hostname: str = None, 
                        lock_duration_minutes: int = 60) -> bool:
        """
        Пытается заблокировать символ для обработки (для параллельной работы на разных ПК)
        
        Args:
            symbol: Символ монеты
            process_id: Уникальный ID процесса (например, PID + timestamp)
            hostname: Имя хоста (опционально)
            lock_duration_minutes: Длительность блокировки в минутах
        
        Returns:
            True если удалось заблокировать, False если уже заблокирован
        """
        try:
            now = datetime.now()
            expires_at = now.replace(second=0, microsecond=0)
            from datetime import timedelta
            expires_at += timedelta(minutes=lock_duration_minutes)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Очищаем истекшие блокировки
                cursor.execute("""
                    DELETE FROM training_locks 
                    WHERE expires_at < ?
                """, (now.isoformat(),))
                
                # Пытаемся заблокировать
                try:
                    cursor.execute("""
                        INSERT INTO training_locks (
                            symbol, process_id, hostname, locked_at, expires_at, status
                        ) VALUES (?, ?, ?, ?, ?, 'PROCESSING')
                    """, (
                        symbol, process_id, hostname, now.isoformat(), expires_at.isoformat()
                    ))
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    # Символ уже заблокирован
                    return False
        except Exception as e:
            logger.debug(f"⚠️ Ошибка блокировки символа {symbol}: {e}")
            return False
    
    def release_lock(self, symbol: str, process_id: str) -> bool:
        """
        Освобождает блокировку символа
        
        Args:
            symbol: Символ монеты
            process_id: ID процесса, который блокировал
        
        Returns:
            True если удалось освободить
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM training_locks 
                    WHERE symbol = ? AND process_id = ?
                """, (symbol, process_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.debug(f"⚠️ Ошибка освобождения блокировки {symbol}: {e}")
            return False
    
    def get_available_symbols(self, all_symbols: List[str], process_id: str, 
                             hostname: str = None) -> List[str]:
        """
        Получает список доступных символов (не заблокированных другими процессами)
        
        Args:
            all_symbols: Все символы для обработки
            process_id: ID текущего процесса
            hostname: Имя хоста (опционально)
        
        Returns:
            Список доступных символов
        """
        try:
            now = datetime.now()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Очищаем истекшие блокировки
                cursor.execute("""
                    DELETE FROM training_locks 
                    WHERE expires_at < ?
                """, (now.isoformat(),))
                conn.commit()
                
                # Получаем заблокированные символы
                cursor.execute("SELECT symbol FROM training_locks")
                locked_symbols = {row[0] for row in cursor.fetchall()}
                
                # Возвращаем только незаблокированные
                available = [s for s in all_symbols if s not in locked_symbols]
                return available
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения доступных символов: {e}")
            return all_symbols  # В случае ошибки возвращаем все
    
    def extend_lock(self, symbol: str, process_id: str, 
                   additional_minutes: int = 30) -> bool:
        """
        Продлевает блокировку символа
        
        Args:
            symbol: Символ монеты
            process_id: ID процесса
            additional_minutes: Сколько минут добавить
        
        Returns:
            True если удалось продлить
        """
        try:
            from datetime import timedelta
            now = datetime.now()
            new_expires_at = now + timedelta(minutes=additional_minutes)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE training_locks 
                    SET expires_at = ?
                    WHERE symbol = ? AND process_id = ?
                """, (new_expires_at.isoformat(), symbol, process_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.debug(f"⚠️ Ошибка продления блокировки {symbol}: {e}")
            return False
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ИСТОРИЕЙ СВЕЧЕЙ ====================
    
    def save_candles(self, symbol: str, candles: List[Dict], timeframe: str = '6h') -> int:
        """
        Сохраняет свечи для символа в БД
        
        Args:
            symbol: Символ монеты
            candles: Список свечей [{'time': int, 'open': float, 'high': float, 'low': float, 'close': float, 'volume': float}, ...]
            timeframe: Таймфрейм (по умолчанию '6h')
        
        Returns:
            Количество сохраненных свечей
        """
        if not candles:
            return 0
        
        try:
            now = datetime.now().isoformat()
            saved_count = 0
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Используем INSERT OR IGNORE для пропуска дубликатов
                cursor.executemany("""
                    INSERT OR IGNORE INTO candles_history (
                        symbol, timeframe, candle_time, open_price, high_price,
                        low_price, close_price, volume, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    (
                        symbol, timeframe,
                        int(candle['time']),
                        float(candle['open']),
                        float(candle['high']),
                        float(candle['low']),
                        float(candle['close']),
                        float(candle['volume']),
                        now
                    )
                    for candle in candles
                ])
                saved_count = cursor.rowcount
                conn.commit()
            return saved_count
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения свечей для {symbol}: {e}")
            return 0
    
    def save_candles_batch(self, candles_data: Dict[str, List[Dict]], timeframe: str = '6h') -> Dict[str, int]:
        """
        Сохраняет свечи для нескольких символов (батч операция)
        
        Args:
            candles_data: Словарь {symbol: [candles]}
            timeframe: Таймфрейм
        
        Returns:
            Словарь {symbol: saved_count}
        """
        results = {}
        for symbol, candles in candles_data.items():
            results[symbol] = self.save_candles(symbol, candles, timeframe)
        return results
    
    def get_candles(self, symbol: str, timeframe: str = '6h', 
                    limit: Optional[int] = None,
                    start_time: Optional[int] = None,
                    end_time: Optional[int] = None) -> List[Dict]:
        """
        Получает свечи для символа
        
        Args:
            symbol: Символ монеты
            timeframe: Таймфрейм
            limit: Максимальное количество свечей
            start_time: Начальное время (timestamp)
            end_time: Конечное время (timestamp)
        
        Returns:
            Список свечей [{'time': int, 'open': float, ...}, ...]
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT candle_time, open_price, high_price, low_price, close_price, volume
                    FROM candles_history
                    WHERE symbol = ? AND timeframe = ?
                """
                params = [symbol, timeframe]
                
                if start_time:
                    query += " AND candle_time >= ?"
                    params.append(start_time)
                
                if end_time:
                    query += " AND candle_time <= ?"
                    params.append(end_time)
                
                query += " ORDER BY candle_time ASC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                candles = []
                for row in rows:
                    candles.append({
                        'time': row['candle_time'],
                        'open': row['open_price'],
                        'high': row['high_price'],
                        'low': row['low_price'],
                        'close': row['close_price'],
                        'volume': row['volume']
                    })
                
                return candles
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки свечей для {symbol}: {e}")
            return []
    
    def get_all_candles_dict(self, timeframe: str = '6h') -> Dict[str, List[Dict]]:
        """
        Получает все свечи для всех символов из БД (таблица candles_history)
        
        Args:
            timeframe: Таймфрейм
        
        Returns:
            Словарь {symbol: [candles]}
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT symbol, candle_time, open_price, high_price, low_price, close_price, volume
                    FROM candles_history
                    WHERE timeframe = ?
                    ORDER BY symbol, candle_time ASC
                """, (timeframe,))
                rows = cursor.fetchall()
                
                result = {}
                for row in rows:
                    symbol = row['symbol']
                    if symbol not in result:
                        result[symbol] = []
                    
                    result[symbol].append({
                        'time': row['candle_time'],
                        'open': row['open_price'],
                        'high': row['high_price'],
                        'low': row['low_price'],
                        'close': row['close_price'],
                        'volume': row['volume']
                    })
                
                return result
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки всех свечей: {e}")
            return {}
    
    def count_candles(self, symbol: Optional[str] = None, timeframe: str = '6h') -> int:
        """Подсчитывает количество свечей"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if symbol:
                    cursor.execute("SELECT COUNT(*) FROM candles_history WHERE symbol = ? AND timeframe = ?", (symbol, timeframe))
                else:
                    cursor.execute("SELECT COUNT(*) FROM candles_history WHERE timeframe = ?", (timeframe,))
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"❌ Ошибка подсчета свечей: {e}")
            return 0
    
    def get_candles_last_time(self, symbol: str, timeframe: str = '6h') -> Optional[int]:
        """Получает время последней свечи для символа"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(candle_time) as last_time
                    FROM candles_history
                    WHERE symbol = ? AND timeframe = ?
                """, (symbol, timeframe))
                row = cursor.fetchone()
                return row['last_time'] if row and row['last_time'] else None
        except Exception as e:
            logger.error(f"❌ Ошибка получения последнего времени для {symbol}: {e}")
            return None
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ДАННЫМИ БОТОВ ====================
    
    def save_bots_data_snapshot(self, bots_data: Dict) -> int:
        """
        Сохраняет снимок данных ботов в БД
        
        Args:
            bots_data: Словарь с данными ботов {
                'timestamp': str,
                'bots': [],
                'rsi_data': {},
                'signals': {},
                'bots_status': {}
            }
        
        Returns:
            ID сохраненной записи
        """
        try:
            now = datetime.now().isoformat()
            snapshot_time = bots_data.get('timestamp', now)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO bots_data_snapshots (
                        snapshot_time, bots_json, rsi_data_json,
                        signals_json, bots_status_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_time,
                    json.dumps(bots_data.get('bots', [])),
                    json.dumps(bots_data.get('rsi_data', {})),
                    json.dumps(bots_data.get('signals', {})),
                    json.dumps(bots_data.get('bots_status', {})),
                    now
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения снимка данных ботов: {e}")
            return 0
    
    def get_bots_data_snapshots(self, limit: int = 1000, 
                                start_time: Optional[str] = None,
                                end_time: Optional[str] = None) -> List[Dict]:
        """
        Получает снимки данных ботов
        
        Args:
            limit: Максимальное количество записей
            start_time: Начальное время (ISO format)
            end_time: Конечное время (ISO format)
        
        Returns:
            Список снимков
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT id, snapshot_time, bots_json, rsi_data_json,
                           signals_json, bots_status_json, created_at
                    FROM bots_data_snapshots
                """
                params = []
                
                conditions = []
                if start_time:
                    conditions.append("snapshot_time >= ?")
                    params.append(start_time)
                if end_time:
                    conditions.append("snapshot_time <= ?")
                    params.append(end_time)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY snapshot_time DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                snapshots = []
                for row in rows:
                    snapshots.append({
                        'id': row['id'],
                        'timestamp': row['snapshot_time'],
                        'bots': json.loads(row['bots_json']) if row['bots_json'] else [],
                        'rsi_data': json.loads(row['rsi_data_json']) if row['rsi_data_json'] else {},
                        'signals': json.loads(row['signals_json']) if row['signals_json'] else {},
                        'bots_status': json.loads(row['bots_status_json']) if row['bots_status_json'] else {},
                        'created_at': row['created_at']
                    })
                
                return snapshots
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки снимков данных ботов: {e}")
            return []
    
    def get_latest_bots_data(self) -> Optional[Dict]:
        """
        Получает последний снимок данных ботов
        
        Returns:
            Последний снимок или None
        """
        snapshots = self.get_bots_data_snapshots(limit=1)
        if snapshots:
            return snapshots[0]
        return None
    
    def count_bots_data_snapshots(self) -> int:
        """Подсчитывает количество снимков данных ботов"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM bots_data_snapshots")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"❌ Ошибка подсчета снимков данных ботов: {e}")
            return 0
    
    def cleanup_old_bots_data_snapshots(self, keep_count: int = 1000) -> int:
        """
        Удаляет старые снимки, оставляя только последние N
        
        Args:
            keep_count: Количество снимков для сохранения
        
        Returns:
            Количество удаленных записей
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Получаем ID записей для удаления
                cursor.execute("""
                    SELECT id FROM bots_data_snapshots
                    ORDER BY snapshot_time DESC
                    LIMIT -1 OFFSET ?
                """, (keep_count,))
                ids_to_delete = [row[0] for row in cursor.fetchall()]
                
                if ids_to_delete:
                    placeholders = ','.join(['?'] * len(ids_to_delete))
                    cursor.execute(f"""
                        DELETE FROM bots_data_snapshots
                        WHERE id IN ({placeholders})
                    """, ids_to_delete)
                    conn.commit()
                    return cursor.rowcount
                return 0
        except Exception as e:
            logger.error(f"❌ Ошибка очистки старых снимков: {e}")
            return 0
    
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
            import shutil
            
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
            
            # Создаем резервную копию текущей БД (если она существует)
            if os.path.exists(self.db_path):
                current_backup = self._backup_database()
                if current_backup:
                    logger.info(f"💾 Текущая БД сохранена как: {current_backup}")
            
            # Восстанавливаем БД
            shutil.copy2(backup_path, self.db_path)
            
            # Восстанавливаем WAL и SHM файлы если есть
            wal_backup = f"{backup_path}-wal"
            shm_backup = f"{backup_path}-shm"
            wal_file = self.db_path + '-wal'
            shm_file = self.db_path + '-shm'
            
            if os.path.exists(wal_backup):
                shutil.copy2(wal_backup, wal_file)
            elif os.path.exists(wal_file):
                os.remove(wal_file)
            
            if os.path.exists(shm_backup):
                shutil.copy2(shm_backup, shm_file)
            elif os.path.exists(shm_file):
                os.remove(shm_file)
            
            logger.info(f"✅ БД восстановлена из резервной копии: {backup_path}")
            
            # Проверяем, что БД работает
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    logger.info("✅ Восстановленная БД проверена и работает")
                    return True
            except Exception as e:
                logger.error(f"❌ Восстановленная БД не работает: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления БД из резервной копии: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    # ==================== МЕТОДЫ ДЛЯ ИСТОРИИ ОБУЧЕНИЯ (training_history) ====================
    
    def add_training_history_record(self, training_data: Dict) -> int:
        """Добавляет запись в историю обучения"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Используем training_sessions для хранения истории
                event_type = training_data.get('event_type', 'TRAINING')
                status = training_data.get('status', 'COMPLETED')
                
                cursor.execute("""
                    INSERT INTO training_sessions (
                        session_type, started_at, completed_at, status, metadata_json
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    event_type,
                    training_data.get('timestamp', now),
                    now if status in ('COMPLETED', 'FAILED') else None,
                    status,
                    json.dumps(training_data)
                ))
                
                return cursor.lastrowid
    
    def get_training_history(self, limit: int = 50) -> List[Dict]:
        """Получает историю обучения"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM training_sessions
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            result = []
            for row in rows:
                record = dict(row)
                if record.get('metadata_json'):
                    metadata = json.loads(record['metadata_json'])
                    record.update(metadata)
                result.append(record)
            
            return result
    
    # ==================== МЕТОДЫ ДЛЯ МЕТРИК ПРОИЗВОДИТЕЛЬНОСТИ ====================
    
    def save_performance_metrics(self, metrics: Dict, symbol: Optional[str] = None):
        """Сохраняет метрики производительности"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Сохраняем общие метрики
                if 'overall' in metrics:
                    for name, value in metrics['overall'].items():
                        if isinstance(value, (int, float)):
                            cursor.execute("""
                                INSERT INTO performance_metrics (
                                    symbol, metric_type, metric_name, metric_value, recorded_at
                                ) VALUES (?, 'overall', ?, ?, ?)
                            """, (symbol, name, float(value), now))
                
                # Сохраняем метрики по символам
                if 'by_symbol' in metrics:
                    for sym, sym_metrics in metrics['by_symbol'].items():
                        for name, value in sym_metrics.items():
                            if isinstance(value, (int, float)):
                                cursor.execute("""
                                    INSERT INTO performance_metrics (
                                        symbol, metric_type, metric_name, metric_value, recorded_at
                                    ) VALUES (?, 'by_symbol', ?, ?, ?)
                                """, (sym, name, float(value), now))
    
    def get_performance_metrics(self, symbol: Optional[str] = None) -> Dict:
        """Получает метрики производительности"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT metric_type, metric_name, metric_value, symbol
                FROM performance_metrics
                WHERE 1=1
            """
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY recorded_at DESC LIMIT 1000"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = {
                'overall': {},
                'by_symbol': {}
            }
            
            for row in rows:
                metric_type = row['metric_type']
                metric_name = row['metric_name']
                metric_value = row['metric_value']
                sym = row['symbol']
                
                if metric_type == 'overall':
                    result['overall'][metric_name] = metric_value
                elif metric_type == 'by_symbol' and sym:
                    if sym not in result['by_symbol']:
                        result['by_symbol'][sym] = {}
                    result['by_symbol'][sym][metric_name] = metric_value
            
            return result
    
    # ==================== МЕТОДЫ ДЛЯ ВЕРСИЙ МОДЕЛЕЙ ====================
    
    def save_model_version(self, version_data: Dict) -> int:
        """Сохраняет версию модели"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                model_id = version_data.get('id', f"model_{int(datetime.now().timestamp())}")
                
                cursor.execute("""
                    INSERT OR REPLACE INTO model_versions (
                        model_id, model_type, version_number, model_path,
                        accuracy, mse, win_rate, total_pnl, training_samples,
                        metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    model_id,
                    version_data.get('model_type', 'UNKNOWN'),
                    version_data.get('version_number'),
                    version_data.get('model_path'),
                    version_data.get('accuracy'),
                    version_data.get('mse'),
                    version_data.get('win_rate'),
                    version_data.get('total_pnl'),
                    version_data.get('training_samples'),
                    json.dumps(version_data),
                    now
                ))
                
                return cursor.lastrowid
    
    def get_model_versions(self, limit: int = 10) -> List[Dict]:
        """Получает версии моделей"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM model_versions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            result = []
            for row in rows:
                version = dict(row)
                if version.get('metadata_json'):
                    metadata = json.loads(version['metadata_json'])
                    version.update(metadata)
                result.append(version)
            
            return result
    
    def get_latest_model_version(self, model_type: Optional[str] = None) -> Optional[Dict]:
        """Получает последнюю версию модели"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM model_versions WHERE 1=1"
            params = []
            
            if model_type:
                query += " AND model_type = ?"
                params.append(model_type)
            
            query += " ORDER BY created_at DESC LIMIT 1"
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            if row:
                version = dict(row)
                if version.get('metadata_json'):
                    metadata = json.loads(version['metadata_json'])
                    version.update(metadata)
                return version
            
            return None
    
    # ==================== МЕТОДЫ ДЛЯ АНАЛИЗА СТРАТЕГИЙ ====================
    
    def save_strategy_analysis(self, analysis_type: str, results: Dict, symbol: Optional[str] = None) -> int:
        """Сохраняет анализ стратегии"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO strategy_analysis (
                        analysis_type, symbol, results_json, created_at
                    ) VALUES (?, ?, ?, ?)
                """, (
                    analysis_type,
                    symbol,
                    json.dumps(results),
                    now
                ))
                
                return cursor.lastrowid
    
    def get_strategy_analysis(self, analysis_type: Optional[str] = None, symbol: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Получает анализ стратегии"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM strategy_analysis WHERE 1=1"
            params = []
            
            if analysis_type:
                query += " AND analysis_type = ?"
                params.append(analysis_type)
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                analysis = dict(row)
                if analysis.get('results_json'):
                    analysis['results'] = json.loads(analysis['results_json'])
                result.append(analysis)
            
            return result
    
    # ==================== МЕТОДЫ ДЛЯ ОПТИМИЗИРОВАННЫХ ПАРАМЕТРОВ ====================
    
    def save_optimized_params(self, symbol: Optional[str], params: Dict, optimization_type: Optional[str] = None) -> int:
        """Сохраняет оптимизированные параметры"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Проверяем существующие параметры
                cursor.execute("""
                    SELECT id FROM optimized_params WHERE symbol = ? AND optimization_type = ?
                """, (symbol, optimization_type))
                existing = cursor.fetchone()
                
                if existing:
                    # Обновляем существующие
                    cursor.execute("""
                        UPDATE optimized_params SET
                            params_json = ?, win_rate = ?, total_pnl = ?, updated_at = ?
                        WHERE id = ?
                    """, (
                        json.dumps(params),
                        params.get('win_rate'),
                        params.get('total_pnl'),
                        now,
                        existing['id']
                    ))
                    return existing['id']
                else:
                    # Создаем новые
                    cursor.execute("""
                        INSERT INTO optimized_params (
                            symbol, params_json, optimization_type, win_rate, total_pnl, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol,
                        json.dumps(params),
                        optimization_type,
                        params.get('win_rate'),
                        params.get('total_pnl'),
                        now,
                        now
                    ))
                    return cursor.lastrowid
    
    def get_optimized_params(self, symbol: Optional[str] = None, optimization_type: Optional[str] = None) -> Optional[Dict]:
        """Получает оптимизированные параметры"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM optimized_params WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if optimization_type:
                query += " AND optimization_type = ?"
                params.append(optimization_type)
            
            query += " ORDER BY updated_at DESC LIMIT 1"
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            if row:
                result = dict(row)
                if result.get('params_json'):
                    result['params'] = json.loads(result['params_json'])
                return result
            
            return None
    
    # ==================== МЕТОДЫ ДЛЯ ПАТТЕРНОВ ТОРГОВЛИ ====================
    
    def save_trade_patterns(self, patterns: List[Dict]) -> int:
        """Сохраняет паттерны торговли"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                saved_count = 0
                
                for pattern in patterns:
                    cursor.execute("""
                        INSERT OR REPLACE INTO trading_patterns (
                            pattern_type, symbol, rsi_range, trend_condition, volatility_range,
                            success_count, failure_count, avg_pnl, avg_duration,
                            pattern_data_json, discovered_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        pattern.get('pattern_type'),
                        pattern.get('symbol'),
                        pattern.get('rsi_range'),
                        pattern.get('trend_condition'),
                        pattern.get('volatility_range'),
                        pattern.get('success_count', 0),
                        pattern.get('failure_count', 0),
                        pattern.get('avg_pnl'),
                        pattern.get('avg_duration'),
                        json.dumps(pattern.get('pattern_data', {})),
                        pattern.get('discovered_at', now),
                        now
                    ))
                    saved_count += 1
                
                return saved_count
    
    def get_trade_patterns(self, pattern_type: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict]:
        """Получает паттерны торговли"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM trading_patterns WHERE 1=1"
            params = []
            
            if pattern_type:
                query += " AND pattern_type = ?"
                params.append(pattern_type)
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY last_seen_at DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                pattern = dict(row)
                if pattern.get('pattern_data_json'):
                    pattern['pattern_data'] = json.loads(pattern['pattern_data_json'])
                result.append(pattern)
            
            return result
    
    # ==================== МЕТОДЫ ДЛЯ СТАТУСА СЕРВИСА ДАННЫХ ====================
    
    def save_data_service_status(self, service_name: str, status: Dict) -> int:
        """Сохраняет статус сервиса данных"""
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO data_service_status (
                        service_name, status_json, updated_at
                    ) VALUES (?, ?, ?)
                """, (
                    service_name,
                    json.dumps(status),
                    now
                ))
                
                return cursor.lastrowid
    
    def get_data_service_status(self, service_name: str) -> Optional[Dict]:
        """Получает статус сервиса данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM data_service_status WHERE service_name = ?
            """, (service_name,))
            
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get('status_json'):
                    result['status'] = json.loads(result['status_json'])
                return result
            
            return None
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Получает общую статистику базы данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Подсчеты по таблицам
            tables = ['simulated_trades', 'bot_trades', 'exchange_trades', 'ai_decisions', 
                     'training_sessions', 'parameter_training_samples', 'used_training_parameters',
                     'best_params_per_symbol', 'blocked_params', 'win_rate_targets', 'training_locks',
                     'candles_history', 'bots_data_snapshots', 'model_versions', 'performance_metrics',
                     'strategy_analysis', 'optimized_params', 'trading_patterns', 'data_service_status']
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            
            # Размер базы данных
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            stats['database_size_mb'] = db_size / 1024 / 1024
            
            # Статистика по символам
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM simulated_trades")
            stats['unique_symbols_simulated'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM bot_trades WHERE is_simulated = 0")
            stats['unique_symbols_real'] = cursor.fetchone()[0]
            
            return stats


# Глобальный экземпляр базы данных
_ai_database_instance = None
_ai_database_lock = threading.Lock()


def get_ai_database(db_path: str = None) -> AIDatabase:
    """Получает глобальный экземпляр базы данных AI"""
    global _ai_database_instance
    
    with _ai_database_lock:
        if _ai_database_instance is None:
            _ai_database_instance = AIDatabase(db_path)
        
        return _ai_database_instance

