use crate::i18n::{tr, Lang};
use egui::{Color32, CornerRadius, FontFamily, FontId, Stroke, TextStyle};
use regex::Regex;
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::time::SystemTime;

#[derive(Debug, Clone)]
pub struct ThemePalette {
    pub id: String,
    pub name: String,
    pub bg_base: Color32,
    pub bg_surface: Color32,
    pub bg_subsurface: Color32,
    pub bg_capsule: Color32,
    pub bg_input: Color32,
    pub bg_input_hover: Color32,
    pub bg_card_hover: Color32,
    pub border: Color32,
    pub border_subtle: Color32,
    pub border_hover: Color32,
    pub accent: Color32,
    pub accent_hover: Color32,
    pub accent_grad_start: Color32,
    pub accent_grad_end: Color32,
    pub accent_surface: Color32,
    pub accent_text: Color32,
    pub text_primary: Color32,
    pub text_secondary: Color32,
    pub text_muted: Color32,
    pub is_terminal: bool,
    pub is_oled: bool,
    pub is_light: bool,
}

impl ThemePalette {
    pub fn radius_card(&self) -> u8 {
        if self.is_terminal {
            3
        } else {
            10
        }
    }

    pub fn radius_btn(&self) -> u8 {
        if self.is_terminal {
            3
        } else {
            7
        }
    }

    pub fn radius_pill(&self) -> u8 {
        if self.is_terminal {
            4
        } else {
            16
        }
    }
}

pub fn parse_hex(hex: &str) -> Color32 {
    let clean = hex.trim().trim_start_matches('#');
    if clean.len() >= 6 {
        let r = u8::from_str_radix(&clean[0..2], 16).unwrap_or(20);
        let g = u8::from_str_radix(&clean[2..4], 16).unwrap_or(20);
        let b = u8::from_str_radix(&clean[4..6], 16).unwrap_or(30);
        let a = if clean.len() == 8 {
            u8::from_str_radix(&clean[6..8], 16).unwrap_or(255)
        } else {
            255
        };
        return Color32::from_rgba_unmultiplied(r, g, b, a);
    }
    Color32::from_rgb(20, 22, 32)
}

pub fn is_light_color(c: Color32) -> bool {
    let lum = (0.299 * c.r() as f32 + 0.587 * c.g() as f32 + 0.114 * c.b() as f32) / 255.0;
    lum > 0.55
}

pub fn with_alpha(c: Color32, alpha: u8) -> Color32 {
    Color32::from_rgba_unmultiplied(c.r(), c.g(), c.b(), alpha)
}

struct RawPalette<'a> {
    id: &'a str,
    name: &'a str,
    bg_base: &'a str,
    bg_surface: &'a str,
    bg_subsurface: &'a str,
    bg_capsule: &'a str,
    bg_input: &'a str,
    bg_input_hover: &'a str,
    bg_card_hover: &'a str,
    border: &'a str,
    border_subtle: &'a str,
    border_hover: &'a str,
    accent: &'a str,
    accent_hover: &'a str,
    accent_grad_start: &'a str,
    accent_grad_end: &'a str,
    accent_surface: &'a str,
    accent_text: &'a str,
    text_primary: &'a str,
    text_secondary: &'a str,
    text_muted: &'a str,
}

impl<'a> RawPalette<'a> {
    fn to_palette(&self) -> ThemePalette {
        let bg_base = parse_hex(self.bg_base);
        ThemePalette {
            id: self.id.into(),
            name: self.name.into(),
            bg_base,
            bg_surface: parse_hex(self.bg_surface),
            bg_subsurface: parse_hex(self.bg_subsurface),
            bg_capsule: parse_hex(self.bg_capsule),
            bg_input: parse_hex(self.bg_input),
            bg_input_hover: parse_hex(self.bg_input_hover),
            bg_card_hover: parse_hex(self.bg_card_hover),
            border: parse_hex(self.border),
            border_subtle: parse_hex(self.border_subtle),
            border_hover: parse_hex(self.border_hover),
            accent: parse_hex(self.accent),
            accent_hover: parse_hex(self.accent_hover),
            accent_grad_start: parse_hex(self.accent_grad_start),
            accent_grad_end: parse_hex(self.accent_grad_end),
            accent_surface: parse_hex(self.accent_surface),
            accent_text: parse_hex(self.accent_text),
            text_primary: parse_hex(self.text_primary),
            text_secondary: parse_hex(self.text_secondary),
            text_muted: parse_hex(self.text_muted),
            is_terminal: self.id.starts_with("terminal"),
            is_oled: self.id == "oled",
            is_light: is_light_color(bg_base),
        }
    }
}

