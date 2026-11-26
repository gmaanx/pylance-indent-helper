@echo off
setlocal
if "%~1"=="" (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --local-shell --auto-model
) else (
    call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --local-shell %*
)
exit /b %ERRORLEVEL%
