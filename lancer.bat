@echo off
cd /d "%~dp0"
set "PYTHON=python"
if exist "..\.venv\Scripts\python.exe" set "PYTHON=..\.venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
echo VoiceScope AI : http://localhost:8000  (Ctrl+C pour arreter)
"%PYTHON%" -m uvicorn server:app --host 127.0.0.1 --port 8000
pause
