// OpenFIQA Studio desktop shell.
//
// ADR-0001: this process renders and supervises. Every scientific operation belongs to the Python
// control plane, reached over HTTP and a WebSocket. Nothing in this crate computes a quality
// score, rescales a component, or interprets an engine's output.
//
// ADR-0002: engines are never launched from here either — the control plane owns per-engine
// environment resolution, because no single interpreter can host all of them.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

/// The control plane the shell supervises.
///
/// Held in Tauri's managed state so the child is terminated when the app exits. A backend left
/// running after the window closes would keep a port bound and a dataset index warm — the P03 gate
/// requires the backend to terminate cleanly, not merely to have been asked to.
struct Backend(Mutex<Option<Child>>);

impl Drop for Backend {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.0.lock() {
            if let Some(child) = guard.as_mut() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

/// Where the shell expects the control plane to be listening.
#[tauri::command]
fn backend_url() -> String {
    std::env::var("OFS_API").unwrap_or_else(|_| "http://127.0.0.1:8790".to_string())
}

fn spawn_backend() -> Option<Child> {
    // Opt-in: during development the backend is usually already running under uvicorn, and
    // spawning a second one would collide on the port.
    if std::env::var("OFS_SPAWN_BACKEND").ok().as_deref() != Some("1") {
        return None;
    }
    let python = std::env::var("OFS_PYTHON").unwrap_or_else(|_| "python3".to_string());
    Command::new(python)
        .args([
            "-m",
            "uvicorn",
            "studio_backend.app:app",
            "--port",
            "8790",
            "--log-level",
            "warning",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .ok()
}

fn main() {
    tauri::Builder::default()
        .manage(Backend(Mutex::new(spawn_backend())))
        .invoke_handler(tauri::generate_handler![backend_url])
        .run(tauri::generate_context!())
        .expect("failed to start the OpenFIQA Studio shell");
}
