"""Atmospheric ambient background canvas for Komorebi Desktop.

Features:
- "Komorebi" dappled light effect: subtle luminous aurora mesh with theme-adaptive radial gradients.
- Floating dust motes / light particles gently drifting with soft alpha pulsation.
- Refined micro-dot grid for depth and modern aesthetic (Linear/Raycast inspired).
- Zero-overhead lifecycle: pauses when window is hidden or minimized.
- Can be toggled on/off in application settings.
"""
import math
import random
import time
from typing import List

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QRadialGradient,
    QLinearGradient,
    QPaintEvent,
    QResizeEvent,
)
from PyQt6.QtWidgets import QWidget

from wallhaven.config import config
from wallhaven.styles import get_palette, _is_light_color


class LightMote:
    """A single floating dappled light mote / particle."""

    def __init__(self, w: float, h: float):
        self.x = random.uniform(0, max(100.0, w))
        self.y = random.uniform(0, max(100.0, h))
        self.radius = random.uniform(1.2, 4.2)
        self.speed_y = random.uniform(0.12, 0.42)
        self.sway_speed = random.uniform(0.6, 1.8)
        self.sway_amp = random.uniform(0.3, 1.2)
        self.base_alpha = random.uniform(30.0, 95.0)
        self.phase = random.uniform(0, math.pi * 2)

    def update(self, dt: float, w: float, h: float, t: float):
        self.y -= self.speed_y * (dt * 30.0)
        self.x += math.sin(t * self.sway_speed + self.phase) * (self.sway_amp * dt * 30.0)

        # Wrap around screen edges
        if self.y < -10:
            self.y = h + random.uniform(5, 20)
            self.x = random.uniform(0, max(100.0, w))
        if self.x < -10:
            self.x = w + 5
        elif self.x > w + 10:
            self.x = -5


