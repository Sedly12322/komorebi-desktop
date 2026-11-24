pub mod ambient;
pub mod detail_modal;
pub mod filters;
pub mod grid;
pub mod pagination;
pub mod pfp_modal;
pub mod settings_modal;
pub mod sidebar;
pub mod toast;

use egui::{
    Align2, Color32, CornerRadius, FontId, Pos2, Rect, Response, RichText, Sense, Stroke,
    StrokeKind, TextureHandle, Ui, Vec2,
};

use crate::theme::{with_alpha, ThemePalette};

/// Compute UV coordinates for cover-crop rendering without distortion.
pub fn compute_cover_uv(tex_size: Vec2, target_size: Vec2) -> Rect {
    if tex_size.x <= 0.0 || tex_size.y <= 0.0 || target_size.x <= 0.0 || target_size.y <= 0.0 {
        return Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0));
    }
    let tex_aspect = tex_size.x / tex_size.y;
    let dst_aspect = target_size.x / target_size.y;

    if tex_aspect > dst_aspect {
        // Source is wider than destination -> crop left/right
        let visible_w = dst_aspect / tex_aspect;
        let pad = (1.0 - visible_w) * 0.5;
        Rect::from_min_max(Pos2::new(pad, 0.0), Pos2::new(1.0 - pad, 1.0))
    } else {
        // Source is taller than destination -> crop top/bottom
        let visible_h = tex_aspect / dst_aspect;
        let pad = (1.0 - visible_h) * 0.5;
        Rect::from_min_max(Pos2::new(0.0, pad), Pos2::new(1.0, 1.0 - pad))
    }
}

/// Compute aspect-preserving fit size inside available bounds.
pub fn compute_contain_size(tex_size: Vec2, avail: Vec2, zoom: f32) -> Vec2 {
    if tex_size.x <= 0.0 || tex_size.y <= 0.0 || avail.x <= 0.0 || avail.y <= 0.0 {
        return avail * zoom;
    }
    let scale = (avail.x / tex_size.x).min(avail.y / tex_size.y).max(0.05);
    Vec2::new(tex_size.x * scale * zoom, tex_size.y * scale * zoom)
}

/// Select the current GIF frame and schedule a repaint matching its frame delay.
pub fn select_gif_frame<'a>(
    ctx: &egui::Context,
    frames: &'a [(TextureHandle, f32)],
) -> Option<&'a TextureHandle> {
    if frames.is_empty() {
        return None;
    }
    if frames.len() == 1 {
        return Some(&frames[0].0);
    }
    let total_dur: f32 = frames.iter().map(|(_, d)| (*d).max(0.02)).sum();
    if total_dur <= 0.0 {
        return Some(&frames[0].0);
    }
    let now = (ctx.input(|i| i.time) as f32) % total_dur;
    let mut acc = 0.0;
    for (tex, delay) in frames {
        let d = (*delay).max(0.02);
        acc += d;
        if now <= acc {
            if ctx.input(|i| i.focused) {
                ctx.request_repaint_after(std::time::Duration::from_secs_f32((acc - now).max(0.02)));
            }
            return Some(tex);
        }
    }
    Some(&frames[0].0)
}

pub fn accent_button(ui: &mut Ui, pal: &ThemePalette, text: &str) -> Response {
    let btn = egui::Button::new(
        RichText::new(text)
            .color(pal.accent_text)
            .strong()
            .size(12.5),
    )
    .fill(pal.accent)
    .stroke(Stroke::new(1.0_f32, pal.accent_hover))
    .corner_radius(CornerRadius::same(pal.radius_btn()));
    ui.add(btn)
}

pub fn secondary_button(ui: &mut Ui, pal: &ThemePalette, text: &str) -> Response {
    let btn = egui::Button::new(RichText::new(text).color(pal.text_primary).size(12.5))
        .fill(pal.bg_input)
        .stroke(Stroke::new(1.0_f32, pal.border))
        .corner_radius(CornerRadius::same(pal.radius_btn()));
    ui.add(btn)
}

pub fn danger_button(ui: &mut Ui, pal: &ThemePalette, text: &str) -> Response {
    let red = Color32::from_rgb(220, 68, 78);
    let btn = egui::Button::new(RichText::new(text).color(Color32::WHITE).strong().size(12.5))
        .fill(with_alpha(red, 210))
        .stroke(Stroke::new(1.0_f32, red))
        .corner_radius(CornerRadius::same(pal.radius_btn()));
    ui.add(btn)
}

pub fn toggle_pill(ui: &mut Ui, pal: &ThemePalette, text: &str, active: bool) -> Response {
    let (fill, stroke_col, text_col) = if active {
        (pal.accent_surface, pal.accent, pal.text_primary)
    } else {
        (pal.bg_input, pal.border_subtle, pal.text_secondary)
    };
    let btn = egui::Button::new(RichText::new(text).color(text_col).size(12.0))
        .fill(fill)
        .stroke(Stroke::new(1.0_f32, stroke_col))
        .corner_radius(CornerRadius::same(pal.radius_pill()));
    ui.add(btn)
}

pub fn draw_badge(
    painter: &egui::Painter,
    anchor_tl: Pos2,
    text: &str,
    bg: Color32,
    fg: Color32,
    border: Option<Color32>,
    radius: u8,
) -> Rect {
    let font = FontId::proportional(10.5);
    let galley = painter.layout_no_wrap(text.to_string(), font, fg);
    let size = galley.size() + Vec2::new(10.0, 4.0);
    let rect = Rect::from_min_size(anchor_tl, size);
    painter.rect_filled(rect, CornerRadius::same(radius), bg);
    if let Some(bcol) = border {
        painter.rect_stroke(
            rect,
            CornerRadius::same(radius),
            Stroke::new(1.0_f32, bcol),
            StrokeKind::Inside,
        );
    }
    painter.galley(
        Pos2::new(rect.left() + 5.0, rect.top() + 2.0),
        galley,
        fg,
    );
    rect
}

pub fn draw_centered_badge(
    ui: &mut Ui,
    rect: Rect,
    text: &str,
    bg: Color32,
    fg: Color32,
    radius: u8,
) {
    let painter = ui.painter();
    painter.rect_filled(rect, CornerRadius::same(radius), bg);
    painter.text(
        rect.center(),
        Align2::CENTER_CENTER,
        text,
        FontId::proportional(11.0),
        fg,
    );
}

pub fn clickable_icon_circle(
    ui: &mut Ui,
    center: Pos2,
    radius: f32,
    glyph: &str,
    bg: Color32,
    hover_bg: Color32,
    fg: Color32,
    id: egui::Id,
) -> Response {
    let rect = Rect::from_center_size(center, Vec2::splat(radius * 2.0));
    let resp = ui.interact(rect, id, Sense::click());
    let fill = if resp.hovered() { hover_bg } else { bg };
    let p = ui.painter();
    p.circle_filled(center, radius, fill);
    p.text(
        center,
        Align2::CENTER_CENTER,
        glyph,
        FontId::proportional(12.5),
        fg,
    );
    resp
}
