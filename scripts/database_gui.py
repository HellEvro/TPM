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


class DraggablePanel(ttk.LabelFrame):
    """Панель с возможностью перетаскивания, прилипания и изменения размера"""
    
    SNAP_DISTANCE = 15  # Расстояние для прилипания в пикселях
    RESIZE_BORDER = 8  # Ширина области для изменения размера в пикселях
    MIN_WIDTH = 200  # Минимальная ширина панели
    MIN_HEIGHT = 150  # Минимальная высота панели
    
    def __init__(self, parent_canvas, canvas_id, text="", **kwargs):
        super().__init__(parent_canvas, text=text, **kwargs)
        self.parent_canvas = parent_canvas
        self.canvas_id = canvas_id  # ID окна на Canvas
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_canvas_x = 0
        self.drag_start_canvas_y = 0
        self.drag_start_width = 0
        self.drag_start_height = 0
        self.is_dragging = False
        self.is_resizing = False
        self.resize_edge = None  # 'n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'
        self.all_panels = []  # Список всех панелей (обновляется извне)
        
        # Делаем заголовок перетаскиваемым и панель изменяемой по размеру
        self._make_draggable_and_resizable()
    
    def set_panels_list(self, panels):
        """Устанавливает список всех панелей для snap"""
        self.all_panels = [p for p in panels if p != self]
    
    def _make_draggable_and_resizable(self):
        """Делает панель перетаскиваемой через заголовок и изменяемой по размеру через края"""
        # Привязываем события мыши
        self.bind("<Button-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_drag_stop)
        
        # Изменяем курсор при наведении на края (для изменения размера) и заголовок
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
    
    def _get_resize_edge(self, event):
        """Определяет край, рядом с которым находится курсор"""
        width = self.winfo_width()
        height = self.winfo_height()
        x = event.x
        y = event.y
        
        # Проверяем углы
        if x < self.RESIZE_BORDER and y < self.RESIZE_BORDER:
            return 'nw'
        elif x >= width - self.RESIZE_BORDER and y < self.RESIZE_BORDER:
            return 'ne'
        elif x < self.RESIZE_BORDER and y >= height - self.RESIZE_BORDER:
            return 'sw'
        elif x >= width - self.RESIZE_BORDER and y >= height - self.RESIZE_BORDER:
            return 'se'
        # Проверяем края
        elif x < self.RESIZE_BORDER:
            return 'w'
        elif x >= width - self.RESIZE_BORDER:
            return 'e'
        elif y < self.RESIZE_BORDER:
            return 'n'
        elif y >= height - self.RESIZE_BORDER:
            return 's'
        return None
    
    def _get_cursor_for_edge(self, edge):
        """Возвращает курсор для указанного края"""
        cursors = {
            'n': 'sb_v_double_arrow',  # Север
            's': 'sb_v_double_arrow',  # Юг
            'e': 'sb_h_double_arrow',  # Восток
            'w': 'sb_h_double_arrow',  # Запад
            'ne': 'top_right_corner',  # Северо-восток
            'nw': 'top_left_corner',   # Северо-запад
            'se': 'bottom_right_corner',  # Юго-восток
            'sw': 'bottom_left_corner',   # Юго-запад
        }
        return cursors.get(edge, '')
    
    def _is_header_area(self, event):
        """Проверяет, находится ли курсор в области заголовка"""
        # Заголовок занимает примерно верхние 30 пикселей
        return event.y < 30 and event.y > self.RESIZE_BORDER
    
    def _on_motion(self, event):
        """Обработчик движения мыши"""
        # Проверяем, не меняем ли мы размер
        if self.is_resizing:
            return
        
        # Проверяем край для изменения размера
        edge = self._get_resize_edge(event)
        if edge:
            cursor = self._get_cursor_for_edge(edge)
            if cursor:
                self.config(cursor=cursor)
        elif self._is_header_area(event):
            self.config(cursor="hand2")
        else:
            self.config(cursor="")
    
    def _on_leave(self, event):
        """Обработчик выхода курсора из панели"""
        if not self.is_dragging and not self.is_resizing:
            self.config(cursor="")
    
    def _on_drag_start(self, event):
        """Начало перетаскивания или изменения размера"""
        # Проверяем, не кликнули ли мы по краю для изменения размера
        edge = self._get_resize_edge(event)
        if edge:
            # Начинаем изменение размера
            self.is_resizing = True
            self.resize_edge = edge
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root
            
            # Получаем текущие размеры и позицию
            coords = self.parent_canvas.coords(self.canvas_id)
            if coords:
                self.drag_start_canvas_x = coords[0]
                self.drag_start_canvas_y = coords[1]
            
            # Получаем текущие размеры из Canvas
            width = self.parent_canvas.itemcget(self.canvas_id, "width")
            height = self.parent_canvas.itemcget(self.canvas_id, "height")
            self.drag_start_width = int(width) if width else self.winfo_width()
            self.drag_start_height = int(height) if height else self.winfo_height()
            
            # Поднимаем панель наверх (z-order)
            self.parent_canvas.tag_raise(self.canvas_id)
            return
        
        # Если кликнули по заголовку - начинаем перетаскивание
        if not self._is_header_area(event):
            return
        
        self.is_dragging = True
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        
        # Получаем текущую позицию на Canvas
        coords = self.parent_canvas.coords(self.canvas_id)
        if coords:
            self.drag_start_canvas_x = coords[0]
            self.drag_start_canvas_y = coords[1]
        
        # Поднимаем панель наверх (z-order)
        self.parent_canvas.tag_raise(self.canvas_id)
    
    def _on_drag_motion(self, event):
        """Перетаскивание панели или изменение размера"""
        if self.is_resizing:
            # Изменяем размер
            delta_x = event.x_root - self.drag_start_x
            delta_y = event.y_root - self.drag_start_y
            
            new_width = self.drag_start_width
            new_height = self.drag_start_height
            new_x = self.drag_start_canvas_x
            new_y = self.drag_start_canvas_y
            
            # Вычисляем новые размеры и позицию в зависимости от края
            edge = self.resize_edge
            
            # Запад (лево)
            if 'w' in edge:
                new_width = max(self.MIN_WIDTH, self.drag_start_width - delta_x)
                new_x = self.drag_start_canvas_x + (self.drag_start_width - new_width)
            
            # Восток (право)
            if 'e' in edge:
                new_width = max(self.MIN_WIDTH, self.drag_start_width + delta_x)
            
            # Север (верх)
            if 'n' in edge:
                new_height = max(self.MIN_HEIGHT, self.drag_start_height - delta_y)
                new_y = self.drag_start_canvas_y + (self.drag_start_height - new_height)
            
            # Юг (низ)
            if 's' in edge:
                new_height = max(self.MIN_HEIGHT, self.drag_start_height + delta_y)
            
            # Ограничиваем размерами Canvas
            canvas_width = self.parent_canvas.winfo_width()
            canvas_height = self.parent_canvas.winfo_height()
            
            if new_x + new_width > canvas_width:
                new_width = canvas_width - new_x
            if new_y + new_height > canvas_height:
                new_height = canvas_height - new_y
            if new_x < 0:
                new_width += new_x
                new_x = 0
            if new_y < 0:
                new_height += new_y
                new_y = 0
            
            # Обновляем размер и позицию на Canvas
            self.parent_canvas.coords(self.canvas_id, new_x, new_y)
            self.parent_canvas.itemconfig(self.canvas_id, width=int(new_width), height=int(new_height))
            self.parent_canvas.update()
            
        elif self.is_dragging:
            # Перетаскиваем панель
            delta_x = event.x_root - self.drag_start_x
            delta_y = event.y_root - self.drag_start_y
            
            new_x = self.drag_start_canvas_x + delta_x
            new_y = self.drag_start_canvas_y + delta_y
            
            # Проверяем прилипание к другим панелям
            snap_x, snap_y = self._check_snap(new_x, new_y)
            
            # Ограничиваем перемещение границами Canvas
            canvas_width = self.parent_canvas.winfo_width()
            canvas_height = self.parent_canvas.winfo_height()
            widget_width = self.winfo_width()
            widget_height = self.winfo_height()
            
            snap_x = max(0, min(snap_x, max(0, canvas_width - widget_width)))
            snap_y = max(0, min(snap_y, max(0, canvas_height - widget_height)))
            
            # Перемещаем панель на Canvas
            self.parent_canvas.coords(self.canvas_id, snap_x, snap_y)
            self.parent_canvas.update()
    
    def _on_drag_stop(self, event):
        """Окончание перетаскивания или изменения размера"""
        if self.is_resizing:
            self.is_resizing = False
            self.resize_edge = None
            self.config(cursor="")
            # Обновляем scrollregion
            self.parent_canvas.config(scrollregion=self.parent_canvas.bbox("all"))
        elif self.is_dragging:
            self.is_dragging = False
            self.config(cursor="")
            # Обновляем scrollregion
            self.parent_canvas.config(scrollregion=self.parent_canvas.bbox("all"))
    
    def _check_snap(self, x, y):
        """Проверяет прилипание к другим панелям"""
        snap_x, snap_y = x, y
        widget_width = self.winfo_width()
        widget_height = self.winfo_height()
        
        # Проверяем прилипание к каждой панели
        for panel in self.all_panels:
            # Получаем позицию панели на Canvas
            coords = self.parent_canvas.coords(panel.canvas_id)
            if not coords:
                continue
            
            px, py = coords
            pw = panel.winfo_width()
            ph = panel.winfo_height()
            
            # Проверяем прилипание слева (к правой стороне другой панели)
            if abs(x - (px + pw)) < self.SNAP_DISTANCE:
                snap_x = px + pw
            
            # Проверяем прилипание справа (к левой стороне другой панели)
            if abs((x + widget_width) - px) < self.SNAP_DISTANCE:
                snap_x = px - widget_width
            
            # Проверяем прилипание сверху (к нижней стороне другой панели)
            if abs(y - (py + ph)) < self.SNAP_DISTANCE:
                snap_y = py + ph
            
            # Проверяем прилипание снизу (к верхней стороне другой панели)
            if abs((y + widget_height) - py) < self.SNAP_DISTANCE:
                snap_y = py - widget_height
            
            # Проверяем прилипание по горизонтали (выравнивание левого края)
            if abs(x - px) < self.SNAP_DISTANCE:
                snap_x = px
            
            # Проверяем прилипание по вертикали (выравнивание верхнего края)
            if abs(y - py) < self.SNAP_DISTANCE:
                snap_y = py
        
        return snap_x, snap_y


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
            # Ошибка подключения будет обработана в вызывающем коде
            raise
    
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
        self.search_var = tk.StringVar()
        
        # Хранилище всех загруженных данных для фильтрации
        self.all_table_data: List[Dict] = []
        self.all_table_columns: List[str] = []
        
        # Создаем интерфейс
        self._build_ui()
        
        # Автоматически находим и загружаем БД из проекта
        self._auto_discover_databases()
    
    def _build_ui(self):
        """Создает интерфейс приложения"""
        # Главный контейнер - Canvas для перетаскиваемых панелей
        main_container = tk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Создаем Canvas для размещения панелей
        self.main_canvas = tk.Canvas(main_container, bg='SystemButtonFace', highlightthickness=0)
        self.main_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Хранилище панелей
        self.panels = {}
        
        # === ЛЕВАЯ ПАНЕЛЬ: Управление БД ===
        left_frame_container = ttk.Frame(self.main_canvas)
        left_frame = DraggablePanel(left_frame_container, None, text="Базы данных")
        left_frame.pack(fill=tk.BOTH, expand=True)
        
        # Размещаем панель на Canvas
        left_id = self.main_canvas.create_window(10, 10, window=left_frame_container, anchor="nw", width=300, height=600)
        left_frame.canvas_id = left_id
        left_frame.parent_canvas = self.main_canvas
        
        # Убираем заголовок - он уже есть в DraggablePanel
        
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
        
        self.panels['left'] = left_frame
        
        # === ПАНЕЛЬ: SQL редактор ===
        sql_frame_container = ttk.Frame(self.main_canvas)
        sql_frame = DraggablePanel(sql_frame_container, None, text="SQL Редактор")
        sql_frame.pack(fill=tk.BOTH, expand=True)
        
        sql_id = self.main_canvas.create_window(320, 10, window=sql_frame_container, anchor="nw", width=600, height=300)
        sql_frame.canvas_id = sql_id
        sql_frame.parent_canvas = self.main_canvas
        
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
        
        self.panels['sql'] = sql_frame
        
        # === ПАНЕЛЬ: Таблицы и данные ===
        tables_frame_container = ttk.Frame(self.main_canvas)
        tables_frame = DraggablePanel(tables_frame_container, None, text="Таблицы и данные")
        tables_frame.pack(fill=tk.BOTH, expand=True)
        
        tables_id = self.main_canvas.create_window(320, 320, window=tables_frame_container, anchor="nw", width=600, height=400)
        tables_frame.canvas_id = tables_id
        tables_frame.parent_canvas = self.main_canvas
        
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
        
        # Поиск/фильтр
        search_frame = ttk.Frame(tables_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT, padx=2)
        search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            width=30
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Привязываем поиск при вводе
        self.search_var.trace_add('write', lambda *args: self._filter_table_data())
        
        ttk.Button(
            search_frame,
            text="Очистить",
            command=self._clear_search
        ).pack(side=tk.LEFT, padx=2)
        
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
        
        self.panels['tables'] = tables_frame
        
        # === ПАНЕЛЬ: Результаты SQL ===
        results_frame_container = ttk.Frame(self.main_canvas)
        results_frame = DraggablePanel(results_frame_container, None, text="Результаты SQL")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        results_id = self.main_canvas.create_window(930, 320, window=results_frame_container, anchor="nw", width=400, height=400)
        results_frame.canvas_id = results_id
        results_frame.parent_canvas = self.main_canvas
        
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
        
        self.panels['results'] = results_frame
        
        # Обновляем размер Canvas при изменении окна
        def update_canvas_size(event=None):
            self.main_canvas.config(scrollregion=self.main_canvas.bbox("all"))
        
        self.main_canvas.bind('<Configure>', update_canvas_size)
        self.bind('<Configure>', update_canvas_size)
        
        # Обновляем список панелей для snap
        panels_list = list(self.panels.values())
        for panel in panels_list:
            panel.set_panels_list(panels_list)
        
        # Обновляем scrollregion при изменении размера
        def update_scrollregion(event=None):
            self.main_canvas.config(scrollregion=self.main_canvas.bbox("all"))
        
        self.main_canvas.bind('<Configure>', update_scrollregion)
        self.bind('<Configure>', update_scrollregion)
        
        # === СТРОКА СТАТУСА ВНИЗУ ===
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        
        status_label = ttk.Label(
            status_frame,
            text="Готов к работе",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=5
        )
        status_label.pack(fill=tk.X)
        self.status_label = status_label
    
    def _update_status(self, message: str, status_type: str = "info"):
        """
        Обновляет строку статуса
        
        Args:
            message: Текст сообщения
            status_type: Тип статуса - "info", "success", "warning", "error"
        """
        self.status_label.config(text=message)
        
        # Цвета для разных типов статуса
        colors = {
            "info": "SystemButtonFace",
            "success": "#d4edda",  # Светло-зеленый
            "warning": "#fff3cd",  # Светло-желтый
            "error": "#f8d7da"     # Светло-красный
        }
        
        bg_color = colors.get(status_type, "SystemButtonFace")
        self.status_label.config(background=bg_color)
        
        # Автоматически очищаем статус через 5 секунд (кроме ошибок)
        if status_type != "error":
            self.after(5000, lambda: self.status_label.config(text="Готов к работе", background="SystemButtonFace"))
    
    def _auto_discover_databases(self):
        """Автоматически находит все БД в проекте"""
        databases = []
        found_paths = set()  # Для отслеживания уже добавленных путей
        
        # Список известных путей к БД (показываем даже если файлы еще не созданы)
        known_paths = [
            ROOT / "data" / "bots_data.db",
            ROOT / "data" / "app_data.db",
            ROOT / "data" / "ai_data.db",
            ROOT / "license_generator" / "licenses.db",
        ]
        
        # Добавляем известные пути
        for db_path in known_paths:
            if db_path.exists():
                found_paths.add(str(db_path))
                databases.append({
                    'name': db_path.name,
                    'path': str(db_path),
                    'relative_path': str(db_path.relative_to(ROOT)),
                    'size': db_path.stat().st_size,
                    'exists': True
                })
            else:
                # Добавляем даже если файл не существует (с пометкой)
                databases.append({
                    'name': db_path.name,
                    'path': str(db_path),
                    'relative_path': str(db_path.relative_to(ROOT)),
                    'size': 0,
                    'exists': False
                })
        
        # Добавляем все .db файлы из проекта (кроме уже добавленных)
        # Исключаем служебные папки
        excluded_dirs = {'.git', '.venv', '__pycache__', 'node_modules', '.idea', '.vscode'}
        
        for db_file in ROOT.rglob("*.db"):
            # Пропускаем файлы .db-wal и .db-shm
            if db_file.name.endswith(('-wal', '-shm')):
                continue
            
            # Пропускаем если путь уже добавлен
            db_path_str = str(db_file)
            if db_path_str in found_paths:
                continue
            
            # Пропускаем если в пути есть исключенные директории
            if any(excluded in db_path_str for excluded in excluded_dirs):
                continue
            
            found_paths.add(db_path_str)
            databases.append({
                'name': db_file.name,
                'path': db_path_str,
                'relative_path': str(db_file.relative_to(ROOT)),
                'size': db_file.stat().st_size if db_file.exists() else 0,
                'exists': db_file.exists()
            })
        
        # Сортируем: сначала существующие, затем по имени
        databases.sort(key=lambda x: (not x.get('exists', True), x['name']))
        
        # Обновляем дерево БД
        self._update_database_tree(databases)
        
        # Обновляем статус (если метод вызван не из __init__)
        if hasattr(self, 'status_label'):
            count = len([db for db in databases if db.get('exists', True)])
            total = len(databases)
            self._update_status(f"Найдено баз данных: {count} существующих из {total} известных", "info")
    
    def _update_database_tree(self, databases: List[Dict]):
        """Обновляет дерево со списком БД"""
        # Очищаем дерево
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
        
        # Добавляем БД в дерево
        root_id = self.db_tree.insert("", tk.END, text="Проект", open=True)
        
        for db in databases:
            exists = db.get('exists', True)
            if exists:
                size_mb = db['size'] / 1024 / 1024
                display_text = f"{db['name']} ({size_mb:.2f} MB)"
            else:
                display_text = f"{db['name']} (не создана)"
            
            item_id = self.db_tree.insert(
                root_id,
                tk.END,
                text=display_text,
                values=(db['path'], db['relative_path'], '1' if exists else '0')
            )
            
            # Визуально выделяем несуществующие файлы (серым цветом)
            if not exists:
                self.db_tree.set(item_id, 'exists', '0')
    
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
        self._update_status("Выбор базы данных...", "info")
        db_path = filedialog.askopenfilename(
            title="Выберите базу данных",
            filetypes=[("SQLite databases", "*.db"), ("All files", "*.*")]
        )
        
        if db_path:
            self._open_database(db_path)
            # Добавляем в дерево
            self._refresh_databases()
        else:
            self._update_status("Выбор базы данных отменен", "info")
    
    def _open_database(self, db_path: str):
        """Открывает базу данных"""
        # Проверяем существование файла
        if not os.path.exists(db_path):
            if messagebox.askyesno(
                "База данных не найдена",
                f"Файл базы данных не существует:\n{db_path}\n\nСоздать новую базу данных?"
            ):
                # Создаем директорию если её нет
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                # Создаем пустую БД
                try:
                    conn = sqlite3.connect(db_path)
                    conn.close()
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось создать базу данных:\n{e}")
                    return
            else:
                return
        
        # Закрываем текущее подключение
        if self.db_conn:
            self.db_conn.disconnect()
        
        # Создаем новое подключение
        try:
            self.db_conn = DatabaseConnection(db_path)
            self.db_conn.connect()
        except Exception as e:
            self._update_status(f"Ошибка подключения: {e}", "error")
            self.db_conn = None
            return
        
        self.db_path_var.set(db_path)
        
        # Обновляем информацию о БД
        self._update_database_info()
        
        # Загружаем список таблиц
        self._load_tables_list()
        
        # Обновляем статус
        db_name = os.path.basename(db_path)
        self._update_status(f"База данных открыта: {db_name}", "success")
        
        # Обновляем список БД (чтобы обновился статус "не создана" -> "существует")
        self._auto_discover_databases()
    
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
        
        self._update_status("Загрузка списка таблиц...", "info")
        tables = self.db_conn.get_tables()
        self.tables_combo['values'] = tables
        
        if tables:
            self.tables_combo.current(0)
            self.current_table = tables[0]
            self._update_status(f"Найдено таблиц: {len(tables)}", "success")
            self._load_table_data()
        else:
            self._update_status("База данных не содержит таблиц", "warning")
    
    def _load_table_data(self):
        """Загружает данные из выбранной таблицы"""
        if not self.db_conn:
            return
        
        table_name = self.table_var.get()
        if not table_name:
            return
        
        self.current_table = table_name
        
        # Обновляем статус
        self._update_status(f"Загрузка данных из таблицы '{table_name}'...", "info")
        
        # Очищаем treeview
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        
        # Получаем схему таблицы
        schema = self.db_conn.get_table_schema(table_name)
        if not schema:
            self._update_status(f"Ошибка: Не удалось получить схему таблицы '{table_name}'", "error")
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
        
        # Сохраняем все данные для фильтрации
        self.all_table_data = rows
        self.all_table_columns = columns
        
        # Очищаем фильтр при загрузке новой таблицы
        self.search_var.set("")
        
        # Отображаем данные (с учетом текущего фильтра)
        self._display_filtered_data()
        
        # Обновляем статус
        self._update_status(f"Загружено {len(rows)} записей из таблицы '{table_name}' (всего: {total_count})", "success")
    
    def _filter_table_data(self):
        """Фильтрует данные таблицы по поисковому запросу"""
        if not self.all_table_data or not self.all_table_columns:
            return
        
        self._display_filtered_data()
    
    def _display_filtered_data(self):
        """Отображает отфильтрованные данные в таблице"""
        # Очищаем treeview
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        
        if not self.all_table_data or not self.all_table_columns:
            self.records_info.config(text="Записей: 0")
            return
        
        # Получаем поисковый запрос
        search_text = self.search_var.get().strip().lower()
        
        # Фильтруем данные
        if search_text:
            filtered_rows = []
            for row in self.all_table_data:
                # Проверяем, содержится ли поисковый запрос в любой из колонок
                match = False
                for col in self.all_table_columns:
                    value = str(row.get(col, '')).lower()
                    if search_text in value:
                        match = True
                        break
                
                if match:
                    filtered_rows.append(row)
        else:
            # Если поисковый запрос пуст, показываем все данные
            filtered_rows = self.all_table_data
        
        # Добавляем отфильтрованные данные
        for row in filtered_rows:
            values = [str(row.get(col, '')) for col in self.all_table_columns]
            self.data_tree.insert("", tk.END, values=values)
        
        # Обновляем информацию о записях
        total_count = len(self.all_table_data)
        shown_count = len(filtered_rows)
        if search_text:
            self.records_info.config(text=f"Записей: {total_count} (найдено: {shown_count})")
        else:
            self.records_info.config(text=f"Записей: {total_count} (показано: {shown_count})")
    
    def _clear_search(self):
        """Очищает поле поиска"""
        self.search_var.set("")
        self._display_filtered_data()
    
    def _execute_sql(self):
        """Выполняет SQL запрос"""
        if not self.db_conn:
            self._update_status("Ошибка: База данных не открыта", "error")
            return
        
        query = self.sql_text.get(1.0, tk.END).strip()
        if not query:
            self._update_status("Предупреждение: SQL запрос пуст", "warning")
            return
        
        # Обновляем статус
        self._update_status("Выполнение SQL запроса...", "info")
        
        # Выполняем запрос
        results, error = self.db_conn.execute_query(query)
        
        if error:
            self._update_status(f"Ошибка SQL: {error}", "error")
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
            
            self._update_status(f"Запрос выполнен. Найдено записей: {len(results)}", "success")
        else:
            self._update_status("Запрос выполнен успешно", "success")
            # Обновляем данные таблицы, если была выбрана таблица
            if self.current_table:
                self._load_table_data()
    
    def _add_record(self):
        """Открывает диалог для добавления новой записи"""
        if not self.db_conn or not self.current_table:
            self._update_status("Предупреждение: Выберите таблицу", "warning")
            return
        
        self._update_status("Открытие диалога добавления записи...", "info")
        RecordDialog(self, self.db_conn, self.current_table, mode='add', callback=self._load_table_data)
    
    def _edit_record(self):
        """Открывает диалог для редактирования записи"""
        if not self.db_conn or not self.current_table:
            self._update_status("Предупреждение: Выберите таблицу", "warning")
            return
        
        selection = self.data_tree.selection()
        if not selection:
            self._update_status("Предупреждение: Выберите запись для редактирования", "warning")
            return
        
        # Получаем данные выбранной записи
        item = selection[0]
        values = self.data_tree.item(item, "values")
        columns = self.data_tree['columns']
        
        record = {col: values[i] for i, col in enumerate(columns)}
        
        self._update_status("Открытие диалога редактирования записи...", "info")
        RecordDialog(self, self.db_conn, self.current_table, mode='edit', record=record, callback=self._load_table_data)
    
    def _delete_record(self):
        """Удаляет выбранную запись"""
        if not self.db_conn or not self.current_table:
            self._update_status("Предупреждение: Выберите таблицу", "warning")
            return
        
        selection = self.data_tree.selection()
        if not selection:
            self._update_status("Предупреждение: Выберите запись для удаления", "warning")
            return
        
        # Подтверждение
        if not messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить эту запись?"):
            self._update_status("Удаление отменено", "info")
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
            self._update_status(f"Ошибка удаления записи: {error}", "error")
        else:
            self._update_status("Запись удалена", "success")
            self._load_table_data()
    
    def _refresh_databases(self):
        """Обновляет список БД"""
        self._update_status("Поиск баз данных...", "info")
        self._auto_discover_databases()
        self._update_status("Список баз данных обновлен", "success")
    
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
            # Обновляем статус в родительском окне
            if self.callback:
                parent = self.master
                if hasattr(parent, '_update_status'):
                    parent._update_status("Запись сохранена", "success")
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

