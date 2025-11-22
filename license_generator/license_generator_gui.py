#!/usr/bin/env python3
"""
GUI приложение для генерации лицензий InfoBot AI Premium
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from tkinter import ttk, messagebox, filedialog, simpledialog
import tkinter as tk

# Добавляем путь к license_generator для импортов
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from license_manager import LicenseManager
from license_database import LicenseDatabase
from hardware_id import get_hardware_id, get_short_hardware_id
from license_types import LicenseFeatures


class LicenseGeneratorGUI(tk.Tk):
    """Главное окно генератора лицензий"""
    
    def __init__(self):
        super().__init__()
        
        self.title("InfoBot License Generator")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # Инициализация компонентов
        self.license_manager = LicenseManager()
        self.database = LicenseDatabase()
        
        # Переменные для формы
        self.hw_id_var = tk.StringVar()
        self.license_type_var = tk.StringVar(value="premium")
        self.days_var = tk.StringVar(value="30")
        self.start_date_var = tk.StringVar()
        self.comments_var = tk.StringVar()
        self.recipient_var = tk.StringVar()
        self.developer_mode_var = tk.BooleanVar(value=False)
        
        # Создаем интерфейс
        self._build_ui()
        
        # Загружаем список получателей
        self._refresh_recipients_list()
    
    def _build_ui(self):
        """Создает интерфейс приложения"""
        # Главный контейнер с прокруткой
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === СЕКЦИЯ 1: Генерация лицензии ===
        gen_frame = ttk.LabelFrame(main_frame, text="Генерация лицензии", padding=10)
        gen_frame.pack(fill=tk.X, pady=(0, 10))
        gen_frame.columnconfigure(1, weight=1)
        
        # Контактная информация получателя
        ttk.Label(gen_frame, text="Контакт получателя:").grid(row=0, column=0, sticky="w", pady=5)
        recipient_entry = ttk.Entry(gen_frame, textvariable=self.recipient_var, width=40)
        recipient_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(gen_frame, text="(email, telegram, и т.д.)").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        # Тип лицензии
        ttk.Label(gen_frame, text="Тип лицензии:").grid(row=1, column=0, sticky="w", pady=5)
        license_type_frame = ttk.Frame(gen_frame)
        license_type_frame.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        license_type_combo = ttk.Combobox(license_type_frame, textvariable=self.license_type_var, 
                                         values=["premium", "trial", "monthly", "yearly", "lifetime", "developer"],
                                         state="readonly", width=20)
        license_type_combo.grid(row=0, column=0, sticky="w")
        license_type_combo.bind("<<ComboboxSelected>>", self._on_license_type_change)
        self.license_type_combo = license_type_combo  # Сохраняем ссылку
        
        # Чекбокс для developer режима (автоматически отключает HWID)
        developer_check = ttk.Checkbutton(license_type_frame, text="Developer (без привязки к HWID)", 
                                         variable=self.developer_mode_var,
                                         command=self._on_developer_mode_change)
        developer_check.grid(row=0, column=1, padx=(10, 0), sticky="w")
        
        # Описание типа лицензии
        ttk.Label(gen_frame, text="Описание:").grid(row=2, column=0, sticky="nw", pady=5)
        description_frame = ttk.Frame(gen_frame)
        description_frame.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        description_frame.columnconfigure(0, weight=1)
        
        # Текстовое поле для описания (readonly, многострочное)
        description_text = tk.Text(description_frame, height=4, width=60, wrap=tk.WORD, 
                                   state=tk.DISABLED, bg="#f5f5f5", relief=tk.FLAT, 
                                   font=("TkDefaultFont", 9))
        description_text.grid(row=0, column=0, sticky="ew")
        self.description_text = description_text  # Сохраняем ссылку
        
        # Обновляем описание при загрузке (для premium по умолчанию)
        self._update_license_description()
        
        # Hardware ID
        ttk.Label(gen_frame, text="Hardware ID:").grid(row=3, column=0, sticky="w", pady=5)
        hw_frame = ttk.Frame(gen_frame)
        hw_frame.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        hw_frame.columnconfigure(0, weight=1)
        
        hw_entry = ttk.Entry(hw_frame, textvariable=self.hw_id_var, width=40)
        hw_entry.grid(row=0, column=0, sticky="ew")
        self.hw_entry = hw_entry  # Сохраняем ссылку для изменения состояния
        
        btn_get_hwid = ttk.Button(hw_frame, text="Получить HWID", command=self._get_current_hwid)
        btn_get_hwid.grid(row=0, column=1, padx=(5, 0))
        
        # Количество дней
        ttk.Label(gen_frame, text="Количество дней:").grid(row=4, column=0, sticky="w", pady=5)
        days_entry = ttk.Entry(gen_frame, textvariable=self.days_var, width=40)
        days_entry.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        
        # Дата начала (опционально)
        ttk.Label(gen_frame, text="Дата начала (опционально):").grid(row=5, column=0, sticky="w", pady=5)
        date_frame = ttk.Frame(gen_frame)
        date_frame.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        
        start_date_entry = ttk.Entry(date_frame, textvariable=self.start_date_var, width=20)
        start_date_entry.grid(row=0, column=0)
        ttk.Label(date_frame, text="(формат: YYYY-MM-DD, если не указано - текущая дата + 1 день)").grid(row=0, column=1, padx=(5, 0), sticky="w")
        
        # Комментарии
        ttk.Label(gen_frame, text="Комментарии:").grid(row=6, column=0, sticky="nw", pady=5)
        comments_text = tk.Text(gen_frame, height=3, width=40)
        comments_text.grid(row=6, column=1, sticky="ew", padx=5, pady=5)
        self.comments_text = comments_text
        
        # Кнопка генерации
        btn_generate = ttk.Button(gen_frame, text="Сгенерировать лицензию", command=self._generate_license)
        btn_generate.grid(row=7, column=0, columnspan=2, pady=10)
        
        # === СЕКЦИЯ 2: Список получателей ===
        recipients_frame = ttk.LabelFrame(main_frame, text="База данных получателей", padding=10)
        recipients_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        recipients_frame.columnconfigure(0, weight=1)
        recipients_frame.rowconfigure(0, weight=1)
        
        # Таблица получателей
        columns = ("ID", "HWID", "Дни", "Начало", "Окончание", "Контакт", "Комментарии", "Файл")
        tree = ttk.Treeview(recipients_frame, columns=columns, show="headings", height=10)
        
        # Настройка колонок
        tree.heading("ID", text="ID")
        tree.heading("HWID", text="Hardware ID")
        tree.heading("Дни", text="Дни")
        tree.heading("Начало", text="Дата начала")
        tree.heading("Окончание", text="Дата окончания")
        tree.heading("Контакт", text="Контакт")
        tree.heading("Комментарии", text="Комментарии")
        tree.heading("Файл", text="Файл лицензии")
        
        tree.column("ID", width=50)
        tree.column("HWID", width=150)
        tree.column("Дни", width=60)
        tree.column("Начало", width=120)
        tree.column("Окончание", width=120)
        tree.column("Контакт", width=150)
        tree.column("Комментарии", width=200)
        tree.column("Файл", width=150)
        
        # Прокрутка для таблицы
        scrollbar = ttk.Scrollbar(recipients_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.recipients_tree = tree
        
        # Кнопки управления
        buttons_frame = ttk.Frame(recipients_frame)
        buttons_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(buttons_frame, text="Обновить список", command=self._refresh_recipients_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Продлить лицензию", command=self._extend_license).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Удалить выбранное", command=self._delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Поиск по HWID", command=self._search_by_hwid).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Открыть папку с лицензиями", command=self._open_licenses_folder).pack(side=tk.LEFT, padx=5)
    
    def _get_license_description(self, license_type: str) -> str:
        """Получает описание типа лицензии"""
        features = LicenseFeatures.get_features(license_type)
        price = LicenseFeatures.get_price(license_type)
        
        descriptions = {
            'trial': (
                "🧪 ПРОБНАЯ ВЕРСИЯ (TRIAL)\n\n"
                "✅ Доступно:\n"
                "  • Обнаружение аномалий\n\n"
                "❌ Недоступно:\n"
                "  • LSTM предсказания\n"
                "  • Распознавание паттернов\n"
                "  • Динамический риск\n"
                "  • Автообучение\n\n"
                "📊 Ограничения:\n"
                "  • Максимум 3 бота\n"
                "  • Срок: 7 дней\n\n"
                "💰 Цена: Бесплатно"
            ),
            'premium': (
                "⭐ ПРЕМИУМ (PREMIUM)\n\n"
                "✅ Все функции включены\n\n"
                "📊 Количество дней указывается вручную\n\n"
                "💡 Выберите конкретный тип лицензии для детальной информации"
            ),
            'monthly': (
                "📅 МЕСЯЧНАЯ ПОДПИСКА (MONTHLY)\n\n"
                "✅ Доступно:\n"
                "  • Все функции AI\n"
                "  • LSTM предсказания\n"
                "  • Распознавание паттернов\n"
                "  • Динамический риск\n"
                "  • Автообучение\n\n"
                "📊 Ограничения:\n"
                "  • Максимум 20 ботов\n"
                "  • По умолчанию: 30 дней (можно указать любое)\n\n"
                "💰 Цена: $29.99/месяц"
            ),
            'yearly': (
                "📆 ГОДОВАЯ ПОДПИСКА (YEARLY)\n\n"
                "✅ Доступно:\n"
                "  • Все функции AI\n"
                "  • LSTM предсказания\n"
                "  • Распознавание паттернов\n"
                "  • Динамический риск\n"
                "  • Автообучение\n\n"
                "📊 Ограничения:\n"
                "  • Максимум 50 ботов\n"
                "  • По умолчанию: 365 дней (можно указать любое)\n\n"
                "💰 Цена: $299.00/год (скидка 16%)"
            ),
            'lifetime': (
                "♾️ ПОЖИЗНЕННАЯ ЛИЦЕНЗИЯ (LIFETIME)\n\n"
                "✅ Доступно:\n"
                "  • Все функции AI\n"
                "  • LSTM предсказания\n"
                "  • Распознавание паттернов\n"
                "  • Динамический риск\n"
                "  • Автообучение\n\n"
                "📊 Ограничения:\n"
                "  • Максимум 999 ботов (практически без ограничений)\n"
                "  • По умолчанию: ~274 года (можно указать любое)\n\n"
                "🎁 Бонусы:\n"
                "  • Приоритетная поддержка\n"
                "  • Ранний доступ к новым функциям\n\n"
                "💰 Цена: $999.00"
            ),
            'developer': (
                "👨‍💻 ДЛЯ РАЗРАБОТЧИКОВ (DEVELOPER)\n\n"
                "✅ Доступно:\n"
                "  • Все функции AI\n"
                "  • LSTM предсказания\n"
                "  • Распознавание паттернов\n"
                "  • Динамический риск\n"
                "  • Автообучение\n\n"
                "📊 Ограничения:\n"
                "  • Максимум 999 ботов\n"
                "  • По умолчанию: ~274 года (можно указать любое)\n\n"
                "🔓 Специальные возможности:\n"
                "  • Отладочный режим\n"
                "  • БЕЗ привязки к HWID (работает на любом ПК)\n"
                "  • Неограниченные активации\n\n"
                "💰 Цена: Бесплатно (для разработчиков)"
            )
        }
        
        return descriptions.get(license_type, descriptions['premium'])
    
    def _update_license_description(self):
        """Обновляет описание выбранного типа лицензии"""
        license_type = self.license_type_var.get()
        if self.developer_mode_var.get():
            license_type = "developer"
        
        description = self._get_license_description(license_type)
        
        self.description_text.config(state=tk.NORMAL)
        self.description_text.delete("1.0", tk.END)
        self.description_text.insert("1.0", description)
        self.description_text.config(state=tk.DISABLED)
    
    def _on_license_type_change(self, event=None):
        """Обработчик изменения типа лицензии"""
        license_type = self.license_type_var.get()
        if license_type == "developer":
            # Для developer автоматически включаем режим без HWID
            self.developer_mode_var.set(True)
            self._on_developer_mode_change()
        else:
            # Для других типов можно включить HWID
            if not self.developer_mode_var.get():
                self.hw_entry.config(state="normal")
        
        # Обновляем описание
        self._update_license_description()
    
    def _on_developer_mode_change(self):
        """Обработчик изменения developer режима"""
        if self.developer_mode_var.get():
            # Отключаем поле HWID и очищаем его
            self.hw_entry.config(state="disabled")
            self.hw_id_var.set("")
            self.license_type_var.set("developer")
            # НЕ меняем количество дней автоматически - пользователь может указать любое
            # Обновляем описание
            self._update_license_description()
        else:
            # Включаем поле HWID
            self.hw_entry.config(state="normal")
            if self.license_type_var.get() == "developer":
                self.license_type_var.set("premium")
            # Обновляем описание
            self._update_license_description()
    
    def _get_current_hwid(self):
        """Получает Hardware ID текущего компьютера"""
        if self.developer_mode_var.get():
            messagebox.showwarning("Developer режим", 
                                 "В developer режиме HWID не требуется.\n"
                                 "Лицензия будет работать на любом оборудовании.")
            return
        
        try:
            # Используем короткий ID (первые 16 символов) для совместимости с проверкой лицензий
            short_hw_id = get_short_hardware_id()
            full_hw_id = get_hardware_id()
            self.hw_id_var.set(short_hw_id)
            messagebox.showinfo("Hardware ID", 
                               f"Short HWID (используется для лицензий):\n{short_hw_id}\n\n"
                               f"Full HWID:\n{full_hw_id}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось получить Hardware ID:\n{str(e)}")
    
    def _parse_start_date(self) -> datetime:
        """Парсит дату начала из поля ввода"""
        start_date_str = self.start_date_var.get().strip()
        
        if not start_date_str:
            return None
        
        try:
            # Пробуем разные форматы
            for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(start_date_str, fmt)
                except ValueError:
                    continue
            raise ValueError("Неверный формат даты")
        except Exception as e:
            raise ValueError(f"Ошибка парсинга даты: {str(e)}")
    
    def _generate_license(self):
        """Генерирует лицензию"""
        try:
            # Определяем тип лицензии
            license_type = self.license_type_var.get()
            if self.developer_mode_var.get():
                license_type = "developer"
            
            # Для developer лицензий HWID не требуется
            hw_id = self.hw_id_var.get().strip().upper() if not self.developer_mode_var.get() else None
            
            if not hw_id and not self.developer_mode_var.get() and license_type != "developer":
                messagebox.showerror("Ошибка", "Укажите Hardware ID или выберите Developer режим")
                return
            
            # Нормализуем HWID: берем только первые 16 символов для совместимости с проверкой лицензий
            # (при проверке сравниваются только первые 16 символов)
            # Только если HWID указан (не developer лицензия)
            if hw_id:
                if len(hw_id) > 16:
                    hw_id = hw_id[:16]
                    messagebox.showinfo("Информация", 
                                       f"HWID обрезан до 16 символов для совместимости:\n{hw_id}")
                elif len(hw_id) < 16:
                    messagebox.showwarning("Предупреждение", 
                                          f"HWID короче 16 символов. Убедитесь, что это правильный ID.\n"
                                          f"Текущий HWID: {hw_id}")
            
            try:
                days = int(self.days_var.get().strip())
                if days <= 0:
                    raise ValueError("Количество дней должно быть положительным")
            except ValueError as e:
                messagebox.showerror("Ошибка", f"Неверное количество дней: {str(e)}")
                return
            
            recipient = self.recipient_var.get().strip()
            # Email для генерации license_id
            if license_type == "developer":
                email = 'developer@infobot.local'
            else:
                email = recipient if recipient and '@' in recipient else 'customer@example.com'
            
            # Парсим дату начала
            start_date = None
            try:
                start_date = self._parse_start_date()
            except ValueError as e:
                messagebox.showerror("Ошибка", str(e))
                return
            
            # Получаем комментарии
            comments = self.comments_text.get("1.0", tk.END).strip()
            
            # Генерируем лицензию
            license_data = self.license_manager.generate_license(
                user_email=email,
                license_type=license_type,
                hardware_id=hw_id,  # None для developer лицензий
                custom_duration_days=days,
                start_date=start_date
            )
            
            # Сохраняем файл лицензии
            output_dir = Path(script_dir) / 'generated_licenses'
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Для developer лицензий используем специальное имя
            hw_prefix = hw_id[:16] if hw_id else "UNIVERSAL"
            filename = f"{hw_prefix}_{license_type}_{days}days_{timestamp}.lic"
            license_path = output_dir / filename
            
            with open(license_path, 'wb') as f:
                f.write(license_data['encrypted_license'])
            
            # Вычисляем дату окончания для базы данных
            if start_date is None:
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            else:
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            end_date = start_date + timedelta(days=days + 1)
            end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Сохраняем в базу данных
            recipient_id = self.database.add_recipient(
                hw_id=hw_id,
                days=days,
                start_date=start_date,
                end_date=end_date,
                recipient=recipient if recipient else None,
                comments=comments if comments else None,
                license_file=str(license_path)
            )
            
            # Показываем результат
            expires_at = license_data['license_data']['expires_at']
            hw_id_display = hw_id if hw_id else "NONE (универсальная лицензия)"
            message = (
                f"Лицензия успешно сгенерирована!\n\n"
                f"Тип лицензии: {license_type}\n"
                f"Hardware ID: {hw_id_display}\n"
                f"Длительность: {days} дней\n"
                f"Дата начала: {start_date.strftime('%Y-%m-%d') if start_date else 'завтра'}\n"
                f"Дата окончания: {expires_at}\n"
                f"Файл: {license_path}\n\n"
                f"Запись добавлена в базу данных (ID: {recipient_id})"
            )
            messagebox.showinfo("Успех", message)
            
            # Обновляем список
            self._refresh_recipients_list()
            
            # Очищаем форму (опционально)
            if messagebox.askyesno("Очистить форму", "Очистить форму для следующей лицензии?"):
                self.hw_id_var.set("")
                # НЕ сбрасываем количество дней - оставляем пользовательское значение
                # self.days_var.set("30")
                self.start_date_var.set("")
                self.recipient_var.set("")
                self.comments_text.delete("1.0", tk.END)
        
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сгенерировать лицензию:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def _refresh_recipients_list(self):
        """Обновляет список получателей в таблице"""
        # Очищаем таблицу
        for item in self.recipients_tree.get_children():
            self.recipients_tree.delete(item)
        
        # Загружаем данные из базы
        recipients = self.database.get_all_recipients()
        
        for recipient in recipients:
            # Форматируем даты для отображения
            start_date = recipient.get('start_date', '')
            if start_date:
                try:
                    dt = datetime.fromisoformat(start_date)
                    start_date = dt.strftime('%Y-%m-%d')
                except:
                    pass
            
            end_date = recipient.get('end_date', '')
            if end_date:
                try:
                    dt = datetime.fromisoformat(end_date)
                    end_date = dt.strftime('%Y-%m-%d')
                except:
                    pass
            
            # Обрезаем комментарии и путь к файлу для отображения
            contact = recipient.get('recipient', '') or ''
            if len(contact) > 20:
                contact = contact[:20] + "..."
            
            comments = recipient.get('comments', '') or ''
            if len(comments) > 30:
                comments = comments[:30] + "..."
            
            license_file = recipient.get('license_file', '') or ''
            if license_file:
                license_file = Path(license_file).name
            
            # Обрабатываем hw_id (может быть None для developer лицензий)
            hw_id_display = recipient.get('hw_id') or 'NONE (developer)'
            if hw_id_display and hw_id_display != 'NONE (developer)':
                if len(hw_id_display) > 20:
                    hw_id_display = hw_id_display[:20] + "..."
            
            self.recipients_tree.insert("", tk.END, values=(
                recipient['id'],
                hw_id_display,
                recipient['days'],
                start_date,
                end_date,
                contact,
                comments,
                license_file
            ))
    
    def _extend_license(self):
        """Продлевает выбранную лицензию (добавляет дни)"""
        selected = self.recipients_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите лицензию для продления")
            return
        
        item = self.recipients_tree.item(selected[0])
        recipient_id = item['values'][0]
        
        # Запрашиваем количество дней для добавления
        days_str = simpledialog.askstring("Продление лицензии", 
                                          "Введите количество дней для добавления:",
                                          initialvalue="30")
        if not days_str:
            return
        
        try:
            days_to_add = int(days_str)
            if days_to_add <= 0:
                raise ValueError("Количество дней должно быть положительным")
        except ValueError as e:
            messagebox.showerror("Ошибка", f"Неверное количество дней: {str(e)}")
            return
        
        # Получаем текущую запись
        recipient = self.database.get_recipient(recipient_id)
        if not recipient:
            messagebox.showerror("Ошибка", "Запись не найдена")
            return
        
        # Вычисляем новую дату окончания
        from datetime import datetime, timedelta
        current_end_date = datetime.fromisoformat(recipient['end_date']) if recipient['end_date'] else datetime.now()
        new_end_date = current_end_date + timedelta(days=days_to_add)
        new_days = recipient['days'] + days_to_add
        
        # Обновляем в базе данных
        self.database.update_recipient(
            recipient_id=recipient_id,
            days=new_days,
            end_date=new_end_date
        )
        
        # Обновляем список
        self._refresh_recipients_list()
        
        messagebox.showinfo("Успех", 
                           f"Лицензия продлена на {days_to_add} дней!\n"
                           f"Новая дата окончания: {new_end_date.strftime('%Y-%m-%d')}")
    
    def _delete_selected(self):
        """Удаляет выбранного получателя"""
        selected = self.recipients_tree.selection()
        if not selected:
            messagebox.showwarning("Предупреждение", "Выберите запись для удаления")
            return
        
        item = self.recipients_tree.item(selected[0])
        recipient_id = item['values'][0]
        
        if messagebox.askyesno("Подтверждение", f"Удалить запись ID {recipient_id}?"):
            if self.database.delete_recipient(recipient_id):
                messagebox.showinfo("Успех", "Запись удалена")
                self._refresh_recipients_list()
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить запись")
    
    def _search_by_hwid(self):
        """Поиск получателей по Hardware ID"""
        hw_id = simpledialog.askstring("Поиск", "Введите Hardware ID для поиска:")
        if not hw_id:
            return
        
        # Очищаем таблицу
        for item in self.recipients_tree.get_children():
            self.recipients_tree.delete(item)
        
        # Ищем в базе
        recipients = self.database.search_by_hw_id(hw_id)
        
        if not recipients:
            messagebox.showinfo("Результат", "Записи не найдены")
            return
        
        # Отображаем результаты
        for recipient in recipients:
            start_date = recipient.get('start_date', '')
            if start_date:
                try:
                    dt = datetime.fromisoformat(start_date)
                    start_date = dt.strftime('%Y-%m-%d')
                except:
                    pass
            
            end_date = recipient.get('end_date', '')
            if end_date:
                try:
                    dt = datetime.fromisoformat(end_date)
                    end_date = dt.strftime('%Y-%m-%d')
                except:
                    pass
            
            contact = recipient.get('recipient', '') or ''
            if len(contact) > 20:
                contact = contact[:20] + "..."
            
            comments = recipient.get('comments', '') or ''
            if len(comments) > 30:
                comments = comments[:30] + "..."
            
            license_file = recipient.get('license_file', '') or ''
            if license_file:
                license_file = Path(license_file).name
            
            # Обрабатываем hw_id (может быть None для developer лицензий)
            hw_id_display = recipient.get('hw_id') or 'NONE (developer)'
            if hw_id_display and hw_id_display != 'NONE (developer)':
                if len(hw_id_display) > 20:
                    hw_id_display = hw_id_display[:20] + "..."
            
            self.recipients_tree.insert("", tk.END, values=(
                recipient['id'],
                hw_id_display,
                recipient['days'],
                start_date,
                end_date,
                contact,
                comments,
                license_file
            ))
        
        messagebox.showinfo("Результат", f"Найдено записей: {len(recipients)}")
    
    def _open_licenses_folder(self):
        """Открывает папку с сгенерированными лицензиями"""
        licenses_dir = Path(script_dir) / 'generated_licenses'
        licenses_dir.mkdir(exist_ok=True)
        
        try:
            if os.name == 'nt':
                os.startfile(str(licenses_dir))
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.run(['open', str(licenses_dir)])
            else:
                import subprocess
                subprocess.run(['xdg-open', str(licenses_dir)])
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{str(e)}")


def main():
    """Точка входа приложения"""
    app = LicenseGeneratorGUI()
    app.mainloop()


if __name__ == '__main__':
    main()

