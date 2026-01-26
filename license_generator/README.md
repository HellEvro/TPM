# LICENSE GENERATOR - Система лицензирования InfoBot

## ВАЖНО: Эта папка НЕ попадает в публичную версию!

---

## Архитектура защиты

```
ЗАЩИЩЁННОЕ ЯДРО (.pyc):
├── bot_engine/ai/ai_manager.pyc       ← Логика AI менеджера
├── bot_engine/ai/license_checker.pyc  ← Проверка лицензий
├── bot_engine/ai/hardware_id_source.pyc
└── bot_engine/ai/_ai_launcher.pyc

AI МОДУЛИ (обычные .py):
├── bot_engine/ai/smart_money_features.py
├── bot_engine/ai/lstm_predictor.py
├── bot_engine/ai/transformer_predictor.py
├── bot_engine/ai/bayesian_optimizer.py
├── bot_engine/ai/drift_detector.py
├── bot_engine/ai/ensemble.py
├── bot_engine/ai/monitoring.py
├── bot_engine/ai/rl_agent.py
├── bot_engine/ai/sentiment.py
├── bot_engine/ai/pattern_detector.py
└── bot_engine/ai/ai_integration.py
```

---

## Как работает защита

1. **Ядро** (ai_manager.pyc, license_checker.pyc) — скомпилировано
2. **При использовании AI** — ядро проверяет лицензию через `check_premium_license()`
3. **Если лицензия ОК** — AI функции работают
4. **Если нет лицензии** — AI отключен

### ВАЖНО:
- **Проверка лицензии ТОЛЬКО в ядре**
- **AI модули — обычные .py файлы** (редактируются на лету)
- **НЕ компилировать AI модули в .pyc** — это лишняя работа

---

## Компиляция ядра

Когда нужно обновить защищённое ядро:

```bash
cd license_generator
python compile_all.py
```

Это скомпилирует:
- `ai_manager_source.py` → `ai_manager.pyc`
- `license_checker.py` → `license_checker.pyc`
- `hardware_id_source.py` → `hardware_id_source.pyc`
- `_ai_launcher_source.py` → `_ai_launcher.pyc`

---

## Генерация лицензии

```bash
cd license_generator
python generate_license.py <HWID> <DAYS>
```

Пример:
```bash
python generate_license.py ABC123DEF456 365
```

---

## Структура папки

```
license_generator/
├── source/                     # Исходники ядра (СЕКРЕТНО!)
│   ├── ai_manager_source.py
│   ├── license_checker.py
│   └── hardware_id_source.py
├── compile_all.py              # Компиляция всего ядра
├── compile_ai_manager.py       # Компиляция ai_manager
├── compile_license_checker.py  # Компиляция license_checker
├── generate_license.py         # Генератор лицензий
├── license_manager.py          # Менеджер лицензий
├── hardware_id.py              # Получение HWID
├── license_types.py            # Типы лицензий
└── README.md                   # Этот файл
```

---

## Что НЕ нужно делать

1. **НЕ компилировать AI модули** (smart_money_features.py и др.) — они обычные .py
2. **НЕ добавлять проверку лицензии в AI модули** — проверка только в ядре
3. **НЕ удалять .py файлы AI** — они нужны для разработки

---

## Проверка лицензии в коде

Если нужно проверить лицензию в своём коде:

```python
from bot_engine.ai import check_premium_license

if check_premium_license():
    # Премиум функции доступны
    pass
else:
    # Только базовые функции
    pass
```

---

## Обновление исходников ядра

Если изменил `ai_manager.py`, обнови исходник:

```bash
cp bot_engine/ai/ai_manager.py license_generator/source/ai_manager_source.py
python license_generator/compile_all.py
```

---

**Система готова к работе!**
