use egui::{
    Align2, Color32, CornerRadius, FontId, Pos2, Rect, RichText, Sense, Stroke, StrokeKind, Ui,
    Vec2,
};
use std::collections::HashSet;

use crate::cache::ImageLoader;
use crate::i18n::{tr, Lang};
use crate::models::{CardSize, NavMode, PfpItem, WallpaperItem};
use crate::theme::{parse_hex, ThemePalette};
use crate::ui::{compute_cover_uv, draw_badge, select_gif_frame};

pub enum GridAction {
    None,
    OpenWallpaper(usize),
    QuickDownload(usize),
    QuickSetWallpaper(usize),
    QuickUninstallWallpaper(usize),
    OpenPfp(usize),
}

#[allow(clippy::too_many_arguments)]
pub fn render_wallpaper_grid(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    mode: NavMode,
    card_size: CardSize,
    grid_w: f32,
    items: &[WallpaperItem],
    installed_ids: &HashSet<String>,
    loading: bool,
    loader: &mut ImageLoader,
    hover_video: Option<(&str, &egui::TextureHandle)>,
    hovered_animated_out: &mut Option<usize>,
) -> GridAction {
    let mut action = GridAction::None;
    let (target_w, _, img_w, img_h) = card_size.dimensions();
    let spacing = 12.0_f32;
    let safe_w = grid_w.max(220.0);
    let cols = ((safe_w + spacing) / (target_w + spacing)).floor().max(1.0) as usize;
    let card_w = ((safe_w - spacing * (cols as f32 - 1.0)) / cols as f32)
        .floor()
        .max(160.0);
    let pad = 6.0_f32;
    let thumb_w = (card_w - pad * 2.0).max(80.0);
    let thumb_h = (thumb_w * (img_h / img_w).clamp(0.52, 0.66)).floor();
    let footer_h = 28.0_f32;
    let card_h = pad + thumb_h + footer_h + pad;

    if loading && items.is_empty() {
        let count = cols * 3;
        render_skeleton_grid(ui, pal, cols, card_w, card_h, spacing, count);
        return GridAction::None;
    }

    if !loading && items.is_empty() {
        render_empty_state(
            ui,
            pal,
            if mode == NavMode::Installed {
                tr(lang, "installed_empty_title")
            } else {
                tr(lang, "grid_empty_title")
            },
            if mode == NavMode::Installed {
                tr(lang, "installed_empty_msg")
            } else {
                tr(lang, "grid_empty_sub")
            },
        );
        return GridAction::None;
    }

    let r = CornerRadius::same(pal.radius_card());
    let inner_r = CornerRadius::same(pal.radius_btn().min(6));
    let now = ui.ctx().input(|i| i.time);

    let mut idx = 0;
    while idx < items.len() {
        ui.horizontal(|ui| {
            ui.spacing_mut().item_spacing.x = spacing;
            for _ in 0..cols {
                if idx >= items.len() {
                    break;
                }
                let item = &items[idx];
                let item_idx = idx;
                idx += 1;

                let (card_rect, resp) =
                    ui.allocate_exact_size(Vec2::new(card_w, card_h), Sense::click());
                let hovered = resp.hovered() || ui.rect_contains_pointer(card_rect);
                if hovered && item.is_animated {
                    *hovered_animated_out = Some(item_idx);
                }

                let card_bg = if hovered {
                    pal.bg_card_hover
                } else {
                    pal.bg_surface
                };
                let stroke = if hovered {
                    Stroke::new(1.5_f32, pal.accent)
                } else {
                    Stroke::new(1.0_f32, pal.border_subtle)
                };
                ui.painter().rect_filled(card_rect, r, card_bg);

                let thumb_rect =
                    Rect::from_min_size(card_rect.min + Vec2::splat(pad), Vec2::new(thumb_w, thumb_h));

                let thumb_src = if !item.thumb_url().is_empty() {
                    item.thumb_url()
                } else {
                    &item.local_path
                };
                let key = format!("thumb:{}:{}", item.id, thumb_src);

                if let Some((hv_id, vtex)) = hover_video.filter(|(id, _)| *id == item.id) {
                    let _ = hv_id;
                    let uv = compute_cover_uv(vtex.size_vec2(), thumb_rect.size());
                    egui::Image::new(vtex)
                        .uv(uv)
                        .corner_radius(inner_r)
                        .paint_at(ui, thumb_rect);
                } else if loader.is_failed(&key) {
                    ui.painter().rect_filled(thumb_rect, inner_r, pal.bg_input);
                    ui.painter().text(
                        thumb_rect.center(),
                        Align2::CENTER_CENTER,
                        "No Preview",
                        FontId::proportional(11.0),
                        pal.text_muted,
                    );
                } else if let Some(tex) = loader.get_texture(&key) {
                    let uv = compute_cover_uv(tex.size_vec2(), thumb_rect.size());
                    egui::Image::new(tex)
                        .uv(uv)
                        .corner_radius(inner_r)
                        .paint_at(ui, thumb_rect);
                } else {
                    if !thumb_src.is_empty() {
                        loader.request_image(&key, thumb_src, true, false, 520, ui.ctx());
                    }
                    let pulse = 0.5 + 0.5 * ((now * 2.5 + item_idx as f64 * 0.25) as f32).sin();
                    let skel_col = pal.bg_input.lerp_to_gamma(pal.bg_input_hover, pulse);
                    ui.painter().rect_filled(thumb_rect, inner_r, skel_col);
                    if ui.ctx().input(|i| i.focused) {
                        ui.ctx()
                            .request_repaint_after(std::time::Duration::from_millis(50));
                    }
                }

                // Top-left badges inside thumbnail
                let mut badge_x = thumb_rect.left() + 7.0;
                let badge_y = thumb_rect.top() + 7.0;
                if item.is_animated {
                    let b = draw_badge(
                        ui.painter(),
                        Pos2::new(badge_x, badge_y),
                        "[ ▶ LIVE ]",
                        Color32::from_rgba_unmultiplied(4, 12, 8, 225),
                        Color32::from_rgb(51, 255, 119),
                        Some(Color32::from_rgb(51, 255, 119)),
                        3,
                    );
                    badge_x = b.right() + 5.0;
                }
                if mode != NavMode::Installed
                    && (item.is_installed || installed_ids.contains(&item.id))
                {
                    draw_badge(
                        ui.painter(),
                        Pos2::new(badge_x, badge_y),
                        tr(lang, "card_installed_badge"),
                        Color32::from_rgba_unmultiplied(4, 18, 12, 225),
                        Color32::from_rgb(125, 255, 168),
                        Some(Color32::from_rgb(47, 122, 75)),
                        3,
                    );
                }

                // Top-right v2.0.6 resolution badge ([4K] gold, [2K] cyan, [WxH] glass)
                if item.dimension_x > 0 || !item.resolution.is_empty() {
                    let (res_text, res_fg, res_border) = if item.dimension_x >= 3840 {
                        (
                            "[4K]".to_string(),
                            Color32::from_rgb(251, 191, 36),
                            Color32::from_rgba_unmultiplied(251, 191, 36, 175),
                        )
                    } else if item.dimension_x >= 2560 {
                        (
                            "[2K]".to_string(),
                            Color32::from_rgb(56, 189, 248),
                            Color32::from_rgba_unmultiplied(56, 189, 248, 175),
                        )
                    } else {
                        (
                            format!("[{}]", item.resolution),
                            Color32::WHITE,
                            Color32::from_white_alpha(55),
                        )
                    };
                    let font = FontId::monospace(10.0);
                    let galley = ui.painter().layout_no_wrap(res_text, font, res_fg);
                    let size = galley.size() + Vec2::new(10.0, 4.0);
                    let pill = Rect::from_min_size(
                        Pos2::new(thumb_rect.right() - size.x - 7.0, badge_y),
                        size,
                    );
                    ui.painter().rect_filled(
                        pill,
                        CornerRadius::same(3),
                        Color32::from_rgba_unmultiplied(12, 15, 22, 225),
                    );
                    ui.painter().rect_stroke(
                        pill,
                        CornerRadius::same(3),
                        Stroke::new(1.0_f32, res_border),
                        StrokeKind::Inside,
                    );
                    ui.painter().galley(
                        Pos2::new(pill.left() + 5.0, pill.top() + 2.0),
                        galley,
                        res_fg,
                    );
                }

                // Floating center-bottom hover action dock
                let mut child_clicked = false;
                if hovered {
                    let is_inst_card = mode == NavMode::Installed
                        || (item.is_installed && !item.local_path.is_empty());
                    let dock_w = 104.0;
                    let dock_h = 30.0;
                    let dock_rect = Rect::from_center_size(
                        Pos2::new(thumb_rect.center().x, thumb_rect.bottom() - 20.0),
                        Vec2::new(dock_w, dock_h),
                    );
                    ui.painter().rect_filled(
                        dock_rect,
                        CornerRadius::same(4),
                        Color32::from_rgba_unmultiplied(10, 12, 20, 220),
                    );
                    ui.painter().rect_stroke(
                        dock_rect,
                        CornerRadius::same(4),
                        Stroke::new(1.0_f32, pal.accent),
                        StrokeKind::Inside,
                    );

                    if is_inst_card {
                        if dock_btn(
                            ui,
                            Pos2::new(dock_rect.left() + 20.0, dock_rect.center().y),
                            "▣",
                            Color32::from_rgb(16, 185, 129),
                            ui.id().with(("dock_set", item_idx)),
                            tr(lang, "set_wall_now_button"),
                        ) {
                            action = GridAction::QuickSetWallpaper(item_idx);
                            child_clicked = true;
                        }
                        if dock_btn(
                            ui,
                            Pos2::new(dock_rect.center().x, dock_rect.center().y),
                            "✕",
                            Color32::from_rgb(239, 68, 68),
                            ui.id().with(("dock_del", item_idx)),
                            tr(lang, "uninstall_button_full"),
                        ) {
                            action = GridAction::QuickUninstallWallpaper(item_idx);
                            child_clicked = true;
                        }
                        if dock_btn(
                            ui,
                            Pos2::new(dock_rect.right() - 20.0, dock_rect.center().y),
                            "◎",
                            pal.accent,
                            ui.id().with(("dock_view", item_idx)),
                            "Preview",
                        ) {
                            action = GridAction::OpenWallpaper(item_idx);
                            child_clicked = true;
                        }
                    } else {
                        if dock_btn(
                            ui,
                            Pos2::new(dock_rect.left() + 20.0, dock_rect.center().y),
                            "↓",
                            pal.accent,
                            ui.id().with(("dock_dl", item_idx)),
                            tr(lang, "download_button"),
                        ) {
                            action = GridAction::QuickDownload(item_idx);
                            child_clicked = true;
                        }
                        if dock_btn(
                            ui,
                            Pos2::new(dock_rect.center().x, dock_rect.center().y),
                            "▣",
                            Color32::from_rgb(14, 165, 233),
                            ui.id().with(("dock_set", item_idx)),
                            tr(lang, "set_wall_now_button"),
                        ) {
                            action = GridAction::QuickSetWallpaper(item_idx);
                            child_clicked = true;
                        }
                        if dock_btn(
                            ui,
                            Pos2::new(dock_rect.right() - 20.0, dock_rect.center().y),
                            "◎",
                            pal.accent_hover,
                            ui.id().with(("dock_view", item_idx)),
                            "Preview",
                        ) {
                            action = GridAction::OpenWallpaper(item_idx);
                            child_clicked = true;
                        }
                    }
                }

                // Compact v2.0.6 Footer Row (category/clean-title on left; swatches + favorites on right)
                let footer_y = thumb_rect.bottom() + footer_h * 0.5;
                let left_start_x = thumb_rect.left() + 2.0;

                if mode == NavMode::Wallhaven {
                    let cat_label = capitalize_first(&item.category);
                    let cat_g = ui.painter().layout_no_wrap(
                        cat_label,
                        FontId::proportional(11.0),
                        pal.accent,
                    );
                    let cat_end_x = left_start_x + cat_g.size().x;
                    ui.painter().galley(
                        Pos2::new(left_start_x, footer_y - cat_g.size().y * 0.5),
                        cat_g,
                        pal.accent,
                    );

                    if item.purity == "sketchy" || item.purity == "nsfw" {
                        let (ptxt, pcol) = if item.purity == "nsfw" {
                            ("NSFW", Color32::from_rgb(225, 29, 72))
                        } else {
                            ("S", Color32::from_rgb(217, 119, 6))
                        };
                        let pg = ui
                            .painter()
                            .layout_no_wrap(ptxt.to_string(), FontId::monospace(9.5), Color32::WHITE);
                        let pr = Rect::from_min_size(
                            Pos2::new(cat_end_x + 6.0, footer_y - 8.0),
                            pg.size() + Vec2::new(8.0, 2.0),
                        );
                        ui.painter().rect_filled(pr, CornerRadius::same(3), pcol);
                        ui.painter().galley(
                            Pos2::new(pr.left() + 4.0, pr.top() + 1.0),
                            pg,
                            Color32::WHITE,
                        );
                    }
                } else {
                    let max_chars = ((thumb_w - 86.0) / 7.2).max(10.0) as usize;
                    let title_str = truncate_chars(&item.display_title(), max_chars);
                    ui.painter().text(
                        Pos2::new(left_start_x, footer_y),
                        Align2::LEFT_CENTER,
                        title_str,
                        FontId::proportional(11.0),
                        pal.text_primary,
                    );
                }

                // Right metadata: stat + up to 3 color dots
                let mut right_cursor = thumb_rect.right() - 2.0;
                if item.favorites > 0 {
                    let stat = format!("★ {}", format_thousands(item.favorites));
                    let fg = Color32::from_rgb(251, 191, 36);
                    let g = ui
                        .painter()
                        .layout_no_wrap(stat, FontId::proportional(10.5), fg);
                    right_cursor -= g.size().x;
                    ui.painter()
                        .galley(Pos2::new(right_cursor, footer_y - g.size().y * 0.5), g, fg);
                    right_cursor -= 7.0;
                } else if item.views > 0 {
                    let stat = format!("◉ {}", format_thousands(item.views));
                    let fg = Color32::from_rgb(56, 189, 248);
                    let g = ui
                        .painter()
                        .layout_no_wrap(stat, FontId::proportional(10.5), fg);
                    right_cursor -= g.size().x;
                    ui.painter()
                        .galley(Pos2::new(right_cursor, footer_y - g.size().y * 0.5), g, fg);
                    right_cursor -= 7.0;
                } else if item.file_size > 0 {
                    let stat = item.human_file_size();
                    let fg = pal.text_muted;
                    let g = ui
                        .painter()
                        .layout_no_wrap(stat, FontId::proportional(10.0), fg);
                    right_cursor -= g.size().x;
                    ui.painter()
                        .galley(Pos2::new(right_cursor, footer_y - g.size().y * 0.5), g, fg);
                    right_cursor -= 7.0;
                }

                for hex in item.colors.iter().take(3).rev() {
                    let dot_r = Rect::from_center_size(
                        Pos2::new(right_cursor - 4.0, footer_y),
                        Vec2::splat(8.0),
                    );
                    ui.painter()
                        .rect_filled(dot_r, CornerRadius::same(2), parse_hex(hex));
                    ui.painter().rect_stroke(
                        dot_r,
                        CornerRadius::same(2),
                        Stroke::new(0.8_f32, Color32::from_white_alpha(80)),
                        StrokeKind::Inside,
                    );
                    right_cursor -= 11.0;
                }

                // Crisp card border drawn last so corners stay sharp
                ui.painter()
                    .rect_stroke(card_rect, r, stroke, StrokeKind::Inside);

                if resp.clicked() && !child_clicked {
                    action = GridAction::OpenWallpaper(item_idx);
                }
            }
        });
        ui.add_space(spacing);
    }

    action
}

