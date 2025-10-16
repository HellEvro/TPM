# Скрипт синхронизации приватной версии с паблик версией
# НЕ копирует: конфиги, ключи, .git, данные, логи

Write-Host "🔄 Синхронизация приватной версии с паблик..." -ForegroundColor Green

# Основные файлы проекта
Write-Host "📁 Копируем основные файлы..." -ForegroundColor Yellow
Copy-Item "app.py" "InfoBot_Public\" -Force
Copy-Item "bots.py" "InfoBot_Public\" -Force
Copy-Item "protector.py" "InfoBot_Public\" -Force
Copy-Item "requirements.txt" "InfoBot_Public\" -Force
Copy-Item "README.md" "InfoBot_Public\" -Force
Copy-Item "INSTALL.md" "InfoBot_Public\" -Force

# Код приложения
Write-Host "📁 Копируем код приложения..." -ForegroundColor Yellow
Copy-Item "app\*.py" "InfoBot_Public\app\" -Force -Exclude "config.py", "keys.py", "*example*"

# Bot Engine
Write-Host "📁 Копируем bot_engine..." -ForegroundColor Yellow
Copy-Item "bot_engine\*" "InfoBot_Public\bot_engine\" -Force -Recurse

# Bots Modules
Write-Host "📁 Копируем bots_modules..." -ForegroundColor Yellow
Copy-Item "bots_modules\*" "InfoBot_Public\bots_modules\" -Force -Recurse

# Exchanges
Write-Host "📁 Копируем exchanges..." -ForegroundColor Yellow
Copy-Item "exchanges\*" "InfoBot_Public\exchanges\" -Force -Recurse

# Static files (CSS, JS, images)
Write-Host "📁 Копируем static..." -ForegroundColor Yellow
Copy-Item "static\*" "InfoBot_Public\static\" -Force -Recurse

# Templates
Write-Host "📁 Копируем templates..." -ForegroundColor Yellow
Copy-Item "templates\*" "InfoBot_Public\templates\" -Force -Recurse

# Scripts
Write-Host "📁 Копируем scripts..." -ForegroundColor Yellow
Copy-Item "scripts\*" "InfoBot_Public\scripts\" -Force -Recurse

# Utils
Write-Host "📁 Копируем utils..." -ForegroundColor Yellow
Copy-Item "utils\*" "InfoBot_Public\utils\" -Force -Recurse

# Tests
Write-Host "📁 Копируем tests..." -ForegroundColor Yellow
Copy-Item "tests\*" "InfoBot_Public\tests\" -Force -Recurse

# Docs
Write-Host "📁 Копируем docs..." -ForegroundColor Yellow
Copy-Item "docs\*" "InfoBot_Public\docs\" -Force -Recurse

# Changelog файлы
Write-Host "📁 Копируем changelog..." -ForegroundColor Yellow
if (Test-Path "CHANGELOG_POSITION_REGISTRY.md") {
    Copy-Item "CHANGELOG_POSITION_REGISTRY.md" "InfoBot_Public\" -Force
}
if (Test-Path "COMMIT_MESSAGE_REGISTRY.md") {
    Copy-Item "COMMIT_MESSAGE_REGISTRY.md" "InfoBot_Public\" -Force
}

Write-Host "✅ Синхронизация завершена!" -ForegroundColor Green
Write-Host "🚫 НЕ копировались: config.py, keys.py, data/, logs/, .git/" -ForegroundColor Red
