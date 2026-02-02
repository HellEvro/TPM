# Предложение: настоящее инкрементальное обучение AI

## Текущее состояние

1. **AITrainer.update_model_online(trade_result)**  
   - Добавляет сделку в `_online_learning_buffer` (7 признаков через `_build_signal_features_7`).  
   - Раз в 10 сделок вызывает `_perform_incremental_training()`.  
   - **Проблема:** `update_model_online` нигде не вызывается → буфер тренера не заполняется.  
   - **Проблема:** `_perform_incremental_training()` только анализирует важность признаков, **не переобучает** модель.

2. **AISelfLearning**  
   - При закрытии сделки вызывается `process_trade_for_self_learning(trade_result)` → `process_trade_result()` → сделка попадает в `online_learning_buffer` (свой буфер, не тренера).  
   - Когда буфер достигает `online_learning_interval`, вызывается `_perform_online_learning()` → `_update_model_online(training_data)` (паттерны успех/неудача) → попытка скорректировать «веса» через `_get_model_weights` / `_set_model_weights`.  
   - **Проблема:** у RandomForest нет обновляемых весов в привычном смысле; реального переобучения нет.

Итог: онлайн-путь сейчас не даёт настоящего обновления модели. Ни буфер тренера не используется, ни переобучение по новым сделкам не запускается.

---

## Вариант A (рекомендуемый): лёгкий ретрайн по последним сделкам

**Идея:** раз в N сделок переобучать `signal_predictor` и `profit_predictor` на последних K сделках из БД (и при желании — на буфере тренера), без полного прогона по всем данным и свечам.

### Шаги

1. **Добавить в AITrainer метод**  
   `retrain_on_recent_trades(self, min_samples: int = 50, max_trades: int = 200) -> bool`  
   - Загрузить сделки: `get_trades_for_training(..., limit=max_trades)`.  
   - Для каждой сделки: `_build_signal_features_7(trade)`; таргет: 1 если pnl > 0, иначе 0; для profit — pnl.  
   - Если валидных образцов < min_samples → вернуть False.  
   - `StandardScaler().fit_transform(X)`, train_test_split (например 0.2), обучить `signal_predictor` и `profit_predictor`, сохранить модели и scaler (`_save_models()`), выставить `expected_features = 7`.  
   - Вернуть True при успехе.

2. **Вызывать ретрайн из AISelfLearning**  
   В `_perform_online_learning()` после подготовки `training_data` (или вместо попытки обновить «веса»):  
   - Получить `ai_trainer` из self.  
   - Если `ai_trainer` и буфер достаточно большой (например, >= 10 сделок):  
     - Вызвать `ai_trainer.retrain_on_recent_trades(min_samples=20, max_trades=150)`.  
   - Не трогать логику паттернов/оценки эффективности: оставить как есть для логов и аналитики.

3. **Опционально: заполнять буфер тренера**  
   В `process_trade_result()` после `self.online_learning_buffer.append(trade_result)` вызвать  
   `if self.ai_trainer: self.ai_trainer.update_model_online(trade_result)`.  
   Тогда буфер тренера будет тем же набором сделок; при желании позже можно в `retrain_on_recent_trades` подмешивать буфер к выборке из БД (если нужны «самые свежие» без задержки записи в БД).

4. **Конфиг**  
   В `bot_config` / AIConfig добавить, например:  
   - `AI_INCREMENTAL_RETRAIN_ENABLED = True`  
   - `AI_INCREMENTAL_RETRAIN_MIN_SAMPLES = 20`  
   - `AI_INCREMENTAL_RETRAIN_MAX_TRADES = 150`  
   И использовать их в `retrain_on_recent_trades` и в условии вызова из AISelfLearning.

**Плюсы:** реальное переобучение на свежих сделках, один формат признаков (7), минимум изменений, не трогаем полный пайплайн со свечами.  
**Минусы:** раз в N сделок — небольшая нагрузка (обучение на 50–200 сделках).

---

## Вариант B: использовать полный цикл обучения раз в N сделок

**Идея:** не вводить отдельный метод, а периодически вызывать уже существующий полный ретрайн.

### Шаги

1. В `_perform_online_learning()` (AISelfLearning) после проверки буфера:  
   - Вызвать `ai_trainer.train_on_real_trades_with_candles()` **или** `ai_trainer.train_on_history()` (в зависимости от того, нужны ли свечи и полная логика).  
2. Ограничить частоту: например, не чаще раза в час или раз в M сделок (счётчик в AISelfLearning или в конфиге).

**Плюсы:** переиспользование готовой логики, не нужно поддерживать второй путь обучения.  
**Минусы:** тяжёлее (загрузка свечей, много сделок), дольше по времени.

---

## Вариант C: реально использовать буфер тренера и ретрайн по нему

**Идея:** буфер тренера заполнять из того же потока сделок, что и AISelfLearning; раз в 10 сделок делать ретрайн только по буферу (без БД).

### Шаги

1. В `process_trade_result()` вызывать `self.ai_trainer.update_model_online(trade_result)` (как в п.3 варианта A).  
2. В `_perform_incremental_training()` (AITrainer):  
   - Собрать из буфера X (уже 7 признаков), y_signal, y_profit.  
   - Если len(X) < 10 → return False.  
   - `scaler = StandardScaler(); X_scaled = scaler.fit_transform(X)` (по буферу).  
   - Обучить `signal_predictor.fit(X_scaled, y_signal)` и `profit_predictor.fit(X_scaled, y_profit)`.  
   - Сохранить модели и scaler, выставить `expected_features = 7`.  
   - Вернуть True.

**Плюсы:** быстрый ретрайн только по последним 10–50 сделкам, без запросов к БД.  
**Минусы:** маленькая выборка → риск переобучения на шуме; лучше комбинировать с вариантом A (буфер + последние из БД).

---

## Рекомендация

- **Сделать сначала вариант A:** метод `retrain_on_recent_trades()` + вызов из `_perform_online_learning()` с конфигом. Так модель будет реально обновляться по последним сделкам без риска сломать текущий полный пайплайн.  
- **Опционально:** п.3 варианта A (вызов `update_model_online` из `process_trade_result`) и затем доработать `_perform_incremental_training()` по варианту C, чтобы раз в 10 сделок делать лёгкий ретрайн по буферу (или по буферу + последним из БД внутри `retrain_on_recent_trades`).

---

## Дополнительные проверки пайплайна (без изменения логики)

1. **Сохранение expected_features при сохранении моделей**  
   Убедиться, что при сохранении scaler/моделей в БД или в метаданные записывается число признаков (7), чтобы после перезапуска не было расхождений с inference.

2. **Использование profit_predictor в inference**  
   Сейчас в `ai_inference.predict_signal()` используется только `signal_predictor`; `predicted_profit` возвращает основной тренер в `predict()`, но не inference. Если нужно показывать ожидаемый PnL в ботах — добавить загрузку и вызов `profit_predictor` в inference по тому же 7-признаковому вектору.

3. **Вызов process_trade_for_self_learning**  
   Убедиться, что при закрытии позиции с `ai_decision_id` всегда передаётся полный `trade_result` (включая entry_rsi, entry_trend, pnl и т.д.), чтобы и AISelfLearning, и при включении п.3 — буфер тренера получали пригодные для обучения данные.

После выбора варианта (A/B/C или комбинации) можно расписать конкретные патчи по файлам и строкам.
