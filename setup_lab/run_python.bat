@echo off
setlocal
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto use_launcher

set "HELPER_PYTHON=%~dp0..\..\.venv\Scripts\python.exe"
if exist "%HELPER_PYTHON%" (
    "%HELPER_PYTHON%" -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
    if not errorlevel 1 goto use_sibling
)

python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 (
    echo Can Python 3.10 tro len.
    exit /b 1
)
python %*
exit /b %ERRORLEVEL%

:use_sibling
"%HELPER_PYTHON%" %*
exit /b %ERRORLEVEL%

:use_launcher
py -3 %*
exit /b %ERRORLEVEL%
