# 📋 Система Ротации Логов

## Описание

Универсальная система автоматической ротации логов с ограничением размера файла до **10 МБ**. При превышении лимита файл автоматически перезаписывается, предотвращая заполнение диска и зависание системы.

## Возможности

✅ **Автоматическая ротация** - При достижении 10MB файл перезаписывается  
✅ **Потокобезопасность** - Работает корректно в многопоточных приложениях  
✅ **UTF-8 кодировка** - Правильная обработка всех символов  
✅ **Простая интеграция** - Легко подключается к любому модулю  
✅ **Производительность** - Минимальные накладные расходы  

## Структура

### Основной модуль

```
utils/log_rotation.py
```

**Ключевые компоненты:**

1. **`RotatingFileHandlerWithSizeLimit`** - Обработчик логов с автоматической ротацией
2. **`setup_logger_with_rotation()`** - Настройка логгера с ротацией
3. **Готовые логгеры для всех компонентов системы**

### Интегрированные модули

| Файл | Логгер | Описание |
|------|--------|----------|
| `scripts/sync/ema_legacy_removed.py` | OptimalEMA | Исторический EMA-модуль (legacy) |
| `protector.py` | Protector | Мониторинг системы |
| `app/telegram_notifier.py` | TelegramNotifier | Уведомления Telegram |
| `bots_modules/imports_and_globals.py` | Bots | Основная система ботов |
| `app.py` | AppLog_* | Flask приложение |

## Использование

### Для новых модулей

```python
from utils.log_rotation import setup_logger_with_rotation

# Создаем логгер с ротацией
logger = setup_logger_with_rotation(
    name='MyModule',
    log_file='logs/mymodule.log',
    level=logging.INFO,
    max_bytes=10 * 1024 * 1024,  # 10MB
    format_string='%(asctime)s - %(levelname)s - %(message)s'
)

# Используем логгер
logger.info("Сообщение в лог")
logger.error("Ошибка!")
```

### Готовые логгеры

```python
from utils.log_rotation import (
    get_ema_legacy_logger,
    get_protector_logger,
    get_telegram_logger,
    get_bots_logger,
    get_app_logger
)

logger = get_ema_legacy_logger()
logger.info("Запуск legacy EMA логгера...")
```

## Параметры

### RotatingFileHandlerWithSizeLimit

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `filename` | str | - | Путь к файлу лога |
| `max_bytes` | int | 10485760 | Максимальный размер (10MB) |
| `backup_count` | int | 0 | Количество backup файлов (0 = перезапись) |
| `encoding` | str | 'utf-8' | Кодировка файла |

### setup_logger_with_rotation

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `name` | str | - | Имя логгера |
| `log_file` | str | - | Путь к файлу лога |
| `level` | int | logging.INFO | Уровень логирования |
| `max_bytes` | int | 10485760 | Максимальный размер (10MB) |
| `format_string` | str | None | Формат сообщений |

## Принцип работы

### 1. Создание логгера

```python
logger = setup_logger_with_rotation(
    name='MyLogger',
    log_file='logs/mylog.log',
    max_bytes=10 * 1024 * 1024
)
```

### 2. Запись логов

- Логи пишутся в файл с UTF-8 кодировкой
- Размер файла проверяется перед каждой записью
- При превышении лимита файл перезаписывается

### 3. Ротация

```python
def doRollover(self):
    """Переопределенная ротация"""
    # 1. Закрываем файл
    if self.stream:
        self.stream.close()
    
    # 2. Удаляем старый файл
    if os.path.exists(self.baseFilename):
        os.remove(self.baseFilename)
    
    # 3. Открываем новый файл
    self.stream = self._open()
```

## Преимущества перед стандартным logging

| Особенность | Стандартный logging | Наша система |
|-------------|---------------------|--------------|
| Ограничение размера | ❌ Нет | ✅ 10MB |
| Автоматическая ротация | ❌ Нет | ✅ Да |
| Перезапись файла | ❌ Только дополнение | ✅ Перезапись при превышении |
| Потокобезопасность | ⚠️ Частично | ✅ Полная |
| UTF-8 кодировка | ⚠️ Зависит от системы | ✅ Всегда |

## Дополнительные функции

### Получение размера лога

