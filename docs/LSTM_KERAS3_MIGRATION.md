# ⚠️ УСТАРЕВШИЙ ДОКУМЕНТ - МИГРАЦИЯ НА PYTORCH ЗАВЕРШЕНА

**Дата:** 2026-01-26  
**Статус:** ✅ Миграция на PyTorch завершена

---

## ⚠️ ВАЖНО

Этот документ описывает миграцию с TensorFlow/Keras на Keras 3, которая была выполнена ранее. 

**Сейчас система использует PyTorch вместо TensorFlow/Keras.**

---

## ТЕКУЩЕЕ СОСТОЯНИЕ

- **Фреймворк:** PyTorch 2.5.1+ (с поддержкой CUDA)
- **Формат моделей:** `.pth` (PyTorch state_dict)
- **GPU:** Автоматическое использование NVIDIA GPU (если доступен)
- **Файлы моделей:**
  - `data/ai/models/lstm_predictor.pth` - PyTorch модель
  - `data/ai/models/lstm_config.json` - конфигурация
  - `data/ai/models/lstm_scaler.pkl` - scaler для данных

---

## АКТУАЛЬНАЯ ДОКУМЕНТАЦИЯ

См.:
- `docs/LSTM_IMPLEMENTATION_SUMMARY.md` - актуальная информация о LSTM Predictor
- `docs/INSTALL.md` - инструкции по установке PyTorch
- `bot_engine/ai/lstm_predictor.py` - исходный код (PyTorch)

---

## ИСТОРИЧЕСКАЯ СПРАВКА

Ранее использовался TensorFlow/Keras:
- Формат моделей: `.h5` → `.keras` (Keras 3)
- Проблема: несовместимость с новыми версиями Keras

Теперь используется PyTorch:
- Формат моделей: `.pth` (PyTorch state_dict)
- Преимущества: лучшая поддержка Python 3.14+, упрощенная установка, лучшая производительность GPU

---

**Этот документ сохранен для исторической справки. Для актуальной информации см. `docs/LSTM_IMPLEMENTATION_SUMMARY.md`.**
