"""
Получение уникального ID оборудования для привязки лицензии
"""

import platform
import hashlib
import subprocess
import uuid
import logging

logger = logging.getLogger('HardwareID')


def _is_random_mac(mac: str) -> bool:
    """
    Проверяет, является ли MAC адрес случайным/генерируемым
    
    Случайные MAC адреса Windows обычно имеют паттерны:
    - ef:bf:ff:ff:fe:XX (Windows 10/11 случайные адреса)
    - 00:00:00:00:00:00 (недоступный адрес)
    - XX:XX:XX:XX:XX:XX где второй байт имеет бит локального администрирования
    
    Args:
        mac: MAC адрес в формате XX:XX:XX:XX:XX:XX
        
    Returns:
        True если MAC адрес выглядит как случайный
    """
    if not mac or mac == '00:00:00:00:00:00':
        return True
    
    parts = mac.split(':')
    if len(parts) != 6:
        return True
    
    # Windows 10/11 случайные MAC адреса часто начинаются с ef:bf
    if mac.startswith('ef:bf:ff:ff:fe:'):
        return True
    
    # Проверяем бит локального администрирования (второй символ первого байта)
    # Если второй символ четный (0, 2, 4, 6, 8, A, C, E) - это глобальный адрес
    # Если нечетный (1, 3, 5, 7, 9, B, D, F) - это локально управляемый (может быть случайным)
    try:
        first_byte_second_char = parts[0][1].lower()
        if first_byte_second_char in '13579bdf':
            # Локально управляемый адрес - вероятно случайный
            # Но некоторые производители тоже используют локально управляемые адреса
            # Поэтому дополнительно проверяем паттерны
            if mac.startswith(('02:', '06:', '0a:', '0e:', '12:', '16:', '1a:', '1e:')):
                # Эти префиксы часто используются производителями
                return False
            # Если содержит много ff или паттерны случайных адресов
            if 'ff:ff' in mac or mac.count('ff') >= 2:
                return True
    except:
        pass
    
    return False


