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
PUBLIC = ROOT.parent / "InfoBot_Public"

# Что копируем
INCLUDE = [
    "app.py", "bots.py", "ai.py", "requirements.txt", "requirements_ai.txt",
    "INSTALL.md", "LICENSE",
    "start_infobot_manager.cmd", "start_infobot_manager.sh", "start_infobot_manager.vbs",
    "app/", "bot_engine/", "bots_modules/", "exchanges/", "utils/",
    "static/", "templates/", "docs/", "scripts/", "installer/", "launcher/",
]

# Файлы, которые нужно ВСЕГДА копировать даже если они попали в исключения.
ALWAYS_INCLUDE = [
    "bot_engine/ai/ai_trainer.py",
    "bot_engine/ai/ai_backtester_new.py",
    "bot_engine/ai/ai_strategy_optimizer.py",
    "bot_engine/ai/filter_utils.py",
    "bot_engine/protections.py",
    "bots_modules/bot_class.py",
    "bots_modules/imports_and_globals.py",
    "tests/test_ai_optimizer_genomes.py",
    "tests/test_ai_simulator_parity.py",
    "tests/test_ai_individual_settings.py",
]

# Обязательные элементы: гарантируем, что они присутствуют в списке на копирование.
MANDATORY_ITEMS = [
    "start_infobot_manager.cmd",
    "start_infobot_manager.sh",
    "start_infobot_manager.vbs",
    "launcher/",
    "installer/",
]

for mandatory in MANDATORY_ITEMS:
    if mandatory not in INCLUDE:
        INCLUDE.append(mandatory)

# Что НЕ копируем
EXCLUDE_DIRS = [
    ".git", "__pycache__", "node_modules",
    "license_generator",  # ВСЯ папка license_generator - там исходники генерации!
    "scripts/fix", "scripts/check",
    "backups",
    "docs/ai_development",
    "docs/ai_technical",
    "docs/ai_guides",
    "data",  # ВСЯ папка data - данные не копируются в публичную версию (кроме файлов из ALWAYS_INCLUDE)
]

EXCLUDE_FILES = [
    "app/keys.py", "app/config.py", "app/current_language.txt", "app/telegram_states.json",
    "launcher/.infobot_manager_state.json",
    "scripts/test_*.py", "scripts/verify_*.py",
    "*.pyc",  # Скомпилированные файлы (общее правило)
    "docs/AI_README.md",
    "docs/LICENSE_SYSTEM.md",  # Документация по лицензиям - только для разработчиков
    ".cursorrules",  # Правила Cursor - только для dev версии
]

# ✅ ИСКЛЮЧЕНИЯ: Скомпилированные файлы лицензирования НУЖНЫ в публичной версии
INCLUDE_PYC = [
    "bot_engine/ai/license_checker.pyc",
    "bot_engine/ai/hardware_id_source.pyc",
    "bot_engine/ai/ai_manager.pyc",
    "bot_engine/ai/_ai_launcher.pyc",
    "scripts/hardware_id.pyc",
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
    "docs/DUPLICATES_REPORT.md",
    "docs/MIGRATION_SUMMARY.md",
    "docs/ML_MODELS_DISTRIBUTION.md",
    "docs/MODULES.md",
    "docs/PREMIUM_STOP_ANALYSIS_ARCHITECTURE.md",
    "docs/SYSTEM_OVERVIEW.md",
    "docs/TZ_AI_Extended_Testing.md",
    
]

ALWAYS_INCLUDE = sorted(set(ALWAYS_INCLUDE))

for always_path in ALWAYS_INCLUDE:
    if always_path not in INCLUDE:
        INCLUDE.append(always_path)

def should_exclude(path_str):
    """Проверяет нужно ли исключить путь"""
    import fnmatch
    
    normalized_path = path_str.replace('\\', '/')

    # ✅ Абсолютный приоритет: если файл в списке ALWAYS_INCLUDE — никогда не исключаем
    for include_path in ALWAYS_INCLUDE:
        include_norm = include_path.replace('\\', '/')
        if normalized_path.endswith(include_norm):
            return False

    # ✅ ПЕРВЫМ ДЕЛОМ: Проверяем исключения для .pyc файлов лицензирования
    # Эти файлы НУЖНЫ в публичной версии, поэтому не исключаем их
    for include_pyc in INCLUDE_PYC:
        if path_str == include_pyc or path_str.replace('\\', '/') == include_pyc.replace('\\', '/'):
            return False  # НЕ исключаем эти файлы!
    
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
# Дальше копируем файлы
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
                
                # Нормализуем путь для сравнения (Windows/Linux совместимость)
                rel_path_str = str(rel_path).replace('\\', '/')
                
                if should_exclude(rel_path_str):
                    continue
                
                dst_file = PUBLIC / rel_path
                if sync_file(src_file, dst_file):
                    copied += 1

# ✅ Отдельно копируем файлы из ALWAYS_INCLUDE (могут быть в исключенных папках, например data/)
print()
print("[INFO] Копирование обязательных файлов из ALWAYS_INCLUDE...")
for always_path in ALWAYS_INCLUDE:
    src = ROOT / always_path
    if src.exists() and src.is_file():
        # Проверяем, не был ли уже скопирован в основном цикле
        dst = PUBLIC / always_path
        if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            if sync_file(src, dst):
                copied += 1
                print(f"[COPY] {always_path}")

print()
print(f"[OK] Скопировано файлов: {copied}")
print("[DONE] Синхронизация завершена")

