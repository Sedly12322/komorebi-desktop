use crossbeam_channel::{unbounded, Receiver, Sender};
use egui::{ColorImage, Context, TextureHandle, TextureOptions};
use image::codecs::gif::GifDecoder;
use image::{AnimationDecoder, GenericImageView};
use reqwest::blocking::Client;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet, VecDeque};
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime};

pub const MAX_CACHE_BYTES: u64 = 750 * 1024 * 1024;
const MAX_TEX_MEM_ENTRIES: usize = 320;
const USER_AGENT: &str = "Mozilla/5.0 (X11; Linux x86_64) KomorebiDesktop/3.0";

pub fn cache_dir() -> PathBuf {
    #[cfg(target_os = "windows")]
    let base = dirs::cache_dir()
        .or_else(dirs::data_local_dir)
        .unwrap_or_else(|| PathBuf::from("."));
    #[cfg(not(target_os = "windows"))]
    let base = dirs::home_dir()
        .map(|h| h.join(".cache"))
        .unwrap_or_else(|| PathBuf::from("."));

    let new_dir = base.join("komorebi-desktop");
    let old_dir = base.join("wallhaven-desktop");
    if !new_dir.exists() && old_dir.exists() {
        let _ = fs::rename(&old_dir, &new_dir);
    }
    new_dir
}

pub fn thumb_cache_dir() -> PathBuf {
    cache_dir().join("thumbnails")
}

pub fn full_cache_dir() -> PathBuf {
    cache_dir().join("previews")
}

pub fn anim_cache_dir() -> PathBuf {
    cache_dir().join("anim")
}

pub fn ensure_cache_dirs() {
    let _ = fs::create_dir_all(thumb_cache_dir());
    let _ = fs::create_dir_all(full_cache_dir());
    let _ = fs::create_dir_all(anim_cache_dir());
}

pub fn url_to_cache_path(url: &str, is_thumb: bool) -> PathBuf {
    let mut hasher = Sha256::new();
    hasher.update(url.as_bytes());
    let hash = hex::encode(hasher.finalize());
    let clean = url.split('?').next().unwrap_or(url);
    let ext = Path::new(clean)
        .extension()
        .and_then(|e| e.to_str())
        .filter(|e| !e.is_empty() && e.len() <= 5)
        .unwrap_or("jpg");
    let dir = if is_thumb {
        thumb_cache_dir()
    } else {
        full_cache_dir()
    };
    dir.join(format!("{}.{}", hash, ext))
}

pub fn get_video_thumb_path(video_path: &str) -> PathBuf {
    let mut hasher = Sha256::new();
    hasher.update(video_path.as_bytes());
    let hash = hex::encode(hasher.finalize());
    thumb_cache_dir().join(format!("vid_{}.jpg", hash))
}

pub fn cache_size_bytes() -> u64 {
    fn dir_bytes(p: &Path) -> u64 {
        let mut total = 0;
        if let Ok(rd) = fs::read_dir(p) {
            for e in rd.flatten() {
                let ep = e.path();
                if ep.is_dir() {
                    total += dir_bytes(&ep);
                } else if let Ok(meta) = e.metadata() {
                    total += meta.len();
                }
            }
        }
        total
    }
    dir_bytes(&cache_dir())
}

pub fn clear_cache() -> Result<(), String> {
    let root = cache_dir();
    if root.exists() {
        fs::remove_dir_all(&root).map_err(|e| e.to_string())?;
    }
    ensure_cache_dirs();
    Ok(())
}

pub fn clean_old_cache_if_needed() {
    let root = cache_dir();
    if !root.exists() {
        return;
    }
    let mut files: Vec<(PathBuf, u64, SystemTime)> = Vec::new();
    let mut stack = vec![root];
    let mut total: u64 = 0;
    while let Some(dir) = stack.pop() {
        if let Ok(rd) = fs::read_dir(&dir) {
            for e in rd.flatten() {
                let p = e.path();
                if p.is_dir() {
                    stack.push(p);
                } else if let Ok(m) = e.metadata() {
                    let len = m.len();
                    let mod_t = m.modified().unwrap_or(SystemTime::UNIX_EPOCH);
                    total += len;
                    files.push((p, len, mod_t));
                }
            }
        }
    }
    if total <= MAX_CACHE_BYTES {
        return;
    }
    files.sort_by_key(|f| f.2);
    let target = (MAX_CACHE_BYTES as f64 * 0.7) as u64;
    for (p, len, _) in files {
        if total <= target {
            break;
        }
        if fs::remove_file(p).is_ok() {
            total = total.saturating_sub(len);
        }
    }
}

pub enum LoadedImagePayload {
    Static {
        key: String,
        image: ColorImage,
    },
    Gif {
        key: String,
        frames: Vec<(ColorImage, f32)>,
    },
    Failed {
        key: String,
    },
}

