#!/usr/bin/env python3
# -*- кодировка: utf-8 -*-
"""
Оболочка для защищённого AI лаунчера.
Вся рабочая логика находится в bot_engine/ai/_ai_launcher.pyc
"""

# Настройка логирования ПЕРЕД импортом защищенного модуля
import sys
import logging

# Раннее логирование через stderr для отладки
sys.stderr.write("[AI WRAPPER] Начало выполнения обёртки ai.py\n")

try:
    sys.stderr.write("[AI WRAPPER] Импорт конфига...\n")
    from bot_engine.ai.ai_launcher_config import AILauncherConfig
    from utils.color_logger import setup_color_logging
    console_levels = getattr(AILauncherConfig, 'CONSOLE_LOG_LEVELS', [])
    sys.stderr.write(f"[AI WRAPPER] CONSOLE_LOG_LEVELS = {console_levels}\n")
    setup_color_logging(console_log_levels=console_levels if console_levels else None)
    sys.stderr.write("[AI WRAPPER] Логирование настроено, тестируем...\n")
    # Тестовое логирование для проверки, что логирование работает
    test_logger = logging.getLogger('ai.wrapper')
    test_logger.info("✅ Логирование настроено в обёртке ai.py")
    sys.stderr.write("[AI WRAPPER] Тестовое логирование отправлено\n")
except Exception as e:
    sys.stderr.write(f"[AI WRAPPER] Ошибка настройки логирования: {e}\n")
    import traceback
    sys.stderr.write(traceback.format_exc())
    # Если не удалось загрузить конфиг, используем стандартную настройку
    try:
        from utils.color_logger import setup_color_logging
        setup_color_logging()
        test_logger = logging.getLogger('ai.wrapper')
        test_logger.info("✅ Логирование настроено в обёртке ai.py (стандартная настройка)")
    except Exception as setup_error:
        sys.stderr.write(f"❌ Ошибка настройки логирования: {setup_error}\n")

sys.stderr.write("[AI WRAPPER] Импорт защищённого модуля...\n")

from typing import TYPE_CHECKING, Any
from bot_engine.ai import _infobot_ai_protected as _protected_module


if TYPE_CHECKING:
    def main(*args: Any, **kwargs: Any) -> Any: ...


_globals = globals()
_skip = {'__name__', '__doc__', '__package__', '__loader__', '__spec__', '__file__'}

for _key, _value in _protected_module.__dict__.items():
    if _key in _skip:
        continue
    _globals[_key] = _value

del _globals, _skip, _key, _value


if __name__ == '__main__':
    import sys
    sys.stderr.write("[AI WRAPPER] Вызов _protected_module.main()...\n")
    _protected_module.main()
