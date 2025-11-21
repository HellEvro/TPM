#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI приложение для работы с базами данных InfoBot

Возможности:
- Автоматический поиск всех БД в проекте
- Открытие внешних БД
- SQL редактор для выполнения запросов
- GUI интерфейс для CRUD операций
- Изменяемые размеры окон
"""

import os
import sys
import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, filedialog
except ImportError:
    print("Ошибка: требуется tkinter. Установите python3-tk или используйте Python с поддержкой tkinter.")
    sys.exit(1)

# Настройка кодировки для Windows консоли
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Определяем корневую директорию проекта
ROOT = Path(__file__).parent.parent


class DatabaseConnection:
    """Класс для работы с подключением к базе данных"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        
    def connect(self) -> bool:
        """Подключается к базе данных"""
        try:
            self.conn = sqlite3.connect(self.db_path, timeout=10.0)
            self.conn.row_factory = sqlite3.Row  # Возвращаем результаты как словари
            return True
        except Exception as e:
            messagebox.showerror("Ошибка подключения", f"Не удалось подключиться к БД:\n{e}")
            return False
    
    def disconnect(self):
        """Отключается от базы данных"""
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
            self.conn = None
    
    def execute_query(self, query: str, params: Tuple = None) -> Tuple[Optional[List], Optional[str]]:
        """
        Выполняет SQL запрос
        
        Args:
            query: SQL запрос
            params: Параметры для запроса (опционально)
        
        Returns:
            (results, error_message) - результаты запроса или сообщение об ошибке
        """
        if not self.conn:
            return None, "Нет подключения к БД"
        
        try:
            cursor = self.conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Если запрос изменяет данные, коммитим
            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                self.conn.commit()
                return [], None  # Изменяющие запросы не возвращают данные
            
            # Получаем результаты
            results = cursor.fetchall()
            # Конвертируем Row объекты в списки словарей
            rows = []
            for row in results:
                rows.append(dict(row))
            return rows, None
        except sqlite3.Error as e:
            return None, str(e)
    
    def get_tables(self) -> List[str]:
        """Получает список всех таблиц в БД"""
        if not self.conn:
            return []
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            return [row[0] for row in cursor.fetchall()]
        except:
            return []
    
    def get_table_schema(self, table_name: str) -> List[Dict]:
        """Получает схему таблицы"""
        if not self.conn:
            return []
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            return [
                {
                    'cid': col[0],
                    'name': col[1],
                    'type': col[2],
                    'notnull': bool(col[3]),
                    'dflt_value': col[4],
                    'pk': bool(col[5])
                }
                for col in columns
            ]
        except:
            return []
    
    def get_table_data(self, table_name: str, limit: int = 1000, offset: int = 0) -> Tuple[List[Dict], int]:
        """
        Получает данные из таблицы с пагинацией
        
        Returns:
            (rows, total_count) - данные и общее количество записей
        """
        if not self.conn:
            return [], 0
        
        try:
            cursor = self.conn.cursor()
            
            # Получаем общее количество записей
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_count = cursor.fetchone()[0]
            
            # Получаем данные с лимитом
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
            rows = cursor.fetchall()
            
            # Конвертируем в список словарей
            result = []
            for row in rows:
                result.append(dict(row))
            
            return result, total_count
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить данные:\n{e}")
            return [], 0


