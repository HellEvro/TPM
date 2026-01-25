"""
Скрипт для компиляции всех модулей лицензирования в .pyc
Поддерживает Python 3.14
"""

import sys
import subprocess
import os
from pathlib import Path

# Добавляем текущую директорию в путь
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

def get_python314():
    """Пытается найти Python 3.14"""
    # Пробуем разные варианты
    for cmd in ['py -3.14', 'python3.14', 'python314', 'python']:
        try:
            result = subprocess.run(
                [cmd.split()[0]] + cmd.split()[1:] + ['--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and '3.14' in result.stdout:
                return cmd.split()[0] if ' ' not in cmd else cmd
        except:
            continue
    return None

def compile_all(use_python314=False):
    """Компилирует все модули лицензирования"""
    
    print("=" * 60)
    print("COMPILING ALL LICENSE MODULES")
    if use_python314:
        print("Using Python 3.14")
    else:
        print(f"Using Python {sys.version_info.major}.{sys.version_info.minor}")
    print("=" * 60)
    print()
    
    # Если нужно использовать Python 3.14, запускаем через subprocess
    if use_python314:
        python314 = get_python314()
        if not python314:
            print("[ERROR] Python 3.14 not found!")
            print("Please install Python 3.14 first")
            return False
        
        print(f"[INFO] Using Python 3.14: {python314}")
        # Запускаем этот же скрипт через Python 3.14
        script_path = Path(__file__).resolve()
        result = subprocess.run(
            python314.split() + [str(script_path), '--no-python314'],
            cwd=project_root
        )
        return result.returncode == 0
    
    results = []
    
    # Компилируем hardware_id_source
    print("1. Compiling hardware_id_source...")
    try:
        from license_generator.compile_hardware_id import compile_hardware_id
        success = compile_hardware_id()
        results.append(("hardware_id_source", success))
    except Exception as e:
        print(f"[ERROR] Failed to compile hardware_id_source: {e}")
        results.append(("hardware_id_source", False))
    
    print()
    
    # Компилируем license_checker
    print("2. Compiling license_checker...")
    try:
        from license_generator.compile_license_checker import compile_license_checker
        success = compile_license_checker()
        results.append(("license_checker", success))
    except Exception as e:
        print(f"[ERROR] Failed to compile license_checker: {e}")
        results.append(("license_checker", False))
    
    print()
    
    # Компилируем ai_manager
    print("3. Compiling ai_manager...")
    try:
        from license_generator.compile_ai_manager import compile_ai_manager
        success = compile_ai_manager()
        results.append(("ai_manager", success))
    except Exception as e:
        print(f"[ERROR] Failed to compile ai_manager: {e}")
        results.append(("ai_manager", False))
    
    print()
    
    # Компилируем _ai_launcher
    print("4. Compiling _ai_launcher...")
    try:
        from license_generator.build_ai_launcher import build_launcher
        build_launcher()
        results.append(("_ai_launcher", True))
    except Exception as e:
        print(f"[ERROR] Failed to compile _ai_launcher: {e}")
        results.append(("_ai_launcher", False))
    
    print()
    print("=" * 60)
    print("COMPILATION SUMMARY")
    print("=" * 60)
    
    all_success = True
    for name, success in results:
        status = "[OK]" if success else "[FAILED]"
        print(f"{status} {name}")
        if not success:
            all_success = False
    
    print("=" * 60)
    
    if all_success:
        print("[OK] All modules compiled successfully!")
    else:
        print("[ERROR] Some modules failed to compile!")
    
    return all_success

if __name__ == '__main__':
    import os
    os.chdir(project_root)
    
    # Проверяем аргументы командной строки
    use_python314 = '--python314' in sys.argv or '--py314' in sys.argv
    no_python314 = '--no-python314' in sys.argv
    
    if not no_python314 and use_python314:
        success = compile_all(use_python314=True)
    else:
        success = compile_all(use_python314=False)
    
    sys.exit(0 if success else 1)

