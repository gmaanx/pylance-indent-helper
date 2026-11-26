@echo off
setlocal
call "%~dp0setup_lab\run_python.bat" "%~dp0nhap_api_key.py" %*
set "API_TEST_EXIT=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %API_TEST_EXIT%
