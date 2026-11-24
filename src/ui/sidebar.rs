use egui::{
    Align2, Color32, CornerRadius, FontId, Pos2, Rect, RichText, Sense, Stroke, StrokeKind,
    TextureHandle, Ui, Vec2,
};

use crate::i18n::{tr, Lang};
use crate::models::NavMode;
use crate::theme::{get_available_themes, with_alpha, ThemePalette};
use crate::updater::{UpdateInfo, APP_VERSION};

pub enum SidebarAction {
    None,
    SelectMode(NavMode),
    ChangeTheme(String),
    ToggleAutoWallpaper(bool),
    OpenSettings,
    OpenUpdateUrl(String),
}

struct NavEntry {
    mode: NavMode,
    glyph: &'static str,
    title_key: &'static str,
    sub_key: &'static str,
    static_badge: Option<&'static str>,
}

const EXPLORE_ITEMS: &[NavEntry] = &[
    NavEntry {
        mode: NavMode::Wallhaven,
        glyph: "◈",
        title_key: "tab_wallhaven",
        sub_key: "sidebar_wallhaven_sub",
        static_badge: None,
    },
    NavEntry {
        mode: NavMode::MoeWalls,
        glyph: "▶",
        title_key: "tab_moewalls",
        sub_key: "sidebar_moewalls_sub",
        static_badge: Some("LIVE"),
    },
    NavEntry {
        mode: NavMode::Osu,
        glyph: "★",
        title_key: "tab_osu",
        sub_key: "sidebar_osu_sub",
        static_badge: None,
    },
    NavEntry {
        mode: NavMode::Pfps,
        glyph: "◉",
        title_key: "tab_pfps",
        sub_key: "sidebar_pfps_sub",
        static_badge: Some("NEW"),
    },
];

const LIBRARY_ITEMS: &[NavEntry] = &[NavEntry {
    mode: NavMode::Installed,
    glyph: "▣",
    title_key: "tab_installed",
    sub_key: "sidebar_installed_sub",
    static_badge: None,
}];

