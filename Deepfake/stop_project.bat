@echo off
title EduVerify AI - Stopper
color 0C

echo ========================================================
echo               EduVerify AI - Process Stopper            
echo ========================================================
echo.
echo Stopping any running backend (ports 8001, 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

echo Stopping any running frontend (port 5173)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

echo.
echo [DONE] Any active EduVerify AI servers have been terminated.
echo ========================================================
ping 127.0.0.1 -n 3 >nul
