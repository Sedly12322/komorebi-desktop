use egui::{
    Align2, Color32, CornerRadius, FontId, Pos2, Rect, RichText, Sense, Stroke, StrokeKind,
    TextureHandle, TextureOptions, Ui, Vec2,
};

use crate::cache::ImageLoader;
use crate::i18n::{tr, Lang};
use crate::models::{format_bytes, WallpaperItem};
use crate::theme::{parse_hex, ThemePalette};
use crate::ui::{
    accent_button, compute_contain_size, danger_button, secondary_button,
};
use crate::video_preview::VideoPreviewPlayer;
use crate::wallpaper::MonitorInfo;

pub struct DetailModalState {
    pub item: WallpaperItem,
    pub index_in_grid: usize,
    pub total_in_grid: usize,
    pub is_installed: bool,
    pub local_path: String,
    pub detail_loading: bool,
    pub zoom: f32,
    pub pan: Vec2,
    pub selected_monitor: String,
    pub video_player: Option<VideoPreviewPlayer>,
    pub video_tex: Option<TextureHandle>,
    pub video_source_started: String,
    pub download_progress: Option<(u64, u64)>,
}

impl DetailModalState {
    pub fn new(
        item: WallpaperItem,
        index_in_grid: usize,
        total_in_grid: usize,
        is_installed: bool,
        local_path: String,
        default_monitor: String,
    ) -> Self {
        Self {
            item,
            index_in_grid,
            total_in_grid,
            is_installed,
            local_path,
            detail_loading: false,
            zoom: 1.0,
            pan: Vec2::ZERO,
            selected_monitor: default_monitor,
            video_player: None,
            video_tex: None,
            video_source_started: String::new(),
            download_progress: None,
        }
    }

    pub fn stop_video(&mut self) {
        if let Some(mut vp) = self.video_player.take() {
            vp.stop();
        }
        self.video_tex = None;
        self.video_source_started.clear();
    }
}

pub enum DetailAction {
    None,
    Close,
    Prev,
    Next,
    Download,
    SaveAs,
    SetWallpaper(String),
    CopyImage,
    OpenFolder,
    OpenWeb(String),
    OpenMpv(String),
    Uninstall,
    CancelDownload,
    FilterByTag(String),
    FilterByColor(String),
    StartVideoPreview(String),
}

