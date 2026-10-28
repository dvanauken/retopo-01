@echo off
cd /d "%~dp0"
python -X utf8 server.py --restart --next-port %*
if errorlevel 1 pause
