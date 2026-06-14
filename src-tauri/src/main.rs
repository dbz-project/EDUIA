// src-tauri/src/main.rs
// Arranca el backend Python usando el venv correcto — NO el Python del PATH
// Recomendación crítica de ChatGPT: nunca depender del PATH de Windows

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn get_python_path() -> PathBuf {
    // Ruta al directorio del ejecutable de Tauri
    let exe_dir = std::env::current_exe()
        .unwrap_or_default()
        .parent()
        .unwrap_or(&std::path::Path::new("."))
        .to_path_buf();

    // En desarrollo: buscar venv relativo al directorio del proyecto
    // En producción: buscar venv junto al .exe instalado
    let candidates = vec![
        // Desarrollo — venv en la raíz del proyecto
        std::env::current_dir()
            .unwrap_or_default()
            .join("venv")
            .join("Scripts")
            .join("python.exe"),
        // Producción — venv junto al .exe
        exe_dir.join("venv").join("Scripts").join("python.exe"),
        exe_dir.join("..").join("venv").join("Scripts").join("python.exe"),
    ];

    for path in &candidates {
        if path.exists() {
            return path.clone();
        }
    }

    // Último recurso — Python del sistema (no ideal pero mejor que fallar)
    PathBuf::from("python")
}

fn get_backend_path() -> PathBuf {
    let candidates = vec![
        std::env::current_dir()
            .unwrap_or_default()
            .join("backend")
            .join("main.py"),
        std::env::current_exe()
            .unwrap_or_default()
            .parent()
            .unwrap_or(&std::path::Path::new("."))
            .join("backend")
            .join("main.py"),
    ];

    for path in &candidates {
        if path.exists() {
            return path.clone();
        }
    }

    PathBuf::from("backend/main.py")
}

fn start_backend() -> Option<Child> {
    let python  = get_python_path();
    let backend = get_backend_path();

    eprintln!("[TAURI] Python: {:?}", python);
    eprintln!("[TAURI] Backend: {:?}", backend);

    Command::new(&python)
        .arg(&backend)
        .spawn()
        .map_err(|e| eprintln!("[TAURI] Error arrancando backend: {}", e))
        .ok()
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let child = start_backend();
            app.manage(BackendProcess(Mutex::new(child)));
            // Esperar a que el backend cargue el modelo (puede tardar ~5s)
            std::thread::sleep(std::time::Duration::from_secs(5));
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
