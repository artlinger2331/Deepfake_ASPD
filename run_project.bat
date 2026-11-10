@echo off
setlocal EnableDelayedExpansion
title EduVerify AI - Quick Launcher
color 0A

echo ========================================================
echo               EduVerify AI - Quick Launcher             
echo ========================================================
echo.

:: Standardize path without trailing backslash
set "CURRENT_DIR=%~dp0"
if "%CURRENT_DIR:~-1%"=="\" set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

:: Locate project root
if exist "%CURRENT_DIR%\Deepfake\eduverify-ai\backend\main.py" (
    set "PROJECT_DIR=%CURRENT_DIR%\Deepfake\eduverify-ai"
) else if exist "%CURRENT_DIR%\eduverify-ai\backend\main.py" (
    set "PROJECT_DIR=%CURRENT_DIR%\eduverify-ai"
) else if exist "%CURRENT_DIR%\backend\main.py" (
    set "PROJECT_DIR=%CURRENT_DIR%"
) else (
    echo [ERROR] Could not automatically locate the EduVerify AI project directory!
    echo Checked from: %CURRENT_DIR%
    echo.
    pause
    exit /b 1
)

set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIR=%PROJECT_DIR%"

:: 1. Clear any dangling processes on ports 8000 and 5173
echo [1/4] Ensuring ports 8000 and 5173 are free...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%a >nul 2>&1
)

:: 2. Pre-flight Node & Frontend Check
echo [2/4] Checking Node.js and Frontend dependencies...
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm is not installed or not in your system PATH!
    pause
    exit /b 1
)
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [WARN] node_modules not found in %FRONTEND_DIR%.
    echo Installing npm dependencies...
    cd /d "%FRONTEND_DIR%" && npm install
)

:: 3. Detect Python Environment
echo [3/4] Detecting Python environment...
if exist "%BACKEND_DIR%\venv_gpu\Scripts\python.exe" (
    set "VENV_DIR=%BACKEND_DIR%\venv_gpu"
    echo       Found GPU environment: venv_gpu
) else if exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    set "VENV_DIR=%BACKEND_DIR%\venv"
    echo       Found standard environment: venv
) else (
    set "VENV_DIR="
    echo       Using system Python
)

:: 4. Launch Backend & Frontend
echo.
echo [4/4] Launching Servers...
if defined VENV_DIR (
    start "EduVerify AI - Backend (FastAPI)" /D "%BACKEND_DIR%" cmd /k "call "%VENV_DIR%\Scripts\activate.bat" && title EduVerify AI - Backend && color 0B && echo ==================================================== && echo               EduVerify AI - Backend Server          && echo ==================================================== && echo Running on: http://localhost:8000 && echo Docs:       http://localhost:8000/docs && echo. && uvicorn main:app --port 8000 --reload"
) else (
    start "EduVerify AI - Backend (FastAPI)" /D "%BACKEND_DIR%" cmd /k "title EduVerify AI - Backend && color 0B && echo ==================================================== && echo               EduVerify AI - Backend Server          && echo ==================================================== && echo Running on: http://localhost:8000 && echo Docs:       http://localhost:8000/docs && echo. && python -m uvicorn main:app --port 8000 --reload"
)

start "EduVerify AI - Frontend (React + Vite)" /D "%FRONTEND_DIR%" cmd /k "title EduVerify AI - Frontend && color 0D && echo ==================================================== && echo               EduVerify AI - Frontend Server         && echo ==================================================== && echo Running on: http://localhost:5173 && echo. && npm run dev"

echo.
echo ========================================================
echo Both servers are launching in separate windows!
echo Waiting for servers to initialize...
echo ========================================================
ping 127.0.0.1 -n 6 >nul

echo Opening browser at http://localhost:5173 ...
start http://localhost:5173

echo.
echo ========================================================
echo [SUCCESS] EduVerify AI is up and running!
echo.
echo  * Frontend:  http://localhost:5173
echo  * Backend:   http://localhost:8000
echo  * API Docs:  http://localhost:8000/docs
echo.
echo  Tip: To stop the servers later, simply run stop_project.bat
echo       or close the Backend and Frontend console windows.
echo ========================================================
echo.
pause
