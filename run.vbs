Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\AJINKYA CHALKE\AI\Mark-LVI"
WshShell.Run "cmd.exe /c "".venv\Scripts\python.exe"" main.py > vbs_error.log 2>&1", 0, False
