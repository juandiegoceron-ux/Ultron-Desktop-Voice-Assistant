@echo off
setlocal
chcp 65001 >nul
title ULTRÓN AI Assistant — Stark Voice OS
cd /d "%~dp0"

echo ====================================================================
echo               INICIANDO ULTRON AI VOICE OS v5.2
echo           Ing. Biomedico: Juan Diego Ceron Duque
echo ====================================================================
echo.

:: 1. Verificar si existe entorno virtual local
if exist "%~dp0.venv\Scripts\python.exe" (
    echo [*] Detectado entorno virtual (.venv)
    set "RUN_CMD="%~dp0.venv\Scripts\python.exe""
    goto :run
)
if exist "%~dp0venv\Scripts\python.exe" (
    echo [*] Detectado entorno virtual (venv)
    set "RUN_CMD="%~dp0venv\Scripts\python.exe""
    goto :run
)

:: 2. Verificar lanzador py de Windows
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Detectado lanzador Python (py -3)
    set "RUN_CMD=py -3"
    goto :run
)

:: 3. Verificar python en PATH
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Detectado Python en PATH
    set "RUN_CMD=python"
    goto :run
)

:: Si llego aqui, no se encontro Python
echo.
echo ====================================================================
echo [ERROR] No se encontro Python en tu sistema ni en .venv/venv.
echo.
echo Para solucionarlo:
echo  1. Instala Python 3.10 o superior desde https://www.python.org/downloads/
echo  2. Asegurate de marcar la casilla: 'Add python.exe to PATH'
echo ====================================================================
echo.
pause
exit /b 1

:run
if "%~1"=="" (
    set "ARGS=--hud"
) else (
    set "ARGS=%*"
)

echo [*] Ejecutando: %RUN_CMD% main.py %ARGS%
echo.

%RUN_CMD% main.py %ARGS%

if %errorlevel% neq 0 (
    echo.
    echo ====================================================================
    echo [!] Ultrón finalizo con codigo de salida %errorlevel%.
    echo Si falta alguna libreria, ejecuta en tu terminal:
    echo     pip install -r requirements.txt
    echo ====================================================================
    echo.
    pause
)
