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

def generate_license(hw_id: Optional[str] = None, 
                    days: int = 99999, 
                    start_date: Optional[datetime] = None,
                    email: str = 'customer@example.com',
                    recipient: str = None,
                    comments: str = None,
                    license_type: str = 'premium',
                    save_to_db: bool = True,
                    verbose: bool = True) -> Dict[str, Any]:
    """
    Генерирует лицензию
    
    Args:
        hw_id: Hardware ID клиента (будет нормализован до 16 символов).
               None или пустая строка = универсальная лицензия (работает на любом ПК).
               Для developer лицензий рекомендуется None.
        days: Количество дней действия (для developer по умолчанию 99999)
        start_date: Дата начала лицензии (если None, используется текущая дата + 1 день)
        email: Email получателя (используется для генерации license_id, можно оставить дефолтным)
        recipient: Контактная информация получателя (email, telegram, и т.д.) - сохраняется в БД
        comments: Комментарии к лицензии
        license_type: Тип лицензии ('premium', 'trial', 'developer', 'lifetime' и т.д.)
                     Для developer лицензий автоматически устанавливается hardware_id=None
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
    # Для developer лицензий автоматически убираем привязку к HWID
    if license_type.lower() == 'developer':
        hw_id = None
        if verbose:
            print("[INFO] Developer лицензия: привязка к HWID отключена (работает на любом ПК)")
    
    # Нормализуем HWID: берем только первые 16 символов для совместимости (если указан)
    if hw_id:
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
        print(f"License Type: {license_type}")
        print(f"HWID: {hw_id if hw_id else 'NONE (универсальная лицензия)'}")
        print(f"Duration: {days} days")
        if start_date:
            print(f"Start date: {start_date.strftime('%Y-%m-%d')}")
        print()
    
    manager = LicenseManager()
    
    # Генерируем лицензию
    license_data = manager.generate_license(
        user_email=email,
        license_type=license_type,
        hardware_id=hw_id,  # None для developer или универсальных лицензий
        custom_duration_days=days,
        start_date=start_date
    )
    
    # Сохраняем файл
    output_dir = script_dir / 'generated_licenses'
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Для универсальных лицензий (без HWID) используем специальное имя
    hw_prefix = hw_id if hw_id else "UNIVERSAL"
    filename = f"{hw_prefix}_{license_type}_{days}days_{timestamp}.lic"
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
        print(f"License Type:   {license_type}")
        print(f"Hardware ID:    {hw_id if hw_id else 'NONE (универсальная лицензия)'}")
        print(f"Duration:       {days} days")
        print(f"Start date:     {start_date.strftime('%Y-%m-%d')}")
        print(f"Expires:        {license_data['license_data']['expires_at']}")
        print()
        if not hw_id or license_type.lower() == 'developer':
            if verbose:
                print("[INFO] УНИВЕРСАЛЬНАЯ ЛИЦЕНЗИЯ: работает на любом оборудовании!")
                print()
        print(f"License file:   {license_path}")
        if recipient_id:
            print(f"Database ID:    {recipient_id}")
        print("=" * 60)
        print()
        if license_type.lower() == 'developer':
            if verbose:
                print("[OK] DEVELOPER ЛИЦЕНЗИЯ: поместите .lic файл в корень проекта")
        else:
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
    if len(sys.argv) < 2:
        print("Usage: python generate_license.py <HWID|--developer> <DAYS> [START_DATE] [RECIPIENT] [COMMENTS]")
        print()
        print("  HWID: Hardware ID (будет обрезан до 16 символов)")
        print("        Или '--developer' для создания developer лицензии (без привязки к HWID)")
        print("  DAYS: Количество дней лицензии (для developer по умолчанию 99999)")
        print("  START_DATE: Дата начала (опционально, по умолчанию: завтра)")
        print("              Форматы: YYYY-MM-DD (2025-12-31) или DD.MM.YYYY (31.12.2025)")
        print("  RECIPIENT: Контактная информация получателя (опционально)")
        print("             Можно указать: email, telegram nickname, telegram ID, и т.д.")
        print("  COMMENTS: Комментарии (опционально)")
        print()
        print("Examples:")
        print("  # Обычная лицензия:")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30")
        print("  python generate_license.py 94EAA22C9EDB6FC7 30 2024-02-01")
        print()
        print("  # Developer лицензия (работает на любом ПК):")
        print("  python generate_license.py --developer")
        print("  python generate_license.py --developer 99999")
        sys.exit(1)
    
    # Проверяем, создается ли developer лицензия
    if sys.argv[1] == '--developer':
        hw_id = None
        license_type = 'developer'
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 99999
        arg_offset = 1  # Пропускаем --developer и days
    else:
        hw_id = sys.argv[1]
        license_type = 'premium'
        days = int(sys.argv[2])
        arg_offset = 0
    
    # Опциональные параметры (с учетом offset для developer)
    start_date = None
    start_arg_idx = 3 + arg_offset
    if len(sys.argv) > start_arg_idx and sys.argv[start_arg_idx]:
        date_str = sys.argv[start_arg_idx]
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
    
    recipient = sys.argv[start_arg_idx + 1] if len(sys.argv) > start_arg_idx + 1 else None
    comments = sys.argv[start_arg_idx + 2] if len(sys.argv) > start_arg_idx + 2 else None
    
    # Email для генерации license_id (можно оставить дефолтным)
    # Для developer лицензий используем специальный email
    if license_type == 'developer':
        email = 'developer@infobot.local'
    else:
        email = recipient if recipient and '@' in recipient else 'customer@example.com'
    
    result = generate_license(hw_id, days, start_date=start_date, email=email, recipient=recipient, 
                             comments=comments, license_type=license_type)
    
    # Возвращаем код выхода 0 при успехе
    sys.exit(0)

