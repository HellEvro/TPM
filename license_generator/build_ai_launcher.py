#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Компилирует исходный AI-лаунчер в защищённый .pyc модуль и обновляет обёртки.

1. Правьте код в license_generator/source/@source/ai_launcher_source.py
2. Запускайте:
       python license_generator/build_ai_launcher.py
3. Скрипт создаст bot_engine/ai/_ai_launcher.pyc,
   обновит обёртку ai.py и loader bot_engine/ai/_infobot_ai_protected.py
"""

from pathlib import Path
import py_compile
import textwrap

SOURCE_PATH = Path('license_generator/source/@source/ai_launcher_source.py')
TARGET_WRAPPER = Path('ai.py')
STUB_PATH = Path('bot_engine/ai/_infobot_ai_protected.py')


def build_launcher() -> None:
    """Компилирует исходник и записывает новый ai.py-обёртку."""
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f'Не найден исходник: {SOURCE_PATH}')

    import sys
    python_version = sys.version_info[:2]
    
    # Определяем целевую директорию на основе версии Python
    base_dir = Path('bot_engine/ai')
    if python_version >= (3, 14):
        target_dir = base_dir / 'pyc_314'
        version_name = "3.14"
    elif python_version == (3, 12):
        target_dir = base_dir / 'pyc_312'
        version_name = "3.12"
    else:
        # Для других версий используем основную директорию
        target_dir = base_dir
        version_name = f"{python_version[0]}.{python_version[1]}"
    
    target_dir.mkdir(parents=True, exist_ok=True)
    TARGET_COMPILED = target_dir / '_ai_launcher.pyc'
    
    print(f"[INFO] Компиляция через Python {version_name}")
    print(f"[INFO] Целевая директория: {target_dir}")
    
    py_compile.compile(
        file=str(SOURCE_PATH),
        cfile=str(TARGET_COMPILED),
        dfile='ai_protected.py',
        optimize=2,
    )
    
    print(f"[OK] Скомпилирован: {TARGET_COMPILED}")

    wrapper = textwrap.dedent(
        '''\
        #!/usr/bin/env python3
        # -*- кодировка: utf-8 -*-
        """
        Оболочка для защищённого AI лаунчера.
        Вся рабочая логика находится в bot_engine/ai/_ai_launcher.pyc
        """

        # ⚠️ КРИТИЧНО: Устанавливаем переменную окружения для идентификации процесса ai.py
        # Это гарантирует, что функции из filters.py будут сохранять свечи в ai_data.db, а не в bots_data.db
        import os
        os.environ['INFOBOT_AI_PROCESS'] = 'true'

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
                sys.stderr.write(f"❌ Ошибка настройки логирования: {setup_error}\\n")

        from typing import TYPE_CHECKING, Any
        from bot_engine.ai import _infobot_ai_protected as _protected_module


        if TYPE_CHECKING:
            def main(*args: Any, **kwargs: Any) -> Any: ...


        # Патч для перенаправления data_service.json в БД
        def _patch_ai_system_update_data_status():
            """
            Патчит метод _update_data_status в классе AISystem для сохранения в БД вместо файла
            """
            try:
                # Импортируем helper для работы с БД
                from bot_engine.ai.data_service_status_helper import update_data_service_status_in_db
                
                # Получаем класс AISystem из защищенного модуля
                if hasattr(_protected_module, 'AISystem'):
                    AISystem = _protected_module.AISystem
                    
                    # Сохраняем оригинальный метод (на случай если понадобится)
                    original_update_data_status = AISystem._update_data_status
                    
                    # Заменяем метод на версию, которая сохраняет в БД
                    def patched_update_data_status(self, **kwargs):
                        """Патченная версия _update_data_status - сохраняет в БД вместо файла"""
                        try:
                            update_data_service_status_in_db(**kwargs)
                        except Exception as e:
                            # В случае ошибки пробуем оригинальный метод (fallback)
                            try:
                                original_update_data_status(self, **kwargs)
                            except:
                                pass
                    
                    # Применяем патч
                    AISystem._update_data_status = patched_update_data_status
                    
            except Exception as e:
                # Если патч не удался, продолжаем работу без него
                pass

        # Применяем патч ПЕРЕД импортом глобальных переменных
        _patch_ai_system_update_data_status()


        _globals = globals()
        _skip = {'__name__', '__doc__', '__package__', '__loader__', '__spec__', '__file__'}

        for _key, _value in _protected_module.__dict__.items():
            if _key in _skip:
                continue
            _globals[_key] = _value

        del _globals, _skip, _key, _value


        if __name__ == '__main__':
            _protected_module.main()
        '''
    )

    TARGET_WRAPPER.write_text(wrapper, encoding='utf-8')

    # НЕ перезаписываем _infobot_ai_protected.py - он уже содержит логику версионирования
    # Просто проверяем, что файл существует и содержит правильную логику
    if STUB_PATH.exists():
        stub_content = STUB_PATH.read_text(encoding='utf-8')
        if '_get_versioned_pyc_path' not in stub_content:
            # Если файл не содержит логику версионирования, обновляем его
            stub = textwrap.dedent(
                '''\
                #!/usr/bin/env python3
                # -*- кодировка: utf-8 -*-
                """
                Loader stub для защищённого AI лаунчера.
                Подгружает bot_engine/ai/_ai_launcher.pyc и регистрирует его как модуль.
                Поддерживает версионированные .pyc файлы для Python 3.14 и 3.12.
                """

                import importlib.machinery
                import sys
                from pathlib import Path

                def _get_versioned_pyc_path():
                    """Определяет путь к версионированному _ai_launcher.pyc на основе текущей версии Python."""
                    base_dir = Path(__file__).resolve().parent
                    python_version = sys.version_info[:2]
                    
                    # Определяем версию Python и соответствующую директорию
                    if python_version >= (3, 14):
                        version_dir = base_dir / 'pyc_314'
                    elif python_version == (3, 12):
                        version_dir = base_dir / 'pyc_312'
                    else:
                        version_dir = base_dir
                    
                    # Путь к версионированному .pyc файлу
                    versioned_path = version_dir / "_ai_launcher.pyc"
                    
                    # Если версионированный файл не найден, пробуем основную директорию
                    if not versioned_path.exists():
                        fallback_path = base_dir / "_ai_launcher.pyc"
                        if fallback_path.exists():
                            return fallback_path
                        return None
                    
                    return versioned_path

                _compiled_path = _get_versioned_pyc_path()

                if _compiled_path is None:
                    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
                    raise RuntimeError(
                        f"Не найден защищённый AI модуль для Python {python_version}.\\n"
                        f"Версионированный файл отсутствует в директории pyc_{sys.version_info.major}{sys.version_info.minor}/.\\n"
                        f"Обратитесь к разработчику для получения правильной версии модулей."
                    )

                try:
                    _loader = importlib.machinery.SourcelessFileLoader(__name__, str(_compiled_path))
                    _loader.exec_module(sys.modules[__name__])
                except Exception as e:
                    err_msg = str(e).lower()
                    if "bad magic number" in err_msg or "bad magic" in err_msg:
                        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
                        raise RuntimeError(
                            f"_ai_launcher.pyc несовместим с Python {python_version}.\\n"
                            f"Модуль был скомпилирован под другую версию Python.\\n"
                            f"Обратитесь к разработчику для получения правильной версии модулей."
                        )
                    raise
                '''
            )
            STUB_PATH.write_text(stub, encoding='utf-8')
            print(f'[OK] Обновлен _infobot_ai_protected.py с логикой версионирования')
        else:
            print(f'[INFO] _infobot_ai_protected.py уже содержит логику версионирования, пропускаем обновление')
    else:
        # Если файл не существует, создаем его с логикой версионирования
        stub = textwrap.dedent(
            '''\
            #!/usr/bin/env python3
            # -*- кодировка: utf-8 -*-
            """
            Loader stub для защищённого AI лаунчера.
            Подгружает bot_engine/ai/_ai_launcher.pyc и регистрирует его как модуль.
            Поддерживает версионированные .pyc файлы для Python 3.14 и 3.12.
            """

            import importlib.machinery
            import sys
            from pathlib import Path

            def _get_versioned_pyc_path():
                """Определяет путь к версионированному _ai_launcher.pyc на основе текущей версии Python."""
                base_dir = Path(__file__).resolve().parent
                python_version = sys.version_info[:2]
                
                # Определяем версию Python и соответствующую директорию
                if python_version >= (3, 14):
                    version_dir = base_dir / 'pyc_314'
                elif python_version == (3, 12):
                    version_dir = base_dir / 'pyc_312'
                else:
                    version_dir = base_dir
                
                # Путь к версионированному .pyc файлу
                versioned_path = version_dir / "_ai_launcher.pyc"
                
                # Если версионированный файл не найден, пробуем основную директорию
                if not versioned_path.exists():
                    fallback_path = base_dir / "_ai_launcher.pyc"
                    if fallback_path.exists():
                        return fallback_path
                    return None
                
                return versioned_path

            _compiled_path = _get_versioned_pyc_path()

            if _compiled_path is None:
                python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
                raise RuntimeError(
                    f"Не найден защищённый AI модуль для Python {python_version}.\\n"
                    f"Версионированный файл отсутствует в директории pyc_{sys.version_info.major}{sys.version_info.minor}/.\\n"
                    f"Обратитесь к разработчику для получения правильной версии модулей."
                )

            try:
                _loader = importlib.machinery.SourcelessFileLoader(__name__, str(_compiled_path))
                _loader.exec_module(sys.modules[__name__])
            except Exception as e:
                err_msg = str(e).lower()
                if "bad magic number" in err_msg or "bad magic" in err_msg:
                    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
                    raise RuntimeError(
                        f"_ai_launcher.pyc несовместим с Python {python_version}.\\n"
                        f"Модуль был скомпилирован под другую версию Python.\\n"
                        f"Обратитесь к разработчику для получения правильной версии модулей."
                    )
                raise
            '''
        )
        STUB_PATH.write_text(stub, encoding='utf-8')
        print(f'[OK] Создан _infobot_ai_protected.py с логикой версионирования')

    print(f'[OK] Скомпилирован _ai_launcher.pyc для Python {version_name}, обновлены ai.py и loader')


if __name__ == '__main__':
    build_launcher()

