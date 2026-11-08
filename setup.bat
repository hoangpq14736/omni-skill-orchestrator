@echo off
setlocal enabledelayedexpansion

title Omni-Kernel v4.1 - One-Click Machine Setup

echo ====================================================================
echo ⚡ OMNI-KERNEL v4.1: ONE-CLICK ENVIRONMENT SETUP ^& BOOTSTRAPPER
echo ====================================================================
echo.

:: 1. Detect Python executable
set "PYTHON_CMD="

:: Check 'python' in PATH
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
    goto :PYTHON_FOUND
)

:: Check 'py' launcher in PATH
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py"
    goto :PYTHON_FOUND
)

:: Check common Windows User AppData locations
for %%V in (313 312 311 310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        goto :PYTHON_FOUND
    )
)

:: Check common Program Files locations
for %%V in (313 312 311 310) do (
    if exist "%ProgramFiles%\Python%%V\python.exe" (
        set "PYTHON_CMD=%ProgramFiles%\Python%%V\python.exe"
        goto :PYTHON_FOUND
    )
    if exist "%ProgramFiles(x86)%\Python%%V\python.exe" (
        set "PYTHON_CMD=%ProgramFiles(x86)%\Python%%V\python.exe"
        goto :PYTHON_FOUND
    )
)

:PYTHON_NOT_FOUND
echo [X] ERROR: Python 3.10+ was not found on this machine!
echo.
echo Would you like to automatically install Python 3.12 via winget?
set /p "INSTALL_PY=Install Python now? (Y/N): "
if /i "%INSTALL_PY%"=="Y" (
    echo [*] Installing Python 3.12 via winget...
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    echo.
    echo [*] Please close this window, open a new command prompt, and run setup.bat again.
    pause
    exit /b 1
) else (
    echo [*] Please install Python 3.10+ from https://www.python.org/downloads/
    echo     Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:PYTHON_FOUND
echo [*] Detected Python Runtime: !PYTHON_CMD!
for /f "tokens=*" %%i in ('"!PYTHON_CMD!" --version 2^>^&1') do set "PY_VER=%%i"
echo     (!PY_VER!)
echo.

:: 2. Set working directory to repository root
cd /d "%~dp0"

:: 3. Execute the Python bootstrapper
echo [*] Launching Omni-Kernel Bootstrap Engine...
echo.
"!PYTHON_CMD!" "%~dp0scripts\bootstrap.py" %*

if errorlevel 1 (
    echo [!] Setup encountered warnings or errors.
) else (
    echo [*] Omni-Kernel is fully configured and ready to use!
)

:: Pause if launched via double-click from Windows Explorer
echo Press any key to exit...
pause >nul
