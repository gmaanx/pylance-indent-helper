@echo off
setlocal
call "%~dp0..\setup.bat" %*
exit /b %ERRORLEVEL%
