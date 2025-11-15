"""
Настройки для standalone AI лаунчера (ai.py).

По аналогии с SystemConfig из bot_config.py, но с фокусом на режимы
обучения/оркестрации и отладочные флаги, которые не нужны основному bots.py.
"""


class AILauncherConfig:
    """Базовые параметры поведения ai.py."""

    # Общие флаги
    DEBUG_MODE = False  # Переводит логгеры в DEBUG и включает дополнительные сообщения
    VERBOSE_PROCESS_LIFECYCLE = True  # Логировать запуск/остановку дочерних процессов подробнее
    LOG_SIGNAL_EVENTS = True  # Печатать стек/детали при получении сигналов остановки

    # Управление трейсингом кода (каждая строка)
    ENABLE_CODE_TRACING = False  # ⚠️ Будет сильно замедлять работу, как и в bots.py
    TRACE_INCLUDE_KEYWORDS = [
        'ai_launcher_source',
        'bot_engine/ai',
        'bot_engine\\ai',
        'bot_engine/ai_backtester_new',
        'bot_engine\\ai_backtester_new',
        'bot_engine/ai_strategy_optimizer',
        'bot_engine\\ai_strategy_optimizer',
        'bot_engine/ai_backtester',
        'bot_engine\\ai_backtester',
        'bots_modules',
        'license_generator',
        'trace_debug',
    ]
    TRACE_SKIP_KEYWORDS = [
        'logging',
        'threading',
        'concurrent',
        'asyncio',
        'json',
        'http',
        'requests',
        'site-packages',
    ]
    TRACE_WRITE_TO_FILE = True
    TRACE_LOG_FILE = 'logs/ai_trace.log'
    TRACE_MAX_LINE_LENGTH = 200

    # Доп. опции можно расширять позднее (например, управление интервалами, автотренером и т.д.)

    # Интервалы циклов (по умолчанию делаем минимальные, чтобы не «засыпать»)
    BACKTEST_LOOP_DELAY_SECONDS = 1      # Пауза между бэктестами (0 = сразу следующий цикл)
    OPTIMIZER_LOOP_DELAY_SECONDS = 1     # Пауза между оптимизациями
    TRAINING_LOOP_DELAY_SECONDS = 1      # Доп. пауза в training worker (если нужно)
    DATA_COLLECTION_INTERVAL_SECONDS = 60  # Уже используется, но можно перенастроить здесь

