use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

pub fn config_dir() -> PathBuf {
    #[cfg(target_os = "windows")]
    let base = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
    #[cfg(not(target_os = "windows"))]
    let base = dirs::home_dir()
        .map(|h| h.join(".config"))
        .unwrap_or_else(|| PathBuf::from("."));

    let new_dir = base.join("komorebi-desktop");
    let old_dir = base.join("wallhaven-desktop");
    if !new_dir.exists() && old_dir.exists() {
        let _ = copy_dir_all(&old_dir, &new_dir);
    }
    new_dir
}

pub fn config_file_path() -> PathBuf {
    config_dir().join("config.json")
}

fn copy_dir_all(src: &Path, dst: &Path) -> std::io::Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let ty = entry.file_type()?;
        if ty.is_dir() {
            copy_dir_all(&entry.path(), &dst.join(entry.file_name()))?;
        } else {
            fs::copy(entry.path(), dst.join(entry.file_name()))?;
        }
    }
    Ok(())
}

pub fn default_download_dir() -> PathBuf {
    if let Some(home) = dirs::home_dir() {
        let candidates = [
            home.join("Obrázky").join("Wallpapers"),
            home.join("Pictures").join("Wallpapers"),
            home.join("wallpapers"),
            home.join("Pictures"),
            home.join("Obrázky"),
            home.join("Downloads"),
            home.join("Stažené"),
        ];
        for c in candidates {
            if c.is_dir() {
                return c;
            }
        }
        let fallback = home.join("Pictures").join("Wallpapers");
        let _ = fs::create_dir_all(&fallback);
        return fallback;
    }
    PathBuf::from(".")
}

fn default_theme() -> String {
    #[cfg(not(target_os = "windows"))]
    if let Some(home) = dirs::home_dir() {
        if home.join(".local/state/serpantinum/qs_colors.json").exists()
            || home.join(".cache/quickshell/matugen.json").exists()
        {
            return "matugen".into();
        }
    }
    "dark".into()
}

fn default_categories() -> String {
    "111".into()
}
fn default_purity() -> String {
    "100".into()
}
fn default_sorting() -> String {
    "toplist".into()
}
fn default_top_range() -> String {
    "1M".into()
}
fn default_per_page() -> usize {
    24
}
fn default_wallpaper_setter() -> String {
    "auto".into()
}
fn default_wallpaper_monitor() -> String {
    "all".into()
}
fn default_moewalls_category() -> String {
    "all".into()
}
fn default_language() -> String {
    "en".into()
}
fn default_card_size() -> String {
    "normal".into()
}
fn default_true() -> bool {
    true
}
fn default_download_dir_str() -> String {
    default_download_dir().to_string_lossy().into_owned()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct AppConfig {
    pub api_key: String,
    #[serde(default = "default_download_dir_str")]
    pub default_download_dir: String,
    #[serde(default = "default_categories")]
    pub categories: String,
    #[serde(default = "default_purity")]
    pub purity: String,
    #[serde(default = "default_sorting")]
    pub sorting: String,
    #[serde(default = "default_top_range")]
    pub top_range: String,
    pub atleast: String,
    pub ratios: String,
    pub color: String,
    #[serde(default = "default_per_page")]
    pub per_page: usize,
    #[serde(default = "default_theme")]
    pub theme: String,
    pub auto_set_wallpaper: bool,
    #[serde(default = "default_wallpaper_setter")]
    pub wallpaper_setter: String,
    #[serde(default = "default_wallpaper_monitor")]
    pub wallpaper_monitor: String,
    pub custom_wallpaper_cmd: String,
    pub custom_video_wallpaper_cmd: String,
    #[serde(default = "default_moewalls_category")]
    pub moewalls_category: String,
    #[serde(default = "default_language")]
    pub language: String,
    #[serde(default = "default_true")]
    pub background_effects: bool,
    #[serde(default = "default_true")]
    pub check_updates_on_launch: bool,
    pub last_update_check: f64,
    #[serde(default = "default_card_size")]
    pub card_size: String,

    #[serde(flatten)]
    pub extra: BTreeMap<String, serde_json::Value>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            api_key: String::new(),
            default_download_dir: default_download_dir_str(),
            categories: default_categories(),
            purity: default_purity(),
            sorting: default_sorting(),
            top_range: default_top_range(),
            atleast: String::new(),
            ratios: String::new(),
            color: String::new(),
            per_page: default_per_page(),
            theme: default_theme(),
            auto_set_wallpaper: false,
            wallpaper_setter: default_wallpaper_setter(),
            wallpaper_monitor: default_wallpaper_monitor(),
            custom_wallpaper_cmd: String::new(),
            custom_video_wallpaper_cmd: String::new(),
            moewalls_category: default_moewalls_category(),
            language: default_language(),
            background_effects: true,
            check_updates_on_launch: true,
            last_update_check: 0.0,
            card_size: default_card_size(),
            extra: BTreeMap::new(),
        }
    }
}

