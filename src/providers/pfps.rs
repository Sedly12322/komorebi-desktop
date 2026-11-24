use std::fs;
use std::io::{Cursor, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::AtomicBool;
use std::sync::OnceLock;

use regex::Regex;
use reqwest::blocking::Client;

use crate::models::{sanitize_filename, PfpItem};
use crate::providers::download_file;

pub const PFP_BASE_URL: &str = "https://pfps.gg";

pub const PFP_CATEGORIES: &[(&str, &str)] = &[
    ("all", "All"),
    ("anime", "Anime"),
    ("animated", "Animated GIFs"),
    ("aesthetic", "Aesthetic"),
    ("gaming", "Gaming"),
    ("cute", "Cute"),
    ("meme", "Meme"),
    ("dark", "Dark"),
    ("matching", "Matching"),
    ("boy", "Boy"),
    ("girl", "Girl"),
    ("cool", "Cool"),
    ("black", "Black"),
    ("blue", "Blue"),
];

pub const PFP_SORTING: &[(&str, &str)] = &[
    ("latest", "Latest"),
    ("downloads", "Most Downloaded"),
    ("oldest", "Oldest"),
];

pub fn build_pfp_url(category: &str, sort: &str, query: &str, page: usize) -> String {
    let q = query.trim();
    if !q.is_empty() {
        format!("{PFP_BASE_URL}/search?q={}&page={page}", urlencoding::encode(q))
    } else if category == "all" && page == 1 && sort == "latest" {
        PFP_BASE_URL.to_string()
    } else if category == "all" {
        format!("{PFP_BASE_URL}?sort={sort}&page={page}")
    } else {
        format!("{PFP_BASE_URL}/pfps/{category}?sort={sort}&page={page}")
    }
}

pub fn fetch_pfps(
    client: &Client,
    category: &str,
    sort: &str,
    query: &str,
    page: usize,
) -> Result<(Vec<PfpItem>, bool), String> {
    let url = build_pfp_url(category, sort, query, page.max(1));
    let resp = client
        .get(&url)
        .header("Referer", PFP_BASE_URL)
        .send()
        .map_err(|e| format!("pfps.gg request failed: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("pfps.gg HTTP {}", resp.status().as_u16()));
    }

    let html = resp
        .text()
        .map_err(|e| format!("Failed to read pfps.gg HTML: {e}"))?;
    Ok(parse_pfps_html(&html, category))
}

pub fn parse_pfps_html(html: &str, category: &str) -> (Vec<PfpItem>, bool) {
    static CARD_RE: OnceLock<Regex> = OnceLock::new();
    static IMG_RE: OnceLock<Regex> = OnceLock::new();
    static TITLE_RE: OnceLock<Regex> = OnceLock::new();
    static HREF_RE: OnceLock<Regex> = OnceLock::new();
    static EXT_RE: OnceLock<Regex> = OnceLock::new();
    static DL_RE: OnceLock<Regex> = OnceLock::new();

    let card_re = CARD_RE.get_or_init(|| {
        Regex::new(r#"(?s)<article class=["'][^"']*item[^"']*["'][^>]*>(.*?)</article>"#).unwrap()
    });
    let img_re = IMG_RE
        .get_or_init(|| Regex::new(r#"<img[^>]+src=["'](https://cdn\.pfps\.gg/pfps/[^"']+)["']"#).unwrap());
    let title_re = TITLE_RE
        .get_or_init(|| Regex::new(r#"(?s)<span[^>]*class=["']line-clamp-1[^"']*["'][^>]*>(.*?)</span>"#).unwrap());
    let href_re = HREF_RE.get_or_init(|| Regex::new(r#"href=["']/pfp/([^"']+)["']"#).unwrap());
    let ext_re = EXT_RE
        .get_or_init(|| Regex::new(r#"(?s)<span[^>]*class=["']uppercase[^"']*["'][^>]*>(.*?)</span>"#).unwrap());
    let dl_re = DL_RE.get_or_init(|| Regex::new(r#"fa-download[^"]*["']></i>\s*([\d,]+)"#).unwrap());

    let mut items = Vec::new();
    for cap in card_re.captures_iter(html) {
        let block = cap.get(1).map(|m| m.as_str()).unwrap_or("");
        let Some(img_cap) = img_re.captures(block) else {
            continue;
        };
        let img_url = img_cap[1].to_string();
        let raw_title = title_re
            .captures(block)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str())
            .unwrap_or("Avatar");
        let title = html_escape::decode_html_entities(raw_title).trim().to_string();

        let slug = href_re
            .captures(block)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().to_string())
            .unwrap_or_else(|| format!("pfp-{}", items.len() + 1));

        let fmt = ext_re
            .captures(block)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().trim().to_lowercase())
            .unwrap_or_else(|| {
                if img_url.ends_with(".gif") {
                    "gif".to_string()
                } else if img_url.ends_with(".webp") {
                    "webp".to_string()
                } else {
                    "png".to_string()
                }
            });

        let downloads = dl_re
            .captures(block)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().trim().to_string())
            .unwrap_or_else(|| "0".to_string());

        let page_url = format!("{PFP_BASE_URL}/pfp/{slug}");

        items.push(PfpItem {
            id: slug,
            title,
            image_url: img_url,
            format: fmt,
            downloads,
            category: category.to_string(),
            page_url,
        });
    }

    let has_next = html.contains("next-page") || items.len() >= 30;
    (items, has_next)
}

pub fn default_avatar_dir() -> PathBuf {
    dirs::picture_dir()
        .unwrap_or_else(|| {
            dirs::home_dir()
                .unwrap_or_else(|| PathBuf::from("."))
                .join("Pictures")
        })
        .join("Komorebi")
        .join("Avatars")
}

pub fn download_pfp(
    client: &Client,
    item: &PfpItem,
    dest_dir: &Path,
    cancelled: &AtomicBool,
) -> Result<PathBuf, String> {
    fs::create_dir_all(dest_dir).map_err(|e| format!("Create avatar dir failed: {e}"))?;
    let safe_name = sanitize_filename(&item.filename());
    let dest = dest_dir.join(safe_name);
    download_file(
        client,
        &item.image_url,
        &dest,
        &[("Referer", PFP_BASE_URL)],
        |_, _| {},
        cancelled,
    )?;
    Ok(dest)
}

pub fn copy_image_bytes_to_clipboard(raw_bytes: &[u8]) -> Result<(), String> {
    let img = image::load_from_memory(raw_bytes).map_err(|e| format!("Decode image failed: {e}"))?;

    #[cfg(target_os = "linux")]
    if std::env::var_os("WAYLAND_DISPLAY").is_some() {
        let mut png_bytes = Vec::new();
        if img
            .write_to(&mut Cursor::new(&mut png_bytes), image::ImageFormat::Png)
            .is_ok()
        {
            if let Ok(mut child) = Command::new("wl-copy")
                .args(["--type", "image/png"])
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
            {
                if let Some(mut stdin) = child.stdin.take() {
                    let _ = stdin.write_all(&png_bytes);
                }
                if let Ok(status) = child.wait() {
                    if status.success() {
                        return Ok(());
                    }
                }
            }
        }
    }

    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut clipboard = arboard::Clipboard::new().map_err(|e| format!("Clipboard unavailable: {e}"))?;
    clipboard
        .set_image(arboard::ImageData {
            width: w as usize,
            height: h as usize,
            bytes: std::borrow::Cow::Owned(rgba.into_raw()),
        })
        .map_err(|e| format!("Clipboard write failed: {e}"))
}

pub fn copy_image_to_clipboard(local_path: &Path) -> Result<(), String> {
    let bytes = fs::read(local_path).map_err(|e| format!("Read image failed: {e}"))?;
    copy_image_bytes_to_clipboard(&bytes)
}

pub fn set_system_avatar(local_path: &Path, title: &str) -> Result<String, String> {
    let home = dirs::home_dir().ok_or_else(|| "Home directory unavailable".to_string())?;
    let face = home.join(".face");
    let face_icon = home.join(".face.icon");

    // Hyprlock and display managers read static raster avatars cleanly at ~/.face.icon;
    // convert animated GIF/WebP first frame to PNG when needed while copying raw bytes for PNG/JPEG.
    let ext = local_path
        .extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_lowercase())
        .unwrap_or_default();

    if ext == "gif" || ext == "webp" {
        let img = image::open(local_path).map_err(|e| format!("Failed to decode avatar: {e}"))?;
        img.save_with_format(&face_icon, image::ImageFormat::Png)
            .map_err(|e| format!("Failed to write ~/.face.icon: {e}"))?;
        img.save_with_format(&face, image::ImageFormat::Png)
            .map_err(|e| format!("Failed to write ~/.face: {e}"))?;
    } else {
        fs::copy(local_path, &face_icon)
            .map_err(|e| format!("Failed to copy to ~/.face.icon: {e}"))?;
        fs::copy(local_path, &face).map_err(|e| format!("Failed to copy to ~/.face: {e}"))?;
    }

    // Update ~/.config/serpantinum/settings.json if it exists
    let serp_cfg = home.join(".config/serpantinum/settings.json");
    if serp_cfg.exists() {
        if let Ok(raw) = fs::read_to_string(&serp_cfg) {
            if let Ok(mut json) = serde_json::from_str::<serde_json::Value>(&raw) {
                if let Some(obj) = json.as_object_mut() {
                    let general = obj
                        .entry("general")
                        .or_insert_with(|| serde_json::Value::Object(serde_json::Map::new()));
                    if let Some(g_obj) = general.as_object_mut() {
                        g_obj.insert(
                            "avatarPath".to_string(),
                            serde_json::Value::String(face_icon.to_string_lossy().into_owned()),
                        );
                    }
                    if let Ok(pretty) = serde_json::to_string_pretty(&json) {
                        let _ = fs::write(&serp_cfg, pretty);
                    }
                }
            }
        }
    }

    #[cfg(target_os = "linux")]
    {
        let _ = std::process::Command::new("notify-send")
            .args([
                "-a",
                "Komorebi",
                "Avatar updated",
                &format!("Set system avatar: {title}"),
            ])
            .spawn();
    }

    Ok(face_icon.to_string_lossy().into_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_pfps_html_cards() {
        let html = r#"
        <article class="item shadow-sm">
            <a href="/pfp/gojo-123">
                <img src="https://cdn.pfps.gg/pfps/gojo-123.gif" />
                <span class="line-clamp-1 font-medium">Satoru Gojo</span>
                <span class="uppercase text-xs">GIF</span>
                <i class="fa fa-download"></i> 14,500
            </a>
        </article>
        "#;
        let (items, has_next) = parse_pfps_html(html, "anime");
        assert!(!has_next);
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].id, "gojo-123");
        assert_eq!(items[0].title, "Satoru Gojo");
        assert_eq!(items[0].format, "gif");
        assert_eq!(items[0].downloads, "14,500");
        assert!(items[0].is_animated());
        assert_eq!(PfpItem::format_download_count("14,500"), "14.5k");
    }
}
