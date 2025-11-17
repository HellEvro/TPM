# Техническое задание: Система генерации лицензий InfoBot AI Premium

## 1. Общее описание

### 1.1 Назначение системы
Разработать систему генерации лицензий для InfoBot AI Premium, которая позволяет создавать лицензионные файлы с привязкой к Hardware ID получателя, управлять базой данных получателей и предоставлять различные интерфейсы для работы (GUI, командная строка, Python API).

### 1.2 Цели разработки
- Автоматизация процесса генерации лицензий
- Централизованное хранение информации о получателях лицензий
- Удобные интерфейсы для различных сценариев использования
- Интеграция с внешними системами (Telegram боты, веб-приложения)

### 1.3 Требования к системе
- Кроссплатформенность (Windows, Linux, macOS)
- Простота использования
- Надежное хранение данных
- Безопасность конфиденциальной информации

---

## 2. Функциональные требования

### 2.1 Генерация лицензий

#### 2.1.1 Обязательные параметры
- **Hardware ID (HWID)** - уникальный идентификатор оборудования получателя
  - Должен автоматически нормализоваться до 16 символов (первые 16 символов в верхнем регистре)
  - Поддержка как полного (64 символа), так и короткого (16 символов) формата
- **Количество дней** - длительность действия лицензии (положительное целое число)

#### 2.1.2 Опциональные параметры
- **Дата начала** - дата начала действия лицензии
  - Если не указана: используется текущая дата + 1 день (завтра, 00:00:00)
  - Поддержка форматов: `YYYY-MM-DD` и `DD.MM.YYYY`
- **Контактная информация получателя (recipient)** - универсальное поле для:
  - Email адреса
  - Telegram nickname (например: @username)
  - Telegram ID (числовой)
  - Имя получателя
  - Любая другая контактная информация
- **Комментарии** - дополнительные заметки о лицензии

#### 2.1.3 Логика расчета дат
- **Дата начала:**
  - Если не указана: `datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)`
  - Если указана: указанная дата с временем 00:00:00
- **Дата окончания:**
  - Формула: `дата_начала + timedelta(days=количество_дней + 1)`
  - Время: всегда 00:00:00
  - Пример: лицензия на 30 дней с 2024-02-01 действует до 2024-03-03 00:00:00

#### 2.1.4 Результат генерации
- Создание файла `.lic` в папке `generated_licenses/`
- Формат имени файла: `{HWID}_{DAYS}days_{TIMESTAMP}.lic`
- Сохранение информации в базу данных (если включено)
- Возврат словаря с информацией о лицензии

### 2.2 База данных получателей

