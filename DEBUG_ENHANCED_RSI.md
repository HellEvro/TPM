# 🔍 ОТЛАДКА: Enhanced RSI не сохраняется

## ❌ **Проблема:**
Настройки Enhanced RSI включаются, но при сохранении выключаются обратно. Система пишет "изменений не обнаружено".

## 🔧 **Добавлена отладка:**

### **1. В функции `collectConfigurationData()`:**
Добавлены детальные логи для каждого Enhanced RSI чекбокса:
```javascript
enhanced_rsi_enabled: (() => {
    const el = document.getElementById('enhancedRsiEnabled');
    const checked = el?.checked || false;
    console.log('[BotsManager] 🔍 Enhanced RSI Enabled - элемент:', !!el, 'значение:', checked);
    return checked;
})(),
```

### **2. В функции `saveConfiguration()`:**
Добавлены логи отправляемой конфигурации:
```javascript
console.log('[BotsManager] 🔍 Отправляемая конфигурация Enhanced RSI:');
console.log('  enhanced_rsi_enabled:', config.autoBot.enhanced_rsi_enabled);
console.log('  enhanced_rsi_require_volume_confirmation:', config.autoBot.enhanced_rsi_require_volume_confirmation);
```

## 🧪 **Тест:**
1. Включить настройки Enhanced RSI
2. Сохранить конфигурацию
3. Проверить консоль браузера на наличие логов:
   - `🔍 Enhanced RSI Enabled - элемент: true значение: true`
   - `🔍 Отправляемая конфигурация Enhanced RSI: enhanced_rsi_enabled: true`

## 📁 **Изменённые файлы:**
- `static/js/managers/bots_manager.js` (строки 4318-4341, 4374-4379)
- Синхронизировано с `InfoBot_Public/static/js/managers/bots_manager.js`

## 🎯 **Цель:**
Выяснить, отправляются ли правильные значения Enhanced RSI на сервер или проблема в другом месте.
