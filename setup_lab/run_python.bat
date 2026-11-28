@echo off
setlocal

REM 1. Uu tien ban cai Python Win32 chuan (tranh Microsoft Store WindowsApps MSIX ao hoa AppData)
set "HELPER_PYTHON=%~dp0..\..\.venv\Scripts\python.exe"
if exist "%HELPER_PYTHON%" (
    "%HELPER_PYTHON%" -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
    if not errorlevel 1 goto use_sibling
)

py -3 -c "import sys; b = getattr(sys, '_base_executable', ''); sys.exit(sys.version_info < (3, 8) or 'WindowsApps' in b)" >nul 2>&1
if not errorlevel 1 goto use_launcher

for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python313"
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "%LOCALAPPDATA%\Programs\Python\Python39"
    "%LOCALAPPDATA%\Programs\Python\Python38"
    "C:\Program Files\Python313"
    "C:\Program Files\Python312"
    "C:\Program Files\Python311"
    "C:\Program Files\Python310"
    "C:\Program Files\Python39"
    "C:\Program Files\Python38"
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

REM 2. Du phong: py launcher hoac python trong PATH (ke ca Microsoft Store Python da duoc ho tro ~/.pylance-helper)
py -3 -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 goto use_launcher

python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 goto use_path_python

echo [LOI] Can cai Python 3.8 tro len tren may.
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