#[allow(clippy::too_many_arguments)]
pub fn render_sidebar(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    active_mode: NavMode,
    current_theme: &str,
    auto_set_wallpaper: bool,
    installed_count: usize,
    emblem_tex: Option<&TextureHandle>,
    update_info: Option<&UpdateInfo>,
) -> SidebarAction {
    let mut action = SidebarAction::None;

    ui.set_width(252.0);
    let panel_rect = ui.available_rect_before_wrap();

    // Subtle vertical gradient matching v2.0.6 command-center sidebar
    {
        let p = ui.painter();
        let top_col = pal.bg_surface.lerp_to_gamma(pal.accent, 0.04);
        let mut mesh = egui::Mesh::default();
        mesh.colored_vertex(panel_rect.left_top(), top_col);
        mesh.colored_vertex(panel_rect.right_top(), top_col);
        mesh.colored_vertex(panel_rect.right_bottom(), pal.bg_capsule);
        mesh.colored_vertex(panel_rect.left_bottom(), pal.bg_capsule);
        mesh.add_triangle(0, 1, 2);
        mesh.add_triangle(0, 2, 3);
        p.add(mesh);

        // Glowing right border line
        p.line_segment(
            [panel_rect.right_top(), panel_rect.right_bottom()],
            Stroke::new(1.5_f32, with_alpha(pal.accent, 145)),
        );
    }

    ui.add_space(12.0);
    egui::Frame::new()
        .inner_margin(egui::Margin::symmetric(12, 0))
        .show(ui, |ui| {
            // 1. Hero Brand Card
            egui::Frame::new()
                .fill(pal.bg_capsule)
                .stroke(Stroke::new(1.0_f32, with_alpha(pal.accent, 180)))
                .corner_radius(CornerRadius::same(pal.radius_card()))
                .inner_margin(egui::Margin::same(10))
                .show(ui, |ui| {
                    ui.set_width(206.0);
                    ui.horizontal(|ui| {
                        let (emblem_rect, _) =
                            ui.allocate_exact_size(Vec2::splat(38.0), Sense::hover());
                        let r = CornerRadius::same(pal.radius_btn());
                        ui.painter().rect_filled(emblem_rect, r, pal.bg_base);
                        if let Some(tex) = emblem_tex {
                            egui::Image::new(tex)
                                .corner_radius(r)
                                .paint_at(ui, emblem_rect.shrink(2.0));
                        } else {
                            ui.painter()
                                .circle_filled(emblem_rect.center(), 8.0, pal.accent);
                        }
                        ui.painter().rect_stroke(
                            emblem_rect,
                            r,
                            Stroke::new(1.0_f32, pal.accent),
                            StrokeKind::Inside,
                        );

                        ui.add_space(4.0);
                        ui.vertical(|ui| {
                            ui.spacing_mut().item_spacing.y = 3.0;
                            let title = if pal.is_terminal {
                                "> komorebi"
                            } else {
                                "Komorebi"
                            };
                            ui.label(
                                RichText::new(title)
                                    .color(pal.text_primary)
                                    .strong()
                                    .size(15.0),
                            );
                            ui.horizontal(|ui| {
                                let sub = if pal.is_terminal {
                                    "~/wallpapers $"
                                } else {
                                    "Wallpaper Studio"
                                };
                                ui.label(RichText::new(sub).color(pal.text_muted).size(10.0));

                                let has_update =
                                    update_info.map(|u| u.has_update).unwrap_or(false);
                                if has_update {
                                    if let Some(upd) = update_info {
                                        let badge = egui::Button::new(
                                            RichText::new(format!("v{}!", upd.latest))
                                                .color(pal.accent_text)
                                                .strong()
                                                .size(9.5),
                                        )
                                        .fill(pal.accent)
                                        .corner_radius(CornerRadius::same(4))
                                        .min_size(Vec2::new(32.0, 16.0));
                                        if ui.add(badge).clicked() {
                                            action = SidebarAction::OpenUpdateUrl(upd.url.clone());
                                        }
                                    }
                                } else {
                                    let (ver_rect, _) = ui.allocate_exact_size(
                                        Vec2::new(46.0, 16.0),
                                        Sense::hover(),
                                    );
                                    let cr = CornerRadius::same(3);
                                    ui.painter().rect_filled(ver_rect, cr, pal.bg_input);
                                    ui.painter().rect_stroke(
                                        ver_rect,
                                        cr,
                                        Stroke::new(1.0_f32, pal.border),
                                        StrokeKind::Inside,
                                    );
                                    ui.painter().text(
                                        ver_rect.center(),
                                        Align2::CENTER_CENTER,
                                        format!("v{APP_VERSION}"),
                                        FontId::monospace(9.5),
                                        pal.text_secondary,
                                    );
                                }
                            });
                        });
                    });
                });

            ui.add_space(14.0);
            section_heading(ui, pal, tr(lang, "nav_explore"));
            ui.add_space(4.0);

            let mut active_tile_rect: Option<Rect> = None;
            for entry in EXPLORE_ITEMS {
                let (clicked, rect) = nav_tile(
                    ui,
                    pal,
                    entry.glyph,
                    tr(lang, entry.title_key),
                    tr(lang, entry.sub_key),
                    entry.mode == active_mode,
                    entry.static_badge.map(str::to_string),
                );
                if entry.mode == active_mode {
                    active_tile_rect = Some(rect);
                }
                if clicked {
                    action = SidebarAction::SelectMode(entry.mode);
                }
                ui.add_space(4.0);
            }

            ui.add_space(10.0);
            section_heading(ui, pal, tr(lang, "nav_library"));
            ui.add_space(4.0);

            for entry in LIBRARY_ITEMS {
                let (clicked, rect) = nav_tile(
                    ui,
                    pal,
                    entry.glyph,
                    tr(lang, entry.title_key),
                    tr(lang, entry.sub_key),
                    entry.mode == active_mode,
                    Some(installed_count.to_string()),
                );
                if entry.mode == active_mode {
                    active_tile_rect = Some(rect);
                }
                if clicked {
                    action = SidebarAction::SelectMode(entry.mode);
                }
            }

            // Flush animated cursor bar aligned directly to the active tile's left edge
            if let Some(tr_rect) = active_tile_rect {
                let anim_y = ui.ctx().animate_value_with_time(
                    egui::Id::new("komorebi_nav_indicator_y"),
                    tr_rect.center().y,
                    0.18,
                );
                let bar_rect = Rect::from_center_size(
                    Pos2::new(tr_rect.left() + 2.0, anim_y),
                    Vec2::new(4.0, tr_rect.height() - 6.0),
                );
                ui.painter().rect_filled(
                    bar_rect,
                    CornerRadius::same(2),
                    pal.accent,
                );
            }

            // Anchor bottom utility card cleanly at the bottom
            let remaining = (ui.available_height() - 134.0).max(12.0);
            ui.add_space(remaining);

            egui::Frame::new()
                .fill(pal.bg_capsule)
                .stroke(Stroke::new(1.0_f32, pal.border))
                .corner_radius(CornerRadius::same(pal.radius_card()))
                .inner_margin(egui::Margin::same(10))
                .show(ui, |ui| {
                    ui.set_width(206.0);

                    // Quick Theme switcher
                    let themes = get_available_themes(lang);
                    let current_label = themes
                        .iter()
                        .find(|(id, _)| id == current_theme)
                        .map(|(_, name)| name.as_str())
                        .unwrap_or(current_theme)
                        .to_string();

                    egui::ComboBox::from_id_salt("sidebar_theme_combo")
                        .width(206.0)
                        .selected_text(
                            RichText::new(format!("{}: {}", tr(lang, "sidebar_theme"), current_label))
                                .size(11.5)
                                .color(pal.text_primary),
                        )
                        .show_ui(ui, |ui| {
                            for (id, name) in &themes {
                                if ui.selectable_label(id == current_theme, name).clicked() {
                                    action = SidebarAction::ChangeTheme(id.clone());
                                }
                            }
                        });

                    ui.add_space(6.0);

                    // Auto Wallpaper toggle (dark emerald tint when ON — crisp contrast, never harsh neon fill)
                    let auto_label = if auto_set_wallpaper {
                        tr(lang, "auto_wall_on")
                    } else {
                        tr(lang, "auto_wall_off")
                    };
                    let (auto_fill, auto_stroke, auto_fg) = if auto_set_wallpaper {
                        (
                            Color32::from_rgba_unmultiplied(16, 185, 129, 42),
                            Color32::from_rgb(16, 185, 129),
                            Color32::from_rgb(74, 222, 128),
                        )
                    } else {
                        (pal.bg_input, pal.border, pal.text_secondary)
                    };
                    let auto_btn = egui::Button::new(
                        RichText::new(auto_label).color(auto_fg).size(11.5).strong(),
                    )
                    .fill(auto_fill)
                    .stroke(Stroke::new(1.0_f32, auto_stroke))
                    .corner_radius(CornerRadius::same(pal.radius_btn()))
                    .min_size(Vec2::new(206.0, 28.0));

                    if ui
                        .add(auto_btn)
                        .on_hover_text(tr(lang, "auto_wallpaper_tip"))
                        .clicked()
                    {
                        action = SidebarAction::ToggleAutoWallpaper(!auto_set_wallpaper);
                    }

                    ui.add_space(6.0);

                    // Settings button
                    let settings_btn = egui::Button::new(
                        RichText::new(format!("⚙  {}", tr(lang, "sidebar_settings")))
                            .color(pal.text_primary)
                            .size(11.5),
                    )
                    .fill(pal.bg_input)
                    .stroke(Stroke::new(1.0_f32, pal.border))
                    .corner_radius(CornerRadius::same(pal.radius_btn()))
                    .min_size(Vec2::new(206.0, 28.0));
                    if ui.add(settings_btn).clicked() {
                        action = SidebarAction::OpenSettings;
                    }
                });
        });

    action
}

