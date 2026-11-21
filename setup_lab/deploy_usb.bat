@echo off
setlocal
call "%~dp0..\setup_nhanh.bat" %*
exit /b %ERRORLEVEL%