impl AppConfig {
    pub fn load() -> Self {
        let path = config_file_path();
        Self::load_from(&path)
    }

    pub fn load_from(path: &Path) -> Self {
        if path.exists() {
            if let Ok(content) = fs::read_to_string(path) {
                if let Ok(mut cfg) = serde_json::from_str::<AppConfig>(&content) {
                    if cfg.default_download_dir.trim().is_empty()
                        || !Path::new(&cfg.default_download_dir).is_dir()
                    {
                        cfg.default_download_dir = default_download_dir_str();
                    }
                    if cfg.wallpaper_monitor.trim().is_empty() {
                        cfg.wallpaper_monitor = "all".into();
                    }
                    if cfg.wallpaper_setter.trim().is_empty() {
                        cfg.wallpaper_setter = "auto".into();
                    }
                    return cfg;
                }
            }
        }
        let cfg = Self::default();
        let _ = cfg.save_to(path);
        cfg
    }

    pub fn save(&self) -> Result<(), String> {
        self.save_to(&config_file_path())
    }

    pub fn save_to(&self, path: &Path) -> Result<(), String> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let json = serde_json::to_string_pretty(self).map_err(|e| e.to_string())?;
        let tmp = path.with_extension("json.tmp");
        fs::write(&tmp, json).map_err(|e| e.to_string())?;
        fs::rename(&tmp, path).map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn effective_download_dir(&self) -> PathBuf {
        let p = PathBuf::from(&self.default_download_dir);
        if p.is_dir() {
            p
        } else {
            default_download_dir()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_v206_config_and_preserves_unknown_keys() {
        let raw = r#"{
            "api_key": "abc123",
            "default_download_dir": "/tmp",
            "categories": "110",
            "purity": "100",
            "sorting": "toplist",
            "top_range": "1M",
            "atleast": "",
            "ratios": "16x9",
            "color": "",
            "per_page": 24,
            "theme": "terminal_ice",
            "auto_set_wallpaper": true,
            "wallpaper_setter": "auto",
            "wallpaper_monitor": "all",
            "custom_wallpaper_cmd": "",
            "custom_video_wallpaper_cmd": "",
            "moewalls_category": "anime",
            "language": "cs",
            "background_effects": true,
            "check_updates_on_launch": true,
            "last_update_check": 1794416508.3492188,
            "card_size": "normal",
            "future_unknown_flag": 42
        }"#;
        let cfg: AppConfig = serde_json::from_str(raw).unwrap();
        assert_eq!(cfg.theme, "terminal_ice");
        assert_eq!(cfg.card_size, "normal");
        assert_eq!(cfg.language, "cs");
        assert!(cfg.auto_set_wallpaper);
        assert_eq!(cfg.extra.get("future_unknown_flag").and_then(|v| v.as_i64()), Some(42));
    }
}
