"""
Подготовка обфусцированного кода для публичной версии
"""

import re
from pathlib import Path

def obfuscate_variable_names(source_code: str) -> str:
    """Обфусцирует имена переменных"""
    
    # Маппинг оригинальных имен на обфусцированные
    replacements = {
        'f': 'f',
        'd': 'd',
        'ld': 'ld',
        'sk': 'sk',
        'x': 'x',
        'cf': 'cf',
        'dec': 'dec',
        'sk2': 'sk2',
        'dtv': 'dtv',
        'es': 'es',
        'ea': 'ea',
        'de': 'de',
        'ch': 'ch',
        'lh': 'lh',
        'k1': 'k1',
        'k2': 'k2',
        'k3': 'k3',
    }
    
    # Заменяем
    for old, new in replacements.items():
        source_code = re.sub(rf'\b{old}\b', new, source_code)
    
    return source_code

def obfuscate_comments(source_code: str) -> str:
    """Удаляет/заменяет комментарии"""
    
    # Удаляем все комментарии
    source_code = re.sub(r'#.*', '', source_code)
    
    # Удаляем докстринги
    source_code = re.sub(r'""".*?"""', 'pass', source_code, flags=re.DOTALL)
    source_code = re.sub(r"'''.*?'''", 'pass', source_code, flags=re.DOTALL)
    
    return source_code

def obfuscate_strings(source_code: str) -> str:
    """Разбивает строки на части для запутывания"""
    
    # Находим строки вида 'InfoBotAI2024'
    strings = re.findall(r"'[A-Za-z0-9_]+'", source_code)
    
    for s in strings:
        if len(s) > 10:
            # Разбиваем на части
            mid = len(s) // 2
            part1 = s[:mid]
            part2 = s[mid:]
            
            replacement = part1 + " + " + part2
            source_code = source_code.replace(s, replacement, 1)
    
    return source_code

def obfuscate_code(source_code: str) -> str:
    """Полная обфускация кода"""
    
    print("Obfuscating...")
    
    # 1. Убираем комментарии
    print("  [-] Removing comments...")
    source_code = obfuscate_comments(source_code)
    
    # 2. Обфусцируем строки
    print("  [-] Obfuscating strings...")
    source_code = obfuscate_strings(source_code)
    
    # 3. Удаляем пустые строки
    print("  [-] Removing empty lines...")
    lines = [l for l in source_code.split('\n') if l.strip()]
    source_code = '\n'.join(lines)
    
    print("[OK] Code obfuscated")
    
    return source_code

def prepare_for_public():
    """Подготавливает код для публичной версии"""
    
    print("=" * 60)
    print("PREPARING FOR PUBLIC")
    print("=" * 60)
    print()
    
    source_file = Path('source/_premium_loader_source.py')
    if not source_file.exists():
        print("[ERROR] Source file not found!")
        return False
    
    print(f"[OK] Reading: {source_file}")
    source_code = source_file.read_text(encoding='utf-8')
    
    # Обфусцируем
    obfuscated = obfuscate_code(source_code)
    
    # Сохраняем
    output_file = Path('../bot_engine/ai/_premium_loader.py')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(obfuscated, encoding='utf-8')
    
    print(f"[OK] Saved to: {output_file}")
    print()
    print("=" * 60)
    print("READY FOR PUBLIC")
    print("=" * 60)
    print()
    print("Now copy files to InfoBot_Public with:")
    print("  python ../scripts/copy_to_public.py")
    print()
    
    return True

if __name__ == '__main__':
    prepare_for_public()

