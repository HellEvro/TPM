@echo off
REM Запуск GUI генератора лицензий для Windows
cd /d "%~dp0"
python license_generator_gui.py
pause

