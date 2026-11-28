@echo off
setlocal

set "HELPER_PYTHON=%~dp0..\..\.venv\Scripts\python.exe"
if not exist "%HELPER_PYTHON%" goto try_py_win32
"%HELPER_PYTHON%" -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 goto use_sibling

:try_py_win32
py -3 -c "import sys; b = getattr(sys, '_base_executable', ''); sys.exit(sys.version_info < (3, 8) or 'WindowsApps' in b)" >nul 2>&1
if not errorlevel 1 goto use_launcher

set "FOUND_PY="
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
    "D:\Python313"
    "D:\Python312"
    "D:\Python311"
    "D:\Python310"
    "D:\Python39"
    "D:\Python38"
    "C:\msys64\ucrt64\bin"
    "C:\msys64\mingw64\bin"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\miniconda3"
    "C:\ProgramData\Anaconda3"
    "C:\ProgramData\Miniconda3"
) do call :probe_candidate "%%~D\python.exe"
if defined FOUND_PY goto use_found

py -3 -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 goto use_launcher

for /f "delims=" %%P in ('where python.exe 2^>nul') do call :probe_candidate "%%~P"
if defined FOUND_PY goto use_found

python -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 goto use_path_python

echo [LOI] Khong tim thay Python 3.8 tro len tren may nay. Hay cai Python truoc!
exit /b 1

:probe_candidate
if defined FOUND_PY exit /b 0
if not exist "%~1" exit /b 1
"%~1" -c "import sys; sys.exit(sys.version_info < (3, 8))" >nul 2>&1
if not errorlevel 1 set "FOUND_PY=%~1"
exit /b 0

:use_found
"%FOUND_PY%" %*
exit /b %ERRORLEVEL%

:use_path_python
python %*
exit /b %ERRORLEVEL%

:use_sibling
"%HELPER_PYTHON%" %*
exit /b %ERRORLEVEL%

:use_launcher
py -3 %*
exit /b %ERRORLEVEL%
