use crate::cache::{anim_cache_dir, ensure_cache_dirs};
use crossbeam_channel::{bounded, Receiver};
use egui::ColorImage;
use reqwest::blocking::Client;
use sha2::{Digest, Sha256};
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, SystemTime};

const MAX_ANIM_CACHE_BYTES: u64 = 400 * 1024 * 1024;
const USER_AGENT: &str = "Mozilla/5.0 (X11; Linux x86_64) KomorebiDesktop/3.0";

pub struct VideoPreviewPlayer {
    frame_rx: Receiver<ColorImage>,
    paused: Arc<AtomicBool>,
    stop: Arc<AtomicBool>,
    child: Arc<Mutex<Option<Child>>>,
    status: Arc<Mutex<String>>,
    handle: Option<JoinHandle<()>>,
}

impl VideoPreviewPlayer {
    pub fn start(
        client: Client,
        source: String,
        max_w: u32,
        max_h: u32,
        ctx: egui::Context,
    ) -> Self {
        let (tx, rx) = bounded::<ColorImage>(2);
        let paused = Arc::new(AtomicBool::new(false));
        let stop = Arc::new(AtomicBool::new(false));
        let child_arc: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
        let status = Arc::new(Mutex::new("Buffering...".to_string()));

        let paused_t = Arc::clone(&paused);
        let stop_t = Arc::clone(&stop);
        let child_t = Arc::clone(&child_arc);
        let status_t = Arc::clone(&status);

        let handle = thread::spawn(move || {
            let local_path = match ensure_local_video(&client, &source, &stop_t) {
                Ok(p) => p,
                Err(e) => {
                    if !stop_t.load(Ordering::Relaxed) {
                        *status_t.lock().unwrap() = format!("Preview error: {}", e);
                        ctx.request_repaint();
                    }
                    return;
                }
            };
            if stop_t.load(Ordering::Relaxed) {
                return;
            }

            let (vw, vh) = probe_dimensions(&local_path).unwrap_or((1280, 720));
            let (tw, th) = fit_even_bounds(vw, vh, max_w, max_h);
            let scale_arg = format!("scale={}:{}:flags=fast_bilinear,fps=24", tw, th);

            while !stop_t.load(Ordering::Relaxed) {
                let child_res = Command::new("ffmpeg")
                    .args([
                        "-nostdin",
                        "-loglevel",
                        "error",
                        "-stream_loop",
                        "-1",
                        "-re",
                        "-i",
                        &local_path,
                        "-vf",
                        &scale_arg,
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgba",
                        "-",
                    ])
                    .stdin(Stdio::null())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::null())
                    .spawn();

                let mut child = match child_res {
                    Ok(c) => c,
                    Err(e) => {
                        *status_t.lock().unwrap() = format!("ffmpeg unavailable: {}", e);
                        if ctx.input(|i| i.focused) {
                            ctx.request_repaint();
                        }
                        return;
                    }
                };

                let mut stdout = match child.stdout.take() {
                    Some(s) => s,
                    None => {
                        let _ = child.kill();
                        let _ = child.wait();
                        return;
                    }
                };

                *child_t.lock().unwrap() = Some(child);
                *status_t.lock().unwrap() = "LIVE".to_string();

                let frame_bytes = (tw as usize) * (th as usize) * 4;
                let mut buf = vec![0u8; frame_bytes];
                let mut frames_decoded = 0usize;

                loop {
                    if stop_t.load(Ordering::Relaxed) {
                        break;
                    }
                    while paused_t.load(Ordering::Relaxed) && !stop_t.load(Ordering::Relaxed) {
                        thread::sleep(Duration::from_millis(40));
                    }
                    if stop_t.load(Ordering::Relaxed) {
                        break;
                    }

                    if stdout.read_exact(&mut buf).is_err() {
                        break;
                    }
                    frames_decoded += 1;
                    let img = ColorImage::from_rgba_unmultiplied([tw as usize, th as usize], &buf);
                    if tx.try_send(img).is_ok() && ctx.input(|i| i.focused) {
                        ctx.request_repaint();
                    }
                }

                if let Some(mut c) = child_t.lock().unwrap().take() {
                    let _ = c.kill();
                    let _ = c.wait();
                }

                if frames_decoded == 0 {
                    if !stop_t.load(Ordering::Relaxed) {
                        *status_t.lock().unwrap() = "Preview error: Failed to decode video".to_string();
                        if ctx.input(|i| i.focused) {
                            ctx.request_repaint();
                        }
                    }
                    break;
                }
            }
        });

        Self {
            frame_rx: rx,
            paused,
            stop,
            child: child_arc,
            status,
            handle: Some(handle),
        }
    }

    pub fn try_next_frame(&self) -> Option<ColorImage> {
        let mut latest = None;
        while let Ok(f) = self.frame_rx.try_recv() {
            latest = Some(f);
        }
        latest
    }

    pub fn is_paused(&self) -> bool {
        self.paused.load(Ordering::Relaxed)
    }

    pub fn set_paused(&self, p: bool) {
        self.paused.store(p, Ordering::Relaxed);
    }

    pub fn toggle_paused(&self) {
        let cur = self.paused.load(Ordering::Relaxed);
        self.paused.store(!cur, Ordering::Relaxed);
    }

    pub fn status(&self) -> String {
        self.status.lock().map(|s| s.clone()).unwrap_or_default()
    }

    pub fn stop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(mut c) = self.child.lock().unwrap().take() {
            let _ = c.kill();
            thread::spawn(move || {
                let _ = c.wait();
            });
        }
        // Detach handle without blocking the UI thread if HTTP/ffmpeg is still unwinding
        self.handle.take();
    }
}

