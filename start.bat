@echo off
setlocal
cd /d "%~dp0"

REM ==========================================
REM  EDUIA STARTER v2.0
REM  Usa el venv correcto — NO el Python del sistema
REM  Recomendación ChatGPT: nunca depender del PATH
REM ==========================================

if not exist "logs" mkdir logs

REM ── Verificar venv ────────────────────────
if not exist "venv\Scripts\python.exe" (
    powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('No se encontro el entorno Python (venv). Reinstala EduIA.','EduIA - Error')"
    exit /b 1
)

REM ── Verificar modelo ──────────────────────
set MODEL_FOUND=0
for %%f in (runtime\models\*.gguf) do set MODEL_FOUND=1
if %MODEL_FOUND%==0 (
    powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('Modelo de IA no encontrado. Ejecuta: python scripts/download_model.py','EduIA - Error')"
    exit /b 1
)

REM ── Arrancar backend con venv (NO el Python global) ──
REM  Logs en logs\backend.log para diagnóstico
start "" /B cmd /c "venv\Scripts\python.exe -m backend.main > logs\backend.log 2>&1"

REM ── Esperar arranque ──────────────────────
timeout /t 6 /nobreak >nul

REM ── Health check con reintentos ───────────
powershell -WindowStyle Hidden -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 5 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    timeout /t 8 /nobreak >nul
    powershell -WindowStyle Hidden -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 5 | Out-Null; exit 0 } catch { exit 1 }"
)
if errorlevel 1 (
    powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('EduIA no pudo iniciarse. Revisa logs\backend.log para mas informacion.','EduIA - Error')"
    exit /b 1
)

REM ── Abrir app ─────────────────────────────
if exist "src-tauri\target\release\app.exe" (
    start "" "src-tauri\target\release\app.exe"
    exit /b 0
)
if exist "EduIA.exe" (
    start "" "EduIA.exe"
    exit /b 0
)

powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('No se encontro EduIA.exe. Compila la app con: npx tauri build','EduIA - Error')"
exit /b 1