const CURATED: &[RawPalette<'static>] = &[
    RawPalette {
        id: "terminal",
        name: "Terminal Phosphor",
        bg_base: "#070b08",
        bg_surface: "#0b120d",
        bg_subsurface: "#090f0b",
        bg_capsule: "#060a07",
        bg_input: "#0d1610",
        bg_input_hover: "#14221a",
        bg_card_hover: "#0f1a13",
        border: "#1d3a28",
        border_subtle: "#142a1d",
        border_hover: "#2f7a4b",
        accent: "#33ff77",
        accent_hover: "#7dffa8",
        accent_grad_start: "#1fcf5a",
        accent_grad_end: "#33ff77",
        accent_surface: "#0f3a20",
        accent_text: "#04120a",
        text_primary: "#c9f7d8",
        text_secondary: "#7fb893",
        text_muted: "#4a7a5c",
    },
    RawPalette {
        id: "terminal_amber",
        name: "Terminal Amber",
        bg_base: "#0b0904",
        bg_surface: "#120e06",
        bg_subsurface: "#0f0b05",
        bg_capsule: "#090703",
        bg_input: "#16110a",
        bg_input_hover: "#241b0d",
        bg_card_hover: "#1a1408",
        border: "#4a3510",
        border_subtle: "#33250c",
        border_hover: "#8a6218",
        accent: "#ffb000",
        accent_hover: "#ffcc4d",
        accent_grad_start: "#e69a00",
        accent_grad_end: "#ffb000",
        accent_surface: "#3d2a05",
        accent_text: "#140d00",
        text_primary: "#ffe3a8",
        text_secondary: "#c9a25a",
        text_muted: "#7d6532",
    },
    RawPalette {
        id: "terminal_ice",
        name: "Terminal Ice",
        bg_base: "#050a0d",
        bg_surface: "#091217",
        bg_subsurface: "#070e12",
        bg_capsule: "#04080a",
        bg_input: "#0b161c",
        bg_input_hover: "#12232c",
        bg_card_hover: "#0d1b22",
        border: "#173a47",
        border_subtle: "#10293a",
        border_hover: "#2a7a94",
        accent: "#3ee6ff",
        accent_hover: "#8af0ff",
        accent_grad_start: "#1bc4e0",
        accent_grad_end: "#3ee6ff",
        accent_surface: "#0a3340",
        accent_text: "#02121a",
        text_primary: "#cdf6ff",
        text_secondary: "#7fb4c4",
        text_muted: "#4a7a8a",
    },
    RawPalette {
        id: "dark",
        name: "Wallhaven Dark",
        bg_base: "#0d1017",
        bg_surface: "#12151f",
        bg_subsurface: "#0f121a",
        bg_capsule: "#0b0d14",
        bg_input: "#151824",
        bg_input_hover: "#1e2434",
        bg_card_hover: "#161a27",
        border: "#232838",
        border_subtle: "#1c2230",
        border_hover: "#3b4461",
        accent: "#6366f1",
        accent_hover: "#818cf8",
        accent_grad_start: "#4f46e5",
        accent_grad_end: "#6366f1",
        accent_surface: "#262463",
        accent_text: "#ffffff",
        text_primary: "#f8fafc",
        text_secondary: "#94a3b8",
        text_muted: "#64748b",
    },
    RawPalette {
        id: "catppuccin",
        name: "Catppuccin Mocha",
        bg_base: "#1e1e2e",
        bg_surface: "#181825",
        bg_subsurface: "#11111b",
        bg_capsule: "#11111b",
        bg_input: "#313244",
        bg_input_hover: "#45475a",
        bg_card_hover: "#252739",
        border: "#45475a",
        border_subtle: "#313244",
        border_hover: "#585b70",
        accent: "#cba6f7",
        accent_hover: "#b4befe",
        accent_grad_start: "#995bf5",
        accent_grad_end: "#cba6f7",
        accent_surface: "#3f3657",
        accent_text: "#ffffff",
        text_primary: "#cdd6f4",
        text_secondary: "#a6adc8",
        text_muted: "#6c7086",
    },
    RawPalette {
        id: "tokyo_night",
        name: "Tokyo Night",
        bg_base: "#1a1b26",
        bg_surface: "#16161e",
        bg_subsurface: "#13141c",
        bg_capsule: "#101016",
        bg_input: "#24283b",
        bg_input_hover: "#2f354f",
        bg_card_hover: "#1f2335",
        border: "#292e42",
        border_subtle: "#1f2335",
        border_hover: "#414868",
        accent: "#7aa2f7",
        accent_hover: "#89b4fa",
        accent_grad_start: "#5981f4",
        accent_grad_end: "#7aa2f7",
        accent_surface: "#233154",
        accent_text: "#ffffff",
        text_primary: "#c0caf5",
        text_secondary: "#9aa5ce",
        text_muted: "#565f89",
    },
    RawPalette {
        id: "nord",
        name: "Nord Frost",
        bg_base: "#242933",
        bg_surface: "#2e3440",
        bg_subsurface: "#272c36",
        bg_capsule: "#1e222a",
        bg_input: "#3b4252",
        bg_input_hover: "#434c5e",
        bg_card_hover: "#353c4a",
        border: "#434c5e",
        border_subtle: "#2e3440",
        border_hover: "#4c566a",
        accent: "#88c0d0",
        accent_hover: "#8fbcbb",
        accent_grad_start: "#5e81ac",
        accent_grad_end: "#88c0d0",
        accent_surface: "#2d4350",
        accent_text: "#eceff4",
        text_primary: "#eceff4",
        text_secondary: "#d8dee9",
        text_muted: "#7b88a1",
    },
    RawPalette {
        id: "dracula",
        name: "Dracula",
        bg_base: "#21222c",
        bg_surface: "#282a36",
        bg_subsurface: "#1e1f29",
        bg_capsule: "#181920",
        bg_input: "#343746",
        bg_input_hover: "#44475a",
        bg_card_hover: "#2d303e",
        border: "#44475a",
        border_subtle: "#2e303e",
        border_hover: "#6272a4",
        accent: "#bd93f9",
        accent_hover: "#ff79c6",
        accent_grad_start: "#9a6df7",
        accent_grad_end: "#bd93f9",
        accent_surface: "#422e5a",
        accent_text: "#ffffff",
        text_primary: "#f8f8f2",
        text_secondary: "#bfbfbf",
        text_muted: "#6272a4",
    },
    RawPalette {
        id: "gruvbox",
        name: "Gruvbox Dark",
        bg_base: "#1d2021",
        bg_surface: "#282828",
        bg_subsurface: "#242424",
        bg_capsule: "#191b1c",
        bg_input: "#3c3836",
        bg_input_hover: "#504945",
        bg_card_hover: "#32302f",
        border: "#504945",
        border_subtle: "#32302f",
        border_hover: "#665c54",
        accent: "#fabd2f",
        accent_hover: "#fe8019",
        accent_grad_start: "#d65d0e",
        accent_grad_end: "#fabd2f",
        accent_surface: "#4e3d1f",
        accent_text: "#1d2021",
        text_primary: "#ebdbb2",
        text_secondary: "#d5c4a1",
        text_muted: "#928374",
    },
    RawPalette {
        id: "cyberpunk",
        name: "Cyberpunk Neon",
        bg_base: "#0a0b12",
        bg_surface: "#111320",
        bg_subsurface: "#0d0f19",
        bg_capsule: "#07080d",
        bg_input: "#181b2e",
        bg_input_hover: "#222640",
        bg_card_hover: "#171a2b",
        border: "#272c4a",
        border_subtle: "#1a1d30",
        border_hover: "#3e4775",
        accent: "#00f0ff",
        accent_hover: "#f72585",
        accent_grad_start: "#f72585",
        accent_grad_end: "#00f0ff",
        accent_surface: "#1a3547",
        accent_text: "#ffffff",
        text_primary: "#e0fbfc",
        text_secondary: "#90e0ef",
        text_muted: "#52796f",
    },
    RawPalette {
        id: "oled",
        name: "OLED Pure Black",
        bg_base: "#000000",
        bg_surface: "#0a0a0a",
        bg_subsurface: "#050505",
        bg_capsule: "#000000",
        bg_input: "#141414",
        bg_input_hover: "#222222",
        bg_card_hover: "#111111",
        border: "#282828",
        border_subtle: "#161616",
        border_hover: "#444444",
        accent: "#3b82f6",
        accent_hover: "#60a5fa",
        accent_grad_start: "#1d4ed8",
        accent_grad_end: "#3b82f6",
        accent_surface: "#13274f",
        accent_text: "#ffffff",
        text_primary: "#ffffff",
        text_secondary: "#a1a1aa",
        text_muted: "#71717a",
    },
    RawPalette {
        id: "rose_pine",
        name: "Rosé Pine",
        bg_base: "#191724",
        bg_surface: "#1f1d2e",
        bg_subsurface: "#14121f",
        bg_capsule: "#12101b",
        bg_input: "#26233a",
        bg_input_hover: "#312d47",
        bg_card_hover: "#211f33",
        border: "#393552",
        border_subtle: "#232136",
        border_hover: "#524f67",
        accent: "#eb6f92",
        accent_hover: "#f6c177",
        accent_grad_start: "#eb6f92",
        accent_grad_end: "#c4a7e7",
        accent_surface: "#392338",
        accent_text: "#ffffff",
        text_primary: "#e0def4",
        text_secondary: "#908caa",
        text_muted: "#6e6a86",
    },
    RawPalette {
        id: "everforest",
        name: "Everforest Dark",
        bg_base: "#2b3339",
        bg_surface: "#323c41",
        bg_subsurface: "#272e33",
        bg_capsule: "#1e2326",
        bg_input: "#3a454a",
        bg_input_hover: "#445055",
        bg_card_hover: "#343f44",
        border: "#4a555b",
        border_subtle: "#374145",
        border_hover: "#7a8478",
        accent: "#a7c080",
        accent_hover: "#dbbc7f",
        accent_grad_start: "#83c092",
        accent_grad_end: "#a7c080",
        accent_surface: "#344237",
        accent_text: "#2b3339",
        text_primary: "#d3c6aa",
        text_secondary: "#9da9a0",
        text_muted: "#7a8478",
    },
    RawPalette {
        id: "kanagawa",
        name: "Kanagawa Wave",
        bg_base: "#1f1f28",
        bg_surface: "#2a2a37",
        bg_subsurface: "#181820",
        bg_capsule: "#16161d",
        bg_input: "#363646",
        bg_input_hover: "#434356",
        bg_card_hover: "#252535",
        border: "#454559",
        border_subtle: "#2d2d3a",
        border_hover: "#5a5a73",
        accent: "#7e9cd8",
        accent_hover: "#957fb8",
        accent_grad_start: "#7e9cd8",
        accent_grad_end: "#7aa89f",
        accent_surface: "#223249",
        accent_text: "#ffffff",
        text_primary: "#dcd7ba",
        text_secondary: "#c8c093",
        text_muted: "#727169",
    },
    RawPalette {
        id: "synthwave",
        name: "Synthwave '84",
        bg_base: "#1a1528",
        bg_surface: "#241b35",
        bg_subsurface: "#140f20",
        bg_capsule: "#110c1c",
        bg_input: "#2e2144",
        bg_input_hover: "#3c2a59",
        bg_card_hover: "#291e3d",
        border: "#49326d",
        border_subtle: "#2f1f47",
        border_hover: "#7247ac",
        accent: "#ff7edb",
        accent_hover: "#36f9f6",
        accent_grad_start: "#ff7edb",
        accent_grad_end: "#36f9f6",
        accent_surface: "#451e52",
        accent_text: "#ffffff",
        text_primary: "#fbf5fc",
        text_secondary: "#b49cdb",
        text_muted: "#79669e",
    },
];

