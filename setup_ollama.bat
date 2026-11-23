@echo off
setlocal
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --local-shell %*
exit /b %ERRORLEVEL%