#### 2.2.1 Структура таблицы `license_recipients`
```sql
CREATE TABLE license_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hw_id TEXT NOT NULL,
    days INTEGER NOT NULL,
    start_date TEXT,
    end_date TEXT NOT NULL,
    recipient TEXT,
    comments TEXT,
    license_file TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

#### 2.2.2 Индексы
- Индекс на `hw_id` для быстрого поиска

#### 2.2.3 Функции работы с БД
- `add_recipient()` - добавление получателя
- `update_recipient()` - обновление данных получателя
- `get_recipient(id)` - получение получателя по ID
- `get_all_recipients()` - получение всех получателей (сортировка по дате создания DESC)
- `search_by_hw_id(hw_id)` - поиск по Hardware ID (LIKE поиск)
- `delete_recipient(id)` - удаление получателя

#### 2.2.4 Автоматическое создание
- База данных создается автоматически при первом использовании
- Путь к БД: `license_generator/licenses.db`

### 2.3 Интерфейсы

#### 2.3.1 GUI приложение
**Технология:** tkinter

**Компоненты:**
1. **Форма генерации лицензий:**
   - Поле "Контакт получателя" (Entry)
   - Поле "Hardware ID" (Entry) с кнопкой "Получить HWID"
   - Поле "Количество дней" (Entry, по умолчанию: 30)
   - Поле "Дата начала" (Entry, опционально)
   - Поле "Комментарии" (Text widget, многострочное)
   - Кнопка "Сгенерировать лицензию"

2. **Таблица получателей:**
   - Колонки: ID, HWID, Дни, Начало, Окончание, Контакт, Комментарии, Файл
   - Прокрутка (Scrollbar)
   - Функции:
     - Обновить список
     - Удалить выбранное
     - Поиск по HWID
     - Открыть папку с лицензиями

**Особенности:**
- Автоматическое обновление таблицы после генерации
- Валидация введенных данных
- Информационные сообщения об успехе/ошибках
- Опция очистки формы после генерации

#### 2.3.2 Командная строка
**Синтаксис:**
```bash
python generate_license.py <HWID> <DAYS> [START_DATE] [RECIPIENT] [COMMENTS]
```

**Параметры:**
- `HWID` - обязательный, Hardware ID
- `DAYS` - обязательный, количество дней
- `START_DATE` - опциональный, дата начала (YYYY-MM-DD или DD.MM.YYYY)
- `RECIPIENT` - опциональный, контактная информация
- `COMMENTS` - опциональный, комментарии

**Вывод:**
- Информация о процессе генерации
- Путь к созданному файлу
- ID записи в базе данных (если сохранено)
- Справка при неправильном использовании

#### 2.3.3 Python API
**Функция:** `generate_license()`

**Сигнатура:**
```python
def generate_license(
    hw_id: str,
    days: int,
    start_date: Optional[datetime] = None,
    email: str = 'customer@example.com',
    recipient: str = None,
    comments: str = None,
    save_to_db: bool = True,
    verbose: bool = True
) -> Dict[str, Any]
```

**Возвращаемое значение:**
```python
{
    'license_path': str,      # Полный путь к файлу .lic
    'license_data': dict,     # Данные лицензии
    'recipient_id': int,      # ID в базе данных (если сохранено)
    'hw_id': str,             # Нормализованный HWID
    'days': int,              # Количество дней
    'start_date': str,        # Дата начала (ISO формат)
    'end_date': str           # Дата окончания (ISO формат)
}
```

---

## 3. Технические требования

### 3.1 Зависимости
- Python 3.7+
- `cryptography` - для шифрования лицензий
- `sqlite3` - встроенная библиотека для БД
- `tkinter` - для GUI (обычно входит в Python)

### 3.2 Структура файлов
```
license_generator/
├── license_manager.py          # Менеджер лицензий (модифицирован)
├── license_database.py          # Модуль работы с БД
├── license_generator_gui.py     # GUI приложение
├── generate_license.py           # Скрипт командной строки и API
├── hardware_id.py               # Получение Hardware ID
├── license_types.py             # Типы лицензий
├── licenses.db                  # База данных (создается автоматически)
├── generated_licenses/          # Папка с .lic файлами
├── start_license_generator.cmd  # Скрипт запуска (Windows)
└── start_license_generator.sh   # Скрипт запуска (Linux/MacOS)
```

### 3.3 Интеграция с LicenseManager

#### 3.3.1 Модификация метода `generate_license()`
Добавить параметр `start_date: datetime = None` в метод `generate_license()` класса `LicenseManager`.

**Логика:**
```python
# Определяем дату начала
if start_date is None:
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
else:
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

# Дата окончания: до 00:00:00 (N+1)-го дня
expires_at = start_date + timedelta(days=duration_days + 1)
expires_at = expires_at.replace(hour=0, minute=0, second=0, microsecond=0)
```

### 3.4 Нормализация Hardware ID

**Требования:**
- Автоматическое обрезание до 16 символов, если введен полный ID (64 символа)
- Преобразование в верхний регистр
- Предупреждение, если ID короче 16 символов

**Реализация:**
```python
hw_id = hw_id.strip().upper()
if len(hw_id) > 16:
    hw_id = hw_id[:16]
elif len(hw_id) < 16:
    # Предупреждение
