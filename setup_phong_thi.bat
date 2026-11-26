@echo off
setlocal
REM Cai dat 1 cham cho may Phong Thi (Full thu vien Py3.8+ + Extension IDE + Tu chon Ollama theo RAM)
REM Co the truyen san API key: setup_phong_thi.bat --provider gemini --key AIza...
call "%~dp0setup_lab\run_python.bat" "%~dp0setup.py" --profile full --local --auto-model %*
exit /b %ERRORLEVEL%
