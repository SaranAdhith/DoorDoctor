@echo off
REM ---------------------------------------------------------------------------
REM  DoorDoctor - start everything for local development (Windows).
REM
REM  Double-click this file. It:
REM    1. starts LM Studio's server (for Chandra OCR), if LM Studio is installed
REM    2. seeds the demo database the first time (backend\doordoc.db)
REM    3. opens the backend   (http://localhost:8000)  in its own window
REM    4. opens the frontend  (http://localhost:5173)  in its own window
REM    5. opens the app in your browser once it answers
REM
REM  Close the two server windows to stop the app.
REM  Logins: family@ / nurse@ / admin@doordoctor.in   password: Demo@123
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
title DoorDoctor launcher

if not exist "backend\.venv\Scripts\python.exe" (
  echo [!] backend\.venv is missing. Create it once with:
  echo       cd backend ^&^& py -3.12 -m venv .venv ^&^& .venv\Scripts\python -m pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo [!] frontend\node_modules is missing. Install it once with:
  echo       cd frontend ^&^& npm ci
  pause
  exit /b 1
)

REM --- 1. LM Studio (optional: without it, scanned pages wait for manual entry) ---
set "LMS=%USERPROFILE%\.lmstudio\bin\lms.exe"
if exist "%LMS%" (
  echo [1/4] Starting LM Studio server for Chandra OCR...
  "%LMS%" server start >nul 2>&1
  if errorlevel 1 (
    echo       LM Studio did not start. Open LM Studio once, then run this again.
    echo       The app still works; scanned pages will be marked for manual entry.
  ) else (
    echo       LM Studio server is up on port 1234. Chandra loads on the first page.
  )
) else (
  echo [1/4] LM Studio not found - OCR is off. Typed PDFs still work.
)

REM --- 2. The demo database, first run only ---
if not exist "backend\doordoc.db" (
  echo [2/4] First run: seeding the demo database...
  pushd backend
  .venv\Scripts\python.exe -m app.seed
  popd
) else (
  echo [2/4] Database found.
)

REM --- 3 and 4. The two servers, each in its own window ---
echo [3/4] Starting the backend on http://localhost:8000 ...
start "DoorDoctor backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

echo [4/4] Starting the frontend on http://localhost:5173 ...
start "DoorDoctor frontend" /D "%~dp0frontend" cmd /k "npm run dev -- --port 5173 --strictPort"

REM --- Open the browser once the frontend answers (up to ~150 s) ---
echo Waiting for the app to come up (the first start can take a minute or two)...
powershell -NoProfile -Command ^
  "$deadline=(Get-Date).AddSeconds(150); while((Get-Date) -lt $deadline){ try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://localhost:5173 | Out-Null; Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8000/docs | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 800 } }; exit 1"
if errorlevel 1 (
  echo [!] The app did not answer within 2.5 minutes. Check the two server windows for errors.
  pause
  exit /b 1
)

start "" http://localhost:5173
echo.
echo DoorDoctor is running:  http://localhost:5173
echo Close the "DoorDoctor backend" and "DoorDoctor frontend" windows to stop it.
timeout /t 5 >nul
endlocal
