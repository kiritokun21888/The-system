@echo off
title Z.E.R.O
cd /d "%~dp0"

echo ================================================
echo    Z.E.R.O  -  launching
echo ================================================
echo.

REM --- 1. Start the Python backend (minimized window) ---
echo [1/3] Starting AI backend...
start "ZERO Backend" /min cmd /c "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe main.py"

REM --- 2. Start the UI server (minimized window) ---
echo [2/3] Starting interface server...
start "ZERO UI" /min cmd /c "cd /d ""%~dp0frontend"" && npm run dev"

REM --- 3. Wait for services, then open the app window ---
echo [3/3] Opening the Z.E.R.O window...
timeout /t 9 /nobreak >nul

set "URL=http://localhost:5173"
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"

if exist "%EDGE%" (
  start "" "%EDGE%" --app=%URL% --window-size=1480,920
) else if exist "%CHROME%" (
  start "" "%CHROME%" --app=%URL% --window-size=1480,920
) else (
  start "" %URL%
)

echo.
echo ------------------------------------------------
echo  Z.E.R.O is running in its own window.
echo.
echo  To shut it down: close the Z.E.R.O window, then
echo  close the two minimized windows in your taskbar
echo  ("ZERO Backend" and "ZERO UI").
echo ------------------------------------------------
echo.
echo You can close THIS window now.
