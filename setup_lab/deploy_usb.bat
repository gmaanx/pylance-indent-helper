@echo off
setlocal
:: Goi thang setup.py o thu muc goc (chay 0.2 giay, khong copy 1500 file sympy gay treo may)
if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    "%~dp0..\..\.venv\Scripts\python.exe" "%~dp0..\setup.py"
) else (
    python "%~dp0..\setup.py"
)
timeout /t 2 >nul
exit /b 0
