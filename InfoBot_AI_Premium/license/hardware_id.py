"""
Получение уникального ID оборудования для привязки лицензии
"""

import platform
import hashlib
import subprocess
import uuid
import logging

logger = logging.getLogger('HardwareID')


def get_hardware_id() -> str:
    """
    Получает уникальный ID оборудования
    
    Комбинирует несколько параметров для создания уникального ID:
    - MAC адрес сетевой карты
    - UUID машины
    - Серийный номер процессора (Windows)
    - Серийный номер диска (Windows)
    
    Returns:
        SHA256 хэш комбинации параметров
    """
    components = []
    
    try:
        # 1. MAC адрес
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                           for elements in range(0, 2*6, 2)][::-1])
            components.append(f"MAC:{mac}")
            logger.debug(f"MAC адрес получен: {mac}")
        except Exception as e:
            logger.warning(f"Не удалось получить MAC адрес: {e}")
        
        # 2. UUID машины
        try:
            machine_uuid = str(uuid.uuid1())
            components.append(f"UUID:{machine_uuid}")
            logger.debug(f"UUID машины получен")
        except Exception as e:
            logger.warning(f"Не удалось получить UUID: {e}")
        
        # 3. Платформа
        try:
            platform_info = f"{platform.system()}-{platform.machine()}"
            components.append(f"PLATFORM:{platform_info}")
            logger.debug(f"Платформа: {platform_info}")
        except Exception as e:
            logger.warning(f"Не удалось получить платформу: {e}")
        
        # 4. Специфичные для Windows данные
        if platform.system() == 'Windows':
            # Серийный номер процессора
            try:
                result = subprocess.check_output(
                    'wmic cpu get processorid',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                
                cpu_id = result.split('\n')[1].strip() if '\n' in result else result.strip()
                if cpu_id and cpu_id != 'ProcessorId':
                    components.append(f"CPU:{cpu_id}")
                    logger.debug(f"CPU ID получен")
            except Exception as e:
                logger.warning(f"Не удалось получить CPU ID: {e}")
            
            # Серийный номер диска
            try:
                result = subprocess.check_output(
                    'wmic diskdrive get serialnumber',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                
                disk_serial = result.split('\n')[1].strip() if '\n' in result else result.strip()
                if disk_serial and disk_serial != 'SerialNumber':
                    components.append(f"DISK:{disk_serial}")
                    logger.debug(f"Disk serial получен")
            except Exception as e:
                logger.warning(f"Не удалось получить Disk serial: {e}")
        
        # 5. Специфичные для Linux данные
        elif platform.system() == 'Linux':
            # Machine ID
            try:
                with open('/etc/machine-id', 'r') as f:
                    machine_id = f.read().strip()
                    components.append(f"MACHINE_ID:{machine_id}")
                    logger.debug(f"Machine ID получен")
            except Exception as e:
                logger.warning(f"Не удалось получить Machine ID: {e}")
        
        # Если ничего не получилось, используем fallback
        if not components:
            logger.warning("Не удалось получить компоненты hardware ID, используем fallback")
            components.append(f"FALLBACK:{platform.node()}")
        
        # Комбинируем и хэшируем
        combined = '|'.join(components)
        hardware_id = hashlib.sha256(combined.encode()).hexdigest()
        
        logger.info(f"Hardware ID сгенерирован: {hardware_id[:16]}...")
        return hardware_id
    
    except Exception as e:
        logger.error(f"Критическая ошибка получения hardware ID: {e}")
        # Fallback - используем просто hostname
        fallback = hashlib.sha256(platform.node().encode()).hexdigest()
        logger.warning(f"Используется fallback hardware ID")
        return fallback


def get_short_hardware_id() -> str:
    """
    Получает короткий hardware ID (первые 16 символов)
    
    Удобно для отображения пользователю
    
    Returns:
        Первые 16 символов hardware ID
    """
    full_id = get_hardware_id()
    return full_id[:16].upper()


if __name__ == '__main__':
    # Тест
    print("=" * 60)
    print("HARDWARE ID TEST")
    print("=" * 60)
    print()
    
    full_id = get_hardware_id()
    short_id = get_short_hardware_id()
    
    print(f"Full Hardware ID: {full_id}")
    print(f"Short Hardware ID: {short_id}")
    print()
    
    print("This ID will be used for license binding")
    print()

