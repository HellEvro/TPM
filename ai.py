#!/usr/bin/env python3
# -*- кодировка: utf-8 -*-
"""
Оболочка для защищённого AI лаунчера.
Вся рабочая логика находится в bot_engine/ai/_ai_launcher.pyc
"""

# Настройка логирования ПЕРЕД импортом защищенного модуля
import logging
try:
    from bot_engine.ai.ai_launcher_config import AILauncherConfig
    from utils.color_logger import setup_color_logging
    console_levels = getattr(AILauncherConfig, 'CONSOLE_LOG_LEVELS', [])
    setup_color_logging(console_log_levels=console_levels if console_levels else None)
except Exception as e:
    # Если не удалось загрузить конфиг, используем стандартную настройку
    try:
        from utils.color_logger import setup_color_logging
        setup_color_logging()
    except Exception as setup_error:
        import sys
        sys.stderr.write(f"❌ Ошибка настройки логирования: {setup_error}\n")

from typing import TYPE_CHECKING, Any
from bot_engine.ai import _infobot_ai_protected as _protected_module


if TYPE_CHECKING:
    def main(*args: Any, **kwargs: Any) -> Any: ...


# ==================== ПЕРЕХВАТ СОХРАНЕНИЯ data_service.json В БД ====================
# Патчим метод _update_data_status в AISystem, чтобы он сохранял в БД вместо файла
def _patch_ai_system_update_data_status():
    """Патчит метод _update_data_status в AISystem для сохранения в БД"""
    try:
        # Импортируем helper для работы с БД
        from bot_engine.ai.data_service_status_helper import update_data_service_status_in_db
        
        # Получаем класс AISystem из защищенного модуля
        if hasattr(_protected_module, 'AISystem'):
            original_update_data_status = _protected_module.AISystem._update_data_status
            
            def patched_update_data_status(self, **kwargs):
                """Патченный метод - сохраняет в БД вместо файла"""
                try:
                    # Сохраняем в БД вместо файла
                    update_data_service_status_in_db(**kwargs)
                except Exception as e:
                    # Если БД недоступна, пробуем оригинальный метод (fallback)
                    try:
                        original_update_data_status(self, **kwargs)
                    except:
                        pass
            
            # Заменяем метод
            _protected_module.AISystem._update_data_status = patched_update_data_status
    except Exception as e:
        # Если патч не удался - продолжаем работу (не критично)
        pass

# Применяем патч ПЕРЕД экспортом модуля
_patch_ai_system_update_data_status()
# ==================== КОНЕЦ ПЕРЕХВАТА ====================


_globals = globals()
_skip = {'__name__', '__doc__', '__package__', '__loader__', '__spec__', '__file__'}

for _key, _value in _protected_module.__dict__.items():
    if _key in _skip:
        continue
    _globals[_key] = _value

del _globals, _skip, _key, _value


if __name__ == '__main__':
    _protected_module.main()
