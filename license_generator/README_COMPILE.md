# Компиляция модулей лицензирования

Модули проверки лицензии должны быть скомпилированы в `.pyc` для защиты исходного кода.

## Структура файлов

### Исходники (в `license_generator/source/`):
- `license_checker_source.py` - проверка лицензии
- `hardware_id_source.py` - генерация hardware ID

### Скомпилированные файлы:
- `bot_engine/ai/license_checker.pyc` - скомпилированный модуль проверки лицензии
- `bot_engine/ai/hardware_id_source.pyc` - скомпилированный модуль hardware ID (fallback для license_checker)
- `scripts/hardware_id.pyc` - скомпилированный модуль hardware ID (используется activate_premium.py и license_checker)

## Компиляция

### Компиляция всех модулей:
```bash
python license_generator/compile_all.py
```

### Компиляция отдельных модулей:
```bash
# Только license_checker
python license_generator/compile_license_checker.py

# Только hardware_id
python license_generator/compile_hardware_id.py
```

## Важно

1. **Исходники должны оставаться в `license_generator/source/`** - они не попадают в продакшн
2. **Скомпилированные `.pyc` файлы** должны быть:
   - `bot_engine/ai/` - для использования в коде (license_checker, hardware_id_source как fallback)
   - `scripts/` - для activate_premium.py (hardware_id.pyc)
3. **После изменения исходников** нужно перекомпилировать модули
4. **`.pyc` файлы добавлены в `.gitignore`** с исключениями - они должны быть в репозитории
5. **hardware_id.pyc компилируется в два места**: `bot_engine/ai/` и `scripts/` для совместимости

## Проверка

После компиляции можно проверить работу:

```python
from bot_engine.ai.license_checker import get_license_checker
from bot_engine.ai import hardware_id_source

checker = get_license_checker()
print("License valid:", checker.is_valid())

hw_id = hardware_id_source.get_hardware_id()
print("Hardware ID:", hw_id[:16])
```

