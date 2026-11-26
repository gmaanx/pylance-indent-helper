@echo off
setlocal
py -3 -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 goto use_launcher

set "HELPER_PYTHON=%~dp0..\..\.venv\Scripts\python.exe"
if exist "%HELPER_PYTHON%" (
    "%HELPER_PYTHON%" -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
    if not errorlevel 1 goto use_sibling
)

python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 goto use_path_python

for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python313"
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "%LOCALAPPDATA%\Programs\Python\Python39"
    "%LOCALAPPDATA%\Programs\Python\Python38"
    "C:\Python313"
    "C:\Python312"
    "C:\Python311"
    "C:\Python310"
    "C:\Python39"
    "C:\Python38"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\miniconda3"
    "C:\ProgramData\Anaconda3"
    "C:\ProgramData\Miniconda3"
) do (
    if exist "%%~D\python.exe" (
        "%%~D\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
        if not errorlevel 1 (
            "%%~D\python.exe" %*
            exit /b %ERRORLEVEL%
        )
    )
)

echo Can Python 3.8 tro len.
exit /b 1

:use_path_python
python %*
exit /b %ERRORLEVEL%

:use_sibling
"%HELPER_PYTHON%" %*
exit /b %ERRORLEVEL%

:use_launcher
py -3 %*
exit /b %ERRORLEVEL%
