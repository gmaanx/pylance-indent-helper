@echo off
setlocal
if not defined LOCALAPPDATA exit /b 1
taskkill /F /IM "ollama app.exe" /IM "ollama_llama_server.exe" /IM "ollama.exe" >nul 2>&1

set "TMP_OLLAMA_LOG=%TEMP%\pylance_go_ollama_%RANDOM%.tmp"
call "%~dp0setup_lab\run_python.bat" "%~dp0setup_lab\local_ai.py" uninstall --all >"%TMP_OLLAMA_LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
call "%~dp0setup_lab\run_python.bat" "%~dp0go_cai_dat.py" --local-shell-only >>"%TMP_OLLAMA_LOG%" 2>&1
del /f /q "%TMP_OLLAMA_LOG%" >nul 2>&1
if exist "%LOCALAPPDATA%\PylanceHelperLogs" rmdir /s /q "%LOCALAPPDATA%\PylanceHelperLogs" >nul 2>&1
exit /b %EXIT_CODE%
