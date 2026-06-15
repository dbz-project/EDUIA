// src-tauri/src/main.rs — v6 con logs de diagnóstico en cada paso (ChatGPT)

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn log(msg: &str) {
    // Escribir en stderr Y en archivo para diagnóstico
    eprintln!("[BOOT] {}", msg);
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true).append(true)
        .open("logs/tauri_boot.log")
    {
        use std::io::Write;
        let _ = writeln!(f, "[BOOT] {}", msg);
    }
}

fn get_project_root() -> PathBuf {
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
            log(&format!("Python encontrado: {:?}", p));
            return p.clone();
        }
    }
    log("Python no encontrado en venv, usando sistema");
    PathBuf::from("python")
}

fn backend_already_running() -> bool {
    check_health()
}

fn start_backend(root: &PathBuf) -> Option<Child> {
    if backend_already_running() {
        log("Backend ya corriendo — no se lanza otro (ISSUE-013)");
        return None;
    }
    let python = get_python_path(root);
    log(&format!("Arrancando backend desde: {:?}", root));
    Command::new(&python)
        .args(["-m", "backend.main"])
        .current_dir(root)
        .spawn()
        .map_err(|e| log(&format!("ERROR arrancando backend: {}", e)))
        .ok()
}

fn wait_for_backend() {
    log("Esperando backend...");
    for (i, secs) in [5u64, 5, 10].iter().enumerate() {
        std::thread::sleep(Duration::from_secs(*secs));
        log(&format!("Health check {}/3", i + 1));
        if check_health() {
            log("Backend listo ✅");
            return;
        }
    }
    log("Timeout — abriendo con fallback activo");
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
    // Crear carpeta logs si no existe
    let _ = std::fs::create_dir_all("logs");

    log("=== EduIA arranque ===");
    log(&format!("exe: {:?}", std::env::current_exe().unwrap_or_default()));
    log(&format!("cwd: {:?}", std::env::current_dir().unwrap_or_default()));

    let root = get_project_root();
    log(&format!("root: {:?}", root));

    log("Iniciando backend...");
    let child = start_backend(&root);

    log("Esperando backend ready...");
    wait_for_backend();

    log("Creando ventana Tauri...");

    tauri::Builder::default()
        .setup(move |app| {
            log("Setup de Tauri OK");
            app.manage(BackendProcess(Mutex::new(child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                log("Ventana cerrada — matando backend");
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
            log(&format!("ERROR FATAL Tauri: {:?}", e));
        });

    log("Proceso terminado");
}
