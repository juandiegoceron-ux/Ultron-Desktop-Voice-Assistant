@echo off
chcp 65001 >nul
title ULTRÓN AI Assistant — Stark Voice OS
cd /d "%~dp0"

echo ====================================================================
echo               INICIANDO ULTRON AI VOICE OS v5.2
echo           Ing. Biomedico: Juan Diego Ceron Duque
echo ====================================================================
echo.

:: Detectar ejecutable de Python (entorno virtual o global)
set "PYTHON_EXE="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    echo [*] Utilizando entorno virtual (.venv)
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
    echo [*] Utilizando entorno virtual (venv)
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python"
        echo [*] Utilizando Python global del sistema
    ) else (
        where py >nul 2>nul
        if %errorlevel% equ 0 (
            set "PYTHON_EXE=py -3"
            echo [*] Utilizando lanzador py de Windows
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo.
    echo [ERROR] No se encontro Python en tu sistema ni en .venv/venv.
    echo Por favor instala Python 3.10+ desde https://www.python.org/downloads/
    echo o desde la Microsoft Store, marcando 'Add python.exe to PATH'.
    echo.
    pause
    exit /b 1
)

:: Si se pasaron parametros extras, usarlos; de lo contrario arrancar con --hud por defecto
if "%~1"=="" (
    set "ARGS=--hud"
) else (
    set "ARGS=%*"
)

echo [*] Ejecutando: %PYTHON_EXE% main.py %ARGS%
echo.
%PYTHON_EXE% main.py %ARGS%

if %errorlevel% neq 0 (
    echo.
    echo [!] Ultrón finalizo con codigo de salida %errorlevel%.
    echo Si falta alguna dependencia, ejecuta: pip install -r requirements.txt
    echo.
    pause
)
