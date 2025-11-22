# 📜 Генератор лицензий InfoBot AI Premium

Полное руководство по использованию генератора лицензий для InfoBot AI Premium.

## 📋 Содержание

1. [Обзор](#обзор)
2. [Способы использования](#способы-использования)
3. [GUI приложение](#gui-приложение)
4. [Командная строка](#командная-строка)
5. [Использование из Python кода](#использование-из-python-кода)
6. [Интеграция с Telegram ботом](#интеграция-с-telegram-ботом)
7. [База данных](#база-данных)
8. [Логика работы с датами](#логика-работы-с-датами)
9. [Примеры использования](#примеры-использования)
10. [FAQ](#faq)

---

## 🎯 Обзор

Генератор лицензий позволяет создавать лицензионные файлы для InfoBot AI Premium с привязкой к Hardware ID получателя. Система включает:

- **GUI приложение** для удобной работы
- **Командная строка** для автоматизации
- **Python API** для интеграции в другие системы
- **База данных SQLite** для хранения информации о получателях

---

## 🚀 Способы использования

### 1. GUI приложение (рекомендуется для ручной работы)

### 2. Командная строка (для автоматизации)

### 3. Python API (для интеграции в боты и другие системы)

---

## 🖥️ GUI приложение

### Запуск

**Windows:**
```cmd
python license_generator/license_generator_gui.py
```

**Linux/MacOS:**
```bash
python3 license_generator/license_generator_gui.py
```

Или используйте скрипты:
- Windows: `start_license_generator.cmd`
- Linux/MacOS: `start_license_generator.sh`

### Интерфейс

GUI содержит две основные секции:

#### 1. Генерация лицензии

**Поля формы:**
- **Контакт получателя** - любая контактная информация (email, telegram, имя и т.д.)
- **Hardware ID** - уникальный ID оборудования получателя
  - Можно ввести вручную
  - Или нажать "Получить HWID" для получения ID текущего компьютера
- **Количество дней** - длительность лицензии (по умолчанию: 30)
- **Дата начала (опционально)** - дата начала действия лицензии
  - Формат: `YYYY-MM-DD` или `DD.MM.YYYY`
  - Если не указана, используется завтрашний день
- **Комментарии** - дополнительные заметки

#### 2. База данных получателей

Таблица со всеми сгенерированными лицензиями:
- ID записи
- Hardware ID
- Количество дней
- Дата начала
- Дата окончания
- Контакт получателя
- Комментарии
- Файл лицензии

**Функции:**
- Обновить список
- Удалить выбранное
- Поиск по HWID
- Открыть папку с лицензиями

---

## 💻 Командная строка

### Базовый синтаксис

```bash
python license_generator/generate_license.py <HWID> <DAYS> [START_DATE] [RECIPIENT] [COMMENTS]
```

### Параметры

| Параметр | Обязательный | Описание |
|----------|--------------|----------|
| `HWID` | ✅ Да | Hardware ID получателя (автоматически обрезается до 16 символов) |
| `DAYS` | ✅ Да | Количество дней действия лицензии |
| `START_DATE` | ❌ Нет | Дата начала в формате `YYYY-MM-DD` или `DD.MM.YYYY` (по умолчанию: завтра) |
| `RECIPIENT` | ❌ Нет | Контактная информация получателя (email, telegram, и т.д.) |
| `COMMENTS` | ❌ Нет | Комментарии к лицензии |

### Примеры

#### Пример 1: Минимальная генерация
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30
```
- Лицензия на 30 дней
- Дата начала: завтра
- Контакт: не указан

#### Пример 2: С датой начала
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01
```
- Лицензия на 30 дней
- Дата начала: 1 февраля 2024
- Дата окончания: 3 марта 2024 00:00:00

#### Пример 3: С датой в российском формате
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 31.12.2025
```
- Лицензия на 30 дней
- Дата начала: 31 декабря 2025
- Дата окончания: 1 февраля 2026 00:00:00

#### Пример 4: С контактной информацией
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com
```
- Лицензия на 30 дней
- Дата начала: 1 февраля 2024
- Контакт: customer@example.com

#### Пример 5: С telegram nickname
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 @telegram_user
```
- Лицензия на 30 дней
- Дата начала: 1 февраля 2024
- Контакт: @telegram_user

#### Пример 6: С telegram ID
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 123456789
```
- Лицензия на 30 дней
- Дата начала: 1 февраля 2024
- Контакт: 123456789 (Telegram ID)

#### Пример 7: Со всеми параметрами
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com "Test license for customer"
```
- Лицензия на 30 дней
- Дата начала: 1 февраля 2024
- Контакт: customer@example.com
- Комментарии: "Test license for customer"

### Результат

После выполнения команды:
1. ✅ Создается файл `.lic` в папке `generated_licenses/`
2. ✅ Запись добавляется в базу данных `licenses.db`
3. ✅ Выводится информация о созданной лицензии

**Формат имени файла:**
```
{HWID}_{DAYS}days_{TIMESTAMP}.lic
```

Пример: `94EAA22C9EDB6FC7_30days_20240201_143022.lic`

---

## 🐍 Использование из Python кода

### Импорт функции

```python
from pathlib import Path
import sys

# Добавляем путь к license_generator
sys.path.insert(0, str(Path(__file__).parent / 'license_generator'))

from generate_license import generate_license
from datetime import datetime
```

### Базовое использование

```python
# Простая генерация
result = generate_license(
    hw_id='94EAA22C9EDB6FC7',
    days=30
)

print(f"Лицензия создана: {result['license_path']}")
```

### С параметрами

```python
result = generate_license(
    hw_id='94EAA22C9EDB6FC7',
    days=30,
    start_date=datetime(2024, 2, 1),
    recipient='customer@example.com',
    comments='Test license',
    save_to_db=True,
    verbose=False
)

# result содержит:
# {
#     'license_path': 'путь/к/файлу.lic',
#     'license_data': {...},
#     'recipient_id': 123,
#     'hw_id': '94EAA22C9EDB6FC7',
#     'days': 30,
#     'start_date': '2024-02-01T00:00:00',
#     'end_date': '2024-03-03T00:00:00'
# }
```

### Параметры функции

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `hw_id` | `str` | ✅ Да | Hardware ID (автоматически обрезается до 16 символов) |
| `days` | `int` | ✅ Да | Количество дней лицензии |
| `start_date` | `datetime` | ❌ Нет | Дата начала (если None, используется завтра) |
| `email` | `str` | ❌ Нет | Email для генерации license_id (по умолчанию: 'customer@example.com') |
| `recipient` | `str` | ❌ Нет | Контактная информация получателя (сохраняется в БД) |
| `comments` | `str` | ❌ Нет | Комментарии |
| `save_to_db` | `bool` | ❌ Нет | Сохранять в БД (по умолчанию: True) |
| `verbose` | `bool` | ❌ Нет | Выводить информацию в консоль (по умолчанию: True) |

### Возвращаемое значение

Функция возвращает словарь:

```python
{
    'license_path': str,      # Полный путь к файлу .lic
    'license_data': dict,     # Данные лицензии
    'recipient_id': int,      # ID в базе данных (если сохранено)
    'hw_id': str,             # Нормализованный HWID (16 символов)
    'days': int,              # Количество дней
    'start_date': str,        # Дата начала (ISO формат)
    'end_date': str           # Дата окончания (ISO формат)
}
```

---

## 🤖 Интеграция с Telegram ботом

### Полный пример с python-telegram-bot

```python
#!/usr/bin/env python3
"""
Пример интеграции генератора лицензий с Telegram ботом
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pathlib import Path
import sys
from datetime import datetime

# Добавляем путь к license_generator
sys.path.insert(0, str(Path(__file__).parent / 'license_generator'))
from generate_license import generate_license

# Токен бота (получите у @BotFather)
BOT_TOKEN = "YOUR_BOT_TOKEN"

# ID администраторов (только они могут генерировать лицензии)
ADMIN_IDS = [123456789, 987654321]


async def generate_license_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /generate_license"""
    
    # Проверка прав доступа
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "❌ У вас нет прав для генерации лицензий.\n"
            "Обратитесь к администратору."
        )
        return
    
    # Проверка аргументов
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Неверный формат команды.\n\n"
            "Использование:\n"
            "`/generate_license <HWID> <DAYS> [START_DATE] [RECIPIENT] [COMMENTS]`\n\n"
            "Примеры:\n"
            "`/generate_license 94EAA22C9EDB6FC7 30`\n"
            "`/generate_license 94EAA22C9EDB6FC7 30 2024-02-01`\n"
            "`/generate_license 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com`\n"
            "`/generate_license 94EAA22C9EDB6FC7 30 2024-02-01 @telegram_user`\n"
            "`/generate_license 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com Test license`",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Парсим аргументы
        hw_id = context.args[0].upper()
        days = int(context.args[1])
        
        # Опциональные параметры
        start_date = None
        if len(context.args) > 2:
            date_str = context.args[2]
            # Поддерживаем два формата
            for date_format in ['%Y-%m-%d', '%d.%m.%Y']:
                try:
                    start_date = datetime.strptime(date_str, date_format)
                    break
                except ValueError:
                    continue
            
            if start_date is None:
                await update.message.reply_text(
                    f"❌ Неверный формат даты: {date_str}\n"
                    "Используйте YYYY-MM-DD (например: 2024-02-01) или DD.MM.YYYY (например: 01.02.2024)"
                )
                return
        
        recipient = context.args[3] if len(context.args) > 3 else None
        comments = ' '.join(context.args[4:]) if len(context.args) > 4 else None
        
        # Email для генерации license_id
        email = recipient if recipient and '@' in recipient else 'customer@example.com'
        
        # Генерируем лицензию
        await update.message.reply_text("⏳ Генерация лицензии...")
        
        result = generate_license(
            hw_id=hw_id,
            days=days,
            start_date=start_date,
            email=email,
            recipient=recipient,
            comments=comments,
            verbose=False  # Не выводим в консоль
        )
        
        # Отправляем файл лицензии
        license_file = Path(result['license_path'])
        if license_file.exists():
            with open(license_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=license_file.name,
                    caption=(
                        f"✅ Лицензия успешно сгенерирована!\n\n"
                        f"📋 Hardware ID: `{result['hw_id']}`\n"
                        f"📅 Длительность: {result['days']} дней\n"
                        f"📆 Дата начала: {result['start_date'][:10]}\n"
                        f"📆 Дата окончания: {result['end_date'][:10]}\n"
                        f"💾 ID в БД: {result.get('recipient_id', 'N/A')}"
                    ),
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text(
                f"❌ Файл лицензии не найден: {result['license_path']}"
            )
            
    except ValueError as e:
        await update.message.reply_text(f"❌ Ошибка в параметрах: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка генерации лицензии: {str(e)}")
        import traceback
        traceback.print_exc()


async def list_licenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /list_licenses - список лицензий"""
    
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    try:
        from license_database import LicenseDatabase
        
        db = LicenseDatabase()
        recipients = db.get_all_recipients()
        
        if not recipients:
            await update.message.reply_text("📋 База данных пуста.")
            return
        
        # Формируем сообщение
        message = f"📋 Всего лицензий: {len(recipients)}\n\n"
        
        for rec in recipients[:10]:  # Показываем первые 10
            hw_id = rec['hw_id'][:16]
            days = rec['days']
            recipient = rec.get('recipient', 'N/A') or 'N/A'
            start_date = rec.get('start_date', '')[:10] if rec.get('start_date') else 'N/A'
            
            message += (
                f"ID: {rec['id']}\n"
                f"HWID: `{hw_id}`\n"
                f"Дней: {days} | Контакт: {recipient}\n"
                f"Начало: {start_date}\n\n"
            )
        
        if len(recipients) > 10:
            message += f"... и еще {len(recipients) - 10} лицензий"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def search_license_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /search_license - поиск по HWID"""
    
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Использование: `/search_license <HWID>`",
            parse_mode='Markdown'
        )
        return
    
    try:
        from license_database import LicenseDatabase
        
        db = LicenseDatabase()
        hw_id = context.args[0].upper()
        recipients = db.search_by_hw_id(hw_id)
        
        if not recipients:
            await update.message.reply_text(f"❌ Лицензии с HWID `{hw_id}` не найдены.", parse_mode='Markdown')
            return
        
        message = f"🔍 Найдено лицензий: {len(recipients)}\n\n"
        
        for rec in recipients:
            message += (
                f"ID: {rec['id']}\n"
                f"HWID: `{rec['hw_id']}`\n"
                f"Дней: {rec['days']}\n"
                f"Контакт: {rec.get('recipient', 'N/A') or 'N/A'}\n"
                f"Начало: {rec.get('start_date', '')[:10] if rec.get('start_date') else 'N/A'}\n"
                f"Окончание: {rec.get('end_date', '')[:10] if rec.get('end_date') else 'N/A'}\n\n"
            )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация команд
    application.add_handler(CommandHandler("generate_license", generate_license_command))
    application.add_handler(CommandHandler("list_licenses", list_licenses_command))
    application.add_handler(CommandHandler("search_license", search_license_command))
    
    # Запуск бота
    print("🤖 Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
```

### Команды бота

#### `/generate_license <HWID> <DAYS> [START_DATE] [RECIPIENT] [COMMENTS]`
Генерирует новую лицензию и отправляет файл `.lic`

**Примеры:**
```
/generate_license 94EAA22C9EDB6FC7 30
/generate_license 94EAA22C9EDB6FC7 30 2024-02-01
/generate_license 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com
/generate_license 94EAA22C9EDB6FC7 30 2024-02-01 @telegram_user
/generate_license 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com Test license
```

#### `/list_licenses`
Показывает список всех лицензий из базы данных

#### `/search_license <HWID>`
Ищет лицензии по Hardware ID

### Установка зависимостей

```bash
pip install python-telegram-bot
```

---

## 💾 База данных

### Структура

База данных SQLite (`licenses.db`) содержит таблицу `license_recipients`:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER | Уникальный ID записи |
| `hw_id` | TEXT | Hardware ID получателя |
| `days` | INTEGER | Количество дней лицензии |
| `start_date` | TEXT | Дата начала (ISO формат) |
| `end_date` | TEXT | Дата окончания (ISO формат) |
| `recipient` | TEXT | Контактная информация получателя |
| `comments` | TEXT | Комментарии |
| `license_file` | TEXT | Путь к файлу лицензии |
| `created_at` | TEXT | Дата создания записи |
| `updated_at` | TEXT | Дата последнего обновления |

### Работа с базой данных

```python
from license_database import LicenseDatabase
from datetime import datetime, timedelta

db = LicenseDatabase()

# Добавить получателя
recipient_id = db.add_recipient(
    hw_id='94EAA22C9EDB6FC7',
    days=30,
    start_date=datetime(2024, 2, 1),
    end_date=datetime(2024, 3, 3),
    recipient='customer@example.com',
    comments='Test license',
    license_file='path/to/license.lic'
)

# Получить всех получателей
all_recipients = db.get_all_recipients()

# Поиск по HWID
recipients = db.search_by_hw_id('94EAA22C9EDB6FC7')

# Получить по ID
recipient = db.get_recipient(recipient_id)

# Обновить запись
db.update_recipient(
    recipient_id=recipient_id,
    recipient='new_email@example.com',
    comments='Updated comment'
)

# Удалить запись
db.delete_recipient(recipient_id)
```

---

## 📅 Логика работы с датами

### Расчет даты начала

- **Если дата начала не указана**: используется текущая дата + 1 день (завтра, 00:00:00)
- **Если дата начала указана**: используется указанная дата (00:00:00)

### Расчет даты окончания

**Формула:** `дата_окончания = дата_начала + (количество_дней + 1) день`

**Время:** всегда 00:00:00

### Примеры

#### Пример 1: Лицензия на 30 дней без указания даты начала
- Сегодня: 2024-01-15
- Дата начала: 2024-01-16 00:00:00 (завтра)
- Дата окончания: 2024-02-16 00:00:00 (начало 31-го дня)

#### Пример 2: Лицензия на 30 дней с датой начала
- Дата начала: 2024-02-01 00:00:00
- Дата окончания: 2024-03-03 00:00:00 (начало 31-го дня)

#### Пример 3: Лицензия на 7 дней
- Дата начала: 2024-01-01 00:00:00
- Дата окончания: 2024-01-09 00:00:00 (начало 8-го дня)

**Важно:** Лицензия действует **до** указанной даты окончания (не включительно). То есть лицензия на 30 дней действует 30 полных дней, а истекает в 00:00:00 (N+1)-го дня.

---

## 📝 Примеры использования

### Пример 1: Генерация лицензии для нового клиента

**Сценарий:** Клиент прислал HWID и запросил лицензию на 30 дней.

**Через GUI:**
1. Открыть GUI приложение
2. Ввести HWID: `94EAA22C9EDB6FC7`
3. Указать дни: `30`
4. Ввести контакт: `customer@example.com`
5. Нажать "Сгенерировать лицензию"
6. Отправить файл `.lic` клиенту

**Через командную строку:**
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 "" customer@example.com "New customer"
```

**Через Python:**
```python
result = generate_license(
    hw_id='94EAA22C9EDB6FC7',
    days=30,
    recipient='customer@example.com',
    comments='New customer'
)
# Отправить result['license_path'] клиенту
```

### Пример 2: Генерация лицензии с конкретной датой начала

**Сценарий:** Лицензия должна начать действовать с 1 февраля 2024.

**Через командную строку:**
```bash
python license_generator/generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com
```

**Через Python:**
```python
from datetime import datetime

result = generate_license(
    hw_id='94EAA22C9EDB6FC7',
    days=30,
    start_date=datetime(2024, 2, 1),
    recipient='customer@example.com'
)
```

### Пример 3: Массовая генерация лицензий

```python
from generate_license import generate_license

customers = [
    {'hw_id': '94EAA22C9EDB6FC7', 'days': 30, 'recipient': 'customer1@example.com'},
    {'hw_id': 'A1B2C3D4E5F6G7H8', 'days': 60, 'recipient': 'customer2@example.com'},
    {'hw_id': '1234567890ABCDEF', 'days': 90, 'recipient': '@telegram_user'},
]

for customer in customers:
    result = generate_license(
        hw_id=customer['hw_id'],
        days=customer['days'],
        recipient=customer['recipient'],
        verbose=False
    )
    print(f"✅ Лицензия создана для {customer['recipient']}: {result['license_path']}")
```

### Пример 4: Интеграция в веб-приложение (Flask)

```python
from flask import Flask, request, send_file
from generate_license import generate_license
from datetime import datetime

app = Flask(__name__)

@app.route('/api/generate_license', methods=['POST'])
def api_generate_license():
    data = request.json
    
    try:
        result = generate_license(
            hw_id=data['hw_id'],
            days=data['days'],
            start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else None,
            recipient=data.get('recipient'),
            comments=data.get('comments'),
            verbose=False
        )
        
        return {
            'success': True,
            'license_path': result['license_path'],
            'recipient_id': result['recipient_id']
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

@app.route('/api/download_license/<int:recipient_id>', methods=['GET'])
def api_download_license(recipient_id):
    from license_database import LicenseDatabase
    
    db = LicenseDatabase()
    recipient = db.get_recipient(recipient_id)
    
    if not recipient or not recipient.get('license_file'):
        return {'error': 'License not found'}, 404
    
    return send_file(recipient['license_file'], as_attachment=True)
```

---

## ❓ FAQ

### Q: Что такое Hardware ID и как его получить?

**A:** Hardware ID - это уникальный идентификатор оборудования компьютера. Получить его можно:

1. **Через скрипт:**
   ```bash
   python scripts/activate_premium.py
   ```
   Покажет Short HWID (16 символов) - именно его нужно использовать.

2. **Через GUI генератора:**
   - Нажать кнопку "Получить HWID"
   - Будет показан Short HWID текущего компьютера

3. **Программно:**
   ```python
   from license_generator.hardware_id import get_short_hardware_id
   hw_id = get_short_hardware_id()
   ```

### Q: Почему HWID обрезается до 16 символов?

**A:** При проверке лицензии сравниваются только первые 16 символов для совместимости. Полный HWID - это 64-символьный SHA256 хэш, но для лицензий достаточно первых 16 символов.

### Q: Можно ли использовать полный HWID (64 символа)?

**A:** Да, можно. Скрипт автоматически обрежет его до 16 символов. Но рекомендуется использовать Short HWID (16 символов) для удобства.

### Q: Что происходит, если дата начала не указана?

**A:** Используется текущая дата + 1 день (завтра, 00:00:00). Это сделано для того, чтобы лицензия начинала действовать с завтрашнего дня, а не с сегодняшнего.

### Q: Как рассчитывается дата окончания?

**A:** Дата окончания = дата начала + (количество дней + 1) день, время 00:00:00.

Например, лицензия на 30 дней с 2024-02-01 действует до 2024-03-03 00:00:00 (начало 31-го дня).

### Q: Можно ли указать email, telegram и другую информацию в поле recipient?

**A:** Да! Поле `recipient` принимает любую текстовую информацию:
- Email: `customer@example.com`
- Telegram nickname: `@telegram_user`
- Telegram ID: `123456789`
- Имя: `Иван Иванов`
- Любая другая информация

### Q: Где хранятся сгенерированные лицензии?

**A:** Все лицензии сохраняются в папке `license_generator/generated_licenses/`

### Q: Можно ли использовать генератор из другого проекта?

**A:** Да, можно импортировать функцию `generate_license` из любого Python проекта, добавив путь к `license_generator` в `sys.path`.

### Q: Нужно ли сохранять базу данных в системе контроля версий?

**A:** Нет, база данных `licenses.db` содержит конфиденциальную информацию и не должна попадать в публичный репозиторий. Добавьте её в `.gitignore`.

### Q: Как проверить, что лицензия работает?

**A:** Поместите файл `.lic` в корень проекта InfoBot и запустите бота. Лицензия будет автоматически проверена при запуске.

---

## 🔒 Безопасность

### Важные замечания:

1. ⚠️ **Папка `license_generator/` НЕ должна попадать в публичную версию проекта**
2. ⚠️ **База данных `licenses.db` содержит конфиденциальную информацию**
3. ⚠️ **Файлы лицензий `.lic` содержат зашифрованные данные**
4. ⚠️ **При использовании в Telegram боте добавьте проверку прав доступа**

### Рекомендации:

- Храните базу данных в защищенном месте
- Регулярно делайте резервные копии базы данных
- Ограничьте доступ к генератору лицензий только авторизованным пользователям
- Используйте HTTPS для передачи лицензий через веб-API

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи в консоли
2. Убедитесь, что все зависимости установлены
3. Проверьте формат параметров командной строки
4. Убедитесь, что Hardware ID указан правильно (16 символов)

---

## 📄 Лицензия

Этот генератор лицензий является частью проекта InfoBot AI Premium и предназначен только для авторизованного использования.

---

**Версия документации:** 1.0  
**Дата обновления:** 2024

