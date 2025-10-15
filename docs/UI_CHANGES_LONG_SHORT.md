# Изменение отображения фильтров LONG/SHORT

**Дата:** 16 октября 2025  
**Время:** 01:55

## 🎨 Изменения в UI

### Проблема
Пользователь попросил изменить отображение кнопок фильтров монет с:
- `🚀 ENTER_LONG (0)` → `🚀 LONG (0)`
- `📉 ENTER_SHORT (0)` → `📉 SHORT (0)`

**Примечание:** Счетчики внизу остались как "Buy:" и "Sell:" (не изменялись)

### ✅ Исправления

#### 1. HTML шаблон (templates/pages/bots.html)
**Строки 145-146:**

**Было:**
```html
<button class="rsi-filter-btn enter-long-filter" data-filter="enter-long">🚀 ENTER_LONG</button>
<button class="rsi-filter-btn enter-short-filter" data-filter="enter-short">📉 ENTER_SHORT</button>
```

**Стало:**
```html
<button class="rsi-filter-btn enter-long-filter" data-filter="enter-long">🚀 LONG</button>
<button class="rsi-filter-btn enter-short-filter" data-filter="enter-short">📉 SHORT</button>
```

#### 2. HTML шаблон - добавлены счетчики (templates/pages/bots.html)
**Строки 140-146:**

**Было:**
```html
<button class="rsi-filter-btn active" data-filter="all">🌐 Все</button>
<button class="rsi-filter-btn buy-filter" data-filter="buy-zone">🟢 ≤29</button>
<button class="rsi-filter-btn sell-filter" data-filter="sell-zone">🔴 ≥71</button>
<button class="rsi-filter-btn trend-up-filter" data-filter="trend-up">📈 UP</button>
<button class="rsi-filter-btn trend-down-filter" data-filter="trend-down">📉 DOWN</button>
<button class="rsi-filter-btn enter-long-filter" data-filter="enter-long">🚀 LONG</button>
<button class="rsi-filter-btn enter-short-filter" data-filter="enter-short">📉 SHORT</button>
```

**Стало:**
```html
<button class="rsi-filter-btn active" data-filter="all">🌐 Все (<span id="filterAllCount">0</span>)</button>
<button class="rsi-filter-btn buy-filter" data-filter="buy-zone">🟢 ≤29 (<span id="filterBuyZoneCount">0</span>)</button>
<button class="rsi-filter-btn sell-filter" data-filter="sell-zone">🔴 ≥71 (<span id="filterSellZoneCount">0</span>)</button>
<button class="rsi-filter-btn trend-up-filter" data-filter="trend-up">📈 UP (<span id="filterTrendUpCount">0</span>)</button>
<button class="rsi-filter-btn trend-down-filter" data-filter="trend-down">📉 DOWN (<span id="filterTrendDownCount">0</span>)</button>
<button class="rsi-filter-btn enter-long-filter" data-filter="enter-long">🚀 LONG (<span id="filterLongCount">0</span>)</button>
<button class="rsi-filter-btn enter-short-filter" data-filter="enter-short">📉 SHORT (<span id="filterShortCount">0</span>)</button>
```

#### 3. JavaScript обновление счетчиков (static/js/managers/bots_manager.js)
**Строки 1044-1072:**

**Добавлена функция `updateSignalCounters()`:**
```javascript
updateSignalCounters() {
    // Подсчитываем все категории
    const allCount = this.coinsRsiData.length;
    const longCount = this.coinsRsiData.filter(coin => this.getEffectiveSignal(coin) === 'ENTER_LONG').length;
    const shortCount = this.coinsRsiData.filter(coin => this.getEffectiveSignal(coin) === 'ENTER_SHORT').length;
    const buyZoneCount = this.coinsRsiData.filter(coin => coin.rsi6h && coin.rsi6h <= 29).length;
    const sellZoneCount = this.coinsRsiData.filter(coin => coin.rsi6h && coin.rsi6h >= 71).length;
    const trendUpCount = this.coinsRsiData.filter(coin => coin.trend6h === 'UP').length;
    const trendDownCount = this.coinsRsiData.filter(coin => coin.trend6h === 'DOWN').length;
    
    // Обновляем счетчики в HTML
    const allCountEl = document.getElementById('filterAllCount');
    const buyZoneCountEl = document.getElementById('filterBuyZoneCount');
    const sellZoneCountEl = document.getElementById('filterSellZoneCount');
    const trendUpCountEl = document.getElementById('filterTrendUpCount');
    const trendDownCountEl = document.getElementById('filterTrendDownCount');
    const longCountEl = document.getElementById('filterLongCount');
    const shortCountEl = document.getElementById('filterShortCount');
    
    if (allCountEl) allCountEl.textContent = allCount;
    if (buyZoneCountEl) buyZoneCountEl.textContent = buyZoneCount;
    if (sellZoneCountEl) sellZoneCountEl.textContent = sellZoneCount;
    if (trendUpCountEl) trendUpCountEl.textContent = trendUpCount;
    if (trendDownCountEl) trendDownCountEl.textContent = trendDownCount;
    if (longCountEl) longCountEl.textContent = longCount;
    if (shortCountEl) shortCountEl.textContent = shortCount;
}
```

## 📊 Результат

### До изменений:
```
🌐 Все  🟢 ≤29  🔴 ≥71  📈 UP  📉 DOWN  🚀 ENTER_LONG (0)  📉 ENTER_SHORT (0)
📈 Всего: 0 | 🟢 Buy: 0 | 🔴 Sell: 0
```

### После изменений:
```
🌐 Все (0)  🟢 ≤29 (0)  🔴 ≥71 (0)  📈 UP (0)  📉 DOWN (0)  🚀 LONG (0)  📉 SHORT (0)
📈 Всего: 0 | 🟢 Buy: 0 | 🔴 Sell: 0
```

**Добавлены счетчики ко всем кнопкам фильтров, изменены названия LONG/SHORT**

## 🔍 Логика работы

- **LONG** - монеты с сигналом `ENTER_LONG` (перекупленность, рекомендация на покупку)
- **SHORT** - монеты с сигналом `ENTER_SHORT` (перепроданность, рекомендация на продажу)
- Счетчики обновляются автоматически при загрузке данных RSI

## 📝 Примечание

Изменения применяются сразу после обновления страницы. Перезапуск сервера не требуется, так как это только фронтенд-изменения.

## 🔍 Логика работы

- **🚀 LONG (0)** - кнопка фильтра для монет с сигналом `ENTER_LONG`
- **📉 SHORT (0)** - кнопка фильтра для монет с сигналом `ENTER_SHORT`
- Число в скобках показывает количество монет с соответствующим сигналом
- Кнопки обновляются автоматически при загрузке данных RSI

