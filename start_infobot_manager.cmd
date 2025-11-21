@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

REM Проверка наличия Python
set "PYTHON_FOUND=0"
python --version >nul 2>&1 && set "PYTHON_FOUND=1"
if !PYTHON_FOUND!==0 (
    py -3 --version >nul 2>&1 && set "PYTHON_FOUND=1"
)
if !PYTHON_FOUND!==0 (
    python3 --version >nul 2>&1 && set "PYTHON_FOUND=1"
)

REM Если Python не найден - пытаемся установить
if !PYTHON_FOUND!==0 (
    winget --version >nul 2>&1
    if !errorlevel!==0 (
        echo [INFO] Установка Python через winget...
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        timeout /t 3 /nobreak >nul
        python --version >nul 2>&1 && set "PYTHON_FOUND=1"
        if !PYTHON_FOUND!==0 (
            py -3 --version >nul 2>&1 && set "PYTHON_FOUND=1"
        )
    )
    
    REM Если Python всё ещё не найден - открываем страницу скачивания
    if !PYTHON_FOUND!==0 (
        echo [ERROR] Python не найден. Открываю страницу для скачивания...
        start https://www.python.org/downloads/windows/
        exit /b 1
    )
)

REM Проверка Git (только если Python установлен)
git --version >nul 2>&1
if !errorlevel! neq 0 (
    winget --version >nul 2>&1
    if !errorlevel!==0 (
        echo [INFO] Установка Git через winget...
        REM Тихая установка Git с максимальной интеграцией и nano редактором
        REM Параметры: /VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES
        REM /COMPONENTS=icons,ext\shellhere,assoc,assoc_sh /PATHOPTION=user /EDITOR=nano
        winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements --override "/VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES /COMPONENTS=icons,ext\shellhere,assoc,assoc_sh /PATHOPTION=user /EDITOR=nano"
    )
)

REM Безопасная инициализация Git репозитория (если Git установлен)
git --version >nul 2>&1
if !errorlevel!==0 (
    if not exist ".git" (
        REM Инициализируем репозиторий БЕЗ pull/fetch, чтобы не перезаписать существующие файлы
        git init >nul 2>&1
        git branch -m main >nul 2>&1
        REM Проверяем, есть ли уже remote origin
        git remote get-url origin >nul 2>&1
        if !errorlevel! neq 0 (
            REM Добавляем remote только если его нет
            git remote add origin git@github.com:HellEvro/TPM_Public.git >nul 2>&1
        )
    )
)

REM Определение Python для запуска
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    set "PYTHON_BIN=python"
) else (
    echo [WARN] Virtual environment not found. Falling back to system Python.
    if exist %SystemRoot%\py.exe (
        set "PYTHON_BIN=py -3"
    ) else (
        set "PYTHON_BIN=python"
    )
)
%PYTHON_BIN% launcher\infobot_manager.py %*
endlocal

