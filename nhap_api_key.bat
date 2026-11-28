@echo off
setlocal
if exist "%~dp0nhap_api_key.py" goto extracted_ok
echo [LOI] Ban dang bam chay truc tiep ben trong file nen ZIP!
echo       Hay giai nen (Extract All / WinRAR) ra thu muc roi bam chay lai file .bat nay!
pause
exit /b 1

:extracted_ok
if not "%~1"=="" goto with_args
call "%~dp0setup_lab\run_python.bat" "%~dp0nhap_api_key.py"
set "API_TEST_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %API_TEST_EXIT%

:with_args
call "%~dp0setup_lab\run_python.bat" "%~dp0nhap_api_key.py" %*
exit /b %ERRORLEVEL%
