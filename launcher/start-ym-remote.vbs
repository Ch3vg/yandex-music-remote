Set shell = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
launcherDir = fso.GetParentFolderName(WScript.ScriptFullName)
root = fso.GetParentFolderName(launcherDir)
ps1 = root & "\start-ym-remote.ps1"
shell.Run "powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File """ & ps1 & """", 0, False
