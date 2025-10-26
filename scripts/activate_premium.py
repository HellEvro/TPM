"""
Активация InfoBot AI Premium лицензии / InfoBot AI Premium License Activation

Этот скрипт показывает Hardware ID пользователя и инструкции по активации.
This script shows user's Hardware ID and activation instructions.
"""

import sys
sys.path.append('.')

import os
from pathlib import Path


def activate_premium_license():
    """Показывает Hardware ID и инструкции по активации"""
    
    print("=" * 60)
    print("InfoBot AI Premium - License Activation")
    print("=" * 60)
    print()
    
    try:
        # В режиме разработки показываем hardware ID
        if os.getenv('AI_DEV_MODE') == '1':
            print("[DEV MODE] Development mode active - no license needed")
            print("[РЕЖИМ РАЗРАБОТКИ] Режим разработки активен - лицензия не требуется")
            print()
            print("To use AI modules in dev mode:")
            print("Чтобы использовать ИИ модули в режиме разработки:")
            print("  1. set AI_DEV_MODE=1")
            print("  2. Edit bot_config.py: AI_ENABLED = True")
            print("  3. python bots.py")
            print()
            return
        
        # Пытаемся импортировать систему лицензий
        try:
            sys.path.insert(0, 'InfoBot_AI_Premium')
            from license.hardware_id import get_hardware_id, get_short_hardware_id
            
            hw_id = get_short_hardware_id()
            full_hw_id = get_hardware_id()
            
            print("=" * 60)
            print("YOUR HARDWARE ID / ВАШ HARDWARE ID")
            print("=" * 60)
            print()
            print(f"Short HWID:    {hw_id}")
            print(f"Full HWID:     {full_hw_id}")
            print()
            print("=" * 60)
            print("HOW TO ACTIVATE / КАК АКТИВИРОВАТЬ")
            print("=" * 60)
            print()
            print("1. Send your Hardware ID to:")
            print("   1. Отправьте ваш Hardware ID на:")
            print("   Email: gci.company.ou@gmail.com")
            print()
            print("2. Wait for your license file (.lic)")
            print("   2. Дождитесь файла лицензии (.lic)")
            print()
            print("3. Place the .lic file in the root folder of InfoBot")
            print("   3. Поместите файл .lic в корневую папку InfoBot")
            print("   (Any file with .lic extension will work)")
            print("   (Подойдет любой файл с расширением .lic)")
            print()
            print("4. Restart the bot:")
            print("   4. Перезапустите бота:")
            print("   python bots.py")
            print()
            print("=" * 60)
            print()
            print("Your license will be automatically detected and activated!")
            print("Ваша лицензия будет автоматически обнаружена и активирована!")
            print()
            
        except ImportError:
            print("[ERROR] Premium license system not found")
            print("[ОШИБКА] Система премиум лицензий не найдена")
            print()
            print("InfoBot AI Premium is not installed.")
            print("InfoBot AI Premium не установлен.")
            print()
            print("Options / Варианты:")
            print("  1. Use development mode (free, for testing):")
            print("     Используйте режим разработки (бесплатно, для тестирования):")
            print("     set AI_DEV_MODE=1")
            print()
            print("  2. Purchase a license:")
            print("     Приобретите лицензию:")
            print("     Email: gci.company.ou@gmail.com")
            print()
            return
    
    except Exception as e:
        print(f"[ERROR] Failed to get hardware ID / Не удалось получить HWID: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    activate_premium_license()
