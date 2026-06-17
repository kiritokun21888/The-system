@echo off
REM ============================================================
REM  System AI - launches the backend engine + the dashboard.
REM  Two windows open. Keep both open while using the system.
REM ============================================================
cd /d "%~dp0"

echo Starting the backend engine...
start "System Backend" cmd /k "cd /d %~dp0assistant && python -m backend.main"

echo Waiting for the engine to come online...
timeout /t 4 /nobreak >nul

echo Starting the dashboard...
start "System Dashboard" cmd /k "cd /d %~dp0dashboard && npm run dev"

echo.
echo Both started. The dashboard will open in your browser shortly.
echo Close this window once they are running.
