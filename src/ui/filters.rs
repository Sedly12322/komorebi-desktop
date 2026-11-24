use egui::{
    Align2, Color32, CornerRadius, FontId, Rect, RichText, Sense, Stroke, StrokeKind, Ui, Vec2,
};

use crate::i18n::{tr, Lang};
use crate::models::{CardSize, NavMode};
use crate::providers::{moewalls, osu, pfps, wallhaven::WALLHAVEN_COLOR_CODES};
use crate::theme::{parse_hex, with_alpha, ThemePalette};
use crate::ui::{secondary_button, toggle_pill};

#[derive(Debug, Clone)]
pub struct FilterState {
    pub query: String,
    pub focus_search: bool,

    // Wallhaven
    pub wh_cat_general: bool,
    pub wh_cat_anime: bool,
    pub wh_cat_people: bool,
    pub wh_sfw: bool,
    pub wh_sketchy: bool,
    pub wh_nsfw: bool,
    pub wh_sorting: String,
    pub wh_top_range: String,
    pub wh_ratios: String,
    pub wh_atleast: String,
    pub wh_color: String,
    pub show_color_bar: bool,

    // MoeWalls
    pub moe_category: String,
    pub moe_resolution: String,

    // osu!
    pub osu_season: String,
    pub osu_theme: String,
    pub osu_sort: String,
    pub osu_clean_only: bool,

    // PFPs
    pub pfp_category: String,
    pub pfp_sort: String,

    // Installed
    pub inst_provider: String,
    pub inst_media_type: String,
    pub inst_sort: String,
}

impl Default for FilterState {
    fn default() -> Self {
        Self {
            query: String::new(),
            focus_search: false,
            wh_cat_general: true,
            wh_cat_anime: true,
            wh_cat_people: true,
            wh_sfw: true,
            wh_sketchy: false,
            wh_nsfw: false,
            wh_sorting: "toplist".to_string(),
            wh_top_range: "1M".to_string(),
            wh_ratios: String::new(),
            wh_atleast: String::new(),
            wh_color: String::new(),
            show_color_bar: false,
            moe_category: "all".to_string(),
            moe_resolution: "all".to_string(),
            osu_season: "all".to_string(),
            osu_theme: "all".to_string(),
            osu_sort: "votes".to_string(),
            osu_clean_only: false,
            pfp_category: "all".to_string(),
            pfp_sort: "latest".to_string(),
            inst_provider: "all".to_string(),
            inst_media_type: "all".to_string(),
            inst_sort: "date".to_string(),
        }
    }
}

impl FilterState {
    pub fn categories_bits(&self) -> String {
        let mut s = format!(
            "{}{}{}",
            u8::from(self.wh_cat_general),
            u8::from(self.wh_cat_anime),
            u8::from(self.wh_cat_people)
        );
        if s == "000" {
            s = "111".to_string();
        }
        s
    }

    pub fn purity_bits(&self) -> String {
        let mut s = format!(
            "{}{}{}",
            u8::from(self.wh_sfw),
            u8::from(self.wh_sketchy),
            u8::from(self.wh_nsfw)
        );
        if s == "000" {
            s = "100".to_string();
        }
        s
    }

    pub fn reset_for_mode(&mut self, mode: NavMode) {
        self.query.clear();
        match mode {
            NavMode::Wallhaven => {
                self.wh_cat_general = true;
                self.wh_cat_anime = true;
                self.wh_cat_people = true;
                self.wh_sfw = true;
                self.wh_sketchy = false;
                self.wh_nsfw = false;
                self.wh_sorting = "toplist".into();
                self.wh_top_range = "1M".into();
                self.wh_ratios.clear();
                self.wh_atleast.clear();
                self.wh_color.clear();
            }
            NavMode::MoeWalls => {
                self.moe_category = "all".into();
                self.moe_resolution = "all".into();
            }
            NavMode::Osu => {
                self.osu_season = "all".into();
                self.osu_theme = "all".into();
                self.osu_sort = "votes".into();
                self.osu_clean_only = false;
            }
            NavMode::Pfps => {
                self.pfp_category = "all".into();
                self.pfp_sort = "latest".into();
            }
            NavMode::Installed => {
                self.inst_provider = "all".into();
                self.inst_media_type = "all".into();
                self.inst_sort = "date".into();
            }
        }
    }
}

