@echo off
setlocal
if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" "%~dp0go_cai_dat.py"
) else (
    python "%~dp0go_cai_dat.py"
)
set "UNINSTALL_RESULT=%ERRORLEVEL%"
if not "%UNINSTALL_RESULT%"=="0" (
    echo Go cai dat chua hoan tat. Hay xem loi ben tren.
    pause
    exit /b %UNINSTALL_RESULT%
)
timeout /t 2 >nul
exit /b %UNINSTALL_RESULT%
