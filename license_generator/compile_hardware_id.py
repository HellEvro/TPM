"""
Скрипт для компиляции hardware_id_source.py в .pyc
"""

import os
import sys
import py_compile
import shutil
from pathlib import Path

def compile_hardware_id():
    """Компилирует hardware_id_source.py в .pyc"""
    
    print("=" * 60)
    print("COMPILING HARDWARE ID")
    print("=" * 60)
    print()
    
    # Исходный файл
    source_file = Path('license_generator/source/hardware_id_source.py')
    if not source_file.exists():
        print(f"[ERROR] Source file not found: {source_file}")
        return False
    
    # Целевая директория для .pyc
    target_dir = Path('bot_engine/ai')
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Временный файл для компиляции (нужен для правильного пути модуля)
    temp_file = target_dir / 'hardware_id_source.py'
    
    # Копируем исходник во временный файл
    shutil.copy2(source_file, temp_file)
    print(f"[OK] Copied source to: {temp_file}")
    
    try:
        # Компилируем в .pyc
        py_compile.compile(
            str(temp_file),
            doraise=True,
            optimize=2  # Максимальная оптимизация
        )
        
        # Ищем скомпилированный файл
        compiled_file = target_dir / '__pycache__' / 'hardware_id_source.cpython-{}{}.opt-2.pyc'.format(
            sys.version_info.major, sys.version_info.minor
        )
        
        if not compiled_file.exists():
            # Пробуем без opt-2
            compiled_file = target_dir / '__pycache__' / 'hardware_id_source.cpython-{}{}.pyc'.format(
                sys.version_info.major, sys.version_info.minor
            )
        
        if compiled_file.exists():
            # Копируем как hardware_id_source.pyc в целевую директорию
            target_pyc = target_dir / 'hardware_id_source.pyc'
            shutil.copy2(compiled_file, target_pyc)
            print(f"[OK] Compiled: {target_pyc}")
            
            # Также копируем в scripts/hardware_id.pyc для activate_premium.py
            scripts_dir = Path('scripts')
            scripts_dir.mkdir(parents=True, exist_ok=True)
            scripts_pyc = scripts_dir / 'hardware_id.pyc'
            shutil.copy2(compiled_file, scripts_pyc)
            print(f"[OK] Also compiled: {scripts_pyc} (for activate_premium.py)")
            
            # Удаляем временный .py файл (оставляем только .pyc)
            if temp_file.exists():
                temp_file.unlink()
                print(f"[OK] Removed temporary .py file")
            
            # Удаляем __pycache__
            cache_dir = target_dir / '__pycache__'
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                print(f"[OK] Removed __pycache__")
            
            print()
            print("=" * 60)
            print("[OK] HARDWARE ID COMPILED SUCCESSFULLY")
            print("=" * 60)
            print()
            print(f"Source: {source_file}")
            print(f"Compiled: {target_pyc}")
            print(f"Also: {scripts_pyc} (for activate_premium.py)")
            print()
            
            return True
        else:
            print(f"[ERROR] Compiled file not found: {compiled_file}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Compilation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Удаляем временный файл если остался
        if temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass

if __name__ == '__main__':
    # Переходим в корень проекта
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    success = compile_hardware_id()
    sys.exit(0 if success else 1)

