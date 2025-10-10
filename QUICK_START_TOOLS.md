# Инструменты для предотвращения ошибок

## Быстрый старт

### 1. Проверка перед запуском
```bash
python check_syntax.py
```

### 2. Автоисправление отступов
```bash
python format_code.py
```

### 3. Проверка + Запуск
```bash
python check_syntax.py && python bots.py
```

## Настройка IDE (Cursor)

1. Откройте настройки (Ctrl+,)
2. Найдите "Format On Save"
3. Включите опцию
4. Установите форматтер: `autopep8`

## Установка pre-commit (опционально)

```bash
pip install pre-commit
pre-commit install
```

Теперь код будет автоматически проверяться перед каждым коммитом.

## Что делать при ошибках отступов

1. **Быстрое исправление:**
   ```bash
   autopep8 --in-place --aggressive --aggressive bots.py
   ```

2. **Проверка:**
   ```bash
   python -m py_compile bots.py
   ```

3. **Запуск:**
   ```bash
   python bots.py
   ```

## Долгосрочное решение

Файл `bots.py` слишком большой (7600+ строк). Рекомендуется разбить на модули:
- См. `docs/CODE_QUALITY.md` для деталей

