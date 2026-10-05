@echo off
setlocal enabledelayedexpansion
title Komorebi Desktop
cd /d "%~dp0"

echo [Komorebi Desktop] Kontrola Python prostredi...

:: 1. Check if Python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo.
        echo ======================================================================
        echo  [CHYBA] Python nebyl v systemu nalezen!
        echo  Pro beh ze zdrojovych kodu je nutne mit nainstalovany Python 3.10+
        echo  Stahnete si jej z: https://www.python.org/downloads/
        echo  DULEZITE: Pri instalaci zaskrtnete "Add python.exe to PATH"!
        echo ======================================================================
        echo.
        pause
        exit /b 1
    )
    set "PY_CMD=py"
) else (
    set "PY_CMD=python"
)

:: 2. Check virtual environment & PyQt6 installation
set "NEED_INSTALL=0"
if not exist ".venv\Scripts\python.exe" (
    echo [Komorebi Desktop] Vytvarim virtualni prostredi .venv...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [CHYBA] Nepodarilo se vytvorit virtualni prostredi .venv.
        pause
        exit /b 1
    )
    set "NEED_INSTALL=1"
) else (
    .venv\Scripts\python.exe -c "import PyQt6" >nul 2>nul
    if %errorlevel% neq 0 (
        set "NEED_INSTALL=1"
    )
)

if "%NEED_INSTALL%"=="1" (
    echo [Komorebi Desktop] Instaluji potrebne knihovny (PyQt6, requests, Pillow)...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [CHYBA] Instalace knihoven z requirements.txt selhala.
        pause
        exit /b 1
    )
)

:: 3. Launch the application
echo [Komorebi Desktop] Spoustim aplikaci...
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py %*
) else (
    start "" ".venv\Scripts\python.exe" main.py %*
)
