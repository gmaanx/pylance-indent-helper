Option Explicit
Dim files, shell, bat
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
bat = files.BuildPath(files.GetParentFolderName(WScript.ScriptFullName), "go_cai_dat.bat")
WScript.Quit shell.Run(Chr(34) & bat & Chr(34), 0, True)