```

### 3.5 Получение Hardware ID

**Функция:** `get_short_hardware_id()` из модуля `hardware_id.py`

**Возвращает:** Первые 16 символов полного Hardware ID в верхнем регистре

**Использование:**
- В GUI: кнопка "Получить HWID" вызывает эту функцию
- При проверке лицензий сравниваются только первые 16 символов

---

## 4. Детальная спецификация компонентов

### 4.1 Модуль `license_database.py`

#### 4.1.1 Класс `LicenseDatabase`

**Методы:**

1. **`__init__(db_path: str = None)`**
   - Инициализация базы данных
   - Автоматическое создание таблиц, если их нет

2. **`_init_database()`**
   - Создание таблицы `license_recipients`
   - Создание индекса на `hw_id`

3. **`add_recipient(...)`**
   - Параметры: hw_id, days, start_date, end_date, recipient, comments, license_file
   - Возвращает: ID созданной записи

4. **`update_recipient(recipient_id, ...)`**
   - Обновление полей записи (только указанные поля)

5. **`get_recipient(recipient_id)`**
   - Возвращает словарь с данными получателя или None

6. **`get_all_recipients()`**
   - Возвращает список всех получателей, отсортированный по дате создания DESC

7. **`search_by_hw_id(hw_id)`**
   - LIKE поиск по Hardware ID
   - Возвращает список найденных записей

8. **`delete_recipient(recipient_id)`**
   - Удаление записи по ID
   - Возвращает True при успехе, False если запись не найдена

### 4.2 Модуль `license_generator_gui.py`

#### 4.2.1 Класс `LicenseGeneratorGUI(tk.Tk)`

**Атрибуты:**
- `license_manager: LicenseManager`
- `database: LicenseDatabase`
- Переменные для формы (StringVar, Text widget)

**Методы:**

1. **`__init__()`**
   - Инициализация компонентов
   - Создание интерфейса
   - Загрузка списка получателей

2. **`_build_ui()`**
   - Создание всех элементов интерфейса
   - Настройка таблицы
   - Размещение элементов

3. **`_get_current_hwid()`**
   - Получение Hardware ID текущего компьютера
   - Отображение в поле ввода
   - Показ полного и короткого ID

4. **`_parse_start_date()`**
   - Парсинг даты из поля ввода
   - Поддержка форматов YYYY-MM-DD и DD.MM.YYYY
   - Возвращает datetime или None

5. **`_generate_license()`**
   - Валидация полей
   - Нормализация HWID
   - Вызов функции генерации
   - Сохранение в БД
   - Отображение результата
   - Обновление таблицы

6. **`_refresh_recipients_list()`**
   - Очистка таблицы
   - Загрузка данных из БД
   - Форматирование дат для отображения
   - Вставка записей в таблицу

7. **`_delete_selected()`**
   - Удаление выбранной записи
   - Подтверждение действия
   - Обновление таблицы

8. **`_search_by_hwid()`**
   - Диалог ввода HWID
   - Поиск в БД
   - Отображение результатов

9. **`_open_licenses_folder()`**
   - Открытие папки `generated_licenses/`
   - Кроссплатформенная реализация

### 4.3 Модуль `generate_license.py`

#### 4.3.1 Функция `generate_license()`

**Алгоритм работы:**

1. Нормализация HWID
   - Обрезание до 16 символов
   - Преобразование в верхний регистр
   - Предупреждения при необходимости

2. Генерация лицензии через LicenseManager
   - Вызов `manager.generate_license()` с параметрами
   - Получение зашифрованных данных

3. Сохранение файла
   - Создание папки `generated_licenses/` если не существует
   - Формирование имени файла
   - Запись бинарных данных

4. Расчет дат для БД
   - Определение даты начала (если не указана)
   - Расчет даты окончания

5. Сохранение в БД (если `save_to_db=True`)
   - Создание экземпляра LicenseDatabase
   - Вызов `add_recipient()`
   - Обработка ошибок

6. Вывод информации (если `verbose=True`)
   - Информация о процессе
   - Путь к файлу
   - ID в БД

7. Возврат результата
   - Словарь с полной информацией

#### 4.3.2 Обработка командной строки

**Алгоритм:**

1. Проверка количества аргументов
   - Минимум 2 (HWID и DAYS)
   - Вывод справки при недостатке аргументов

2. Парсинг обязательных параметров
   - `hw_id = sys.argv[1]`
   - `days = int(sys.argv[2])`

3. Парсинг опциональных параметров
   - `start_date` - парсинг с поддержкой двух форматов
   - `recipient = sys.argv[4]` если есть
   - `comments = sys.argv[5]` если есть

4. Определение email для license_id
   - Если recipient содержит '@', использовать его
   - Иначе использовать дефолтный email

5. Вызов функции генерации
6. Завершение с кодом 0 при успехе

---

## 5. Логика работы с датами

### 5.1 Правила расчета

#### 5.1.1 Дата начала
- **Если не указана:**
  ```python
  start_date = datetime.now().replace(
      hour=0, minute=0, second=0, microsecond=0
  ) + timedelta(days=1)
  ```
  Результат: завтра, 00:00:00

- **Если указана:**
  ```python
  start_date = start_date.replace(
      hour=0, minute=0, second=0, microsecond=0
  )
  ```
  Результат: указанная дата, 00:00:00

#### 5.1.2 Дата окончания
```python
end_date = start_date + timedelta(days=days + 1)
end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
```

**Пояснение:**
- Лицензия на N дней действует N полных дней
- Истекает в 00:00:00 (N+1)-го дня от даты начала
- Пример: 30 дней с 2024-02-01 → действует до 2024-03-03 00:00:00

### 5.2 Примеры

| Дата начала | Дней | Дата окончания | Пояснение |
|-------------|------|----------------|-----------|
| Не указана (сегодня 2024-01-15) | 30 | 2024-02-16 00:00:00 | Начало: завтра (16.01) |
| 2024-02-01 | 30 | 2024-03-03 00:00:00 | Начало: 01.02, конец: начало 32-го дня |
| 2024-01-01 | 7 | 2024-01-09 00:00:00 | Начало: 01.01, конец: начало 8-го дня |

---

## 6. Интерфейсы и примеры использования

### 6.1 GUI приложение

**Запуск:**
```bash
python license_generator/license_generator_gui.py
```

**Рабочий процесс:**
1. Заполнение формы
2. Нажатие "Сгенерировать лицензию"
3. Просмотр результата
4. Автоматическое обновление таблицы
5. Опциональная очистка формы

### 6.2 Командная строка

**Базовое использование:**
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30
```

