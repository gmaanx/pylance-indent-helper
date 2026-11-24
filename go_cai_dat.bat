@echo off
setlocal
if not defined LOCALAPPDATA exit /b 1
set "HELPER_LOG_DIR=%LOCALAPPDATA%\PylanceHelperLogs"
if not exist "%HELPER_LOG_DIR%" mkdir "%HELPER_LOG_DIR%" >nul 2>&1
if "%~1"=="" (
    call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" --all >"%HELPER_LOG_DIR%\go_cai_dat.log" 2>&1
) else (
    call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" %* >"%HELPER_LOG_DIR%\go_cai_dat.log" 2>&1
)
exit /b %ERRORLEVEL%
