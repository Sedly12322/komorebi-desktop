use reqwest::blocking::Client;
use serde::Deserialize;

pub const APP_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const REPO_SLUG: &str = "Sedly12322/komorebi-desktop";
pub const RELEASES_URL: &str = "https://github.com/Sedly12322/komorebi-desktop/releases/latest";

#[derive(Debug, Clone)]
pub struct UpdateInfo {
    pub current: String,
    pub latest: String,
    pub has_update: bool,
    pub url: String,
    pub notes: String,
}

#[derive(Deserialize)]
struct GithubRelease {
    #[serde(default)]
    tag_name: String,
    #[serde(default)]
    html_url: String,
    #[serde(default)]
    body: String,
}

pub fn parse_semver(raw: &str) -> (u32, u32, u32) {
    let cleaned = raw.trim().trim_start_matches('v').trim_start_matches('V');
    let base = cleaned.split('-').next().unwrap_or(cleaned);
    let mut parts = base.split('.').map(|p| p.parse::<u32>().unwrap_or(0));
    (
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
    )
}

pub fn is_newer_version(latest: &str, current: &str) -> bool {
    parse_semver(latest) > parse_semver(current)
}

pub fn check_github_release(client: &Client) -> Result<UpdateInfo, String> {
    let url = format!("https://api.github.com/repos/{REPO_SLUG}/releases/latest");
    let resp = client
        .get(&url)
        .header("Accept", "application/vnd.github+json")
        .send()
        .map_err(|e| format!("Update check failed: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("GitHub API HTTP {}", resp.status().as_u16()));
    }

    let rel: GithubRelease = resp
        .json()
        .map_err(|e| format!("Invalid GitHub release JSON: {e}"))?;
    let latest = rel.tag_name.trim().trim_start_matches('v').to_string();
    let has_update = !latest.is_empty() && is_newer_version(&latest, APP_VERSION);
    let release_url = if rel.html_url.is_empty() {
        RELEASES_URL.to_string()
    } else {
        rel.html_url
    };

    Ok(UpdateInfo {
        current: APP_VERSION.to_string(),
        latest,
        has_update,
        url: release_url,
        notes: rel.body,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn semver_comparison_works() {
        assert_eq!(parse_semver("v3.1.2-beta"), (3, 1, 2));
        assert!(is_newer_version("v3.0.1", "3.0.0"));
        assert!(!is_newer_version("3.0.0", "3.0.0"));
        assert!(!is_newer_version("v2.0.6", "3.0.0"));
    }
}
