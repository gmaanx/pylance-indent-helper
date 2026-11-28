@echo off
setlocal
if not defined LOCALAPPDATA exit /b 1
if not "%~1"=="" goto with_args

set "TMP_UNINST_LOG=%TEMP%\pylance_uninst_%RANDOM%.tmp"
call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" --all >"%TMP_UNINST_LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
del /f /q "%TMP_UNINST_LOG%" >nul 2>&1
if exist "%LOCALAPPDATA%\PylanceHelperLogs" rmdir /s /q "%LOCALAPPDATA%\PylanceHelperLogs" >nul 2>&1
exit /b %EXIT_CODE%

:with_args
set "HELPER_LOG_DIR=%LOCALAPPDATA%\PylanceHelperLogs"
if not exist "%HELPER_LOG_DIR%" mkdir "%HELPER_LOG_DIR%" >nul 2>&1
call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" %* >"%HELPER_LOG_DIR%\go_cai_dat.log" 2>&1
exit /b %ERRORLEVEL%
