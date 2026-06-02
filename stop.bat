@echo off
setlocal EnableDelayedExpansion

echo.
echo  ========================================
echo    Stopping AI Novel Platform Services
echo  ========================================
echo.

set BACKEND_DIR=%~dp0backend
set FRONTEND_DIR=%~dp0frontend

:: =============================================
:: Helper: kill_by_pid_ps <pid_file> <port>
:: Uses PowerShell Stop-Process for reliable killing
:: =============================================
goto :main

:kill_by_pid_ps
set "PID_FILE=%~1"
set "PORT=%~2"

if not exist "%PID_FILE%" (
    echo  [Port %PORT%] No PID file found
    exit /b 0
)

set /p TARGET_PID=<"%PID_FILE%"
if "%TARGET_PID%"=="" (
    echo  [Port %PORT%] PID file empty
    del /F "%PID_FILE%" 2>nul
    exit /b 0
)

powershell -NoProfile -Command "Stop-Process -Id %TARGET_PID% -Force -ErrorAction SilentlyContinue"
echo  [Port %PORT%] Stopped PID %TARGET_PID%
del /F "%PID_FILE%" 2>nul
exit /b 0

:: =============================================
:: Helper: kill_by_port_ps <port>
:: Uses PowerShell to find and kill all processes listening on port
:: =============================================
:kill_by_port_ps
set "PORT=%~1"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo  [Port %PORT%] Stopping PID %%a...
    powershell -NoProfile -Command "Stop-Process -Id %%a -Force -ErrorAction SilentlyContinue"
)
exit /b 0

:: =============================================
:: Main
:: =============================================
:main

:: Backend: PID file first, then port fallback
call :kill_by_pid_ps "%BACKEND_DIR%\app.pid" 8000
call :kill_by_port_ps 8000

:: Frontend: PID file first, then port fallback
call :kill_by_pid_ps "%FRONTEND_DIR%\app.pid" 5173
call :kill_by_port_ps 5173

echo.
echo  ========================================
echo   All project processes stopped
echo  ========================================
echo.
pause
