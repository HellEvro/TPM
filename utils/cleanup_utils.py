# -*- coding: utf-8 -*-
"""
Периодическая очистка временных файлов и освобождение ресурсов.

- Удаление устаревших .tmp файлов в data/, logs/
- Очистка пустой папки build_temp при необходимости
- Не удаляет файлы, изменённые недавно (защита от активной записи)
"""

import gc
import os
import time
from pathlib import Path
from typing import Tuple

# Возраст файла (сек), после которого .tmp считается «зависшим» и его можно удалить
TEMP_FILE_MAX_AGE_SECONDS = 3600  # 1 час
# Минимальный возраст для удаления build_temp (сек)
BUILD_TEMP_MIN_AGE_SECONDS = 86400  # 24 часа


def cleanup_temp_files(project_root: str | Path, max_age_seconds: int = TEMP_FILE_MAX_AGE_SECONDS) -> int:
    """
    Удаляет устаревшие временные файлы (.tmp) в data/ и logs/.

    Не трогает файлы, изменённые недавно (чтобы не удалить .tmp во время записи).

    :param project_root: корень проекта (каталог с data/, logs/)
    :param max_age_seconds: удалять .tmp старше этого количества секунд
    :return: количество удалённых файлов
    """
    root = Path(project_root)
    if not root.is_dir():
        return 0
    now = time.time()
    removed = 0
    for dir_name in ("data", "logs"):
        dir_path = root / dir_name
        if not dir_path.is_dir():
            continue
        try:
            for p in dir_path.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix == ".tmp" or p.name.endswith(".tmp"):
                    try:
                        if now - p.stat().st_mtime >= max_age_seconds:
                            p.unlink()
                            removed += 1
                    except OSError:
                        pass
        except OSError:
            pass
    return removed


def cleanup_build_temp(project_root: str | Path, min_age_seconds: int = BUILD_TEMP_MIN_AGE_SECONDS) -> bool:
    """
    Удаляет каталог build_temp, если он существует и не изменялся давно.

    :param project_root: корень проекта
    :param min_age_seconds: удалять только если каталог не трогали min_age_seconds секунд
    :return: True если каталог был удалён
    """
    root = Path(project_root)
    build_temp = root / "build_temp"
    if not build_temp.is_dir():
        return False
    try:
        mtime = build_temp.stat().st_mtime
        if time.time() - mtime >= min_age_seconds:
            import shutil
            shutil.rmtree(build_temp, ignore_errors=True)
            return True
    except OSError:
        pass
    return False


def run_periodic_cleanup(
    project_root: str | Path,
    temp_max_age: int = TEMP_FILE_MAX_AGE_SECONDS,
    trim_memory: bool = True,
) -> Tuple[int, bool]:
    """
    Полный цикл периодической очистки: временные файлы + при необходимости подрезка кэшей и GC.

    :param project_root: корень проекта
    :param temp_max_age: возраст (сек), после которого .tmp удаляются
    :param trim_memory: вызывать trim_memory_caches и gc
    :return: (количество удалённых .tmp файлов, была ли вызвана очистка памяти)
    """
    removed = cleanup_temp_files(project_root, max_age_seconds=temp_max_age)
    memory_done = False
    if trim_memory:
        try:
            from bots_modules.sync_and_cache import trim_memory_caches
            trim_memory_caches()
            gc.collect(2)
            memory_done = True
        except Exception:
            try:
                gc.collect(2)
                memory_done = True
            except Exception:
                pass
    return removed, memory_done
