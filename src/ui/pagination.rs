use egui::{CornerRadius, RichText, Stroke, Ui, Vec2};

use crate::theme::{with_alpha, ThemePalette};

pub struct PaginationState {
    pub jump_open: bool,
    pub jump_input: String,
    pub capsule_width: f32,
}

impl Default for PaginationState {
    fn default() -> Self {
        Self {
            jump_open: false,
            jump_input: String::new(),
            capsule_width: 280.0,
        }
    }
}

pub enum PageAction {
    None,
    GoToPage(usize),
}

#[allow(clippy::too_many_arguments)]
pub fn render_pagination(
    ui: &mut Ui,
    pal: &ThemePalette,
    state: &mut PaginationState,
    content_w: f32,
    current_page: usize,
    last_page: usize,
    total_items: usize,
    has_next_hint: Option<bool>,
) -> PageAction {
    let mut action = PageAction::None;
    let can_prev = current_page > 1;
    let can_next = has_next_hint.unwrap_or(current_page < last_page);

    if current_page <= 1 && last_page <= 1 && has_next_hint == Some(false) {
        return PageAction::None;
    }

    ui.add_space(6.0);
    ui.horizontal(|ui| {
        let pad_left = ((content_w - state.capsule_width) * 0.5).max(0.0);
        ui.add_space(pad_left);

        let frame_resp = egui::Frame::new()
            .fill(pal.bg_capsule)
            .stroke(Stroke::new(1.0_f32, with_alpha(pal.accent, 145)))
            .corner_radius(CornerRadius::same(pal.radius_pill()))
            .inner_margin(egui::Margin::symmetric(10, 5))
            .show(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.spacing_mut().item_spacing.x = 5.0;

                    let nav_btn = |ui: &mut Ui, txt: &str, enabled: bool| -> bool {
                        let btn = egui::Button::new(
                            RichText::new(txt)
                                .color(if enabled {
                                    pal.text_primary
                                } else {
                                    pal.text_muted
                                })
                                .size(12.0),
                        )
                        .fill(pal.bg_input)
                        .stroke(Stroke::new(1.0_f32, pal.border_subtle))
                        .corner_radius(CornerRadius::same(pal.radius_btn()))
                        .min_size(Vec2::new(26.0, 24.0));
                        ui.add_enabled(enabled, btn).clicked()
                    };

                    if nav_btn(ui, "«", can_prev) {
                        state.jump_open = false;
                        action = PageAction::GoToPage(1);
                    }
                    if nav_btn(ui, "‹", can_prev) {
                        state.jump_open = false;
                        action = PageAction::GoToPage(current_page.saturating_sub(1).max(1));
                    }

                    let page_text = if has_next_hint.is_some() {
                        format!("Page {current_page}")
                    } else if total_items > 0 {
                        format!("Page {current_page} / {} • {total_items}", last_page.max(1))
                    } else {
                        format!("Page {current_page} / {}", last_page.max(1))
                    };
                    let pill_btn = egui::Button::new(
                        RichText::new(page_text)
                            .color(pal.accent_text)
                            .strong()
                            .size(11.5),
                    )
                    .fill(pal.accent)
                    .stroke(Stroke::new(1.0_f32, pal.accent_hover))
                    .corner_radius(CornerRadius::same(pal.radius_btn()))
                    .min_size(Vec2::new(86.0, 24.0));

                    if ui.add(pill_btn).clicked() {
                        state.jump_open = !state.jump_open;
                        state.jump_input = current_page.to_string();
                    }

                    if state.jump_open {
                        let resp = ui.add_sized(
                            [48.0, 24.0],
                            egui::TextEdit::singleline(&mut state.jump_input).hint_text("#"),
                        );
                        let enter =
                            resp.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter));
                        let go_btn = egui::Button::new(
                            RichText::new("Go").color(pal.accent_text).size(11.5),
                        )
                        .fill(pal.accent)
                        .corner_radius(CornerRadius::same(pal.radius_btn()))
                        .min_size(Vec2::new(32.0, 24.0));
                        if enter || ui.add(go_btn).clicked() {
                            if let Ok(p) = state.jump_input.trim().parse::<usize>() {
                                let clamped = if has_next_hint.is_some() {
                                    p.max(1)
                                } else {
                                    p.clamp(1, last_page.max(1))
                                };
                                action = PageAction::GoToPage(clamped);
                            }
                            state.jump_open = false;
                        }
                    }

                    if nav_btn(ui, "›", can_next) {
                        state.jump_open = false;
                        action = PageAction::GoToPage(current_page + 1);
                    }
                    if has_next_hint.is_none() && nav_btn(ui, "»", can_next) {
                        state.jump_open = false;
                        action = PageAction::GoToPage(last_page.max(1));
                    }
                });
            });

        state.capsule_width = frame_resp.response.rect.width().max(180.0);
    });

    action
}
