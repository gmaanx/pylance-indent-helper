@echo off
setlocal
if "%~1"=="" (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --profile full
) else (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" %*
)
set "ERR=%ERRORLEVEL%"
echo %CMDCMDLINE% | findstr /i /c:"/c """"" >nul && (
    echo.
    if "%ERR%"=="0" (
        echo [HOAN TAT] Neu VS Code dang mo san, hay bam Ctrl+Shift+P -^> Reload Window!
    )
    pause
)
exit /b %ERR%
