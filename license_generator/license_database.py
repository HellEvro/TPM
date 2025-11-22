"""
База данных для хранения получателей лицензий
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger('LicenseDatabase')


class LicenseDatabase:
    """Управление базой данных получателей лицензий"""
    
    def __init__(self, db_path: str = None):
        """
        Инициализация базы данных
        
        Args:
            db_path: Путь к файлу базы данных (если None, используется license_generator/licenses.db)
        """
        if db_path is None:
            script_dir = Path(__file__).parent
            db_path = str(script_dir / "licenses.db")
        
        self.db_path = db_path
        
        # Определяем корень проекта (родительская директория license_generator)
        self.project_root = Path(__file__).parent.parent.absolute()
        
        self._init_database()
    
    def _to_relative_path(self, file_path: str) -> Optional[str]:
        """
        Преобразует абсолютный путь в относительный от корня проекта
        
        Args:
            file_path: Абсолютный путь к файлу
        
        Returns:
            Относительный путь или None если путь не в проекте
        """
        if not file_path:
            return None
        
        try:
            abs_path = Path(file_path).absolute()
            try:
                relative = abs_path.relative_to(self.project_root)
                return str(relative).replace('\\', '/')  # Нормализуем разделители
            except ValueError:
                # Путь не находится в проекте - возвращаем как есть (для обратной совместимости)
                return file_path
        except Exception:
            return file_path
    
    def _to_absolute_path(self, file_path: str) -> Optional[str]:
        """
        Преобразует относительный путь в абсолютный
        
        Args:
            file_path: Относительный путь от корня проекта
        
        Returns:
            Абсолютный путь или None
        """
        if not file_path:
            return None
        
        try:
            # Если путь уже абсолютный - возвращаем как есть
            if os.path.isabs(file_path):
                return file_path
            
            # Преобразуем относительный путь в абсолютный
            abs_path = (self.project_root / file_path).absolute()
            return str(abs_path)
        except Exception:
            return file_path
    
    def _init_database(self):
        """Создает таблицы базы данных, если их нет"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу, если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS license_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hw_id TEXT,
                days INTEGER NOT NULL,
                start_date TEXT,
                end_date TEXT NOT NULL,
                recipient TEXT,
                comments TEXT,
                license_file TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Миграция: если таблица существует с NOT NULL, обновляем схему
        try:
            cursor.execute("PRAGMA table_info(license_recipients)")
            columns = cursor.fetchall()
            # Проверяем, есть ли ограничение NOT NULL на hw_id
            hw_id_not_null = any(col[1] == 'hw_id' and col[3] == 1 for col in columns)
            if hw_id_not_null:
                # Создаем новую таблицу без NOT NULL
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS license_recipients_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hw_id TEXT,
                        days INTEGER NOT NULL,
                        start_date TEXT,
                        end_date TEXT NOT NULL,
                        recipient TEXT,
                        comments TEXT,
                        license_file TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                # Копируем данные
                cursor.execute("INSERT INTO license_recipients_new SELECT * FROM license_recipients")
                # Удаляем старую таблицу
                cursor.execute("DROP TABLE license_recipients")
                # Переименовываем новую
                cursor.execute("ALTER TABLE license_recipients_new RENAME TO license_recipients")
                conn.commit()
        except Exception:
            # Если ошибка - значит таблица уже обновлена или её нет
            pass
        
        # Индекс для быстрого поиска по HWID
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hw_id ON license_recipients(hw_id)
        """)
        
        # ==================== МИГРАЦИЯ: Преобразование абсолютных путей в относительные ====================
        try:
            # Проверяем, есть ли записи с абсолютными путями
            cursor.execute("SELECT id, license_file FROM license_recipients WHERE license_file IS NOT NULL LIMIT 1")
            row = cursor.fetchone()
            
            if row and row[1]:
                # Проверяем, является ли путь абсолютным
                test_path = row[1]
                if os.path.isabs(test_path) and Path(test_path).exists():
                    logger.info("📦 Обнаружены абсолютные пути в license_file, выполняю миграцию в относительные...")
                    
                    # Получаем все записи с абсолютными путями
                    cursor.execute("SELECT id, license_file FROM license_recipients WHERE license_file IS NOT NULL")
                    all_rows = cursor.fetchall()
                    
                    migrated_count = 0
                    for record_row in all_rows:
                        record_id = record_row[0]
                        abs_path = record_row[1]
                        
                        if abs_path and os.path.isabs(abs_path):
                            # Преобразуем в относительный путь
                            relative_path = self._to_relative_path(abs_path)
                            if relative_path and relative_path != abs_path:
                                cursor.execute("""
                                    UPDATE license_recipients 
                                    SET license_file = ? 
                                    WHERE id = ?
                                """, (relative_path, record_id))
                                migrated_count += 1
                    
                    if migrated_count > 0:
                        logger.info(f"✅ Миграция license_file завершена: {migrated_count} путей преобразовано из абсолютных в относительные")
                    else:
                        logger.debug("ℹ️ Все пути уже относительные")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка миграции license_file: {e}")
        
        conn.commit()
        conn.close()
    
    def add_recipient(self, 
                     hw_id: Optional[str] = None,
                     days: int = None,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None,
                     recipient: str = None,
                     comments: str = None,
                     license_file: str = None) -> int:
        """
        Добавляет получателя лицензии в базу данных
        
        Args:
            hw_id: Hardware ID (None для developer/универсальных лицензий)
            days: Количество дней лицензии
            start_date: Дата начала (опционально)
            end_date: Дата окончания (обязательно, если не указана start_date)
            recipient: Контактная информация получателя (email, telegram, и т.д.)
            comments: Комментарии
            license_file: Путь к файлу лицензии (абсолютный или относительный - будет сохранен как относительный)
        
        Returns:
            ID созданной записи
        """
        now = datetime.now().isoformat()
        
        # Преобразуем абсолютный путь в относительный перед сохранением
        license_file_relative = self._to_relative_path(license_file) if license_file else None
        
        # Преобразуем даты в строки
        start_date_str = start_date.isoformat() if start_date else None
        end_date_str = end_date.isoformat() if end_date else None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO license_recipients 
            (hw_id, days, start_date, end_date, recipient, comments, license_file, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (hw_id, days, start_date_str, end_date_str, recipient, comments, license_file_relative, now, now))
        
        recipient_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return recipient_id
    
    def update_recipient(self, 
                        recipient_id: int,
                        hw_id: str = None,
                        days: int = None,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None,
                        recipient: str = None,
                        comments: str = None,
                        license_file: str = None):
        """
        Обновляет данные получателя лицензии
        
        Args:
            recipient_id: ID записи
            hw_id: Hardware ID (если нужно обновить)
            days: Количество дней (если нужно обновить)
            start_date: Дата начала (если нужно обновить)
            end_date: Дата окончания (если нужно обновить)
            recipient: Контактная информация получателя (если нужно обновить)
            comments: Комментарии (если нужно обновить)
            license_file: Путь к файлу лицензии (если нужно обновить)
        """
        now = datetime.now().isoformat()
        
        # Собираем поля для обновления
        updates = []
        values = []
        
        if hw_id is not None:
            updates.append("hw_id = ?")
            values.append(hw_id)
        
        if days is not None:
            updates.append("days = ?")
            values.append(days)
        
        if start_date is not None:
            updates.append("start_date = ?")
            values.append(start_date.isoformat())
        
        if end_date is not None:
            updates.append("end_date = ?")
            values.append(end_date.isoformat())
        
        if recipient is not None:
            updates.append("recipient = ?")
            values.append(recipient)
        
        if comments is not None:
            updates.append("comments = ?")
            values.append(comments)
        
        if license_file is not None:
            updates.append("license_file = ?")
            # Преобразуем абсолютный путь в относительный перед сохранением
            license_file_relative = self._to_relative_path(license_file)
            values.append(license_file_relative)
        
        if not updates:
            return
        
        updates.append("updated_at = ?")
        values.append(now)
        values.append(recipient_id)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            UPDATE license_recipients 
            SET {', '.join(updates)}
            WHERE id = ?
        """, values)
        
        conn.commit()
        conn.close()
    
    def get_recipient(self, recipient_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает данные получателя по ID
        
        Args:
            recipient_id: ID записи
        
        Returns:
            Словарь с данными получателя или None (license_file преобразован в абсолютный путь)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM license_recipients WHERE id = ?", (recipient_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row is None:
            return None
        
        result = dict(row)
        # Преобразуем относительный путь обратно в абсолютный при загрузке
        if result.get('license_file'):
            result['license_file'] = self._to_absolute_path(result['license_file'])
        
        return result
    
    def get_all_recipients(self) -> List[Dict[str, Any]]:
        """
        Получает всех получателей лицензий
        
        Returns:
            Список словарей с данными получателей (license_file преобразован в абсолютный путь)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM license_recipients ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        conn.close()
        
        result = []
        for row in rows:
            recipient = dict(row)
            # Преобразуем относительный путь обратно в абсолютный при загрузке
            if recipient.get('license_file'):
                recipient['license_file'] = self._to_absolute_path(recipient['license_file'])
            result.append(recipient)
        
        return result
    
    def search_by_hw_id(self, hw_id: str) -> List[Dict[str, Any]]:
        """
        Ищет получателей по Hardware ID
        
        Args:
            hw_id: Hardware ID для поиска
        
        Returns:
            Список словарей с данными получателей (license_file преобразован в абсолютный путь)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM license_recipients WHERE hw_id LIKE ? ORDER BY created_at DESC", 
                       (f"%{hw_id}%",))
        rows = cursor.fetchall()
        
        conn.close()
        
        result = []
        for row in rows:
            recipient = dict(row)
            # Преобразуем относительный путь обратно в абсолютный при загрузке
            if recipient.get('license_file'):
                recipient['license_file'] = self._to_absolute_path(recipient['license_file'])
            result.append(recipient)
        
        return result
    
    def delete_recipient(self, recipient_id: int) -> bool:
        """
        Удаляет получателя из базы данных
        
        Args:
            recipient_id: ID записи
        
        Returns:
            True если удалено успешно, False если запись не найдена
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM license_recipients WHERE id = ?", (recipient_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted

