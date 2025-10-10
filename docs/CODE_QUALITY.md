# Рекомендации по качеству кода

## Проблема
Файл `bots.py` имеет 7600+ строк, что затрудняет поддержку и приводит к ошибкам отступов.

## Решения

### 1. Автоматическое форматирование (РЕКОМЕНДУЕТСЯ)

**Перед каждым коммитом:**
```bash
# Форматирование с autopep8
python format_code.py

# ИЛИ с black (более строгий)
black bots.py --line-length 120

# Проверка синтаксиса
python check_syntax.py
```

### 2. Настройка IDE (Cursor/VS Code)

**Установите расширения:**
- Python (Microsoft)
- Pylance
- autopep8

**Настройки (settings.json):**
```json
{
  "editor.formatOnSave": true,
  "python.formatting.provider": "autopep8",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "editor.rulers": [120],
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true
}
```

### 3. Pre-commit hooks (автоматическая проверка)

```bash
pip install pre-commit
pre-commit install
```

Теперь перед каждым коммитом код будет автоматически проверяться и форматироваться.

### 4. Рефакторинг (долгосрочное решение)

Разбить `bots.py` на модули:

```
bot_service/
├── __init__.py
├── api/
│   ├── endpoints.py      # API endpoints
│   ├── health.py         # Health checks
│   └── config.py         # Configuration API
├── core/
│   ├── bot.py           # NewTradingBot class
│   ├── filters.py       # RSI filters, ExitScam
│   ├── maturity.py      # Maturity checks
│   └── signals.py       # Signal processing
├── workers/
│   ├── auto_save.py     # Auto save worker
│   └── rsi_loader.py    # RSI loading
└── utils/
    ├── rsi.py           # RSI calculations
    └── ema.py           # EMA calculations
```

### 5. Быстрые команды

**Проверка перед запуском:**
```bash
# Проверка синтаксиса
python -m py_compile bots.py

# Форматирование
autopep8 --in-place --aggressive --aggressive bots.py

# Проверка стиля
flake8 bots.py --max-line-length=120 --ignore=E501,W503
```

## Текущие инструменты

- ✅ `format_code.py` - автоформатирование
- ✅ `check_syntax.py` - проверка синтаксиса
- ✅ `.editorconfig` - настройки IDE
- ✅ `.pre-commit-config.yaml` - автопроверка при коммите

## Использование

```bash
# Перед изменениями
python check_syntax.py

# После изменений
python format_code.py
python check_syntax.py

# Запуск сервиса
python bots.py
```

