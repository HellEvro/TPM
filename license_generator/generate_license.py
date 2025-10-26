#!/usr/bin/env python3
"""
Генератор лицензий для InfoBot AI Premium
ВАЖНО: Эта папка НЕ попадает в публичную версию!
"""

import sys
from pathlib import Path
from datetime import datetime

# Добавляем путь к license_generator для импортов
import os
sys.path.insert(0, os.path.dirname(__file__))

from license_manager import LicenseManager

def generate_license(hw_id: str, days: int):
    """
    Генерирует лицензию
    
    Args:
        hw_id: Hardware ID клиента
        days: Количество дней действия
    """
    print("=" * 60)
    print("LICENSE GENERATOR")
    print("=" * 60)
    print()
    print(f"HWID: {hw_id}")
    print(f"Duration: {days} days")
    print()
    
    manager = LicenseManager()
    
    # Генерируем лицензию
    license_data = manager.generate_license(
        user_email='customer@example.com',
        license_type='premium',
        hardware_id=hw_id,
        custom_duration_days=days
    )
    
    # Сохраняем
    output_dir = Path('generated_licenses')
    output_dir.mkdir(exist_ok=True)
    
    filename = f"{hw_id}_{days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.lic"
    license_path = output_dir / filename
    
    with open(license_path, 'wb') as f:
        f.write(license_data['encrypted_license'])
    
    print(f"[OK] License saved: {license_path}")
    print()
    print("=" * 60)
    print("LICENSE GENERATED")
    print("=" * 60)
    print(f"Hardware ID:    {hw_id}")
    print(f"Duration:       {days} days")
    print(f"Expires:        {license_data['license_data']['expires_at']}")
    print()
    print(f"License file:   {license_path}")
    print("=" * 60)
    print()
    print("Send this .lic file to customer!")
    print(f"File: {license_path}")
    print()

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python generate_license.py <HWID> <DAYS>")
        sys.exit(1)
    
    hw_id = sys.argv[1]
    days = int(sys.argv[2])
    
    generate_license(hw_id, days)