pub fn matugen_watch_paths() -> Vec<PathBuf> {
    let Some(home) = dirs::home_dir() else {
        return Vec::new();
    };
    vec![
        home.join(".cache/quickshell/matugen.json"),
        home.join(".local/state/serpantinum/qs_matugen_colors.json"),
        home.join(".local/state/serpantinum/qs_colors.json"),
        home.join(".config/matugen/colors.json"),
        home.join(".cache/matugen/colors.json"),
        home.join(".local/state/matugen/colors.json"),
        home.join(".cache/wal/colors.json"),
        home.join(".config/gtk-3.0/colors.css"),
        home.join(".config/gtk-4.0/colors.css"),
        home.join(".config/kdeglobals"),
    ]
}

pub fn matugen_mtime() -> Option<SystemTime> {
    let mut latest: Option<SystemTime> = None;
    for p in matugen_watch_paths() {
        if let Ok(meta) = fs::metadata(p) {
            if let Ok(m) = meta.modified() {
                latest = Some(match latest {
                    Some(prev) if prev > m => prev,
                    _ => m,
                });
            }
        }
    }
    latest
}

pub fn is_matugen_available() -> bool {
    if let Some(home) = dirs::home_dir() {
        let paths = [
            home.join(".cache/quickshell/matugen.json"),
            home.join(".cache/sedly-rice/current_wallpaper"),
            home.join(".config/gtk-3.0/colors.css"),
            home.join(".config/gtk-4.0/colors.css"),
            home.join(".config/kdeglobals"),
            home.join(".local/state/serpantinum/qs_colors.json"),
            home.join(".local/state/serpantinum/qs_matugen_colors.json"),
            home.join(".config/matugen/colors.json"),
            home.join(".cache/matugen/colors.json"),
        ];
        if paths.iter().any(|p| p.exists()) {
            return true;
        }
    }
    std::path::Path::new("/usr/bin/matugen").exists()
}

