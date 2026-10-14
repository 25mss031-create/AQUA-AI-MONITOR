@echo off
cd /d "%~dp0"
echo Starting AQUA AI Monitor backend...
start "AQUA backend" cmd /k python run.py
timeout /t 5 >nul
echo Opening dashboard in the default browser...
start "" http://localhost:8000
echo Starting ESP32 sensor simulator (no hardware needed)...
start "AQUA simulator" cmd /k python -m backend.simulator --detections
echo.
echo Demo is running: dashboard at http://localhost:8000
echo Close the two windows to stop, or press Ctrl+C in them.
pause
