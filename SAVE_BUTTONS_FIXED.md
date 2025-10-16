# Исправление кнопок сохранения конфигурации

## Проблема
Кнопки сохранения конфигурации (типа `btn btn-success config-section-save-btn`) не работали.

## Причина
Неправильные CSS селекторы в JavaScript коде:

**Неправильно** (старые селекторы):
```javascript
document.querySelector('[data-section="basic"] .config-section-actions button')
```

**Правильно** (новые селекторы):
```javascript
document.querySelector('.config-section-save-btn[data-section="basic"]')
```

## Структура HTML кнопок:
```html
<button class="btn btn-success config-section-save-btn" data-section="basic">
    <span data-translate="save_basic_section_btn">💾 Сохранить основные настройки</span>
</button>
```

## Исправленные селекторы:

### ✅ Основные настройки
- `data-section="basic"` → `saveBasicSettings()`

### ✅ Системные настройки  
- `data-section="system"` → `saveSystemSettings()`

### ✅ Торговые параметры
- `data-section="trading"` → `saveTradingParameters()`

### ✅ RSI выходы
- `data-section="rsi-exits"` → `saveRsiExits()`

### ✅ RSI временной фильтр
- `data-section="rsi-time-filter"` → `saveRsiTimeFilter()`

### ✅ ExitScam фильтр
- `data-section="exit-scam"` → `saveExitScamFilter()`

### ✅ Enhanced RSI
- `data-section="enhanced-rsi"` → `saveEnhancedRsi()`

### ✅ Торговые настройки
- `data-section="trading-settings"` → `saveTradingSettings()`

### ✅ Защитные механизмы
- `data-section="protective"` → `saveProtectiveMechanisms()`

### ✅ Настройки зрелости
- `data-section="maturity"` → `saveMaturitySettings()`

### ✅ EMA параметры
- `data-section="ema"` → `saveEmaParameters()`

## Файл:
`static/js/managers/bots_manager.js` - исправлены все селекторы кнопок сохранения

## Результат:
✅ Все 11 кнопок сохранения конфигурации теперь работают  
✅ Каждая кнопка сохраняет только свою секцию  
✅ Частичные обновления конфигурации работают корректно  

## Дата исправления:
2025-10-16 23:22
