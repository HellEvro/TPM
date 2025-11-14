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
TARGET_COMPILED = Path('bot_engine/ai/_ai_launcher.pyc')
TARGET_WRAPPER = Path('ai.py')
STUB_PATH = Path('bot_engine/ai/_infobot_ai_protected.py')


def build_launcher() -> None:
    """Компилирует исходник и записывает новый ai.py-обёртку."""
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f'Не найден исходник: {SOURCE_PATH}')

    TARGET_COMPILED.parent.mkdir(parents=True, exist_ok=True)
    py_compile.compile(
        file=str(SOURCE_PATH),
        cfile=str(TARGET_COMPILED),
        dfile='ai_protected.py',
        optimize=2,
    )

    wrapper = textwrap.dedent(
        '''\
        #!/usr/bin/env python3
        # -*- кодировка: utf-8 -*-
        """
        Оболочка для защищённого AI лаунчера.
        Вся рабочая логика находится в bot_engine/ai/_ai_launcher.pyc
        """

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
            _protected_module.main()
        '''
    )

    TARGET_WRAPPER.write_text(wrapper, encoding='utf-8')

    stub = textwrap.dedent(
        '''\
        #!/usr/bin/env python3
        # -*- кодировка: utf-8 -*-
        """
        Loader stub для защищённого AI лаунчера.
        Подгружает bot_engine/ai/_ai_launcher.pyc и регистрирует его как модуль.
        """

        import importlib.machinery
        import sys
        from pathlib import Path

        _COMPILED_NAME = "_ai_launcher.pyc"
        _compiled_path = Path(__file__).with_name(_COMPILED_NAME)

        if not _compiled_path.exists():
            raise RuntimeError(f"Не найден защищённый AI модуль: {_compiled_path}")

        _loader = importlib.machinery.SourcelessFileLoader(__name__, str(_compiled_path))
        _loader.exec_module(sys.modules[__name__])
        '''
    )

    STUB_PATH.write_text(stub, encoding='utf-8')

    print('[OK] Скомпилирован _ai_launcher.pyc, обновлены ai.py и loader')


if __name__ == '__main__':
    build_launcher()

