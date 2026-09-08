' ACE Free Zone Daemon - Windows Background Launcher
' Double-click to start 24h continuous learning silently in background
'
' 自由区副本启动器：
' - 24h 持续运行
' - 零成本（只用免费 API）
' - 输出到 02_MEMORY/free_zone/
' - 每 8 小时 TG 心跳

Option Explicit

Dim WShell, FSO, ScriptDir, Workspace, PythonExe, Cmd

Set WShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
Workspace = FSO.GetParentFolderName(FSO.GetParentFolderName(ScriptDir))

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

' Read credentials from the process environment. Never embed secrets in launchers.
Dim GLMKey, NIMKey1, NIMKey2, NIMKey3, GHKey, TGBotToken, TGChatId
GLMKey = WShell.Environment("Process").Item("GLM_KEY")
NIMKey1 = WShell.Environment("Process").Item("NIM_KEY_1")
NIMKey2 = WShell.Environment("Process").Item("NIM_KEY_2")
NIMKey3 = WShell.Environment("Process").Item("NIM_KEY_3")
GHKey = WShell.Environment("Process").Item("GH_MODELS_KEY")
TGBotToken = WShell.Environment("Process").Item("TG_BOT_TOKEN_2")
TGChatId = WShell.Environment("Process").Item("TG_CHAT_ID")

' Build command
Cmd = "cmd /c cd /d """ & Workspace & """"
If GLMKey <> "" Then Cmd = Cmd & " && set GLM_KEY=""" & GLMKey & """"
If NIMKey1 <> "" Then Cmd = Cmd & " && set NIM_KEY_1=""" & NIMKey1 & """"
If NIMKey2 <> "" Then Cmd = Cmd & " && set NIM_KEY_2=""" & NIMKey2 & """"
If NIMKey3 <> "" Then Cmd = Cmd & " && set NIM_KEY_3=""" & NIMKey3 & """"
If GHKey <> "" Then Cmd = Cmd & " && set GH_MODELS_KEY=""" & GHKey & """"
If TGBotToken <> "" Then Cmd = Cmd & " && set TG_BOT_TOKEN_2=""" & TGBotToken & """"
If TGChatId <> "" Then Cmd = Cmd & " && set TG_CHAT_ID=""" & TGChatId & """"
Cmd = Cmd & "&& """ & PythonExe & """ 06_RUNTIME\free_zone\daemon.py --daemon >nul 2>&1"

' Start silently (hidden window, 0 = hidden)
WShell.Run Cmd, 0, False

Set WShell = Nothing
Set FSO = Nothing
