@echo off
REM ============================================================
REM  System AI - one-double-click installer (Windows)
REM ============================================================
cd /d "%~dp0"
echo.
echo ===== Installing System AI =====
echo.

echo [1/3] Installing core backend packages...
python -m pip install --upgrade pip
python -m pip install -r assistant\backend\requirements.txt
if errorlevel 1 (
  echo.
  echo ERROR: core install failed. Make sure Python is installed and on PATH.
  pause
  exit /b 1
)

echo.
echo [2/3] Installing voice packages ^(optional, large download^)...
echo     If this fails, the system still works - just without voice.
python -m pip install vosk openai-whisper sounddevice pyttsx3 numpy

echo.
echo [3/3] Installing dashboard ^(frontend^) packages...
cd dashboard
call npm install
cd ..

echo.
echo ============================================
echo  Installation complete!
echo  Double-click Start-System.bat to launch.
echo ============================================
pause