def get_hardware_id() -> str:
    """
    Получает уникальный ID оборудования
    
    Использует ТОЛЬКО стабильные параметры оборудования, которые не меняются
    после перезагрузки системы:
    
    Windows:
    - CPU ID (серийный номер процессора)
    - Disk Serial (серийный номер диска)
    - Motherboard Serial (серийный номер материнской платы)
    - Платформа
    
    Linux:
    - Machine ID (из /etc/machine-id)
    - CPU Serial (если доступен)
    - DMI Serial (если доступен)
    - Платформа
    
    НЕ использует:
    - MAC адрес (может быть случайным на миниПК)
    - Hostname/UUID (может меняться)
    
    Returns:
        SHA256 хэш комбинации стабильных параметров
    """
    components = []
    
    try:
        # 1. Платформа (стабильный параметр)
        try:
            platform_info = f"{platform.system()}-{platform.machine()}"
            components.append(f"PLATFORM:{platform_info}")
            # Убрано: logger.debug(f"Платформа: {platform_info}") - слишком шумно
        except Exception as e:
            logger.warning(f"Не удалось получить платформу: {e}")
        
        # 2. Специфичные для Windows данные
        if platform.system() == 'Windows':
            # Серийный номер процессора (СТАБИЛЬНЫЙ)
            try:
                result = subprocess.check_output(
                    'wmic cpu get processorid',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                
                cpu_id = result.split('\n')[1].strip() if '\n' in result else result.strip()
                if cpu_id and cpu_id != 'ProcessorId':
                    components.append(f"CPU:{cpu_id}")
                    # Убрано: logger.debug(f"CPU ID получен: {cpu_id[:16]}...") - слишком шумно
                else:
                    logger.warning("CPU ID не найден")
            except Exception as e:
                logger.warning(f"Не удалось получить CPU ID: {e}")
            
            # Серийный номер диска (СТАБИЛЬНЫЙ)
            try:
                result = subprocess.check_output(
                    'wmic diskdrive get serialnumber',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                
                disk_serial = result.split('\n')[1].strip() if '\n' in result else result.strip()
                if disk_serial and disk_serial != 'SerialNumber' and disk_serial.strip():
                    components.append(f"DISK:{disk_serial}")
                    # Убрано: logger.debug(f"Disk serial получен: {disk_serial[:20]}...") - слишком шумно
                else:
                    logger.warning("Disk serial не найден")
            except Exception as e:
                logger.warning(f"Не удалось получить Disk serial: {e}")
            
            # Серийный номер материнской платы (СТАБИЛЬНЫЙ, даже если "Default string")
            try:
                result = subprocess.check_output(
                    'wmic baseboard get serialnumber',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                
                board_serial = result.split('\n')[1].strip() if '\n' in result else result.strip()
                if board_serial and board_serial != 'SerialNumber' and board_serial.strip():
                    # Даже если это "Default string", используем его - он уникален для устройства
                    components.append(f"BOARD:{board_serial}")
                    # Убрано: logger.debug(f"Motherboard serial получен: {board_serial[:20]}...") - слишком шумно
            except Exception as e:
                logger.warning(f"Не удалось получить Motherboard serial: {e}")
            
            # ВАЖНО: MAC адреса на Windows часто случайные/виртуальные (особенно на мини-ПК)
            # Чтобы HWID не менялся после перезагрузки, полностью игнорируем MAC адрес
            pass
        
        # 3. Специфичные для Linux данные
        elif platform.system() == 'Linux':
            # Machine ID (СТАБИЛЬНЫЙ)
            try:
                with open('/etc/machine-id', 'r') as f:
                    machine_id = f.read().strip()
                    if machine_id:
                        components.append(f"MACHINE_ID:{machine_id}")
                        pass
            except Exception as e:
                logger.warning(f"Не удалось получить Machine ID: {e}")
            
            # CPU Serial (СТАБИЛЬНЫЙ, если доступен)
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    for line in cpuinfo.split('\n'):
                        if 'Serial' in line and ':' in line:
                            cpu_serial = line.split(':')[1].strip()
                            if cpu_serial and cpu_serial != '0000000000000000':
                                components.append(f"CPU_SERIAL:{cpu_serial}")
                                pass
                                break
            except Exception as e:
                pass
            
            # DMI Product Serial (СТАБИЛЬНЫЙ, если доступен)
            try:
                result = subprocess.check_output(
                    ['cat', '/sys/class/dmi/id/product_serial'],
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                if result and result != 'Not Specified' and result.strip():
                    components.append(f"DMI_SERIAL:{result}")
                    pass
            except:
                pass
        
        # Если ничего не получилось, используем fallback на основе CPU + Disk
        if not components or len(components) == 1:  # Только PLATFORM
            logger.warning("Недостаточно стабильных компонентов для HWID")
            # Пытаемся получить хотя бы CPU и Disk
            fallback_components = []
            if platform.system() == 'Windows':
                try:
                    result = subprocess.check_output(
                        'wmic cpu get processorid',
                        shell=True,
                        stderr=subprocess.DEVNULL
                    ).decode().strip()
                    cpu_id = result.split('\n')[1].strip() if '\n' in result else result.strip()
                    if cpu_id and cpu_id != 'ProcessorId':
                        fallback_components.append(f"CPU:{cpu_id}")
                except:
                    pass
                
                try:
                    result = subprocess.check_output(
                        'wmic diskdrive get serialnumber',
                        shell=True,
                        stderr=subprocess.DEVNULL
                    ).decode().strip()
                    disk_serial = result.split('\n')[1].strip() if '\n' in result else result.strip()
                    if disk_serial and disk_serial != 'SerialNumber':
                        fallback_components.append(f"DISK:{disk_serial}")
                except:
                    pass
            
            if fallback_components:
                components.extend(fallback_components)
                logger.warning(f"Использованы fallback компоненты: {fallback_components}")
            else:
                # Последний резерв - используем hostname (но это нестабильно!)
                fallback = f"FALLBACK:{platform.node()}"
                components.append(fallback)
                logger.warning(f"Используется нестабильный fallback: {fallback}")
        
        # Комбинируем и хэшируем
        combined = '|'.join(components)
        hardware_id = hashlib.sha256(combined.encode()).hexdigest()
        
        # Убрано: logger.info - не должно попадать в логи ai.py
        # Убрано: logger.debug(f"Компоненты: {combined}") - слишком шумно
        return hardware_id
    
    except Exception as e:
        logger.error(f"Критическая ошибка получения hardware ID: {e}")
        # Fallback - используем CPU ID если доступен
        if platform.system() == 'Windows':
            try:
                result = subprocess.check_output(
                    'wmic cpu get processorid',
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                cpu_id = result.split('\n')[1].strip() if '\n' in result else result.strip()
                if cpu_id and cpu_id != 'ProcessorId':
                    fallback = hashlib.sha256(f"CPU:{cpu_id}".encode()).hexdigest()
                    logger.warning(f"Используется критический fallback на основе CPU ID")
                    return fallback
            except:
                pass
        
        # Последний резерв - hostname (нестабильно!)
        fallback = hashlib.sha256(platform.node().encode()).hexdigest()
        logger.warning(f"Используется нестабильный fallback hardware ID")
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

