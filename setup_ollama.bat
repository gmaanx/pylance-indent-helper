@echo off
setlocal
if "%~1"=="" (
    if exist "%~dp0setup_lab\wheels\simpleai-*.whl" (
        call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --profile full --local --auto-model
    ) else (
        call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --local-shell --auto-model
    )
) else (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --local-shell %*
)
set "ERR=%ERRORLEVEL%"
echo %CMDCMDLINE% | findstr /i /c:"/c """"" >nul && (
    echo.
    if not "%ERR%"=="0" (
        echo [!] Co loi xay ra khi cai dat. Hay kiem tra mang Internet hoac thong bao phia tren.
    ) else (
        echo =====================================================================
        echo [HOAN TAT] Neu VS Code dang mo san, hay bam Ctrl+Shift+P -^> Reload Window
        echo            de VS Code nhan ngay Ollama ^(Alt+5 / Alt+2^)!
        echo =====================================================================
    )
    pause
)
exit /b %ERR%
