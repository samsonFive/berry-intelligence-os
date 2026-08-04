@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat

echo.
echo Starting Berry Intelligence OS...
echo Once you see "Application startup complete", open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C to stop the server.
echo.

uvicorn app.main:app --reload
pause
