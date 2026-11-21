@echo off
setlocal
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto use_sibling
py -3 "%~dp0go_cai_dat.py"
goto finished

:use_sibling
set "HELPER_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%HELPER_PYTHON%" goto use_python
"%HELPER_PYTHON%" -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto use_python
"%HELPER_PYTHON%" "%~dp0go_cai_dat.py"
goto finished

:use_python
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto python_missing
python "%~dp0go_cai_dat.py"
goto finished

:python_missing
echo Can Python 3.10 tro len de go cai dat.
pause
exit /b 1

:finished
set "UNINSTALL_RESULT=%ERRORLEVEL%"
if not "%UNINSTALL_RESULT%"=="0" (
    echo Go cai dat chua hoan tat. Hay xem loi ben tren.
    pause
    exit /b %UNINSTALL_RESULT%
)
timeout /t 2 >nul
exit /b %UNINSTALL_RESULT%
