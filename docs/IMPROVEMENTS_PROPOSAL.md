# Предложения по улучшению InfoBot AI System

**Дата анализа:** 26 января 2026  
**Версия проекта:** 1.7 AI Edition  
**Аналитик:** AI Assistant

---

## Содержание

1. [Резюме текущего состояния](#1-резюме-текущего-состояния)
2. [Улучшения архитектуры LSTM Predictor](#2-улучшения-архитектуры-lstm-predictor)
3. [Добавление Transformer архитектуры](#3-добавление-transformer-архитектуры)
4. [Улучшение Feature Engineering](#4-улучшение-feature-engineering)
5. [Оптимизация гиперпараметров](#5-оптимизация-гиперпараметров)
6. [Ensemble методы](#6-ensemble-методы)
7. [Reinforcement Learning для торговли](#7-reinforcement-learning-для-торговли)
8. [Улучшение Pattern Detector](#8-улучшение-pattern-detector)
9. [Мониторинг и MLOps](#9-мониторинг-и-mlops)
10. [Дополнительные источники данных](#10-дополнительные-источники-данных)
11. [Приоритеты реализации](#11-приоритеты-реализации)

---

## 1. Резюме текущего состояния

### Сильные стороны проекта

- ✅ **Модульная архитектура** - четкое разделение AI компонентов
- ✅ **PyTorch для LSTM** - современный фреймворк с GPU поддержкой
- ✅ **SQLite база данных** - масштабируемое хранение данных
- ✅ **Hot reload моделей** - обновление без перезапуска
- ✅ **Множественные триггеры переобучения** - адаптивная система
- ✅ **Continuous Learning** - постоянное улучшение на реальных данных

### Текущие AI модули

| Модуль | Статус | Архитектура | Примечания |
|--------|--------|-------------|------------|
| LSTM Predictor | ✅ Активен | 3-слойный LSTM | Требует улучшения |
| Anomaly Detector | ✅ Активен | IsolationForest | Работает хорошо |
| Risk Manager | ✅ Активен | Эвристики + ML | Может быть улучшен |
| Strategy Optimizer | ✅ Активен | Grid Search | Неэффективен |
| Pattern Detector | ⚠️ В разработке | RandomForest | 0/7 задач |
| ML Risk Predictor | ✅ Активен | GradientBoosting | Требует премиум |

---

## 2. Улучшения архитектуры LSTM Predictor

### 2.1 Проблемы текущей архитектуры

```python
# Текущая архитектура (lstm_predictor.py:88-116)
self.lstm1 = nn.LSTM(input_size, 128, batch_first=True)
self.lstm2 = nn.LSTM(128, 64, batch_first=True)
self.lstm3 = nn.LSTM(64, 32, batch_first=True)
self.fc1 = nn.Linear(32, 32)
self.fc2 = nn.Linear(32, 16)
self.fc3 = nn.Linear(16, 3)  # direction, change%, confidence
```

**Проблемы:**
- Слишком простая архитектура для сложных финансовых данных
- Нет Attention механизма для фокусировки на важных временных шагах
- Нет skip connections (residual learning)
- BatchNorm применяется неоптимально
- Фиксированный dropout для всех слоев

### 2.2 Предлагаемая улучшенная архитектура

```python
class ImprovedLSTMModel(nn.Module):
    """
    Улучшенная LSTM модель с Attention и Residual connections
    """
    
    def __init__(
        self,
        input_size: int,
        hidden_sizes: List[int] = [256, 128, 64],
        num_heads: int = 4,
        dropout: float = 0.3,
        use_attention: bool = True
    ):
        super().__init__()
        
        self.use_attention = use_attention
        
        # Bidirectional LSTM для лучшего понимания контекста
        self.lstm1 = nn.LSTM(
            input_size, hidden_sizes[0],
            batch_first=True,
            bidirectional=True,
            num_layers=2,
            dropout=dropout
        )
        
        # Layer Normalization (лучше для RNN чем BatchNorm)
        self.ln1 = nn.LayerNorm(hidden_sizes[0] * 2)  # *2 для bidirectional
        
        # Multi-Head Self-Attention
        if use_attention:
            self.attention = nn.MultiheadAttention(
                embed_dim=hidden_sizes[0] * 2,
                num_heads=num_heads,
                dropout=dropout,
                batch_first=True
            )
            self.ln_attn = nn.LayerNorm(hidden_sizes[0] * 2)
        
        # Второй LSTM с residual connection
        self.lstm2 = nn.LSTM(
            hidden_sizes[0] * 2, hidden_sizes[1],
            batch_first=True,
            bidirectional=True,
            dropout=dropout
        )
        self.ln2 = nn.LayerNorm(hidden_sizes[1] * 2)
        
        # Projection для residual connection
        self.residual_proj = nn.Linear(hidden_sizes[0] * 2, hidden_sizes[1] * 2)
        
        # Feature pyramid для multi-scale features
        self.pool_global = nn.AdaptiveAvgPool1d(1)
        self.pool_max = nn.AdaptiveMaxPool1d(1)
        
        # MLP Head с Gated Linear Units
        mlp_input_size = hidden_sizes[1] * 2 * 2  # avg + max pooling
        self.gate1 = nn.Linear(mlp_input_size, hidden_sizes[2] * 2)
        self.fc1 = nn.Linear(mlp_input_size, hidden_sizes[2] * 2)
        
        self.gate2 = nn.Linear(hidden_sizes[2], 32 * 2)
        self.fc2 = nn.Linear(hidden_sizes[2], 32 * 2)
        
        # Отдельные головы для каждого выхода
        self.head_direction = nn.Linear(32, 1)  # tanh -> [-1, 1]
        self.head_change = nn.Linear(32, 1)     # linear -> %
        self.head_confidence = nn.Linear(32, 1) # sigmoid -> [0, 1]
        
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x):
        batch_size = x.size(0)
        
        # LSTM 1
        lstm1_out, _ = self.lstm1(x)
        lstm1_out = self.ln1(lstm1_out)
        lstm1_out = self.dropout(lstm1_out)
        
        # Self-Attention
        if self.use_attention:
            attn_out, _ = self.attention(lstm1_out, lstm1_out, lstm1_out)
            lstm1_out = self.ln_attn(lstm1_out + attn_out)  # Residual
        
        # LSTM 2 с residual
        lstm2_out, _ = self.lstm2(lstm1_out)
        lstm2_out = self.ln2(lstm2_out)
        residual = self.residual_proj(lstm1_out[:, -1, :])
        lstm2_out = lstm2_out[:, -1, :] + residual  # Residual connection
        
        # Multi-scale pooling
        lstm2_seq = lstm2_out.unsqueeze(2)  # (batch, features, 1)
        pool_avg = self.pool_global(lstm2_seq).squeeze(-1)
        pool_max = self.pool_max(lstm2_seq).squeeze(-1)
        features = torch.cat([pool_avg, pool_max], dim=-1)
        
        # Gated Linear Unit (GLU)
        gate1 = torch.sigmoid(self.gate1(features))
        x = self.fc1(features) * gate1
        x = x[:, :x.size(1)//2]  # GLU splits in half
        x = self.dropout(x)
        
        gate2 = torch.sigmoid(self.gate2(x))
        x = self.fc2(x) * gate2
        x = x[:, :x.size(1)//2]
        
        # Отдельные выходы
        direction = torch.tanh(self.head_direction(x))
        change = self.head_change(x)
        confidence = torch.sigmoid(self.head_confidence(x))
        
        return torch.cat([direction, change, confidence], dim=-1)
```

### 2.3 Добавление Temporal Convolutional Network (TCN)

TCN часто превосходит LSTM для временных рядов:

```python
class TemporalBlock(nn.Module):
    """Temporal Block с dilated causal convolution"""
    
    def __init__(self, n_inputs, n_outputs, kernel_size, stride, dilation, dropout):
        super().__init__()
        
        padding = (kernel_size - 1) * dilation
        
        self.conv1 = nn.Conv1d(
            n_inputs, n_outputs, kernel_size,
            stride=stride, padding=padding, dilation=dilation
        )
        self.chomp1 = Chomp1d(padding)  # Causal convolution
        self.bn1 = nn.BatchNorm1d(n_outputs)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)
        
        self.conv2 = nn.Conv1d(
            n_outputs, n_outputs, kernel_size,
            stride=stride, padding=padding, dilation=dilation
        )
        self.chomp2 = Chomp1d(padding)
        self.bn2 = nn.BatchNorm1d(n_outputs)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)
        
        self.net = nn.Sequential(
            self.conv1, self.chomp1, self.bn1, self.relu1, self.dropout1,
            self.conv2, self.chomp2, self.bn2, self.relu2, self.dropout2
        )
        
        # Residual connection
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.ReLU()
        
    def forward(self, x):
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)


class TCNPredictor(nn.Module):
    """Temporal Convolutional Network для предсказания цен"""
    
    def __init__(
        self,
        input_size: int,
        num_channels: List[int] = [64, 128, 256],
        kernel_size: int = 3,
        dropout: float = 0.2
    ):
        super().__init__()
        
        layers = []
        num_levels = len(num_channels)
        
        for i in range(num_levels):
            dilation = 2 ** i
            in_channels = input_size if i == 0 else num_channels[i-1]
            out_channels = num_channels[i]
            
            layers.append(TemporalBlock(
                in_channels, out_channels, kernel_size,
                stride=1, dilation=dilation, dropout=dropout
            ))
        
        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(num_channels[-1], 3)  # 3 outputs
        
    def forward(self, x):
        # x: (batch, seq_len, features) -> (batch, features, seq_len)
        x = x.transpose(1, 2)
        x = self.network(x)
        x = x[:, :, -1]  # Take last timestep
        return self.fc(x)
```

---

## 3. Добавление Transformer архитектуры

### 3.1 Почему Transformer?

- **Self-Attention** - лучше улавливает долгосрочные зависимости
- **Параллельное обучение** - быстрее чем LSTM
- **State-of-the-art** в финансовом прогнозировании
- **Interpretability** - attention weights показывают важность временных шагов

### 3.2 Реализация Temporal Fusion Transformer (TFT)

```python
class TemporalFusionTransformer(nn.Module):
    """
    Temporal Fusion Transformer для временных рядов
    
    Основан на статье: "Temporal Fusion Transformers for Interpretable 
    Multi-horizon Time Series Forecasting" (Google, 2020)
    """
    
    def __init__(
        self,
        input_size: int,
        hidden_size: int = 128,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
        forecast_horizon: int = 6  # Предсказание на 6 часов
    ):
        super().__init__()
        
        self.hidden_size = hidden_size
        self.forecast_horizon = forecast_horizon
        
        # Variable Selection Networks
        self.vsn_encoder = VariableSelectionNetwork(
            input_size, hidden_size, dropout
        )
        
        # LSTM Encoder-Decoder
        self.lstm_encoder = nn.LSTM(
            hidden_size, hidden_size,
            batch_first=True, dropout=dropout
        )
        self.lstm_decoder = nn.LSTM(
            hidden_size, hidden_size,
            batch_first=True, dropout=dropout
        )
        
        # Gated Residual Networks
        self.grn_encoder = GatedResidualNetwork(hidden_size, hidden_size, dropout)
        self.grn_decoder = GatedResidualNetwork(hidden_size, hidden_size, dropout)
        
        # Interpretable Multi-Head Attention
        self.attention = InterpretableMultiHeadAttention(
            hidden_size, num_heads, dropout
        )
        
        # Position-wise Feed-Forward
        self.ff = nn.Sequential(
            nn.Linear(hidden_size, hidden_size * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size * 4, hidden_size)
        )
        
        # Layer Normalization
        self.ln1 = nn.LayerNorm(hidden_size)
        self.ln2 = nn.LayerNorm(hidden_size)
        
        # Output quantile heads
        self.output_layer = nn.Linear(hidden_size, 3)
        
    def forward(self, x):
        batch_size, seq_len, _ = x.shape
        
        # Variable Selection
        x, variable_weights = self.vsn_encoder(x)
        
        # LSTM Encoder
        encoder_out, (h, c) = self.lstm_encoder(x)
        encoder_out = self.grn_encoder(encoder_out)
        
        # Self-Attention
        attn_out, attention_weights = self.attention(
            encoder_out, encoder_out, encoder_out
        )
        x = self.ln1(encoder_out + attn_out)
        
        # Feed-Forward
        ff_out = self.ff(x)
        x = self.ln2(x + ff_out)
        
        # Take last hidden state
        x = x[:, -1, :]
        
        # Output
        output = self.output_layer(x)
        
        return output, {
            'variable_weights': variable_weights,
            'attention_weights': attention_weights
        }


class VariableSelectionNetwork(nn.Module):
    """Выбор важных переменных с помощью Softmax attention"""
    
    def __init__(self, input_size, hidden_size, dropout):
        super().__init__()
        
        self.flattened_grn = GatedResidualNetwork(
            input_size, hidden_size, dropout, context_size=hidden_size
        )
        
        self.single_grns = nn.ModuleList([
            GatedResidualNetwork(1, hidden_size, dropout)
            for _ in range(input_size)
        ])
        
        self.softmax = nn.Softmax(dim=-1)
        
    def forward(self, x):
        # x: (batch, seq_len, features)
        
        # Process each variable
        variable_outputs = []
        for i, grn in enumerate(self.single_grns):
            variable_outputs.append(grn(x[:, :, i:i+1]))
        
        variable_outputs = torch.stack(variable_outputs, dim=-1)  # (batch, seq, hidden, features)
        
        # Variable weights
        flat_embedding = self.flattened_grn(x.mean(dim=1))  # (batch, hidden)
        variable_weights = self.softmax(flat_embedding.unsqueeze(1).unsqueeze(1))
        
        # Weighted sum
        output = (variable_outputs * variable_weights).sum(dim=-1)
        
        return output, variable_weights.squeeze()


class GatedResidualNetwork(nn.Module):
    """Gated Residual Network (GRN) из TFT"""
    
    def __init__(self, input_size, hidden_size, dropout, context_size=None):
        super().__init__()
        
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        
        if context_size is not None:
            self.context = nn.Linear(context_size, hidden_size, bias=False)
        else:
            self.context = None
        
        self.gate = nn.Linear(hidden_size, hidden_size)
        self.ln = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)
        
        # Skip connection
        self.skip = nn.Linear(input_size, hidden_size) if input_size != hidden_size else None
        
    def forward(self, x, context=None):
        residual = self.skip(x) if self.skip else x
        
        x = self.fc1(x)
        if self.context is not None and context is not None:
            x = x + self.context(context)
        
        x = F.elu(x)
        x = self.fc2(x)
        x = self.dropout(x)
        
        # Gated Linear Unit
        gate = torch.sigmoid(self.gate(x))
        x = gate * x
        
        return self.ln(x + residual)
```

---

## 4. Smart Money Concepts (SMC) вместо классических индикаторов

### 4.1 Философия подхода

**Текущий подход (правильный):**
- RSI 6H таймфрейм - основа для входов
- Зоны перепроданности (<30) и перекупленности (>70)
- Время ожидания для отложенного входа

**Проблема классических индикаторов:**
- MACD, Stochastic, Williams %R - создают шум
- Множество ложных сигналов
- Не учитывают институциональную активность

**Решение - Smart Money Concepts:**
- Основаны на поведении крупных игроков (институционалы, банки)
- Order Blocks, FVG, Liquidity - реальные зоны интереса
- Меньше сигналов, но более качественные

### 4.2 Реализация Smart Money Concepts

```python
class SmartMoneyFeatures:
    """
    Smart Money Concepts (SMC) для институционального анализа рынка
    
    Основа: RSI 6H + Order Blocks + FVG + Liquidity + Market Structure
    Минимум шума, максимум качества сигналов
    """
    
    def __init__(self, rsi_period: int = 14):
        self.rsi_period = rsi_period
        self.swing_lookback = 5  # Свечей для определения swing point
    
    # ==================== RSI (ОСНОВА) ====================
    
    def compute_rsi(self, df: pd.DataFrame) -> pd.Series:
        """RSI - основной индикатор для входов"""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def detect_rsi_divergence(self, df: pd.DataFrame, rsi: pd.Series) -> pd.Series:
        """
        Детектирует дивергенции RSI
        
        Bullish divergence: цена делает LL, RSI делает HL
        Bearish divergence: цена делает HH, RSI делает LH
        """
        lookback = 10
        divergence = pd.Series(0, index=df.index)
        
        for i in range(lookback, len(df)):
            # Bullish divergence
            if (df['low'].iloc[i] < df['low'].iloc[i-lookback] and 
                rsi.iloc[i] > rsi.iloc[i-lookback]):
                divergence.iloc[i] = 1  # Bullish
            # Bearish divergence
            elif (df['high'].iloc[i] > df['high'].iloc[i-lookback] and 
                  rsi.iloc[i] < rsi.iloc[i-lookback]):
                divergence.iloc[i] = -1  # Bearish
        
        return divergence
    
    # ==================== ORDER BLOCKS ====================
    
    def find_order_blocks(self, df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """
        Находит Order Blocks - зоны накопления крупных игроков
        
        Bullish OB: последняя медвежья свеча перед импульсным ростом
        Bearish OB: последняя бычья свеча перед импульсным падением
        """
        order_blocks = []
        
        # Определяем импульсные движения (более 2% за 3 свечи)
        impulse_threshold = 0.02
        
        for i in range(3, min(lookback, len(df))):
            idx = len(df) - i
            
            # Проверяем импульс вверх (для Bullish OB)
            if idx + 3 < len(df):
                move = (df['close'].iloc[idx+3] - df['close'].iloc[idx]) / df['close'].iloc[idx]
                
                if move > impulse_threshold:
                    # Ищем последнюю медвежью свечу перед импульсом
                    for j in range(idx, max(idx-5, 0), -1):
                        if df['close'].iloc[j] < df['open'].iloc[j]:  # Медвежья свеча
                            order_blocks.append({
                                'type': 'bullish',
                                'high': df['high'].iloc[j],
                                'low': df['low'].iloc[j],
                                'index': j,
                                'strength': move,
                                'tested': self._is_ob_tested(df, j, 'bullish')
                            })
                            break
                
                elif move < -impulse_threshold:
                    # Ищем последнюю бычью свечу перед падением
                    for j in range(idx, max(idx-5, 0), -1):
                        if df['close'].iloc[j] > df['open'].iloc[j]:  # Бычья свеча
                            order_blocks.append({
                                'type': 'bearish',
                                'high': df['high'].iloc[j],
                                'low': df['low'].iloc[j],
                                'index': j,
                                'strength': abs(move),
                                'tested': self._is_ob_tested(df, j, 'bearish')
                            })
                            break
        
        return order_blocks
    
    def _is_ob_tested(self, df: pd.DataFrame, ob_index: int, ob_type: str) -> bool:
        """Проверяет, был ли Order Block протестирован"""
        ob_high = df['high'].iloc[ob_index]
        ob_low = df['low'].iloc[ob_index]
        
        for i in range(ob_index + 1, len(df)):
            if ob_type == 'bullish':
                # Bullish OB тестируется когда цена возвращается в зону
                if df['low'].iloc[i] <= ob_high and df['low'].iloc[i] >= ob_low:
                    return True
            else:  # bearish
                if df['high'].iloc[i] >= ob_low and df['high'].iloc[i] <= ob_high:
                    return True
        
        return False
    
    # ==================== FAIR VALUE GAPS (FVG) ====================
    
    def find_fvg(self, df: pd.DataFrame) -> List[Dict]:
        """
        Находит Fair Value Gaps (FVG) - зоны дисбаланса
        
        Bullish FVG: gap между high[i-2] и low[i] (цена не заполнила зону)
        Bearish FVG: gap между low[i-2] и high[i]
        """
        fvg_list = []
        
        for i in range(2, len(df)):
            # Bullish FVG
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gap_size = (df['low'].iloc[i] - df['high'].iloc[i-2]) / df['close'].iloc[i]
                if gap_size > 0.001:  # Минимум 0.1% gap
                    fvg_list.append({
                        'type': 'bullish',
                        'top': df['low'].iloc[i],
                        'bottom': df['high'].iloc[i-2],
                        'index': i,
                        'size_pct': gap_size * 100,
                        'mitigated': self._is_fvg_mitigated(df, i, 'bullish', 
                                                           df['high'].iloc[i-2], df['low'].iloc[i])
                    })
            
            # Bearish FVG
            if df['high'].iloc[i] < df['low'].iloc[i-2]:
                gap_size = (df['low'].iloc[i-2] - df['high'].iloc[i]) / df['close'].iloc[i]
                if gap_size > 0.001:
                    fvg_list.append({
                        'type': 'bearish',
                        'top': df['low'].iloc[i-2],
                        'bottom': df['high'].iloc[i],
                        'index': i,
                        'size_pct': gap_size * 100,
                        'mitigated': self._is_fvg_mitigated(df, i, 'bearish',
                                                           df['high'].iloc[i], df['low'].iloc[i-2])
                    })
        
        return fvg_list
    
    def _is_fvg_mitigated(self, df: pd.DataFrame, fvg_index: int, 
                          fvg_type: str, bottom: float, top: float) -> bool:
        """Проверяет, был ли FVG заполнен (mitigated)"""
        for i in range(fvg_index + 1, len(df)):
            if fvg_type == 'bullish':
                # Bullish FVG mitigated когда цена опускается в gap
                if df['low'].iloc[i] <= top:
                    return True
            else:  # bearish
                # Bearish FVG mitigated когда цена поднимается в gap
                if df['high'].iloc[i] >= bottom:
                    return True
        return False
    
    # ==================== LIQUIDITY ZONES ====================
    
    def find_liquidity_zones(self, df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """
        Находит зоны ликвидности - места со скоплением стоп-лоссов
        
        - Equal highs/lows (двойные/тройные вершины)
        - Зоны выше swing high / ниже swing low
        """
        liquidity_zones = []
        tolerance = 0.002  # 0.2% допуск для "равных" уровней
        
        # Находим swing points
        swing_highs = self._find_swing_highs(df, self.swing_lookback)
        swing_lows = self._find_swing_lows(df, self.swing_lookback)
        
        # Ищем equal highs (зоны продаж / buy-side liquidity)
        for i, sh1 in enumerate(swing_highs):
            for sh2 in swing_highs[i+1:]:
                if abs(sh1['price'] - sh2['price']) / sh1['price'] < tolerance:
                    liquidity_zones.append({
                        'type': 'buy_side',  # Ликвидность сверху (стопы шортов)
                        'price': max(sh1['price'], sh2['price']),
                        'strength': 2,  # Двойная вершина
                        'indices': [sh1['index'], sh2['index']]
                    })
        
        # Ищем equal lows (зоны покупок / sell-side liquidity)
        for i, sl1 in enumerate(swing_lows):
            for sl2 in swing_lows[i+1:]:
                if abs(sl1['price'] - sl2['price']) / sl1['price'] < tolerance:
                    liquidity_zones.append({
                        'type': 'sell_side',  # Ликвидность снизу (стопы лонгов)
                        'price': min(sl1['price'], sl2['price']),
                        'strength': 2,
                        'indices': [sl1['index'], sl2['index']]
                    })
        
        return liquidity_zones
    
    # ==================== MARKET STRUCTURE ====================
    
    def _find_swing_highs(self, df: pd.DataFrame, lookback: int) -> List[Dict]:
        """Находит swing highs"""
        swing_highs = []
        for i in range(lookback, len(df) - lookback):
            if df['high'].iloc[i] == df['high'].iloc[i-lookback:i+lookback+1].max():
                swing_highs.append({
                    'price': df['high'].iloc[i],
                    'index': i
                })
        return swing_highs
    
    def _find_swing_lows(self, df: pd.DataFrame, lookback: int) -> List[Dict]:
        """Находит swing lows"""
        swing_lows = []
        for i in range(lookback, len(df) - lookback):
            if df['low'].iloc[i] == df['low'].iloc[i-lookback:i+lookback+1].min():
                swing_lows.append({
                    'price': df['low'].iloc[i],
                    'index': i
                })
        return swing_lows
    
    def detect_bos(self, df: pd.DataFrame) -> Dict:
        """
        Детектирует Break of Structure (BOS)
        
        Bullish BOS: пробой предыдущего swing high
        Bearish BOS: пробой предыдущего swing low
        """
        swing_highs = self._find_swing_highs(df, self.swing_lookback)
        swing_lows = self._find_swing_lows(df, self.swing_lookback)
        
        current_price = df['close'].iloc[-1]
        
        # Проверяем пробой последнего swing high
        if swing_highs:
            last_sh = swing_highs[-1]['price']
            if current_price > last_sh:
                return {
                    'type': 'bullish',
                    'broken_level': last_sh,
                    'current_price': current_price,
                    'strength': (current_price - last_sh) / last_sh * 100
                }
        
        # Проверяем пробой последнего swing low
        if swing_lows:
            last_sl = swing_lows[-1]['price']
            if current_price < last_sl:
                return {
                    'type': 'bearish',
                    'broken_level': last_sl,
                    'current_price': current_price,
                    'strength': (last_sl - current_price) / last_sl * 100
                }
        
        return {'type': 'none'}
    
    def detect_choch(self, df: pd.DataFrame) -> Dict:
        """
        Детектирует Change of Character (CHoCH) - первый признак смены тренда
        
        В восходящем тренде: первый LL (пробой swing low)
        В нисходящем тренде: первый HH (пробой swing high)
        """
        structure = self.analyze_market_structure(df)
        bos = self.detect_bos(df)
        
        # CHoCH = BOS против текущего тренда
        if structure['trend'] == 'bullish' and bos['type'] == 'bearish':
            return {
                'detected': True,
                'type': 'bearish_choch',
                'message': 'Смена тренда с бычьего на медвежий',
                'broken_level': bos['broken_level']
            }
        elif structure['trend'] == 'bearish' and bos['type'] == 'bullish':
            return {
                'detected': True,
                'type': 'bullish_choch',
                'message': 'Смена тренда с медвежьего на бычий',
                'broken_level': bos['broken_level']
            }
        
        return {'detected': False}
    
    def analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """
        Анализирует рыночную структуру
        
        HH + HL = Bullish (восходящий тренд)
        LH + LL = Bearish (нисходящий тренд)
        """
        swing_highs = self._find_swing_highs(df, self.swing_lookback)
        swing_lows = self._find_swing_lows(df, self.swing_lookback)
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {'trend': 'undefined', 'structure': []}
        
        # Анализируем последние swing points
        hh = swing_highs[-1]['price'] > swing_highs[-2]['price']  # Higher High
        hl = swing_lows[-1]['price'] > swing_lows[-2]['price']    # Higher Low
        lh = swing_highs[-1]['price'] < swing_highs[-2]['price']  # Lower High
        ll = swing_lows[-1]['price'] < swing_lows[-2]['price']    # Lower Low
        
        if hh and hl:
            trend = 'bullish'
        elif lh and ll:
            trend = 'bearish'
        else:
            trend = 'ranging'
        
        return {
            'trend': trend,
            'higher_high': hh,
            'higher_low': hl,
            'lower_high': lh,
            'lower_low': ll,
            'last_swing_high': swing_highs[-1]['price'],
            'last_swing_low': swing_lows[-1]['price']
        }
    
    def get_price_zone(self, df: pd.DataFrame, lookback: int = 50) -> Dict:
        """
        Определяет зону цены: Premium, Discount или Equilibrium
        
        Premium (верхние 50%): зона для продаж
        Discount (нижние 50%): зона для покупок
        Equilibrium: середина диапазона
        """
        recent = df.iloc[-lookback:]
        high = recent['high'].max()
        low = recent['low'].min()
        current = df['close'].iloc[-1]
        
        range_size = high - low
        equilibrium = low + range_size * 0.5
        
        position = (current - low) / range_size if range_size > 0 else 0.5
        
        if position > 0.7:
            zone = 'premium'
            recommendation = 'Зона для продаж (SHORT)'
        elif position < 0.3:
            zone = 'discount'
            recommendation = 'Зона для покупок (LONG)'
        else:
            zone = 'equilibrium'
            recommendation = 'Нейтральная зона'
        
        return {
            'zone': zone,
            'position_pct': position * 100,
            'equilibrium': equilibrium,
            'range_high': high,
            'range_low': low,
            'recommendation': recommendation
        }
    
    # ==================== КОМПЛЕКСНЫЙ СИГНАЛ ====================
    
    def get_smc_signal(self, df: pd.DataFrame) -> Dict:
        """
        Возвращает комплексный сигнал на основе всех SMC факторов
        """
        # RSI
        rsi = self.compute_rsi(df)
        current_rsi = rsi.iloc[-1]
        rsi_div = self.detect_rsi_divergence(df, rsi)
        
        # SMC компоненты
        order_blocks = self.find_order_blocks(df)
        fvg_list = self.find_fvg(df)
        liquidity = self.find_liquidity_zones(df)
        structure = self.analyze_market_structure(df)
        bos = self.detect_bos(df)
        choch = self.detect_choch(df)
        price_zone = self.get_price_zone(df)
        
        # Анализ сигналов
        reasons = []
        score = 0  # -100 до +100
        
        # RSI сигналы
        if current_rsi <= 30:
            score += 30
            reasons.append(f'RSI перепродан ({current_rsi:.1f})')
        elif current_rsi >= 70:
            score -= 30
            reasons.append(f'RSI перекуплен ({current_rsi:.1f})')
        
        # RSI дивергенция
        if rsi_div.iloc[-1] == 1:
            score += 20
            reasons.append('Bullish RSI дивергенция')
        elif rsi_div.iloc[-1] == -1:
            score -= 20
            reasons.append('Bearish RSI дивергенция')
        
        # Order Blocks
        current_price = df['close'].iloc[-1]
        for ob in order_blocks[-5:]:  # Последние 5 OB
            if ob['type'] == 'bullish' and not ob['tested']:
                if ob['low'] <= current_price <= ob['high']:
                    score += 25
                    reasons.append('Цена в зоне Bullish Order Block')
            elif ob['type'] == 'bearish' and not ob['tested']:
                if ob['low'] <= current_price <= ob['high']:
                    score -= 25
                    reasons.append('Цена в зоне Bearish Order Block')
        
        # FVG
        for fvg in fvg_list[-5:]:
            if not fvg['mitigated']:
                if fvg['type'] == 'bullish' and fvg['bottom'] <= current_price <= fvg['top']:
                    score += 15
                    reasons.append('Цена в Bullish FVG (незаполненный)')
                elif fvg['type'] == 'bearish' and fvg['bottom'] <= current_price <= fvg['top']:
                    score -= 15
                    reasons.append('Цена в Bearish FVG (незаполненный)')
        
        # Market Structure
        if structure['trend'] == 'bullish':
            score += 10
            reasons.append('Бычья структура рынка (HH+HL)')
        elif structure['trend'] == 'bearish':
            score -= 10
            reasons.append('Медвежья структура рынка (LH+LL)')
        
        # CHoCH (сильный сигнал разворота)
        if choch['detected']:
            if choch['type'] == 'bullish_choch':
                score += 30
                reasons.append('CHoCH: разворот на бычий')
            else:
                score -= 30
                reasons.append('CHoCH: разворот на медвежий')
        
        # Price Zone
        if price_zone['zone'] == 'discount' and score > 0:
            score += 10
            reasons.append('Цена в Discount зоне (хорошо для LONG)')
        elif price_zone['zone'] == 'premium' and score < 0:
            score -= 10
            reasons.append('Цена в Premium зоне (хорошо для SHORT)')
        
        # Определяем сигнал
        if score >= 40:
            signal = 'LONG'
            confidence = min(abs(score), 100)
        elif score <= -40:
            signal = 'SHORT'
            confidence = min(abs(score), 100)
        else:
            signal = 'WAIT'
            confidence = 100 - abs(score)
        
        return {
            'signal': signal,
            'score': score,
            'confidence': confidence,
            'reasons': reasons,
            'rsi': current_rsi,
            'structure': structure['trend'],
            'price_zone': price_zone['zone'],
            'order_blocks_count': len([ob for ob in order_blocks if not ob['tested']]),
            'unfilled_fvg_count': len([fvg for fvg in fvg_list if not fvg['mitigated']])
        }
```

---

## 5. Оптимизация гиперпараметров

### 5.1 Проблема текущего Grid Search

```python
# Текущий Grid Search (ai_strategy_optimizer.py:634-884)
# Вложенные циклы - O(n^11) комбинаций!
for rsi_long_entry in rsi_long_entry_range[:4]:
    for rsi_short_entry in rsi_short_entry_range[:4]:
        for rsi_long_exit in rsi_long_exit_range[:3]:
            # ... еще 8 вложенных циклов
```

**Проблемы:**
- Экспоненциальная сложность
- Ограничение на 200 итераций слишком мало
- Не учитывает историю предыдущих попыток

### 5.2 Предлагаемый Bayesian Optimization

```python
from typing import Dict, Any, Callable, Optional
import numpy as np
from scipy.stats import norm
from scipy.optimize import minimize

class BayesianOptimizer:
    """
    Bayesian Optimization для гиперпараметров с Gaussian Process
    
    Преимущества:
    - Находит оптимум за меньше итераций
    - Учитывает историю предыдущих попыток
    - Автоматически балансирует exploration vs exploitation
    """
    
    def __init__(
        self,
        param_space: Dict[str, Dict[str, Any]],
        objective_function: Callable,
        n_initial_points: int = 10,
        acquisition_function: str = 'ei'  # 'ei' или 'ucb'
    ):
        """
        Args:
            param_space: Пространство параметров
                {
                    'rsi_long': {'min': 20, 'max': 35, 'type': 'int'},
                    'stop_loss': {'min': 5.0, 'max': 25.0, 'type': 'float'},
                }
            objective_function: Функция для оптимизации (должна возвращать score)
            n_initial_points: Начальное количество случайных точек
            acquisition_function: 'ei' (Expected Improvement) или 'ucb' (Upper Confidence Bound)
        """
        self.param_space = param_space
        self.objective = objective_function
        self.n_initial = n_initial_points
        self.acq_func = acquisition_function
        
        self.X_observed = []  # Наблюдаемые параметры
        self.y_observed = []  # Наблюдаемые результаты
        
        self.best_params = None
        self.best_score = float('-inf')
        
    def optimize(self, n_iterations: int = 50) -> Dict[str, Any]:
        """
        Запускает оптимизацию
        
        Args:
            n_iterations: Количество итераций
        
        Returns:
            Лучшие найденные параметры
        """
        # 1. Начальная фаза - случайный поиск
        for _ in range(self.n_initial):
            params = self._sample_random_params()
            score = self._evaluate(params)
            self._update(params, score)
        
        # 2. Основная фаза - Bayesian optimization
        for i in range(n_iterations - self.n_initial):
            # Находим следующую точку для оценки
            next_params = self._get_next_params()
            score = self._evaluate(next_params)
            self._update(next_params, score)
            
            if (i + 1) % 10 == 0:
                logger.info(f"[BayesOpt] Итерация {i + 1 + self.n_initial}/{n_iterations}, "
                          f"лучший score: {self.best_score:.4f}")
        
        return self.best_params
    
    def _sample_random_params(self) -> Dict[str, Any]:
        """Случайная выборка параметров"""
        params = {}
        for name, space in self.param_space.items():
            if space['type'] == 'int':
                params[name] = np.random.randint(space['min'], space['max'] + 1)
            else:
                params[name] = np.random.uniform(space['min'], space['max'])
        return params
    
    def _evaluate(self, params: Dict[str, Any]) -> float:
        """Оценивает параметры"""
        return self.objective(params)
    
    def _update(self, params: Dict[str, Any], score: float):
        """Обновляет историю наблюдений"""
        self.X_observed.append(self._params_to_array(params))
        self.y_observed.append(score)
        
        if score > self.best_score:
            self.best_score = score
            self.best_params = params
    
    def _params_to_array(self, params: Dict[str, Any]) -> np.ndarray:
        """Конвертирует параметры в массив"""
        return np.array([params[name] for name in sorted(self.param_space.keys())])
    
    def _array_to_params(self, arr: np.ndarray) -> Dict[str, Any]:
        """Конвертирует массив в параметры"""
        params = {}
        for i, name in enumerate(sorted(self.param_space.keys())):
            value = arr[i]
            if self.param_space[name]['type'] == 'int':
                value = int(round(value))
            params[name] = value
        return params
    
    def _get_next_params(self) -> Dict[str, Any]:
        """Находит следующую точку для оценки используя acquisition function"""
        X = np.array(self.X_observed)
        y = np.array(self.y_observed)
        
        # Подгоняем Gaussian Process
        # Упрощенная версия - используем RBF kernel
        mean, std = self._fit_gp(X, y)
        
        # Оптимизируем acquisition function
        best_x = None
        best_acq = float('-inf')
        
        # Multi-start оптимизация
        for _ in range(100):
            x0 = self._sample_random_params()
            x0_arr = self._params_to_array(x0)
            
            if self.acq_func == 'ei':
                acq_value = self._expected_improvement(x0_arr, mean, std, y.max())
            else:
                acq_value = self._ucb(x0_arr, mean, std)
            
            if acq_value > best_acq:
                best_acq = acq_value
                best_x = x0_arr
        
        # Локальная оптимизация
        bounds = [(self.param_space[name]['min'], self.param_space[name]['max'])
                 for name in sorted(self.param_space.keys())]
        
        result = minimize(
            lambda x: -self._expected_improvement(x, mean, std, y.max()),
            best_x,
            bounds=bounds,
            method='L-BFGS-B'
        )
        
        return self._array_to_params(result.x)
    
    def _fit_gp(self, X: np.ndarray, y: np.ndarray):
        """
        Подгоняет Gaussian Process (упрощенная версия)
        
        В реальной имплементации лучше использовать GPyTorch или sklearn.gaussian_process
        """
        # Нормализация
        y_mean = y.mean()
        y_std = y.std() + 1e-6
        y_normalized = (y - y_mean) / y_std
        
        # RBF kernel
        def kernel(x1, x2, length_scale=1.0):
            dist = np.sum((x1 - x2) ** 2)
            return np.exp(-dist / (2 * length_scale ** 2))
        
        # Prediction function
        def predict(x_new):
            k_new = np.array([kernel(x_new, xi) for xi in X])
            K = np.array([[kernel(xi, xj) for xj in X] for xi in X])
            K += 1e-6 * np.eye(len(X))  # Numerical stability
            
            K_inv = np.linalg.inv(K)
            mean = k_new @ K_inv @ y_normalized * y_std + y_mean
            var = 1 - k_new @ K_inv @ k_new
            std = np.sqrt(max(var, 1e-6)) * y_std
            
            return mean, std
        
        return predict
    
    def _expected_improvement(
        self, x: np.ndarray, gp_predict, y_best: float, xi: float = 0.01
    ) -> float:
        """Expected Improvement acquisition function"""
        mean, std = gp_predict(x)
        
        if std < 1e-6:
            return 0.0
        
        z = (mean - y_best - xi) / std
        ei = (mean - y_best - xi) * norm.cdf(z) + std * norm.pdf(z)
        
        return ei
    
    def _ucb(self, x: np.ndarray, gp_predict, kappa: float = 2.0) -> float:
        """Upper Confidence Bound acquisition function"""
        mean, std = gp_predict(x)
        return mean + kappa * std


# Пример использования
def optimize_strategy_bayesian(symbol: str, candles: List[Dict]) -> Optional[Dict]:
    """Оптимизация стратегии с Bayesian Optimization"""
    
    param_space = {
        'rsi_long_threshold': {'min': 20, 'max': 35, 'type': 'int'},
        'rsi_short_threshold': {'min': 65, 'max': 80, 'type': 'int'},
        'rsi_exit_long': {'min': 55, 'max': 75, 'type': 'int'},
        'rsi_exit_short': {'min': 25, 'max': 45, 'type': 'int'},
        'max_loss_percent': {'min': 8.0, 'max': 25.0, 'type': 'float'},
        'take_profit_percent': {'min': 10.0, 'max': 40.0, 'type': 'float'},
        'trailing_stop_activation': {'min': 10.0, 'max': 70.0, 'type': 'float'},
        'trailing_stop_distance': {'min': 5.0, 'max': 40.0, 'type': 'float'},
    }
    
    def objective(params: Dict[str, Any]) -> float:
        """Симулирует торговлю и возвращает score"""
        simulated_trades = simulate_trading(candles, params)
        
        if len(simulated_trades) < 5:
            return -1000  # Недостаточно сделок
        
        win_rate = sum(1 for t in simulated_trades if t['is_successful']) / len(simulated_trades)
        total_pnl = sum(t['pnl_pct'] for t in simulated_trades)
        sharpe = calculate_sharpe(simulated_trades)
        
        # Комбинированный score
        score = win_rate * 100 + total_pnl * 0.5 + sharpe * 10
        
        return score
    
    optimizer = BayesianOptimizer(
        param_space=param_space,
        objective_function=objective,
        n_initial_points=20
    )
    
    best_params = optimizer.optimize(n_iterations=100)
    
    return {
        **best_params,
        'optimization_score': optimizer.best_score,
        'optimization_method': 'bayesian'
    }
```

### 5.3 Добавление Optuna для автоматического подбора

```python
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import HyperbandPruner

def optimize_with_optuna(symbol: str, candles: List[Dict], n_trials: int = 100):
    """Оптимизация с Optuna (state-of-the-art)"""
    
    def objective(trial: optuna.Trial) -> float:
        # Параметры стратегии
        params = {
            'rsi_long_threshold': trial.suggest_int('rsi_long_threshold', 20, 35),
            'rsi_short_threshold': trial.suggest_int('rsi_short_threshold', 65, 80),
            'rsi_exit_long': trial.suggest_int('rsi_exit_long', 55, 75),
            'rsi_exit_short': trial.suggest_int('rsi_exit_short', 25, 45),
            'max_loss_percent': trial.suggest_float('max_loss_percent', 8.0, 25.0),
            'take_profit_percent': trial.suggest_float('take_profit_percent', 10.0, 40.0),
            'trailing_activation': trial.suggest_float('trailing_activation', 10.0, 70.0),
            'trailing_distance': trial.suggest_float('trailing_distance', 5.0, 40.0),
        }
        
        # Симуляция
        trades = simulate_trading(candles, params)
        
        if len(trades) < 10:
            raise optuna.TrialPruned()
        
        win_rate = sum(1 for t in trades if t['is_successful']) / len(trades)
        total_pnl = sum(t['pnl_pct'] for t in trades)
        
        # Цель: максимизировать win_rate и PnL
        return win_rate * 100 + total_pnl * 0.1
    
    # Создаем study с TPE sampler и Hyperband pruner
    study = optuna.create_study(
        direction='maximize',
        sampler=TPESampler(seed=42),
        pruner=HyperbandPruner()
    )
    
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    
    return study.best_params, study.best_value
```

---

## 6. Ensemble методы

### 6.1 Voting Ensemble

```python
class VotingEnsemble:
    """
    Ensemble из нескольких моделей с голосованием
    """
    
    def __init__(self):
        self.models = {}
        self.weights = {}
        
    def add_model(self, name: str, model: nn.Module, weight: float = 1.0):
        """Добавляет модель в ensemble"""
        self.models[name] = model
        self.weights[name] = weight
    
    def predict(self, x: torch.Tensor) -> Dict[str, Any]:
        """
        Предсказание с взвешенным голосованием
        
        Returns:
            {
                'direction': -1 или 1,
                'change_percent': float,
                'confidence': float,
                'model_predictions': dict с предсказаниями каждой модели
            }
        """
        predictions = {}
        total_weight = sum(self.weights.values())
        
        direction_votes = 0
        change_sum = 0
        confidence_sum = 0
        
        for name, model in self.models.items():
            model.eval()
            with torch.no_grad():
                pred = model(x)
                
            direction = 1 if pred[0, 0].item() > 0 else -1
            change = pred[0, 1].item()
            conf = abs(pred[0, 0].item())  # Уверенность из направления
            
            weight = self.weights[name] / total_weight
            
            direction_votes += direction * weight
            change_sum += change * weight
            confidence_sum += conf * weight
            
            predictions[name] = {
                'direction': direction,
                'change_percent': change,
                'confidence': conf
            }
        
        return {
            'direction': 1 if direction_votes > 0 else -1,
            'change_percent': change_sum,
            'confidence': confidence_sum,
            'model_predictions': predictions
        }


class StackingEnsemble(nn.Module):
    """
    Stacking Ensemble - мета-модель обучается на выходах базовых моделей
    """
    
    def __init__(
        self,
        base_models: Dict[str, nn.Module],
        meta_hidden_size: int = 64
    ):
        super().__init__()
        
        self.base_models = nn.ModuleDict(base_models)
        
        # Количество выходов от всех моделей
        n_base_outputs = len(base_models) * 3  # Каждая модель дает 3 выхода
        
        # Мета-модель
        self.meta_model = nn.Sequential(
            nn.Linear(n_base_outputs, meta_hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(meta_hidden_size, meta_hidden_size // 2),
            nn.ReLU(),
            nn.Linear(meta_hidden_size // 2, 3)
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Получаем предсказания базовых моделей
        base_outputs = []
        
        for name, model in self.base_models.items():
            with torch.no_grad():  # Не обучаем базовые модели
                output = model(x)
            base_outputs.append(output)
        
        # Конкатенируем все выходы
        stacked = torch.cat(base_outputs, dim=-1)
        
        # Мета-модель
        return self.meta_model(stacked)
    
    def train_meta_model(
        self,
        train_loader: DataLoader,
        epochs: int = 50,
        lr: float = 0.001
    ):
        """Обучает только мета-модель"""
        optimizer = optim.Adam(self.meta_model.parameters(), lr=lr)
        criterion = nn.MSELoss()
        
        for epoch in range(epochs):
            total_loss = 0
            
            for batch_x, batch_y in train_loader:
                optimizer.zero_grad()
                
                output = self.forward(batch_x)
                loss = criterion(output, batch_y)
                
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Meta-model Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(train_loader):.6f}")
```

---

## 7. Reinforcement Learning для торговли

### 7.1 Зачем RL?

- Модель учится напрямую максимизировать прибыль
- Учитывает последовательность действий
- Адаптируется к изменениям рынка

### 7.2 DQN (Deep Q-Network) для торговли

```python
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
import random

class TradingEnvironment:
    """
    Торговое окружение для RL
    """
    
    def __init__(
        self,
        candles: List[Dict],
        initial_balance: float = 10000,
        position_size: float = 0.1,  # 10% баланса на сделку
        fee: float = 0.001  # 0.1% комиссия
    ):
        self.candles = candles
        self.initial_balance = initial_balance
        self.position_size_ratio = position_size
        self.fee = fee
        
        self.reset()
    
    def reset(self) -> np.ndarray:
        """Сброс окружения"""
        self.current_step = 60  # Начинаем после достаточного количества свечей
        self.balance = self.initial_balance
        self.position = None  # {'direction': 'LONG'/'SHORT', 'entry_price': float, 'size': float}
        self.done = False
        self.trade_history = []
        
        return self._get_state()
    
    def _get_state(self) -> np.ndarray:
        """Получает текущее состояние"""
        # Берем последние 60 свечей
        recent_candles = self.candles[self.current_step-60:self.current_step]
        
        # Нормализуем цены относительно последней цены
        last_close = recent_candles[-1]['close']
        
        state = []
        for candle in recent_candles:
            state.extend([
                candle['close'] / last_close - 1,  # Нормализованная цена
                candle['volume'] / np.mean([c['volume'] for c in recent_candles]) - 1,  # Норм. объем
                (candle['high'] - candle['low']) / last_close,  # Range
            ])
        
        # Добавляем информацию о позиции
        if self.position:
            state.append(1 if self.position['direction'] == 'LONG' else -1)
            state.append((last_close - self.position['entry_price']) / self.position['entry_price'])
        else:
            state.append(0)
            state.append(0)
        
        return np.array(state, dtype=np.float32)
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Выполняет действие
        
        Args:
            action: 0 = HOLD, 1 = BUY/LONG, 2 = SELL/SHORT, 3 = CLOSE
        
        Returns:
            (next_state, reward, done, info)
        """
        current_price = self.candles[self.current_step]['close']
        reward = 0
        info = {}
        
        # Выполняем действие
        if action == 1 and self.position is None:  # BUY/LONG
            size = self.balance * self.position_size_ratio
            self.position = {
                'direction': 'LONG',
                'entry_price': current_price,
                'size': size / current_price
            }
            self.balance -= size * (1 + self.fee)
            info['action'] = 'OPEN_LONG'
            
        elif action == 2 and self.position is None:  # SELL/SHORT
            size = self.balance * self.position_size_ratio
            self.position = {
                'direction': 'SHORT',
                'entry_price': current_price,
                'size': size / current_price
            }
            self.balance -= size * self.fee  # Только комиссия для шорта
            info['action'] = 'OPEN_SHORT'
            
        elif action == 3 and self.position is not None:  # CLOSE
            if self.position['direction'] == 'LONG':
                pnl = (current_price - self.position['entry_price']) * self.position['size']
            else:  # SHORT
                pnl = (self.position['entry_price'] - current_price) * self.position['size']
            
            pnl -= abs(pnl) * self.fee  # Комиссия
            reward = pnl / self.initial_balance * 100  # Reward в % от начального баланса
            
            self.balance += self.position['size'] * current_price + pnl
            
            self.trade_history.append({
                'direction': self.position['direction'],
                'entry_price': self.position['entry_price'],
                'exit_price': current_price,
                'pnl': pnl,
                'pnl_percent': pnl / (self.position['size'] * self.position['entry_price']) * 100
            })
            
            self.position = None
            info['action'] = 'CLOSE'
            info['pnl'] = pnl
        
        # Переходим к следующему шагу
        self.current_step += 1
        
        # Проверяем завершение
        if self.current_step >= len(self.candles) - 1:
            self.done = True
            # Закрываем открытую позицию в конце
            if self.position:
                _, close_reward, _, _ = self.step(3)
                reward += close_reward
        
        # Reward shaping: штраф за бездействие с открытой позицией
        if action == 0 and self.position:
            # Небольшой reward/penalty за держание позиции
            if self.position['direction'] == 'LONG':
                unrealized_pnl = (current_price - self.position['entry_price']) / self.position['entry_price']
            else:
                unrealized_pnl = (self.position['entry_price'] - current_price) / self.position['entry_price']
            reward += unrealized_pnl * 0.1  # Маленький reward за положительный PnL
        
        return self._get_state(), reward, self.done, info


class DQNNetwork(nn.Module):
    """Deep Q-Network"""
    
    def __init__(self, state_size: int, action_size: int = 4):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(state_size, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, action_size)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class DQNAgent:
    """DQN Agent для торговли"""
    
    def __init__(
        self,
        state_size: int,
        action_size: int = 4,
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995,
        memory_size: int = 10000,
        batch_size: int = 64
    ):
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        
        # Neural networks
        self.policy_net = DQNNetwork(state_size, action_size)
        self.target_net = DQNNetwork(state_size, action_size)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        self.memory = deque(maxlen=memory_size)
        
    def act(self, state: np.ndarray, training: bool = True) -> int:
        """Выбирает действие"""
        if training and random.random() < self.epsilon:
            return random.randrange(self.action_size)
        
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0)
            q_values = self.policy_net(state_tensor)
            return q_values.argmax().item()
    
    def remember(self, state, action, reward, next_state, done):
        """Сохраняет опыт в памяти"""
        self.memory.append((state, action, reward, next_state, done))
    
    def replay(self):
        """Обучается на batch из памяти"""
        if len(self.memory) < self.batch_size:
            return
        
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        
        states = torch.FloatTensor(states)
        actions = torch.LongTensor(actions)
        rewards = torch.FloatTensor(rewards)
        next_states = torch.FloatTensor(next_states)
        dones = torch.FloatTensor(dones)
        
        # Current Q values
        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1))
        
        # Target Q values (Double DQN)
        with torch.no_grad():
            next_actions = self.policy_net(next_states).argmax(1)
            next_q = self.target_net(next_states).gather(1, next_actions.unsqueeze(1))
            target_q = rewards.unsqueeze(1) + self.gamma * next_q * (1 - dones.unsqueeze(1))
        
        # Loss
        loss = nn.MSELoss()(current_q, target_q)
        
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        self.optimizer.step()
        
        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
    
    def update_target(self):
        """Обновляет target network"""
        self.target_net.load_state_dict(self.policy_net.state_dict())
    
    def train(self, env: TradingEnvironment, episodes: int = 1000):
        """Обучение агента"""
        scores = []
        
        for episode in range(episodes):
            state = env.reset()
            total_reward = 0
            
            while not env.done:
                action = self.act(state)
                next_state, reward, done, info = env.step(action)
                
                self.remember(state, action, reward, next_state, done)
                self.replay()
                
                state = next_state
                total_reward += reward
            
            scores.append(total_reward)
            
            # Update target network
            if (episode + 1) % 10 == 0:
                self.update_target()
            
            if (episode + 1) % 100 == 0:
                avg_score = np.mean(scores[-100:])
                logger.info(f"Episode {episode+1}, Avg Score: {avg_score:.2f}, Epsilon: {self.epsilon:.3f}")
        
        return scores
```

---

## 8. Улучшение Pattern Detector

### 8.1 Текущее состояние

Pattern Detector (`pattern_detector.py`) находится в разработке (0/7 задач).

### 8.2 Добавление CNN для распознавания паттернов

```python
class CNNPatternDetector(nn.Module):
    """
    CNN для распознавания паттернов на графиках
    
    Преобразует ценовые данные в "изображение" и использует свертки
    для обнаружения паттернов
    """
    
    def __init__(
        self,
        sequence_length: int = 100,
        num_features: int = 5,  # OHLCV
        num_patterns: int = 10  # Количество паттернов для классификации
    ):
        super().__init__()
        
        # Входные данные: (batch, channels=features, height=1, width=seq_len)
        
        # 1D convolutions для временных паттернов
        self.conv1 = nn.Conv1d(num_features, 32, kernel_size=5, padding=2)
        self.bn1 = nn.BatchNorm1d(32)
        
        self.conv2 = nn.Conv1d(32, 64, kernel_size=5, padding=2)
        self.bn2 = nn.BatchNorm1d(64)
        
        self.conv3 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm1d(128)
        
        # Multi-scale features с разными размерами ядер
        self.conv_3 = nn.Conv1d(128, 64, kernel_size=3, padding=1)
        self.conv_5 = nn.Conv1d(128, 64, kernel_size=5, padding=2)
        self.conv_7 = nn.Conv1d(128, 64, kernel_size=7, padding=3)
        
        # Global pooling
        self.global_avg_pool = nn.AdaptiveAvgPool1d(1)
        self.global_max_pool = nn.AdaptiveMaxPool1d(1)
        
        # Classifier
        self.fc1 = nn.Linear(64 * 3 * 2, 256)  # 3 multi-scale * 2 pooling
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, num_patterns)
        
        self.dropout = nn.Dropout(0.3)
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, seq_len, features)
        
        Returns:
            pattern_logits: (batch, num_patterns)
            signal: (batch, 3) - [bullish_prob, bearish_prob, neutral_prob]
        """
        # Transpose для Conv1d: (batch, features, seq_len)
        x = x.transpose(1, 2)
        
        # Convolutional layers
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.max_pool1d(x, 2)
        
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.max_pool1d(x, 2)
        
        x = F.relu(self.bn3(self.conv3(x)))
        
        # Multi-scale features
        x_3 = F.relu(self.conv_3(x))
        x_5 = F.relu(self.conv_5(x))
        x_7 = F.relu(self.conv_7(x))
        
        # Global pooling для каждого масштаба
        features = []
        for x_scale in [x_3, x_5, x_7]:
            features.append(self.global_avg_pool(x_scale).squeeze(-1))
            features.append(self.global_max_pool(x_scale).squeeze(-1))
        
        x = torch.cat(features, dim=-1)
        
        # Classifier
        x = self.dropout(F.relu(self.fc1(x)))
        x = self.dropout(F.relu(self.fc2(x)))
        pattern_logits = self.fc3(x)
        
        # Signal prediction (из паттернов)
        # Паттерны 0-3: bullish, 4-6: bearish, 7-9: neutral
        bullish = F.softmax(pattern_logits[:, :4], dim=-1).sum(dim=-1, keepdim=True)
        bearish = F.softmax(pattern_logits[:, 4:7], dim=-1).sum(dim=-1, keepdim=True)
        neutral = F.softmax(pattern_logits[:, 7:], dim=-1).sum(dim=-1, keepdim=True)
        
        signal = torch.cat([bullish, bearish, neutral], dim=-1)
        signal = signal / signal.sum(dim=-1, keepdim=True)  # Normalize
        
        return pattern_logits, signal


# Список паттернов для классификации
PATTERN_LABELS = [
    'bullish_engulfing',      # 0 - bullish
    'hammer',                  # 1 - bullish
    'double_bottom',           # 2 - bullish
    'ascending_triangle',      # 3 - bullish
    'bearish_engulfing',       # 4 - bearish
    'shooting_star',           # 5 - bearish
    'double_top',              # 6 - bearish
    'descending_triangle',     # 7 - neutral (wait for breakout)
    'doji',                    # 8 - neutral
    'no_pattern',              # 9 - neutral
]
```

---

## 9. Мониторинг и MLOps

### 9.1 Data Drift Detection

```python
from scipy import stats

class DataDriftDetector:
    """
    Детектор дрифта данных
    
    Отслеживает изменения в распределении входных данных,
    которые могут указывать на необходимость переобучения
    """
    
    def __init__(self, reference_data: np.ndarray, threshold: float = 0.05):
        """
        Args:
            reference_data: Данные, на которых обучалась модель
            threshold: P-value threshold для KS-test
        """
        self.reference_data = reference_data
        self.threshold = threshold
        
        # Вычисляем статистики reference data
        self.ref_mean = np.mean(reference_data, axis=0)
        self.ref_std = np.std(reference_data, axis=0)
        self.ref_min = np.min(reference_data, axis=0)
        self.ref_max = np.max(reference_data, axis=0)
    
    def detect_drift(self, new_data: np.ndarray) -> Dict[str, Any]:
        """
        Проверяет наличие дрифта в новых данных
        
        Returns:
            {
                'drift_detected': bool,
                'drifted_features': list,
                'ks_statistics': dict,
                'recommendation': str
            }
        """
        drifted_features = []
        ks_stats = {}
        
        for i in range(new_data.shape[1]):
            # Kolmogorov-Smirnov test
            statistic, p_value = stats.ks_2samp(
                self.reference_data[:, i],
                new_data[:, i]
            )
            
            ks_stats[f'feature_{i}'] = {
                'statistic': statistic,
                'p_value': p_value
            }
            
            if p_value < self.threshold:
                drifted_features.append(i)
        
        drift_detected = len(drifted_features) > 0
        drift_severity = len(drifted_features) / new_data.shape[1]
        
        if drift_severity > 0.5:
            recommendation = 'URGENT: Переобучение модели рекомендуется'
        elif drift_severity > 0.2:
            recommendation = 'WARNING: Рассмотрите переобучение'
        else:
            recommendation = 'OK: Дрифт минимален'
        
        return {
            'drift_detected': drift_detected,
            'drift_severity': drift_severity,
            'drifted_features': drifted_features,
            'ks_statistics': ks_stats,
            'recommendation': recommendation
        }


class ModelPerformanceMonitor:
    """
    Мониторинг производительности модели в production
    """
    
    def __init__(self, window_size: int = 100):
        self.predictions = deque(maxlen=window_size)
        self.actuals = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)
        
    def log_prediction(self, prediction: Dict, actual: Optional[Dict] = None):
        """Логирует предсказание и (опционально) фактический результат"""
        self.predictions.append(prediction)
        self.actuals.append(actual)
        self.timestamps.append(datetime.now())
    
    def update_actual(self, index: int, actual: Dict):
        """Обновляет фактический результат для предыдущего предсказания"""
        if index < len(self.actuals):
            self.actuals[index] = actual
    
    def get_metrics(self) -> Dict[str, Any]:
        """Вычисляет метрики производительности"""
        # Фильтруем только те, где есть фактические результаты
        valid_pairs = [
            (p, a) for p, a in zip(self.predictions, self.actuals)
            if a is not None
        ]
        
        if not valid_pairs:
            return {'error': 'No validated predictions'}
        
        predictions, actuals = zip(*valid_pairs)
        
        # Direction accuracy
        pred_directions = [1 if p['direction'] > 0 else -1 for p in predictions]
        actual_directions = [1 if a['actual_change'] > 0 else -1 for a in actuals]
        direction_accuracy = sum(
            p == a for p, a in zip(pred_directions, actual_directions)
        ) / len(predictions)
        
        # MAE для change_percent
        pred_changes = [p['change_percent'] for p in predictions]
        actual_changes = [a['actual_change'] for a in actuals]
        mae = np.mean(np.abs(np.array(pred_changes) - np.array(actual_changes)))
        
        # Confidence calibration
        confidences = [p['confidence'] for p in predictions]
        correct = [
            1 if p == a else 0
            for p, a in zip(pred_directions, actual_directions)
        ]
        
        # Группируем по уровням уверенности
        calibration = {}
        for conf_level in [0.5, 0.6, 0.7, 0.8, 0.9]:
            subset = [
                (c, corr) for c, conf, corr in zip(confidences, confidences, correct)
                if conf >= conf_level and conf < conf_level + 0.1
            ]
            if subset:
                calibration[f'{conf_level:.1f}-{conf_level+0.1:.1f}'] = {
                    'count': len(subset),
                    'accuracy': sum(s[1] for s in subset) / len(subset)
                }
        
        return {
            'direction_accuracy': direction_accuracy,
            'mae_change_percent': mae,
            'total_predictions': len(predictions),
            'confidence_calibration': calibration,
            'last_update': datetime.now().isoformat()
        }
```

### 9.2 Logging и Experiment Tracking

```python
# Интеграция с MLflow или W&B
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

class ExperimentTracker:
    """Трекер экспериментов для AI моделей"""
    
    def __init__(self, experiment_name: str = 'infobot_ai'):
        self.experiment_name = experiment_name
        
        if MLFLOW_AVAILABLE:
            mlflow.set_experiment(experiment_name)
    
    def start_run(self, run_name: str):
        """Начинает новый run"""
        if MLFLOW_AVAILABLE:
            mlflow.start_run(run_name=run_name)
    
    def log_params(self, params: Dict[str, Any]):
        """Логирует гиперпараметры"""
        if MLFLOW_AVAILABLE:
            mlflow.log_params(params)
    
    def log_metrics(self, metrics: Dict[str, float], step: int = None):
        """Логирует метрики"""
        if MLFLOW_AVAILABLE:
            mlflow.log_metrics(metrics, step=step)
    
    def log_model(self, model: nn.Module, model_name: str):
        """Сохраняет модель"""
        if MLFLOW_AVAILABLE:
            mlflow.pytorch.log_model(model, model_name)
    
    def end_run(self):
        """Завершает run"""
        if MLFLOW_AVAILABLE:
            mlflow.end_run()
```

---

## 10. Дополнительные источники данных

### 10.1 Sentiment Analysis

```python
class SentimentAnalyzer:
    """
    Анализ настроений из социальных сетей и новостей
    """
    
    def __init__(self):
        # Можно использовать предобученную модель
        try:
            from transformers import pipeline
            self.sentiment_model = pipeline(
                'sentiment-analysis',
                model='nlptown/bert-base-multilingual-uncased-sentiment'
            )
            self.available = True
        except:
            self.available = False
            logger.warning("Sentiment analysis недоступен (установите transformers)")
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Анализирует текст на sentiment"""
        if not self.available:
            return {'sentiment': 0, 'confidence': 0}
        
        result = self.sentiment_model(text[:512])[0]  # Ограничиваем длину
        
        # Конвертируем в числовое значение
        label = result['label']
        score = result['score']
        
        # '1 star' -> -1, '5 stars' -> 1
        if '1' in label or '2' in label:
            sentiment = -1
        elif '4' in label or '5' in label:
            sentiment = 1
        else:
            sentiment = 0
        
        return {
            'sentiment': sentiment * score,
            'confidence': score,
            'label': label
        }
    
    def get_crypto_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Получает sentiment для криптовалюты
        
        TODO: Интеграция с Twitter API, Reddit API, CryptoCompare, etc.
        """
        # Placeholder для будущей интеграции
        return {
            'symbol': symbol,
            'twitter_sentiment': 0,
            'reddit_sentiment': 0,
            'news_sentiment': 0,
            'overall_sentiment': 0,
            'data_source': 'placeholder'
        }


class OnChainAnalyzer:
    """
    Анализ on-chain метрик
    """
    
    def get_whale_activity(self, symbol: str) -> Dict[str, Any]:
        """
        Отслеживает активность крупных кошельков
        
        TODO: Интеграция с Glassnode, Whale Alert, etc.
        """
        return {
            'large_transactions_24h': 0,
            'exchange_inflow': 0,
            'exchange_outflow': 0,
            'net_flow': 0,
            'whale_accumulation': False
        }
    
    def get_network_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        Получает сетевые метрики
        """
        return {
            'active_addresses_24h': 0,
            'transaction_count_24h': 0,
            'avg_transaction_value': 0,
            'hash_rate': 0,  # Для PoW монет
            'staking_ratio': 0  # Для PoS монет
        }
```

---

## 11. Приоритеты реализации

### Фаза 1: Критические улучшения (Высокий приоритет)

| # | Задача | Сложность | Влияние | Файлы |
|---|--------|-----------|---------|-------|
| 1 | Улучшение Feature Engineering | Средняя | Высокое | `lstm_predictor.py`, новый `feature_engineering.py` |
| 2 | Добавление Attention к LSTM | Средняя | Высокое | `lstm_predictor.py` |
| 3 | Замена Grid Search на Bayesian Opt | Средняя | Высокое | `ai_strategy_optimizer.py` |
| 4 | Data Drift Detection | Низкая | Среднее | новый `drift_detector.py` |

### Фаза 2: Важные улучшения (Средний приоритет)

| # | Задача | Сложность | Влияние | Файлы |
|---|--------|-----------|---------|-------|
| 5 | Transformer архитектура | Высокая | Высокое | новый `transformer_predictor.py` |
| 6 | Ensemble методы | Средняя | Среднее | новый `ensemble.py` |
| 7 | CNN Pattern Detector | Средняя | Среднее | `pattern_detector.py` |
| 8 | Performance Monitoring | Низкая | Среднее | новый `monitoring.py` |

### Фаза 3: Продвинутые функции (Низкий приоритет)

| # | Задача | Сложность | Влияние | Файлы |
|---|--------|-----------|---------|-------|
| 9 | Reinforcement Learning | Высокая | Высокое | новый `rl_agent.py` |
| 10 | Sentiment Analysis | Средняя | Среднее | новый `sentiment.py` |
| 11 | On-Chain Analysis | Средняя | Среднее | новый `onchain.py` |
| 12 | Experiment Tracking (MLflow) | Низкая | Низкое | `auto_trainer.py` |

---

## Заключение

Проект InfoBot имеет солидную архитектуру, но есть значительный потенциал для улучшения AI компонентов. Наиболее критичные улучшения:

1. **Feature Engineering** - текущих 7 признаков недостаточно для сложных рыночных паттернов
2. **Архитектура LSTM** - добавление Attention и улучшение сетевой структуры
3. **Оптимизация гиперпараметров** - переход от Grid Search к Bayesian Optimization
4. **Мониторинг** - отслеживание дрифта данных и производительности модели

Рекомендую начать с Фазы 1, которая даст наибольший эффект при умеренных усилиях.

---

**Автор:** AI Assistant  
**Версия документа:** 1.0  
**Дата:** 26 января 2026