pub fn render_detail_modal(
    ctx: &egui::Context,
    pal: &ThemePalette,
    lang: Lang,
    state: &mut DetailModalState,
    monitors: &[MonitorInfo],
    loader: &mut ImageLoader,
) -> DetailAction {
    let mut action = DetailAction::None;
    let screen = ctx.screen_rect();

    let win_w = (screen.width() * 0.90).clamp(740.0, 1220.0);
    let win_h = (screen.height() * 0.88).clamp(520.0, 860.0);

    let modal_resp = egui::Modal::new(egui::Id::new("komorebi_detail_modal"))
        .backdrop_color(Color32::from_black_alpha(110))
        .frame(
            egui::Frame::new()
                .fill(pal.bg_surface)
                .stroke(Stroke::new(1.5_f32, pal.accent))
                .corner_radius(CornerRadius::same(pal.radius_card()))
                .inner_margin(egui::Margin::same(16)),
        )
        .show(ctx, |ui| {
            ui.set_min_size(Vec2::new(win_w, win_h));
            ui.set_max_size(Vec2::new(win_w, win_h));
            // Header bar
            ui.horizontal(|ui| {
                ui.label(
                    RichText::new(state.item.display_title())
                        .color(pal.text_primary)
                        .strong()
                        .size(16.0),
                );
                if state.detail_loading {
                    ui.spinner();
                }

                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if secondary_button(ui, pal, "✕").clicked() {
                        action = DetailAction::Close;
                    }
                    if !state.item.url.is_empty()
                        && secondary_button(ui, pal, &format!("↗ {}", tr(lang, "detail_open_web")))
                            .clicked()
                    {
                        action = DetailAction::OpenWeb(state.item.url.clone());
                    }
                    if ui
                        .add_enabled(
                            state.index_in_grid + 1 < state.total_in_grid,
                            egui::Button::new("Next >")
                                .fill(pal.bg_input)
                                .corner_radius(CornerRadius::same(pal.radius_btn())),
                        )
                        .clicked()
                    {
                        action = DetailAction::Next;
                    }
                    if ui
                        .add_enabled(
                            state.index_in_grid > 0,
                            egui::Button::new("< Prev")
                                .fill(pal.bg_input)
                                .corner_radius(CornerRadius::same(pal.radius_btn())),
                        )
                        .clicked()
                    {
                        action = DetailAction::Prev;
                    }
                });
            });

            ui.separator();
            ui.add_space(6.0);

            let body_h = (win_h - 78.0).max(320.0);
            let left_w = ((win_w - 32.0) * 0.64).max(360.0);
            let right_w = ((win_w - 32.0) - left_w - 14.0).max(240.0);

            ui.horizontal_top(|ui| {
                // LEFT: Visual / Live Video Preview Pane
                ui.vertical(|ui| {
                    ui.set_width(left_w);
                    ui.set_min_height(body_h);

                    let preview_h = if state.item.is_animated {
                        body_h - 42.0
                    } else {
                        body_h - 28.0
                    };
                    let (canvas_rect, resp) =
                        ui.allocate_exact_size(Vec2::new(left_w, preview_h), Sense::click_and_drag());
                    let r = CornerRadius::same(pal.radius_card());
                    ui.painter().rect_filled(canvas_rect, r, pal.bg_base);
                    ui.painter().rect_stroke(
                        canvas_rect,
                        r,
                        Stroke::new(1.0_f32, pal.border_subtle),
                        StrokeKind::Inside,
                    );

                    // Video frame polling if active
                    if state.item.is_animated {
                        let vid_src = if !state.local_path.is_empty() {
                            state.local_path.clone()
                        } else if !state.item.preview_video_url.is_empty() {
                            state.item.preview_video_url.clone()
                        } else {
                            state.item.path.clone()
                        };

                        if !vid_src.is_empty()
                            && state.video_source_started != vid_src
                            && matches!(action, DetailAction::None)
                        {
                            action = DetailAction::StartVideoPreview(vid_src);
                        }

                        if let Some(vp) = &state.video_player {
                            if let Some(img) = vp.try_next_frame() {
                                if let Some(tex) = &mut state.video_tex {
                                    tex.set(img, TextureOptions::LINEAR);
                                } else {
                                    state.video_tex = Some(ctx.load_texture(
                                        format!("vid_live_{}", state.item.id),
                                        img,
                                        TextureOptions::LINEAR,
                                    ));
                                }
                            }
                        }
                    }

                    // Pick texture to draw: active video frame -> full preview image -> thumbnail
                    let active_video_tex = state.video_tex.as_ref();
                    let full_src = if !state.local_path.is_empty() && !state.item.is_animated {
                        state.local_path.clone()
                    } else {
                        state.item.preview_image_url().to_string()
                    };
                    let full_key = format!("full:{}:{}", state.item.id, full_src);
                    let thumb_key = format!("thumb:{}:{}", state.item.id, state.item.thumb_url());

                    let static_tex_opt: Option<&TextureHandle> = if active_video_tex.is_none() {
                        if !state.item.is_animated && !full_src.is_empty() && !loader.is_failed(&full_key) {
                            if loader.get_texture(&full_key).is_none() {
                                loader.request_image(&full_key, &full_src, false, false, 1920, ctx);
                            }
                        }
                        if let Some(t) = loader.get_texture(&full_key) {
                            Some(t)
                        } else {
                            loader.get_texture(&thumb_key)
                        }
                    } else {
                        None
                    };

                    if let Some(tex) = active_video_tex.or(static_tex_opt) {
                        // Zoom & pan interactions for static images
                        if active_video_tex.is_none() {
                            if resp.hovered() {
                                let scroll = ui.input(|i| i.raw_scroll_delta.y);
                                if scroll.abs() > 0.1 {
                                    let factor = if scroll > 0.0 { 1.12 } else { 0.89 };
                                    state.zoom = (state.zoom * factor).clamp(1.0, 5.0);
                                    if (state.zoom - 1.0).abs() < 0.03 {
                                        state.zoom = 1.0;
                                        state.pan = Vec2::ZERO;
                                    }
                                }
                            }
                            if resp.dragged() && state.zoom > 1.01 {
                                state.pan += resp.drag_delta();
                            }
                            if resp.double_clicked() {
                                state.zoom = 1.0;
                                state.pan = Vec2::ZERO;
                            }
                        }

                        let fitted = compute_contain_size(
                            tex.size_vec2(),
                            canvas_rect.size() - Vec2::splat(16.0),
                            state.zoom,
                        );
                        let img_rect = Rect::from_center_size(canvas_rect.center() + state.pan, fitted);
                        let clipped = ui.painter().with_clip_rect(canvas_rect);
                        let mut mesh = egui::Mesh::with_texture(tex.id());
                        mesh.add_rect_with_uv(
                            img_rect,
                            Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)),
                            Color32::WHITE,
                        );
                        clipped.add(mesh);
                    } else {
                        ui.painter().text(
                            canvas_rect.center(),
                            Align2::CENTER_CENTER,
                            if state.item.is_animated {
                                "Buffering Live Video Preview..."
                            } else {
                                "Loading Full Resolution..."
                            },
                            FontId::proportional(13.0),
                            pal.text_muted,
                        );
                    }

                    // Bottom bar under preview (video controls or zoom hint)
                    ui.add_space(6.0);
                    ui.horizontal(|ui| {
                        if state.item.is_animated {
                            let is_paused = state
                                .video_player
                                .as_ref()
                                .map(|v| v.is_paused())
                                .unwrap_or(false);
                            let play_lbl = if is_paused {
                                format!("▶ {}", tr(lang, "media_play"))
                            } else {
                                format!("⏸ {}", tr(lang, "media_pause"))
                            };
                            if secondary_button(ui, pal, &play_lbl).clicked() {
                                if let Some(vp) = &state.video_player {
                                    vp.toggle_paused();
                                }
                            }
                            let mpv_src = if !state.local_path.is_empty() {
                                state.local_path.clone()
                            } else if !state.item.preview_video_url.is_empty() {
                                state.item.preview_video_url.clone()
                            } else {
                                state.item.path.clone()
                            };
                            if !mpv_src.is_empty()
                                && secondary_button(ui, pal, tr(lang, "open_mpv")).clicked()
                            {
                                action = DetailAction::OpenMpv(mpv_src);
                            }
                            if let Some(vp) = &state.video_player {
                                let st = vp.status();
                                let col = if st.starts_with("Preview error") || st.starts_with("ffmpeg") {
                                    Color32::from_rgb(248, 113, 113)
                                } else {
                                    pal.accent
                                };
                                ui.label(RichText::new(st).color(col).size(11.0));
                            }
                        } else {
                            ui.label(
                                RichText::new(format!(
                                    "Zoom: {:.0}%  (Scroll to zoom, double-click to reset)",
                                    state.zoom * 100.0
                                ))
                                .color(pal.text_muted)
                                .size(11.0),
                            );
                        }
                    });
                });

                ui.add_space(12.0);

                // RIGHT: Metadata, Palette, Tags, Monitor, Actions
                ui.vertical(|ui| {
                    ui.set_width(right_w);
                    ui.set_max_height(body_h);

                    egui::ScrollArea::vertical()
                        .id_salt("detail_meta_scroll")
                        .show(ui, |ui| {
                            // Key/Value Metadata Grid
                            egui::Frame::new()
                                .fill(pal.bg_subsurface)
                                .stroke(Stroke::new(1.0_f32, pal.border_subtle))
                                .corner_radius(CornerRadius::same(pal.radius_card()))
                                .inner_margin(egui::Margin::same(10))
                                .show(ui, |ui| {
                                    egui::Grid::new("detail_meta_grid")
                                        .num_columns(2)
                                        .spacing([12.0, 5.0])
                                        .show(ui, |ui| {
                                            meta_row(ui, pal, tr(lang, "meta_source"), &state.item.source.to_uppercase());
                                            if !state.item.origin_url.is_empty() {
                                                meta_row(ui, pal, "Origin", &state.item.origin_url);
                                            }
                                            if !state.item.resolution.is_empty() {
                                                meta_row(ui, pal, tr(lang, "meta_resolution"), &state.item.resolution);
                                            }
                                            if !state.item.ratio.is_empty() {
                                                meta_row(ui, pal, tr(lang, "meta_ratio"), &state.item.ratio);
                                            }
                                            if state.item.file_size > 0 {
                                                meta_row(ui, pal, tr(lang, "meta_file_size"), &state.item.human_file_size());
                                            }
                                            if !state.item.file_type.is_empty() {
                                                meta_row(ui, pal, tr(lang, "meta_format"), &state.item.file_type);
                                            }
                                            if !state.item.category.is_empty() {
                                                meta_row(ui, pal, tr(lang, "meta_category"), &state.item.category);
                                            }
                                            if !state.item.uploader.is_empty() {
                                                meta_row(ui, pal, "Artist / Author", &state.item.uploader);
                                            }
                                            if state.item.views > 0 {
                                                meta_row(ui, pal, tr(lang, "meta_views"), &state.item.views.to_string());
                                            }
                                            if state.item.favorites > 0 {
                                                meta_row(ui, pal, tr(lang, "meta_favorites"), &state.item.favorites.to_string());
                                            }
                                        });
                                });

                            // Color Palette swatches
                            if !state.item.colors.is_empty() {
                                ui.add_space(10.0);
                                ui.label(
                                    RichText::new(tr(lang, "meta_palette"))
                                        .color(pal.text_secondary)
                                        .strong()
                                        .size(12.0),
                                );
                                ui.add_space(4.0);
                                ui.horizontal_wrapped(|ui| {
                                    ui.spacing_mut().item_spacing = Vec2::splat(6.0);
                                    for hex in &state.item.colors {
                                        let c = parse_hex(hex);
                                        let (sw_rect, sw_resp) =
                                            ui.allocate_exact_size(Vec2::new(26.0, 22.0), Sense::click());
                                        let r = CornerRadius::same(4);
                                        ui.painter().rect_filled(sw_rect, r, c);
                                        ui.painter().rect_stroke(
                                            sw_rect,
                                            r,
                                            Stroke::new(
                                                if sw_resp.hovered() { 1.5_f32 } else { 1.0_f32 },
                                                if sw_resp.hovered() { pal.accent } else { pal.border },
                                            ),
                                            StrokeKind::Inside,
                                        );
                                        if sw_resp.on_hover_text(hex).clicked() {
                                            action = DetailAction::FilterByColor(
                                                hex.trim_start_matches('#').to_string(),
                                            );
                                        }
                                    }
                                });
                            }

                            // Clickable Tags
                            if !state.item.tags.is_empty() {
                                ui.add_space(10.0);
                                ui.label(
                                    RichText::new(tr(lang, "tags_title"))
                                        .color(pal.text_secondary)
                                        .strong()
                                        .size(12.0),
                                );
                                ui.add_space(4.0);
                                ui.horizontal_wrapped(|ui| {
                                    ui.spacing_mut().item_spacing = Vec2::splat(5.0);
                                    for tag in &state.item.tags {
                                        let btn = egui::Button::new(
                                            RichText::new(tag).color(pal.text_primary).size(11.0),
                                        )
                                        .fill(pal.bg_input)
                                        .stroke(Stroke::new(1.0_f32, pal.border_subtle))
                                        .corner_radius(CornerRadius::same(pal.radius_pill()));
                                        if ui.add(btn).clicked() {
                                            action = DetailAction::FilterByTag(tag.clone());
                                        }
                                    }
                                });
                            }

                            ui.add_space(12.0);
                            ui.separator();
                            ui.add_space(8.0);

                            // Monitor Selector
                            ui.horizontal(|ui| {
                                ui.label(
                                    RichText::new(tr(lang, "detail_monitor_label"))
                                        .color(pal.text_muted)
                                        .size(12.0),
                                );
                                let cur_mon_label = monitors
                                    .iter()
                                    .find(|m| m.id == state.selected_monitor)
                                    .map(|m| m.label.as_str())
                                    .unwrap_or(tr(lang, "monitor_all"));
                                egui::ComboBox::from_id_salt("detail_mon_combo")
                                    .selected_text(cur_mon_label)
                                    .width((right_w - 82.0).max(120.0))
                                    .show_ui(ui, |ui| {
                                        for m in monitors {
                                            ui.selectable_value(
                                                &mut state.selected_monitor,
                                                m.id.clone(),
                                                &m.label,
                                            );
                                        }
                                    });
                            });

                            ui.add_space(8.0);

                            // Download progress or Primary Action Buttons
                            if let Some((done, total)) = state.download_progress {
                                let frac = if total > 0 {
                                    (done as f32 / total as f32).clamp(0.0, 1.0)
                                } else {
                                    0.0
                                };
                                let label = if total > 0 {
                                    format!("{} / {}", format_bytes(done), format_bytes(total))
                                } else {
                                    format!("Downloading... {}", format_bytes(done))
                                };
                                ui.add(egui::ProgressBar::new(frac).text(label).animate(true));
                                ui.add_space(6.0);
                                if secondary_button(ui, pal, tr(lang, "cancel")).clicked() {
                                    action = DetailAction::CancelDownload;
                                }
                            } else {
                                // Set as Wallpaper (downloads automatically if not installed)
                                if ui
                                    .add_sized(
                                        [right_w - 8.0, 34.0],
                                        egui::Button::new(
                                            RichText::new(tr(lang, "set_wall_now_button"))
                                                .color(pal.accent_text)
                                                .strong()
                                                .size(13.0),
                                        )
                                        .fill(pal.accent)
                                        .stroke(Stroke::new(1.0_f32, pal.accent_hover))
                                        .corner_radius(CornerRadius::same(pal.radius_btn())),
                                    )
                                    .clicked()
                                {
                                    action =
                                        DetailAction::SetWallpaper(state.selected_monitor.clone());
                                }

                                ui.add_space(6.0);
                                ui.horizontal_wrapped(|ui| {
                                    ui.spacing_mut().item_spacing = Vec2::splat(6.0);
                                    if !state.is_installed
                                        && accent_button(ui, pal, tr(lang, "download_button")).clicked()
                                    {
                                        action = DetailAction::Download;
                                    }
                                    if !state.item.is_animated
                                        && secondary_button(ui, pal, tr(lang, "detail_copy_btn")).clicked()
                                    {
                                        action = DetailAction::CopyImage;
                                    }
                                    if secondary_button(ui, pal, tr(lang, "save_as_button")).clicked()
                                    {
                                        action = DetailAction::SaveAs;
                                    }
                                });

                                if state.is_installed {
                                    ui.add_space(6.0);
                                    ui.horizontal(|ui| {
                                        if secondary_button(ui, pal, tr(lang, "open_folder_button"))
                                            .clicked()
                                        {
                                            action = DetailAction::OpenFolder;
                                        }
                                        if danger_button(
                                            ui,
                                            pal,
                                            tr(lang, "uninstall_button_full"),
                                        )
                                        .clicked()
                                        {
                                            action = DetailAction::Uninstall;
                                        }
                                    });
                                }
                            }
                        });
                });
            });
        });

    if matches!(action, DetailAction::None) && modal_resp.should_close() {
        action = DetailAction::Close;
    }

    action
}

fn meta_row(ui: &mut Ui, pal: &ThemePalette, label: &str, value: &str) {
    ui.label(RichText::new(label).color(pal.text_muted).size(11.5));
    ui.label(
        RichText::new(value)
            .color(pal.text_primary)
            .size(11.5),
    );
    ui.end_row();
}
