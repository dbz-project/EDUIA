// src-tauri/src/main.rs — v8
// Health check con TCP puro en Rust, sin PowerShell
// Backoff progresivo: 1s,2s,2s,5s,10s (idea ChatGPT)

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn get_project_root() -> PathBuf {
    if cfg!(debug_assertions) {
        return std::env::current_dir().unwrap_or_default();
    }
    // app.exe está en src-tauri/target/release/ — subir 3 niveles
    let exe = std::env::current_exe().unwrap_or_default();
    exe.parent().unwrap_or(&exe)   // release/
       .parent().unwrap_or(&exe)   // target/
       .parent().unwrap_or(&exe)   // src-tauri/
       .parent().unwrap_or(&exe)   // RAÍZ ← aquí
       .to_path_buf()
}

fn get_python_path(root: &PathBuf) -> PathBuf {
    let p = root.join("venv").join("Scripts").join("python.exe");
    if p.exists() { return p; }
    PathBuf::from("python")
}

fn backend_already_running() -> bool {
    check_health_tcp()
}

fn start_backend(root: &PathBuf) -> Option<Child> {
    if backend_already_running() {
        eprintln!("[BOOT] Backend ya corriendo");
        return None;
    }
    let python = get_python_path(root);
    eprintln!("[BOOT] root={:?}", root);
    eprintln!("[BOOT] python={:?}", python);

    // Forzar UTF-8 en el proceso hijo para evitar UnicodeEncodeError cp1252
    Command::new(&python)
        .args(["-m", "backend.main"])
        .current_dir(root)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .spawn()
        .map_err(|e| eprintln!("[BOOT] ERROR spawn: {}", e))
        .ok()
}

/// Health check TCP puro — sin PowerShell, sin dependencias externas
/// Hace una petición HTTP mínima a /health y busca "ready":true
fn check_health_tcp() -> bool {
    let Ok(mut stream) = TcpStream::connect_timeout(
        &"127.0.0.1:8765".parse().unwrap(),
        Duration::from_secs(2),
    ) else {
        return false;
    };

    let req = "GET /health HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }

    // Buscar "ready":true o "ready": true en la respuesta
    response.contains("\"ready\":true") || response.contains("\"ready\": true")
}

/// Backoff progresivo: 1+2+2+5+10 = 20s total, más reactivo en arranques rápidos
fn wait_for_backend() {
    let delays = [1u64, 2, 2, 5, 10];
    let start = Instant::now();

    for (i, delay) in delays.iter().enumerate() {
        std::thread::sleep(Duration::from_secs(*delay));
        let elapsed = start.elapsed().as_millis();
        eprintln!("[BOOT] Health check {}/{} ({}ms)...", i + 1, delays.len(), elapsed);

        if check_health_tcp() {
            eprintln!("[BOOT] Backend listo en {}ms", elapsed);
            return;
        }
    }

    eprintln!("[BOOT] Timeout {}ms — abriendo con fallback", start.elapsed().as_millis());
}

fn main() {
    eprintln!("[BOOT] === EduIA v0.1.0 ===");
    let root = get_project_root();
    eprintln!("[BOOT] root={:?}", root);

    let child = start_backend(&root);

    eprintln!("[BOOT] Esperando backend...");
    wait_for_backend();

    eprintln!("[BOOT] Creando ventana...");

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
        .unwrap_or_else(|e| eprintln!("[BOOT] ERROR: {:?}", e));
}
