#!/usr/bin/env python3
"""
Генератор лицензий для InfoBot AI Premium
ВАЖНО: Эта папка НЕ попадает в публичную версию!
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Добавляем путь к license_generator для импортов
import os
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from license_manager import LicenseManager
from license_database import LicenseDatabase

def generate_license(hw_id: str, 
                    days: int, 
                    start_date: Optional[datetime] = None,
                    email: str = 'customer@example.com',
                    recipient: str = None,
                    comments: str = None,
                    save_to_db: bool = True,
                    verbose: bool = True) -> Dict[str, Any]:
    """
    Генерирует лицензию
    
    Args:
        hw_id: Hardware ID клиента (будет нормализован до 16 символов)
        days: Количество дней действия
        start_date: Дата начала лицензии (если None, используется текущая дата + 1 день)
        email: Email получателя (используется для генерации license_id, можно оставить дефолтным)
        recipient: Контактная информация получателя (email, telegram, и т.д.) - сохраняется в БД
        comments: Комментарии к лицензии
        save_to_db: Сохранять ли в базу данных
        verbose: Выводить ли информацию в консоль
    
    Returns:
        Словарь с информацией о лицензии:
        {
            'license_path': путь к файлу,
            'license_data': данные лицензии,
            'recipient_id': ID в базе данных (если сохранено)
        }
    """
    # Нормализуем HWID: берем только первые 16 символов для совместимости
    hw_id = hw_id.strip().upper()
    if len(hw_id) > 16:
        hw_id = hw_id[:16]
        if verbose:
            print(f"[INFO] HWID обрезан до 16 символов: {hw_id}")
    elif len(hw_id) < 16:
        if verbose:
            print(f"[WARNING] HWID короче 16 символов: {hw_id}")
    
    if verbose:
        print("=" * 60)
        print("LICENSE GENERATOR")
        print("=" * 60)
        print()
        print(f"HWID: {hw_id}")
        print(f"Duration: {days} days")
        if start_date:
            print(f"Start date: {start_date.strftime('%Y-%m-%d')}")
        print()
    
    manager = LicenseManager()
    
    # Генерируем лицензию
    license_data = manager.generate_license(
        user_email=email,
        license_type='premium',
        hardware_id=hw_id,
        custom_duration_days=days,
        start_date=start_date
    )
    
    # Сохраняем файл
    output_dir = script_dir / 'generated_licenses'
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{hw_id}_{days}days_{timestamp}.lic"
    license_path = output_dir / filename
    
    with open(license_path, 'wb') as f:
        f.write(license_data['encrypted_license'])
    
    # Вычисляем даты для базы данных
    if start_date is None:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    else:
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    end_date = start_date + timedelta(days=days + 1)
    end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    recipient_id = None
    if save_to_db:
        try:
            db = LicenseDatabase()
            recipient_id = db.add_recipient(
                hw_id=hw_id,
                days=days,
                start_date=start_date,
                end_date=end_date,
                recipient=recipient,
                comments=comments,
                license_file=str(license_path)
            )
        except Exception as e:
            if verbose:
                print(f"[WARNING] Не удалось сохранить в БД: {e}")
    
    if verbose:
        print(f"[OK] License saved: {license_path}")
        print()
        print("=" * 60)
        print("LICENSE GENERATED")
        print("=" * 60)
        print(f"Hardware ID:    {hw_id}")
        print(f"Duration:       {days} days")
        print(f"Start date:     {start_date.strftime('%Y-%m-%d')}")
        print(f"Expires:        {license_data['license_data']['expires_at']}")
        print()
        print(f"License file:   {license_path}")
        if recipient_id:
            print(f"Database ID:    {recipient_id}")
        print("=" * 60)
        print()
        print("Send this .lic file to customer!")
        print(f"File: {license_path}")
        print()
    
    return {
        'license_path': str(license_path),
        'license_data': license_data['license_data'],
        'recipient_id': recipient_id,
        'hw_id': hw_id,
        'days': days,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat()
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python generate_license.py <HWID> <DAYS> [START_DATE] [RECIPIENT] [COMMENTS]")
        print("  HWID: Hardware ID (будет обрезан до 16 символов)")
        print("  DAYS: Количество дней лицензии")
        print("  START_DATE: Дата начала (опционально, по умолчанию: завтра)")
        print("              Форматы: YYYY-MM-DD (2025-12-31) или DD.MM.YYYY (31.12.2025)")
        print("  RECIPIENT: Контактная информация получателя (опционально)")
        print("             Можно указать: email, telegram nickname, telegram ID, и т.д.")
        print("  COMMENTS: Комментарии (опционально)")
        print()
        print("Examples:")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30 31.12.2025")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 @telegram_user")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com 'Test license'")
        sys.exit(1)
    
    hw_id = sys.argv[1]
    days = int(sys.argv[2])
    
    # Опциональные параметры
    start_date = None
    if len(sys.argv) > 3 and sys.argv[3]:
        date_str = sys.argv[3]
        # Поддерживаем два формата: YYYY-MM-DD и DD.MM.YYYY
        for date_format in ['%Y-%m-%d', '%d.%m.%Y']:
            try:
                start_date = datetime.strptime(date_str, date_format)
                break
            except ValueError:
                continue
        
        if start_date is None:
            print(f"[ERROR] Неверный формат даты: {date_str}")
            print("Используйте формат YYYY-MM-DD (например: 2025-12-31) или DD.MM.YYYY (например: 31.12.2025)")
            sys.exit(1)
    
    recipient = sys.argv[4] if len(sys.argv) > 4 else None
    comments = sys.argv[5] if len(sys.argv) > 5 else None
    
    # Email для генерации license_id (можно оставить дефолтным)
    email = recipient if recipient and '@' in recipient else 'customer@example.com'
    
    result = generate_license(hw_id, days, start_date=start_date, email=email, recipient=recipient, comments=comments)
    
    # Возвращаем код выхода 0 при успехе
    sys.exit(0)