pub fn get_available_themes(lang: Lang) -> Vec<(String, String)> {
    let mut out = Vec::new();
    if is_matugen_available() {
        out.push(("matugen".into(), tr(lang, "theme_matugen").into()));
    }
    for p in CURATED {
        out.push((p.id.into(), p.name.into()));
    }
    if let Some(home) = dirs::home_dir() {
        if home.join(".cache/wal/colors.json").exists() {
            out.push(("pywal".into(), tr(lang, "theme_pywal").into()));
        }
    }
    out
}

pub fn parse_flat_matugen_json(text: &str, label: &str) -> Option<ThemePalette> {
    let v: Value = serde_json::from_str(text).ok()?;
    let obj = v.as_object()?;
    let get_s = |k: &str| obj.get(k).and_then(|x| x.as_str());
    let primary = get_s("primary").filter(|s| s.starts_with('#'))?;

    let bg_base_s = get_s("surface_container_lowest")
        .or_else(|| get_s("surface"))
        .or_else(|| get_s("background"))
        .unwrap_or("#140c0c");
    let bg_surface_s = get_s("surface_container_low")
        .or_else(|| get_s("surface"))
        .or_else(|| get_s("background"))
        .unwrap_or("#1f1818");
    let bg_sub_s = get_s("surface").unwrap_or(bg_base_s);
    let bg_cap_s = get_s("surface_container_lowest").unwrap_or(bg_base_s);
    let bg_in_s = get_s("surface_container")
        .or_else(|| get_s("surface_variant"))
        .unwrap_or("#271d1d");
    let bg_in_hov_s = get_s("surface_container_high")
        .or_else(|| get_s("surface_bright"))
        .unwrap_or("#322827");
    let bg_card_hov_s = get_s("surface_container_high").unwrap_or(bg_in_hov_s);
    let border_s = get_s("outline_variant")
        .or_else(|| get_s("surface_variant"))
        .unwrap_or("#534342");
    let border_sub_s = get_s("surface_container_highest")
        .or_else(|| get_s("outline_variant"))
        .unwrap_or("#3d3231");
    let accent = parse_hex(primary);
    let accent_hover_s = get_s("surface_tint").or_else(|| get_s("secondary")).unwrap_or(primary);
    let accent_surface_s = get_s("primary_container").unwrap_or("#733332");
    let bg_base = parse_hex(bg_base_s);
    let accent_text = get_s("on_primary")
        .map(parse_hex)
        .unwrap_or_else(|| if is_light_color(accent) { bg_base } else { Color32::WHITE });
    let grad_end = get_s("secondary").unwrap_or(accent_hover_s);

    Some(ThemePalette {
        id: "matugen".into(),
        name: label.into(),
        bg_base,
        bg_surface: parse_hex(bg_surface_s),
        bg_subsurface: parse_hex(bg_sub_s),
        bg_capsule: parse_hex(bg_cap_s),
        bg_input: parse_hex(bg_in_s),
        bg_input_hover: parse_hex(bg_in_hov_s),
        bg_card_hover: parse_hex(bg_card_hov_s),
        border: parse_hex(border_s),
        border_subtle: parse_hex(border_sub_s),
        border_hover: accent,
        accent,
        accent_hover: parse_hex(accent_hover_s),
        accent_grad_start: accent,
        accent_grad_end: parse_hex(grad_end),
        accent_surface: parse_hex(accent_surface_s),
        accent_text,
        text_primary: parse_hex(get_s("on_surface").unwrap_or("#f0dedd")),
        text_secondary: parse_hex(get_s("on_surface_variant").unwrap_or("#d8c1c0")),
        text_muted: parse_hex(get_s("outline").unwrap_or("#a08c8b")),
        is_terminal: false,
        is_oled: false,
        is_light: is_light_color(bg_base),
    })
}

