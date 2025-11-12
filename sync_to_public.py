#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синхронизация файлов в InfoBot_Public"""

import os
import shutil
import sys
from pathlib import Path

# Настройка кодировки для Windows консоли
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        try:
            import subprocess
            subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
        except:
            pass

ROOT = Path(__file__).parent
PUBLIC = ROOT / "InfoBot_Public"

# Что копируем
INCLUDE = [
    "app.py", "bots.py", "ai.py", "README.md", "requirements.txt", "requirements_ai.txt",
    "INSTALL.md", "LICENSE",
    "start_infobot_manager.cmd", "start_infobot_manager.sh", "start_infobot_manager.vbs",
    "app/", "bot_engine/", "bots_modules/", "exchanges/", "utils/",
    "static/", "templates/", "docs/", "data/", "scripts/", "installer/", "launcher/",
]

# Что НЕ копируем
EXCLUDE_DIRS = [
    ".git", "__pycache__", "node_modules",
    "license_generator",  # ВСЯ папка license_generator - там исходники генерации!
    "scripts/fix", "scripts/check",
    "backups",
    "docs/ai_development",
    "docs/ai_technical",
    "docs/ai_guides",
]

EXCLUDE_FILES = [
    "app/keys.py", "app/config.py", "app/current_language.txt", "app/telegram_states.json",
    "scripts/test_*.py", "scripts/verify_*.py",
    "*.pyc",  # Скомпилированные файлы
]

# Файлы которые генерируются системой при работе
GENERATED_FILES = [
    "data/async_state.json",
    "data/bot_history.json", 
    "data/process_state.json",
    "data/bots_state.json",
    "data/telegram_states.json",
    "logs/*.log",
    "license_generator/*.pyc",
]

# Документы разработки (не для пользователей)
DEV_DOCS = [
    "docs/AI_*.md",
    "docs/GIT_*.md",
    "docs/LSTM_*.md",
    "docs/SYNC_REPORT*.md",
    "docs/LOG_ROTATION.md",
    "docs/BOT_SIGNAL*.md",
    "docs/CONFIGURATION.md",
    "docs/DEPLOYMENT.md",
    "docs/FILTER_LOGIC*.md",
    "docs/DOCUMENTATION_COMPLETE.md",
    "docs/READY_FOR_YOU.md",
    "docs/READ_ME_FIRST.txt",
    "docs/GITIGNORE*.md",
    "docs/ARCHITECTURE.md",
    "docs/BOT_HISTORY.md",
    "docs/Bots_TZ.md",
    "docs/FUTURE_FEATURES.md",
    "docs/CHANGELOG.md",
]

def should_exclude(path_str):
    """Проверяет нужно ли исключить путь"""
    import fnmatch
    
    # Проверяем директории
    for exc in EXCLUDE_DIRS:
        if exc in path_str:
            return True
    
    # Проверяем файлы для исключения
    for exc in EXCLUDE_FILES:
        if fnmatch.fnmatch(path_str, exc) or exc == path_str:
            return True
    
    # Проверяем генерируемые файлы
    for gen in GENERATED_FILES:
        if fnmatch.fnmatch(path_str, gen) or gen == path_str:
            return True
    
    # Проверяем документы разработки
    for doc in DEV_DOCS:
        if fnmatch.fnmatch(path_str, doc) or doc == path_str:
            return True
    
    return False

def sync_file(src: Path, dst: Path):
    """Синхронизирует один файл - ПРИНУДИТЕЛЬНО копирует всегда!"""
    try:
        if not dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
        # ✅ ВСЕГДА копируем! Не проверяем mtime - мы обновляем только в одну сторону!
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"Error copying {src}: {e}")
        return False

print("=" * 80)
print("СИНХРОНИЗАЦИЯ В ПУБЛИЧНУЮ ВЕРСИЮ")
print("=" * 80)
print()

# Удаляем ненужные папки (ВАЖНО: НЕ ТРОГАЕМ .git!)
for item in PUBLIC.iterdir():
    # КРИТИЧЕСКИ ВАЖНО: НИКОГДА НЕ УДАЛЯЕМ .git!!!
    if item.name == '.git':
        continue
    if item.is_dir() and should_exclude(item.name):
        print(f"[SKIP] Пропускаем папку: {item.name}")

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

