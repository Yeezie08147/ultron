Set WshShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath
WshShell.Run chr(34) & strPath & "\.venv_win313\Scripts\pythonw.exe" & chr(34) & " desktop.py", 0, False
Set WshShell = Nothing