pub enum FilterAction {
    None,
    Search,
    SetCardSize(CardSize),
    NsfwBlockedNeedsApiKey,
    OpenDownloadFolder,
    RescanInstalled,
}

#[allow(clippy::too_many_arguments)]
pub fn render_filter_panel(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    mode: NavMode,
    state: &mut FilterState,
    card_size: CardSize,
    content_w: f32,
    has_api_key: bool,
    installed_stats_text: &str,
) -> FilterAction {
    let mut action = FilterAction::None;
    let inner_w = (content_w - 22.0).max(200.0);

    // BAR 1: Spotlight Search Bar + [Ctrl+K] + [S|M|L] + Search
    egui::Frame::new()
        .fill(pal.bg_surface)
        .stroke(Stroke::new(1.0_f32, with_alpha(pal.accent, 145)))
        .corner_radius(CornerRadius::same(pal.radius_card()))
        .inner_margin(egui::Margin::symmetric(10, 8))
        .show(ui, |ui| {
            ui.set_max_width(inner_w);
            ui.horizontal(|ui| {
                ui.spacing_mut().item_spacing.x = 6.0;

                // Left accent badge (30x30)
                let (badge_rect, _) = ui.allocate_exact_size(Vec2::splat(30.0), Sense::hover());
                let br = CornerRadius::same(pal.radius_btn());
                ui.painter().rect_filled(badge_rect, br, pal.accent_surface);
                ui.painter().rect_stroke(
                    badge_rect,
                    br,
                    Stroke::new(1.0_f32, pal.accent),
                    StrokeKind::Inside,
                );
                ui.painter().text(
                    badge_rect.center(),
                    Align2::CENTER_CENTER,
                    if pal.is_terminal { ">" } else { "✦" },
                    FontId::monospace(14.0),
                    pal.accent,
                );

                // Fixed budget calculation so nothing overflows past inner_w
                let show_keycap = content_w >= 650.0;
                let keycap_w = if show_keycap { 58.0 + 6.0 } else { 0.0 };
                let size_strip_w = 92.0 + 6.0;
                let search_btn_w = 78.0 + 6.0;
                let right_w = keycap_w + size_strip_w + search_btn_w;
                let input_w = (inner_w - 30.0 - 6.0 - right_w).max(120.0);

                let placeholder = match mode {
                    NavMode::Wallhaven => tr(lang, "search_placeholder"),
                    NavMode::MoeWalls => tr(lang, "moe_search_placeholder"),
                    NavMode::Osu => tr(lang, "osu_search_placeholder"),
                    NavMode::Pfps => tr(lang, "pfps_search_placeholder"),
                    NavMode::Installed => tr(lang, "installed_search_placeholder"),
                };

                let resp = ui.add_sized(
                    [input_w, 30.0],
                    egui::TextEdit::singleline(&mut state.query).hint_text(placeholder),
                );
                if state.focus_search {
                    resp.request_focus();
                    state.focus_search = false;
                }
                if resp.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter)) {
                    action = FilterAction::Search;
                }

                if show_keycap {
                    let (kr, _) =
                        ui.allocate_exact_size(Vec2::new(58.0, 30.0), Sense::hover());
                    let kcr = CornerRadius::same(pal.radius_btn());
                    ui.painter().rect_filled(kr, kcr, pal.bg_input);
                    ui.painter().rect_stroke(
                        kr,
                        kcr,
                        Stroke::new(1.0_f32, pal.border_subtle),
                        StrokeKind::Inside,
                    );
                    ui.painter().text(
                        kr.center(),
                        Align2::CENTER_CENTER,
                        "Ctrl+K",
                        FontId::monospace(10.5),
                        pal.text_muted,
                    );
                }

                // Segmented S | M | L card size control
                let (seg_rect, _) = ui.allocate_exact_size(Vec2::new(92.0, 30.0), Sense::hover());
                let scr = CornerRadius::same(pal.radius_btn());
                ui.painter().rect_filled(seg_rect, scr, pal.bg_capsule);
                ui.painter().rect_stroke(
                    seg_rect,
                    scr,
                    Stroke::new(1.0_f32, pal.border),
                    StrokeKind::Inside,
                );
                let seg_w = seg_rect.width() / 3.0;
                for (i, (sz, lbl, tip_key)) in [
                    (CardSize::Compact, "S", "card_size_compact_tip"),
                    (CardSize::Normal, "M", "card_size_normal_tip"),
                    (CardSize::Large, "L", "card_size_large_tip"),
                ]
                .into_iter()
                .enumerate()
                {
                    let r = Rect::from_min_size(
                        egui::Pos2::new(seg_rect.left() + i as f32 * seg_w, seg_rect.top()),
                        Vec2::new(seg_w, seg_rect.height()),
                    );
                    let resp_seg =
                        ui.interact(r, ui.id().with(("card_seg", i)), Sense::click());
                    let active = card_size == sz;
                    if active {
                        ui.painter().rect_filled(
                            r.shrink(2.0),
                            CornerRadius::same(pal.radius_btn().min(4)),
                            pal.accent,
                        );
                    } else if resp_seg.hovered() {
                        ui.painter().rect_filled(
                            r.shrink(2.0),
                            CornerRadius::same(pal.radius_btn().min(4)),
                            pal.bg_input_hover,
                        );
                    }
                    ui.painter().text(
                        r.center(),
                        Align2::CENTER_CENTER,
                        lbl,
                        FontId::proportional(11.5),
                        if active {
                            pal.accent_text
                        } else {
                            pal.text_secondary
                        },
                    );
                    if resp_seg.on_hover_text(tr(lang, tip_key)).clicked() {
                        action = FilterAction::SetCardSize(sz);
                    }
                }

                // Search button (aligned height 30)
                let search_btn = egui::Button::new(
                    RichText::new(tr(lang, "search_button"))
                        .color(pal.accent_text)
                        .strong()
                        .size(12.0),
                )
                .fill(pal.accent)
                .stroke(Stroke::new(1.0_f32, pal.accent_hover))
                .corner_radius(CornerRadius::same(pal.radius_btn()))
                .min_size(Vec2::new(78.0, 30.0));
                if ui.add(search_btn).clicked() {
                    action = FilterAction::Search;
                }
            });
        });

    ui.add_space(6.0);

    // BAR 2: Mode-specific Filter Bar (strictly bounded within content_w)
    egui::Frame::new()
        .fill(pal.bg_surface)
        .stroke(Stroke::new(1.0_f32, pal.border_subtle))
        .corner_radius(CornerRadius::same(pal.radius_card()))
        .inner_margin(egui::Margin::symmetric(10, 7))
        .show(ui, |ui| {
            ui.set_max_width(inner_w);
            match mode {
                NavMode::Wallhaven => {
                    render_wallhaven_filters(ui, pal, lang, state, content_w, has_api_key, &mut action);
                }
                NavMode::MoeWalls => render_moewalls_filters(ui, pal, lang, state, &mut action),
                NavMode::Osu => render_osu_filters(ui, pal, lang, state, &mut action),
                NavMode::Pfps => render_pfps_filters(ui, pal, lang, state, &mut action),
                NavMode::Installed => {
                    render_installed_filters(ui, pal, lang, state, installed_stats_text, &mut action)
                }
            }
        });

    action
}