pub struct ImageLoader {
    client: Client,
    pool: rayon::ThreadPool,
    tx: Sender<LoadedImagePayload>,
    rx: Receiver<LoadedImagePayload>,
    in_flight: Arc<Mutex<HashSet<String>>>,
    failed: HashSet<String>,
    textures: HashMap<String, TextureHandle>,
    lru: VecDeque<String>,
    gifs: HashMap<String, Vec<(TextureHandle, f32)>>,
}

impl ImageLoader {
    pub fn new(client: Client) -> Self {
        ensure_cache_dirs();
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(6)
            .build()
            .expect("rayon thread pool");
        let (tx, rx) = unbounded();
        Self {
            client,
            pool,
            tx,
            rx,
            in_flight: Arc::new(Mutex::new(HashSet::new())),
            failed: HashSet::new(),
            textures: HashMap::new(),
            lru: VecDeque::new(),
            gifs: HashMap::new(),
        }
    }

    pub fn get_texture(&mut self, key: &str) -> Option<&TextureHandle> {
        if self.textures.contains_key(key) {
            self.touch_lru(key);
            return self.textures.get(key);
        }
        None
    }

    pub fn get_gif(&self, key: &str) -> Option<&Vec<(TextureHandle, f32)>> {
        self.gifs.get(key)
    }

    pub fn is_failed(&self, key: &str) -> bool {
        self.failed.contains(key)
    }

    pub fn clear_memory(&mut self) {
        self.textures.clear();
        self.lru.clear();
        self.gifs.clear();
        self.failed.clear();
    }

    pub fn evict_key(&mut self, key: &str) {
        self.textures.remove(key);
        self.gifs.remove(key);
        self.failed.remove(key);
        self.lru.retain(|k| k != key);
    }

    fn touch_lru(&mut self, key: &str) {
        self.lru.retain(|k| k != key);
        self.lru.push_back(key.to_string());
    }

    fn insert_texture(&mut self, key: String, tex: TextureHandle) {
        self.touch_lru(&key);
        self.textures.insert(key, tex);
        while self.lru.len() > MAX_TEX_MEM_ENTRIES {
            if let Some(oldest) = self.lru.pop_front() {
                self.textures.remove(&oldest);
            }
        }
    }

    pub fn request_image(
        &mut self,
        key: &str,
        url_or_path: &str,
        is_thumb: bool,
        decode_gif: bool,
        max_side: u32,
        ctx: &Context,
    ) {
        if url_or_path.trim().is_empty() {
            return;
        }
        if decode_gif {
            if self.gifs.contains_key(key) {
                return;
            }
        } else if self.textures.contains_key(key) {
            return;
        }
        if self.failed.contains(key) {
            return;
        }
        {
            let mut guard = self.in_flight.lock().unwrap();
            if guard.contains(key) {
                return;
            }
            guard.insert(key.to_string());
        }

        let key_s = key.to_string();
        let src = url_or_path.to_string();
        let client = self.client.clone();
        let tx = self.tx.clone();
        let in_flight = Arc::clone(&self.in_flight);
        let ctx_clone = ctx.clone();

        self.pool.spawn(move || {
            let res = load_or_fetch(&client, &src, is_thumb, decode_gif, max_side);
            let msg = match res {
                Some(OkGifOrStatic::Static(img)) => LoadedImagePayload::Static {
                    key: key_s.clone(),
                    image: img,
                },
                Some(OkGifOrStatic::Gif(frames)) => LoadedImagePayload::Gif {
                    key: key_s.clone(),
                    frames,
                },
                None => LoadedImagePayload::Failed { key: key_s.clone() },
            };
            let _ = tx.send(msg);
            if let Ok(mut g) = in_flight.lock() {
                g.remove(&key_s);
            }
            ctx_clone.request_repaint();
        });
    }

    pub fn poll(&mut self, ctx: &Context) {
        while let Ok(msg) = self.rx.try_recv() {
            match msg {
                LoadedImagePayload::Static { key, image } => {
                    let tex = ctx.load_texture(&key, image, TextureOptions::LINEAR);
                    self.insert_texture(key, tex);
                }
                LoadedImagePayload::Gif { key, frames } => {
                    let mut handles = Vec::with_capacity(frames.len());
                    for (idx, (img, delay)) in frames.into_iter().enumerate() {
                        let name = format!("{}#frame{}", key, idx);
                        let tex = ctx.load_texture(name, img, TextureOptions::LINEAR);
                        handles.push((tex, delay));
                    }
                    if !handles.is_empty() {
                        self.gifs.insert(key, handles);
                    }
                }
                LoadedImagePayload::Failed { key } => {
                    self.failed.insert(key);
                }
            }
        }
    }
}

enum OkGifOrStatic {
    Static(ColorImage),
    Gif(Vec<(ColorImage, f32)>),
}

