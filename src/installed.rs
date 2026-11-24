use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use crate::config::config_dir;
use crate::models::{format_bytes, WallpaperItem};

const STATIC_EXTS: &[&str] = &["jpg", "jpeg", "png", "webp", "bmp"];
const VIDEO_EXTS: &[&str] = &["mp4", "mkv", "webm", "avi", "mov"];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstalledRecord {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub title: String,
    #[serde(default = "default_local")]
    pub source: String,
    #[serde(default)]
    pub file_path: String,
    #[serde(default)]
    pub file_size: u64,
    #[serde(default)]
    pub is_animated: bool,
    #[serde(default)]
    pub resolution: String,
    #[serde(default)]
    pub dimension_x: u32,
    #[serde(default)]
    pub dimension_y: u32,
    #[serde(default)]
    pub ratio: String,
    #[serde(default)]
    pub thumb_url: String,
    #[serde(default)]
    pub url: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub colors: Vec<String>,
    #[serde(default)]
    pub category: String,
    #[serde(default = "default_sfw")]
    pub purity: String,
    #[serde(default)]
    pub installed_at: f64,
}

fn default_local() -> String {
    "local".to_string()
}

fn default_sfw() -> String {
    "sfw".to_string()
}

impl InstalledRecord {
    pub fn to_wallpaper_item(&self) -> WallpaperItem {
        let thumb = if !self.thumb_url.is_empty() {
            self.thumb_url.clone()
        } else {
            self.file_path.clone()
        };
        let file_type = if self.is_animated {
            "video/mp4".to_string()
        } else {
            "image/jpeg".to_string()
        };

        WallpaperItem {
            id: self.id.clone(),
            title: self.title.clone(),
            url: self.url.clone(),
            short_url: self.url.clone(),
            source: self.source.clone(),
            purity: self.purity.clone(),
            category: self.category.clone(),
            dimension_x: self.dimension_x,
            dimension_y: self.dimension_y,
            resolution: self.resolution.clone(),
            ratio: self.ratio.clone(),
            file_size: self.file_size,
            file_type,
            colors: self.colors.clone(),
            path: self.file_path.clone(),
            thumb_large: thumb.clone(),
            thumb_small: thumb.clone(),
            thumb_original: self.file_path.clone(),
            tags: self.tags.clone(),
            is_animated: self.is_animated,
            is_installed: true,
            local_path: self.file_path.clone(),
            ..Default::default()
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct InstalledStats {
    pub total: usize,
    pub static_count: usize,
    pub live_count: usize,
    pub total_bytes: u64,
}

impl InstalledStats {
    pub fn total_size_human(&self) -> String {
        format_bytes(self.total_bytes)
    }
}

pub fn installed_file_path() -> PathBuf {
    config_dir().join("installed.json")
}

#[derive(Debug, Clone)]
pub struct InstalledManager {
    manifest_path: PathBuf,
    records: HashMap<String, InstalledRecord>,
}

impl InstalledManager {
    pub fn load_default() -> Self {
        Self::load_from_path(installed_file_path())
    }

    pub fn load_from_path(manifest_path: PathBuf) -> Self {
        let mut records: HashMap<String, InstalledRecord> = if manifest_path.exists() {
            fs::read_to_string(&manifest_path)
                .ok()
                .and_then(|s| serde_json::from_str(&s).ok())
                .unwrap_or_default()
        } else {
            HashMap::new()
        };

        // Prune records whose backing file vanished from disk.
        let before = records.len();
        records.retain(|path, _| Path::new(path).exists());
        let mgr = Self {
            manifest_path,
            records,
        };
        if mgr.records.len() != before {
            let _ = mgr.save();
        }
        mgr
    }

    pub fn save(&self) -> Result<(), String> {
        if let Some(parent) = self.manifest_path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("Create config dir failed: {e}"))?;
        }
        let json = serde_json::to_string_pretty(&self.records)
            .map_err(|e| format!("Serialize installed.json failed: {e}"))?;
        let tmp = self.manifest_path.with_extension("json.tmp");
        fs::write(&tmp, json).map_err(|e| format!("Write installed.json tmp failed: {e}"))?;
        fs::rename(&tmp, &self.manifest_path)
            .map_err(|e| format!("Rename installed.json failed: {e}"))
    }

    pub fn is_installed(&self, id: &str, file_path: Option<&str>) -> bool {
        if let Some(p) = file_path {
            if self.records.contains_key(p) && Path::new(p).exists() {
                return true;
            }
        }
        self.records
            .values()
            .any(|r| r.id == id && Path::new(&r.file_path).exists())
    }

    pub fn installed_ids(&self) -> HashSet<String> {
        self.records
            .values()
            .filter(|r| Path::new(&r.file_path).exists())
            .map(|r| r.id.clone())
            .collect()
    }

    pub fn local_path_for_id(&self, id: &str) -> Option<String> {
        self.records
            .values()
            .find(|r| r.id == id && Path::new(&r.file_path).exists())
            .map(|r| r.file_path.clone())
    }

    pub fn register_download(&mut self, item: &WallpaperItem, local_path: &Path) {
        let abs = local_path.to_string_lossy().into_owned();
        let file_size = fs::metadata(local_path).map(|m| m.len()).unwrap_or(item.file_size);
        let ext = local_path
            .extension()
            .and_then(|e| e.to_str())
            .map(|s| s.to_lowercase())
            .unwrap_or_default();
        let is_animated = item.is_animated || VIDEO_EXTS.contains(&ext.as_str());

        let (mut w, mut h) = (item.dimension_x, item.dimension_y);
        if w == 0 || h == 0 {
            if is_animated {
                if let Some((vw, vh)) = probe_video_dimensions(local_path) {
                    w = vw;
                    h = vh;
                }
            } else if let Ok((iw, ih)) = image::image_dimensions(local_path) {
                w = iw;
                h = ih;
            }
        }
        let resolution = if w > 0 && h > 0 {
            format!("{w}x{h}")
        } else {
            item.resolution.clone()
        };
        let ratio = if h > 0 {
            format!("{:.2}", w as f64 / h as f64)
        } else {
            item.ratio.clone()
        };

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);

        let rec = InstalledRecord {
            id: item.id.clone(),
            title: item.display_title(),
            source: item.source.clone(),
            file_path: abs.clone(),
            file_size,
            is_animated,
            resolution,
            dimension_x: w,
            dimension_y: h,
            ratio,
            thumb_url: item.thumb_url().to_string(),
            url: item.url.clone(),
            tags: item.tags.clone(),
            colors: item.colors.clone(),
            category: item.category.clone(),
            purity: item.purity.clone(),
            installed_at: now,
        };
        self.records.insert(abs, rec);
        let _ = self.save();
    }

