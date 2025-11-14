#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Компилирует исходный AI-лаунчер в защищённый .pyc модуль и обновляет ai.py.

1. Правьте код в license_generator/source/@source/ai_launcher_source.py
2. Запускайте:
       python license_generator/build_ai_launcher.py
3. Скрипт создаст bot_engine/ai/_ai_launcher.pyc и тонкий оболочный ai.py
"""

from pathlib import Path
import py_compile
import textwrap

SOURCE_PATH = Path('license_generator/source/@source/ai_launcher_source.py')
TARGET_COMPILED = Path('bot_engine/ai/_ai_launcher.pyc')
TARGET_WRAPPER = Path('ai.py')


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
        # -*- coding: utf-8 -*-
        """
        Оболочка для защищённого AI лаунчера.
        Вся рабочая логика находится в bot_engine/ai/_ai_launcher.pyc
        """

        import importlib.machinery
        import importlib.util
        import sys
        from pathlib import Path
        from typing import TYPE_CHECKING, Any

        _MODULE_NAME = "_infobot_ai_protected"
        _COMPILED_NAME = "_ai_launcher.pyc"
        _PROTECTED_MODULE = None


        def _load_protected_module():
            global _PROTECTED_MODULE
            if _PROTECTED_MODULE is not None:
                return _PROTECTED_MODULE

            compiled_path = Path(__file__).parent / 'bot_engine' / 'ai' / _COMPILED_NAME
            if not compiled_path.exists():
                raise RuntimeError(
                    f"Не найден защищённый AI модуль: {compiled_path}"
                )

            loader = importlib.machinery.SourcelessFileLoader(
                _MODULE_NAME, str(compiled_path)
            )
            spec = importlib.util.spec_from_loader(loader.name, loader)
            module = importlib.util.module_from_spec(spec)
            loader.exec_module(module)
            sys.modules.setdefault(_MODULE_NAME, module)
            _PROTECTED_MODULE = module

            for name, value in module.__dict__.items():
                if name == '__builtins__':
                    continue
                globals()[name] = value

            return module


        if TYPE_CHECKING:
            def main(*args: Any, **kwargs: Any) -> Any: ...


        _load_protected_module()


        if __name__ == '__main__':
            main()
        '''
    )

    TARGET_WRAPPER.write_text(wrapper, encoding='utf-8')
    print('[OK] Скомпилирован _ai_launcher.pyc и обновлён ai.py')


if __name__ == '__main__':
    build_launcher()