impl Drop for VideoPreviewPlayer {
    fn drop(&mut self) {
        self.stop();
    }
}

fn ensure_local_video(
    client: &Client,
    source: &str,
    stop: &AtomicBool,
) -> Result<String, String> {
    if !source.starts_with("http://") && !source.starts_with("https://") {
        if Path::new(source).exists() {
            return Ok(source.to_string());
        }
        return Err("Video file not found".into());
    }

    ensure_cache_dirs();
    let mut hasher = Sha256::new();
    hasher.update(source.as_bytes());
    let hash = hex::encode(hasher.finalize());
    let clean = source.split('?').next().unwrap_or(source);
    let ext = Path::new(clean)
        .extension()
        .and_then(|e| e.to_str())
        .filter(|e| !e.is_empty() && e.len() <= 5)
        .unwrap_or("webm");
    let target = anim_cache_dir().join(format!("{}.{}", hash, ext));
    if target.exists() && fs::metadata(&target).map(|m| m.len() > 0).unwrap_or(false) {
        return Ok(target.to_string_lossy().into_owned());
    }

    let tmp = target.with_extension("part");
    let mut resp = client
        .get(source)
        .header("User-Agent", USER_AGENT)
        .header("Referer", "https://moewalls.com/")
        .timeout(Duration::from_secs(25))
        .send()
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }

    let mut file = fs::File::create(&tmp).map_err(|e| e.to_string())?;
    let mut chunk = [0u8; 64 * 1024];
    loop {
        if stop.load(Ordering::Relaxed) {
            drop(file);
            let _ = fs::remove_file(&tmp);
            return Err("cancelled".into());
        }
        let n = resp.read(&mut chunk).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        file.write_all(&chunk[..n]).map_err(|e| e.to_string())?;
    }
    drop(file);
    fs::rename(&tmp, &target).map_err(|e| e.to_string())?;
    prune_anim_cache();
    Ok(target.to_string_lossy().into_owned())
}

fn prune_anim_cache() {
    let dir = anim_cache_dir();
    let Ok(rd) = fs::read_dir(&dir) else {
        return;
    };
    let mut files: Vec<(PathBuf, u64, SystemTime)> = Vec::new();
    let mut total: u64 = 0;
    for e in rd.flatten() {
        let p = e.path();
        if let Ok(m) = e.metadata() {
            if m.is_file() {
                total += m.len();
                files.push((p, m.len(), m.modified().unwrap_or(SystemTime::UNIX_EPOCH)));
            }
        }
    }
    if total <= MAX_ANIM_CACHE_BYTES {
        return;
    }
    files.sort_by_key(|f| f.2);
    let target = (MAX_ANIM_CACHE_BYTES as f64 * 0.8) as u64;
    for (p, len, _) in files {
        if total <= target {
            break;
        }
        if fs::remove_file(p).is_ok() {
            total = total.saturating_sub(len);
        }
    }
}

fn probe_dimensions(path: &str) -> Option<(u32, u32)> {
    let out = Command::new("ffprobe")
        .args([
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            path,
        ])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let s = String::from_utf8_lossy(&out.stdout);
    let parts: Vec<&str> = s.trim().split('x').collect();
    if parts.len() >= 2 {
        let w = parts[0].trim().parse::<u32>().ok()?;
        let h = parts[1].trim().parse::<u32>().ok()?;
        if w > 0 && h > 0 {
            return Some((w, h));
        }
    }
    None
}

fn fit_even_bounds(vw: u32, vh: u32, max_w: u32, max_h: u32) -> (u32, u32) {
    let scale = f64::min(
        max_w as f64 / vw.max(1) as f64,
        max_h as f64 / vh.max(1) as f64,
    )
    .min(1.0);
    let w = (((vw as f64 * scale) as u32) / 2 * 2).max(2);
    let h = (((vh as f64 * scale) as u32) / 2 * 2).max(2);
    (w, h)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn decodes_live_video_frames_and_stops_fast() {
        let has_ffmpeg = Command::new("ffmpeg")
            .arg("-version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .map(|s| s.success())
            .unwrap_or(false);
        if !has_ffmpeg {
            return;
        }

        let dir = std::env::temp_dir().join("komorebi_test_vid_preview");
        let _ = fs::create_dir_all(&dir);
        let mp4 = dir.join("sample.mp4");
        let status = Command::new("ffmpeg")
            .args([
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=64x64:d=0.6:r=24",
                "-pix_fmt",
                "yuv420p",
                mp4.to_str().unwrap(),
            ])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .unwrap();
        assert!(status.success());

        assert_eq!(probe_dimensions(mp4.to_str().unwrap()), Some((64, 64)));

        let client = crate::providers::build_http_client();
        let ctx = egui::Context::default();
        let mut player = VideoPreviewPlayer::start(
            client,
            mp4.to_string_lossy().into_owned(),
            128,
            128,
            ctx,
        );

        let deadline = Instant::now() + Duration::from_secs(3);
        let mut got_frame = None;
        while Instant::now() < deadline {
            if let Some(f) = player.try_next_frame() {
                got_frame = Some(f);
                break;
            }
            thread::sleep(Duration::from_millis(20));
        }

        let frame = got_frame.expect("VideoPreviewPlayer should yield at least 1 RGBA frame");
        assert_eq!(frame.size, [64, 64]);

        let t0 = Instant::now();
        player.stop();
        assert!(t0.elapsed() < Duration::from_millis(200));

        let _ = fs::remove_dir_all(&dir);
    }
}
