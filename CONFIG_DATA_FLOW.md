# ПОЛНЫЙ ПУТЬ ДАННЫХ КОНФИГУРАЦИИ

## 📋 СОДЕРЖАНИЕ
1. [СОХРАНЕНИЕ: UI → Backend → bot_config.py](#сохранение-ui--backend--bot_configpy)
2. [ЗАГРУЗКА: bot_config.py → Backend → UI](#загрузка-bot_configpy--backend--ui)
3. [Ключевые точки синхронизации](#ключевые-точки-синхронизации)

---

## 🔄 СОХРАНЕНИЕ: UI → Backend → bot_config.py

### Шаг 1: UI - Сбор данных из формы
**Файл:** `InfoBot_Public/static/js/managers/bots_manager.js`

**Функция:** `collectConfigurationData()` (строка ~6021)
```javascript
// 1. Берет базовые данные из cachedAutoBotConfig (кэш из последней загрузки)
const autoBotConfig = JSON.parse(JSON.stringify(this.cachedAutoBotConfig));

// 2. Применяет изменения из DOM элементов (только если они отличаются от originalConfig)
applyDomChange('trailing_stop_activation', () => {
    const val = parseFloat(trailingStopActivationEl.value);
    return Number.isFinite(val) ? val : undefined;
});
// ... аналогично для других полей

// 3. Возвращает объект { autoBot: {...}, system: {...} }
return { autoBot: autoBotConfig, system: systemConfig };
```

**Ключевые поля:**
- `trailing_stop_activation` - из DOM элемента `#trailingStopActivation`
- `trailing_stop_distance` - из DOM элемента `#trailingStopDistance`
- `break_even_trigger` - из DOM элемента `#breakEvenTrigger`
- `avoid_down_trend` - из DOM элемента `#avoidDownTrend` (checkbox.checked)
- `avoid_up_trend` - из DOM элемента `#avoidUpTrend` (checkbox.checked)

---

### Шаг 2: UI - Отправка на сервер
**Файл:** `InfoBot_Public/static/js/managers/bots_manager.js`

**Функция:** `sendConfigUpdate(endpoint, data, sectionName)` (строка ~6669)
```javascript
// 1. Фильтрует только измененные параметры (сравнивает с originalConfig)
const filteredData = this.filterChangedParams(data);

// 2. Отправляет POST запрос на /api/bots/auto-bot
const response = await fetch(`${this.BOTS_SERVICE_URL}/api/bots/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(filteredData)  // ← Только измененные параметры
});

// 3. После успешного сохранения:
//    - Обновляет cachedAutoBotConfig
//    - Обновляет originalConfig
//    - Вызывает updateFormFieldsFromConfig()
//    - Через 1 секунду вызывает loadConfigurationData() для перезагрузки с сервера
```

**URL:** `POST http://localhost:5001/api/bots/auto-bot`

**Тело запроса (пример):**
```json
{
  "trailing_stop_activation": 31,
  "trailing_stop_distance": 11,
  "trailing_take_distance": 0.51,
  "trend_detection_enabled": false
}
```

---

### Шаг 3: Backend - Получение данных
**Файл:** `bots_modules/api_endpoints.py`

**Функция:** `auto_bot_config()` (строка ~2188)
**Метод:** `POST`

```python
# 1. Парсит JSON из запроса
data = request.get_json()  # { "trailing_stop_activation": 31, ... }

# 2. Сохраняет старую конфигурацию для сравнения
with bots_data_lock:
    old_config = bots_data['auto_bot_config'].copy()

# 3. Обновляет bots_data новыми значениями
with bots_data_lock:
    for key, value in data.items():
        if key in bots_data['auto_bot_config']:
            bots_data['auto_bot_config'][key] = value  # ← Обновление в памяти

# 4. Вызывает сохранение в файл
save_result = save_auto_bot_config()  # ← Сохраняет в bot_config.py
```

---

### Шаг 4: Backend - Сохранение в файл
**Файл:** `bots_modules/sync_and_cache.py`

**Функция:** `save_auto_bot_config()` (строка ~575)

```python
# 1. Берет данные из bots_data
with bots_data_lock:
    config_data = bots_data['auto_bot_config'].copy()  # ← Из памяти

# 2. Сохраняет в bot_config.py через config_writer
from bots_modules.config_writer import save_auto_bot_config_to_py
success = save_auto_bot_config_to_py(config_data)

# 3. После успешного сохранения:
#    - Обновляет bots_data из сохраненных данных
#    - Перезагружает модуль bot_config
#    - Сбрасывает _last_mtime = 0
#    - Вызывает load_auto_bot_config() для перезагрузки из файла
```

---

### Шаг 5: Backend - Запись в bot_config.py
**Файл:** `bots_modules/config_writer.py`

**Функция:** `save_auto_bot_config_to_py(config)` (строка ~11)

```python
# 1. Читает файл bot_engine/bot_config.py
with open('bot_engine/bot_config.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 2. Находит блок DEFAULT_AUTO_BOT_CONFIG = {...}
#    (строки ~67-126)

# 3. Обновляет значения в блоке:
#    'trailing_stop_activation': 20 → 31
#    'trailing_stop_distance': 5 → 11
#    и т.д.

# 4. Записывает обратно в файл
with open('bot_engine/bot_config.py', 'w', encoding='utf-8') as f:
    f.writelines(updated_lines)

# 5. Проверяет сохранение - перезагружает модуль и читает значения
importlib.reload(bot_engine.bot_config)
from bot_engine.bot_config import DEFAULT_AUTO_BOT_CONFIG
# Логирует: trailing_stop_activation: 31, trailing_stop_distance: 11, ...
```

**Файл:** `bot_engine/bot_config.py`
```python
DEFAULT_AUTO_BOT_CONFIG = {
    'trailing_stop_activation': 31,  # ← Обновлено!
    'trailing_stop_distance': 11,    # ← Обновлено!
    'break_even_trigger': 20,
    'avoid_down_trend': False,
    'avoid_up_trend': False,
    ...
}
```

---

### Шаг 6: Backend - Перезагрузка модуля
**Файл:** `bots_modules/sync_and_cache.py`

**Функция:** `save_auto_bot_config()` → вызывает `load_auto_bot_config()` (строка ~648-656)

```python
# После сохранения в файл:

# 1. Перезагружает модуль bot_config
import bot_engine.bot_config
importlib.reload(bot_engine.bot_config)

# 2. Сбрасывает кэш времени модификации
load_auto_bot_config._last_mtime = 0

# 3. Перезагружает конфигурацию из файла
load_auto_bot_config()  # ← Читает из bot_config.py и обновляет bots_data
```

---

### Шаг 7: Backend - Обновление в памяти
**Файл:** `bots_modules/imports_and_globals.py`

**Функция:** `load_auto_bot_config()` (строка ~566)

```python
# 1. Перезагружает модуль (если файл изменился или _last_mtime == 0)
if current_mtime > load_auto_bot_config._last_mtime or load_auto_bot_config._last_mtime == 0:
    importlib.reload(bot_engine.bot_config)

# 2. Импортирует DEFAULT_AUTO_BOT_CONFIG из перезагруженного модуля
from bot_engine.bot_config import DEFAULT_AUTO_BOT_CONFIG

# 3. Копирует конфигурацию
merged_config = DEFAULT_AUTO_BOT_CONFIG.copy()

# 4. Обновляет bots_data в памяти
with bots_data_lock:
    bots_data['auto_bot_config'] = merged_config  # ← Обновление в памяти!
```

---

## 📥 ЗАГРУЗКА: bot_config.py → Backend → UI

### Шаг 1: UI - Запрос конфигурации
**Файл:** `InfoBot_Public/static/js/managers/bots_manager.js`

**Функция:** `loadConfigurationData()` (строка ~5133)

```javascript
// 1. Добавляет cache-busting параметр для предотвращения кэширования
const cacheBuster = `_t=${Date.now()}`;

// 2. Отправляет GET запрос на /api/bots/auto-bot
const autoBotResponse = await fetch(`${this.BOTS_SERVICE_URL}/api/bots/auto-bot?${cacheBuster}`, {
    method: 'GET',
    cache: 'no-store',
    headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }
});

// 3. Парсит ответ
const autoBotData = await autoBotResponse.json();
// autoBotData = { success: true, config: { trailing_stop_activation: 31, ... } }

// 4. Вызывает populateConfigurationForm()
this.populateConfigurationForm({
    autoBot: autoBotData.config,
    system: systemData.config
});
```

**URL:** `GET http://localhost:5001/api/bots/auto-bot?_t=1234567890`

---

### Шаг 2: Backend - Принудительная перезагрузка модуля
**Файл:** `bots_modules/api_endpoints.py`

**Функция:** `auto_bot_config()` (строка ~2188)
**Метод:** `GET`

```python
if request.method == 'GET':
    # ✅ КРИТИЧНО: Принудительно перезагружаем модуль перед возвратом данных
    
    # 1. Перезагружает модуль bot_config
    if 'bot_engine.bot_config' in sys.modules:
        import bot_engine.bot_config
        importlib.reload(bot_engine.bot_config)
    
    # 2. Сбрасывает кэш времени модификации
    if hasattr(load_auto_bot_config, '_last_mtime'):
        load_auto_bot_config._last_mtime = 0  # ← Принудительная перезагрузка!
    
    # 3. Загружает конфигурацию из перезагруженного модуля
    from bots_modules.imports_and_globals import load_auto_bot_config
    load_auto_bot_config()  # ← Читает из bot_config.py и обновляет bots_data
    
    # 4. Берет данные из bots_data
    with bots_data_lock:
        config = bots_data['auto_bot_config'].copy()  # ← Свежие данные из файла!
    
    # 5. Логирует значения (INFO уровень для отладки)
    logger.info(f"[CONFIG_API] 📤 Возвращаем конфигурацию в UI:")
    logger.info(f"  trailing_stop_activation: {config.get('trailing_stop_activation')}")
    logger.info(f"  trailing_stop_distance: {config.get('trailing_stop_distance')}")
    # ...
    
    # 6. Возвращает JSON
    return jsonify({
        'success': True,
        'config': config  # ← Данные из bot_config.py через bots_data
    })
```

---

### Шаг 3: Backend - Загрузка из bot_config.py
**Файл:** `bots_modules/imports_and_globals.py`

**Функция:** `load_auto_bot_config()` (строка ~566)

```python
# 1. Проверяет время модификации файла
config_file_path = 'bot_engine/bot_config.py'
current_mtime = os.path.getmtime(config_file_path)

# 2. Если _last_mtime == 0 или файл изменился - перезагружает модуль
if current_mtime > load_auto_bot_config._last_mtime or load_auto_bot_config._last_mtime == 0:
    importlib.reload(bot_engine.bot_config)  # ← Перезагрузка!
    load_auto_bot_config._last_mtime = current_mtime

# 3. Импортирует DEFAULT_AUTO_BOT_CONFIG
from bot_engine.bot_config import DEFAULT_AUTO_BOT_CONFIG

# 4. Копирует конфигурацию
merged_config = DEFAULT_AUTO_BOT_CONFIG.copy()
# merged_config = { 'trailing_stop_activation': 31, 'trailing_stop_distance': 11, ... }

# 5. Обновляет bots_data
with bots_data_lock:
    bots_data['auto_bot_config'] = merged_config  # ← Обновление в памяти!
```

---

### Шаг 4: UI - Заполнение формы
**Файл:** `InfoBot_Public/static/js/managers/bots_manager.js`

**Функция:** `populateConfigurationForm(config)` (строка ~5211)

```javascript
// 1. Извлекает данные из config
const autoBotConfig = config.autoBot || config;
const systemConfig = config.system || {};

// 2. Обновляет cachedAutoBotConfig
this.cachedAutoBotConfig = autoBotConfig;

// 3. Обновляет originalConfig (для отслеживания изменений)
this.originalConfig = {
    autoBot: JSON.parse(JSON.stringify(autoBotConfig))  // Глубокое копирование
};

// 4. Заполняет DOM элементы значениями из конфига
const trailingStopActivationEl = document.getElementById('trailingStopActivation');
if (trailingStopActivationEl) {
    const rawValue = autoBotConfig.trailing_stop_activation;  // 31
    // ... преобразование в число ...
    trailingStopActivationEl.value = finalValue;  // 31
}

const trailingStopDistanceEl = document.getElementById('trailingStopDistance');
if (trailingStopDistanceEl) {
    const rawValue = autoBotConfig.trailing_stop_distance;  // 11
    // ... преобразование в число ...
    trailingStopDistanceEl.value = finalValue;  // 11
}

const avoidDownTrendEl = document.getElementById('avoidDownTrend');
if (avoidDownTrendEl) {
    const rawValue = autoBotConfig.avoid_down_trend;  // false
    // ... преобразование в boolean ...
    avoidDownTrendEl.checked = shouldBeChecked;  // false
}

// ... аналогично для всех полей ...
```

---

## 🔑 КЛЮЧЕВЫЕ ТОЧКИ СИНХРОНИЗАЦИИ

### 1. `originalConfig` в UI
**Назначение:** Отслеживает, какие параметры были изменены пользователем
**Обновляется:**
- При загрузке конфигурации из API: `this.originalConfig = { autoBot: {...} }`
- После сохранения: обновляется измененными значениями

### 2. `cachedAutoBotConfig` в UI
**Назначение:** Кэш последней загруженной конфигурации
**Обновляется:**
- При загрузке конфигурации: `this.cachedAutoBotConfig = autoBotConfig`
- После сохранения: синхронизируется с сохраненными значениями

### 3. `bots_data['auto_bot_config']` в Backend
**Назначение:** Конфигурация в памяти сервера
**Обновляется:**
- При загрузке из `bot_config.py`: через `load_auto_bot_config()`
- При сохранении: сначала обновляется из POST запроса, затем перезагружается из файла

### 4. `bot_engine/bot_config.py` - DEFAULT_AUTO_BOT_CONFIG
**Назначение:** ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ
**Обновляется:**
- При сохранении через `save_auto_bot_config_to_py()`
- Не должен обновляться вручную (кроме как через UI или config_writer)

---

## ⚠️ ВОЗМОЖНЫЕ ПРОБЛЕМЫ

### Проблема 1: UI показывает старые значения после перезагрузки страницы
**Причина:** Браузер кэширует ответы API
**Решение:** ✅ Добавлен cache-busting параметр и заголовки `Cache-Control`

### Проблема 2: API возвращает старые значения из bots_data
**Причина:** Модуль `bot_config` не перезагружается при GET запросе
**Решение:** ✅ Принудительная перезагрузка модуля перед возвратом данных

### Проблема 3: originalConfig не синхронизирован после сохранения
**Причина:** Не обновляется после успешного сохранения
**Решение:** ✅ Обновляется в `sendConfigUpdate()` и принудительно перезагружается через `loadConfigurationData()`

---

## 📊 СХЕМА ПОТОКА ДАННЫХ

```
┌─────────────────────────────────────────────────────────────────┐
│                        СОХРАНЕНИЕ (UI → Backend)                │
└─────────────────────────────────────────────────────────────────┘

[HTML Форма] 
    ↓
[collectConfigurationData()] - собирает из DOM + кэша
    ↓
[sendConfigUpdate()] - фильтрует измененные параметры
    ↓
[POST /api/bots/auto-bot] 
    ↓
[api_endpoints.py: auto_bot_config() POST] - обновляет bots_data
    ↓
[save_auto_bot_config()] - вызывает config_writer
    ↓
[save_auto_bot_config_to_py()] - записывает в bot_config.py
    ↓
[bot_engine/bot_config.py] - файл обновлен! ✓
    ↓
[importlib.reload(bot_engine.bot_config)] - перезагрузка модуля
    ↓
[load_auto_bot_config()] - читает из файла и обновляет bots_data
    ↓
[bots_data['auto_bot_config']] - обновлено из файла! ✓


┌─────────────────────────────────────────────────────────────────┐
│                        ЗАГРУЗКА (Backend → UI)                  │
└─────────────────────────────────────────────────────────────────┘

[loadConfigurationData()] - запрос с cache-busting
    ↓
[GET /api/bots/auto-bot?_t=timestamp]
    ↓
[api_endpoints.py: auto_bot_config() GET]
    ↓
[importlib.reload(bot_engine.bot_config)] - принудительная перезагрузка!
    ↓
[load_auto_bot_config()] - читает из bot_config.py
    ↓
[bots_data['auto_bot_config']] - свежие данные из файла
    ↓
[return jsonify({ config: bots_data['auto_bot_config'] })] - возврат в UI
    ↓
[populateConfigurationForm()] - заполнение DOM элементов
    ↓
[cachedAutoBotConfig] - обновление кэша
    ↓
[originalConfig] - обновление для отслеживания изменений
    ↓
[HTML Форма] - значения отображаются пользователю! ✓
```

---

## 🔍 КРИТИЧЕСКИЕ МЕСТА ДЛЯ ОТЛАДКИ

### 1. Логирование в UI (браузер консоль)
```javascript
// В collectConfigurationData()
console.log('[BotsManager] ✅ Конфигурация собрана:');
console.log('  trailing_stop_activation:', result.autoBot.trailing_stop_activation);

// В sendConfigUpdate()
console.log(`[BotsManager] 📤 Отправка измененных параметров:`, filteredData);

// В populateConfigurationForm()
console.log('[BotsManager] 🔍 autoBotConfig получен в populateConfigurationForm:');
console.log('   trailing_stop_activation:', autoBotConfig.trailing_stop_activation);
```

### 2. Логирование в Backend (сервер логи)
```python
# В api_endpoints.py GET
logger.info(f"[CONFIG_API] 📤 Возвращаем конфигурацию в UI:")
logger.info(f"  trailing_stop_activation: {config.get('trailing_stop_activation')}")

# В config_writer.py
logger.info(f"[CONFIG_WRITER] ✏️ trailing_stop_activation: {old_value} → {new_value}")

# В imports_and_globals.py
logger.info(f"[CONFIG] 📋 Значения из bot_config.py:")
logger.info(f"  trailing_stop_activation: {merged_config.get('trailing_stop_activation')}")
```

---

## ✅ ПРОВЕРКА ПРАВИЛЬНОЙ РАБОТЫ

### После сохранения:
1. ✅ В логах сервера: `[CONFIG_WRITER] ✏️ trailing_stop_activation: 20 → 31`
2. ✅ В файле `bot_config.py`: `'trailing_stop_activation': 31`
3. ✅ В логах: `[CONFIG] 📋 Значения из bot_config.py: trailing_stop_activation: 31`

### После перезагрузки страницы:
1. ✅ В логах сервера: `[CONFIG_API] 📤 Возвращаем конфигурацию в UI: trailing_stop_activation: 31`
2. ✅ В консоли браузера: `[BotsManager] 🔍 autoBotConfig: trailing_stop_activation: 31`
3. ✅ В UI: поле `trailingStopActivation` показывает значение `31`