fn render_wallhaven_filters(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    state: &mut FilterState,
    content_w: f32,
    has_api_key: bool,
    action: &mut FilterAction,
) {
    let draw_toggles = |ui: &mut Ui, state: &mut FilterState, action: &mut FilterAction| {
        if toggle_pill(ui, pal, tr(lang, "cat_general"), state.wh_cat_general).clicked() {
            state.wh_cat_general = !state.wh_cat_general;
            *action = FilterAction::Search;
        }
        if toggle_pill(ui, pal, tr(lang, "cat_anime"), state.wh_cat_anime).clicked() {
            state.wh_cat_anime = !state.wh_cat_anime;
            *action = FilterAction::Search;
        }
        if toggle_pill(ui, pal, tr(lang, "cat_people"), state.wh_cat_people).clicked() {
            state.wh_cat_people = !state.wh_cat_people;
            *action = FilterAction::Search;
        }
        ui.separator();
        if toggle_pill(ui, pal, "SFW", state.wh_sfw).clicked() {
            state.wh_sfw = !state.wh_sfw;
            *action = FilterAction::Search;
        }
        if toggle_pill(ui, pal, "Sketchy", state.wh_sketchy).clicked() {
            state.wh_sketchy = !state.wh_sketchy;
            *action = FilterAction::Search;
        }
        if toggle_pill(ui, pal, "NSFW", state.wh_nsfw).clicked() {
            if !has_api_key && !state.wh_nsfw {
                *action = FilterAction::NsfwBlockedNeedsApiKey;
            } else {
                state.wh_nsfw = !state.wh_nsfw;
                *action = FilterAction::Search;
            }
        }
    };

    let draw_combos_and_tools =
        |ui: &mut Ui, state: &mut FilterState, action: &mut FilterAction, include_tools: bool| {
            let sorts = [
                ("toplist", tr(lang, "sort_toplist")),
                ("hot", tr(lang, "sort_hot")),
                ("date_added", tr(lang, "sort_latest")),
                ("views", tr(lang, "sort_views")),
                ("favorites", tr(lang, "sort_favorites")),
                ("random", tr(lang, "sort_random")),
                ("relevance", tr(lang, "sort_relevance")),
            ];
            let cur_sort = sorts
                .iter()
                .find(|(id, _)| *id == state.wh_sorting)
                .map(|(_, l)| *l)
                .unwrap_or("Toplist");
            egui::ComboBox::from_id_salt("wh_sort_combo")
                .selected_text(cur_sort)
                .width(96.0)
                .show_ui(ui, |ui| {
                    for (id, label) in sorts {
                        if ui
                            .selectable_value(&mut state.wh_sorting, id.to_string(), label)
                            .changed()
                        {
                            *action = FilterAction::Search;
                        }
                    }
                });

            if state.wh_sorting == "toplist" {
                let ranges = [
                    ("1d", tr(lang, "range_1d")),
                    ("3d", tr(lang, "range_3d")),
                    ("1w", tr(lang, "range_1w")),
                    ("1M", tr(lang, "range_1M")),
                    ("3M", tr(lang, "range_3M")),
                    ("6M", tr(lang, "range_6M")),
                    ("1y", tr(lang, "range_1y")),
                ];
                let cur_range = ranges
                    .iter()
                    .find(|(id, _)| *id == state.wh_top_range)
                    .map(|(_, l)| *l)
                    .unwrap_or("1M");
                egui::ComboBox::from_id_salt("wh_range_combo")
                    .selected_text(cur_range)
                    .width(86.0)
                    .show_ui(ui, |ui| {
                        for (id, label) in ranges {
                            if ui
                                .selectable_value(&mut state.wh_top_range, id.to_string(), label)
                                .changed()
                            {
                                *action = FilterAction::Search;
                            }
                        }
                    });
            }

            let ratios = [
                ("", tr(lang, "ratio_any")),
                ("16x9", tr(lang, "ratio_16x9")),
                ("16x10", tr(lang, "ratio_16x10")),
                ("21x9", tr(lang, "ratio_21x9")),
                ("32x9", tr(lang, "ratio_32x9")),
                ("9x16", tr(lang, "ratio_9x16")),
            ];
            let cur_ratio = ratios
                .iter()
                .find(|(id, _)| *id == state.wh_ratios)
                .map(|(_, l)| *l)
                .unwrap_or("Any Ratio");
            egui::ComboBox::from_id_salt("wh_ratio_combo")
                .selected_text(cur_ratio)
                .width(108.0)
                .show_ui(ui, |ui| {
                    for (id, label) in ratios {
                        if ui
                            .selectable_value(&mut state.wh_ratios, id.to_string(), label)
                            .changed()
                        {
                            *action = FilterAction::Search;
                        }
                    }
                });

            let res_opts = [
                ("", tr(lang, "res_any")),
                ("1920x1080", tr(lang, "res_1080p")),
                ("2560x1440", tr(lang, "res_1440p")),
                ("3840x2160", tr(lang, "res_4k")),
                ("7680x4320", tr(lang, "res_8k")),
            ];
            let cur_res = res_opts
                .iter()
                .find(|(id, _)| *id == state.wh_atleast)
                .map(|(_, l)| *l)
                .unwrap_or("Any");
            egui::ComboBox::from_id_salt("wh_res_combo")
                .selected_text(cur_res)
                .width(114.0)
                .show_ui(ui, |ui| {
                    for (id, label) in res_opts {
                        if ui
                            .selectable_value(&mut state.wh_atleast, id.to_string(), label)
                            .changed()
                        {
                            *action = FilterAction::Search;
                        }
                    }
                });

            if include_tools {
                let col_lbl = if state.wh_color.is_empty() {
                    tr(lang, "colors_button").to_string()
                } else {
                    format!("#{}", state.wh_color)
                };
                if toggle_pill(
                    ui,
                    pal,
                    &col_lbl,
                    state.show_color_bar || !state.wh_color.is_empty(),
                )
                .clicked()
                {
                    state.show_color_bar = !state.show_color_bar;
                }
                if secondary_button(ui, pal, "↺")
                    .on_hover_text(tr(lang, "reset_filters_tip"))
                    .clicked()
                {
                    state.reset_for_mode(NavMode::Wallhaven);
                    *action = FilterAction::Search;
                }
            }
        };

    if content_w >= 980.0 {
        ui.horizontal_wrapped(|ui| {
            ui.spacing_mut().item_spacing = Vec2::new(5.0, 4.0);
            draw_toggles(ui, state, action);
            ui.separator();
            draw_combos_and_tools(ui, state, action, true);
        });
    } else {
        // Two clean, non-clipping rows on narrower tiled splits (e.g. 944x1020)
        ui.horizontal(|ui| {
            ui.spacing_mut().item_spacing.x = 5.0;
            draw_toggles(ui, state, action);
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if secondary_button(ui, pal, "↺")
                    .on_hover_text(tr(lang, "reset_filters_tip"))
                    .clicked()
                {
                    state.reset_for_mode(NavMode::Wallhaven);
                    *action = FilterAction::Search;
                }
                let col_lbl = if state.wh_color.is_empty() {
                    tr(lang, "colors_button").to_string()
                } else {
                    format!("#{}", state.wh_color)
                };
                if toggle_pill(
                    ui,
                    pal,
                    &col_lbl,
                    state.show_color_bar || !state.wh_color.is_empty(),
                )
                .clicked()
                {
                    state.show_color_bar = !state.show_color_bar;
                }
            });
        });
        ui.add_space(5.0);
        ui.horizontal_wrapped(|ui| {
            ui.spacing_mut().item_spacing = Vec2::new(5.0, 4.0);
            ui.label(RichText::new(tr(lang, "sorting_label")).color(pal.text_muted).size(11.0));
            draw_combos_and_tools(ui, state, action, false);
        });
    }

    if state.show_color_bar {
        ui.add_space(6.0);
        ui.horizontal_wrapped(|ui| {
            ui.spacing_mut().item_spacing = Vec2::new(5.0, 4.0);
            ui.label(RichText::new(tr(lang, "color_label")).color(pal.text_muted).size(11.5));

            if toggle_pill(ui, pal, tr(lang, "color_clear"), state.wh_color.is_empty()).clicked() {
                state.wh_color.clear();
                *action = FilterAction::Search;
            }

            for code in WALLHAVEN_COLOR_CODES {
                let selected = state.wh_color.eq_ignore_ascii_case(code);
                let (rect, resp) = ui.allocate_exact_size(Vec2::splat(20.0), Sense::click());
                let fill = parse_hex(code);
                let cr = CornerRadius::same(4);
                ui.painter().rect_filled(rect, cr, fill);
                let stroke = if selected {
                    Stroke::new(2.0_f32, Color32::WHITE)
                } else if resp.hovered() {
                    Stroke::new(1.5_f32, pal.accent)
                } else {
                    Stroke::new(1.0_f32, pal.border_subtle)
                };
                ui.painter().rect_stroke(rect, cr, stroke, StrokeKind::Inside);
                if resp.on_hover_text(format!("#{code}")).clicked() {
                    state.wh_color = if selected {
                        String::new()
                    } else {
                        (*code).to_string()
                    };
                    *action = FilterAction::Search;
                }
            }
        });
    }
}

