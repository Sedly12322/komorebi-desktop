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

from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QRadialGradient,
    QPaintEvent,
    QResizeEvent,
)
from PyQt6.QtWidgets import QWidget

from wallhaven.config import config
from wallhaven.styles import get_palette


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

        # 1. Base dark container background
        bg_hex = pal.get("bg_base", "#0d0f17")
        bg_col = QColor(bg_hex)
        painter.fillRect(self.rect(), bg_col)

        if not self._effects_enabled or w < 50 or h < 50:
            painter.end()
            return

        t = self._anim_time

        # Accent colors
        accent_col = QColor(pal.get("accent", "#6366f1"))
        sec_col = QColor(pal.get("accent_secondary", pal.get("accent_hover", "#8b5cf6")))

        is_oled = (theme_id == "oled")
        orb_alpha = 18 if is_oled else 36
        sec_alpha = 14 if is_oled else 28

        # 2. Ambient Mesh Orbs (gentle floating aurora)
        # Orb 1: Upper-right quadrant drifting
        ox1 = w * 0.72 + math.sin(t * 0.35) * (w * 0.12)
        oy1 = h * 0.22 + math.cos(t * 0.28) * (h * 0.10)
        r1 = max(260.0, min(w, h) * 0.60)

        grad1 = QRadialGradient(ox1, oy1, r1)
        grad1.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), orb_alpha))
        grad1.setColorAt(0.45, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), int(orb_alpha * 0.5)))
        grad1.setColorAt(1.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 0))
        painter.fillRect(self.rect(), grad1)

        # Orb 2: Lower-left quadrant drifting with complementary hue
        ox2 = w * 0.22 + math.cos(t * 0.30) * (w * 0.10)
        oy2 = h * 0.78 + math.sin(t * 0.40) * (h * 0.12)
        r2 = max(220.0, min(w, h) * 0.50)

        grad2 = QRadialGradient(ox2, oy2, r2)
        grad2.setColorAt(0.0, QColor(sec_col.red(), sec_col.green(), sec_col.blue(), sec_alpha))
        grad2.setColorAt(0.50, QColor(sec_col.red(), sec_col.green(), sec_col.blue(), int(sec_alpha * 0.4)))
        grad2.setColorAt(1.0, QColor(sec_col.red(), sec_col.green(), sec_col.blue(), 0))
        painter.fillRect(self.rect(), grad2)

        # Orb 3: Subtle central breathing light
        cx = w * 0.50 + math.sin(t * 0.22) * (w * 0.08)
        cy = h * 0.50 + math.cos(t * 0.25) * (h * 0.08)
        r3 = max(180.0, min(w, h) * 0.38)
        pulse = (math.sin(t * 0.6) + 1.0) * 0.5  # 0.0 to 1.0
        c3_alpha = int((12 if is_oled else 22) + pulse * 10)

        grad3 = QRadialGradient(cx, cy, r3)
        grad3.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), c3_alpha))
        grad3.setColorAt(1.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 0))
        painter.fillRect(self.rect(), grad3)

        # 3. Micro-dot Grid (Subtle Linear/Raycast tech matrix)
        dot_spacing = 32
        dot_col = QColor(255, 255, 255, 9 if is_oled else 13)
        painter.setPen(dot_col)
        pts: List[QPointF] = []
        for x in range(dot_spacing // 2, int(w), dot_spacing):
            for y in range(dot_spacing // 2, int(h), dot_spacing):
                pts.append(QPointF(float(x), float(y)))
        if pts:
            painter.drawPoints(pts)

        # 4. Floating Komorebi Light Motes (Dappled Sunlight Particles)
        self._ensure_motes()
        for mote in self._motes:
            # Alpha breathing
            alpha_wave = (math.sin(t * mote.sway_speed * 1.5 + mote.phase) + 1.0) * 0.5
            cur_alpha = int(mote.base_alpha * (0.6 + 0.4 * alpha_wave))
            cur_alpha = max(10, min(140, cur_alpha))

            # Outer soft glow halo
            halo_r = mote.radius * 2.2
            halo_grad = QRadialGradient(mote.x, mote.y, halo_r)
            halo_grad.setColorAt(0.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), int(cur_alpha * 0.6)))
            halo_grad.setColorAt(1.0, QColor(accent_col.red(), accent_col.green(), accent_col.blue(), 0))
            painter.setBrush(halo_grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(mote.x, mote.y), halo_r, halo_r)

            # Core particle
            core_col = QColor(255, 255, 255, cur_alpha)
            painter.setBrush(core_col)
            painter.drawEllipse(QPointF(mote.x, mote.y), mote.radius, mote.radius)

        painter.end()
