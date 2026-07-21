@echo off
setlocal

cd /d "%~dp0"

echo Starting SENAMHI DataLake...
echo.

start "SENAMHI API" cmd /k "python run_dev.py"
start "SENAMHI Worker" cmd /k "python scripts\run_extraction_worker.py"

echo Waiting for the web server...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$deadline=(Get-Date).AddSeconds(45); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"

if errorlevel 1 (
  echo The server did not answer yet. Opening the page anyway...
) else (
  echo Server ready.
)

start "" "http://127.0.0.1:8000"
endlocal
