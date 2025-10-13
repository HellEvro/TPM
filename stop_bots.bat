@echo off
echo Останавливаем InfoBot на порту 5001...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5001 ^| findstr LISTENING') do (
    echo Убиваем процесс PID: %%a
    taskkill /F /PID %%a
)

echo.
echo Готово!
pause

