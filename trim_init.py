with open('bots_modules/init_functions.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = lines[:634]

with open('bots_modules/init_functions.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f'Обрезано с {len(lines)} до {len(new_lines)} строк')