pub fn parse_standard_matugen_json(text: &str, label: &str) -> Option<ThemePalette> {
    let v: Value = serde_json::from_str(text).ok()?;
    let colors = v.get("colors")?.as_object()?;
    let get_c = |key: &str, fallback: &str| -> String {
        if let Some(item) = colors.get(key).and_then(|x| x.as_object()) {
            if let Some(c) = item
                .get("dark")
                .and_then(|d| d.get("color"))
                .and_then(|s| s.as_str())
            {
                return c.to_string();
            }
            if let Some(c) = item
                .get("default")
                .and_then(|d| d.get("color"))
                .and_then(|s| s.as_str())
            {
                return c.to_string();
            }
        }
        fallback.to_string()
    };

    let bg_base_s = get_c("surface_container_lowest", &get_c("background", "#0c0e13"));
    let bg_base = parse_hex(&bg_base_s);
    let accent_s = get_c("primary", "#a5c8fe");
    let accent = parse_hex(&accent_s);
    let accent_hover_s = get_c("surface_tint", "#c1c1ff");
    let accent_text_s = get_c("on_primary", "");
    let accent_text = if accent_text_s.is_empty() {
        if is_light_color(accent) { bg_base } else { Color32::WHITE }
    } else {
        parse_hex(&accent_text_s)
    };

    Some(ThemePalette {
        id: "matugen".into(),
        name: label.into(),
        bg_base,
        bg_surface: parse_hex(&get_c("surface_container_low", &get_c("surface", "#111318"))),
        bg_subsurface: parse_hex(&get_c("surface", "#0c0e13")),
        bg_capsule: bg_base,
        bg_input: parse_hex(&get_c("surface_container", "#1d2024")),
        bg_input_hover: parse_hex(&get_c("surface_container_high", "#282a2f")),
        bg_card_hover: parse_hex(&get_c("surface_container_high", "#191c20")),
        border: parse_hex(&get_c("outline_variant", "#32353a")),
        border_subtle: parse_hex(&get_c("surface_container_highest", "#282a2f")),
        border_hover: accent,
        accent,
        accent_hover: parse_hex(&accent_hover_s),
        accent_grad_start: accent,
        accent_grad_end: parse_hex(&accent_hover_s),
        accent_surface: parse_hex(&get_c("primary_container", "#214876")),
        accent_text,
        text_primary: parse_hex(&get_c("on_surface", "#e1e2e9")),
        text_secondary: parse_hex(&get_c("on_surface_variant", "#c3c6cf")),
        text_muted: parse_hex(&get_c("outline", "#8d9199")),
        is_terminal: false,
        is_oled: false,
        is_light: is_light_color(bg_base),
    })
}

