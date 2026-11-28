@echo off
setlocal
chcp 65001 >nul 2>&1
if exist "%~dp0setup.py" goto extracted_ok
echo [LOI] Ban dang bam chay truc tiep ben trong file nen ZIP!
echo       Hay giai nen (Extract All / WinRAR) ra thu muc roi bam chay lai setup.bat!
pause
exit /b 1

:extracted_ok
if not "%~1"=="" goto with_args
pushd "%~dp0" >nul 2>&1
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --interactive
set "ERR=%ERRORLEVEL%"
popd >nul 2>&1
echo.
if not "%ERR%"=="0" goto install_failed
echo =====================================================================
echo [HOAN TAT 100%%] Vao VS Code bam Ctrl+Shift+P --^> Reload Window la dung ngay!
echo =====================================================================
pause
exit /b 0

:install_failed
echo [!] Cai dat bao loi (ma %ERR%). Hay xem dong [LOI] phia tren!
pause
exit /b %ERR%

:with_args
pushd "%~dp0" >nul 2>&1
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" %*
set "ERR=%ERRORLEVEL%"
popd >nul 2>&1
exit /b %ERR%
