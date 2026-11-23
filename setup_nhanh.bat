@echo off
setlocal
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" %*
exit /b %ERRORLEVEL%
