Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Получаем директорию проекта (на уровень выше от license_generator)
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(scriptDir)

' Проверяем наличие виртуального окружения
venvPython = fso.BuildPath(projectDir, ".venv\Scripts\pythonw.exe")
guiScript = fso.BuildPath(scriptDir, "license_generator_gui.py")

' Устанавливаем рабочую директорию на проект
shell.CurrentDirectory = projectDir

' Запускаем GUI (0 = скрытое окно)
If fso.FileExists(venvPython) Then
    cmd = """" & venvPython & """ """ & guiScript & """"
Else
    cmd = "pythonw """ & guiScript & """"
End If

shell.Run cmd, 0, False

