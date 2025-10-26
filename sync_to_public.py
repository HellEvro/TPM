#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синхронизация файлов в InfoBot_Public"""

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
PUBLIC = ROOT / "InfoBot_Public"

# Что копируем
INCLUDE = [
    "app.py", "bots.py", "README.md", "requirements.txt", "requirements_ai.txt",
    "INSTALL.md", "LICENSE",
    "app/", "bot_engine/", "bots_modules/", "exchanges/", "utils/",
    "static/", "templates/", "docs/", "data/", "scripts/",
]

# Что НЕ копируем
EXCLUDE_DIRS = [
    ".git", "__pycache__", "*.pyc", "node_modules",
    "license_generator/source",
    "scripts/fix", "scripts/check",
]

EXCLUDE_FILES = [
    "app/keys.py", "app/config.py",
    "scripts/test_*.py", "scripts/verify_*.py",
]

def should_exclude(path_str):
    """Проверяет нужно ли исключить путь"""
    for exc in EXCLUDE_DIRS:
        if exc in path_str:
            return True
    for exc in EXCLUDE_FILES:
        import fnmatch
        if fnmatch.fnmatch(path_str, exc):
            return True
    return False

def sync_file(src: Path, dst: Path):
    """Синхронизирует один файл"""
    try:
        if not dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            return  # Уже актуальный
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"Error copying {src}: {e}")
        return False

print("=" * 80)
print("СИНХРОНИЗАЦИЯ В ПУБЛИЧНУЮ ВЕРСИЮ")
print("=" * 80)
print()

# Удаляем ненужные папки
for item in PUBLIC.iterdir():
    if item.name == '.git':
        continue
    if item.is_dir():
        if should_exclude(item.name):
            print(f"Удаление папки: {item}")
            shutil.rmtree(item, ignore_errors=True)

# Копируем нужные файлы
copied = 0
for pattern in INCLUDE:
    src = ROOT / pattern
    if not src.exists():
        continue
    
    if src.is_file():
        if should_exclude(str(pattern)):
            continue
        dst = PUBLIC / pattern
        if sync_file(src, dst):
            copied += 1
    
    elif src.is_dir():
        for root, dirs, files in os.walk(src):
            # Исключаем директории
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d))]
            
            for file in files:
                src_file = Path(root) / file
                rel_path = src_file.relative_to(ROOT)
                
                if should_exclude(str(rel_path)):
                    continue
                
                dst_file = PUBLIC / rel_path
                if sync_file(src_file, dst_file):
                    copied += 1

print()
print(f"[OK] Скопировано файлов: {copied}")
print("[DONE] Синхронизация завершена")

