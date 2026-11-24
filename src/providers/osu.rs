use std::collections::BTreeSet;
use std::sync::OnceLock;

use serde::Deserialize;

use crate::models::{SearchResult, WallpaperItem};

const EMBEDDED_OSU_JSON: &str = include_str!("../../assets/osu_seasonal.json");

#[derive(Debug, Deserialize, Clone)]
struct RawOsuEntry {
    id: String,
    #[serde(default)]
    contest_id: u32,
    #[serde(default)]
    contest_name: String,
    #[serde(default)]
    season: String,
    #[serde(default)]
    theme: String,
    #[serde(default)]
    title: String,
    #[serde(default)]
    artist: String,
    #[serde(default)]
    votes: u64,
    #[serde(default)]
    rank: u32,
    #[serde(default)]
    width: u32,
    #[serde(default)]
    height: u32,
    #[serde(default)]
    resolution: String,
    #[serde(default)]
    preview_url: String,
    #[serde(default)]
    thumbnail_url: String,
    #[serde(default)]
    contest_url: String,
    #[serde(default)]
    is_clean: bool,
}

static OSU_ITEMS: OnceLock<Vec<WallpaperItem>> = OnceLock::new();

fn load_items() -> &'static [WallpaperItem] {
    OSU_ITEMS.get_or_init(|| {
        let raw: Vec<RawOsuEntry> = serde_json::from_str(EMBEDDED_OSU_JSON).unwrap_or_default();
        raw.into_iter()
            .map(|e| {
                let mut tags = Vec::new();
                if !e.season.is_empty() {
                    tags.push(e.season.clone());
                }
                if !e.theme.is_empty() {
                    tags.push(e.theme.clone());
                }
                if !e.contest_name.is_empty() {
                    tags.push(e.contest_name.clone());
                }
                if e.is_clean {
                    tags.push("No Logo".to_string());
                }
                let ratio = if e.height > 0 {
                    format!("{:.2}", e.width as f64 / e.height as f64)
                } else {
                    String::new()
                };
                let res = if !e.resolution.is_empty() {
                    e.resolution
                } else if e.width > 0 && e.height > 0 {
                    format!("{}x{}", e.width, e.height)
                } else {
                    String::new()
                };
                let file_type = if e.preview_url.ends_with(".png") {
                    "image/png"
                } else {
                    "image/jpeg"
                };

                WallpaperItem {
                    id: e.id,
                    title: e.title,
                    url: e.contest_url.clone(),
                    short_url: e.contest_url,
                    favorites: e.votes,
                    source: "osu".to_string(),
                    purity: "sfw".to_string(),
                    category: "anime".to_string(),
                    dimension_x: e.width,
                    dimension_y: e.height,
                    resolution: res,
                    ratio,
                    file_type: file_type.to_string(),
                    path: e.preview_url.clone(),
                    thumb_large: e.thumbnail_url.clone(),
                    thumb_small: e.thumbnail_url.clone(),
                    thumb_original: e.preview_url,
                    tags,
                    uploader: e.artist,
                    osu_season: e.season,
                    osu_theme: e.theme,
                    osu_rank: e.rank,
                    osu_contest_id: e.contest_id,
                    ..Default::default()
                }
            })
            .collect()
    })
}

pub fn total_count() -> usize {
    load_items().len()
}

pub fn seasons() -> Vec<String> {
    let mut set = BTreeSet::new();
    for item in load_items() {
        if !item.osu_season.is_empty() {
            set.insert(item.osu_season.clone());
        }
    }
    set.into_iter().collect()
}

pub fn themes() -> Vec<String> {
    let mut set = BTreeSet::new();
    for item in load_items() {
        if !item.osu_theme.is_empty() {
            set.insert(item.osu_theme.clone());
        }
    }
    set.into_iter().collect()
}

#[derive(Debug, Clone)]
pub struct OsuSearchParams {
    pub query: String,
    pub season: String,
    pub theme: String,
    pub sort: String,
    pub clean_only: bool,
    pub page: usize,
    pub per_page: usize,
}

impl Default for OsuSearchParams {
    fn default() -> Self {
        Self {
            query: String::new(),
            season: "all".to_string(),
            theme: "all".to_string(),
            sort: "votes".to_string(),
            clean_only: false,
            page: 1,
            per_page: 24,
        }
    }
}

pub fn search(params: &OsuSearchParams) -> SearchResult {
    let q = params.query.trim().to_lowercase();
    let mut filtered: Vec<WallpaperItem> = load_items()
        .iter()
        .filter(|item| {
            if params.season != "all"
                && !params.season.is_empty()
                && !item.osu_season.eq_ignore_ascii_case(&params.season)
            {
                return false;
            }
            if params.theme != "all"
                && !params.theme.is_empty()
                && !item.osu_theme.eq_ignore_ascii_case(&params.theme)
            {
                return false;
            }
            if params.clean_only && !item.tags.iter().any(|t| t == "No Logo") {
                return false;
            }
            if !q.is_empty() {
                let hit = item.title.to_lowercase().contains(&q)
                    || item.uploader.to_lowercase().contains(&q)
                    || item.osu_theme.to_lowercase().contains(&q)
                    || item.osu_season.to_lowercase().contains(&q)
                    || item.tags.iter().any(|t| t.to_lowercase().contains(&q));
                if !hit {
                    return false;
                }
            }
            true
        })
        .cloned()
        .collect();

    match params.sort.as_str() {
        "newest" => filtered.sort_by(|a, b| {
            b.osu_contest_id
                .cmp(&a.osu_contest_id)
                .then_with(|| a.osu_rank.cmp(&b.osu_rank))
        }),
        "rank" => filtered.sort_by(|a, b| {
            a.osu_rank
                .cmp(&b.osu_rank)
                .then_with(|| b.favorites.cmp(&a.favorites))
        }),
        _ => filtered.sort_by(|a, b| b.favorites.cmp(&a.favorites)),
    }

    let per_page = params.per_page.max(1);
    let total = filtered.len();
    let last_page = total.div_ceil(per_page).max(1);
    let page = params.page.clamp(1, last_page);
    let start = (page - 1) * per_page;
    let end = (start + per_page).min(total);
    let items = if start < total {
        filtered[start..end].to_vec()
    } else {
        Vec::new()
    };

    SearchResult {
        items,
        current_page: page,
        last_page,
        per_page,
        total,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn loads_embedded_osu_dataset_and_filters() {
        assert_eq!(total_count(), 271);
        let res = search(&OsuSearchParams::default());
        assert_eq!(res.items.len(), 24);
        assert!(res.last_page >= 12);

        let winter = search(&OsuSearchParams {
            theme: "Winter".to_string(),
            sort: "votes".to_string(),
            ..Default::default()
        });
        assert!(!winter.items.is_empty());
        assert!(winter.items.iter().all(|w| w.osu_theme == "Winter"));
    }
}
