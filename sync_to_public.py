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

# ✅ ПРОСТАЯ ЛОГИКА: ОДИН СПИСОК ЧТО НЕ КОПИРУЕТСЯ, ВСЁ ОСТАЛЬНОЕ КОПИРУЕТСЯ
EXCLUDE = [

    "README.md",
    "LICENSE.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "PULL_REQUEST_TEMPLATE.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CODE_OF_CONDUCT.md",
    "TODO.txt",
    "TODO.md",
    "TODO.txt",
    "TODO.md",
    "sync_to_public.py",
    "git_commit_gui.*",

    # Служебные папки
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    ".idea",
    ".vscode",
    "backups",
    "restored_cursor_sessions",  # Восстановленные сессии Cursor (большие файлы)
    
    # Внутренние папки (не для публики)
    "license_generator",  # Исходники генерации лицензий
    "data",  # Данные пользователей
    "logs",  # Логи
    
    # Внутренние подпапки scripts
    "scripts/fix",
    "scripts/check",
    
    # Внутренние подпапки docs
    "docs/ai_development",
    "docs/ai_technical",
    "docs/ai_guides",
    
    # Конфиденциальные файлы
    "app/keys.py",
    "app/config.py",
    "app/current_language.txt",
    "app/telegram_states.json",
    "launcher/.infobot_manager_state.json",
    
    # Тестовые и служебные скрипты (verify_pyc_files.py исключен через INCLUDE_ANYWAY)
    "scripts/test_*.py",
    
    # Скомпилированные файлы (кроме нужных)
    "*.pyc",
    
    # Документация разработки
    "docs/AI_README.md",
    "docs/LICENSE_SYSTEM.md",
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
    "docs/POSTGRES_MIGRATION_PLAN.md",  # Внутренний план миграции
    "docs/ML_MODELS_DISTRIBUTION.md",
    "docs/MODULES.md",
    "docs/PREMIUM_STOP_ANALYSIS_ARCHITECTURE.md",
    "docs/SYSTEM_OVERVIEW.md",
    "docs/TZ_AI_Extended_Testing.md",
    "docs/HWID_*.md",  # Все файлы про HWID (внутренние отчеты)
    
    # Служебные файлы
    ".cursorrules",
    
    # Генерируемые файлы
    "data/async_state.json",
    "data/bot_history.json",
    "data/process_state.json",
    "data/bots_state.json",
    "data/telegram_states.json",
    "logs/*.log",
    "license_generator/*.pyc",
]

# ✅ ИСКЛЮЧЕНИЯ: Файлы которые НУЖНЫ в публичной версии (даже если в EXCLUDE)
INCLUDE_ANYWAY = [
    # Старые .pyc файлы (обратная совместимость)
    "bot_engine/ai/license_checker.pyc",
    "bot_engine/ai/hardware_id_source.pyc",
    "bot_engine/ai/ai_manager.pyc",
    "bot_engine/ai/_ai_launcher.pyc",
    "scripts/hardware_id.pyc",
    # Версионированные .pyc файлы для Python 3.12+ (ВСЕ файлы из директорий)
    "bot_engine/ai/pyc_312/",
    "bot_engine/ai/pyc_314/",
    # Скрипт проверки .pyc файлов
    "scripts/verify_pyc_files.py",
    # Исходные Python файлы
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

def should_exclude(path_str):
    """Проверяет нужно ли исключить путь - ПРОСТАЯ ЛОГИКА"""
    import fnmatch
    
    normalized_path = path_str.replace('\\', '/')
    
    # ✅ ПЕРВЫЙ ПРИОРИТЕТ: Если файл в INCLUDE_ANYWAY - НИКОГДА не исключаем
    for include_path in INCLUDE_ANYWAY:
        include_norm = include_path.replace('\\', '/')
        # Точное совпадение
        if normalized_path == include_norm:
            return False
        # Если путь заканчивается на include_path
        if normalized_path.endswith('/' + include_norm):
            return False
        # Если include_path заканчивается на /, проверяем что путь начинается с него
        if include_norm.endswith('/') and normalized_path.startswith(include_norm):
            return False
    
    # ✅ Проверяем список исключений
    for exc in EXCLUDE:
        exc_norm = exc.replace('\\', '/')
        
        # Точное совпадение
        if normalized_path == exc_norm:
            return True
        
        # Проверка через fnmatch для паттернов
        if fnmatch.fnmatch(normalized_path, exc_norm) or fnmatch.fnmatch(os.path.basename(normalized_path), exc_norm):
            return True
        
        # Проверка, что путь начинается с исключаемой директории
        if normalized_path.startswith(exc_norm + '/') or normalized_path.startswith(exc_norm + '\\'):
            return True
    
    # ✅ ВСЁ ОСТАЛЬНОЕ КОПИРУЕТСЯ
    return False

def sync_file(src: Path, dst: Path):
    """Синхронизирует один файл"""
    try:
        if not dst.parent.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"Error copying {src}: {e}")
        return False

print("=" * 80)
print("СИНХРОНИЗАЦИЯ В ПУБЛИЧНУЮ ВЕРСИЮ")
print("=" * 80)
print()

# Копируем ВСЁ из корня проекта, кроме исключений
copied = 0
skipped = 0

# Обходим весь проект
for root, dirs, files in os.walk(ROOT):
    # Исключаем директории из обхода
    dirs[:] = [d for d in dirs if not should_exclude(os.path.join(root, d).replace(str(ROOT) + os.sep, '').replace('\\', '/'))]
    
    for file in files:
        src_file = Path(root) / file
        rel_path = src_file.relative_to(ROOT)
        rel_path_str = str(rel_path).replace('\\', '/')
        
        # Пропускаем .git
        if '.git' in rel_path_str:
            continue
        
        # Проверяем исключения
        if should_exclude(rel_path_str):
            skipped += 1
            continue
        
        # Копируем файл
        dst_file = PUBLIC / rel_path
        if sync_file(src_file, dst_file):
            copied += 1

print()
print(f"[OK] Скопировано файлов: {copied}")
print(f"[SKIP] Пропущено файлов: {skipped}")
print("[DONE] Синхронизация завершена")
