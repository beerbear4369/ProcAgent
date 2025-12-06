@echo off
echo ==========================================
echo    ProcAgent Public Server Startup
echo ==========================================
echo.

:: Activate conda base environment
call C:\ProgramData\Anaconda3\Scripts\activate.bat

:: Change to project directory
cd /d D:\dev\ProcAgent-nginx

:: Check if nginx is already running
tasklist /FI "IMAGENAME eq nginx.exe" 2>NUL | find /I /N "nginx.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [!] nginx already running, restarting...
    cd /d C:\nginx
    nginx.exe -s quit
    timeout /t 2 >nul
)

:: Kill any existing Python server on port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo [!] Killing existing process on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo [1/3] Starting FastAPI server...
cd /d D:\dev\ProcAgent-nginx
start "ProcAgent-FastAPI" cmd /k "python -m procagent.server.app"
timeout /t 3 >nul

echo [2/3] Starting nginx...
cd /d C:\nginx
start "" nginx.exe
timeout /t 2 >nul

echo [3/3] Getting public IP...
echo.
for /f %%i in ('curl -s ifconfig.me') do set PUBLIC_IP=%%i

echo ==========================================
echo    Server is running!
echo ==========================================
echo.
echo   Public URL:  http://%PUBLIC_IP%/
echo   Local URL:   http://localhost/
echo.
echo   Login: Check config/settings.yaml
echo.
echo ==========================================
echo.
echo Press any key to exit (servers will keep running)
pause >nul
