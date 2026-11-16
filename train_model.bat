@echo off
setlocal EnableDelayedExpansion
title EduVerify AI - Model Trainer
color 0B

echo ========================================================
echo        EduVerify AI - Forensic Model Training Pipeline  
echo ========================================================
echo.

:: Standardize path without trailing backslash
set "CURRENT_DIR=%~dp0"
if "%CURRENT_DIR:~-1%"=="\" set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

:: Locate project root
if exist "%CURRENT_DIR%\Deepfake\eduverify-ai\backend\evaluation\train_classifier.py" (
    set "PROJECT_DIR=%CURRENT_DIR%\Deepfake\eduverify-ai"
) else if exist "%CURRENT_DIR%\eduverify-ai\backend\evaluation\train_classifier.py" (
    set "PROJECT_DIR=%CURRENT_DIR%\eduverify-ai"
) else if exist "%CURRENT_DIR%\backend\evaluation\train_classifier.py" (
    set "PROJECT_DIR=%CURRENT_DIR%"
) else (
    echo [ERROR] Could not automatically locate the EduVerify AI evaluation directory!
    echo Checked from: %CURRENT_DIR%
    echo.
    pause
    exit /b 1
)

set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "EVAL_DIR=%BACKEND_DIR%\evaluation"

:: Locate Python virtualenv
if exist "%BACKEND_DIR%\venv_gpu\Scripts\python.exe" (
    set "PYTHON_EXE=%BACKEND_DIR%\venv_gpu\Scripts\python.exe"
    echo [INFO] Using GPU-accelerated environment: venv_gpu
) else if exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe"
    echo [INFO] Using virtual environment: venv
) else (
    set "PYTHON_EXE=python"
    echo [INFO] Using system Python on PATH
)

echo.
echo [1/2] Training Calibrated Feature Classifier on Benchmark Dataset...
echo ---------------------------------------------------------------------
"%PYTHON_EXE%" "%EVAL_DIR%\train_classifier.py"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Model training failed with error code %errorlevel%!
    pause
    exit /b %errorlevel%
)

echo.
echo [2/2] Updating Official Benchmark Metrics and Evaluation Report...
echo ---------------------------------------------------------------------
"%PYTHON_EXE%" "%EVAL_DIR%\calculate_metrics.py"

echo.
echo =====================================================================
echo [SUCCESS] Model training complete!
echo Exported to: %BACKEND_DIR%\models\visual_detector.joblib
echo Updated report: %EVAL_DIR%\evaluation_report.md
echo =====================================================================
echo.
pause
