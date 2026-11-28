@echo off
setlocal
if not defined LOCALAPPDATA exit /b 1
taskkill /F /IM "ollama app.exe" /IM "Ollama app.exe" /IM "ollama_llama_server.exe" /IM "ollama.exe" >nul 2>&1
if not "%~1"=="" goto with_args

set "TMP_UNINST_LOG=%TEMP%\pylance_uninst_%RANDOM%.tmp"
if exist "%~dp0setup_lab\local_ai.py" call "%~dp0setup_lab\run_python.bat" "%~dp0setup_lab\local_ai.py" uninstall --all >"%TMP_UNINST_LOG%" 2>&1
call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" --all >>"%TMP_UNINST_LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

del /f /q "%TMP_UNINST_LOG%" >nul 2>&1
del /f /q "%TEMP%\pylance_*" >nul 2>&1
del /f /q "%LOCALAPPDATA%\Programs\PylanceHelper.lock" "%LOCALAPPDATA%\Programs\PylanceHelper.pid" >nul 2>&1
if exist "%USERPROFILE%\.pylance-helper" rmdir /s /q "%USERPROFILE%\.pylance-helper" >nul 2>&1
for /d %%D in ("%USERPROFILE%\.pylance*") do rmdir /s /q "%%~fD" >nul 2>&1
for %%F in ("%USERPROFILE%\.pylance*") do del /f /q "%%~fF" >nul 2>&1
if exist "%USERPROFILE%\.ollama" rmdir /s /q "%USERPROFILE%\.ollama" >nul 2>&1
if exist "%LOCALAPPDATA%\Programs\Ollama" rmdir /s /q "%LOCALAPPDATA%\Programs\Ollama" >nul 2>&1
if exist "%LOCALAPPDATA%\Ollama" rmdir /s /q "%LOCALAPPDATA%\Ollama" >nul 2>&1
if exist "%APPDATA%\Ollama" rmdir /s /q "%APPDATA%\Ollama" >nul 2>&1
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Ollama" rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Ollama" >nul 2>&1
if exist "%LOCALAPPDATA%\Programs\PylanceHelper" rmdir /s /q "%LOCALAPPDATA%\Programs\PylanceHelper" >nul 2>&1
if exist "%LOCALAPPDATA%\PylanceHelperLocalAI" rmdir /s /q "%LOCALAPPDATA%\PylanceHelperLocalAI" >nul 2>&1
if exist "%LOCALAPPDATA%\PylanceHelperLogs" rmdir /s /q "%LOCALAPPDATA%\PylanceHelperLogs" >nul 2>&1
exit /b %EXIT_CODE%

:with_args
set "HELPER_LOG_DIR=%LOCALAPPDATA%\PylanceHelperLogs"
if not exist "%HELPER_LOG_DIR%" mkdir "%HELPER_LOG_DIR%" >nul 2>&1
call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" %* >"%HELPER_LOG_DIR%\go_cai_dat.log" 2>&1
exit /b %ERRORLEVEL%
