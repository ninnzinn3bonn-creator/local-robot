@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================
echo  Local robot web UI
echo ========================================
echo URL: http://127.0.0.1:8765
echo Stop: Ctrl+C
echo ========================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" web.py --host 127.0.0.1 --port 8765 %*
) else (
    python web.py --host 127.0.0.1 --port 8765 %*
)
