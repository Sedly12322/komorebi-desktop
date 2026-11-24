use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use regex::Regex;
use reqwest::blocking::Client;

use crate::models::{SearchResult, WallpaperItem};

pub const BASE_URL: &str = "https://moewalls.com";

pub const CATEGORIES: &[(&str, &str)] = &[
    ("all", "All"),
    ("anime", "Anime"),
    ("games", "Games"),
    ("sci-fi", "Sci-Fi"),
    ("fantasy", "Fantasy"),
    ("landscape", "Landscape"),
    ("pixel-art", "Pixel Art"),
    ("animal", "Animals"),
    ("vehicle", "Vehicles"),
    ("movies", "Movies"),
    ("lifestyle", "Lifestyle"),
    ("abstract", "Abstract"),
    ("others", "Others"),
];

pub const RESOLUTIONS: &[(&str, &str)] = &[
    ("all", "moe_res_all"),
    ("3840x2160", "moe_res_4k"),
    ("2560x1440", "moe_res_2k"),
    ("1920x1080", "moe_res_1080p"),
    ("3440x1440", "moe_res_ultrawide"),
    ("5120x1440", "moe_res_super_ultrawide"),
    ("7680x2160", "moe_res_dual_4k"),
    ("1280x720", "moe_res_720p"),
];

#[derive(Debug, Clone, Default)]
pub struct MoeDetail {
    pub preview_video_url: String,
    pub download_url: String,
    pub tags: Vec<String>,
}

static DETAIL_CACHE: OnceLock<Mutex<HashMap<String, MoeDetail>>> = OnceLock::new();

fn detail_cache() -> &'static Mutex<HashMap<String, MoeDetail>> {
    DETAIL_CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

pub fn normalize_moewalls_url(raw: &str) -> String {
    let s = raw.trim();
    if s.is_empty() {
        String::new()
    } else if s.starts_with("//") {
        format!("https:{s}")
    } else if s.starts_with('/') {
        format!("{BASE_URL}{s}")
    } else {
        s.to_string()
    }
}

#[derive(Debug, Clone)]
pub struct MoeSearchParams {
    pub query: String,
    pub category: String,
    pub resolution: String,
    pub page: usize,
}

impl Default for MoeSearchParams {
    fn default() -> Self {
        Self {
            query: String::new(),
            category: "all".to_string(),
            resolution: "all".to_string(),
            page: 1,
        }
    }
}

pub fn build_search_url(params: &MoeSearchParams) -> String {
    let mut url = if params.page > 1 {
        format!("{BASE_URL}/page/{}/", params.page)
    } else {
        format!("{BASE_URL}/")
    };

    let mut query_parts = Vec::new();
    let q = params.query.trim();
    if !q.is_empty() {
        query_parts.push(format!("s={}", urlencoding::encode(q)));
    }
    if !params.category.is_empty() && params.category != "all" {
        query_parts.push(format!("category_name={}", urlencoding::encode(&params.category)));
    }
    if !params.resolution.is_empty() && params.resolution != "all" {
        query_parts.push(format!("resolutions={}", urlencoding::encode(&params.resolution)));
    }

    if !query_parts.is_empty() {
        url.push('?');
        url.push_str(&query_parts.join("&"));
    }
    url
}

