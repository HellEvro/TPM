#!/usr/bin/env python3
"""
Скрипт для копирования файлов в публичную версию
Исключает: license_generator/, keys.py, InfoBot_AI_Premium/ (источники)
"""

import shutil
from pathlib import Path
import os

EXCLUDE_FOLDERS = [
    'license_generator',
    'InfoBot_AI_Premium',  # Исходники для разработки
    'InfoBot_Public',  # Целевая папка
    '.git',
    '__pycache__',
    'dist',
    'build',
    'generated_licenses',
    'backups',
    'deploy',
]

EXCLUDE_FILES = [
    'keys.py',
    'keys.example.py',
    'config.py',
]

def should_copy(path: Path) -> bool:
    """Проверяет, нужно ли копировать файл/папку"""
    # Проверяем папки
    if path.is_dir():
        if path.name in EXCLUDE_FOLDERS:
            return False
    
    # Проверяем файлы
    if path.is_file():
        if path.name in EXCLUDE_FILES:
            return False
        
        # Исключаем .lic файлы (лицензии клиентов)
        if path.suffix == '.lic':
            return False
    
    return True

def copy_to_public():
    """Копирует файлы в InfoBot_Public"""
    
    print("=" * 60)
    print("COPYING TO PUBLIC VERSION")
    print("=" * 60)
    print()
    
    source = Path('.')
    target = Path('InfoBot_Public')
    
    if not target.exists():
        print(f"[ERROR] Target directory {target} does not exist!")
        return False
    
    # Счетчики
    copied_files = 0
    copied_dirs = 0
    skipped = 0
    
    # Копируем рекурсивно
    for path in source.rglob('*'):
        if path.is_dir():
            continue
        
        # Пропускаем исключенные
        if not should_copy(path):
            skipped += 1
            continue
        
        # Определяем относительный путь
        rel_path = path.relative_to(source)
        target_path = target / rel_path
        
        # Создаем директории
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Копируем файл
        try:
            shutil.copy2(path, target_path)
            copied_files += 1
            if copied_files % 50 == 0:
                print(f"Copied {copied_files} files...")
        except Exception as e:
            print(f"[ERROR] Failed to copy {path}: {e}")
    
    print()
    print("=" * 60)
    print("COPY COMPLETE")
    print("=" * 60)
    print(f"Files copied: {copied_files}")
    print(f"Files skipped: {skipped}")
    print()
    print(f"Public version updated: {target}")
    print()

if __name__ == '__main__':
    copy_to_public()