pub fn render_pfp_grid(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    card_size: CardSize,
    grid_w: f32,
    items: &[PfpItem],
    loading: bool,
    loader: &mut ImageLoader,
) -> GridAction {
    let mut action = GridAction::None;
    let spacing = 12.0_f32;
    let target = match card_size {
        CardSize::Compact => 165.0,
        CardSize::Normal => 195.0,
        CardSize::Large => 235.0,
    };
    let safe_w = grid_w.max(220.0);
    let cols = ((safe_w + spacing) / (target + spacing)).floor().max(2.0) as usize;
    let card_w = ((safe_w - spacing * (cols as f32 - 1.0)) / cols as f32).floor();
    let pad = 6.0_f32;
    let img_side = (card_w - pad * 2.0).max(80.0);
    let card_h = pad + img_side + 36.0 + pad;

    if loading && items.is_empty() {
        render_skeleton_grid(ui, pal, cols, card_w, card_h, spacing, cols * 3);
        return GridAction::None;
    }

    if !loading && items.is_empty() {
        render_empty_state(
            ui,
            pal,
            tr(lang, "grid_empty_title"),
            tr(lang, "grid_empty_sub"),
        );
        return GridAction::None;
    }

    let r = CornerRadius::same(pal.radius_card());
    let inner_r = CornerRadius::same(pal.radius_btn().min(6));
    let now = ui.ctx().input(|i| i.time);

    let mut idx = 0;
    while idx < items.len() {
        ui.horizontal(|ui| {
            ui.spacing_mut().item_spacing.x = spacing;
            for _ in 0..cols {
                if idx >= items.len() {
                    break;
                }
                let item = &items[idx];
                let item_idx = idx;
                idx += 1;

                let (card_rect, resp) =
                    ui.allocate_exact_size(Vec2::new(card_w, card_h), Sense::click());
                let hovered = resp.hovered();
                let bg = if hovered {
                    pal.bg_card_hover
                } else {
                    pal.bg_surface
                };
                let stroke = if hovered {
                    Stroke::new(1.5_f32, pal.accent)
                } else {
                    Stroke::new(1.0_f32, pal.border_subtle)
                };

                ui.painter().rect_filled(card_rect, r, bg);
                let img_rect =
                    Rect::from_min_size(card_rect.min + Vec2::splat(pad), Vec2::splat(img_side));
                let key = format!("pfp:{}", item.id);

                if item.is_animated() {
                    if let Some(frames) = loader.get_gif(&key) {
                        if let Some(tex) = select_gif_frame(ui.ctx(), frames) {
                            let uv = compute_cover_uv(tex.size_vec2(), img_rect.size());
                            egui::Image::new(tex)
                                .uv(uv)
                                .corner_radius(inner_r)
                                .paint_at(ui, img_rect);
                        }
                    } else if loader.is_failed(&key) {
                        ui.painter().rect_filled(img_rect, inner_r, pal.bg_input);
                    } else {
                        loader.request_image(&key, &item.image_url, true, true, 320, ui.ctx());
                        let pulse =
                            0.5 + 0.5 * ((now * 2.5 + item_idx as f64 * 0.2) as f32).sin();
                        ui.painter().rect_filled(
                            img_rect,
                            inner_r,
                            pal.bg_input.lerp_to_gamma(pal.bg_input_hover, pulse),
                        );
                    }
                } else if let Some(tex) = loader.get_texture(&key) {
                    let uv = compute_cover_uv(tex.size_vec2(), img_rect.size());
                    egui::Image::new(tex)
                        .uv(uv)
                        .corner_radius(inner_r)
                        .paint_at(ui, img_rect);
                } else if loader.is_failed(&key) {
                    ui.painter().rect_filled(img_rect, inner_r, pal.bg_input);
                } else {
                    loader.request_image(&key, &item.image_url, true, false, 320, ui.ctx());
                    let pulse = 0.5 + 0.5 * ((now * 2.5 + item_idx as f64 * 0.2) as f32).sin();
                    ui.painter().rect_filled(
                        img_rect,
                        inner_r,
                        pal.bg_input.lerp_to_gamma(pal.bg_input_hover, pulse),
                    );
                }

                draw_badge(
                    ui.painter(),
                    Pos2::new(img_rect.left() + 7.0, img_rect.top() + 7.0),
                    &item.format.to_uppercase(),
                    if item.is_animated() {
                        pal.accent
                    } else {
                        Color32::from_black_alpha(190)
                    },
                    if item.is_animated() {
                        pal.accent_text
                    } else {
                        Color32::WHITE
                    },
                    None,
                    3,
                );

                ui.painter()
                    .rect_stroke(card_rect, r, stroke, StrokeKind::Inside);

                ui.painter().text(
                    Pos2::new(img_rect.left() + 2.0, img_rect.bottom() + 6.0),
                    Align2::LEFT_TOP,
                    truncate_chars(&item.title, 20),
                    FontId::proportional(11.5),
                    pal.text_primary,
                );
                ui.painter().text(
                    Pos2::new(img_rect.left() + 2.0, img_rect.bottom() + 22.0),
                    Align2::LEFT_TOP,
                    format!(
                        "{} {}",
                        PfpItem::format_download_count(&item.downloads),
                        tr(lang, "pfp_downloads_suffix")
                    ),
                    FontId::proportional(10.0),
                    pal.text_muted,
                );

                if resp.clicked() {
                    action = GridAction::OpenPfp(item_idx);
                }
            }
        });
        ui.add_space(spacing);
    }

    action
}

