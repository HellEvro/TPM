# 🔗 Интеграция AI модуля в систему

## Быстрая интеграция

### Вариант 1: Автоматический запуск вместе с bots.py

Добавьте в начало `bots.py` (после импортов):

```python
# Инициализация AI системы
try:
    from ai import get_ai_system
    ai_system = get_ai_system()
    ai_system.start()
    logger.info("🤖 AI система запущена")
except Exception as e:
    logger.warning(f"⚠️ AI система не запущена: {e}")
```

### Вариант 2: Отдельный процесс

Запустите AI систему в отдельном терминале:

```bash
python ai.py
```

## Использование предсказаний в коде

### В bots.py или app.py

```python
from ai import get_ai_system

# Получить AI систему
ai_system = get_ai_system()

# Предсказание сигнала
prediction = ai_system.predict_signal('BTCUSDT', {
    'rsi': 30,
    'trend': 'UP',
    'price': 50000
})

if prediction.get('signal') == 'LONG' and prediction.get('confidence', 0) > 0.7:
    # Открыть позицию
    pass
```

### Использование оптимизированных параметров

```python
from ai import get_ai_system

ai_system = get_ai_system()

# Оптимизировать конфигурацию бота
optimized_config = ai_system.optimize_bot_config('BTCUSDT')

# Применить оптимизированные параметры
if optimized_config and 'error' not in optimized_config:
    # Обновить конфигурацию бота
    pass
```

## API endpoints для AI (опционально)

Можно добавить в `bots_modules/api_endpoints.py`:

```python
@bots_app.route('/api/ai/status', methods=['GET'])
def get_ai_status():
    """Получить статус AI системы"""
    try:
        from ai import get_ai_system
        ai_system = get_ai_system()
        return jsonify({
            'success': True,
            'status': ai_system.get_status()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bots_app.route('/api/ai/predict/<symbol>', methods=['POST'])
def predict_signal(symbol):
    """Предсказание сигнала для символа"""
    try:
        from ai import get_ai_system
        data = request.get_json()
        ai_system = get_ai_system()
        prediction = ai_system.predict_signal(symbol, data)
        return jsonify({
            'success': True,
            'prediction': prediction
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

## Проверка работы

1. Запустите bots.py:
```bash
python bots.py
```

2. Запустите ai.py (в отдельном терминале):
```bash
python ai.py
```

3. Проверьте логи:
```bash
tail -f logs/ai.log
```

4. Проверьте данные:
```bash
ls -la data/ai/
```

## Требования

- bots.py должен быть запущен на порту 5001
- app.py должен быть запущен на порту 5000 (опционально)
- Минимум 50 закрытых сделок для обучения

## Автоматическая торговля

Для включения автоматической торговли через AI:

```python
from ai import get_ai_system

ai_system = get_ai_system()
ai_system.config['auto_trading'] = True
```

⚠️ **Внимание**: Автоматическая торговля требует тщательного тестирования!

