@echo off
setlocal enabledelayedexpansion

:: Navigate to current folder
cd /d "%~dp0"

echo ================================================================
echo       SIGN LANGUAGE AI STUDIO - AUTOMATED LAUNCHER
echo ================================================================
echo.

:: 1. Check for Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your system PATH!
    echo Please install Python 3.9, 3.10, or 3.11 from https://www.python.org
    echo and make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

python --version

:: 2. Create virtual environment if missing
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo [*] Creating Python virtual environment in .venv ...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment (.venv).
        echo Please ensure you have the python3-venv package installed.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Virtual environment found (.venv).
)

:: 3. Activate virtual environment
echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    echo.
    pause
    exit /b 1
)

:: 4. Verify and install requirements
echo [*] Checking dependencies in requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install one or more dependencies from requirements.txt.
    echo Please review the errors above.
    echo.
    pause
    exit /b 1
)

:: 5. Build React frontend if dist is missing
if not exist "dist\index.html" (
    where npm >nul 2>nul
    if %errorlevel% equ 0 (
        echo.
        echo [*] Building web frontend for production (one-time setup)...
        call npm install
        call npm run build
    ) else (
        echo [INFO] npm not found on PATH. If frontend was prebuilt, it will be served directly.
    )
)

:: 6. Launch FastAPI server and open browser
echo.
echo ================================================================
echo   Launching Sign Language AI Studio...
echo   URL: http://localhost:8000
echo ================================================================
echo.

start "" "http://localhost:8000"

python backend.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The backend server stopped unexpectedly with error code %errorlevel%.
    echo.
    pause
    exit /b %errorlevel%
)

pause
