@echo off
setlocal
REM Ban sieu nhe (~397 MB) danh cho phong may truong co mang WiFi/LAN cham!
if exist "%~dp0setup_lab\wheels\simpleai-*.whl" (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --profile full --local --local-model qwen2.5-coder:0.5b %*
) else (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --local-shell --local-model qwen2.5-coder:0.5b %*
)
set "ERR=%ERRORLEVEL%"
echo %CMDCMDLINE% | findstr /i /c:"/c """"" >nul && (
    echo.
    if not "%ERR%"=="0" (
        echo [!] Co loi xay ra khi cai dat. Hay kiem tra mang Internet hoac thong bao phia tren.
    ) else (
        echo =====================================================================
        echo [HOAN TAT] Da tai xong ban sieu nhe 0.5b!
        echo            Neu VS Code dang mo, bam Ctrl+Shift+P -^> Reload Window!
        echo =====================================================================
    )
    pause
)
exit /b %ERR%