fn load_matugen_palette(lang: Lang) -> Option<ThemePalette> {
    let home = dirs::home_dir()?;
    let label = tr(lang, "theme_matugen");

    for fp in [
        home.join(".cache/quickshell/matugen.json"),
        home.join(".local/state/serpantinum/qs_matugen_colors.json"),
    ] {
        if let Ok(txt) = fs::read_to_string(fp) {
            if let Some(p) = parse_flat_matugen_json(&txt, label) {
                return Some(p);
            }
        }
    }

    if let Ok(txt) = fs::read_to_string(home.join(".local/state/serpantinum/qs_colors.json")) {
        if let Ok(v) = serde_json::from_str::<Value>(&txt) {
            if let (Some(base), Some(text)) = (v.get("base").and_then(|x| x.as_str()), v.get("text").and_then(|x| x.as_str())) {
                let get_s = |k: &str, fb: &str| -> String {
                    v.get(k)
                        .and_then(|x| x.as_str())
                        .unwrap_or(fb)
                        .to_string()
                };
                let bg_base = parse_hex(base);
                let accent_s = v.get("blue").or_else(|| v.get("mauve")).and_then(|x| x.as_str()).unwrap_or("#a5c8fe");
                let accent = parse_hex(accent_s);
                let accent_hover_s = v.get("mauve").or_else(|| v.get("blue")).and_then(|x| x.as_str()).unwrap_or("#c1c1ff");
                return Some(ThemePalette {
                    id: "matugen".into(),
                    name: label.into(),
                    bg_base,
                    bg_surface: parse_hex(&get_s("crust", "#111318")),
                    bg_subsurface: parse_hex(&get_s("crust", "#111318")),
                    bg_capsule: bg_base,
                    bg_input: parse_hex(&get_s("surface0", "#1d2024")),
                    bg_input_hover: parse_hex(&get_s("surface1", "#282a2f")),
                    bg_card_hover: parse_hex(&get_s("mantle", "#191c20")),
                    border: parse_hex(&get_s("surface2", "#32353a")),
                    border_subtle: parse_hex(&get_s("surface1", "#282a2f")),
                    border_hover: accent,
                    accent,
                    accent_hover: parse_hex(accent_hover_s),
                    accent_grad_start: accent,
                    accent_grad_end: parse_hex(accent_hover_s),
                    accent_surface: parse_hex(&get_s("sapphire", "#214876")),
                    accent_text: if is_light_color(accent) { bg_base } else { Color32::WHITE },
                    text_primary: parse_hex(text),
                    text_secondary: parse_hex(&get_s("subtext0", "#c3c6cf")),
                    text_muted: parse_hex(&get_s("subtext1", "#8d9199")),
                    is_terminal: false,
                    is_oled: false,
                    is_light: is_light_color(bg_base),
                });
            }
        }
    }

    for mp in [
        home.join(".config/matugen/colors.json"),
        home.join(".cache/matugen/colors.json"),
        home.join(".local/state/matugen/colors.json"),
    ] {
        if let Ok(txt) = fs::read_to_string(mp) {
            if let Some(p) = parse_standard_matugen_json(&txt, label) {
                return Some(p);
            }
        }
    }

    None
}

fn load_gtk_palette(lang: Lang) -> Option<ThemePalette> {
    let home = dirs::home_dir()?;
    let re = Regex::new(r"@define-color\s+([\w-]+)\s+(#[0-9a-fA-F]{6});").ok()?;
    for gp in [
        home.join(".config/gtk-3.0/colors.css"),
        home.join(".config/gtk-4.0/colors.css"),
    ] {
        if let Ok(content) = fs::read_to_string(gp) {
            let mut map = HashMap::new();
            for cap in re.captures_iter(&content) {
                map.insert(cap[1].to_string(), cap[2].to_string());
            }
            if let (Some(acc_s), Some(bg_s)) = (map.get("accent_color"), map.get("window_bg_color")) {
                let bg = parse_hex(bg_s);
                let accent = parse_hex(acc_s);
                let fg = parse_hex(map.get("window_fg_color").map(|s| s.as_str()).unwrap_or("#f0dedd"));
                let header = parse_hex(map.get("headerbar_bg_color").map(|s| s.as_str()).unwrap_or(bg_s));
                let card = parse_hex(map.get("card_bg_color").map(|s| s.as_str()).unwrap_or(bg_s));
                let accent_fg = map
                    .get("accent_fg_color")
                    .map(|s| parse_hex(s))
                    .unwrap_or_else(|| if is_light_color(accent) { bg } else { Color32::WHITE });
                return Some(ThemePalette {
                    id: "matugen".into(),
                    name: tr(lang, "theme_gtk").into(),
                    bg_base: bg,
                    bg_surface: header,
                    bg_subsurface: bg,
                    bg_capsule: bg,
                    bg_input: card,
                    bg_input_hover: card,
                    bg_card_hover: card,
                    border: parse_hex(map.get("sidebar_border_color").map(|s| s.as_str()).unwrap_or("#333333")),
                    border_subtle: parse_hex("#282828"),
                    border_hover: accent,
                    accent,
                    accent_hover: accent,
                    accent_grad_start: accent,
                    accent_grad_end: accent,
                    accent_surface: parse_hex(map.get("accent_bg_color").map(|s| s.as_str()).unwrap_or(acc_s)),
                    accent_text: accent_fg,
                    text_primary: fg,
                    text_secondary: fg,
                    text_muted: parse_hex("#888888"),
                    is_terminal: false,
                    is_oled: false,
                    is_light: is_light_color(bg),
                });
            }
        }
    }
    None
}

