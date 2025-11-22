"""
Менеджер лицензий для InfoBot AI Premium

Создание, проверка и управление лицензиями.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from typing import Tuple, Dict, Any
import logging

try:
    from .license_types import LicenseType, LicenseFeatures
    from .hardware_id import get_hardware_id
except ImportError:
    from license_types import LicenseType, LicenseFeatures
    from hardware_id import get_hardware_id

logger = logging.getLogger('LicenseManager')


class LicenseManager:
    """Управление лицензиями"""
    
    # КРИТИЧЕСКИ ВАЖНО: Ключ подписи (ДОЛЖЕН СОВПАДАТЬ С КЛЮЧОМ В ai_manager.py!)
    # Этот ключ использует ai_manager.py для проверки подписи:
    # sk2 = 'SECRET' + '_SIGNATURE_' + 'KEY_2024_PREMIUM' 
    # В ai_manager.py используется: 'SECRET' + '_SIGNATURE_' + 'KEY_2024_PREMIUM'
    SECRET_KEY = ('SECRET' + '_SIGNATURE_' + 'KEY_2024_PREMIUM').encode()
    
    def __init__(self, secret_key: bytes = None):
        """
        Инициализация менеджера лицензий
        
        Args:
            secret_key: Секретный ключ для подписи (если None, используется дефолтный)
        """
        self.secret_key = secret_key if secret_key else self.SECRET_KEY
        
        # КРИТИЧЕСКИ ВАЖНО: Используем фиксированный ключ шифрования!
        # Если менять ключ - старые лицензии не будут работать!
        # В production храните ключ в защищенном месте
        from base64 import urlsafe_b64encode
        
        # Фиксированный ключ шифрования (ДОЛЖЕН СОВПАДАТЬ С КЛЮЧОМ В ai_manager.py!)
        # Этот ключ использует ai_manager.py для расшифровки:
        # k1 = 'InfoBot' + 'AI2024'
        # k2 = 'Premium' + 'License'  
        # k3 = 'Key_SECRET'
        # sk = (k1 + k2 + k3 + '_DO_NOT_SHARE').encode()[:32]
        fixed_key_string = 'InfoBot' + 'AI2024' + 'Premium' + 'License' + 'Key_SECRET' + '_DO_NOT_SHARE'
        fixed_key_bytes = fixed_key_string.encode()[:32]
        self.encryption_key = urlsafe_b64encode(fixed_key_bytes)
        self.cipher = Fernet(self.encryption_key)
    
    def generate_license(self, 
                        user_email: str,
                        license_type: str,
                        hardware_id: str = None,
                        custom_duration_days: int = None,
                        start_date: datetime = None) -> Dict[str, Any]:
        """
        Генерирует новую лицензию
        
        Args:
            user_email: Email пользователя
            license_type: Тип лицензии (trial/monthly/yearly/lifetime/developer)
            hardware_id: ID оборудования (None = можно активировать на любом ПК)
            custom_duration_days: Кастомная длительность (если None, берется из типа)
            start_date: Дата начала лицензии (если None, используется текущая дата + 1 день)
        
        Returns:
            Словарь с данными лицензии и ключом активации
        """
        # Получаем возможности для типа лицензии
        features = LicenseFeatures.get_features(license_type)
        
        # Определяем длительность
        duration_days = custom_duration_days if custom_duration_days else features['duration_days']
        
        # Определяем дату начала
        if start_date is None:
            # Если дата начала не указана, используем текущую дату + 1 день
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            # Убеждаемся, что время установлено на 00:00:00
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Дата окончания: до 00:00:00 (N+1)-го дня
        # Если лицензия на N дней, то она действует до начала (N+1)-го дня
        expires_at = start_date + timedelta(days=duration_days + 1)
        expires_at = expires_at.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Создаем данные лицензии
        license_data = {
            'email': user_email,
            'type': license_type,
            'features': features,
            'issued_at': datetime.now().isoformat(),
            'expires_at': expires_at.isoformat(),
            'hardware_id': hardware_id,  # None = без привязки к железу
            'version': '1.0',
            'license_id': self._generate_license_id(user_email, license_type)
        }
        
        # Подписываем лицензию
        signature = self._sign_license(license_data)
        license_data['signature'] = signature
        
        # Шифруем лицензию
        encrypted_license = self._encrypt_license(license_data)
        
        # Генерируем ключ активации
        activation_key = self._generate_activation_key(user_email, license_type)
        
        return {
            'activation_key': activation_key,
            'encrypted_license': encrypted_license,
            'license_data': license_data
        }
    
    def verify_license(self, license_file_path: str) -> Tuple[bool, Any]:
        """
        Проверяет валидность лицензии
        
        Args:
            license_file_path: Путь к файлу лицензии
        
        Returns:
            (is_valid: bool, license_data: dict или error_message: str)
        """
        try:
            # Читаем файл лицензии
            with open(license_file_path, 'rb') as f:
                encrypted_license = f.read()
            
            # Расшифровываем
            license_data = self._decrypt_license(encrypted_license)
            
            # Проверяем подпись
            if not self._verify_signature(license_data):
                return False, "Invalid license signature (possible tampering)"
            
            # Проверяем срок действия
            expires_at = datetime.fromisoformat(license_data['expires_at'])
            if datetime.now() > expires_at:
                days_expired = (datetime.now() - expires_at).days
                return False, f"License expired {days_expired} days ago"
            
            # Проверяем привязку к железу (если есть)
            if license_data.get('hardware_id'):
                current_hw_id = get_hardware_id()
                license_hw_id = license_data['hardware_id']
                
                # Сравниваем только первые 16 символов для совместимости
                if current_hw_id[:16].upper() != license_hw_id[:16].upper():
                    return False, "License is bound to different hardware"
            
            logger.info(f"[License] ✅ Валидная лицензия: {license_data['type']}")
            return True, license_data
            
        except FileNotFoundError:
            return False, "License file not found"
        except Exception as e:
            return False, f"License verification failed: {str(e)}"
    
    def _sign_license(self, license_data: dict) -> str:
        """Создает цифровую подпись лицензии"""
        # Убираем signature перед подписью
        data_to_sign = {k: v for k, v in license_data.items() if k != 'signature'}
        data_string = json.dumps(data_to_sign, sort_keys=True)
        
        signature = hmac.new(
            self.secret_key,
            data_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _verify_signature(self, license_data: dict) -> bool:
        """Проверяет подпись лицензии"""
        stored_signature = license_data.get('signature')
        if not stored_signature:
            return False
        
        calculated_signature = self._sign_license(license_data)
        return hmac.compare_digest(stored_signature, calculated_signature)
    
    def _encrypt_license(self, license_data: dict) -> bytes:
        """Шифрует данные лицензии"""
        data_string = json.dumps(license_data)
        encrypted = self.cipher.encrypt(data_string.encode())
        return encrypted
    
    def _decrypt_license(self, encrypted_data: bytes) -> dict:
        """Расшифровывает данные лицензии"""
        decrypted = self.cipher.decrypt(encrypted_data)
        license_data = json.loads(decrypted.decode())
        return license_data
    
    def _generate_activation_key(self, email: str, license_type: str) -> str:
        """
        Генерирует ключ активации в формате XXXX-XXXX-XXXX-XXXX
        
        Args:
            email: Email пользователя
            license_type: Тип лицензии
        
        Returns:
            Ключ активации
        """
        # Комбинируем email + тип + время + случайная соль
        data = f"{email}-{license_type}-{time.time()}"
        hash_value = hashlib.sha256(data.encode()).hexdigest()
        
        # Берем первые 16 символов и форматируем
        key = hash_value[:16].upper()
        formatted_key = f"{key[0:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"
        
        return formatted_key
    
    def _generate_license_id(self, email: str, license_type: str) -> str:
        """Генерирует уникальный ID лицензии"""
        data = f"{email}-{license_type}-{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32].upper()


if __name__ == '__main__':
    # Тест генерации лицензии
    print("=" * 60)
    print("LICENSE MANAGER TEST")
    print("=" * 60)
    print()
    
    manager = LicenseManager()
    
    # Генерируем тестовую лицензию
    hw_id = get_hardware_id()
    
    license = manager.generate_license(
        user_email='test@example.com',
        license_type='developer',
        hardware_id=hw_id
    )
    
    print(f"Activation Key: {license['activation_key']}")
    print(f"License ID: {license['license_data']['license_id']}")
    print(f"Type: {license['license_data']['type']}")
    print(f"Expires: {license['license_data']['expires_at']}")
    print()
    
    # Сохраняем
    with open('test_license.lic', 'wb') as f:
        f.write(license['encrypted_license'])
    
    print("[OK] License saved to test_license.lic")
    print()
    
    # Проверяем
    is_valid, result = manager.verify_license('test_license.lic')
    
    if is_valid:
        print("[OK] License is VALID")
        print(f"Type: {result['type']}")
        print(f"Features: {result['features']}")
    else:
        print(f"[ERROR] License is INVALID: {result}")
    
    print()

