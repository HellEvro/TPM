"""
Создание лицензий для клиентов вручную
Использование: python create_customer_license.py
"""

import sys
sys.path.append('.')
sys.path.insert(0, 'InfoBot_AI_Premium')

from license.hardware_id import get_hardware_id
from license.license_manager import LicenseManager
from pathlib import Path
from datetime import datetime

def create_customer_license():
    """Создает лицензию для клиента"""
    
    print("=" * 60)
    print("LICENSE GENERATOR FOR CUSTOMERS")
    print("=" * 60)
    print()
    
    # Просим ввести данные через параметры командной строки или интерактивно
    if len(sys.argv) == 3:
        hw_id = sys.argv[1]
        duration_input = sys.argv[2]
    else:
        print("Usage: python create_customer_license.py <HWID> <DAYS>")
        print()
        print("Examples:")
        print("  python create_customer_license.py CB286F975D4A8194 365")
        print("  python create_customer_license.py CB286F975D4A8194 30")
        print("  python create_customer_license.py CB286F975D4A8194 9999")
        return
    
    if not hw_id:
        print("[ERROR] Hardware ID is required!")
        return
    
    try:
        custom_days = int(duration_input)
    except ValueError:
        print("[ERROR] Duration must be a number!")
        return
    
    print(f"HWID: {hw_id}")
    print(f"Duration: {custom_days} days")
    print()
    print("Generating license...")
    print()
    
    try:
        email = "customer@local"
        license_type = "premium"
        
        # Создаем менеджер лицензий
        manager = LicenseManager()
        
        # Генерируем лицензию
        license_data = manager.generate_license(
            user_email=email,
            license_type=license_type,
            hardware_id=hw_id,
            custom_duration_days=custom_days
        )
        
        print("[OK] License generated successfully!")
        print()
        
        # Сохраняем лицензию
        output_dir = Path('generated_licenses')
        output_dir.mkdir(exist_ok=True)
        
        filename = f"{hw_id}_{custom_days}days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.lic"
        license_path = output_dir / filename
        
        with open(license_path, 'wb') as f:
            f.write(license_data['encrypted_license'])
        
        print(f"[OK] License saved: {license_path}")
        print()
        
        # Также создаем активационный файл для клиента
        activation_file = output_dir / f"ACTIVATION_KEY_{filename.replace('.lic', '.txt')}"
        with open(activation_file, 'w', encoding='utf-8') as f:
            f.write(f"CUSTOMER LICENSE INFORMATION\n")
            f.write(f"===================\n\n")
            f.write(f"Hardware ID:  {hw_id}\n")
            f.write(f"Duration:     {custom_days} days\n")
            f.write(f"Expires:      {license_data['license_data']['expires_at']}\n")
            f.write(f"\nActivation Key:\n")
            f.write(f"{license_data['activation_key']}\n")
            f.write(f"\nInstructions:\n")
            f.write(f"1. Copy the .lic file to your InfoBot folder\n")
            f.write(f"2. Restart the bot\n")
            f.write(f"3. Premium features will be activated!\n")
        
        print(f"[OK] Activation file saved: {activation_file}")
        print()
        
        print("=" * 60)
        print("LICENSE SUMMARY")
        print("=" * 60)
        print(f"Activation Key (format: XXXX-XXXX-XXXX-XXXX):")
        print(f"  {license_data['activation_key']}")
        print()
        print(f"Hardware ID:    {hw_id}")
        print(f"Duration:       {custom_days} days")
        print(f"Expires:        {license_data['license_data']['expires_at']}")
        print()
        print(f"License file:   {license_path}")
        print("=" * 60)
        print()
        print("✅ License is ready to send to customer!")
        print()
        print("Send to customer:")
        print(f"  1. The .lic file: {license_path}")
        print(f"  2. Activation key: {license_data['activation_key']}")
        print()
        
    except Exception as e:
        print(f"[ERROR] Failed to generate license: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    create_customer_license()
