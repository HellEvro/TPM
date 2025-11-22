afSet fso = CreateObject("Scripting.FileSystemObject")
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

' Функция проверки версии Python (должна быть >= 3.13)
Function CheckPythonVersion()
    On Error Resume Next
    Dim versionOutput, versionParts, major, minor
    Dim pythonCmd
    
    ' Пробуем разные команды для получения версии
    If CommandExists("python") Then
        pythonCmd = "python"
    ElseIf CommandExists("py") Then
        pythonCmd = "py -3"
    ElseIf CommandExists("python3") Then
        pythonCmd = "python3"
    Else
        CheckPythonVersion = False
        Exit Function
    End If
    
    ' Получаем версию Python
    Dim wshExec
    Set wshExec = shell.Exec("cmd /c " & pythonCmd & " --version")
    versionOutput = wshExec.StdOut.ReadAll
    Set wshExec = Nothing
    
    ' Парсим версию (формат: Python 3.13.0)
    If InStr(versionOutput, "Python") > 0 Then
        versionParts = Split(versionOutput, " ")
        If UBound(versionParts) >= 1 Then
            Dim versionStr
            versionStr = versionParts(1)
            versionParts = Split(versionStr, ".")
            If UBound(versionParts) >= 1 Then
                major = CInt(versionParts(0))
                minor = CInt(versionParts(1))
                ' Проверяем версию >= 3.13
                If major > 3 Or (major = 3 And minor >= 13) Then
                    CheckPythonVersion = True
                    Exit Function
                End If
            End If
        End If
    End If
    
    CheckPythonVersion = False
    On Error GoTo 0
End Function

' Проверка Python
pythonFound = False
If CommandExists("python") Or CommandExists("py") Or CommandExists("python3") Then
    If CheckPythonVersion() Then
        pythonFound = True
    End If
End If

If Not pythonFound Then
    ' Попытка установки через winget
    wingetFound = CommandExists("winget")
    If wingetFound Then
        ' Тихая установка Python 3.13 через winget
        shell.Run "winget install --id Python.Python.3.13 --silent --accept-package-agreements --accept-source-agreements", 0, True
        ' Проверка после установки
        WScript.Sleep 3000
        If CheckPythonVersion() Then
            pythonFound = True
        End If
    End If
    
    ' Если Python всё ещё не найден или версия < 3.13 - открываем страницу скачивания
    If Not pythonFound Then
        shell.Run "https://www.python.org/downloads/windows/", 1, False
        WScript.Quit 1
    End If
End If

' Функция проверки установки Git через стандартные пути
Function GitInstalled()
    On Error Resume Next
    Dim gitPaths
    gitPaths = Array("C:\Program Files\Git\cmd\git.exe", "C:\Program Files (x86)\Git\cmd\git.exe", "C:\Program Files\Git\bin\git.exe")
    Dim i
    For i = 0 To UBound(gitPaths)
        If fso.FileExists(gitPaths(i)) Then
            GitInstalled = True
            Exit Function
        End If
    Next
    ' Проверяем через команду git
    If CommandExists("git") Then
        GitInstalled = True
        Exit Function
    End If
    GitInstalled = False
    On Error GoTo 0
End Function

' Проверка Git (только если Python установлен)
' Сначала проверяем, установлен ли Git
Dim gitCheckResult
gitCheckResult = GitInstalled()
If Not gitCheckResult Then
    ' Git не найден - пытаемся установить
    wingetFound = CommandExists("winget")
    If wingetFound Then
        ' Выводим сообщение об установке Git (показываем на 3 секунды)
        shell.Run "cmd /c echo [INFO] Установка Git через winget... && timeout /t 3 >nul", 1, True
        ' Тихая установка Git с максимальной интеграцией
        ' Параметры установщика Git передаются через --override
        ' /VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES
        ' /COMPONENTS=icons,ext\shellhere,assoc,assoc_sh /PATHOPTION=user /EDITOR=nano
        Dim gitParams
        gitParams = "/VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES /COMPONENTS=icons,ext\shellhere,assoc,assoc_sh /PATHOPTION=user /EDITOR=nano"
        ' Запускаем установку Git (скрыто, но ждем завершения)
        shell.Run "winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements --override """ & gitParams & """", 0, True
        ' Ждем завершения установки (winget может установить Git в фоне)
        WScript.Sleep 12000
        ' Проверяем установку через стандартные пути
        If Not GitInstalled() Then
            ' Если Git все еще не найден, ждем еще немного
            WScript.Sleep 5000
            ' Повторная проверка
            If Not GitInstalled() Then
                ' Последняя попытка - проверяем через команду git
                WScript.Sleep 3000
            End If
        End If
    End If
End If

' Безопасная инициализация Git репозитория (если Git установлен)
If GitInstalled() Then
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
