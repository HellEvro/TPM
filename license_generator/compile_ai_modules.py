"""
Скрипт для компиляции всех AI модулей в .pyc
Защищает исходный код AI от копирования
"""

import os
import sys
import py_compile
import shutil
from pathlib import Path

# Список AI модулей для компиляции
AI_MODULES = [
    "smart_money_features.py",
    "lstm_predictor.py",
    "transformer_predictor.py",
    "bayesian_optimizer.py",
    "drift_detector.py",
    "ensemble.py",
    "monitoring.py",
    "rl_agent.py",
    "sentiment.py",
    "pattern_detector.py",
    "ai_integration.py",
]


def compile_ai_modules():
    """Компилирует все AI модули в .pyc"""
    
    print("=" * 60)
    print("COMPILING AI MODULES")
    print("=" * 60)
    print()
    
    # Определяем пути
    project_root = Path(__file__).parent.parent
    ai_dir = project_root / 'bot_engine' / 'ai'
    
    # Определяем целевую директорию на основе версии Python
    python_version = sys.version_info[:2]
    
    if python_version >= (3, 14):
        target_dir = ai_dir / 'pyc_314'
        version_name = "3.14+"
    elif python_version == (3, 12):
        target_dir = ai_dir / 'pyc_312'
        version_name = "3.12"
    else:
        target_dir = ai_dir / f'pyc_{python_version[0]}{python_version[1]}'
        version_name = f"{python_version[0]}.{python_version[1]}"
    
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Компиляция для Python {version_name}")
    print(f"[INFO] Целевая директория: {target_dir}")
    print()
    
    results = []
    
    for module_name in AI_MODULES:
        source_file = ai_dir / module_name
        
        if not source_file.exists():
            print(f"[SKIP] {module_name} - файл не найден")
            results.append((module_name, False, "not found"))
            continue
        
        print(f"[...] Компиляция {module_name}...")
        
        # Временный файл в целевой директории
        temp_file = target_dir / module_name
        
        try:
            # Копируем исходник
            shutil.copy2(source_file, temp_file)
            
            # Компилируем
            py_compile.compile(
                str(temp_file),
                doraise=True,
                optimize=2  # Максимальная оптимизация (удаляет docstrings и assert)
            )
            
            # Ищем скомпилированный файл
            base_name = module_name.replace('.py', '')
            compiled_patterns = [
                f'{base_name}.cpython-{sys.version_info.major}{sys.version_info.minor}.opt-2.pyc',
                f'{base_name}.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc',
            ]
            
            compiled_file = None
            cache_dir = target_dir / '__pycache__'
            
            for pattern in compiled_patterns:
                candidate = cache_dir / pattern
                if candidate.exists():
                    compiled_file = candidate
                    break
            
            if compiled_file and compiled_file.exists():
                # Копируем как module.pyc
                target_pyc = target_dir / f'{base_name}.pyc'
                shutil.copy2(compiled_file, target_pyc)
                print(f"[OK] {module_name} -> {target_pyc.name}")
                results.append((module_name, True, str(target_pyc)))
            else:
                print(f"[ERROR] {module_name} - compiled file not found")
                results.append((module_name, False, "pyc not found"))
                
        except Exception as e:
            print(f"[ERROR] {module_name} - {e}")
            results.append((module_name, False, str(e)))
            
        finally:
            # Удаляем временный .py файл
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
    # Удаляем __pycache__
    cache_dir = target_dir / '__pycache__'
    if cache_dir.exists():
        try:
            shutil.rmtree(cache_dir)
        except:
            pass
    
    # Итоги
    print()
    print("=" * 60)
    print(f"COMPILATION SUMMARY FOR PYTHON {version_name}")
    print("=" * 60)
    
    success_count = sum(1 for _, ok, _ in results if ok)
    fail_count = len(results) - success_count
    
    for name, ok, info in results:
        status = "[OK]" if ok else "[FAILED]"
        print(f"{status} {name}")
    
    print()
    print(f"Success: {success_count}, Failed: {fail_count}")
    print("=" * 60)
    
    return fail_count == 0


if __name__ == '__main__':
    # Переходим в корень проекта
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    success = compile_ai_modules()
    sys.exit(0 if success else 1)
