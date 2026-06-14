// src-tauri/src/main.rs
// Rutas absolutas basadas en la ubicación del .exe — fix ISSUE-005

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

/// Directorio raíz del proyecto — donde está el .exe o donde se ejecuta en dev
fn get_project_root() -> PathBuf {
    // En desarrollo: directorio actual (C:\Users\adam\Desktop\EDUIA)
    // En producción: directorio del .exe instalado
    if cfg!(debug_assertions) {
        std::env::current_dir().unwrap_or_default()
    } else {
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
    eprintln!("[TAURI] Python no encontrado en venv, usando sistema");
    PathBuf::from("python")
}

fn start_backend(root: &PathBuf) -> Option<Child> {
    let python = get_python_path(root);

    eprintln!("[TAURI] Root: {:?}", root);
    eprintln!("[TAURI] Arrancando backend...");

    Command::new(&python)
        .args(["-m", "backend.main"])
        .current_dir(root)   // ← CLAVE: directorio de trabajo = raíz del proyecto
        .spawn()
        .map_err(|e| eprintln!("[TAURI] Error: {}", e))
        .ok()
}

fn wait_for_backend() {
    // Intento 1: 5s, Intento 2: +5s, Intento 3: +10s
    for (i, secs) in [5u64, 5, 10].iter().enumerate() {
        std::thread::sleep(Duration::from_secs(*secs));
        eprintln!("[TAURI] Health check {}/3...", i + 1);
        if check_health() {
            eprintln!("[TAURI] ✅ Backend listo");
            return;
        }
    }
    eprintln!("[TAURI] Abriendo app (fallback activo si modelo no cargó)");
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
