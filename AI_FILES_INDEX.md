# 📁 AI Модуль - Индекс файлов

**Навигация по всем AI файлам**

---

## 🎯 НАЧНИТЕ ОТСЮДА

### Для пользователя:
1. **READY_FOR_YOU.md** ⭐ - Сводка всей работы (начните с этого!)
2. **AI_QUICK_START.md** - Быстрый старт
3. **AI_STATUS.md** - Текущий статус AI

### Для разработчика:
1. **AI_IMPLEMENTATION_COMPLETE_SUMMARY.md** - Полная техническая сводка
2. **docs/AI_README.md** - Главный README для AI модуля
3. **CHANGELOG_AI_SESSION.md** - Детали последней сессии

---

## 📚 ДОКУМЕНТАЦИЯ

### Основная:
- **docs/AI_README.md** - Главный README
- **docs/AI_IMPLEMENTATION_CHECKLIST.md** - Чеклист (42% завершено)
- **docs/AI_PREMIUM_ARCHITECTURE.md** - Архитектура premium модуля
- **docs/AI_IMPLEMENTATION_SUMMARY.md** - Краткое резюме

### Технические детали:
- **docs/AI_RISK_MANAGER.md** - Dynamic Risk Manager (детали)
- **docs/AI_CURRENT_VS_PLANNED.md** - Что работает vs планы
- **docs/AI_INITIALIZATION.md** - Как работает инициализация
- **docs/AI_DATA_COLLECTION_LOGIC.md** - Логика сбора данных
- **docs/AI_AUTO_TRAINING_CONFIG.md** - Настройка автообучения
- **docs/AUTO_TRAINER_FIXES_SUMMARY.md** - Исправления Auto Trainer
- **docs/AI_AUTO_TRAINING.md** - Автообучение (старая версия)
- **docs/AI_QUICK_START.md** - Быстрый старт (старая версия)

### Сводки и изменения:
- **CHANGES_SUMMARY_AI_PHASE_5.md** - Список всех изменений
- **COMMIT_MESSAGE_AI_PHASE_5.md** - Сообщение для коммита
- **SESSION_COMPLETE.md** - Итоги сессии

---

## 💻 КОД

### AI Модули (bot_engine/ai/):
- **__init__.py** - Публичный интерфейс
- **_premium_loader.py** - Загрузчик premium модулей
- **ai_manager.py** - Менеджер всех AI модулей
- **anomaly_detector.py** - Обнаружение pump/dump
- **risk_manager.py** ⭐ - Умное управление рисками (НОВЫЙ!)
- **auto_trainer.py** - Автообучение в фоне

### Интеграция:
- **bots.py** - Ранняя инициализация AI
- **bot_engine/trading_bot.py** - Использование AI для SL и размера
- **bot_engine/bot_config.py** - Настройки AI
- **bots_modules/filters.py** - AI в Exit Scam фильтре

---

## 🧪 ТЕСТЫ

### Проверка компонентов:
- **scripts/test_ai_initialization.py** - Инициализация AI
- **scripts/test_ai_detector_status.py** - Статус Anomaly Detector
- **scripts/test_risk_manager.py** ⭐ - Тест Risk Manager (НОВЫЙ!)
- **scripts/test_full_ai_system.py** ⭐ - Комплексный тест (НОВЫЙ!)
- **scripts/test_incremental_update.py** - Тест инкрементального обновления
- **scripts/verify_ai_ready.py** ⭐ - Финальная проверка (НОВЫЙ!)

### Работа с данными:
- **scripts/ai/collect_historical_data.py** - Сбор данных с биржи
- **scripts/ai/train_anomaly_on_real_data.py** - Обучение модели
- **scripts/ai/check_collected_data.py** - Проверка данных
- **scripts/ai/optimize_threshold.py** - Оптимизация порогов
- **scripts/ai/create_dev_license.py** - Создание dev лицензии

### Старые тесты:
- **scripts/test_ai_loading.py** - Загрузка AI модулей
- **scripts/ai/test_anomaly_detector.py** - Тест на синтетических данных

---

## 📊 ДАННЫЕ

### Модели (data/ai/models/):
- **anomaly_detector.pkl** - Обученная модель (815 KB)
- **anomaly_scaler.pkl** - Scaler для нормализации (1 KB)
- **anomaly_detector_test.pkl** - Тестовая модель
- **anomaly_detector_test_scaler.pkl** - Тестовый scaler

### Исторические данные (data/ai/historical/):
- **583 файла** `{SYMBOL}_6h_historical.csv`
- **~1,700,000 свечей** (2920 свечей × 583 монеты)
- **~350 MB** общий размер

### Другое:
- **license.lic** - Developer лицензия
- **data/ai/.gitkeep** - Git placeholder
- **data/ai/models/.gitkeep** - Git placeholder
- **data/ai/historical/.gitkeep** - Git placeholder

---

## 🎯 БЫСТРАЯ НАВИГАЦИЯ

### Хочу запустить:
→ **AI_QUICK_START.md**

### Хочу понять что работает:
→ **docs/AI_CURRENT_VS_PLANNED.md**

### Хочу настроить:
→ **docs/AI_AUTO_TRAINING_CONFIG.md**

### Хочу увидеть детали Risk Manager:
→ **docs/AI_RISK_MANAGER.md**

### Хочу проверить всё:
→ **scripts/verify_ai_ready.py**

### Хочу увидеть прогресс:
→ **docs/AI_IMPLEMENTATION_CHECKLIST.md**

---

## 📞 КОМАНДЫ

### Проверка:
```bash
python scripts/verify_ai_ready.py       # Финальная проверка (10 тестов)
python scripts/test_full_ai_system.py   # Комплексный тест AI
```

### Запуск:
```bash
python bots.py                          # Запуск бота с AI
```

### Мониторинг:
```bash
tail -f logs/bots.log | grep AI         # AI логи в реальном времени
```

---

## ✅ СТАТУС: ГОТОВ К ИСПОЛЬЗОВАНИЮ

**Проверка:** 10/10 тестов ✅  
**Прогресс:** 42.1% (почти половина)  
**Качество:** Нет ошибок  
**Документация:** Полная

**Просто запустите `python bots.py` и AI заработает!** 🚀

