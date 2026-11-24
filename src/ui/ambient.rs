use egui::{Color32, Painter, Pos2, Rect};
use rand::Rng;

use crate::theme::{with_alpha, ThemePalette};

#[derive(Debug, Clone)]
struct LightMote {
    x_norm: f32,
    y_norm: f32,
    vx: f32,
    vy: f32,
    radius: f32,
    alpha: u8,
    phase: f32,
    use_secondary: bool,
}

pub struct AmbientCanvas {
    motes: Vec<LightMote>,
    last_time: f64,
}

impl Default for AmbientCanvas {
    fn default() -> Self {
        Self::new()
    }
}

impl AmbientCanvas {
    pub fn new() -> Self {
        let mut rng = rand::thread_rng();
        let motes = (0..22)
            .map(|i| LightMote {
                x_norm: rng.gen_range(0.03..0.97),
                y_norm: rng.gen_range(0.03..0.97),
                vx: rng.gen_range(-0.003..0.003),
                vy: rng.gen_range(-0.011..-0.003),
                radius: rng.gen_range(1.0..2.6),
                alpha: rng.gen_range(10..32),
                phase: rng.gen_range(0.0..std::f32::consts::TAU),
                use_secondary: i % 3 == 0,
            })
            .collect();
        Self {
            motes,
            last_time: 0.0,
        }
    }

    pub fn paint(
        &mut self,
        ctx: &egui::Context,
        painter: &Painter,
        rect: Rect,
        pal: &ThemePalette,
        enabled: bool,
    ) {
        painter.rect_filled(rect, 0.0, pal.bg_base);

        if !enabled || pal.is_oled {
            return;
        }

        let time = ctx.input(|i| i.time);
        let dt = if self.last_time > 0.0 {
            ((time - self.last_time) as f32).clamp(0.0, 0.1)
        } else {
            0.016
        };
        self.last_time = time;

        // Subtle overhead accent atmospheric tint matching v2.0.6 depth
        let top_band = Rect::from_min_max(
            rect.min,
            Pos2::new(rect.right(), rect.top() + (rect.height() * 0.36).min(240.0)),
        );
        let mut mesh = egui::Mesh::default();
        let top_col = with_alpha(pal.accent, if pal.is_light { 12 } else { 24 });
        let bot_col = with_alpha(pal.accent, 0);
        mesh.colored_vertex(top_band.left_top(), top_col);
        mesh.colored_vertex(top_band.right_top(), top_col);
        mesh.colored_vertex(top_band.right_bottom(), bot_col);
        mesh.colored_vertex(top_band.left_bottom(), bot_col);
        mesh.add_triangle(0, 1, 2);
        mesh.add_triangle(0, 2, 3);
        painter.add(mesh);

        // Very faint breathing center bloom (zero noisy scanlines or dot grid)
        let t32 = time as f32;
        let pulse = 0.5 + 0.5 * (t32 * 0.6).sin();
        let center_alpha = if pal.is_light { 6 } else { (8.0 + pulse * 4.0) as u8 };
        paint_soft_glow(
            painter,
            Pos2::new(rect.center().x, rect.top() + rect.height() * 0.42),
            rect.width().max(520.0) * 0.38,
            pal.accent,
            center_alpha,
        );

        // Gentle drifting komorebi sunlight motes
        for m in &mut self.motes {
            m.x_norm += m.vx * dt;
            m.y_norm += m.vy * dt;
            if m.y_norm < -0.02 {
                m.y_norm = 1.02;
            }
            if m.x_norm < -0.02 {
                m.x_norm = 1.02;
            } else if m.x_norm > 1.02 {
                m.x_norm = -0.02;
            }

            let m_pulse = 0.65 + 0.35 * (t32 * 1.2 + m.phase).sin();
            let alpha = ((m.alpha as f32) * m_pulse).clamp(6.0, 34.0) as u8;
            let base_col = if m.use_secondary {
                pal.accent_grad_end
            } else {
                pal.accent
            };
            let pos = Pos2::new(
                rect.left() + m.x_norm * rect.width(),
                rect.top() + m.y_norm * rect.height(),
            );
            painter.circle_filled(pos, m.radius * 1.8, with_alpha(base_col, alpha / 3));
            painter.circle_filled(pos, m.radius, with_alpha(base_col, alpha));
        }

        if ctx.input(|i| i.focused) {
            ctx.request_repaint_after(std::time::Duration::from_millis(33));
        }
    }
}

fn paint_soft_glow(painter: &Painter, center: Pos2, radius: f32, color: Color32, max_alpha: u8) {
    let steps = 4;
    for i in (1..=steps).rev() {
        let frac = i as f32 / steps as f32;
        let r = radius * frac;
        let a = ((max_alpha as f32) * (1.0 - frac + 0.25) / (steps as f32 * 0.65)) as u8;
        painter.circle_filled(center, r, with_alpha(color, a));
    }
}