**С параметрами:**
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com "Test license"
```

### 6.3 Python API

**Базовое использование:**
```python
from generate_license import generate_license

result = generate_license(
    hw_id='94EAA22C9EDB6FC7',
    days=30
)
```

**С параметрами:**
```python
from generate_license import generate_license
from datetime import datetime

result = generate_license(
    hw_id='94EAA22C9EDB6FC7',
    days=30,
    start_date=datetime(2024, 2, 1),
    recipient='customer@example.com',
    comments='Test license',
    save_to_db=True,
    verbose=False
)
```

### 6.4 Интеграция с Telegram ботом

**Требования:**
- Библиотека `python-telegram-bot`
- Проверка прав доступа (только администраторы)

**Команды бота:**
- `/generate_license <HWID> <DAYS> [START_DATE] [RECIPIENT] [COMMENTS]` - генерация лицензии
- `/list_licenses` - список всех лицензий
- `/search_license <HWID>` - поиск по Hardware ID

**Пример обработчика:**
```python
async def generate_license_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка прав
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет прав доступа")
        return
    
    # Парсинг аргументов
    hw_id = context.args[0]
    days = int(context.args[1])
    # ... остальные параметры
    
    # Генерация
    result = generate_license(hw_id=hw_id, days=days, verbose=False)
    
    # Отправка файла
    await update.message.reply_document(
        document=open(result['license_path'], 'rb'),
        filename=Path(result['license_path']).name
    )
