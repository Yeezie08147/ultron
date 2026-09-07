Set WshShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath
WshShell.Run chr(34) & strPath & "\.venv_win313\Scripts\pythonw.exe" & chr(34) & " desktop.py --stealth", 0, False
WScript.Sleep 2000
If CreateObject("Scripting.FileSystemObject").FileExists("C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") Then
    WshShell.Run """C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"" --app=http://127.0.0.1:8340 --start-maximized", 1, False
Else
    WshShell.Run "http://127.0.0.1:8340", 1, False
End If
Set WshShell = Nothing
