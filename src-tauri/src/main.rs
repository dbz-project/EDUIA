// src-tauri/src/main.rs
// Health check inteligente — abre Tauri cuando ready=true, no por tiempo fijo
// Recomendación ChatGPT: no depender de sleep fijo

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn get_python_path() -> PathBuf {
    let exe_dir = std::env::current_exe()
        .unwrap_or_default()
        .parent()
        .unwrap_or(&std::path::Path::new("."))
        .to_path_buf();

    let candidates = vec![
        std::env::current_dir()
            .unwrap_or_default()
            .join("venv").join("Scripts").join("python.exe"),
        exe_dir.join("venv").join("Scripts").join("python.exe"),
        exe_dir.join("..").join("venv").join("Scripts").join("python.exe"),
    ];

    for path in &candidates {
        if path.exists() {
            eprintln!("[TAURI] Python encontrado: {:?}", path);
            return path.clone();
        }
    }
    eprintln!("[TAURI] Usando Python del sistema (fallback)");
    PathBuf::from("python")
}

fn get_backend_path() -> PathBuf {
    let candidates = vec![
        std::env::current_dir()
            .unwrap_or_default()
            .join("backend").join("main.py"),
        std::env::current_exe()
            .unwrap_or_default()
            .parent()
            .unwrap_or(&std::path::Path::new("."))
            .join("backend").join("main.py"),
    ];
    for path in &candidates {
        if path.exists() { return path.clone(); }
    }
    PathBuf::from("backend/main.py")
}

fn start_backend() -> Option<Child> {
    let python  = get_python_path();
    let backend = get_backend_path();
    eprintln!("[TAURI] Arrancando: {:?} -m backend.main", python);

    // Usar -m backend.main para evitar el problema de módulo no encontrado
    Command::new(&python)
        .arg("-m").arg("backend.main")
        .current_dir(
            std::env::current_dir().unwrap_or_default()
        )
        .spawn()
        .map_err(|e| eprintln!("[TAURI] Error: {}", e))
        .ok()
}

/// Health check inteligente — reintenta hasta que ready=true
/// Intento 1: espera 5s
/// Intento 2: espera 5s más  
/// Intento 3: espera 10s más
/// Total máximo: ~20s antes de abrir igualmente (con fallback activo)
fn wait_for_backend() {
    let waits = [5u64, 5, 10];
    for (i, wait) in waits.iter().enumerate() {
        std::thread::sleep(Duration::from_secs(*wait));
        eprintln!("[TAURI] Health check intento {}...", i + 1);

        // Llamada HTTP simple al health endpoint
        if backend_is_ready() {
            eprintln!("[TAURI] Backend listo ✅");
            return;
        }
        eprintln!("[TAURI] Backend aún no listo, reintentando...");
    }
    // Abrir igualmente — el fallback responderá si Qwen no cargó
    eprintln!("[TAURI] Abriendo app (fallback activo si es necesario)");
}

#[cfg(target_os = "windows")]
fn backend_is_ready() -> bool {
    // En Windows usamos un proceso PowerShell para el health check
    // sin añadir dependencias HTTP a Rust
    let output = Command::new("powershell")
        .args([
            "-WindowStyle", "Hidden",
            "-Command",
            "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 3; \
             $j = $r.Content | ConvertFrom-Json; \
             if ($j.ready -eq $true) { exit 0 } else { exit 1 } } catch { exit 1 }"
        ])
        .output();

    match output {
        Ok(o) => o.status.success(),
        Err(_) => false,
    }
}

#[cfg(not(target_os = "windows"))]
fn backend_is_ready() -> bool {
    false // En no-Windows siempre usa el sleep
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let child = start_backend();
            app.manage(BackendProcess(Mutex::new(child)));
            wait_for_backend();
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut child) = state.0.lock() {
                        if let Some(ref mut process) = *child {
                            let _ = process.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("Error al arrancar EduIA");
}
