Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Ultron\Ultron"
WshShell.Run """C:\Ultron\Ultron\.venv_win313\Scripts\pythonw.exe"" ""C:\Ultron\Ultron\desktop.py""", 0, False
Set WshShell = Nothing
