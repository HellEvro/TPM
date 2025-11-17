from .keys import EXCHANGES, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Настройки приложения
# ВНИМАНИЕ: Изменение APP_HOST на '0.0.0.0' открывает доступ из интернета!
# Это может быть небезопасно для торгового бота с API ключами
# Рекомендуется использовать только в доверенной локальной сети
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

# Настройки графиков
CHART_MAX_POINTS = 30  # Максимальное количество точек на графике
CHART_COLORS = {
    'POSITIVE': {
        'BORDER': '#4CAF50',
        'BACKGROUND': 'rgba(74, 175, 80, 0.2)'
    },
    'NEGATIVE': {
        'BORDER': '#f44336',
        'BACKGROUND': 'rgba(244, 67, 54, 0.2)'
    }
}

# Настройки графика статистики
STATISTICS_CHART = {
    'type': 'line',
    'tension': 0.4,
    'fill': True,
    'responsive': True,
    'maintain_aspect_ratio': False,
    'animation': False,
    'max_points': CHART_MAX_POINTS,
    'height': 600,  # Высота графика в пикселях
    'scales': {
        'y': {
            'begin_at_zero': False,
            'grid': {
                'color': 'rgba(255, 255, 255, 0.1)'
            }
        },
        'x': {
            'grid': {
                'display': False
            }
        }
    },
    'legend': {
        'display': False
    },
    'colors': CHART_COLORS  # Используем существующие цвета
}

# Настройки пагинации
DEFAULT_PAGE_SIZE = 10
AVAILABLE_PAGE_SIZES = [10, 50, 100]

# Настройки кэширования
CHART_CACHE_TIME = 5 * 60 * 1000  # Время жизни кэша графиков (5 минут)
SMA200_CACHE_TIME = 7 * 60 * 1000  # Время жизни кэша SMA200 (7 минут)

# Настройки сортировки
DEFAULT_SORT_ORDER = 'pnl_desc'
SORT_OPTIONS = {
    'pnl_desc': 'PNL (макс-мин)',
    'pnl_asc': 'PNL (мин-макс)',
    'alphabet_asc': 'A-Z',
    'alphabet_desc': 'Z-A'
}

# Настройки темы
DEFAULT_THEME = 'dark'
THEME_COLORS = {
    'dark': {
        'bg_color': '#1a1a1a',
        'text_color': '#fff',
        'section_bg': '#2d2d2d',
        'border_color': '#404040'
    },
    'light': {
        'bg_color': '#f0f0f0',
        'text_color': '#000',
        'section_bg': '#fff',
        'border_color': '#ddd'
    }
}

# Настройки логирования
LOG_DIR = 'logs'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'

# ============================================================================
# НАСТРОЙКИ УРОВНЕЙ ЛОГИРОВАНИЯ В КОНСОЛИ
# ============================================================================
# Позволяет фильтровать логи, выводимые в консоль (stdout).
# Файловые логи (logs/*.log) НЕ затрагиваются - туда пишется всё.
#
# ДОСТУПНЫЕ УРОВНИ:
#   DEBUG    - отладочная информация (самый подробный)
#   INFO     - информационные сообщения
#   WARNING  - предупреждения
#   ERROR    - ошибки
#   CRITICAL - критические ошибки (самый важный)
#
# ФОРМАТ НАСТРОЙКИ:
#   Можно использовать два варианта:
#   1. Список строк: ['+INFO', '-WARNING', '+ERROR']
#   2. Одна строка с запятыми: "+INFO, -WARNING, +ERROR"
#
# СИНТАКСИС:
#   +LEVEL  - включить уровень (показывать в консоли)
#   -LEVEL  - выключить уровень (скрыть из консоли)
#
# ЛОГИКА РАБОТЫ:
#   1. Если указаны уровни с префиксом + (включить):
#      - Показываются ТОЛЬКО указанные уровни
#      - Все остальные автоматически скрываются
#      Пример: ['+ERROR'] → показывается только ERROR
#
#   2. Если указаны ТОЛЬКО уровни с префиксом - (выключить):
#      - Показываются ВСЕ уровни КРОМЕ указанных
#      Пример: ['-DEBUG', '-INFO'] → показываются WARNING, ERROR, CRITICAL
#
#   3. Если список пустой, строка пустая или None:
#      - Показываются ВСЕ уровни (фильтрация отключена)
#
# ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
#
#   # Пример 1: Показывать только ошибки
#   CONSOLE_LOG_LEVELS = ['+ERROR']
#   # или
#   CONSOLE_LOG_LEVELS = "+ERROR"
#
#   # Пример 2: Показывать только ERROR и WARNING
#   CONSOLE_LOG_LEVELS = ['+ERROR', '+WARNING']
#   # или
#   CONSOLE_LOG_LEVELS = "+ERROR, +WARNING"
#
#   # Пример 3: Показывать всё кроме DEBUG
#   CONSOLE_LOG_LEVELS = ['-DEBUG']
#   # или
#   CONSOLE_LOG_LEVELS = "-DEBUG"
#
#   # Пример 4: Показывать всё кроме DEBUG и INFO
#   CONSOLE_LOG_LEVELS = ['-DEBUG', '-INFO']
#   # или
#   CONSOLE_LOG_LEVELS = "-DEBUG, -INFO"
#
#   # Пример 5: Явно указать все нужные уровни
#   CONSOLE_LOG_LEVELS = ['+INFO', '+WARNING', '+ERROR', '+CRITICAL']
#   # или
#   CONSOLE_LOG_LEVELS = "+INFO, +WARNING, +ERROR, +CRITICAL"
#
#   # Пример 6: Смешанный синтаксис (если есть +, то - игнорируются)
#   CONSOLE_LOG_LEVELS = ['+ERROR', '-DEBUG', '-INFO']
#   # Результат: показывается только ERROR (т.к. есть +ERROR)
#
#   # Пример 7: Отключить фильтрацию (показывать всё)
#   CONSOLE_LOG_LEVELS = []
#   # или
#   CONSOLE_LOG_LEVELS = ""
#
# ВАЖНО:
#   - Настройка применяется ТОЛЬКО к консольному выводу
#   - В файлы logs/*.log пишется всё независимо от этой настройки
#   - Регистр не важен: '+error' = '+ERROR' = '+Error'
#   - Пробелы вокруг запятых игнорируются
# ============================================================================
CONSOLE_LOG_LEVELS = []  # По умолчанию все уровни разрешены

# Telegram settings
TELEGRAM_NOTIFICATIONS_ENABLED = True

# Notification settings
TELEGRAM_NOTIFY = {
    'ERRORS': True,              # Уведомления об ошибках
    'RAPID_GROWTH': True,        # Быстрый рост позиций
    'HIGH_ROI': True,            # Высокий ROI (>100%)
    'HIGH_LOSS': True,           # Большие убытки (<-40 USDT)
    'HIGH_PNL': True,            # Высокий PnL (>1000 USDT)
    'DAILY_REPORT': True,        # Ежедневный отчет
    'DAILY_REPORT_TIME': '00:00', # Время отправки дневного отчета
    'STATISTICS': True,          # Отправка статистики
    'STATISTICS_INTERVAL': 300,    # Интервал отправки в секундах (если включено)
    'STATISTICS_INTERVAL_ENABLED': True,  # Включить/выключить отправку по интервалу
    'STATISTICS_TIME_ENABLED': False,     # Включить/выключить отправку в определенное время
    'STATISTICS_TIME': ['09:00', '21:00']  # Время отправки (если включено)
}