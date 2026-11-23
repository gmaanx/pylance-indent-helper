@echo off
setlocal
if not defined LOCALAPPDATA exit /b 1
set "HELPER_LOG_DIR=%LOCALAPPDATA%\PylanceHelperLogs"
if not exist "%HELPER_LOG_DIR%" mkdir "%HELPER_LOG_DIR%" >nul 2>&1

call "%~dp0setup_lab\run_python.bat" "%~dp0setup_lab\local_ai.py" uninstall >"%HELPER_LOG_DIR%\go_ollama.log" 2>&1
if errorlevel 1 exit /b %ERRORLEVEL%
call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" --local-shell-only >>"%HELPER_LOG_DIR%\go_ollama.log" 2>&1
exit /b %ERRORLEVEL%
