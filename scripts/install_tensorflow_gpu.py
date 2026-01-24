#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматической установки TensorFlow с поддержкой GPU
Проверяет наличие GPU и устанавливает правильную версию TensorFlow
"""

import subprocess
import sys
import os

def check_gpu():
    """Проверяет наличие NVIDIA GPU в системе"""
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return False

def check_tensorflow():
    """Проверяет установлен ли TensorFlow"""
    try:
        import tensorflow as tf
        return True, tf.__version__
    except ImportError:
        return False, None

def check_cuda_support():
    """Проверяет, скомпилирован ли TensorFlow с поддержкой CUDA"""
    try:
        import tensorflow as tf
        return tf.test.is_built_with_cuda()
    except:
        return False

def install_tensorflow_gpu():
    """Устанавливает TensorFlow с поддержкой GPU"""
    print("=" * 80)
    print("УСТАНОВКА TENSORFLOW С ПОДДЕРЖКОЙ GPU")
    print("=" * 80)
    
    # Проверяем наличие GPU
    print("\n[1] Проверка GPU...")
    has_gpu = check_gpu()
    if has_gpu:
        print("✅ NVIDIA GPU обнаружен в системе")
    else:
        print("⚠️ NVIDIA GPU не обнаружен")
        response = input("Продолжить установку TensorFlow с GPU поддержкой? (y/n): ")
        if response.lower() != 'y':
            print("Установка отменена")
            return False
    
    # Проверяем текущую установку TensorFlow
    print("\n[2] Проверка текущей установки TensorFlow...")
    tf_installed, tf_version = check_tensorflow()
    if tf_installed:
        print(f"TensorFlow установлен: версия {tf_version}")
        cuda_support = check_cuda_support()
        if cuda_support:
            print("✅ TensorFlow уже скомпилирован с поддержкой CUDA")
            gpus = None
            try:
                import tensorflow as tf
                gpus = tf.config.list_physical_devices('GPU')
            except:
                pass
            if gpus:
                print(f"✅ GPU устройства обнаружены: {len(gpus)}")
                return True
            else:
                print("⚠️ GPU устройства не обнаружены TensorFlow")
                print("   Возможно, требуется установка CUDA библиотек")
        else:
            print("⚠️ TensorFlow установлен БЕЗ поддержки CUDA")
            response = input("Переустановить TensorFlow с поддержкой GPU? (y/n): ")
            if response.lower() != 'y':
                return False
            print("Удаление старой версии TensorFlow...")
            subprocess.run([sys.executable, '-m', 'pip', 'uninstall', 'tensorflow', '-y'], check=False)
    else:
        print("TensorFlow не установлен")
    
    # Устанавливаем TensorFlow с поддержкой GPU
    print("\n[3] Установка TensorFlow с поддержкой GPU...")
    print("Это может занять несколько минут...")
    
    try:
        # Пытаемся установить tensorflow[and-cuda]
        print("Установка: tensorflow[and-cuda]...")
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'tensorflow[and-cuda]'],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ TensorFlow с поддержкой GPU установлен успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Ошибка при установке tensorflow[and-cuda]: {e}")
        print("Пробуем установить базовый TensorFlow...")
        
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', 'tensorflow'],
                check=True
            )
            print("✅ TensorFlow установлен (базовая версия)")
            print("⚠️ Для использования GPU может потребоваться установка CUDA библиотек вручную")
            return True
        except subprocess.CalledProcessError as e2:
            print(f"❌ Ошибка установки TensorFlow: {e2}")
            return False

def verify_installation():
    """Проверяет установку TensorFlow и GPU"""
    print("\n[4] Проверка установки...")
    try:
        import tensorflow as tf
        print(f"✅ TensorFlow версия: {tf.__version__}")
        
        cuda_built = tf.test.is_built_with_cuda()
        print(f"CUDA поддержка: {'✅ Да' if cuda_built else '❌ Нет'}")
        
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            print(f"✅ Найдено GPU устройств: {len(gpus)}")
            for i, gpu in enumerate(gpus):
                print(f"   GPU {i}: {gpu.name}")
        else:
            print("⚠️ GPU устройства не найдены")
            if cuda_built:
                print("   TensorFlow скомпилирован с CUDA, но GPU не обнаружен")
                print("   Возможно, требуется установка CUDA библиотек:")
                print("   pip install nvidia-cudnn-cu12 nvidia-cublas-cu12 nvidia-cuda-runtime-cu12")
            else:
                print("   TensorFlow установлен без поддержки CUDA")
        
        return True
    except ImportError:
        print("❌ TensorFlow не установлен")
        return False

if __name__ == "__main__":
    success = install_tensorflow_gpu()
    if success:
        verify_installation()
        print("\n" + "=" * 80)
        print("УСТАНОВКА ЗАВЕРШЕНА")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("УСТАНОВКА НЕ ЗАВЕРШЕНА")
        print("=" * 80)
        sys.exit(1)
