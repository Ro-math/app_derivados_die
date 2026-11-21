@echo off
REM =============================================================================
REM Lanzador para Windows (CMD o PowerShell)
REM Uso:
REM   run.bat web
REM   run.bat consola
REM   run.bat comand
REM =============================================================================
setlocal
cd /d "%~dp0"

REM 1. Probar con python estándar de Windows
where python >nul 2>nul
if %errorlevel% equ 0 (
    python run.py %*
    goto :end
)

REM 2. Probar con el launcher py de Windows
where py >nul 2>nul
if %errorlevel% equ 0 (
    py run.py %*
    goto :end
)

echo.
echo =======================================================================
echo [Error] No se encontro Python instalado en el sistema.
echo Por favor instala Python 3 desde python.org o la Microsoft Store,
echo asegurandote de marcar la casilla: 'Add Python to PATH'.
echo =======================================================================
echo.
pause
exit /b 1

:end
endlocal