    pub fn scan_directory(&mut self, download_dir: &Path) -> usize {
        if !download_dir.is_dir() {
            return 0;
        }
        let mut added = 0usize;
        let Ok(entries) = fs::read_dir(download_dir) else {
            return 0;
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            let ext = path
                .extension()
                .and_then(|e| e.to_str())
                .map(|s| s.to_lowercase())
                .unwrap_or_default();
            let is_video = VIDEO_EXTS.contains(&ext.as_str());
            let is_static = STATIC_EXTS.contains(&ext.as_str());
            if !is_video && !is_static {
                continue;
            }

            let abs = path.to_string_lossy().into_owned();
            if self.records.contains_key(&abs) {
                continue;
            }

            let file_size = entry.metadata().map(|m| m.len()).unwrap_or(0);
            let stem = path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("Wallpaper")
                .to_string();

            let (w, h) = if is_video {
                probe_video_dimensions(&path).unwrap_or((0, 0))
            } else {
                image::image_dimensions(&path).unwrap_or((0, 0))
            };
            let resolution = if w > 0 && h > 0 {
                format!("{w}x{h}")
            } else {
                String::new()
            };
            let ratio = if h > 0 {
                format!("{:.2}", w as f64 / h as f64)
            } else {
                String::new()
            };

            let mtime = entry
                .metadata()
                .and_then(|m| m.modified())
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_secs_f64())
                .unwrap_or(0.0);

            let rec = InstalledRecord {
                id: format!("local-{}", stem),
                title: stem,
                source: "local".to_string(),
                file_path: abs.clone(),
                file_size,
                is_animated: is_video,
                resolution,
                dimension_x: w,
                dimension_y: h,
                ratio,
                thumb_url: abs.clone(),
                url: String::new(),
                tags: Vec::new(),
                colors: Vec::new(),
                category: if is_video { "live" } else { "general" }.to_string(),
                purity: "sfw".to_string(),
                installed_at: mtime,
            };
            self.records.insert(abs, rec);
            added += 1;
        }

