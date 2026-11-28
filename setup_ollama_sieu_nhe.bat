@echo off
setlocal
if exist "%~dp0setup.py" goto extracted_ok
echo [LOI] Ban dang bam chay truc tiep ben trong file nen ZIP!
echo       Hay giai nen (Extract All / WinRAR) ra thu muc roi bam chay lai file .bat nay!
pause
exit /b 1

:extracted_ok
if not "%~1"=="" goto with_args
pushd "%~dp0" >nul 2>&1
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --profile full --local --local-model qwen2.5-coder:0.5b
set "ERR=%ERRORLEVEL%"
popd >nul 2>&1
echo.
if not "%ERR%"=="0" goto install_failed
echo =====================================================================
echo [HOAN TAT 100%%] Da cai xong ban sieu nhe 0.5b!
echo                  Vao VS Code bam Ctrl+Shift+P --^> Reload Window la dung ngay!
echo =====================================================================
pause
exit /b 0

:install_failed
echo [!] Cai dat bao loi (ma %ERR%). Hay xem dong [LOI] mau trang phia tren!
pause
exit /b %ERR%

:with_args
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --local-shell --local-model qwen2.5-coder:0.5b %*
exit /b %ERRORLEVEL%
