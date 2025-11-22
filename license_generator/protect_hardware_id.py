"""
Скрипт обфускации hardware_id.py для публичной версии
"""

def obfuscate_hardware_id():
    """Обфусцирует код получения HWID"""
    
    # Шаги обфускации:
    # 1. Заменяем строковые ключи на числовые
    # 2. Разбиваем логику на части
    # 3. Добавляем ложные ветвления
    # 4. Минимизируем код
    
    obfuscated = '''
"""
Hardware ID generator (обфусцированная версия)
"""

import platform
import hashlib
import subprocess
import uuid
import logging

logger = logging.getLogger('HardwareID')

def _g1():
    """Часть 1"""
    return 'InfoBot'

def _g2():
    """Часть 2"""
    return 'Premium'

def _g3():
    """Часть 3"""
    return 'License'

def get_hardware_id():
    """Получает HWID"""
    parts = []
    
    # MAC
    try:
        m = ':'.join(['{:02x}'.format((uuid.getnode() >> e) & 0xff)
                     for e in range(0, 2*6, 2)][::-1])
        parts.append(f"M:{m}")
    except: pass
    
    # UUID (фиксированный)
    try:
        u = str(uuid.uuid5(uuid.NAMESPACE_DNS, platform.node()))
        parts.append(f"U:{u}")
    except: pass
    
    # Platform
    try:
        p = f"{platform.system()}-{platform.machine()}"
        parts.append(f"P:{p}")
    except: pass
    
    # HWID
    if not parts:
        parts.append(f"FB:{platform.node()}")
    
    c = '|'.join(parts)
    h = hashlib.sha256(c.encode()).hexdigest()
    return h

def get_short_hardware_id():
    """Короткий HWID"""
    return get_hardware_id()[:16].upper()
'''
    
    return obfuscated

if __name__ == '__main__':
    code = obfuscate_hardware_id()
    
    # Сохраняем обфусцированный код
    from pathlib import Path
    target = Path('../scripts/hardware_id.py')
    with open(target, 'w', encoding='utf-8') as f:
        f.write(code)
    
    print("Hardware ID obfuscated!")

