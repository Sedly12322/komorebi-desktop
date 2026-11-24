mod app;
mod cache;
mod config;
mod i18n;
mod installed;
mod models;
mod providers;
mod theme;
mod ui;
mod updater;
mod video_preview;
mod wallpaper;

use std::fs;
use std::path::Path;

use app::KomorebiApp;
use egui::{FontData, FontDefinitions, FontFamily, IconData};

fn load_app_icon() -> Option<IconData> {
    let bytes = include_bytes!("../assets/icon.png");
    let img = image::load_from_memory(bytes).ok()?.to_rgba8();
    let (width, height) = img.dimensions();
    Some(IconData {
        rgba: img.into_raw(),
        width,
        height,
    })
}

fn configure_fonts(ctx: &egui::Context) {
    let mut fonts = FontDefinitions::default();

    let proportional_order = [
        ("noto_sans", "/usr/share/fonts/noto/NotoSans-Regular.ttf"),
        ("nerd_mono", "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf"),
        ("dejavu_sans", "/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ];

    for (name, path) in proportional_order {
        if Path::new(path).exists() {
            if let Ok(bytes) = fs::read(path) {
                fonts
                    .font_data
                    .insert(name.to_owned(), FontData::from_owned(bytes).into());
            }
        }
    }

    let prop_list = fonts
        .families
        .entry(FontFamily::Proportional)
        .or_default();
    let mut idx = 0;
    for (name, _) in proportional_order {
        if fonts.font_data.contains_key(name) {
            prop_list.insert(idx, name.to_owned());
            idx += 1;
        }
    }

    if fonts.font_data.contains_key("nerd_mono") {
        let mono_list = fonts
            .families
            .entry(FontFamily::Monospace)
            .or_default();
        mono_list.insert(0, "nerd_mono".to_owned());
    }

    ctx.set_fonts(fonts);
}

fn main() -> eframe::Result<()> {
    let mut viewport = egui::ViewportBuilder::default()
        .with_title("Komorebi Desktop")
        .with_inner_size([1280.0, 820.0])
        .with_min_inner_size([920.0, 620.0])
        .with_app_id("komorebi-desktop");

    if let Some(icon) = load_app_icon() {
        viewport = viewport.with_icon(std::sync::Arc::new(icon));
    }

    let options = eframe::NativeOptions {
        viewport,
        vsync: cfg!(not(target_os = "linux")),
        ..Default::default()
    };

    eframe::run_native(
        "Komorebi Desktop",
        options,
        Box::new(|cc| {
            configure_fonts(&cc.egui_ctx);
            Ok(Box::new(KomorebiApp::new(cc)))
        }),
    )
}
