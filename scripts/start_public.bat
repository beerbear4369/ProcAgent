@echo off
echo ==========================================
echo    ProcAgent Public Server Startup
echo ==========================================
echo.

:: Activate conda base environment
call C:\ProgramData\Anaconda3\Scripts\activate.bat

:: Change to project directory
cd /d D:\dev\ProcAgent

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

:: Kill any existing websockify on port 6080
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :6080 ^| findstr LISTENING') do (
    echo [!] Killing existing process on port 6080...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
:: Check if TightVNC is already running
tasklist /FI "IMAGENAME eq tvnserver.exe" 2>NUL | find /I /N "tvnserver.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [1/5] TightVNC already running, skipping...
) else (
    echo [1/5] Starting TightVNC Server...
    start "" "C:\Program Files\TightVNC\tvnserver.exe" -run
    timeout /t 2 >nul
)

echo [2/5] Starting websockify (for noVNC)...
cd /d D:\dev\ProcAgent
start "ProcAgent-websockify" cmd /k "python -m websockify 6080 localhost:5900"
timeout /t 2 >nul

echo [3/5] Starting FastAPI server...
cd /d D:\dev\ProcAgent
start "ProcAgent-FastAPI" cmd /k "python -m procagent.server.app"
timeout /t 3 >nul

echo [4/5] Starting nginx...
cd /d C:\nginx
start "" nginx.exe
timeout /t 2 >nul

echo [5/5] Getting public IP...
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