```

---

## 7. Требования к безопасности

### 7.1 Защита данных
- База данных `licenses.db` содержит конфиденциальную информацию
- Не должна попадать в публичный репозиторий (добавить в `.gitignore`)
- Папка `license_generator/` не копируется в публичную версию

### 7.2 Контроль доступа
- При использовании в Telegram боте обязательна проверка прав доступа
- Ограничение доступа к генератору только авторизованным пользователям

### 7.3 Резервное копирование
- Рекомендуется регулярное резервное копирование базы данных
- Хранение резервных копий в защищенном месте

---

## 8. Обработка ошибок

### 8.1 Валидация входных данных
- Проверка формата Hardware ID
- Проверка количества дней (должно быть положительным)
- Проверка формата даты (поддержка двух форматов)
- Предупреждения при некорректных данных

### 8.2 Обработка исключений
- Обработка ошибок базы данных
- Обработка ошибок файловой системы
- Обработка ошибок генерации лицензии
- Информативные сообщения об ошибках

### 8.3 Логирование
- Логирование успешных операций
- Логирование ошибок
- Логирование предупреждений

---

## 9. Тестирование

### 9.1 Тестовые сценарии

1. **Генерация лицензии без даты начала**
   - Проверка: дата начала = завтра
   - Проверка: дата окончания рассчитана правильно

2. **Генерация лицензии с датой начала**
   - Проверка: используется указанная дата
   - Проверка: дата окончания рассчитана правильно

3. **Нормализация HWID**
   - Полный ID (64 символа) → обрезается до 16
   - Короткий ID (16 символов) → остается без изменений
   - Короткий ID (< 16 символов) → предупреждение

4. **Работа с базой данных**
   - Добавление записи
   - Получение всех записей
   - Поиск по HWID
   - Обновление записи
   - Удаление записи

5. **GUI приложение**
   - Открытие и отображение интерфейса
   - Генерация лицензии через форму
   - Обновление таблицы
   - Поиск по HWID
   - Удаление записи

6. **Командная строка**
   - Минимальные параметры
   - Все параметры
   - Неверные параметры (проверка справки)

---

## 10. Документация

### 10.1 Требования к документации
- Полное описание всех способов использования
- Примеры для каждого сценария
- Описание логики работы с датами
- FAQ с ответами на частые вопросы
- Примеры интеграции (Telegram бот, веб-приложение)

### 10.2 Структура документации
1. Обзор системы
2. Способы использования (GUI, CLI, API)
3. Детальное описание каждого интерфейса
4. Примеры использования
5. FAQ
6. Безопасность

---

## 11. Этапы разработки

### Этап 1: Базовая функциональность
1. Модификация `LicenseManager` для поддержки `start_date`
2. Создание модуля `license_database.py`
3. Обновление `generate_license.py` с интеграцией БД

### Этап 2: GUI приложение
1. Создание базового интерфейса
2. Реализация формы генерации
3. Реализация таблицы получателей
4. Добавление функций управления

### Этап 3: Улучшения
1. Нормализация HWID
2. Поддержка форматов даты
3. Обработка ошибок
4. Валидация данных

### Этап 4: Документация и примеры
1. Создание полной документации
2. Примеры использования
3. Пример интеграции с Telegram ботом

---

## 12. Критерии приемки

### 12.1 Функциональность
- ✅ Генерация лицензий работает корректно
- ✅ База данных создается и работает
- ✅ GUI приложение полностью функционально
- ✅ Командная строка работает со всеми параметрами
- ✅ Python API возвращает корректные данные

### 12.2 Качество кода
- ✅ Код следует PEP 8
- ✅ Документированы все функции и классы
- ✅ Обработка ошибок на всех уровнях
- ✅ Валидация входных данных

### 12.3 Документация
- ✅ Полная документация создана
- ✅ Примеры использования работают
- ✅ FAQ покрывает основные вопросы

### 12.4 Тестирование
- ✅ Все тестовые сценарии пройдены
- ✅ Нет критических ошибок
- ✅ Предупреждения обрабатываются корректно

---

## 13. Дополнительные требования

### 13.1 Производительность
- Генерация лицензии должна выполняться быстро (< 1 секунды)
- Загрузка списка получателей должна быть быстрой даже при большом количестве записей

### 13.2 Удобство использования
- Интуитивно понятный интерфейс GUI
- Понятные сообщения об ошибках
- Подробная справка в командной строке

### 13.3 Расширяемость
- Возможность добавления новых полей в базу данных
- Возможность добавления новых форматов дат
- Возможность интеграции с другими системами

---

## 14. Технические детали реализации

### 14.1 Нормализация HWID

**Код:**
```python
hw_id = hw_id.strip().upper()
if len(hw_id) > 16:
    hw_id = hw_id[:16]
    if verbose:
        print(f"[INFO] HWID обрезан до 16 символов: {hw_id}")
elif len(hw_id) < 16:
    if verbose:
        print(f"[WARNING] HWID короче 16 символов: {hw_id}")
```

### 14.2 Расчет дат

**Код:**
```python
# Дата начала
if start_date is None:
    start_date = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
else:
    start_date = start_date.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

# Дата окончания
end_date = start_date + timedelta(days=days + 1)
end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
```

### 14.3 Парсинг даты из командной строки

**Код:**
```python
date_str = sys.argv[3]
for date_format in ['%Y-%m-%d', '%d.%m.%Y']:
    try:
        start_date = datetime.strptime(date_str, date_format)
        break
    except ValueError:
        continue

if start_date is None:
    print(f"[ERROR] Неверный формат даты: {date_str}")
    sys.exit(1)