fn dock_btn(
    ui: &mut Ui,
    center: Pos2,
    glyph: &str,
    hover_accent: Color32,
    id: egui::Id,
    tip: &str,
) -> bool {
    let rect = Rect::from_center_size(center, Vec2::splat(24.0));
    let resp = ui.interact(rect, id, Sense::click());
    let hovered = resp.hovered();
    let fill = if hovered {
        hover_accent
    } else {
        Color32::from_rgba_unmultiplied(20, 27, 45, 225)
    };
    let cr = CornerRadius::same(3);
    ui.painter().rect_filled(rect, cr, fill);
    ui.painter().rect_stroke(
        rect,
        cr,
        Stroke::new(
            1.0_f32,
            if hovered {
                Color32::WHITE
            } else {
                Color32::from_white_alpha(65)
            },
        ),
        StrokeKind::Inside,
    );
    ui.painter().text(
        rect.center(),
        Align2::CENTER_CENTER,
        glyph,
        FontId::proportional(12.5),
        Color32::WHITE,
    );
    resp.on_hover_text(tip).clicked()
}

fn render_skeleton_grid(
    ui: &mut Ui,
    pal: &ThemePalette,
    cols: usize,
    card_w: f32,
    card_h: f32,
    spacing: f32,
    count: usize,
) {
    let now = ui.ctx().input(|i| i.time);
    let r = CornerRadius::same(pal.radius_card());
    let mut i = 0;
    while i < count {
        ui.horizontal(|ui| {
            ui.spacing_mut().item_spacing.x = spacing;
            for _ in 0..cols {
                if i >= count {
                    break;
                }
                let (rect, _) = ui.allocate_exact_size(Vec2::new(card_w, card_h), Sense::hover());
                let pulse = 0.5 + 0.5 * ((now * 3.0 + i as f64 * 0.25) as f32).sin();
                let skel = pal.bg_surface.lerp_to_gamma(pal.bg_input_hover, pulse);
                ui.painter().rect_filled(rect, r, skel);
                ui.painter().rect_stroke(
                    rect,
                    r,
                    Stroke::new(1.0_f32, pal.border_subtle),
                    StrokeKind::Inside,
                );
                i += 1;
            }
        });
        ui.add_space(spacing);
    }
    if ui.ctx().input(|i| i.focused) {
        ui.ctx()
            .request_repaint_after(std::time::Duration::from_millis(33));
    }
}

fn render_empty_state(ui: &mut Ui, pal: &ThemePalette, title: &str, subtitle: &str) {
    ui.add_space(64.0);
    ui.vertical_centered(|ui| {
        ui.label(RichText::new("◈").color(pal.accent).size(38.0));
        ui.add_space(8.0);
        ui.label(
            RichText::new(title)
                .color(pal.text_primary)
                .strong()
                .size(16.0),
        );
        ui.add_space(4.0);
        ui.label(RichText::new(subtitle).color(pal.text_muted).size(12.5));
    });
}

fn capitalize_first(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        None => String::new(),
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
    }
}

fn format_thousands(n: u64) -> String {
    let s = n.to_string();
    let mut out = String::with_capacity(s.len() + s.len() / 3);
    for (idx, ch) in s.chars().rev().enumerate() {
        if idx > 0 && idx % 3 == 0 {
            out.push(',');
        }
        out.push(ch);
    }
    out.chars().rev().collect()
}

fn truncate_chars(s: &str, max: usize) -> String {
    let mut chars = s.chars();
    let collected: String = chars.by_ref().take(max).collect();
    if chars.next().is_some() {
        format!("{collected}...")
    } else {
        collected
    }
}
