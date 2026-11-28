@echo off
setlocal
REM Cai dat 1 cham cho may Phong Thi (Full thu vien Py3.8+ + Extension moi IDE + Tu chon Ollama theo RAM)
REM Co the truyen san API key: setup_phong_thi.bat --provider gemini --key AIza...
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --profile full --local --auto-model %*
set "ERR=%ERRORLEVEL%"
echo %CMDCMDLINE% | findstr /i /c:"/c """"" >nul && (
    echo.
    if "%ERR%"=="0" (
        echo =====================================================================
        echo [HOAN TAT 100%%] Neu VS Code dang mo san, bam Ctrl+Shift+P -^> Reload Window!
        echo =====================================================================
    )
    pause
)
exit /b %ERR%
