use egui::{
    Align2, Color32, CornerRadius, FontId, Pos2, RichText, Sense, Stroke, StrokeKind, Vec2,
};

use crate::cache::ImageLoader;
use crate::i18n::{tr, Lang};
use crate::models::PfpItem;
use crate::theme::ThemePalette;
use crate::ui::{
    accent_button, compute_cover_uv, draw_badge, secondary_button, select_gif_frame,
};

pub struct PfpModalState {
    pub item: PfpItem,
    pub busy: bool,
}

pub enum PfpAction {
    None,
    Close,
    SetSystemAvatar,
    CopyImage,
    Download,
    OpenWeb(String),
}

pub fn render_pfp_modal(
    ctx: &egui::Context,
    pal: &ThemePalette,
    lang: Lang,
    state: &PfpModalState,
    loader: &mut ImageLoader,
) -> PfpAction {
    let mut action = PfpAction::None;
    let modal_resp = egui::Modal::new(egui::Id::new("komorebi_pfp_modal"))
        .backdrop_color(Color32::from_black_alpha(110))
        .frame(
            egui::Frame::new()
                .fill(pal.bg_surface)
                .stroke(Stroke::new(1.5_f32, pal.accent))
                .corner_radius(CornerRadius::same(pal.radius_card()))
                .inner_margin(egui::Margin::same(16)),
        )
        .show(ctx, |ui| {
            ui.set_min_size(Vec2::new(430.0, 560.0));
            ui.set_max_size(Vec2::new(430.0, 560.0));
            ui.horizontal(|ui| {
                ui.label(
                    RichText::new(&state.item.title)
                        .color(pal.text_primary)
                        .strong()
                        .size(16.0),
                );
                if state.busy {
                    ui.spinner();
                }
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if secondary_button(ui, pal, "✕").clicked() {
                        action = PfpAction::Close;
                    }
                    if secondary_button(ui, pal, "↗ pfps.gg").clicked() {
                        action = PfpAction::OpenWeb(state.item.page_url.clone());
                    }
                });
            });

            ui.separator();
            ui.add_space(10.0);

            ui.vertical_centered(|ui| {
                let (img_rect, _) = ui.allocate_exact_size(Vec2::splat(320.0), Sense::hover());
                let r = CornerRadius::same(pal.radius_card());
                ui.painter().rect_filled(img_rect, r, pal.bg_base);

                let key = format!("pfp_modal:{}", state.item.id);
                if state.item.is_animated() {
                    if let Some(frames) = loader.get_gif(&key) {
                        if let Some(tex) = select_gif_frame(ctx, frames) {
                            let uv = compute_cover_uv(tex.size_vec2(), img_rect.size());
                            egui::Image::new(tex).uv(uv).corner_radius(r).paint_at(ui, img_rect);
                        }
                    } else if !loader.is_failed(&key) {
                        loader.request_image(&key, &state.item.image_url, false, true, 512, ctx);
                        ui.painter().text(
                            img_rect.center(),
                            Align2::CENTER_CENTER,
                            "Loading GIF...",
                            FontId::proportional(13.0),
                            pal.text_muted,
                        );
                    }
                } else if let Some(tex) = loader.get_texture(&key) {
                    let uv = compute_cover_uv(tex.size_vec2(), img_rect.size());
                    egui::Image::new(tex).uv(uv).corner_radius(r).paint_at(ui, img_rect);
                } else if !loader.is_failed(&key) {
                    loader.request_image(&key, &state.item.image_url, false, false, 512, ctx);
                    ui.painter().text(
                        img_rect.center(),
                        Align2::CENTER_CENTER,
                        "Loading...",
                        FontId::proportional(13.0),
                        pal.text_muted,
                    );
                }

                draw_badge(
                    ui.painter(),
                    Pos2::new(img_rect.left() + 10.0, img_rect.top() + 10.0),
                    &state.item.format.to_uppercase(),
                    if state.item.is_animated() {
                        pal.accent
                    } else {
                        Color32::from_black_alpha(180)
                    },
                    if state.item.is_animated() {
                        pal.accent_text
                    } else {
                        Color32::WHITE
                    },
                    None,
                    4,
                );

                ui.painter()
                    .rect_stroke(img_rect, r, Stroke::new(1.0_f32, pal.border), StrokeKind::Inside);

                ui.add_space(10.0);
                ui.label(
                    RichText::new(format!(
                        "{} {}  •  {}",
                        PfpItem::format_download_count(&state.item.downloads),
                        tr(lang, "pfp_downloads_suffix"),
                        state.item.category
                    ))
                    .color(pal.text_muted)
                    .size(12.0),
                );
                ui.add_space(14.0);

                if ui
                    .add_enabled(
                        !state.busy,
                        egui::Button::new(
                            RichText::new(tr(lang, "pfp_btn_set_avatar"))
                                .color(pal.accent_text)
                                .strong()
                                .size(13.0),
                        )
                        .fill(pal.accent)
                        .corner_radius(CornerRadius::same(pal.radius_btn()))
                        .min_size(Vec2::new(340.0, 36.0)),
                    )
                    .clicked()
                {
                    action = PfpAction::SetSystemAvatar;
                }

                ui.add_space(8.0);
                ui.horizontal(|ui| {
                    ui.add_space(36.0);
                    if !state.busy && secondary_button(ui, pal, tr(lang, "pfp_btn_copy")).clicked() {
                        action = PfpAction::CopyImage;
                    }
                    if !state.busy && accent_button(ui, pal, tr(lang, "pfp_btn_download")).clicked() {
                        action = PfpAction::Download;
                    }
                });
            });
        });

    if matches!(action, PfpAction::None) && modal_resp.should_close() {
        action = PfpAction::Close;
    }

    action
}
