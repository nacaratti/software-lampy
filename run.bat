@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Lampy - Fiber Laser Studio
echo ============================================

REM --- 1. Python venv -------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [1/4] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create venv. Is Python 3.10+ installed and on PATH?
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment found.
)

REM --- 2. Backend dependencies -----------------------------------------
if not exist "venv\lampy_installed.marker" (
    echo [2/4] Installing backend dependencies (first run only)...
    venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo Failed to install Python dependencies.
        pause
        exit /b 1
    )
    echo done > venv\lampy_installed.marker
) else (
    echo [2/4] Backend dependencies already installed.
)

REM --- 3. Frontend build ------------------------------------------------
REM Rebuild whenever frontend sources are newer than the last build, so the
REM UI served on :8000 never lags behind the code (dist/ used to be built once
REM and then reused forever).
set "NEED_BUILD=0"
if not exist "frontend\dist\index.html" set "NEED_BUILD=1"
if "!NEED_BUILD!"=="0" (
    for /f %%R in ('powershell -NoProfile -Command "$b=(Get-Item 'frontend\dist\index.html').LastWriteTime; $s=Get-ChildItem 'frontend\src','frontend\index.html','frontend\package.json','frontend\vite.config.ts' -Recurse -File | Where-Object { $_.LastWriteTime -gt $b } | Select-Object -First 1; if ($s) { 1 } else { 0 }"') do set "NEED_BUILD=%%R"
)
if "!NEED_BUILD!"=="1" (
    echo [3/4] Building frontend...
    if not exist "frontend
ode_modules" (
        call npm install --prefix frontend
        if errorlevel 1 (
            echo Failed to install frontend dependencies. Is Node.js installed?
            pause
            exit /b 1
        )
    )
    call npm run build --prefix frontend
    if errorlevel 1 (
        echo Frontend build failed.
        pause
        exit /b 1
    )
) else (
    echo [3/4] Frontend build is up to date.
)

REM --- 4. Launch ---------------------------------------------------------
echo [4/4] Starting Lampy on http://localhost:8000 ...
start "" http://localhost:8000
venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

pause
