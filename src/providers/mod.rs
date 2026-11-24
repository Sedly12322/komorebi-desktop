pub mod moewalls;
pub mod osu;
pub mod pfps;
pub mod wallhaven;

use reqwest::blocking::Client;
use std::fs;
use std::io::{Read, Write};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

pub fn build_http_client() -> Client {
    Client::builder()
        .user_agent("KomorebiDesktop/3.0 (High-Performance Wallpaper Manager)")
        .timeout(Duration::from_secs(20))
        .build()
        .expect("reqwest blocking client")
}

pub fn download_file<F>(
    client: &Client,
    url: &str,
    dest_path: &Path,
    extra_headers: &[(&str, &str)],
    mut on_progress: F,
    cancelled: &AtomicBool,
) -> Result<(), String>
where
    F: FnMut(u64, u64),
{
    if let Some(parent) = dest_path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let tmp_path = dest_path.with_file_name(format!(
        "{}.download",
        dest_path.file_name().and_then(|s| s.to_str()).unwrap_or("file")
    ));

    let mut req = client
        .get(url)
        .header(
            "User-Agent",
            "KomorebiDesktop/3.0 (High-Performance Wallpaper Manager)",
        )
        .timeout(Duration::from_secs(60));
    for (k, v) in extra_headers {
        req = req.header(*k, *v);
    }

    let mut resp = req.send().map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }

    let total = resp.content_length().unwrap_or(0);
    let mut downloaded: u64 = 0;

    let mut file = fs::File::create(&tmp_path).map_err(|e| e.to_string())?;
    let mut buf = [0u8; 64 * 1024];
    loop {
        if cancelled.load(Ordering::Relaxed) {
            drop(file);
            let _ = fs::remove_file(&tmp_path);
            return Err("Download cancelled".into());
        }
        let n = resp.read(&mut buf).map_err(|e| {
            let _ = fs::remove_file(&tmp_path);
            e.to_string()
        })?;
        if n == 0 {
            break;
        }
        file.write_all(&buf[..n]).map_err(|e| {
            let _ = fs::remove_file(&tmp_path);
            e.to_string()
        })?;
        downloaded += n as u64;
        on_progress(downloaded, total);
    }
    drop(file);
    if dest_path.exists() {
        let _ = fs::remove_file(dest_path);
    }
    fs::rename(&tmp_path, dest_path).map_err(|e| e.to_string())?;
    Ok(())
}