fn render_moewalls_filters(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    state: &mut FilterState,
    action: &mut FilterAction,
) {
    ui.horizontal_wrapped(|ui| {
        ui.spacing_mut().item_spacing = Vec2::new(6.0, 4.0);
        ui.label(
            RichText::new(tr(lang, "moe_category_label"))
                .color(pal.text_muted)
                .size(11.5),
        );
        let cur_cat = moewalls::CATEGORIES
            .iter()
            .find(|(id, _)| *id == state.moe_category)
            .map(|(_, l)| *l)
            .unwrap_or("All");
        egui::ComboBox::from_id_salt("moe_cat_combo")
            .selected_text(cur_cat)
            .width(126.0)
            .show_ui(ui, |ui| {
                for (id, label) in moewalls::CATEGORIES {
                    if ui
                        .selectable_value(&mut state.moe_category, (*id).to_string(), *label)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        ui.label(
            RichText::new(tr(lang, "moe_res_label"))
                .color(pal.text_muted)
                .size(11.5),
        );
        let cur_res_key = moewalls::RESOLUTIONS
            .iter()
            .find(|(id, _)| *id == state.moe_resolution)
            .map(|(_, k)| *k)
            .unwrap_or("moe_res_all");
        egui::ComboBox::from_id_salt("moe_res_combo")
            .selected_text(tr(lang, cur_res_key))
            .width(170.0)
            .show_ui(ui, |ui| {
                for (id, key) in moewalls::RESOLUTIONS {
                    if ui
                        .selectable_value(
                            &mut state.moe_resolution,
                            (*id).to_string(),
                            tr(lang, key),
                        )
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        if secondary_button(ui, pal, "↺")
            .on_hover_text(tr(lang, "reset_filters_tip"))
            .clicked()
        {
            state.reset_for_mode(NavMode::MoeWalls);
            *action = FilterAction::Search;
        }
    });
}

fn render_osu_filters(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    state: &mut FilterState,
    action: &mut FilterAction,
) {
    ui.horizontal_wrapped(|ui| {
        ui.spacing_mut().item_spacing = Vec2::new(6.0, 4.0);
        ui.label(
            RichText::new(tr(lang, "season_label"))
                .color(pal.text_muted)
                .size(11.5),
        );
        egui::ComboBox::from_id_salt("osu_season_combo")
            .selected_text(if state.osu_season == "all" {
                tr(lang, "theme_all")
            } else {
                state.osu_season.as_str()
            })
            .width(120.0)
            .show_ui(ui, |ui| {
                if ui
                    .selectable_value(&mut state.osu_season, "all".into(), tr(lang, "theme_all"))
                    .changed()
                {
                    *action = FilterAction::Search;
                }
                for s in osu::seasons() {
                    if ui
                        .selectable_value(&mut state.osu_season, s.clone(), &s)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        ui.label(
            RichText::new(tr(lang, "theme_label"))
                .color(pal.text_muted)
                .size(11.5),
        );
        egui::ComboBox::from_id_salt("osu_theme_combo")
            .selected_text(if state.osu_theme == "all" {
                tr(lang, "theme_all")
            } else {
                state.osu_theme.as_str()
            })
            .width(110.0)
            .show_ui(ui, |ui| {
                if ui
                    .selectable_value(&mut state.osu_theme, "all".into(), tr(lang, "theme_all"))
                    .changed()
                {
                    *action = FilterAction::Search;
                }
                for t in osu::themes() {
                    if ui
                        .selectable_value(&mut state.osu_theme, t.clone(), &t)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        let sorts = [
            ("votes", tr(lang, "sort_osu_votes")),
            ("newest", tr(lang, "sort_osu_newest")),
            ("rank", "Contest Rank"),
        ];
        let cur_sort = sorts
            .iter()
            .find(|(id, _)| *id == state.osu_sort)
            .map(|(_, l)| *l)
            .unwrap_or("Winners");
        egui::ComboBox::from_id_salt("osu_sort_combo")
            .selected_text(cur_sort)
            .width(105.0)
            .show_ui(ui, |ui| {
                for (id, lbl) in sorts {
                    if ui
                        .selectable_value(&mut state.osu_sort, id.to_string(), lbl)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        if toggle_pill(ui, pal, "No Logo", state.osu_clean_only).clicked() {
            state.osu_clean_only = !state.osu_clean_only;
            *action = FilterAction::Search;
        }
        if secondary_button(ui, pal, "↺")
            .on_hover_text(tr(lang, "reset_filters_tip"))
            .clicked()
        {
            state.reset_for_mode(NavMode::Osu);
            *action = FilterAction::Search;
        }
    });
}

fn render_pfps_filters(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    state: &mut FilterState,
    action: &mut FilterAction,
) {
    ui.horizontal_wrapped(|ui| {
        ui.spacing_mut().item_spacing = Vec2::new(6.0, 4.0);
        ui.label(
            RichText::new(tr(lang, "pfps_category_label"))
                .color(pal.text_muted)
                .size(11.5),
        );
        let cur_cat = pfps::PFP_CATEGORIES
            .iter()
            .find(|(id, _)| *id == state.pfp_category)
            .map(|(_, l)| *l)
            .unwrap_or("All");
        egui::ComboBox::from_id_salt("pfp_cat_combo")
            .selected_text(cur_cat)
            .width(136.0)
            .show_ui(ui, |ui| {
                for (id, lbl) in pfps::PFP_CATEGORIES {
                    if ui
                        .selectable_value(&mut state.pfp_category, (*id).to_string(), *lbl)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        ui.label(
            RichText::new(tr(lang, "pfps_sort_label"))
                .color(pal.text_muted)
                .size(11.5),
        );
        let cur_sort = pfps::PFP_SORTING
            .iter()
            .find(|(id, _)| *id == state.pfp_sort)
            .map(|(_, l)| *l)
            .unwrap_or("Latest");
        egui::ComboBox::from_id_salt("pfp_sort_combo")
            .selected_text(cur_sort)
            .width(140.0)
            .show_ui(ui, |ui| {
                for (id, lbl) in pfps::PFP_SORTING {
                    if ui
                        .selectable_value(&mut state.pfp_sort, (*id).to_string(), *lbl)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        if secondary_button(ui, pal, "↺")
            .on_hover_text(tr(lang, "reset_filters_tip"))
            .clicked()
        {
            state.reset_for_mode(NavMode::Pfps);
            *action = FilterAction::Search;
        }
    });
}

fn render_installed_filters(
    ui: &mut Ui,
    pal: &ThemePalette,
    lang: Lang,
    state: &mut FilterState,
    stats_text: &str,
    action: &mut FilterAction,
) {
    ui.horizontal_wrapped(|ui| {
        ui.spacing_mut().item_spacing = Vec2::new(6.0, 4.0);
        let providers = [
            ("all", tr(lang, "installed_provider_all")),
            ("wallhaven", "Wallhaven"),
            ("moewalls", "MoeWalls"),
            ("osu", "osu!"),
            ("local", "Local Files"),
        ];
        let cur_prov = providers
            .iter()
            .find(|(id, _)| *id == state.inst_provider)
            .map(|(_, l)| *l)
            .unwrap_or("All");
        egui::ComboBox::from_id_salt("inst_prov_combo")
            .selected_text(cur_prov)
            .width(116.0)
            .show_ui(ui, |ui| {
                for (id, lbl) in providers {
                    if ui
                        .selectable_value(&mut state.inst_provider, id.to_string(), lbl)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        let types = [
            ("all", tr(lang, "installed_type_all")),
            ("static", tr(lang, "installed_type_image")),
            ("live", tr(lang, "installed_type_video")),
        ];
        let cur_t = types
            .iter()
            .find(|(id, _)| *id == state.inst_media_type)
            .map(|(_, l)| *l)
            .unwrap_or("All");
        egui::ComboBox::from_id_salt("inst_type_combo")
            .selected_text(cur_t)
            .width(120.0)
            .show_ui(ui, |ui| {
                for (id, lbl) in types {
                    if ui
                        .selectable_value(&mut state.inst_media_type, id.to_string(), lbl)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        let sorts = [
            ("date", tr(lang, "installed_sort_newest")),
            ("name", tr(lang, "installed_sort_name")),
            ("size", tr(lang, "installed_sort_size")),
        ];
        let cur_s = sorts
            .iter()
            .find(|(id, _)| *id == state.inst_sort)
            .map(|(_, l)| *l)
            .unwrap_or("Newest");
        egui::ComboBox::from_id_salt("inst_sort_combo")
            .selected_text(cur_s)
            .width(110.0)
            .show_ui(ui, |ui| {
                for (id, lbl) in sorts {
                    if ui
                        .selectable_value(&mut state.inst_sort, id.to_string(), lbl)
                        .changed()
                    {
                        *action = FilterAction::Search;
                    }
                }
            });

        if secondary_button(ui, pal, tr(lang, "installed_open_folder")).clicked() {
            *action = FilterAction::OpenDownloadFolder;
        }
        if secondary_button(ui, pal, "↻").clicked() {
            *action = FilterAction::RescanInstalled;
        }
        ui.label(
            RichText::new(stats_text)
                .color(pal.text_secondary)
                .size(11.0),
        );
    });
}
