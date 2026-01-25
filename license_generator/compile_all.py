"""
Скрипт для компиляции всех модулей лицензирования в .pyc
Поддерживает компиляцию для Python 3.14 и 3.12
"""

import sys
import subprocess
import os
from pathlib import Path

# Добавляем текущую директорию в путь
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

def get_python_version(python_cmd):
    """Получает версию Python из команды"""
    try:
        result = subprocess.run(
            python_cmd.split() + ['--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_str = result.stdout.strip()
            # Парсим версию (например, "Python 3.14.2")
            import re
            match = re.search(r'(\d+)\.(\d+)', version_str)
            if match:
                return (int(match.group(1)), int(match.group(2)))
    except:
        pass
    return None

def get_python312():
    """Пытается найти Python 3.12"""
    import platform
    import os
    
    # Сначала проверяем .venv_gpu (если он существует, там должен быть Python 3.12)
    venv_gpu_path = project_root / '.venv_gpu'
    if venv_gpu_path.exists():
        if platform.system() == 'Windows':
            venv_python = venv_gpu_path / 'Scripts' / 'python.exe'
        else:
            venv_python = venv_gpu_path / 'bin' / 'python'
        
        if venv_python.exists():
            try:
                result = subprocess.run(
                    [str(venv_python), '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and '3.12' in (result.stdout or '') + (result.stderr or ''):
                    return str(venv_python)
            except:
                pass
    
    # На Windows пробуем py -3.12
    if platform.system() == 'Windows':
        try:
            result = subprocess.run(
                ['py', '-3.12', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and '3.12' in (result.stdout or '') + (result.stderr or ''):
                return 'py -3.12'
        except:
            pass
    
    # Пробуем другие варианты
    for cmd in ['python3.12', 'python312', 'python']:
        try:
            version = get_python_version(cmd)
            if version and version == (3, 12):
                return cmd
        except:
            continue
    return None

def get_python314():
    """Пытается найти Python 3.14"""
    for cmd in ['py -3.14', 'python3.14', 'python314', 'python']:
        try:
            version = get_python_version(cmd)
            if version and version >= (3, 14):
                return cmd.split()[0] if ' ' not in cmd else cmd
        except:
            continue
    return None

def compile_all_for_version(python_cmd=None):
    """Компилирует все модули лицензирования для текущей версии Python"""
    
    current_version = sys.version_info[:2]
    version_name = f"{current_version[0]}.{current_version[1]}"
    
    print("=" * 60)
    print(f"COMPILING ALL LICENSE MODULES FOR PYTHON {version_name}")
    if python_cmd:
        print(f"Using: {python_cmd}")
    print("=" * 60)
    print()
    
    results = []
    
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
    print(f"COMPILATION SUMMARY FOR PYTHON {version_name}")
    print("=" * 60)
    
    all_success = True
    for name, success in results:
        status = "[OK]" if success else "[FAILED]"
        print(f"{status} {name}")
        if not success:
            all_success = False
    
    print("=" * 60)
    
    return all_success

def compile_all_both_versions():
    """Компилирует все модули для обеих версий Python (3.14 и 3.12)"""
    
    print("=" * 80)
    print("COMPILING ALL LICENSE MODULES FOR BOTH PYTHON VERSIONS (3.14 and 3.12)")
    print("=" * 80)
    print()
    
    script_path = Path(__file__).resolve()
    all_success = True
    
    # Компилируем для Python 3.14
    print("\n" + "=" * 80)
    print("COMPILING FOR PYTHON 3.14")
    print("=" * 80)
    python314 = get_python314()
    if python314:
        print(f"[INFO] Found Python 3.14: {python314}")
        result = subprocess.run(
            python314.split() + [str(script_path), '--version-only'],
            cwd=project_root
        )
        if result.returncode != 0:
            all_success = False
            print("[ERROR] Failed to compile for Python 3.14")
    else:
        print("[WARNING] Python 3.14 not found, skipping compilation for Python 3.14")
        all_success = False
    
    # Компилируем для Python 3.12
    print("\n" + "=" * 80)
    print("COMPILING FOR PYTHON 3.12")
    print("=" * 80)
    python312 = get_python312()
    if python312:
        print(f"[INFO] Found Python 3.12: {python312}")
        # Правильно обрабатываем команду 'py -3.12'
        if python312.startswith('py '):
            cmd = python312.split() + [str(script_path), '--version-only']
        else:
            cmd = [python312, str(script_path), '--version-only']
        
        result = subprocess.run(
            cmd,
            cwd=project_root
        )
        if result.returncode != 0:
            all_success = False
            print("[ERROR] Failed to compile for Python 3.12")
    else:
        print("[WARNING] Python 3.12 not found, skipping compilation for Python 3.12")
        print("[INFO] Попробуйте установить Python 3.12 или запустите компиляцию вручную:")
        print("   py -3.12 license_generator/compile_all.py --version-only")
        all_success = False
    
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    
    if all_success:
        print("[OK] All modules compiled successfully for both Python versions!")
    else:
        print("[WARNING] Some modules failed to compile for one or both Python versions!")
    
    return all_success

if __name__ == '__main__':
    os.chdir(project_root)
    
    # Проверяем аргументы командной строки
    version_only = '--version-only' in sys.argv
    both_versions = '--both' in sys.argv or '--all' in sys.argv
    
    if both_versions or (not version_only and len(sys.argv) == 1):
        # По умолчанию компилируем для обеих версий
        success = compile_all_both_versions()
    else:
        # Компилируем только для текущей версии Python
        success = compile_all_for_version()
    
    sys.exit(0 if success else 1)

