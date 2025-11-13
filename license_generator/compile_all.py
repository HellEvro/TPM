"""
Скрипт для компиляции всех модулей лицензирования в .pyc
"""

import sys
from pathlib import Path

# Добавляем текущую директорию в путь
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

def compile_all():
    """Компилирует все модули лицензирования"""
    
    print("=" * 60)
    print("COMPILING ALL LICENSE MODULES")
    print("=" * 60)
    print()
    
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
    success = compile_all()
    sys.exit(0 if success else 1)

