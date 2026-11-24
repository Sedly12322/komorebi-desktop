use crate::models::{SearchResult, WallpaperItem};
use reqwest::blocking::Client;
use serde::Deserialize;

const API_BASE_URL: &str = "https://wallhaven.cc/api/v1";
const USER_AGENT: &str = "KomorebiDesktop/3.0 (High-Performance Wallpaper Manager)";

pub const WALLHAVEN_COLOR_CODES: &[&str] = &[
    "660000", "cc0000", "ea4c88", "993399", "333399", "0066cc", "0099ff", "66cccc", "77cc33",
    "336600", "ffff00", "ff9900", "ff6600", "663300", "000000", "424153", "999999", "ffffff",
];

#[derive(Debug, Clone)]
pub struct WallhavenSearchParams {
    pub query: String,
    pub categories: String,
    pub purity: String,
    pub sorting: String,
    pub order: String,
    pub top_range: String,
    pub atleast: String,
    pub ratios: String,
    pub color: String,
    pub page: usize,
    pub seed: String,
    pub api_key: String,
}

impl Default for WallhavenSearchParams {
    fn default() -> Self {
        Self {
            query: String::new(),
            categories: "111".into(),
            purity: "100".into(),
            sorting: "toplist".into(),
            order: "desc".into(),
            top_range: "1M".into(),
            atleast: String::new(),
            ratios: String::new(),
            color: String::new(),
            page: 1,
            seed: String::new(),
            api_key: String::new(),
        }
    }
}

#[derive(Debug, Deserialize)]
struct ApiSearchResponse {
    data: Vec<ApiWallpaper>,
    #[serde(default)]
    meta: ApiMeta,
}

#[derive(Debug, Deserialize)]
struct ApiDetailResponse {
    data: ApiWallpaper,
}

#[derive(Debug, Default, Deserialize)]
struct ApiMeta {
    #[serde(default = "one")]
    current_page: usize,
    #[serde(default = "one")]
    last_page: usize,
    #[serde(default = "default_per_page")]
    per_page: usize,
    #[serde(default)]
    total: usize,
}

fn one() -> usize {
    1
}
fn default_per_page() -> usize {
    24
}

#[derive(Debug, Default, Deserialize)]
struct ApiThumbs {
    #[serde(default)]
    large: String,
    #[serde(default)]
    small: String,
    #[serde(default)]
    original: String,
}

#[derive(Debug, Default, Deserialize)]
struct ApiTag {
    #[serde(default)]
    name: String,
}

#[derive(Debug, Default, Deserialize)]
struct ApiUploader {
    #[serde(default)]
    username: String,
}

#[derive(Debug, Default, Deserialize)]
struct ApiWallpaper {
    #[serde(default)]
    id: String,
    #[serde(default)]
    url: String,
    #[serde(default)]
    short_url: String,
    #[serde(default)]
    views: u64,
    #[serde(default)]
    favorites: u64,
    #[serde(default)]
    source: String,
    #[serde(default)]
    purity: String,
    #[serde(default)]
    category: String,
    #[serde(default)]
    dimension_x: u32,
    #[serde(default)]
    dimension_y: u32,
    #[serde(default)]
    resolution: String,
    #[serde(default)]
    ratio: String,
    #[serde(default)]
    file_size: u64,
    #[serde(default)]
    file_type: String,
    #[serde(default)]
    created_at: String,
    #[serde(default)]
    colors: Vec<String>,
    #[serde(default)]
    path: String,
    #[serde(default)]
    thumbs: ApiThumbs,
    #[serde(default)]
    tags: Vec<ApiTag>,
    #[serde(default)]
    uploader: Option<ApiUploader>,
}