        if added > 0 {
            let _ = self.save();
        }
        added
    }

    pub fn uninstall(&mut self, file_path: &str, delete_file: bool) -> Result<(), String> {
        self.records.remove(file_path);
        let _ = self.save();
        if delete_file {
            let p = Path::new(file_path);
            if p.exists() {
                fs::remove_file(p).map_err(|e| format!("Delete file failed: {e}"))?;
            }
        }
        Ok(())
    }

    pub fn get_stats(&self) -> InstalledStats {
        let mut stats = InstalledStats::default();
        for rec in self.records.values() {
            if !Path::new(&rec.file_path).exists() {
                continue;
            }
            stats.total += 1;
            if rec.is_animated {
                stats.live_count += 1;
            } else {
                stats.static_count += 1;
            }
            stats.total_bytes += rec.file_size;
        }
        stats
    }

    pub fn search(
        &self,
        query: &str,
        media_filter: &str,
        source_filter: &str,
        sort: &str,
    ) -> Vec<WallpaperItem> {
        let q = query.trim().to_lowercase();
        let mut matched: Vec<&InstalledRecord> = self
            .records
            .values()
            .filter(|rec| {
                if !Path::new(&rec.file_path).exists() {
                    return false;
                }
                match media_filter {
                    "static" if rec.is_animated => return false,
                    "live" if !rec.is_animated => return false,
                    _ => {}
                }
                if source_filter != "all"
                    && !source_filter.is_empty()
                    && !rec.source.eq_ignore_ascii_case(source_filter)
                {
                    return false;
                }
                if !q.is_empty() {
                    let hit = rec.title.to_lowercase().contains(&q)
                        || rec.id.to_lowercase().contains(&q)
                        || rec.tags.iter().any(|t| t.to_lowercase().contains(&q));
                    if !hit {
                        return false;
                    }
                }
                true
            })
            .collect();

        match sort {
            "name" => matched.sort_by(|a, b| a.title.to_lowercase().cmp(&b.title.to_lowercase())),
            "size" => matched.sort_by(|a, b| b.file_size.cmp(&a.file_size)),
            _ => matched.sort_by(|a, b| {
                b.installed_at
                    .partial_cmp(&a.installed_at)
                    .unwrap_or(std::cmp::Ordering::Equal)
            }),
        }

        matched.into_iter().map(|r| r.to_wallpaper_item()).collect()
    }
}

fn probe_video_dimensions(path: &Path) -> Option<(u32, u32)> {
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
        ])
        .arg(path)
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&out.stdout);
    let (w, h) = text.trim().split_once('x')?;
    Some((w.parse().ok()?, h.parse().ok()?))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn installed_manager_parses_registers_searches_and_uninstalls() {
        let dir = std::env::temp_dir().join("komorebi_test_installed_rs");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        let img_path = dir.join("wallhaven-abc123.png");
        fs::write(&img_path, b"fake-png-bytes-123456").unwrap();

        let manifest = dir.join("installed.json");
        let mut mgr = InstalledManager::load_from_path(manifest.clone());

        let item = WallpaperItem {
            id: "abc123".to_string(),
            title: "Test Sky".to_string(),
            source: "wallhaven".to_string(),
            dimension_x: 1920,
            dimension_y: 1080,
            resolution: "1920x1080".to_string(),
            ..Default::default()
        };
        mgr.register_download(&item, &img_path);
        assert!(mgr.is_installed("abc123", None));

        let reloaded = InstalledManager::load_from_path(manifest);
        assert_eq!(reloaded.get_stats().total, 1);
        assert_eq!(reloaded.search("sky", "all", "all", "date").len(), 1);

        let _ = fs::remove_dir_all(&dir);
    }
}
