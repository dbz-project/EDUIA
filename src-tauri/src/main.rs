// src-tauri/src/main.rs — v7
// Fix definitivo: root calculado desde exe subiendo 3 niveles
// src-tauri/target/release/app.exe → subir 3 → raíz del proyecto

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn get_project_root() -> PathBuf {
    let exe = std::env::current_exe().unwrap_or_default();
    
    if cfg!(debug_assertions) {
        // Desarrollo: usar directorio actual
        return std::env::current_dir().unwrap_or_default();
    }

    // Producción: el .exe está en src-tauri/target/release/app.exe
    // Subir 3 niveles para llegar a la raíz del proyecto
    // release → target → src-tauri → RAÍZ
    let root = exe
        .parent().unwrap_or(&exe)  // release/
        .parent().unwrap_or(&exe)  // target/
        .parent().unwrap_or(&exe)  // src-tauri/
        .parent().unwrap_or(&exe); // RAÍZ del proyecto ← aquí

    eprintln!("[BOOT] exe: {:?}", exe);
    eprintln!("[BOOT] root calculado: {:?}", root);

    root.to_path_buf()
}

fn get_python_path(root: &PathBuf) -> PathBuf {
    let venv_python = root.join("venv").join("Scripts").join("python.exe");
    if venv_python.exists() {
        eprintln!("[BOOT] Python venv: {:?}", venv_python);
        return venv_python;
    }
    eprintln!("[BOOT] AVISO: venv no encontrado en {:?}", root.join("venv"));
    PathBuf::from("python")
}

fn backend_already_running() -> bool {
    check_health()
}

fn start_backend(root: &PathBuf) -> Option<Child> {
    if backend_already_running() {
        eprintln!("[BOOT] Backend ya corriendo (ISSUE-013)");
        return None;
    }

    let python = get_python_path(root);
    eprintln!("[BOOT] Lanzando: {:?} -m backend.main en {:?}", python, root);

    Command::new(&python)
        .args(["-m", "backend.main"])
        .current_dir(root)
        .spawn()
        .map_err(|e| eprintln!("[BOOT] ERROR spawn: {}", e))
        .ok()
}

fn wait_for_backend() {
    eprintln!("[BOOT] Esperando backend...");
    for (i, secs) in [5u64, 5, 10].iter().enumerate() {
        std::thread::sleep(Duration::from_secs(*secs));
        eprintln!("[BOOT] Health check {}/3...", i + 1);
        if check_health() {
            eprintln!("[BOOT] Backend listo ✅");
            return;
        }
    }
    eprintln!("[BOOT] Timeout — abriendo con fallback");
}

fn check_health() -> bool {
    let out = Command::new("powershell")
        .args([
            "-WindowStyle", "Hidden", "-Command",
            "try{$r=(Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' \
             -TimeoutSec 3).Content|ConvertFrom-Json;\
             if($r.ready){exit 0}else{exit 1}}catch{exit 1}"
        ])
        .output();
    matches!(out, Ok(o) if o.status.success())
}

fn main() {
    eprintln!("[BOOT] === EduIA arrancando ===");

    let root = get_project_root();
    eprintln!("[BOOT] root final: {:?}", root);

    eprintln!("[BOOT] Lanzando backend...");
    let child = start_backend(&root);

    eprintln!("[BOOT] Esperando ready...");
    wait_for_backend();

    eprintln!("[BOOT] Creando ventana Tauri...");

    tauri::Builder::default()
        .setup(move |app| {
            eprintln!("[BOOT] Setup OK");
            app.manage(BackendProcess(Mutex::new(child)));
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
        .unwrap_or_else(|e| {
            eprintln!("[BOOT] ERROR FATAL: {:?}", e);
        });
}
