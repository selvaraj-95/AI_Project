@echo off
echo =======================================================================
echo   Starting GenAI - Enterprise Risk Intelligence Assistant (ERM Portal)
echo =======================================================================
echo.
cd /d "%~dp0"
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload
pause
