@echo off
setlocal EnableDelayedExpansion
title EduVerify AI - Quick Launcher
color 0A

echo ========================================================
echo               EduVerify AI - Quick Launcher             
echo ========================================================
echo.

:: Detect project directory based on script location
set "CURRENT_DIR=%~dp0"

if exist "%CURRENT_DIR%Deepfake\eduverify-ai\backend\main.py" (
    set "PROJECT_DIR=%CURRENT_DIR%Deepfake\eduverify-ai"
) else if exist "%CURRENT_DIR%eduverify-ai\backend\main.py" (
    set "PROJECT_DIR=%CURRENT_DIR%eduverify-ai"
) else if exist "%CURRENT_DIR%backend\main.py" (
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

echo [1/3] Detecting Python environment...
if exist "%BACKEND_DIR%\venv_gpu\Scripts\python.exe" (
    set "PYTHON_EXE=%BACKEND_DIR%\venv_gpu\Scripts\python.exe"
    echo       Found GPU environment: venv_gpu
) else if exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe"
    echo       Found standard environment: venv
) else (
    set "PYTHON_EXE=python"
    echo       Using system Python
)

echo.
echo [2/3] Starting FastAPI Backend on http://localhost:8000 ...
start "EduVerify AI - Backend (FastAPI)" cmd /k "cd /d "%BACKEND_DIR%" && title EduVerify AI - Backend && color 0B && echo ==================================================== && echo               EduVerify AI - Backend Server          && echo ==================================================== && echo Running on: http://localhost:8000 && echo Docs:       http://localhost:8000/docs && echo. && "%PYTHON_EXE%" -m uvicorn main:app --port 8000 --reload"

echo.
echo [3/3] Starting Vite Frontend on http://localhost:5173 ...
start "EduVerify AI - Frontend (React + Vite)" cmd /k "cd /d "%FRONTEND_DIR%" && title EduVerify AI - Frontend && color 0D && echo ==================================================== && echo               EduVerify AI - Frontend Server         && echo ==================================================== && echo Running on: http://localhost:5173 && echo. && npm run dev"

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
