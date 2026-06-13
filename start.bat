@echo off
setlocal
cd /d "%~dp0"

REM ==========================================
REM  EDUIA STARTER v1.0
REM  Doble clic para arrancar EduIA
REM ==========================================

REM Crear carpeta de logs si no existe
if not exist "logs" mkdir logs

REM ── Comprobar entorno Python ──────────────
if not exist "venv\Scripts\python.exe" (
    powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('No se encontro el entorno de Python. Reinstala EduIA o contacta con tu administrador.','EduIA - Error')"
    exit /b 1
)

REM ── Comprobar modelo IA ───────────────────
if not exist "runtime\models\*.gguf" (
    powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('El modelo de IA no esta descargado. Ejecuta primero: python scripts/download_model.py','EduIA - Error')"
    exit /b 1
)

REM ── Arrancar backend en segundo plano ─────
REM  Logs guardados en logs\backend.log
REM  Sin ventana de consola visible
start "" /B cmd /c "venv\Scripts\python.exe backend\main.py > logs\backend.log 2>&1"

REM ── Esperar arranque del backend ──────────
echo Iniciando EduIA...
timeout /t 5 /nobreak >nul

REM ── Health check (idea ChatGPT) ───────────
REM  Comprueba que FastAPI responde antes de abrir la UI
powershell -WindowStyle Hidden -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 5; exit 0 } catch { exit 1 }"

if errorlevel 1 (
    REM Esperar 10s más — el modelo puede tardar en cargar
    timeout /t 10 /nobreak >nul
    powershell -WindowStyle Hidden -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 5 | Out-Null; exit 0 } catch { exit 1 }"
)

if errorlevel 1 (
    powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('No se pudo iniciar EduIA correctamente. Revisa el archivo logs\backend.log o contacta con tu administrador.','EduIA - Error')"
    exit /b 1
)

REM ── Abrir la app ──────────────────────────
REM  Plan A: .exe de Tauri ya instalado
if exist "src-tauri\target\release\app.exe" (
    start "" "src-tauri\target\release\app.exe"
    exit /b 0
)

REM  Plan B: instalador NSIS
if exist "src-tauri\target\release\bundle\nsis\EduIA_0.1.0_x64-setup.exe" (
    start "" "src-tauri\target\release\bundle\nsis\EduIA_0.1.0_x64-setup.exe"
    exit /b 0
)

powershell -WindowStyle Hidden -Command "[System.Windows.MessageBox]::Show('No se encontro EduIA.exe. Compila la app primero con: npx tauri build','EduIA - Error')"
exit /b 1
