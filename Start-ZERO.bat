@echo off
title Z.E.R.O
echo ============================================
echo   Z.E.R.O - launching desktop application
echo ============================================
echo.

cd /d "%~dp0frontend"

REM Build the UI bundle the first time (or after updates) if it's missing.
if not exist "dist\index.html" (
  echo Building the interface, one moment...
  call npm run build
)

echo Starting Z.E.R.O. The window will open shortly.
echo Keep this console open while you use the app; close it to shut Z.E.R.O down.
echo.

REM Launch the Electron desktop window. It boots the Python backend itself.
call npx electron .
