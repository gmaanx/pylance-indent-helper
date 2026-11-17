@echo off
setlocal
:: Dung chung trinh go va giu nguyen ma loi khi go that bai.
call "%~dp0..\go_cai_dat.bat"
exit /b %ERRORLEVEL%
