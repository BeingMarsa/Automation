@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Please run:
    echo uv venv
    echo uv pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py %*
