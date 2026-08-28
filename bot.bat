@echo off
rem Запуск из папки, где лежит этот файл (раньше был жёстко C:\bot)
cd /d "%~dp0"
python bot.py
pause
