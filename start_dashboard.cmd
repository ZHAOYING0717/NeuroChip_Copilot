@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo NeuroChip Python environment was not found.
    echo Run the project setup before starting the dashboard.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8501/_stcore/health; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>nul
if errorlevel 1 (
    start "NeuroChip Copilot" /min ".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
)

for /l %%i in (1,1,30) do (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8501/_stcore/health; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>nul
    if not errorlevel 1 goto open_dashboard
    ping 127.0.0.1 -n 2 >nul
)

echo NeuroChip Copilot did not start on port 8501.
pause
exit /b 1

:open_dashboard
start "" "http://127.0.0.1:8501"
exit /b 0
