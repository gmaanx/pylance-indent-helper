@echo off
setlocal
if "%~1"=="" (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --profile full
) else (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" %*
)
exit /b %ERRORLEVEL%