class DatabaseGUI(tk.Tk):
    """Главное окно GUI для работы с базами данных"""
    
    def __init__(self):
        super().__init__()
        
        self.title("InfoBot Database Manager")
        self.geometry("1400x900")
        self.minsize(1000, 700)
        
        # Текущее подключение к БД
        self.db_conn: Optional[DatabaseConnection] = None
        self.current_table: Optional[str] = None
        
        # Переменные
        self.db_path_var = tk.StringVar()
        self.table_var = tk.StringVar()
        
        # Создаем интерфейс
        self._build_ui()
        
        # Автоматически находим и загружаем БД из проекта
        self._auto_discover_databases()
    
    def _build_ui(self):
        """Создает интерфейс приложения"""
        # Главный контейнер с изменяемыми размерами
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # === ЛЕВАЯ ПАНЕЛЬ: Управление БД ===
        left_frame = ttk.Frame(main_paned, width=300)
        main_paned.add(left_frame, weight=1)
        
        # Заголовок
        title_label = ttk.Label(
            left_frame,
            text="Базы данных",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=10)
        
        # Кнопки управления БД
        db_buttons_frame = ttk.Frame(left_frame)
        db_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            db_buttons_frame,
            text="Найти БД в проекте",
            command=self._auto_discover_databases
        ).pack(fill=tk.X, pady=2)
        
        ttk.Button(
            db_buttons_frame,
            text="Открыть внешнюю БД",
            command=self._open_external_database
        ).pack(fill=tk.X, pady=2)
        
        ttk.Button(
            db_buttons_frame,
            text="Обновить список",
            command=self._refresh_databases
        ).pack(fill=tk.X, pady=2)
        
        # Список найденных БД
        db_list_frame = ttk.LabelFrame(left_frame, text="Найденные БД", padding=5)
        db_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview для списка БД
        db_tree = ttk.Treeview(db_list_frame, show="tree", height=15)
        db_tree.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar для списка
        db_scroll = ttk.Scrollbar(db_list_frame, orient=tk.VERTICAL, command=db_tree.yview)
        db_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        db_tree.configure(yscrollcommand=db_scroll.set)
        
        self.db_tree = db_tree
        
        # Привязываем двойной клик к открытию БД
        db_tree.bind("<Double-1>", lambda e: self._open_database_from_tree())
        
        # Информация о текущей БД
        info_frame = ttk.LabelFrame(left_frame, text="Информация о БД", padding=5)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.db_info_text = tk.Text(info_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
        self.db_info_text.pack(fill=tk.X)
        
        # === ПРАВАЯ ПАНЕЛЬ: Работа с данными ===
        right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_paned, weight=3)
        
        # === ВЕРХНЯЯ ПАНЕЛЬ: SQL редактор ===
        sql_frame = ttk.LabelFrame(right_paned, text="SQL Редактор", padding=5)
        right_paned.add(sql_frame, weight=1)
        
        # SQL редактор
        sql_text = scrolledtext.ScrolledText(
            sql_frame,
            wrap=tk.NONE,
            font=("Consolas", 10),
            height=10
        )
        sql_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.sql_text = sql_text
        
        # Кнопки SQL
        sql_buttons_frame = ttk.Frame(sql_frame)
        sql_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            sql_buttons_frame,
            text="Выполнить запрос (F5)",
            command=self._execute_sql
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            sql_buttons_frame,
            text="Очистить",
            command=lambda: self.sql_text.delete(1.0, tk.END)
        ).pack(side=tk.LEFT, padx=2)
        
        # Привязываем F5 к выполнению запроса
        self.bind('<F5>', lambda e: self._execute_sql())
        
        # === НИЖНЯЯ ПАНЕЛЬ: GUI для таблиц ===
        tables_paned = ttk.PanedWindow(right_paned, orient=tk.HORIZONTAL)
        right_paned.add(tables_paned, weight=2)
        
        # Левая часть: Список таблиц и данные
        tables_frame = ttk.LabelFrame(tables_paned, text="Таблицы и данные", padding=5)
        tables_paned.add(tables_frame, weight=2)
        
        # Список таблиц
        tables_list_frame = ttk.Frame(tables_frame)
        tables_list_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(tables_list_frame, text="Таблицы:").pack(side=tk.LEFT)
        tables_combo = ttk.Combobox(
            tables_list_frame,
            textvariable=self.table_var,
            state="readonly",
            width=30
        )
        tables_combo.pack(side=tk.LEFT, padx=5)
        tables_combo.bind("<<ComboboxSelected>>", lambda e: self._load_table_data())
        self.tables_combo = tables_combo
        
        # Кнопки управления таблицей
        table_buttons_frame = ttk.Frame(tables_frame)
        table_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            table_buttons_frame,
            text="Обновить",
            command=self._load_table_data
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            table_buttons_frame,
            text="Добавить запись",
            command=self._add_record
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            table_buttons_frame,
            text="Редактировать",
            command=self._edit_record
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            table_buttons_frame,
            text="Удалить",
            command=self._delete_record
        ).pack(side=tk.LEFT, padx=2)
        
        # Данные таблицы
        data_frame = ttk.Frame(tables_frame)
        data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview для отображения данных
        data_tree = ttk.Treeview(data_frame)
        data_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=data_tree.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll = ttk.Scrollbar(data_frame, orient=tk.HORIZONTAL, command=data_tree.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        data_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.data_tree = data_tree
        
        # Информация о записях
        records_info = ttk.Label(tables_frame, text="Записей: 0")
        records_info.pack(padx=5, pady=2)
        self.records_info = records_info
        
        # Правая часть: Результаты SQL
        results_frame = ttk.LabelFrame(tables_paned, text="Результаты SQL", padding=5)
        tables_paned.add(results_frame, weight=1)
        
        # Treeview для результатов
        results_tree = ttk.Treeview(results_frame)
        results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbars для результатов
        res_v_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
        res_v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        res_h_scroll = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=results_tree.xview)
        res_h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        results_tree.configure(yscrollcommand=res_v_scroll.set, xscrollcommand=res_h_scroll.set)
        
        self.results_tree = results_tree
    
    def _auto_discover_databases(self):
        """Автоматически находит все БД в проекте"""
        databases = []
        
        # Список известных путей к БД
        known_paths = [
            ROOT / "data" / "bots_data.db",
            ROOT / "data" / "ai" / "ai_data.db",
            ROOT / "license_generator" / "licenses.db",
        ]
        
        # Добавляем все .db файлы из проекта
        for db_file in ROOT.rglob("*.db"):
            # Пропускаем файлы .db-wal и .db-shm
            if db_file.name.endswith(('-wal', '-shm')):
                continue
            databases.append({
                'name': db_file.name,
                'path': str(db_file),
                'relative_path': str(db_file.relative_to(ROOT)),
                'size': db_file.stat().st_size if db_file.exists() else 0
            })
        
        # Обновляем дерево БД
        self._update_database_tree(databases)
    
    def _update_database_tree(self, databases: List[Dict]):
        """Обновляет дерево со списком БД"""
        # Очищаем дерево
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
        
        # Добавляем БД в дерево
        root_id = self.db_tree.insert("", tk.END, text="Проект", open=True)
        
        for db in databases:
            size_mb = db['size'] / 1024 / 1024
            display_text = f"{db['name']} ({size_mb:.2f} MB)"
            item_id = self.db_tree.insert(
                root_id,
                tk.END,
                text=display_text,
                values=(db['path'], db['relative_path'])
            )
    
    def _open_database_from_tree(self):
        """Открывает БД из дерева (двойной клик)"""
        selection = self.db_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.db_tree.item(item, "values")
        
        if values:
            db_path = values[0]
            self._open_database(db_path)
    
    def _open_external_database(self):
        """Открывает внешнюю БД через диалог выбора файла"""
        db_path = filedialog.askopenfilename(
            title="Выберите базу данных",
            filetypes=[("SQLite databases", "*.db"), ("All files", "*.*")]
        )
        
        if db_path:
            self._open_database(db_path)
            # Добавляем в дерево
            self._refresh_databases()
    
    def _open_database(self, db_path: str):
        """Открывает базу данных"""
        # Закрываем текущее подключение
        if self.db_conn:
            self.db_conn.disconnect()
        
        # Создаем новое подключение
        self.db_conn = DatabaseConnection(db_path)
        
        if not self.db_conn.connect():
            self.db_conn = None
            return
        
        self.db_path_var.set(db_path)
        
        # Обновляем информацию о БД
        self._update_database_info()
        
        # Загружаем список таблиц
        self._load_tables_list()
        
        messagebox.showinfo("Успех", f"База данных открыта:\n{db_path}")
    
    def _update_database_info(self):
        """Обновляет информацию о текущей БД"""
        if not self.db_conn or not self.db_conn.conn:
            self.db_info_text.config(state=tk.NORMAL)
            self.db_info_text.delete(1.0, tk.END)
            self.db_info_text.config(state=tk.DISABLED)
            return
        
        try:
            # Получаем информацию о БД
            db_path = self.db_conn.db_path
            file_size = os.path.getsize(db_path) / 1024 / 1024
            tables = self.db_conn.get_tables()
            
            info_text = f"Путь: {db_path}\n"
            info_text += f"Размер: {file_size:.2f} MB\n"
            info_text += f"Таблиц: {len(tables)}\n"
            
            # Получаем статистику
            if tables:
                cursor = self.db_conn.conn.cursor()
                stats = []
                for table in tables[:5]:  # Показываем только первые 5 таблиц
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        stats.append(f"{table}: {count} записей")
                    except:
                        pass
                if stats:
                    info_text += "\n".join(stats)
            
            self.db_info_text.config(state=tk.NORMAL)
            self.db_info_text.delete(1.0, tk.END)
            self.db_info_text.insert(1.0, info_text)
            self.db_info_text.config(state=tk.DISABLED)
        except Exception as e:
            self.db_info_text.config(state=tk.NORMAL)
            self.db_info_text.delete(1.0, tk.END)
            self.db_info_text.insert(1.0, f"Ошибка: {e}")
            self.db_info_text.config(state=tk.DISABLED)
    
    def _load_tables_list(self):
        """Загружает список таблиц в комбобокс"""
        if not self.db_conn:
            return
        
        tables = self.db_conn.get_tables()
        self.tables_combo['values'] = tables
        
        if tables:
            self.tables_combo.current(0)
            self.current_table = tables[0]
            self._load_table_data()
    
    def _load_table_data(self):
        """Загружает данные из выбранной таблицы"""
        if not self.db_conn:
            return
        
        table_name = self.table_var.get()
        if not table_name:
            return
        
        self.current_table = table_name
        
        # Очищаем treeview
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        
        # Получаем схему таблицы
        schema = self.db_conn.get_table_schema(table_name)
        if not schema:
            return
        
        # Настраиваем колонки
        columns = [col['name'] for col in schema]
        self.data_tree['columns'] = columns
        self.data_tree['show'] = 'headings'
        
        # Настраиваем заголовки
        for col in columns:
            self.data_tree.heading(col, text=col)
            self.data_tree.column(col, width=150, minwidth=100)
        
        # Загружаем данные
        rows, total_count = self.db_conn.get_table_data(table_name)
        
        # Добавляем данные
        for row in rows:
            values = [str(row.get(col, '')) for col in columns]
            self.data_tree.insert("", tk.END, values=values)
        
        # Обновляем информацию о записях
        self.records_info.config(text=f"Записей: {total_count} (показано: {len(rows)})")
    
    def _execute_sql(self):
        """Выполняет SQL запрос"""
        if not self.db_conn:
            messagebox.showwarning("Предупреждение", "База данных не открыта")
            return
        
        query = self.sql_text.get(1.0, tk.END).strip()
        if not query:
            messagebox.showwarning("Предупреждение", "SQL запрос пуст")
            return
        
        # Выполняем запрос
        results, error = self.db_conn.execute_query(query)
        
        if error:
            messagebox.showerror("Ошибка SQL", f"Ошибка выполнения запроса:\n{error}")
            return
        
        # Очищаем результаты
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Отображаем результаты
        if results:
            # Получаем колонки из первой записи
            columns = list(results[0].keys())
            self.results_tree['columns'] = columns
            self.results_tree['show'] = 'headings'
            
            # Настраиваем заголовки
            for col in columns:
                self.results_tree.heading(col, text=col)
                self.results_tree.column(col, width=150, minwidth=100)
            
            # Добавляем данные
            for row in results:
                values = [str(row.get(col, '')) for col in columns]
                self.results_tree.insert("", tk.END, values=values)
            
            messagebox.showinfo("Успех", f"Запрос выполнен. Найдено записей: {len(results)}")
        else:
            messagebox.showinfo("Успех", "Запрос выполнен успешно")
            # Обновляем данные таблицы, если была выбрана таблица
            if self.current_table:
                self._load_table_data()
    
    def _add_record(self):
        """Открывает диалог для добавления новой записи"""
        if not self.db_conn or not self.current_table:
            messagebox.showwarning("Предупреждение", "Выберите таблицу")
            return
        
        RecordDialog(self, self.db_conn, self.current_table, mode='add', callback=self._load_table_data)
    
    def _edit_record(self):
        """Открывает диалог для редактирования записи"""
        if not self.db_conn or not self.current_table:
            messagebox.showwarning("Предупреждение", "Выберите таблицу")
            return
        
        selection = self.data_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите запись для редактирования")
            return
        
        # Получаем данные выбранной записи
        item = selection[0]
        values = self.data_tree.item(item, "values")
        columns = self.data_tree['columns']
        
        record = {col: values[i] for i, col in enumerate(columns)}
        
        RecordDialog(self, self.db_conn, self.current_table, mode='edit', record=record, callback=self._load_table_data)
    
    def _delete_record(self):
        """Удаляет выбранную запись"""
        if not self.db_conn or not self.current_table:
            messagebox.showwarning("Предупреждение", "Выберите таблицу")
            return
        
        selection = self.data_tree.selection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Выберите запись для удаления")
            return
        
        # Подтверждение
        if not messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить эту запись?"):
            return
        
        # Получаем данные выбранной записи
        item = selection[0]
        values = self.data_tree.item(item, "values")
        columns = self.data_tree['columns']
        
        # Получаем схему таблицы для определения первичного ключа
        schema = self.db_conn.get_table_schema(self.current_table)
        pk_columns = [col['name'] for col in schema if col['pk']]
        
        if not pk_columns:
            messagebox.showerror("Ошибка", "Не найдено первичного ключа для удаления записи")
            return
        
        # Формируем WHERE условие
        conditions = []
        params = []
        for pk_col in pk_columns:
            col_idx = columns.index(pk_col)
            conditions.append(f"{pk_col} = ?")
            params.append(values[col_idx])
        
        where_clause = " AND ".join(conditions)
        query = f"DELETE FROM {self.current_table} WHERE {where_clause}"
        
        # Выполняем удаление
        results, error = self.db_conn.execute_query(query, tuple(params))
        
        if error:
            messagebox.showerror("Ошибка", f"Ошибка удаления записи:\n{error}")
        else:
            messagebox.showinfo("Успех", "Запись удалена")
            self._load_table_data()
    
    def _refresh_databases(self):
        """Обновляет список БД"""
        self._auto_discover_databases()
    
    def on_closing(self):
        """Обработчик закрытия окна"""
        if self.db_conn:
            self.db_conn.disconnect()
        self.destroy()


