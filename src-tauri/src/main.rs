// src-tauri/src/main.rs
// Arranca el backend Python automáticamente al abrir la app

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn start_backend() -> Option<Child> {
    // Buscar python en el sistema
    let python = if cfg!(target_os = "windows") { "python" } else { "python3" };
    
    // Ruta al backend relativa al .exe
    let exe_dir = std::env::current_exe()
        .ok()?
        .parent()?
        .to_path_buf();
    
    // En desarrollo: buscar en el proyecto
    // En producción: buscar junto al .exe
    let backend_path = if cfg!(debug_assertions) {
        std::env::current_dir().ok()?.join("backend").join("main.py")
    } else {
        exe_dir.join("backend").join("main.py")
    };

    Command::new(python)
        .arg(backend_path)
        .spawn()
        .ok()
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Arrancar backend al iniciar la app
            let child = start_backend();
            app.manage(BackendProcess(Mutex::new(child)));
            
            // Esperar 2 segundos a que el backend arranque
            std::thread::sleep(std::time::Duration::from_secs(2));
            Ok(())
        })
        .on_window_event(|window, event| {
            // Cerrar el backend al cerrar la app
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