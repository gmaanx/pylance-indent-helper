@echo off
setlocal
python "%~dp0nhap_api_key.py" %*
set "API_TEST_EXIT=%ERRORLEVEL%"
pause
exit /b %API_TEST_EXIT%
