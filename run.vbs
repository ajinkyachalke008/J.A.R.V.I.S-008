Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run "cmd.exe /c "".venv\Scripts\python.exe"" main.py > vbs_error.log 2>&1", 0, False
