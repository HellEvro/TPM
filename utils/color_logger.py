#!/usr/bin/env python3
"""
Цветная система логирования для InfoBot
"""
import logging
import sys
from datetime import datetime

class LogLevelFilter(logging.Filter):
    """
    Фильтр для управления уровнями логирования в консоли.
    Поддерживает синтаксис: +INFO, -WARNING, +ERROR, -DEBUG и т.д.
    Также поддерживает строку с запятыми: "+INFO, -WARNING, +ERROR, -DEBUG"
    
    Автоматически скрывает DEBUG логи от внешних библиотек (urllib3, pybit и т.д.)
    если DEBUG уровень не включен явно.
    """
    
    # Маппинг строковых уровней на числовые
    LEVEL_MAP = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }
    
    # Логгеры внешних библиотек, которые обычно шумят в DEBUG
    EXTERNAL_LOGGERS = {
        'urllib3',
        'urllib3.connectionpool',
        'pybit',
        'pybit._http_manager',
        'requests',
        'requests.packages.urllib3',
        'httpcore',
        'httpx',
        'tensorflow',
        'tensorflow.python',
        'tensorflow.core',
        'matplotlib',
        'matplotlib.font_manager',
        'matplotlib.backends',
        'PIL',
        'PIL.PngImagePlugin',
        'pandas',
        'pandas.io',
        'pandas.core',
    }
    
    def __init__(self, level_settings=None):
        """
        Инициализация фильтра
        
        Args:
            level_settings: Может быть:
                - Список строк: ['+INFO', '-WARNING', '+ERROR', '-DEBUG']
                - Одна строка с запятыми: "+INFO, -WARNING, +ERROR, -DEBUG"
                - None или пустой список [] - все уровни разрешены
        """
        super().__init__()
        self.enabled_levels = set()
        # По умолчанию DEBUG не включен (скрываем шумные логи от библиотек)
        self.debug_enabled = False
        
        # Проверяем, что настройки не None и не пустые
        if level_settings is not None and level_settings != []:
            # Если это пустая строка после обработки, тоже считаем как "все разрешено"
            if isinstance(level_settings, str) and not level_settings.strip():
                # Пустая строка - разрешаем все
                all_levels = set(self.LEVEL_MAP.keys())
                self.enabled_levels = all_levels
                self.debug_enabled = True
            else:
                self._parse_settings(level_settings)
                # Если после парсинга enabled_levels пустой, значит нужно разрешить все
                if not self.enabled_levels:
                    all_levels = set(self.LEVEL_MAP.keys())
                    self.enabled_levels = all_levels
                    self.debug_enabled = True
        else:
            # Если настройки не указаны (None) или пустой список [], включаем все уровни
            all_levels = set(self.LEVEL_MAP.keys())
            self.enabled_levels = all_levels
            # Когда все уровни разрешены, включаем DEBUG для всех (включая внешние библиотеки)
            self.debug_enabled = True
    
    def _parse_settings(self, settings):
        """Парсит настройки уровней логирования"""
        # Если список пустой, разрешаем все уровни
        if not settings:
            return
        
        # Если переданная строка (не список), разбиваем по запятым
        if isinstance(settings, str):
            settings = [s.strip() for s in settings.split(',') if s.strip()]
        
        # Сначала собираем все включенные и выключенные уровни
        enabled = set()
        disabled = set()
        
        for setting in settings:
            # Если это уже строка, используем как есть, иначе преобразуем
            if not isinstance(setting, str):
                setting = str(setting)
            setting = setting.strip().upper()
            if not setting:
                continue
            
            # Парсим формат: +LEVEL или -LEVEL
            if setting.startswith('+'):
                level_name = setting[1:]
                if level_name in self.LEVEL_MAP:
                    enabled.add(level_name)
                    if level_name == 'DEBUG':
                        # Если явно включен DEBUG, разрешаем его для всех (включая внешние библиотеки)
                        self.debug_enabled = True
            elif setting.startswith('-'):
                level_name = setting[1:]
                if level_name in self.LEVEL_MAP:
                    disabled.add(level_name)
                    if level_name == 'DEBUG':
                        self.debug_enabled = False
        
        # Если есть явно включенные уровни, используем только их
        # Иначе используем все уровни кроме явно выключенных
        if enabled:
            self.enabled_levels = enabled
        else:
            # Разрешаем все уровни кроме выключенных
            all_levels = set(self.LEVEL_MAP.keys())
            self.enabled_levels = all_levels - disabled
        
        # КРИТИЧНО: Если enabled_levels пустой после парсинга, значит все уровни выключены
        # В этом случае включаем все уровни (это не должно происходить, но на всякий случай)
        if not self.enabled_levels:
            all_levels = set(self.LEVEL_MAP.keys())
            self.enabled_levels = all_levels
            self.debug_enabled = True
    
    def filter(self, record):
        """
        Фильтрует записи логов на основе настроек уровней
        
        Returns:
            True если запись должна быть показана, False если нужно скрыть
        """
        level_name = record.levelname
        logger_name = record.name if hasattr(record, 'name') else ''
        
        # Скрываем сообщения с неформатированными плейсхолдерами %s (обычно это ошибки форматирования)
        try:
            message = record.getMessage() if hasattr(record, 'getMessage') else str(record.msg)
            # Скрываем сообщения с неформатированными плейсхолдерами %s (обычно это ошибки форматирования)
            if isinstance(message, str) and '%s' in message:
                # Скрываем типичные сообщения библиотек с неформатированными %s
                # (например, "Creating converter from %s to %s" без подстановки значений)
                if 'Creating converter from %s to %s' in message:
                    return False
                # Проверяем наличие неформатированных %s плейсхолдеров
                import re
                # Проверяем, есть ли неформатированные %s (не в конце строки и не как часть нормального сообщения)
                if re.search(r'%s(?!\s*$)', message) and not re.search(r'%[0-9]*[diouxXeEfFgGcrs]', message):
                    # Это неформатированное сообщение - скрываем его
                    return False
        except:
            pass  # Если не удалось проверить, пропускаем
        
        # Скрываем несущественные SSL ошибки при получении сетевого времени (DEBUG уровень)
        # Это не критичные ошибки, которые не должны засорять логи
        try:
            message = record.getMessage() if hasattr(record, 'getMessage') else str(record.msg)
            if isinstance(message, str) and level_name == 'DEBUG':
                message_lower = message.lower()
                # Проверяем, является ли это SSL ошибкой при получении сетевого времени
                if ('worldtimeapi' in message_lower or 'сетевое время' in message_lower or 'network time' in message_lower) and \
                   ('ssl' in message_lower or 'sslerror' in message_lower or 'unexpected_eof' in message_lower or 'ssl: unexpected_eof' in message_lower):
                    # Это несущественная SSL ошибка - скрываем её
                    return False
        except:
            pass  # Если не удалось проверить, пропускаем
        
        # Всегда скрываем DEBUG от внешних библиотек, если DEBUG не включен явно
        if level_name == 'DEBUG' and not self.debug_enabled:
            for external_logger in self.EXTERNAL_LOGGERS:
                if logger_name.startswith(external_logger):
                    return False
        
        # Если уровни не настроены, разрешаем все (кроме уже отфильтрованных выше)
        if not self.enabled_levels:
            return True
        
        # КРИТИЧНО: Проверяем уровень записи
        # Если уровень не включен, скрываем
        if level_name not in self.enabled_levels:
            return False
        
        return True

