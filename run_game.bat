@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src\main.py
    goto :end
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 src\main.py
    goto :end
)

python src\main.py

:end
if errorlevel 1 (
    echo.
    echo Game failed to start. Run: python -m pip install -r requirements.txt
    pause
)