class RecordDialog(tk.Toplevel):
    """Диалог для добавления/редактирования записи"""
    
    def __init__(self, parent, db_conn: DatabaseConnection, table_name: str, mode: str = 'add', record: Dict = None, callback=None):
        super().__init__(parent)
        
        self.db_conn = db_conn
        self.table_name = table_name
        self.mode = mode
        self.record = record or {}
        self.callback = callback
        
        self.title(f"{'Редактирование' if mode == 'edit' else 'Добавление'} записи: {table_name}")
        self.geometry("600x500")
        self.resizable(True, True)
        
        # Переменные для полей
        self.field_vars = {}
        
        # Создаем интерфейс
        self._build_ui()
        
        # Фокусируемся на этом окне
        self.transient(parent)
        self.grab_set()
    
    def _build_ui(self):
        """Создает интерфейс диалога"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Получаем схему таблицы
        schema = self.db_conn.get_table_schema(self.table_name)
        
        # Контейнер с прокруткой для полей
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Создаем поля для каждой колонки (кроме AUTOINCREMENT)
        fields_frame = scrollable_frame
        
        row = 0
        for col in schema:
            col_name = col['name']
            col_type = col['type'].upper()
            
            # Пропускаем AUTOINCREMENT колонки при добавлении
            if self.mode == 'add' and col['pk'] and 'INTEGER' in col_type:
                continue
            
            # Создаем label
            label = ttk.Label(fields_frame, text=f"{col_name}:")
            label.grid(row=row, column=0, sticky="w", padx=5, pady=5)
            
            # Создаем поле ввода
            if 'TEXT' in col_type or 'VARCHAR' in col_type or 'CHAR' in col_type:
                # Текстовое поле
                if self.mode == 'edit' and col['pk']:
                    # Первичный ключ - только чтение при редактировании
                    entry = ttk.Entry(fields_frame, state='readonly')
                    entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
                    var = tk.StringVar(value=str(self.record.get(col_name, '')))
                    entry.config(textvariable=var)
                else:
                    entry = ttk.Entry(fields_frame, width=40)
                    entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
                    var = tk.StringVar(value=str(self.record.get(col_name, '')))
                    entry.config(textvariable=var)
            elif 'INTEGER' in col_type or 'REAL' in col_type or 'NUMERIC' in col_type:
                # Числовое поле
                entry = ttk.Entry(fields_frame, width=40)
                entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
                var = tk.StringVar(value=str(self.record.get(col_name, '')))
                entry.config(textvariable=var)
            else:
                # По умолчанию текстовое поле
                entry = ttk.Entry(fields_frame, width=40)
                entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
                var = tk.StringVar(value=str(self.record.get(col_name, '')))
                entry.config(textvariable=var)
            
            fields_frame.columnconfigure(1, weight=1)
            self.field_vars[col_name] = var
            row += 1
        
        # Упаковываем canvas и scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Привязываем прокрутку колесом мыши
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Кнопки
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            buttons_frame,
            text="Сохранить",
            command=self._save_record
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="Отмена",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)
    
    def _save_record(self):
        """Сохраняет запись"""
        schema = self.db_conn.get_table_schema(self.table_name)
        
        if self.mode == 'add':
            # INSERT
            columns = []
            values = []
            params = []
            
            for col in schema:
                col_name = col['name']
                col_type = col['type'].upper()
                
                # Пропускаем AUTOINCREMENT
                if col['pk'] and 'INTEGER' in col_type:
                    continue
                
                # Проверяем наличие поля (может быть пропущено для AUTOINCREMENT)
                if col_name not in self.field_vars:
                    continue
                
                value = self.field_vars[col_name].get().strip()
                
                # Если поле пустое и NOT NULL - пропускаем (будет ошибка от БД)
                if not value and col['notnull']:
                    continue
                
                columns.append(col_name)
                values.append("?")
                
                # Преобразуем значение по типу
                if value:
                    if 'INTEGER' in col_type or 'INT' in col_type:
                        try:
                            params.append(int(value))
                        except:
                            params.append(value)
                    elif 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
                        try:
                            params.append(float(value))
                        except:
                            params.append(value)
                    else:
                        params.append(value)
                else:
                    params.append(None)
            
            query = f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({', '.join(values)})"
        else:
            # UPDATE
            pk_columns = [col['name'] for col in schema if col['pk']]
            
            if not pk_columns:
                messagebox.showerror("Ошибка", "Не найдено первичного ключа для обновления")
                return
            
            set_clauses = []
            params = []
            
            for col in schema:
                col_name = col['name']
                col_type = col['type'].upper()
                
                # Пропускаем первичный ключ
                if col_name in pk_columns:
                    continue
                
                # Проверяем наличие поля
                if col_name not in self.field_vars:
                    continue
                
                value = self.field_vars[col_name].get().strip()
                set_clauses.append(f"{col_name} = ?")
                
                # Преобразуем значение по типу
                if value:
                    if 'INTEGER' in col_type or 'INT' in col_type:
                        try:
                            params.append(int(value))
                        except:
                            params.append(value)
                    elif 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
                        try:
                            params.append(float(value))
                        except:
                            params.append(value)
                    else:
                        params.append(value)
                else:
                    params.append(None)
            
            # WHERE условие
            where_clauses = []
            for pk_col in pk_columns:
                where_clauses.append(f"{pk_col} = ?")
                params.append(self.record.get(pk_col))
            
            query = f"UPDATE {self.table_name} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
        
        # Выполняем запрос
        results, error = self.db_conn.execute_query(query, tuple(params))
        
        if error:
            messagebox.showerror("Ошибка", f"Ошибка сохранения записи:\n{error}")
        else:
            messagebox.showinfo("Успех", "Запись сохранена")
            if self.callback:
                self.callback()
            self.destroy()


def main():
    """Главная функция"""
    app = DatabaseGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()

