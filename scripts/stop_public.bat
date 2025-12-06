@echo off
echo Stopping ProcAgent services...

:: Stop nginx
cd /d C:\nginx
nginx.exe -s quit 2>nul
echo [x] nginx stopped

:: Kill Python server
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo [x] FastAPI stopped

echo.
echo All services stopped.
pause
