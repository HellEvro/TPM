"""
Пример конфигурации InfoBot
Скопируйте этот файл в config.py

⚠️  API КЛЮЧИ ХРАНЯТСЯ В ОТДЕЛЬНОМ ФАЙЛЕ!
   1. Скопируйте app/keys.example.py -> app/keys.py
   2. Добавьте реальные API ключи в app/keys.py
   3. Скопируйте этот файл -> app/config.py
   
   config.py импортирует ключи из keys.py автоматически
"""

# ========== ИМПОРТ API КЛЮЧЕЙ ==========
from .keys import EXCHANGES, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

APP_HOST = '0.0.0.0'  # 'localhost' для только локального доступа, '0.0.0.0' для доступа из сети
APP_PORT = 5000
APP_DEBUG = True

# Активная биржа
ACTIVE_EXCHANGE = 'BYBIT'

# Настройки позиций
GROWTH_MULTIPLIER = 3.0
DEFAULT_PNL_THRESHOLD = 1000
MIN_PNL_THRESHOLD = 5
HIGH_ROI_THRESHOLD = 100
HIGH_LOSS_THRESHOLD = -40

# Настройки обновления данных
UPDATE_INTERVAL = 2000  # Интервал обновления основных данных (мс)
CHART_UPDATE_INTERVAL = 60000  # Интервал обновления графика (мс)
CLOSED_PNL_UPDATE_INTERVAL = 10000  # Интервал обновления закрытых позиций (мс)

# ========== TELEGRAM УВЕДОМЛЕНИЯ ==========
# Токены настраиваются в keys.py
TELEGRAM_NOTIFY = {
    'ENABLED': True,
    'HIGH_PNL_THRESHOLD': 100,        # Уведомление при PnL > 100 USDT
    'LOSING_THRESHOLD': -50,          # Уведомление при убытке > 50 USDT
    'DAILY_REPORT': True,
    'REPORT_TIME': '21:00'            # Время ежедневного отчета
}
TELEGRAM_NOTIFICATIONS_ENABLED = True

# ========== ЗАЩИТНЫЕ МЕХАНИЗМЫ ==========
MAX_LOSS_PERCENT = 15.0               # Максимальные потери (%)
TRAILING_STOP_ACTIVATION = 300.0      # Активация трейлинг стопа (%)
TRAILING_STOP_DISTANCE = 150.0        # Расстояние трейлинг стопа (%)

# ========== РИСК-МЕНЕДЖМЕНТ ==========
MAX_CONCURRENT_BOTS = 5               # Максимум одновременных ботов
RISK_CAP_PERCENT = 10.0               # Лимит риска (% от депозита)
MIN_BALANCE_USDT = 10.0
MAX_ACTIVE_BOTS = 10
MIN_RISK_PROFILE = 0.5
MAX_RISK_PROFILE = 2.0

# ========== RSI ПАРАМЕТРЫ ==========
RSI_PERIOD = 14
RSI_OVERSOLD = 29                     # Порог для LONG
RSI_OVERBOUGHT = 71                   # Порог для SHORT
RSI_EXIT_LONG = 65                    # Выход из LONG
RSI_EXIT_SHORT = 35                   # Выход из SHORT

# ========== СИСТЕМНЫЕ НАСТРОЙКИ ==========
RSI_UPDATE_INTERVAL = 300             # 5 минут
AUTO_SAVE_INTERVAL = 30               # 30 секунд
DEBUG_MODE = False
AUTO_REFRESH_UI = True
UI_REFRESH_INTERVAL = 10              # секунд

