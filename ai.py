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
