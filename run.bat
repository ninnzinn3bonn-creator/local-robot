@echo off
setlocal
cd /d "%~dp0"

REM -------------------------------------------------------
REM Local modal agent launcher
REM -------------------------------------------------------
REM Prerequisite: VOICEVOX ENGINE is running.
REM Preferred: .venv\Scripts\python.exe created with Python 3.11.
REM -------------------------------------------------------

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [WARN] .venv was not found. Looking for system Python.
    set "PYTHON="
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /I "\\Microsoft\\WindowsApps\\python.exe" > nul
        if errorlevel 1 if not defined PYTHON set "PYTHON=%%P"
    )
    if not defined PYTHON (
        echo [ERROR] Python is not available.
        echo         Create .venv with Python 3.11, then run this again.
        echo         Example: py -3.11 -m venv .venv
        exit /b 1
    )
)

"%PYTHON%" --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python failed to start.
    echo         Create .venv with Python 3.11, then run this again.
    echo         Example: py -3.11 -m venv .venv
    exit /b 1
)

echo ========================================
echo  Local modal agent
echo ========================================
echo  Stop: Ctrl+C
echo ========================================

"%PYTHON%" main.py %*