fn is_local_video(path: &str) -> bool {
    let lower = path.to_ascii_lowercase();
    lower.ends_with(".mp4")
        || lower.ends_with(".webm")
        || lower.ends_with(".mkv")
        || lower.ends_with(".mov")
        || lower.ends_with(".avi")
}

fn generate_video_thumb(video_path: &str) -> Option<PathBuf> {
    let thumb = get_video_thumb_path(video_path);
    if thumb.exists() && fs::metadata(&thumb).map(|m| m.len() > 0).unwrap_or(false) {
        return Some(thumb);
    }
    ensure_cache_dirs();
    let thumb_str = thumb.to_string_lossy().into_owned();
    let status = Command::new("ffmpeg")
        .args([
            "-y",
            "-ss",
            "00:00:01",
            "-i",
            video_path,
            "-vframes",
            "1",
            "-update",
            "1",
            "-vf",
            "scale=480:-1",
            &thumb_str,
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .ok()?;
    if status.success() && thumb.exists() && fs::metadata(&thumb).map(|m| m.len() > 0).unwrap_or(false) {
        return Some(thumb);
    }
    // Fallback to frame 0 for very short videos
    let status2 = Command::new("ffmpeg")
        .args([
            "-y",
            "-i",
            video_path,
            "-vframes",
            "1",
            "-update",
            "1",
            "-vf",
            "scale=480:-1",
            &thumb_str,
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .ok()?;
    if status2.success() && thumb.exists() {
        Some(thumb)
    } else {
        None
    }
}

fn load_or_fetch(
    client: &Client,
    src: &str,
    is_thumb: bool,
    decode_gif: bool,
    max_side: u32,
) -> Option<OkGifOrStatic> {
    let bytes = if src.starts_with("http://") || src.starts_with("https://") {
        let cache_path = url_to_cache_path(src, is_thumb);
        if cache_path.exists() && fs::metadata(&cache_path).map(|m| m.len() > 0).unwrap_or(false) {
            fs::read(&cache_path).ok()?
        } else {
            let mut req = client.get(src).header("User-Agent", USER_AGENT);
            if src.contains("moewalls.com") {
                req = req.header("Referer", "https://moewalls.com/");
            } else if src.contains("pfps.gg") {
                req = req.header("Referer", "https://pfps.gg/");
            }
            let resp = req.timeout(Duration::from_secs(18)).send().ok()?;
            if !resp.status().is_success() {
                return None;
            }
            let data = resp.bytes().ok()?.to_vec();
            if !data.is_empty() {
                ensure_cache_dirs();
                let tmp = cache_path.with_extension("tmp");
                if fs::write(&tmp, &data).is_ok() {
                    let _ = fs::rename(&tmp, &cache_path);
                }
            }
            data
        }
    } else {
        let p = Path::new(src);
        if !p.exists() {
            return None;
        }
        if is_local_video(src) {
            let thumb = generate_video_thumb(src)?;
            fs::read(thumb).ok()?
        } else {
            fs::read(p).ok()?
        }
    };

    if decode_gif && bytes.starts_with(b"GIF8") {
        if let Ok(decoder) = GifDecoder::new(Cursor::new(&bytes)) {
            if let Ok(frames) = decoder.into_frames().collect_frames() {
                if frames.len() > 1 {
                    let mut out = Vec::with_capacity(frames.len().min(90));
                    for frame in frames.into_iter().take(90) {
                        let (num, den) = frame.delay().numer_denom_ms();
                        let delay_s = ((num as f32) / (den.max(1) as f32) / 1000.0).clamp(0.02, 0.5);
                        let mut dyn_img = image::DynamicImage::ImageRgba8(frame.into_buffer());
                        let (w, h) = dyn_img.dimensions();
                        if max_side > 0 && (w > max_side || h > max_side) {
                            dyn_img = dyn_img.resize(
                                max_side,
                                max_side,
                                image::imageops::FilterType::Triangle,
                            );
                        }
                        let rgba = dyn_img.to_rgba8();
                        let size = [rgba.width() as usize, rgba.height() as usize];
                        out.push((ColorImage::from_rgba_unmultiplied(size, rgba.as_raw()), delay_s));
                    }
                    if !out.is_empty() {
                        return Some(OkGifOrStatic::Gif(out));
                    }
                }
            }
        }
    }

    let mut img = image::load_from_memory(&bytes).ok()?;
    let (w, h) = img.dimensions();
    if max_side > 0 && (w > max_side || h > max_side) {
        img = img.resize(max_side, max_side, image::imageops::FilterType::Triangle);
    }
    let rgba = img.to_rgba8();
    let size = [rgba.width() as usize, rgba.height() as usize];
    Some(OkGifOrStatic::Static(ColorImage::from_rgba_unmultiplied(
        size,
        rgba.as_raw(),
    )))
}
