use egui::{Align2, Color32, CornerRadius, FontId, Pos2, Rect, Stroke, StrokeKind, Vec2};

use crate::theme::{with_alpha, ThemePalette};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ToastKind {
    Info,
    Success,
    Warning,
    Error,
}

#[derive(Debug, Clone)]
struct ToastEntry {
    message: String,
    kind: ToastKind,
    expires_at: f64,
    duration: f64,
}

#[derive(Default)]
pub struct ToastManager {
    entries: Vec<ToastEntry>,
}

impl ToastManager {
    pub fn push(&mut self, ctx: &egui::Context, message: impl Into<String>, kind: ToastKind, duration_secs: f64) {
        let now = ctx.input(|i| i.time);
        self.entries.push(ToastEntry {
            message: message.into(),
            kind,
            expires_at: now + duration_secs.max(1.5),
            duration: duration_secs.max(1.5),
        });
        if self.entries.len() > 4 {
            self.entries.remove(0);
        }
        ctx.request_repaint();
    }

    pub fn info(&mut self, ctx: &egui::Context, msg: impl Into<String>) {
        self.push(ctx, msg, ToastKind::Info, 3.2);
    }

    pub fn success(&mut self, ctx: &egui::Context, msg: impl Into<String>) {
        self.push(ctx, msg, ToastKind::Success, 3.5);
    }

    pub fn warning(&mut self, ctx: &egui::Context, msg: impl Into<String>) {
        self.push(ctx, msg, ToastKind::Warning, 4.5);
    }

    pub fn error(&mut self, ctx: &egui::Context, msg: impl Into<String>) {
        self.push(ctx, msg, ToastKind::Error, 5.0);
    }

    pub fn render(&mut self, ctx: &egui::Context, pal: &ThemePalette) {
        let now = ctx.input(|i| i.time);
        self.entries.retain(|e| e.expires_at > now);
        if self.entries.is_empty() {
            return;
        }

        let screen = ctx.screen_rect();
        let layer_id = egui::LayerId::new(egui::Order::Tooltip, egui::Id::new("komorebi_toasts"));
        let painter = ctx.layer_painter(layer_id);

        let mut y_bottom = screen.bottom() - 22.0;
        for entry in self.entries.iter().rev() {
            let remaining = (entry.expires_at - now) as f32;
            let elapsed = (entry.duration - remaining as f64) as f32;
            let fade_in = (elapsed / 0.18).clamp(0.0, 1.0);
            let fade_out = (remaining / 0.35).clamp(0.0, 1.0);
            let alpha_mul = fade_in.min(fade_out);

            let (accent_col, prefix) = match entry.kind {
                ToastKind::Success => (Color32::from_rgb(74, 222, 128), "[OK]"),
                ToastKind::Warning => (Color32::from_rgb(250, 204, 21), "[!]"),
                ToastKind::Error => (Color32::from_rgb(248, 113, 113), "[ERR]"),
                ToastKind::Info => (pal.accent, "[i]"),
            };

            let text_galley = painter.layout(
                format!("{prefix} {}", entry.message),
                FontId::proportional(12.5),
                with_alpha(pal.text_primary, (255.0 * alpha_mul) as u8),
                360.0,
            );

            let size = Vec2::new(text_galley.size().x + 28.0, text_galley.size().y + 18.0);
            let rect = Rect::from_min_size(
                Pos2::new(screen.right() - size.x - 24.0, y_bottom - size.y),
                size,
            );
            let r = CornerRadius::same(pal.radius_card());

            painter.rect_filled(
                rect,
                r,
                with_alpha(pal.bg_surface, (242.0 * alpha_mul) as u8),
            );
            painter.rect_stroke(
                rect,
                r,
                Stroke::new(1.2_f32, with_alpha(accent_col, (200.0 * alpha_mul) as u8)),
                StrokeKind::Inside,
            );
            // Left accent stripe
            let stripe = Rect::from_min_size(rect.min, Vec2::new(3.5, rect.height()));
            painter.rect_filled(
                stripe,
                CornerRadius::same(2),
                with_alpha(accent_col, (240.0 * alpha_mul) as u8),
            );

            painter.galley(
                Pos2::new(rect.left() + 14.0, rect.top() + 9.0),
                text_galley,
                with_alpha(pal.text_primary, (255.0 * alpha_mul) as u8),
            );

            y_bottom = rect.top() - 8.0;
        }

        let _ = Align2::RIGHT_BOTTOM;
        ctx.request_repaint_after(std::time::Duration::from_millis(33));
    }
}