fn section_heading(ui: &mut Ui, pal: &ThemePalette, text: &str) {
    ui.label(
        RichText::new(text)
            .color(pal.text_muted)
            .strong()
            .size(10.0),
    );
}

fn nav_tile(
    ui: &mut Ui,
    pal: &ThemePalette,
    glyph: &str,
    title: &str,
    subtitle: &str,
    active: bool,
    badge: Option<String>,
) -> (bool, Rect) {
    let desired = Vec2::new(228.0, 50.0);
    let (rect, resp) = ui.allocate_exact_size(desired, Sense::click());
    let hovered = resp.hovered();

    let fill = if active {
        pal.accent_surface
    } else if hovered {
        pal.bg_input_hover
    } else {
        with_alpha(pal.bg_capsule, 140)
    };
    let border = if active {
        Stroke::new(1.2_f32, pal.accent)
    } else if hovered {
        Stroke::new(1.0_f32, pal.border_hover)
    } else {
        Stroke::new(1.0_f32, pal.border_subtle)
    };

    let p = ui.painter();
    let r = CornerRadius::same(pal.radius_btn());
    p.rect_filled(rect, r, fill);
    p.rect_stroke(rect, r, border, StrokeKind::Inside);

    // 32x32 framed icon tile
    let icon_rect = Rect::from_center_size(Pos2::new(rect.left() + 26.0, rect.center().y), Vec2::splat(32.0));
    let ir = CornerRadius::same(pal.radius_btn().min(4));
    p.rect_filled(icon_rect, ir, pal.bg_capsule);
    p.rect_stroke(
        icon_rect,
        ir,
        Stroke::new(1.0_f32, if active { pal.accent } else { pal.border }),
        StrokeKind::Inside,
    );
    p.text(
        icon_rect.center(),
        Align2::CENTER_CENTER,
        glyph,
        FontId::proportional(14.0),
        if active { pal.accent } else { pal.text_secondary },
    );

    // Title & subtitle
    let title_col = if active || hovered {
        pal.text_primary
    } else {
        pal.text_secondary
    };
    p.text(
        Pos2::new(rect.left() + 48.0, rect.top() + 10.0),
        Align2::LEFT_TOP,
        title,
        FontId::proportional(12.5),
        title_col,
    );
    p.text(
        Pos2::new(rect.left() + 48.0, rect.top() + 28.0),
        Align2::LEFT_TOP,
        subtitle,
        FontId::proportional(9.5),
        pal.text_muted,
    );

    // Right-aligned crisp bordered pill badge
    if let Some(btxt) = badge {
        let font = FontId::monospace(9.5);
        let galley = p.layout_no_wrap(btxt, font, pal.text_primary);
        let bsize = Vec2::new((galley.size().x + 12.0).max(26.0), 18.0);
        let brect = Rect::from_center_size(
            Pos2::new(rect.right() - bsize.x * 0.5 - 8.0, rect.center().y),
            bsize,
        );
        let br = CornerRadius::same(3);
        let (bfill, bstroke, bfg) = if active {
            (pal.accent, pal.accent_hover, pal.accent_text)
        } else {
            (pal.bg_capsule, pal.accent, pal.accent_hover)
        };
        p.rect_filled(brect, br, bfill);
        p.rect_stroke(brect, br, Stroke::new(1.0_f32, bstroke), StrokeKind::Inside);
        p.galley(
            brect.center() - galley.size() * 0.5,
            galley,
            bfg,
        );
    }

    (resp.clicked(), rect)
}
