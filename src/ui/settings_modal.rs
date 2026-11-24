use egui::{Color32, CornerRadius, RichText, Stroke, Ui, Vec2};

use crate::config::AppConfig;
use crate::i18n::{tr, Lang};
use crate::models::format_bytes;
use crate::theme::{get_available_themes, ThemePalette};
use crate::ui::{accent_button, danger_button, secondary_button};
use crate::updater::UpdateInfo;
use crate::wallpaper::{MonitorInfo, SetterOption};

pub struct SettingsModalState {
    pub draft: AppConfig,
    pub original_theme: String,
    pub original_lang: String,
    pub show_api_key: bool,
    pub cache_bytes: u64,
    pub monitors: Vec<MonitorInfo>,
    pub setters: Vec<SetterOption>,
    pub update_status: Option<Result<UpdateInfo, String>>,
    pub checking_updates: bool,
}

impl SettingsModalState {
    pub fn new(
        cfg: &AppConfig,
        cache_bytes: u64,
        monitors: Vec<MonitorInfo>,
        setters: Vec<SetterOption>,
        update_info: Option<&UpdateInfo>,
    ) -> Self {
        Self {
            draft: cfg.clone(),
            original_theme: cfg.theme.clone(),
            original_lang: cfg.language.clone(),
            show_api_key: false,
            cache_bytes,
            monitors,
            setters,
            update_status: update_info.cloned().map(Ok),
            checking_updates: false,
        }
    }
}

pub enum SettingsAction {
    None,
    Save,
    Cancel,
    PreviewTheme(String),
    PreviewLanguage(String),
    BrowseDownloadDir,
    ClearCache,
    TestSetter,
    CheckUpdates,
    OpenUrl(String),
}