```python
from utils.log_rotation import get_log_file_size

size = get_log_file_size('logs/ema_legacy.log')
print(f"Размер файла: {size} байт ({size / 1024 / 1024:.2f} MB)")
```

### Очистка старых логов

```python
from utils.log_rotation import cleanup_old_logs

# Удаляет логи старше 7 дней
cleanup_old_logs(logs_dir='logs', max_age_days=7)
```

## Примеры интеграции

### legacy_ema_removed.py

```python
from utils.log_rotation import setup_logger_with_rotation

def setup_logging():
    logger = setup_logger_with_rotation(
        name='OptimalEMA',
        log_file='logs/ema_legacy.log',
        level=logging.INFO,
        max_bytes=10 * 1024 * 1024,
        format_string='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Добавляем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(console_handler)
    
    return logger
```

### protector.py

```python
from utils.log_rotation import setup_logger_with_rotation

file_logger = setup_logger_with_rotation(
    name='Protector',
    log_file='logs/protector.log',
    level=logging.INFO,
    max_bytes=10 * 1024 * 1024
)

def log(message, level="INFO"):
    # Вывод в консоль с цветами
    print(formatted_message)
    
    # Запись в файл с ротацией
    log_level = getattr(logging, level, logging.INFO)
    file_logger.log(log_level, message)
```

### app.py

```python
from utils.log_rotation import RotatingFileHandlerWithSizeLimit

_log_file_handlers = {}

def log_to_file(filename, data):
    log_path = f'logs/{filename}'
    
    if log_path not in _log_file_handlers:
        handler = RotatingFileHandlerWithSizeLimit(
            filename=log_path,
            max_bytes=10 * 1024 * 1024,
            backup_count=0,
            encoding='utf-8'
        )
        logger = logging.getLogger(f'AppLog_{filename}')
        logger.addHandler(handler)
        _log_file_handlers[log_path] = logger
    
    logger = _log_file_handlers[log_path]
    logger.info(f"\n=== {timestamp} ===\n{data}\n")
```

## Мониторинг

### Проверка размера логов

```bash
# Windows PowerShell
Get-ChildItem logs/*.log | Select-Object Name, @{Name="Size(MB)";Expression={[math]::Round($_.Length/1MB, 2)}}

# Linux/Mac
ls -lh logs/*.log
```

### Тестирование ротации

```python
# Запустите test в utils/log_rotation.py
python -m utils.log_rotation
```

## FAQ

**Q: Что происходит со старыми логами?**  
A: При превышении 10MB файл полностью перезаписывается. Старые данные теряются.

**Q: Можно ли сохранить backup файлы?**  
A: Да, установите `backup_count=3` для сохранения последних 3 версий.

**Q: Как изменить максимальный размер?**  
A: Измените параметр `max_bytes` при создании логгера.

**Q: Работает ли в многопоточных приложениях?**  
A: Да, используется `threading.Lock()` для потокобезопасности.

**Q: Что делать если лог растет очень быстро?**  
A: Уменьшите `max_bytes` или измените уровень логирования на WARNING/ERROR.

## Решение проблем

### Ошибка "Файл занят другим процессом"

**Проблема:** `[WinError 32] Процесс не может получить доступ к файлу`

**Решение:** Система автоматически использует блокировки и retry механизм

### Лог не перезаписывается

**Проверьте:**
1. Правильный ли `max_bytes` (должен быть > текущего размера)
2. Есть ли права на запись в директорию
3. Используется ли `RotatingFileHandlerWithSizeLimit`

### Потеря кодировки

**Решение:** Всегда указывайте `encoding='utf-8'` при создании handler

## Обновления

**v1.0.0** - 2025-10-15
- ✅ Первая версия системы ротации логов
- ✅ Интеграция во все модули системы
- ✅ Автоматическая перезапись при 10MB
- ✅ Потокобезопасность
- ✅ UTF-8 кодировка

## Дальнейшее развитие

- [ ] Сжатие старых логов (gzip)
- [ ] Отправка в удаленное хранилище
- [ ] Web интерфейс для просмотра логов
- [ ] Поиск по логам
- [ ] Статистика по логам

---

**Автор:** AI Assistant  
**Дата:** 15.10.2025  
**Версия:** 1.0.0