fn load_pywal_palette(lang: Lang) -> Option<ThemePalette> {
    let home = dirs::home_dir()?;
    let txt = fs::read_to_string(home.join(".cache/wal/colors.json")).ok()?;
    let v: Value = serde_json::from_str(&txt).ok()?;
    let c = v.get("colors")?.as_object()?;
    let sp = v.get("special")?.as_object()?;
    let bg_s = sp.get("background").and_then(|x| x.as_str()).unwrap_or("#121212");
    let fg_s = sp.get("foreground").and_then(|x| x.as_str()).unwrap_or("#f0f0f0");
    let accent_s = c.get("color4").and_then(|x| x.as_str()).unwrap_or("#6366f1");
    let alt_s = c.get("color5").and_then(|x| x.as_str()).unwrap_or("#818cf8");
    let bg = parse_hex(bg_s);
    Some(ThemePalette {
        id: "pywal".into(),
        name: tr(lang, "theme_pywal").into(),
        bg_base: bg,
        bg_surface: parse_hex(c.get("color0").and_then(|x| x.as_str()).unwrap_or("#181818")),
        bg_subsurface: bg,
        bg_capsule: bg,
        bg_input: parse_hex(c.get("color8").and_then(|x| x.as_str()).unwrap_or("#282828")),
        bg_input_hover: parse_hex(c.get("color7").and_then(|x| x.as_str()).unwrap_or("#383838")),
        bg_card_hover: parse_hex(c.get("color0").and_then(|x| x.as_str()).unwrap_or("#202020")),
        border: parse_hex(c.get("color8").and_then(|x| x.as_str()).unwrap_or("#333333")),
        border_subtle: parse_hex(c.get("color0").and_then(|x| x.as_str()).unwrap_or("#222222")),
        border_hover: parse_hex(accent_s),
        accent: parse_hex(accent_s),
        accent_hover: parse_hex(alt_s),
        accent_grad_start: parse_hex(accent_s),
        accent_grad_end: parse_hex(alt_s),
        accent_surface: parse_hex(c.get("color1").and_then(|x| x.as_str()).unwrap_or("#2b2244")),
        accent_text: Color32::WHITE,
        text_primary: parse_hex(fg_s),
        text_secondary: parse_hex(c.get("color7").and_then(|x| x.as_str()).unwrap_or("#b0b0b0")),
        text_muted: parse_hex(c.get("color8").and_then(|x| x.as_str()).unwrap_or("#777777")),
        is_terminal: false,
        is_oled: false,
        is_light: is_light_color(bg),
    })
}

fn parse_kde_rgb(raw: &str) -> Option<Color32> {
    let mut parts = raw.trim().split(',').filter_map(|p| p.trim().parse::<u8>().ok());
    let r = parts.next()?;
    let g = parts.next()?;
    let b = parts.next()?;
    Some(Color32::from_rgb(r, g, b))
}

fn load_kde_palette(lang: Lang) -> Option<ThemePalette> {
    let home = dirs::home_dir()?;
    let content = fs::read_to_string(home.join(".config/kdeglobals")).ok()?;
    let mut section = String::new();
    let mut win_bg = None;
    let mut view_bg = None;
    let mut fg = None;
    let mut sel_bg = None;
    let mut sel_fg = None;

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            section = trimmed[1..trimmed.len() - 1].to_string();
            continue;
        }
        let Some((k, v)) = trimmed.split_once('=') else {
            continue;
        };
        let key = k.trim();
        let val = v.trim();
        match (section.as_str(), key) {
            ("Colors:Window", "BackgroundNormal") => win_bg = parse_kde_rgb(val),
            ("Colors:Window", "ForegroundNormal") => fg = parse_kde_rgb(val),
            ("Colors:View", "BackgroundNormal") => view_bg = parse_kde_rgb(val),
            ("Colors:Selection", "BackgroundNormal") => sel_bg = parse_kde_rgb(val),
            ("Colors:Selection", "ForegroundNormal") => sel_fg = parse_kde_rgb(val),
            _ => {}
        }
    }

    let bg_base = win_bg?;
    let accent = sel_bg?;
    let bg_surface = view_bg.unwrap_or(bg_base);
    let text_primary = fg.unwrap_or(Color32::WHITE);
    let accent_text = sel_fg.unwrap_or_else(|| {
        if is_light_color(accent) {
            bg_base
        } else {
            Color32::WHITE
        }
    });

    Some(ThemePalette {
        id: "matugen".into(),
        name: tr(lang, "theme_kde").into(),
        bg_base,
        bg_surface,
        bg_subsurface: bg_base,
        bg_capsule: bg_base,
        bg_input: bg_surface,
        bg_input_hover: bg_surface,
        bg_card_hover: bg_surface,
        border: with_alpha(text_primary, 40),
        border_subtle: with_alpha(text_primary, 24),
        border_hover: accent,
        accent,
        accent_hover: accent,
        accent_grad_start: accent,
        accent_grad_end: accent,
        accent_surface: with_alpha(accent, 64),
        accent_text,
        text_primary,
        text_secondary: with_alpha(text_primary, 200),
        text_muted: with_alpha(text_primary, 130),
        is_terminal: false,
        is_oled: false,
        is_light: is_light_color(bg_base),
    })
}

pub fn get_palette(theme_id: &str, lang: Lang) -> ThemePalette {
    let tid = theme_id.trim();
    if matches!(tid, "matugen" | "auto" | "system") {
        if let Some(p) = load_matugen_palette(lang) {
            return p;
        }
        if let Some(p) = load_gtk_palette(lang) {
            return p;
        }
        if let Some(p) = load_kde_palette(lang) {
            return p;
        }
        if let Some(p) = load_pywal_palette(lang) {
            return p;
        }
        return CURATED.iter().find(|p| p.id == "dark").unwrap().to_palette();
    }
    if tid == "kde" {
        if let Some(p) = load_kde_palette(lang) {
            return p;
        }
    }
    if tid == "pywal" {
        if let Some(p) = load_pywal_palette(lang) {
            return p;
        }
        return CURATED.iter().find(|p| p.id == "dark").unwrap().to_palette();
    }
    CURATED
        .iter()
        .find(|p| p.id == tid)
        .unwrap_or_else(|| CURATED.iter().find(|p| p.id == "dark").unwrap())
        .to_palette()
}

