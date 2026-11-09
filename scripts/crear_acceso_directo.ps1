# ==============================================================================
# Script de Creacion de Acceso Directo de Ultrón AI para Windows 11 / 10
# Ingenieria Biomedica - Ing. Juan Diego Ceron Duque
# ==============================================================================

$ErrorActionPreference = "Stop"

# Determinar la raiz del proyecto de forma dinamica
$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$desktopPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)

if (-not (Test-Path $desktopPath)) {
    # Fallback por si la variable de entorno especial no resuelve
    $desktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
}

$iconPath = Join-Path $projectRoot "ultron.ico"
$vbsPath  = Join-Path $projectRoot "Iniciar_Ultron_Silencioso.vbs"
$batPath  = Join-Path $projectRoot "Iniciar_Ultron.bat"
$wscriptExe = Join-Path $env:SystemRoot "System32\wscript.exe"

$wshShell = New-Object -ComObject WScript.Shell

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "   CONFIGURANDO ACCESOS DIRECTOS DE ULTRON AI EN TU ESCRITORIO   " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "[*] Raiz del proyecto: $projectRoot" -ForegroundColor DarkGray
Write-Host "[*] Carpeta Escritorio: $desktopPath" -ForegroundColor DarkGray

# 1. Crear Acceso Directo Principal: Ultrón AI (Modo App Stark HUD)
$mainShortcutPath = Join-Path $desktopPath "Ultrón AI.lnk"
$mainShortcut = $wshShell.CreateShortcut($mainShortcutPath)
$mainShortcut.TargetPath = $wscriptExe
$mainShortcut.Arguments = "`"$vbsPath`""
$mainShortcut.WorkingDirectory = $projectRoot
$mainShortcut.Description = "Ultrón AI Voice OS & Asistente Jarvis - Juan Diego Ceron"
if (Test-Path $iconPath) {
    $mainShortcut.IconLocation = "$iconPath, 0"
}
$mainShortcut.Hotkey = "Ctrl+Alt+U"
$mainShortcut.Save()
Write-Host "[OK] Creado: Ultrón AI.lnk (Modo App Nativa)" -ForegroundColor Green
Write-Host "     -> Atajo global asignado: Ctrl + Alt + U" -ForegroundColor Yellow

# 2. Crear Acceso Directo de Depuracion: Ultrón AI (Consola)
$debugShortcutPath = Join-Path $desktopPath "Ultrón AI (Consola).lnk"
$debugShortcut = $wshShell.CreateShortcut($debugShortcutPath)
$debugShortcut.TargetPath = $batPath
$debugShortcut.WorkingDirectory = $projectRoot
$debugShortcut.Description = "Ultrón AI Voice OS (Modo Consola con Logs)"
if (Test-Path $iconPath) {
    $debugShortcut.IconLocation = "$iconPath, 0"
}
$debugShortcut.Save()
Write-Host "[OK] Creado: Ultrón AI (Consola).lnk (Modo con Terminal)" -ForegroundColor Green

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " ¡LISTO! Ahora puedes abrir a Ultrón con 1 solo clic en tu        " -ForegroundColor Green
Write-Host " escritorio o pulsando Ctrl + Alt + U en cualquier momento.       " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""