pub fn search(client: &Client, params: &MoeSearchParams) -> Result<SearchResult, String> {
    let url = build_search_url(params);
    let resp = client
        .get(&url)
        .header("Referer", BASE_URL)
        .send()
        .map_err(|e| format!("MoeWalls request failed: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("MoeWalls HTTP {}", resp.status().as_u16()));
    }

    let html = resp
        .text()
        .map_err(|e| format!("Failed to read MoeWalls HTML: {e}"))?;
    Ok(parse_search_html(&html, params.page.max(1)))
}

pub fn parse_search_html(html: &str, current_page: usize) -> SearchResult {
    static ARTICLE_RE: OnceLock<Regex> = OnceLock::new();
    static LINK_RE_1: OnceLock<Regex> = OnceLock::new();
    static LINK_RE_2: OnceLock<Regex> = OnceLock::new();
    static IMG_RE: OnceLock<Regex> = OnceLock::new();
    static IMG_DATA_SRC_RE: OnceLock<Regex> = OnceLock::new();
    static RES_RE: OnceLock<Regex> = OnceLock::new();
    static POST_ID_RE: OnceLock<Regex> = OnceLock::new();
    static CAT_RE: OnceLock<Regex> = OnceLock::new();
    static PAGE_RE: OnceLock<Regex> = OnceLock::new();

    let article_re = ARTICLE_RE
        .get_or_init(|| Regex::new(r#"(?s)<article[^>]*class=["']([^"']+)["'][^>]*>(.*?)</article>"#).unwrap());
    let link_re_1 = LINK_RE_1
        .get_or_init(|| Regex::new(r#"(?s)<a[^>]+title=["']([^"']+)["'][^>]+href=["']([^"']+)["']"#).unwrap());
    let link_re_2 = LINK_RE_2
        .get_or_init(|| Regex::new(r#"(?s)<a[^>]+href=["']([^"']+)["'][^>]+title=["']([^"']+)["']"#).unwrap());
    let img_re = IMG_RE.get_or_init(|| Regex::new(r#"<img[^>]+src=["']([^"']+)["']"#).unwrap());
    let img_data_src_re =
        IMG_DATA_SRC_RE.get_or_init(|| Regex::new(r#"<img[^>]+data-src=["']([^"']+)["']"#).unwrap());
    let res_re = RES_RE.get_or_init(|| Regex::new(r"resolutions-(\d+x\d+)").unwrap());
    let post_id_re = POST_ID_RE.get_or_init(|| Regex::new(r"post-(\d+)").unwrap());
    let cat_re = CAT_RE.get_or_init(|| Regex::new(r"category-([a-zA-Z0-9_-]+)").unwrap());
    let page_re = PAGE_RE.get_or_init(|| Regex::new(r"/page/(\d+)/").unwrap());

    let mut items = Vec::new();
    for cap in article_re.captures_iter(html) {
        let classes = cap.get(1).map(|m| m.as_str()).unwrap_or("");
        let body = cap.get(2).map(|m| m.as_str()).unwrap_or("");

        if !classes.contains("post-") && !classes.contains("type-post") {
            continue;
        }

        let (raw_title, page_url) = if let Some(c) = link_re_1.captures(body) {
            (
                c.get(1).map(|m| m.as_str()).unwrap_or(""),
                c.get(2).map(|m| m.as_str()).unwrap_or(""),
            )
        } else if let Some(c) = link_re_2.captures(body) {
            (
                c.get(2).map(|m| m.as_str()).unwrap_or(""),
                c.get(1).map(|m| m.as_str()).unwrap_or(""),
            )
        } else {
            continue;
        };

        let title = html_escape::decode_html_entities(raw_title).trim().to_string();
        let page_url = normalize_moewalls_url(page_url);
        if page_url.is_empty() {
            continue;
        }

        let thumb = img_data_src_re
            .captures(body)
            .and_then(|c| c.get(1))
            .map(|m| normalize_moewalls_url(m.as_str()))
            .or_else(|| {
                img_re
                    .captures(body)
                    .and_then(|c| c.get(1))
                    .map(|m| normalize_moewalls_url(m.as_str()))
            })
            .unwrap_or_default();

        let id = post_id_re
            .captures(classes)
            .and_then(|c| c.get(1))
            .map(|m| format!("mw_{}", m.as_str()))
            .unwrap_or_else(|| format!("mw_{}", items.len() + 1));

        let resolution = res_re
            .captures(classes)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().to_string())
            .unwrap_or_default();

        let (dimension_x, dimension_y) = if let Some((w, h)) = resolution.split_once('x') {
            (w.parse::<u32>().unwrap_or(0), h.parse::<u32>().unwrap_or(0))
        } else {
            (0, 0)
        };

        let ratio = if dimension_y > 0 {
            format!("{:.2}", dimension_x as f64 / dimension_y as f64)
        } else {
            String::new()
        };

        let category = cat_re
            .captures(classes)
            .and_then(|c| c.get(1))
            .map(|m| m.as_str().to_string())
            .unwrap_or_else(|| "live".to_string());

        items.push(WallpaperItem {
            id,
            title,
            url: page_url.to_string(),
            short_url: page_url.to_string(),
            source: "moewalls".to_string(),
            purity: "sfw".to_string(),
            category,
            dimension_x,
            dimension_y,
            resolution,
            ratio,
            file_type: "video/mp4".to_string(),
            path: String::new(),
            thumb_large: thumb.clone(),
            thumb_small: thumb.clone(),
            thumb_original: thumb,
            uploader: "MoeWalls".to_string(),
            is_animated: true,
            ..Default::default()
        });
    }

    let mut last_page = current_page;
    for cap in page_re.captures_iter(html) {
        if let Ok(p) = cap[1].parse::<usize>() {
            if p > last_page {
                last_page = p;
            }
        }
    }

    SearchResult {
        per_page: items.len().max(1),
        total: items.len() * last_page,
        items,
        current_page,
        last_page,
    }
}

pub fn get_detail(client: &Client, page_url: &str) -> Result<MoeDetail, String> {
    if let Ok(guard) = detail_cache().lock() {
        if let Some(cached) = guard.get(page_url) {
            return Ok(cached.clone());
        }
    }

    let resp = client
        .get(page_url)
        .header("Referer", BASE_URL)
        .send()
        .map_err(|e| format!("MoeWalls detail failed: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("MoeWalls detail HTTP {}", resp.status().as_u16()));
    }

    let html = resp
        .text()
        .map_err(|e| format!("Failed to read MoeWalls detail HTML: {e}"))?;
    let detail = parse_detail_html(&html);

    if let Ok(mut guard) = detail_cache().lock() {
        guard.insert(page_url.to_string(), detail.clone());
    }

    Ok(detail)
}

pub fn parse_detail_html(html: &str) -> MoeDetail {
    static SOURCE_RE: OnceLock<Regex> = OnceLock::new();
    static DL_SLUG_RE_1: OnceLock<Regex> = OnceLock::new();
    static DL_SLUG_RE_2: OnceLock<Regex> = OnceLock::new();
    static MP4_RE: OnceLock<Regex> = OnceLock::new();
    static TAG_RE: OnceLock<Regex> = OnceLock::new();

    let source_re = SOURCE_RE.get_or_init(|| Regex::new(r#"<source[^>]+src=["']([^"']+)["']"#).unwrap());
    let dl_re_1 = DL_SLUG_RE_1
        .get_or_init(|| Regex::new(r#"id=["']moe-download["'][^>]*data-url=["']([^"']+)["']"#).unwrap());
    let dl_re_2 = DL_SLUG_RE_2
        .get_or_init(|| Regex::new(r#"data-url=["']([^"']+)["'][^>]*id=["']moe-download["']"#).unwrap());
    let mp4_re = MP4_RE.get_or_init(|| Regex::new(r#"https?://[^"'\s<>]+\.mp4"#).unwrap());
    let tag_re = TAG_RE
        .get_or_init(|| Regex::new(r#"(?s)<a[^>]+href=["']https://moewalls\.com/tag/[^"']+["'][^>]*>(.*?)</a>"#).unwrap());

    let preview_video_url = source_re
        .captures(html)
        .and_then(|c| c.get(1))
        .map(|m| normalize_moewalls_url(m.as_str()))
        .unwrap_or_default();

    let slug = dl_re_1
        .captures(html)
        .and_then(|c| c.get(1))
        .or_else(|| dl_re_2.captures(html).and_then(|c| c.get(1)))
        .map(|m| m.as_str().trim().to_string())
        .unwrap_or_default();

    let download_url = if !slug.is_empty() {
        if slug.starts_with("http") {
            slug
        } else {
            format!("https://go.moewalls.com/download.php?video={slug}")
        }
    } else if let Some(m) = mp4_re.find(html) {
        m.as_str().to_string()
    } else {
        preview_video_url.clone()
    };

    let mut tags = Vec::new();
    for cap in tag_re.captures_iter(html) {
        let raw = cap.get(1).map(|m| m.as_str()).unwrap_or("");
        let decoded = html_escape::decode_html_entities(raw).trim().to_string();
        if !decoded.is_empty() && !tags.contains(&decoded) {
            tags.push(decoded);
        }
    }

    MoeDetail {
        preview_video_url,
        download_url,
        tags,
    }
}

pub fn get_download_url(client: &Client, item: &mut WallpaperItem) -> Result<String, String> {
    if !item.path.is_empty() && !item.preview_video_url.is_empty() {
        return Ok(item.path.clone());
    }
    let detail = get_detail(client, &item.url)?;
    if !detail.preview_video_url.is_empty() {
        item.preview_video_url = detail.preview_video_url;
    }
    if !detail.download_url.is_empty() {
        item.path = detail.download_url.clone();
    }
    if item.tags.is_empty() && !detail.tags.is_empty() {
        item.tags = detail.tags;
    }
    if item.path.is_empty() {
        Err("No MoeWalls download URL found".to_string())
    } else {
        Ok(item.path.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_moewalls_search_and_detail_html() {
        let search_html = r#"
        <article class="post-12345 post type-post category-anime resolutions-3840x2160">
            <a title="Sakura &amp; Rain" href="https://moewalls.com/anime/sakura-rain-live-wallpaper/">
                <img src="https://moewalls.com/thumbs/sakura.webp" />
            </a>
        </article>
        <div class="nav-links"><a href="https://moewalls.com/page/4/">4</a></div>
        "#;

        let res = parse_search_html(search_html, 1);
        assert_eq!(res.items.len(), 1);
        assert_eq!(res.last_page, 4);
        let item = &res.items[0];
        assert_eq!(item.id, "mw_12345");
        assert_eq!(item.title, "Sakura & Rain");
        assert_eq!(item.resolution, "3840x2160");
        assert_eq!(item.dimension_x, 3840);
        assert_eq!(item.dimension_y, 2160);
        assert_eq!(item.category, "anime");
        assert!(item.is_animated);

        let detail_html = r#"
        <video><source src="/wp-content/uploads/preview/2026/sakura.webm" type="video/webm"></video>
        <button id="moe-download" data-url="sakura-rain">Download</button>
        <a href="https://moewalls.com/tag/cherry-blossom/">Cherry Blossom</a>
        "#;
        let detail = parse_detail_html(detail_html);
        assert_eq!(detail.preview_video_url, "https://moewalls.com/wp-content/uploads/preview/2026/sakura.webm");
        assert_eq!(detail.download_url, "https://go.moewalls.com/download.php?video=sakura-rain");
        assert_eq!(detail.tags, vec!["Cherry Blossom".to_string()]);
    }
}