pub fn apply_to_ctx(ctx: &egui::Context, pal: &ThemePalette) {
    let mut visuals = if pal.is_light {
        egui::Visuals::light()
    } else {
        egui::Visuals::dark()
    };

    let r = CornerRadius::same(pal.radius_btn());
    visuals.window_fill = pal.bg_surface;
    visuals.panel_fill = pal.bg_base;
    visuals.faint_bg_color = pal.bg_subsurface;
    visuals.extreme_bg_color = pal.bg_capsule;
    visuals.code_bg_color = pal.bg_input;
    visuals.window_stroke = Stroke::new(1.0_f32, pal.border);
    visuals.window_corner_radius = CornerRadius::same(pal.radius_card());

    visuals.selection.bg_fill = pal.accent_surface;
    visuals.selection.stroke = Stroke::new(1.0_f32, pal.accent);
    visuals.hyperlink_color = pal.accent;

    visuals.widgets.noninteractive.bg_fill = pal.bg_surface;
    visuals.widgets.noninteractive.weak_bg_fill = pal.bg_subsurface;
    visuals.widgets.noninteractive.bg_stroke = Stroke::new(1.0_f32, pal.border_subtle);
    visuals.widgets.noninteractive.fg_stroke = Stroke::new(1.0_f32, pal.text_primary);
    visuals.widgets.noninteractive.corner_radius = r;

    visuals.widgets.inactive.bg_fill = pal.bg_input;
    visuals.widgets.inactive.weak_bg_fill = pal.bg_input;
    visuals.widgets.inactive.bg_stroke = Stroke::new(1.0_f32, pal.border);
    visuals.widgets.inactive.fg_stroke = Stroke::new(1.0_f32, pal.text_primary);
    visuals.widgets.inactive.corner_radius = r;

    visuals.widgets.hovered.bg_fill = pal.bg_input_hover;
    visuals.widgets.hovered.weak_bg_fill = pal.bg_input_hover;
    visuals.widgets.hovered.bg_stroke = Stroke::new(1.5_f32, pal.accent);
    visuals.widgets.hovered.fg_stroke = Stroke::new(1.5_f32, pal.text_primary);
    visuals.widgets.hovered.corner_radius = r;

    visuals.widgets.active.bg_fill = pal.accent_surface;
    visuals.widgets.active.weak_bg_fill = pal.accent_surface;
    visuals.widgets.active.bg_stroke = Stroke::new(1.5_f32, pal.accent_hover);
    visuals.widgets.active.fg_stroke = Stroke::new(1.5_f32, pal.text_primary);
    visuals.widgets.active.corner_radius = r;

    ctx.set_visuals(visuals);

    let ui_family = if pal.is_terminal {
        FontFamily::Monospace
    } else {
        FontFamily::Proportional
    };

    ctx.style_mut(|style| {
        style.text_styles.insert(TextStyle::Small, FontId::new(10.5, ui_family.clone()));
        style.text_styles.insert(TextStyle::Body, FontId::new(12.5, ui_family.clone()));
        style.text_styles.insert(TextStyle::Button, FontId::new(12.0, ui_family.clone()));
        style.text_styles.insert(TextStyle::Heading, FontId::new(17.0, ui_family));
        style
            .text_styles
            .insert(TextStyle::Monospace, FontId::new(12.0, FontFamily::Monospace));

        style.spacing.scroll = egui::style::ScrollStyle {
            floating: false,
            bar_width: 5.0,
            handle_min_length: 28.0,
            bar_inner_margin: 3.0,
            bar_outer_margin: 2.0,
            ..egui::style::ScrollStyle::solid()
        };
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn curated_terminal_ice_exists() {
        let p = get_palette("terminal_ice", Lang::En);
        assert_eq!(p.id, "terminal_ice");
        assert!(p.is_terminal);
        assert_eq!(p.accent, parse_hex("#3ee6ff"));
    }

    #[test]
    fn parses_flat_and_standard_matugen() {
        let flat = r##"{"primary":"#a6c8ff","on_primary":"#003062","surface":"#111318","on_surface":"#e1e2e9"}"##;
        let p = parse_flat_matugen_json(flat, "Matugen").unwrap();
        assert_eq!(p.accent, parse_hex("#a6c8ff"));
        assert_eq!(p.bg_base, parse_hex("#111318"));

        let std_json = r##"{"colors":{"primary":{"dark":{"color":"#ffb4ab"}},"surface":{"dark":{"color":"#141218"}},"on_surface":{"dark":{"color":"#e6e0e9"}}}}"##;
        let p2 = parse_standard_matugen_json(std_json, "Matugen").unwrap();
        assert_eq!(p2.accent, parse_hex("#ffb4ab"));
    }
}
