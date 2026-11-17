@echo off
setlocal
if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" "%~dp0nhap_api_key.py"
) else (
    python "%~dp0nhap_api_key.py"
)
pause
