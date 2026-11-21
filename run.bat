@echo off
REM Starts the SentinelDesk API (port 8000) and the web console (port 5173).
REM Usage: run.bat          real models
REM        run.bat mock     mock API (SENTINEL_MOCK=1)
cd /d "%~dp0"

if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

if /i "%~1"=="mock" (set SENTINEL_MOCK=1) else (set SENTINEL_MOCK=)

if not exist web\node_modules (
  pushd web
  call npm install
  popd
)

start "SentinelDesk API" cmd /k python -m uvicorn api.main:app --reload --port 8000
start "SentinelDesk UI" cmd /k "cd /d web && npm run dev"

echo API: http://localhost:8000   UI: http://localhost:5173
timeout /t 5 >nul
start http://localhost:5173
