' ACE Runtime - Windows Background Launcher
' Double-click to start Runtime silently in background
' Loads environment variables from ace_env.ps1 first

Option Explicit

Dim WShell, FSO, ScriptDir, Workspace, PythonExe, Cmd

Set WShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
Workspace = FSO.GetParentFolderName(ScriptDir)

' Find python.exe
PythonExe = "python"
On Error Resume Next
PythonExe = WShell.RegRead("HKLM\SOFTWARE\Python\PythonCore\3.11\InstallPath\ExecutablePath")
If Err.Number <> 0 Then
    Err.Clear
    PythonExe = WShell.RegRead("HKLM\SOFTWARE\Python\PythonCore\3.10\InstallPath\ExecutablePath")
End If
If Err.Number <> 0 Then
    Err.Clear
    PythonExe = WShell.RegRead("HKLM\SOFTWARE\Python\PythonCore\3.9\InstallPath\ExecutablePath")
End If
On Error GoTo 0

If PythonExe = "" Then PythonExe = "python"

' Forward credentials from the process environment. Never embed tokens here.
Dim BotToken, Topic, ChatId
BotToken = WShell.Environment("Process").Item("TG_BOT_TOKEN_2")
Topic = WShell.Environment("Process").Item("NTPY_TOPIC")
ChatId = WShell.Environment("Process").Item("TG_CHAT_ID")

' Build command - daemon mode, silent
Cmd = "cmd /c cd /d """ & Workspace & """"
If BotToken <> "" Then Cmd = Cmd & " && set TG_BOT_TOKEN_2=""" & BotToken & """"
If Topic <> "" Then Cmd = Cmd & " && set NTPY_TOPIC=""" & Topic & """"
If ChatId <> "" Then Cmd = Cmd & " && set TG_CHAT_ID=""" & ChatId & """"
Cmd = Cmd & "&& """ & PythonExe & """ 06_RUNTIME\core\runtime_main.py --daemon >nul 2>&1"

' Start silently (hidden window, 0 = hidden)
WShell.Run Cmd, 0, False

Set WShell = Nothing
Set FSO = Nothing
