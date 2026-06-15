// src-tauri/src/main.rs
// Fix ISSUE-013: prevención de arranque múltiple
// Fix ISSUE-005: rutas absolutas desde ubicación del .exe

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn get_project_root() -> PathBuf {
    if cfg!(debug_assertions) {
        std::env::current_dir().unwrap_or_default()
    } else {
        // En producción: directorio donde está instalado el .exe
        std::env::current_exe()
            .unwrap_or_default()
            .parent()
            .unwrap_or(&std::path::Path::new("."))
            .to_path_buf()
    }
}

fn get_python_path(root: &PathBuf) -> PathBuf {
    let candidates = vec![
        root.join("venv").join("Scripts").join("python.exe"),
        root.join(".venv").join("Scripts").join("python.exe"),
    ];
    for p in &candidates {
        if p.exists() {
            eprintln!("[TAURI] Python: {:?}", p);
            return p.clone();
        }
    }
    eprintln!("[TAURI] Usando Python del sistema");
    PathBuf::from("python")
}

/// ISSUE-013: Verificar si el backend ya está corriendo
/// Si ya corre, no lanzar otro proceso
fn backend_already_running() -> bool {
    check_health()
}

fn start_backend(root: &PathBuf) -> Option<Child> {
    // ISSUE-013: No arrancar si ya hay uno corriendo
    if backend_already_running() {
        eprintln!("[TAURI] Backend ya está corriendo, no se lanza otro");
        return None;
    }

    let python = get_python_path(root);
    eprintln!("[TAURI] Root: {:?}", root);
    eprintln!("[TAURI] Arrancando backend...");

    Command::new(&python)
        .args(["-m", "backend.main"])
        .current_dir(root)
        .spawn()
        .map_err(|e| eprintln!("[TAURI] Error arrancando backend: {}", e))
        .ok()
}

fn wait_for_backend() {
    for (i, secs) in [5u64, 5, 10].iter().enumerate() {
        std::thread::sleep(Duration::from_secs(*secs));
        eprintln!("[TAURI] Health check {}/3...", i + 1);
        if check_health() {
            eprintln!("[TAURI] ✅ Backend listo");
            return;
        }
    }
    eprintln!("[TAURI] Timeout — abriendo con fallback");
}

fn check_health() -> bool {
    let out = Command::new("powershell")
        .args([
            "-WindowStyle", "Hidden", "-Command",
            "try { $r=(Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' \
             -TimeoutSec 3).Content|ConvertFrom-Json; \
             if($r.ready){exit 0}else{exit 1} } catch { exit 1 }"
        ])
        .output();
    matches!(out, Ok(o) if o.status.success())
}

fn main() {
    let root = get_project_root();

    tauri::Builder::default()
        .setup(move |app| {
            let child = start_backend(&root);
            app.manage(BackendProcess(Mutex::new(child)));
            wait_for_backend();
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut child) = state.0.lock() {
                        if let Some(ref mut p) = *child {
                            let _ = p.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("Error EduIA");
}
