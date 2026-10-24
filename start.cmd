@echo off
cd /d "%~dp0"
python -X utf8 server.py %*
if errorlevel 1 pause
