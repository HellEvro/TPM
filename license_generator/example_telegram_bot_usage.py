#!/usr/bin/env python3
"""
Пример использования generate_license.py из телеграм-бота или другого модуля

ВАЖНО: Это пример! Адаптируйте под вашу реализацию телеграм-бота.
"""

import sys
from pathlib import Path
from datetime import datetime

# Добавляем путь к license_generator
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from generate_license import generate_license


def handle_telegram_command_generate_license(message_text: str, user_id: int):
    """
    Пример обработчика команды телеграм-бота для генерации лицензии
    
    Команда может быть в формате:
    /generate_license <HWID> <DAYS> [START_DATE] [EMAIL] [COMMENTS]
    
    Args:
        message_text: Текст сообщения от пользователя
        user_id: ID пользователя в телеграме
    
    Returns:
        Ответное сообщение для пользователя
    """
    try:
        # Парсим команду
        parts = message_text.split()
        
        if len(parts) < 3:
            return (
                "❌ Неверный формат команды.\n\n"
                "Использование:\n"
                "/generate_license <HWID> <DAYS> [START_DATE] [EMAIL] [COMMENTS]\n\n"
                "Примеры:\n"
                "/generate_license 94EAA22C9EDB6FC7 30\n"
                "/generate_license 94EAA22C9EDB6FC7 30 2024-02-01\n"
                "/generate_license 94EAA22C9EDB6FC7 30 2024-02-01 customer@example.com 'Test license'"
            )
        
        hw_id = parts[1]
        days = int(parts[2])
        
        # Опциональные параметры
        start_date = None
        if len(parts) > 3 and parts[3]:
            try:
                start_date = datetime.strptime(parts[3], '%Y-%m-%d')
            except ValueError:
                return f"❌ Неверный формат даты: {parts[3]}. Используйте YYYY-MM-DD"
        
        email = parts[4] if len(parts) > 4 else 'customer@example.com'
        comments = ' '.join(parts[5:]) if len(parts) > 5 else None
        
        # Генерируем лицензию (verbose=False, чтобы не выводить в консоль)
        result = generate_license(
            hw_id=hw_id,
            days=days,
            start_date=start_date,
            email=email,
            comments=comments,
            save_to_db=True,
            verbose=False  # Не выводим в консоль, так как это бот
        )
        
        # Формируем ответ
        response = (
            "✅ Лицензия успешно сгенерирована!\n\n"
            f"📋 Hardware ID: {result['hw_id']}\n"
            f"📅 Длительность: {result['days']} дней\n"
            f"📆 Дата начала: {result['start_date'][:10]}\n"
            f"📆 Дата окончания: {result['end_date'][:10]}\n"
            f"📁 Файл: {Path(result['license_path']).name}\n"
        )
        
        if result.get('recipient_id'):
            response += f"💾 ID в базе: {result['recipient_id']}\n"
        
        response += f"\n📂 Полный путь: {result['license_path']}"
        
        return response
        
    except ValueError as e:
        return f"❌ Ошибка в параметрах: {str(e)}"
    except Exception as e:
        return f"❌ Ошибка генерации лицензии: {str(e)}"


def handle_telegram_command_subprocess(message_text: str):
    """
    Альтернативный вариант: вызов через subprocess (если нужно запустить как отдельный процесс)
    
    Args:
        message_text: Текст сообщения от пользователя
    
    Returns:
        Ответное сообщение для пользователя
    """
    import subprocess
    
    try:
        parts = message_text.split()
        
        if len(parts) < 3:
            return "❌ Неверный формат команды"
        
        hw_id = parts[1]
        days = parts[2]
        
        # Формируем команду
        script_path = script_dir / 'generate_license.py'
        cmd = [sys.executable, str(script_path), hw_id, days]
        
        # Добавляем опциональные параметры
        if len(parts) > 3:
            cmd.append(parts[3])  # start_date
        if len(parts) > 4:
            cmd.append(parts[4])  # email
        if len(parts) > 5:
            cmd.append(' '.join(parts[5:]))  # comments
        
        # Выполняем команду
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(script_dir)
        )
        
        if result.returncode == 0:
            # Парсим вывод для получения пути к файлу
            output_lines = result.stdout.split('\n')
            license_path = None
            for line in output_lines:
                if 'License file:' in line:
                    license_path = line.split('License file:')[1].strip()
                    break
            
            return (
                f"✅ Лицензия успешно сгенерирована!\n\n"
                f"📁 Файл: {Path(license_path).name if license_path else 'N/A'}\n"
                f"📂 Путь: {license_path if license_path else 'N/A'}"
            )
        else:
            return f"❌ Ошибка: {result.stderr}"
            
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"


# Пример использования с python-telegram-bot
"""
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

async def generate_license_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Обработчик команды /generate_license'''
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Неверный формат команды.\n\n"
            "Использование: /generate_license <HWID> <DAYS> [START_DATE] [EMAIL] [COMMENTS]"
        )
        return
    
    hw_id = context.args[0]
    days = int(context.args[1])
    
    start_date = None
    if len(context.args) > 2:
        try:
            start_date = datetime.strptime(context.args[2], '%Y-%m-%d')
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте YYYY-MM-DD")
            return
    
    email = context.args[3] if len(context.args) > 3 else 'customer@example.com'
    comments = ' '.join(context.args[4:]) if len(context.args) > 4 else None
    
    # Генерируем лицензию
    result = generate_license(
        hw_id=hw_id,
        days=days,
        start_date=start_date,
        email=email,
        comments=comments,
        verbose=False
    )
    
    # Отправляем файл лицензии
    license_file = Path(result['license_path'])
    if license_file.exists():
        await update.message.reply_document(
            document=open(license_file, 'rb'),
            caption=(
                f"✅ Лицензия сгенерирована!\n\n"
                f"HWID: {result['hw_id']}\n"
                f"Дней: {result['days']}\n"
                f"Начало: {result['start_date'][:10]}\n"
                f"Окончание: {result['end_date'][:10]}"
            )
        )
    else:
        await update.message.reply_text("❌ Файл лицензии не найден")

# Регистрация обработчика
application.add_handler(CommandHandler("generate_license", generate_license_command))
"""


if __name__ == '__main__':
    # Тест функции
    test_command = "/generate_license 94EAA22C9EDB6FC7 30"
    result = handle_telegram_command_generate_license(test_command, user_id=123)
    print(result)