pub fn render_settings_modal(
    ctx: &egui::Context,
    pal: &ThemePalette,
    lang: Lang,
    state: &mut SettingsModalState,
) -> SettingsAction {
    let mut action = SettingsAction::None;
    let screen = ctx.screen_rect();

    let win_w = (screen.width() * 0.62).clamp(540.0, 740.0);
    let win_h = (screen.height() * 0.84).clamp(480.0, 740.0);

    let modal_resp = egui::Modal::new(egui::Id::new("komorebi_settings_modal"))
        .backdrop_color(Color32::from_black_alpha(110))
        .frame(
            egui::Frame::new()
                .fill(pal.bg_surface)
                .stroke(Stroke::new(1.5_f32, pal.accent))
                .corner_radius(CornerRadius::same(pal.radius_card()))
                .inner_margin(egui::Margin::same(18)),
        )
        .show(ctx, |ui| {
            ui.set_min_size(Vec2::new(win_w, win_h));
            ui.set_max_size(Vec2::new(win_w, win_h));
            ui.horizontal(|ui| {
                ui.label(
                    RichText::new(tr(lang, "settings_title"))
                        .color(pal.text_primary)
                        .strong()
                        .size(18.0),
                );
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if secondary_button(ui, pal, "✕").clicked() {
                        action = SettingsAction::Cancel;
                    }
                });
            });

            ui.separator();
            ui.add_space(6.0);

            let scroll_h = (win_h - 118.0).max(240.0);
            egui::ScrollArea::vertical()
                .max_height(scroll_h)
                .show(ui, |ui| {
                    // Appearance & Theme
                    section_box(ui, pal, tr(lang, "theme_section"), |ui| {
                        let themes = get_available_themes(lang);
                        let cur_t = themes
                            .iter()
                            .find(|(id, _)| id == &state.draft.theme)
                            .map(|(_, n)| n.as_str())
                            .unwrap_or(&state.draft.theme)
                            .to_string();
                        ui.horizontal(|ui| {
                            ui.label(RichText::new(tr(lang, "theme_setting_label")).color(pal.text_secondary));
                            egui::ComboBox::from_id_salt("settings_theme_combo")
                                .selected_text(cur_t)
                                .width(260.0)
                                .show_ui(ui, |ui| {
                                    for (id, name) in &themes {
                                        if ui
                                            .selectable_value(&mut state.draft.theme, id.clone(), name)
                                            .changed()
                                        {
                                            action = SettingsAction::PreviewTheme(id.clone());
                                        }
                                    }
                                });
                        });

                        ui.horizontal(|ui| {
                            ui.label(RichText::new(tr(lang, "lang_label")).color(pal.text_secondary));
                            let langs = [("en", "English"), ("cs", "Čeština")];
                            let cur_l = langs
                                .iter()
                                .find(|(id, _)| *id == state.draft.language)
                                .map(|(_, n)| *n)
                                .unwrap_or("English");
                            egui::ComboBox::from_id_salt("settings_lang_combo")
                                .selected_text(cur_l)
                                .width(180.0)
                                .show_ui(ui, |ui| {
                                    for (id, name) in langs {
                                        if ui
                                            .selectable_value(
                                                &mut state.draft.language,
                                                id.to_string(),
                                                name,
                                            )
                                            .changed()
                                        {
                                            action = SettingsAction::PreviewLanguage(id.to_string());
                                        }
                                    }
                                });
                        });

                        ui.checkbox(
                            &mut state.draft.background_effects,
                            tr(lang, "bg_effects_label"),
                        );
                    });

                    ui.add_space(10.0);

                    // Wallhaven API Key
                    section_box(ui, pal, tr(lang, "api_group"), |ui| {
                        ui.horizontal(|ui| {
                            let edit = egui::TextEdit::singleline(&mut state.draft.api_key)
                                .password(!state.show_api_key)
                                .desired_width((ui.available_width() - 80.0).max(200.0))
                                .hint_text(tr(lang, "api_placeholder"));
                            ui.add(edit);
                            if secondary_button(
                                ui,
                                pal,
                                if state.show_api_key { "Hide" } else { "Show" },
                            )
                            .clicked()
                            {
                                state.show_api_key = !state.show_api_key;
                            }
                        });
                    });

                    ui.add_space(10.0);

                    // Download Folder
                    section_box(ui, pal, tr(lang, "dir_group"), |ui| {
                        ui.horizontal(|ui| {
                            ui.add(
                                egui::TextEdit::singleline(&mut state.draft.default_download_dir)
                                    .desired_width((ui.available_width() - 100.0).max(220.0)),
                            );
                            if secondary_button(ui, pal, tr(lang, "browse_button")).clicked() {
                                action = SettingsAction::BrowseDownloadDir;
                            }
                        });
                    });

                    ui.add_space(10.0);

                    // Desktop Wallpaper Settings
                    section_box(ui, pal, tr(lang, "wall_group"), |ui| {
                        ui.checkbox(
                            &mut state.draft.auto_set_wallpaper,
                            tr(lang, "auto_wall_checkbox"),
                        );

                        ui.horizontal(|ui| {
                            ui.label(
                                RichText::new(tr(lang, "wallpaper_setter_label"))
                                    .color(pal.text_secondary),
                            );
                            let cur_s = state
                                .setters
                                .iter()
                                .find(|s| s.id == state.draft.wallpaper_setter)
                                .map(|s| s.label.as_str())
                                .unwrap_or(&state.draft.wallpaper_setter)
                                .to_string();
                            egui::ComboBox::from_id_salt("settings_setter_combo")
                                .selected_text(cur_s)
                                .width(260.0)
                                .show_ui(ui, |ui| {
                                    for s in &state.setters {
                                        let label = if s.available {
                                            format!("{}  ✓", s.label)
                                        } else {
                                            format!("{}  (not found)", s.label)
                                        };
                                        ui.selectable_value(
                                            &mut state.draft.wallpaper_setter,
                                            s.id.clone(),
                                            label,
                                        );
                                    }
                                });
                            if secondary_button(ui, pal, tr(lang, "test_setter_btn")).clicked() {
                                action = SettingsAction::TestSetter;
                            }
                        });

                        ui.horizontal(|ui| {
                            ui.label(
                                RichText::new(tr(lang, "detail_monitor_label"))
                                    .color(pal.text_secondary),
                            );
                            let cur_m = state
                                .monitors
                                .iter()
                                .find(|m| m.id == state.draft.wallpaper_monitor)
                                .map(|m| m.label.as_str())
                                .unwrap_or(tr(lang, "monitor_all"))
                                .to_string();
                            egui::ComboBox::from_id_salt("settings_monitor_combo")
                                .selected_text(cur_m)
                                .width(220.0)
                                .show_ui(ui, |ui| {
                                    for m in &state.monitors {
                                        ui.selectable_value(
                                            &mut state.draft.wallpaper_monitor,
                                            m.id.clone(),
                                            &m.label,
                                        );
                                    }
                                });
                        });

                        ui.add_space(4.0);
                        ui.label(
                            RichText::new(tr(lang, "custom_cmd_label"))
                                .color(pal.text_muted)
                                .size(11.5),
                        );
                        ui.add(
                            egui::TextEdit::singleline(&mut state.draft.custom_wallpaper_cmd)
                                .desired_width(f32::INFINITY)
                                .hint_text("e.g. swww img \"{file}\" -o {monitor}"),
                        );

                        ui.label(
                            RichText::new(tr(lang, "custom_video_cmd_label"))
                                .color(pal.text_muted)
                                .size(11.5),
                        );
                        ui.add(
                            egui::TextEdit::singleline(&mut state.draft.custom_video_wallpaper_cmd)
                                .desired_width(f32::INFINITY)
                                .hint_text("e.g. mpvpaper -vs -o \"no-audio --loop\" '*' \"{file}\""),
                        );
                    });

                    ui.add_space(10.0);

                    // Disk Cache
                    section_box(ui, pal, tr(lang, "cache_group"), |ui| {
                        ui.horizontal(|ui| {
                            ui.label(
                                RichText::new(format!(
                                    "Cache size: {}",
                                    format_bytes(state.cache_bytes)
                                ))
                                .color(pal.text_secondary),
                            );
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                if danger_button(ui, pal, tr(lang, "cache_clear_button")).clicked() {
                                    action = SettingsAction::ClearCache;
                                }
                            });
                        });
                    });

                    ui.add_space(10.0);

                    // Updates
                    section_box(ui, pal, tr(lang, "update_section"), |ui| {
                        ui.checkbox(
                            &mut state.draft.check_updates_on_launch,
                            tr(lang, "update_auto_check"),
                        );
                        ui.horizontal(|ui| {
                            if secondary_button(ui, pal, tr(lang, "update_check_btn")).clicked() {
                                action = SettingsAction::CheckUpdates;
                            }
                            if state.checking_updates {
                                ui.spinner();
                            } else if let Some(res) = &state.update_status {
                                match res {
                                    Ok(upd) if upd.has_update => {
                                        ui.label(
                                            RichText::new(format!(
                                                "New release available: v{}",
                                                upd.latest
                                            ))
                                            .color(pal.accent),
                                        );
                                        if secondary_button(ui, pal, "Open Release").clicked() {
                                            action = SettingsAction::OpenUrl(upd.url.clone());
                                        }
                                    }
                                    Ok(upd) => {
                                        ui.label(
                                            RichText::new(format!("Up to date (v{})", upd.current))
                                                .color(pal.text_muted),
                                        );
                                    }
                                    Err(err) => {
                                        ui.label(
                                            RichText::new(err)
                                                .color(Color32::from_rgb(248, 113, 113)),
                                        );
                                    }
                                }
                            }
                        });
                    });
                });

            ui.add_space(8.0);
            ui.separator();
            ui.add_space(6.0);

            ui.horizontal(|ui| {
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if accent_button(ui, pal, tr(lang, "btn_save")).clicked() {
                        action = SettingsAction::Save;
                    }
                    if secondary_button(ui, pal, tr(lang, "btn_cancel")).clicked() {
                        action = SettingsAction::Cancel;
                    }
                });
            });
        });

    if matches!(action, SettingsAction::None) && modal_resp.should_close() {
        action = SettingsAction::Cancel;
    }

    action
}

fn section_box(
    ui: &mut Ui,
    pal: &ThemePalette,
    title: &str,
    add_contents: impl FnOnce(&mut Ui),
) {
    egui::Frame::new()
        .fill(pal.bg_subsurface)
        .stroke(Stroke::new(1.0_f32, pal.border_subtle))
        .corner_radius(CornerRadius::same(pal.radius_card()))
        .inner_margin(egui::Margin::same(12))
        .show(ui, |ui| {
            ui.label(
                RichText::new(title)
                    .color(pal.accent)
                    .strong()
                    .size(13.0),
            );
            ui.add_space(6.0);
            add_contents(ui);
        });
}