class Colors:
    """ANSI цветовые коды"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Основные цвета
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Яркие цвета
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Фоновые цвета
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'

class ColorFormatter(logging.Formatter):
    """Форматтер с цветами для разных уровней логирования"""
    
    # Цвета для разных уровней
    COLORS = {
        'DEBUG': Colors.DIM + Colors.WHITE,
        'INFO': Colors.BRIGHT_CYAN,
        'WARNING': Colors.BRIGHT_YELLOW,
        'ERROR': Colors.BRIGHT_RED,
        'CRITICAL': Colors.BG_RED + Colors.BRIGHT_WHITE,
    }
    
    # Эмодзи для разных категорий
    EMOJIS = {
        'INIT': '🚀',
        'CONFIG': '⚙️',
        'AUTO': '🤖',
        'SYNC': '🔄',
        'CLEANUP': '🧹',
        'STOP': '🛑',
        'ERROR': '❌',
        'SUCCESS': '✅',
        'WARNING': '⚠️',
        'INFO': 'ℹ️',
        'DEBUG': '🔍',
        'RSI': '📈',
        'BOT': '🤖',
        'EXCHANGE': '🏦',
        'API': '🌐',
        'CACHE': '💾',
        'POSITION': '📊',
        'SIGNAL': '🎯',
        'FILTER': '🔍',
        'SAVE': '💾',
        'LOAD': '📂',
        'BATCH': '📦',
        'STOP_LOSS': '🛡️',
        'INACTIVE': '🗑️',
        'STARTUP': '🎬',
        'MATURITY': '🌱',
        'OPTIMAL': '⚡',
        'PROCESS': '⚙️',
        'DEFAULT': '📋',
        'SYSTEM': '🔧',
        'SMART_RSI': '🧠',
        'AUTO_BOT': '🤖',
        'AUTO_SAVE': '💾',
        'EXCHANGE_POSITIONS': '📊',
        'BOTS_CACHE': '💾',
        'POSITION_UPDATE': '🔄',
        'POSITION_SYNC': '🔄',
        'INACTIVE_CLEANUP': '🧹',
        'STOP_LOSS_SETUP': '🛡️',
        'AUTO_BOT_FILTER': '🔍',
        'BOT_INIT': '🤖',
        'BOT_ACTIVE': '✅',
        'BOT_BCH': '🤖',
        'BOT_ES': '🤖',
        'BOT_GPS': '🤖',
        'BOT_HFT': '🤖',
        'BOT_M': '🤖',
        'BOT_RHEA': '🤖',
        'BOT_SLF': '🤖',
        'BOT_TUT': '🤖',
        'LOAD_STATE': '📂',
        'SAVE_STATE': '💾',
        'SIGNAL': '🎯',
        'FILTER_PROCESSING': '🔍',
        'NEW_AUTO_FILTER': '🔍',
        'NEW_BOT_SIGNALS': '🎯',
        'AUTOBOT_FILTER': '🔍',
    }
    
    def format(self, record):
        # Получаем цвет для уровня логирования
        level_color = self.COLORS.get(record.levelname, Colors.WHITE)
        
        # Получаем исходное сообщение (до форматирования)
        # Важно: работаем с record.msg напрямую, чтобы удалить префикс ДО форматирования
        if hasattr(record, 'msg'):
            if isinstance(record.msg, str):
                message = record.msg
            else:
                # Если record.msg - это не строка (например, объект форматирования),
                # получаем отформатированное сообщение
                message = record.getMessage()
        else:
            message = record.getMessage()
        
        # Определяем имя логгера заранее (используется и ниже)
        logger_name = record.name if hasattr(record, 'name') else 'ROOT'
        
        # Извлекаем категорию из сообщения (например, [INIT], [AUTO], etc.)
        category = 'DEFAULT'
        emoji = '📝'
        
        if isinstance(message, str):
            # Ищем категорию в формате [CATEGORY] в начале сообщения
            import re
            # Ищем категорию в начале сообщения (может быть с пробелами или без)
            # Используем более точное регулярное выражение
            match = re.search(r'^\[([A-Z_]+)\]\s*', message)
            if match:
                category = match.group(1)
                emoji = self.EMOJIS.get(category, '📝')
                # Удаляем префикс категории из сообщения, чтобы избежать дубликата
                # Удаляем [CATEGORY] и возможные пробелы после него
                # Важно: удаляем ТОЛЬКО из начала сообщения
                message_cleaned = re.sub(r'^\[([A-Z_]+)\]\s*', '', message, count=1).strip()
                # Убеждаемся, что удалили именно этот префикс
                if message_cleaned != message:
                    message = message_cleaned
                    # Обновляем record.msg, чтобы удалить префикс из финального сообщения
                    if hasattr(record, 'msg') and isinstance(record.msg, str):
                        record.msg = message
                    # Переопределяем getMessage() чтобы вернуть очищенное сообщение
                    try:
                        # Сохраняем оригинальный getMessage
                        original_getMessage = record.getMessage
                        # Переопределяем его
                        def getMessage_override():
                            return message
                        record.getMessage = getMessage_override
                    except:
                        pass
        
        # ВАЖНО: Удаляем любые оставшиеся префиксы [CATEGORY] из сообщения
        # Это нужно для случаев, когда префиксы добавляются динамически
        if isinstance(message, str):
            import re
            # Удаляем все префиксы [CATEGORY] из начала сообщения
            # (на случай, если они добавились после первоначальной обработки)
            message = re.sub(r'^\[([A-Z_]+)\]\s*', '', message, count=1)
            # Также удаляем префиксы после ANSI-кодов
            message = re.sub(r'(\033\[[0-9;]*m)*\[([A-Z_]+)\]\s*', r'\1', message, count=1)
            
            # Специальная обработка для werkzeug логов - упрощаем формат
            if logger_name == 'werkzeug' or 'werkzeug' in logger_name.lower():
                # Убираем дублирование даты/времени и упрощаем формат
                # Было: 192.168.1.2 - - [14/Nov/2025 05:37:36] "%s" %s %s
                # Станет: GET /api/positions 200
                message = re.sub(r'^[\d\.\s-]+\[.*?\]\s*', '', message)  # Убираем IP и дату
                message = re.sub(r'["%s"]+\s*%s\s*%s', '', message)  # Убираем плейсхолдеры
                message = message.strip()
                
                # Если сообщение пустое или содержит только плейсхолдеры, пропускаем
                if not message or message == '%s' or len(message) < 3:
                    return ''  # Пропускаем пустые сообщения
        
        # Определяем префикс на основе имени логгера (как в ai.py)
        if logger_name.startswith('AI.') or logger_name == 'AI.Main':
            prefix = '[AI]'
        elif logger_name == 'werkzeug' or 'werkzeug' in logger_name.lower():
            prefix = '[APP]'
        elif logger_name.startswith('BotsService') or logger_name == 'BotsService' or 'bot' in logger_name.lower():
            prefix = '[BOTS]'
        else:
            # Для остальных логгеров определяем префикс по имени
            if 'ai' in logger_name.lower():
                prefix = '[AI]'
            elif 'app' in logger_name.lower() or 'flask' in logger_name.lower():
                prefix = '[APP]'
            else:
                prefix = '[BOTS]'  # По умолчанию для bots.py
        
        # Форматируем время без даты и миллисекунд (компактный формат)
        try:
            dt = datetime.fromtimestamp(record.created)
            timestamp = dt.strftime('%H:%M:%S')
        except:
            # Если не удалось получить время, используем текущее время
            dt = datetime.now()
            timestamp = dt.strftime('%H:%M:%S')
        
        # Применяем цвета к разным частям сообщения
        if record.levelname == 'ERROR':
            colored_message = f"{Colors.BRIGHT_RED}{message}{Colors.RESET}"
        elif record.levelname == 'WARNING':
            colored_message = f"{Colors.BRIGHT_YELLOW}{message}{Colors.RESET}"
        elif record.levelname == 'INFO':
            # Выделяем важные части сообщения
            colored_message = self._highlight_important_parts(message)
        else:
            colored_message = message
        
        # Создаем цветные части (компактный формат)
        colored_prefix = f"{Colors.BRIGHT_MAGENTA}{prefix}{Colors.RESET}"
        colored_timestamp = f"{Colors.DIM}{timestamp}{Colors.RESET}"
        colored_level = f"{level_color}{record.levelname}{Colors.RESET}"
        
        # Компактный формат: [PREFIX] HH:MM:SS - LEVEL - message
        formatted = f"{colored_prefix} {colored_timestamp} - {colored_level} - {colored_message}"
        
        return formatted
    
    def _highlight_important_parts(self, message):
        """Выделяет важные части сообщения цветом"""
        # Выделяем числа
        import re
        message = re.sub(r'(\d+\.?\d*)', f'{Colors.BRIGHT_CYAN}\\1{Colors.RESET}', message)
        
        # Выделяем статусы
        statuses = ['running', 'idle', 'in_position_long', 'in_position_short', 'paused']
        for status in statuses:
            message = message.replace(status, f'{Colors.BRIGHT_GREEN}{status}{Colors.RESET}')
        
        # Выделяем символы монет
        message = re.sub(r'\b([A-Z]{2,10})\b', f'{Colors.BRIGHT_BLUE}\\1{Colors.RESET}', message)
        
        # Выделяем проценты
        message = re.sub(r'(\d+\.?\d*%)', f'{Colors.BRIGHT_YELLOW}\\1{Colors.RESET}', message)
        
        return message

def setup_color_logging(console_log_levels=None):
    """
    Настройка цветного логирования
    
    Args:
        console_log_levels: Список настроек уровней логирования для консоли, например:
            ['+INFO', '-WARNING', '+ERROR', '-DEBUG']
            Если None - все уровни разрешены
    """
    # Создаем логгер
    logger = logging.getLogger()
    # Устанавливаем минимальный уровень, чтобы все сообщения доходили до фильтра
    logger.setLevel(logging.DEBUG)
    
    # Проверяем, есть ли уже консольный обработчик с нашим фильтром
    # Если есть, обновляем фильтр, но не пересоздаём обработчик
    has_our_handler = False
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            # Проверяем, есть ли наш фильтр
            for filter_obj in handler.filters:
                if isinstance(filter_obj, LogLevelFilter):
                    has_our_handler = True
                    # Обновляем настройки фильтра, если они изменились
                    # Создаём новый фильтр с новыми настройками
                    new_filter = LogLevelFilter(console_log_levels)
                    # Заменяем старый фильтр на новый
                    handler.removeFilter(filter_obj)
                    handler.addFilter(new_filter)
                    break
    
    # Если обработчик уже есть и фильтр обновлён, не пересоздаём обработчик
    if has_our_handler:
        return logger
    
    # КРИТИЧНО: Удаляем ВСЕ консольные обработчики БЕЗ нашего фильтра из ВСЕХ логгеров
    # Это нужно, чтобы гарантировать, что все логи проходят через наш фильтр
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            # Проверяем, есть ли наш фильтр
            has_our_filter = any(isinstance(f, LogLevelFilter) for f in handler.filters)
            if not has_our_filter:
                logger.removeHandler(handler)
    
    # КРИТИЧНО: Удаляем консольные обработчики из ВСЕХ существующих логгеров
    # Это гарантирует, что все логи идут через корневой логгер с нашим фильтром
    for existing_logger_name in logging.Logger.manager.loggerDict:
        existing_logger = logging.getLogger(existing_logger_name)
        # Удаляем все StreamHandler'ы без нашего фильтра
        for handler in existing_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                has_our_filter = any(isinstance(f, LogLevelFilter) for f in handler.filters)
                if not has_our_filter:
                    existing_logger.removeHandler(handler)
        # Убеждаемся, что все логгеры пропагируют в корневой
        existing_logger.propagate = True
        existing_logger.setLevel(logging.DEBUG)
    
    # Создаем консольный обработчик
    # На Windows используем errors='replace' для обработки эмодзи
    console_handler = logging.StreamHandler(sys.stdout)
    # Устанавливаем кодировку для Windows консоли
    if sys.platform == 'win32' and hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except:
            pass  # Если не удалось, используем стандартную кодировку
    console_handler.setLevel(logging.DEBUG)  # Устанавливаем минимальный уровень для обработчика
    
    # Применяем фильтр уровней
    # Создаем фильтр всегда (даже для пустого списка или None - это означает "все уровни разрешены")
    level_filter = LogLevelFilter(console_log_levels)
    console_handler.addFilter(level_filter)
    
    # Устанавливаем цветной форматтер
    formatter = ColorFormatter()
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчик к логгеру
    logger.addHandler(console_handler)
    
    # ОТЛАДКА: Проверяем, что обработчик добавлен (только для отладки, можно убрать)
    # sys.stderr.write(f"[COLOR_LOGGER] Обработчик добавлен, всего handlers: {len(logger.handlers)}\n")
    # sys.stderr.write(f"[COLOR_LOGGER] enabled_levels: {level_filter.enabled_levels}\n")
    # sys.stderr.write(f"[COLOR_LOGGER] debug_enabled: {level_filter.debug_enabled}\n")
    
    # Настраиваем уровни для внешних логгеров, чтобы они не шумели
    # Определяем, какие уровни разрешены
    allowed_levels = set()
    if level_filter and level_filter.enabled_levels:
        allowed_levels = level_filter.enabled_levels
    else:
        # Если фильтр не настроен, разрешаем все уровни
        allowed_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    
    # Настраиваем уровни для внешних библиотек
    external_loggers = [
        'urllib3',
        'urllib3.connectionpool',
        'urllib3.util',
        'urllib3.poolmanager',
        'pybit',
        'pybit._http_manager',
        'requests',
        'requests.packages.urllib3',
        'httpcore',
        'httpx',
        'tensorflow',
        'tensorflow.python',
        'tensorflow.core',
        'tensorflow._api',
    ]
    
    # Определяем минимальный разрешенный уровень
    level_priority = {'DEBUG': 10, 'INFO': 20, 'WARNING': 30, 'ERROR': 40, 'CRITICAL': 50}
    min_level = min([level_priority.get(level, 50) for level in allowed_levels], default=50)
    
    # Устанавливаем уровень для внешних логгеров
    for logger_name in external_loggers:
        external_logger = logging.getLogger(logger_name)
        # НЕ устанавливаем уровень здесь - оставляем DEBUG, чтобы сообщения доходили до фильтра
        # Фильтрация происходит через LogLevelFilter в обработчике
        # Убеждаемся, что они используют корневой логгер (propagate=True)
        external_logger.propagate = True
    
    # Также настраиваем уровни для наших логгеров
    our_loggers = [
        'exchanges.exchange_factory',
        'exchanges',
        'root',
        'app',
        'BotsService',
        'API.AI',
        'AI.Main',
        'bot_engine.bot_history',
    ]
    
    for logger_name in our_loggers:
        our_logger = logging.getLogger(logger_name)
        # НЕ удаляем обработчики - пусть они остаются, если есть
        # НЕ устанавливаем уровень здесь - оставляем DEBUG, чтобы сообщения доходили до фильтра
        # Фильтрация происходит через LogLevelFilter в обработчике
        # КРИТИЧНО: propagate=True, чтобы сообщения шли в корневой логгер с фильтром
        our_logger.propagate = True
        our_logger.setLevel(logging.DEBUG)
    
    # НЕ устанавливаем уровень корневого логгера на min_level,
    # так как это предотвратит создание сообщений ниже этого уровня,
    # и фильтр не сможет их обработать.
    # Фильтрация происходит через LogLevelFilter в обработчике.
    
    return logger

if __name__ == "__main__":
    # Тест цветного логирования
    setup_color_logging()
    logger = logging.getLogger("test")
    
    logger.info("[INIT] 🚀 Инициализация системы...")
    logger.info("[AUTO] 🤖 Auto Bot включен: True")
    logger.info("[SYNC] 🔄 Синхронизация позиций с биржей")
    logger.warning("[WARNING] ⚠️ Обнаружено 6 расхождений между ботом и биржей")
    logger.error("[ERROR] ❌ Ошибка подключения к бирже")
    logger.info("[BOT] 🤖 Создан бот для BTC (RSI: 25.3, сигнал: ENTER_LONG)")
    logger.info("[POSITION] 📊 Найдено 97 активных позиций с биржи")
    logger.info("[CACHE] 💾 Кэш обновлен: 17 ботов")