class KomorebiAmbientCanvas(QWidget):
    """Living ambient background canvas with dynamic glowing aurora mesh and particles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ambientContentCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self._anim_time = 0.0
        self._last_tick = time.time()
        self._effects_enabled = getattr(config, "background_effects", True)

        self._motes: List[LightMote] = []
        self._motes_count = 28

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._on_tick)

        if self._effects_enabled:
            self._timer.start()

    def set_effects_enabled(self, enabled: bool):
        self._effects_enabled = enabled
        if enabled:
            if not self._timer.isActive() and self.isVisible():
                self._last_tick = time.time()
                self._timer.start()
        else:
            if self._timer.isActive():
                self._timer.stop()
        self.update()

    def _ensure_motes(self):
        w = float(self.width())
        h = float(self.height())
        if not self._motes and w > 50 and h > 50:
            self._motes = [LightMote(w, h) for _ in range(self._motes_count)]

    def _on_tick(self):
        now = time.time()
        dt = min(0.1, max(0.001, now - self._last_tick))
        self._last_tick = now
        self._anim_time += dt

        w = float(self.width())
        h = float(self.height())

        for mote in self._motes:
            mote.update(dt, w, h, self._anim_time)

        self.update()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._ensure_motes()

    def showEvent(self, event):
        super().showEvent(event)
        if self._effects_enabled and not self._timer.isActive():
            self._last_tick = time.time()
            self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._timer.isActive():
            self._timer.stop()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())

        pal = get_palette(config.theme)
        theme_id = config.theme

        bg_hex = pal.get("bg_base", "#0d0f17")
        bg_col = QColor(bg_hex)
        is_oled = (theme_id == "oled")
        is_light = _is_light_color(bg_hex)

        accent_hex = pal.get("accent", "#6366f1")
        accent_col = QColor(accent_hex)
        sec_hex = pal.get("accent_gradient_end", pal.get("accent_hover", "#8b5cf6"))
        sec_col = QColor(sec_hex)

        # 1. Base vertical atmospheric fading
        base_grad = QLinearGradient(0.0, 0.0, 0.0, h)
        if is_oled:
            base_grad.setColorAt(0.0, QColor(0, 0, 0))
            base_grad.setColorAt(1.0, QColor(0, 0, 0))
        elif is_light:
            base_grad.setColorAt(0.0, bg_col.lighter(103))
            base_grad.setColorAt(0.50, bg_col)
            base_grad.setColorAt(1.0, bg_col.darker(106))
        else:
            # Subtle accent infusion at top, deep grounded darkness at bottom
            top_r = min(255, int(bg_col.red() * 0.94 + accent_col.red() * 0.06))
            top_g = min(255, int(bg_col.green() * 0.94 + accent_col.green() * 0.06))
            top_b = min(255, int(bg_col.blue() * 0.94 + accent_col.blue() * 0.06))
            base_grad.setColorAt(0.0, QColor(top_r, top_g, top_b))
            base_grad.setColorAt(0.40, bg_col)
            base_grad.setColorAt(0.85, bg_col.darker(110))
            base_grad.setColorAt(1.0, bg_col.darker(122))

        painter.fillRect(self.rect(), base_grad)

        if not self._effects_enabled or w < 50 or h < 50:
            painter.end()
            return

        t = self._anim_time

        # 2. Top atmospheric light fade (Overhead soft glow)
        top_glow_h = min(280.0, h * 0.42)
        top_glow = QLinearGradient(0.0, 0.0, 0.0, top_glow_h)
        top_alpha = 22 if is_oled else (14 if is_light else 44)
        top_glow.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), top_alpha))
        top_glow.setColorAt(0.45, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), int(top_alpha * 0.40)))
        top_glow.setColorAt(1.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 0))
        painter.fillRect(QRectF(0.0, 0.0, w, top_glow_h), top_glow)

        # 3. CRT phosphor bloom (very faint, breathing)
        pulse = (math.sin(t * 0.6) + 1.0) * 0.5
        bloom_alpha = int((6 if is_light else 14) + pulse * 8)
        bloom = QRadialGradient(w * 0.5, h * 0.45, max(w, h) * 0.55)
        bloom.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), bloom_alpha))
        bloom.setColorAt(1.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 0))
        painter.fillRect(self.rect(), bloom)

        # 4. Perimeter Radial Vignette (Soft edge fading)
        if not is_oled:
            vignette = QRadialGradient(w * 0.50, h * 0.45, max(w, h) * 0.72)
            vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
            vignette.setColorAt(0.55, QColor(0, 0, 0, 0))
            vig_alpha = 20 if is_light else 45
            vignette.setColorAt(0.85, QColor(0, 0, 0, int(vig_alpha * 0.55)))
            vignette.setColorAt(1.0, QColor(0, 0, 0, vig_alpha))
            painter.fillRect(self.rect(), vignette)

        # 5. Bottom Grounding Edge Fade (Behind floating pagination capsule)
        bot_fade_h = min(160.0, h * 0.24)
        bot_fade = QLinearGradient(0.0, h - bot_fade_h, 0.0, h)
        bot_alpha = 18 if is_light else (0 if is_oled else 40)
        bot_fade.setColorAt(0.0, QColor(0, 0, 0, 0))
        bot_fade.setColorAt(0.60, QColor(0, 0, 0, int(bot_alpha * 0.45)))
        bot_fade.setColorAt(1.0, QColor(0, 0, 0, bot_alpha))
        painter.fillRect(QRectF(0.0, h - bot_fade_h, w, bot_fade_h), bot_fade)

        # 6. Terminal scanlines (1px dark line every 3px)
        scan_col = QColor(0, 0, 0, 34 if not is_light else 12)
        painter.setPen(scan_col)
        for y in range(0, int(h), 3):
            painter.drawLine(0, y, int(w), y)

        # 7. Slow rolling scan band (old CRT refresh line)
        band_h = 90.0
        band_y = ((t * 38.0) % (h + band_h * 2)) - band_h
        band = QLinearGradient(0.0, band_y, 0.0, band_y + band_h)
        band.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 0))
        band.setColorAt(0.8, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 9 if not is_light else 4))
        band.setColorAt(1.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 0))
        painter.fillRect(QRectF(0.0, band_y, w, band_h), band)

        painter.end()
