' ==============================================================================
' Ultrón AI Assistant - Lanzador Silencioso en Segundo Plano
' Ejecuta Ultrón sin mostrar ninguna ventana negra de terminal (CMD)
' ==============================================================================
Option Explicit

Dim fso, wshShell, scriptDir, pythonExe

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set wshShell = CreateObject("WScript.Shell")
wshShell.CurrentDirectory = scriptDir

' Priorizar pythonw.exe (que nunca abre consola) si existe en .venv o venv
If fso.FileExists(scriptDir & "\.venv\Scripts\pythonw.exe") Then
    pythonExe = """" & scriptDir & "\.venv\Scripts\pythonw.exe"""
ElseIf fso.FileExists(scriptDir & "\venv\Scripts\pythonw.exe") Then
    pythonExe = """" & scriptDir & "\venv\Scripts\pythonw.exe"""
ElseIf fso.FileExists(scriptDir & "\.venv\Scripts\python.exe") Then
    pythonExe = """" & scriptDir & "\.venv\Scripts\python.exe"""
ElseIf fso.FileExists(scriptDir & "\venv\Scripts\python.exe") Then
    pythonExe = """" & scriptDir & "\venv\Scripts\python.exe"""
Else
    pythonExe = "pythonw"
End If

' Ejecutar con ventana oculta (0 = SW_HIDE, False = ejecucion asincrona en background)
On Error Resume Next
wshShell.Run pythonExe & " main.py --hud", 0, False

If Err.Number <> 0 Then
    ' Fallback con python estandar en modo oculto
    Err.Clear
    wshShell.Run "python main.py --hud", 0, False
End If
