Dim ruta
ruta = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Set WShell = CreateObject("WScript.Shell")
WShell.Run "cmd /c """ & ruta & "\iniciar_smic.bat""", 0, False
