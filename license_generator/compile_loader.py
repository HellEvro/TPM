"""
Скрипт для компиляции _premium_loader.py в .pyd файл
"""

import os
import sys
from pathlib import Path
import shutil

def compile_loader():
    """Компилирует _premium_loader в .pyd"""
    
    print("=" * 60)
    print("COMPILING PREMIUM LOADER")
    print("=" * 60)
    print()
    
    source_file = Path('source/_premium_loader_source.py')
    if not source_file.exists():
        print("[ERROR] Source file not found!")
        return False
    
    # Копируем в рабочую директорию
    work_dir = Path('build_temp')
    work_dir.mkdir(exist_ok=True)
    
    target_file = work_dir / '_premium_loader.py'
    shutil.copy2(source_file, target_file)
    
    print(f"[OK] Copied source to: {target_file}")
    print()
    
    # Компилируем через pyinstaller или cython
    try:
        import Cython
        print("[OK] Cython installed")
        
        # Используем setup.py для компиляции
        os.chdir(str(work_dir))
        
        # Запускаем компиляцию
        os.system('python -m Cython.Build build_ext --inplace _premium_loader.py')
        
        # Ищем скомпилированный файл
        compiled_file = work_dir / '_premium_loader.pyd'
        if compiled_file.exists():
            print(f"[OK] Compiled: {compiled_file}")
            
            # Копируем в корень проекта
            target = Path('../../bot_engine/ai/_premium_loader.pyd')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(compiled_file, target)
            print(f"[OK] Copied to: {target}")
            
            return True
        else:
            print("[ERROR] Compilation failed!")
            return False
            
    except ImportError:
        print("[ERROR] Cython not installed!")
        print("Install: pip install cython")
        return False

if __name__ == '__main__':
    compile_loader()

