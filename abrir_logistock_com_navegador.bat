@echo off
cd /d "%~dp0"
if exist ".runtime\python311\python.exe" (
    ".runtime\python311\python.exe" abrir_logistock.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" abrir_logistock.py
) else (
    python abrir_logistock.py
)
pause