impl From<ApiWallpaper> for WallpaperItem {
    fn from(w: ApiWallpaper) -> Self {
        Self {
            id: w.id,
            title: String::new(),
            url: w.url,
            short_url: w.short_url,
            views: w.views,
            favorites: w.favorites,
            source: "wallhaven".into(),
            origin_url: w.source,
            purity: if w.purity.is_empty() { "sfw".into() } else { w.purity },
            category: if w.category.is_empty() {
                "general".into()
            } else {
                w.category
            },
            dimension_x: w.dimension_x,
            dimension_y: w.dimension_y,
            resolution: w.resolution,
            ratio: w.ratio,
            file_size: w.file_size,
            file_type: w.file_type,
            created_at: w.created_at,
            colors: w.colors,
            path: w.path,
            thumb_large: w.thumbs.large,
            thumb_small: w.thumbs.small,
            thumb_original: w.thumbs.original,
            tags: w.tags.into_iter().map(|t| t.name).filter(|s| !s.is_empty()).collect(),
            uploader: w.uploader.map(|u| u.username).unwrap_or_default(),
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

pub fn search(client: &Client, params: &WallhavenSearchParams) -> Result<SearchResult, String> {
    let mut query_pairs: Vec<(&str, String)> = vec![
        ("page", params.page.to_string()),
        ("categories", params.categories.clone()),
        ("purity", params.purity.clone()),
        ("sorting", params.sorting.clone()),
        ("order", params.order.clone()),
    ];

    let q = params.query.trim();
    if !q.is_empty() {
        query_pairs.push(("q", q.to_string()));
    }
    if params.sorting == "toplist" && !params.top_range.is_empty() {
        query_pairs.push(("topRange", params.top_range.clone()));
    }
    if params.sorting == "random" && !params.seed.is_empty() {
        query_pairs.push(("seed", params.seed.clone()));
    }
    if !params.atleast.is_empty() {
        query_pairs.push(("atleast", params.atleast.clone()));
    }
    if !params.ratios.is_empty() {
        query_pairs.push(("ratios", params.ratios.clone()));
    }
    if !params.color.is_empty() {
        query_pairs.push(("colors", params.color.clone()));
    }
    let key = params.api_key.trim();
    if !key.is_empty() {
        query_pairs.push(("apikey", key.to_string()));
    }

    let url = format!("{}/search", API_BASE_URL);
    let mut req = client
        .get(&url)
        .query(&query_pairs)
        .header("User-Agent", USER_AGENT)
        .header("Accept", "application/json");
    if !key.is_empty() {
        req = req.header("X-API-Key", key);
    }

    let resp = req.send().map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("Wallhaven API HTTP {}", resp.status()));
    }
    let parsed: ApiSearchResponse = resp.json().map_err(|e| e.to_string())?;
    parse_search_response(parsed, params.page)
}

fn parse_search_response(parsed: ApiSearchResponse, fallback_page: usize) -> Result<SearchResult, String> {
    let items: Vec<WallpaperItem> = parsed.data.into_iter().map(WallpaperItem::from).collect();
    let total = if parsed.meta.total == 0 {
        items.len()
    } else {
        parsed.meta.total
    };
    Ok(SearchResult {
        items,
        current_page: parsed.meta.current_page.max(1).max(fallback_page.min(parsed.meta.last_page.max(1))),
        last_page: parsed.meta.last_page.max(1),
        per_page: parsed.meta.per_page.max(1),
        total,
    })
}

pub fn get_detail(client: &Client, wallpaper_id: &str, api_key: &str) -> Result<WallpaperItem, String> {
    let url = format!("{}/w/{}", API_BASE_URL, wallpaper_id);
    let mut req = client
        .get(&url)
        .header("User-Agent", USER_AGENT)
        .header("Accept", "application/json");
    let key = api_key.trim();
    if !key.is_empty() {
        req = req.query(&[("apikey", key)]).header("X-API-Key", key);
    }
    let resp = req.send().map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("Wallhaven detail HTTP {}", resp.status()));
    }
    let parsed: ApiDetailResponse = resp.json().map_err(|e| e.to_string())?;
    Ok(WallpaperItem::from(parsed.data))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_wallhaven_search_json() {
        let json = r##"{
            "data": [{
                "id": "8586my",
                "url": "https://wallhaven.cc/w/8586my",
                "short_url": "https://whvn.cc/8586my",
                "views": 12345,
                "favorites": 420,
                "source": "https://www.pixiv.net/artworks/123",
                "purity": "sfw",
                "category": "anime",
                "dimension_x": 3840,
                "dimension_y": 2160,
                "resolution": "3840x2160",
                "ratio": "1.78",
                "file_size": 2621440,
                "file_type": "image/png",
                "created_at": "2026-01-01",
                "colors": ["#111111", "#6366f1"],
                "path": "https://w.wallhaven.cc/full/85/wallhaven-8586my.png",
                "thumbs": {
                    "large": "https://th.wallhaven.cc/lg/85/8586my.jpg",
                    "original": "https://th.wallhaven.cc/orig/85/8586my.jpg",
                    "small": "https://th.wallhaven.cc/small/85/8586my.jpg"
                }
            }],
            "meta": {
                "current_page": 1,
                "last_page": 10,
                "per_page": 24,
                "total": 240
            }
        }"##;
        let parsed: ApiSearchResponse = serde_json::from_str(json).unwrap();
        let res = parse_search_response(parsed, 1).unwrap();
        assert_eq!(res.items.len(), 1);
        assert_eq!(res.items[0].id, "8586my");
        assert_eq!(res.items[0].source, "wallhaven");
        assert_eq!(res.items[0].origin_url, "https://www.pixiv.net/artworks/123");
        assert_eq!(res.items[0].human_file_size(), "2.5 MB");
        assert_eq!(res.last_page, 10);
        assert_eq!(res.total, 240);
    }
}
