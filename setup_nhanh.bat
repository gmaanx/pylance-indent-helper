@echo off
setlocal
:: Setup sieu toc 0.2 giay - Khong treo man hinh den - Khong can USB
if exist "%~dp0..\.venv\Scripts\python.exe" (
    "%~dp0..\.venv\Scripts\python.exe" "%~dp0setup.py"
) else (
    python "%~dp0setup.py"
)
timeout /t 2 >nul
exit /b 0