```

### 14.4 Определение email для license_id

**Код:**
```python
email = recipient if recipient and '@' in recipient else 'customer@example.com'
```

---

## 15. Структура данных

### 15.1 Возвращаемое значение `generate_license()`

```python
{
    'license_path': str,           # 'license_generator/generated_licenses/94EAA22C9EDB6FC7_30days_20240201_143022.lic'
    'license_data': dict,          # Данные лицензии от LicenseManager
    'recipient_id': int,           # 123 (ID в базе данных)
    'hw_id': str,                  # '94EAA22C9EDB6FC7'
    'days': int,                    # 30
    'start_date': str,             # '2024-02-01T00:00:00'
    'end_date': str                # '2024-03-03T00:00:00'
}
```

### 15.2 Структура записи в БД

```python
{
    'id': 1,
    'hw_id': '94EAA22C9EDB6FC7',
    'days': 30,
    'start_date': '2024-02-01T00:00:00',
    'end_date': '2024-03-03T00:00:00',
    'recipient': 'customer@example.com',
    'comments': 'Test license',
    'license_file': 'license_generator/generated_licenses/94EAA22C9EDB6FC7_30days_20240201_143022.lic',
    'created_at': '2024-01-15T14:30:22',
    'updated_at': '2024-01-15T14:30:22'
}
```

---

## 16. Примеры кода

### 16.1 Инициализация базы данных

```python
def _init_database(self):
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hw_id TEXT NOT NULL,
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
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_hw_id ON license_recipients(hw_id)
    """)
    
    conn.commit()
    conn.close()
```

### 16.2 Добавление получателя

```python
def add_recipient(self, hw_id, days, start_date=None, end_date=None, 
                 recipient=None, comments=None, license_file=None):
    now = datetime.now().isoformat()
    start_date_str = start_date.isoformat() if start_date else None
    end_date_str = end_date.isoformat() if end_date else None
    
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO license_recipients 
        (hw_id, days, start_date, end_date, recipient, comments, license_file, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (hw_id, days, start_date_str, end_date_str, recipient, comments, 
          license_file, now, now))
    
    recipient_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return recipient_id
```

### 16.3 Генерация лицензии с сохранением в БД

```python
# Генерация через LicenseManager
license_data = manager.generate_license(
    user_email=email,
    license_type='premium',
    hardware_id=hw_id,
    custom_duration_days=days,
    start_date=start_date
)

# Сохранение файла
output_dir = script_dir / 'generated_licenses'
output_dir.mkdir(exist_ok=True)
filename = f"{hw_id}_{days}days_{timestamp}.lic"
license_path = output_dir / filename

with open(license_path, 'wb') as f:
    f.write(license_data['encrypted_license'])

# Сохранение в БД
if save_to_db:
    db = LicenseDatabase()
    recipient_id = db.add_recipient(
        hw_id=hw_id,
        days=days,
        start_date=start_date,
        end_date=end_date,
        recipient=recipient,
        comments=comments,
        license_file=str(license_path)
    )
```

---

## 17. Чеклист разработки

### Фаза 1: Подготовка
- [ ] Изучить существующий код LicenseManager
- [ ] Изучить структуру лицензий
- [ ] Определить требования к базе данных

### Фаза 2: База данных
- [ ] Создать модуль license_database.py
- [ ] Реализовать класс LicenseDatabase
- [ ] Реализовать все методы работы с БД
- [ ] Протестировать работу БД

### Фаза 3: Модификация LicenseManager
- [ ] Добавить параметр start_date
- [ ] Реализовать логику расчета дат
- [ ] Протестировать генерацию с разными датами

### Фаза 4: Обновление generate_license.py
- [ ] Добавить параметры recipient и start_date
- [ ] Реализовать нормализацию HWID
- [ ] Интегрировать с базой данных
- [ ] Обновить обработку командной строки
- [ ] Протестировать все сценарии

### Фаза 5: GUI приложение
- [ ] Создать базовую структуру интерфейса
- [ ] Реализовать форму генерации
- [ ] Реализовать таблицу получателей
- [ ] Добавить функции управления
- [ ] Протестировать GUI

### Фаза 6: Документация
- [ ] Создать полную документацию
- [ ] Добавить примеры использования
- [ ] Создать пример Telegram бота
- [ ] Добавить FAQ

### Фаза 7: Тестирование
- [ ] Протестировать все функции
- [ ] Проверить обработку ошибок
- [ ] Проверить работу на разных ОС
- [ ] Исправить найденные ошибки

---

## 18. Заключение

Данное техническое задание описывает полную систему генерации лицензий с GUI интерфейсом, базой данных и различными способами использования. Следуя этому ТЗ, можно воссоздать систему с нуля или модифицировать существующую.

**Ключевые моменты:**
- Модульная архитектура
- Гибкость в использовании
- Надежное хранение данных
- Удобные интерфейсы
- Полная документация

**Версия ТЗ:** 1.0  
**Дата:** 2024

