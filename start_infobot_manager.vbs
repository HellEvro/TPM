Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
venvPython = fso.BuildPath(projectDir, ".venv\Scripts\pythonw.exe")
launcher = fso.BuildPath(projectDir, "launcher\infobot_manager.py")

' Функция проверки наличия команды
Function CommandExists(cmd)
    On Error Resume Next
    Dim exitCode
    If InStr(cmd, " ") > 0 Then
        ' Команда с параметрами - используем cmd /c
        exitCode = shell.Run("cmd /c " & cmd & " --version >nul 2>&1", 0, True)
    Else
        ' Простая команда
        exitCode = shell.Run("cmd /c """ & cmd & """ --version >nul 2>&1", 0, True)
    End If
    CommandExists = (exitCode = 0)
    On Error GoTo 0
End Function

' Проверка Python
pythonFound = False
If CommandExists("python") Then
    pythonFound = True
ElseIf CommandExists("py") Then
    pythonFound = True
ElseIf CommandExists("python3") Then
    pythonFound = True
End If

If Not pythonFound Then
    ' Попытка установки через winget
    wingetFound = CommandExists("winget")
    If wingetFound Then
        ' Тихая установка Python через winget
        shell.Run "winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements", 0, True
        ' Проверка после установки
        WScript.Sleep 2000
        If CommandExists("python") Or CommandExists("py") Then
            pythonFound = True
        End If
    End If
    
    ' Если Python всё ещё не найден - открываем страницу скачивания
    If Not pythonFound Then
        shell.Run "https://www.python.org/downloads/windows/", 1, False
        WScript.Quit 1
    End If
End If

' Проверка Git (только если Python установлен)
If Not CommandExists("git") Then
    wingetFound = CommandExists("winget")
    If wingetFound Then
        ' Тихая установка Git с максимальной интеграцией
        ' Параметры установщика Git передаются через --override
        ' /VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES
        ' /COMPONENTS=icons,ext\shellhere,assoc,assoc_sh /PATHOPTION=user /EDITOR=nano
        Dim gitParams
        gitParams = "/VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES /COMPONENTS=icons,ext\shellhere,assoc,assoc_sh /PATHOPTION=user /EDITOR=nano"
        shell.Run "winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements --override """ & gitParams & """", 0, True
    End If
End If

' Безопасная инициализация Git репозитория (если Git установлен)
If CommandExists("git") Then
    Dim gitDir
    gitDir = fso.BuildPath(projectDir, ".git")
    If Not fso.FolderExists(gitDir) Then
        ' Инициализируем репозиторий БЕЗ pull/fetch, чтобы не перезаписать существующие файлы
        shell.Run "cmd /c cd /d """ & projectDir & """ && git init", 0, True
        shell.Run "cmd /c cd /d """ & projectDir & """ && git branch -m main", 0, True
        ' Проверяем, есть ли уже remote origin
        Dim remoteCheck
        remoteCheck = shell.Run("cmd /c cd /d """ & projectDir & """ && git remote get-url origin >nul 2>&1", 0, True)
        If remoteCheck <> 0 Then
            ' Добавляем remote только если его нет
            shell.Run "cmd /c cd /d """ & projectDir & """ && git remote add origin git@github.com:HellEvro/TPM_Public.git", 0, True
        End If
    End If
End If

' Запуск приложения
If fso.FileExists(venvPython) Then
    cmd = """" & venvPython & """ """ & launcher & """"
Else
    ' Определяем Python для запуска
    Dim pythonCmd
    pythonCmd = ""
    If CommandExists("python") Then
        ' Проверяем наличие pythonw
        If shell.Run("cmd /c pythonw --version >nul 2>&1", 0, True) = 0 Then
            pythonCmd = "pythonw"
        Else
            pythonCmd = "python"
        End If
    ElseIf CommandExists("py") Then
        pythonCmd = "py -3"
    ElseIf CommandExists("python3") Then
        pythonCmd = "python3"
    End If
    
    If pythonCmd <> "" Then
        cmd = pythonCmd & " """ & launcher & """"
    Else
        ' Fallback
        cmd = "python """ & launcher & """"
    End If
End If

shell.CurrentDirectory = projectDir
shell.Run cmd, 0, False

