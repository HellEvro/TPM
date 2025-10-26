"""
КРИТИЧЕСКИЙ модуль проверки лицензий
ВОТ ЭТОТ ФАЙЛ БУДЕТ СКОМПИЛИРОВАН В .pyd!
Не содержит отладочной информации
"""

import os
import json
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
import hmac
import hashlib

class LicenseChecker:
    """Встроенный проверщик лицензий"""
    
    def __init__(self):
        self._license_valid = False
        self._license_info = None
    
    def check_license(self, project_root: Path):
        """Проверяет наличие и валидность лицензии"""
        lic_files = [f for f in os.listdir(project_root) if f.endswith('.lic')]
        
        if not lic_files:
            return False, None
        
        # Читаем первый .lic файл
        lic_file = project_root / lic_files[0]
        
        try:
            # Расшифровка лицензии
            with open(lic_file, 'rb') as f:
                d = f.read()
            
            # Ключи (запутаны)
            k1 = 'InfoBot' + 'AI2024'
            k2 = 'Premium' + 'License'
            k3 = 'Key_SECRET'
            sk = (k1 + k2 + k3 + '_DO_NOT_SHARE').encode()[:32]
            x = urlsafe_b64encode(sk)
            cf = Fernet(x)
            
            # Расшифровка
            dec = cf.decrypt(d)
            ld = json.loads(dec.decode())
            
            # Проверка подписи
            sk2 = 'SECRET' + '_SIGNATURE_' + 'KEY_2024_PREMIUM'
            dtv = json.dumps({k:v for k,v in ld.items() if k != 'signature'}, sort_keys=True)
            es = hmac.new(sk2.encode(), dtv.encode(), hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(ld.get('signature', ''), es):
                return False, None
            
            # Проверка срока
            ea = datetime.fromisoformat(ld['expires_at'])
            if datetime.now() > ea:
                return False, None
            
            self._license_valid = True
            self._license_info = ld
            return True, ld
            
        except Exception:
            return False, None
    
    def is_valid(self):
        return self._license_valid
    
    def get_info(self):
        return self._license_info

