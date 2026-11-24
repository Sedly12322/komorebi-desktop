use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum NavMode {
    Wallhaven,
    MoeWalls,
    Osu,
    Pfps,
    Installed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CardSize {
    Compact,
    Normal,
    Large,
}

impl CardSize {
    pub fn from_str_lossy(s: &str) -> Self {
        match s.trim().to_ascii_lowercase().as_str() {
            "compact" => Self::Compact,
            "large" => Self::Large,
            _ => Self::Normal,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Compact => "compact",
            Self::Normal => "normal",
            Self::Large => "large",
        }
    }

    /// Returns `(card_w, card_h, img_w, img_h)`.
    pub fn dimensions(&self) -> (f32, f32, f32, f32) {
        match self {
            Self::Compact => (236.0, 176.0, 224.0, 130.0),
            Self::Normal => (296.0, 218.0, 284.0, 172.0),
            Self::Large => (368.0, 266.0, 356.0, 220.0),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WallpaperItem {
    pub id: String,
    pub title: String,
    pub url: String,
    pub short_url: String,
    pub views: u64,
    pub favorites: u64,
    pub source: String,
    pub origin_url: String,
    pub purity: String,
    pub category: String,
    pub dimension_x: u32,
    pub dimension_y: u32,
    pub resolution: String,
    pub ratio: String,
    pub file_size: u64,
    pub file_type: String,
    pub created_at: String,
    pub colors: Vec<String>,
    pub path: String,
    pub thumb_large: String,
    pub thumb_small: String,
    pub thumb_original: String,
    pub tags: Vec<String>,
    pub uploader: String,
    pub is_animated: bool,
    pub preview_video_url: String,
    pub is_installed: bool,
    pub local_path: String,
    pub osu_season: String,
    pub osu_theme: String,
    pub osu_rank: u32,
    pub osu_contest_id: u32,
}

impl Default for WallpaperItem {
    fn default() -> Self {
        Self {
            id: String::new(),
            title: String::new(),
            url: String::new(),
            short_url: String::new(),
            views: 0,
            favorites: 0,
            source: String::new(),
            origin_url: String::new(),
            purity: "sfw".into(),
            category: "general".into(),
            dimension_x: 0,
            dimension_y: 0,
            resolution: String::new(),
            ratio: String::new(),
            file_size: 0,
            file_type: String::new(),
            created_at: String::new(),
            colors: Vec::new(),
            path: String::new(),
            thumb_large: String::new(),
            thumb_small: String::new(),
            thumb_original: String::new(),
            tags: Vec::new(),
            uploader: String::new(),
            is_animated: false,
            preview_video_url: String::new(),
            is_installed: false,
            local_path: String::new(),
            osu_season: String::new(),
            osu_theme: String::new(),
            osu_rank: 0,
            osu_contest_id: 0,
        }
    }
}

impl WallpaperItem {
    pub fn display_title(&self) -> String {
        if !self.title.is_empty() {
            return self.title.clone();
        }
        if !self.osu_season.is_empty() {
            return format!("osu! {} #{}", self.osu_season, self.id);
        }
        if self.source.is_empty() {
            format!("#{}", self.id)
        } else {
            format!("{} #{}", self.source, self.id)
        }
    }

    pub fn human_file_size(&self) -> String {
        format_bytes(self.file_size)
    }

    pub fn thumb_url(&self) -> &str {
        if !self.thumb_large.is_empty() {
            &self.thumb_large
        } else if !self.thumb_small.is_empty() {
            &self.thumb_small
        } else if !self.local_path.is_empty() {
            &self.local_path
        } else {
            &self.path
        }
    }

    pub fn preview_image_url(&self) -> &str {
        if !self.local_path.is_empty() && !self.is_animated {
            &self.local_path
        } else if !self.is_animated && !self.path.is_empty() {
            &self.path
        } else if !self.thumb_original.is_empty() {
            &self.thumb_original
        } else {
            self.thumb_url()
        }
    }

    pub fn suggested_filename(&self) -> String {
        if !self.local_path.is_empty() {
            if let Some(name) = std::path::Path::new(&self.local_path).file_name() {
                return name.to_string_lossy().into_owned();
            }
        }
        let ext = guess_extension(&self.path, &self.file_type, self.is_animated);
        if self.source.eq_ignore_ascii_case("MoeWalls") || self.is_animated {
            let clean = sanitize_filename(if self.title.is_empty() { &self.id } else { &self.title });
            format!("moewalls-{}.{}", clean, ext)
        } else if !self.osu_season.is_empty() {
            let season = sanitize_filename(&self.osu_season);
            let artist = sanitize_filename(if self.uploader.is_empty() { "artist" } else { &self.uploader });
            let title = sanitize_filename(if self.title.is_empty() { &self.id } else { &self.title });
            format!("osu-{}-{}-{}.{}", season, artist, title, ext)
        } else {
            format!("wallhaven-{}.{}", sanitize_filename(&self.id), ext)
        }
    }
}

pub fn format_bytes(size: u64) -> String {
    if size == 0 {
        return "N/A".to_string();
    }
    let mut s = size as f64;
    for unit in ["B", "KB", "MB", "GB"] {
        if s < 1024.0 {
            return format!("{:.1} {}", s, unit);
        }
        s /= 1024.0;
    }
    format!("{:.1} TB", s)
}

pub fn sanitize_filename(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    for ch in raw.chars() {
        if ch.is_ascii_alphanumeric() || ch == '-' || ch == '_' || ch == '.' {
            out.push(ch);
        } else if ch.is_whitespace() {
            out.push('_');
        }
    }
    while out.contains("__") {
        out = out.replace("__", "_");
    }
    let trimmed = out.trim_matches('_').to_string();
    if trimmed.is_empty() {
        "wallpaper".into()
    } else {
        trimmed
    }
}

fn guess_extension(url_or_path: &str, file_type: &str, is_animated: bool) -> &'static str {
    let clean = url_or_path.split('?').next().unwrap_or(url_or_path).to_ascii_lowercase();
    if clean.ends_with(".png") || file_type.contains("png") {
        "png"
    } else if clean.ends_with(".webp") || file_type.contains("webp") {
        "webp"
    } else if clean.ends_with(".gif") || file_type.contains("gif") {
        "gif"
    } else if clean.ends_with(".webm") || file_type.contains("webm") {
        "webm"
    } else if clean.ends_with(".mp4") || file_type.contains("mp4") || is_animated {
        "mp4"
    } else {
        "jpg"
    }
}

#[derive(Debug, Clone, Default)]
pub struct SearchResult {
    pub items: Vec<WallpaperItem>,
    pub current_page: usize,
    pub last_page: usize,
    pub per_page: usize,
    pub total: usize,
}

#[derive(Debug, Clone)]
pub struct PfpItem {
    pub id: String,
    pub title: String,
    pub image_url: String,
    pub format: String,
    pub downloads: String,
    pub category: String,
    pub page_url: String,
}

impl PfpItem {
    pub fn is_animated(&self) -> bool {
        self.format.eq_ignore_ascii_case("gif")
            || self.image_url.to_ascii_lowercase().ends_with(".gif")
    }

    pub fn filename(&self) -> String {
        let ext = self.format.trim_start_matches('.').to_ascii_lowercase();
        let ext = if ext.is_empty() { "png" } else { ext.as_str() };
        let safe_title: String = self
            .title
            .chars()
            .map(|c| {
                if c.is_alphanumeric() || c == '-' || c == '_' || c == '.' {
                    c
                } else {
                    '_'
                }
            })
            .collect();
        let safe_id: String = self
            .id
            .chars()
            .map(|c| {
                if c.is_alphanumeric() || c == '-' || c == '_' {
                    c
                } else {
                    '_'
                }
            })
            .collect();
        format!("{}_{}.{}", safe_title, safe_id, ext)
    }

    pub fn format_download_count(count: &str) -> String {
        let cleaned: String = count.replace(',', "").trim().to_string();
        if let Ok(val) = cleaned.parse::<u64>() {
            if val >= 1_000_000 {
                return format!("{:.1}M", val as f64 / 1_000_000.0);
            }
            if val >= 1_000 {
                return format!("{:.1}k", val as f64 / 1_000.0);
            }
            return val.to_string();
        }
        if count.trim().is_empty() {
            "0".into()
        } else {
            count.trim().to_string()
        }
    }
}
