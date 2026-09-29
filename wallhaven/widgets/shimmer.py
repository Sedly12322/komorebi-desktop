"""Animated skeleton shimmer loading widget for wallpaper and avatar cards."""
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QPainterPath
from PyQt6.QtWidgets import QLabel


class ShimmerLabel(QLabel):
    """Image label with smooth animated shimmer skeleton wave and smooth pixmap fade-in."""

    _shared_timer: QTimer | None = None
    _shared_phase: float = 0.0
    _active_instances: set = set()

    @classmethod
    def _start_shared_timer(cls):
        if cls._shared_timer is None:
            cls._shared_timer = QTimer()
            cls._shared_timer.setInterval(33)  # ~30 FPS
            cls._shared_timer.timeout.connect(cls._on_timer_tick)
        if not cls._shared_timer.isActive():
            cls._shared_timer.start()

    @classmethod
    def _stop_shared_timer_if_empty(cls):
        if not cls._active_instances and cls._shared_timer and cls._shared_timer.isActive():
            cls._shared_timer.stop()

    @classmethod
    def _on_timer_tick(cls):
        cls._shared_phase = (cls._shared_phase + 0.035) % 1.0
        dead = []
        for inst in list(cls._active_instances):
            try:
                if inst.isVisible() and inst._is_shimmering:
                    inst.update()
            except RuntimeError:
                dead.append(inst)
        for d in dead:
            cls._active_instances.discard(d)

    def __init__(self, parent=None, corner_radius: int = 10):
        super().__init__(parent)
        self.corner_radius = corner_radius
        self._is_shimmering = True
        self._pixmap: QPixmap | None = None
        self._fade_opacity: float = 1.0
        self._fade_anim: QPropertyAnimation | None = None

        ShimmerLabel._active_instances.add(self)
        ShimmerLabel._start_shared_timer()

    @pyqtProperty(float)
    def fadeOpacity(self) -> float:
        return self._fade_opacity

    @fadeOpacity.setter
    def fadeOpacity(self, val: float):
        self._fade_opacity = val
        self.update()

    def set_corner_radius(self, radius: int):
        self.corner_radius = radius
        self.update()

    def set_loaded_pixmap(self, pixmap: QPixmap, animate: bool = True):
        self._is_shimmering = False
        self._pixmap = pixmap
        self.setText("")

        if animate:
            self._fade_opacity = 0.0
            self._fade_anim = QPropertyAnimation(self, b"fadeOpacity")
            self._fade_anim.setDuration(240)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._fade_anim.start()
        else:
            self._fade_opacity = 1.0

        self.update()

    def reset_loading(self, placeholder_text: str = ""):
        self._is_shimmering = True
        self._pixmap = None
        self._fade_opacity = 1.0
        self.setText(placeholder_text)
        ShimmerLabel._active_instances.add(self)
        ShimmerLabel._start_shared_timer()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(rect.width()), float(rect.height()), float(self.corner_radius), float(self.corner_radius))
        painter.setClipPath(path)

        if self._is_shimmering or not self._pixmap or self._pixmap.isNull():
            # Base dark container color
            painter.fillPath(path, QColor(16, 19, 28))

            # Animated wave gradient
            phase = ShimmerLabel._shared_phase
            w = float(rect.width())
            wave_width = w * 0.7
            center_x = (phase * (w + wave_width * 2)) - wave_width

            gradient = QLinearGradient(center_x - wave_width / 2, 0, center_x + wave_width / 2, 0)
            gradient.setColorAt(0.0, QColor(25, 30, 44, 0))
            gradient.setColorAt(0.5, QColor(70, 85, 120, 110))
            gradient.setColorAt(1.0, QColor(25, 30, 44, 0))

            painter.fillPath(path, gradient)

            # Subtle inner border
            pen = painter.pen()
            pen.setColor(QColor(36, 43, 62, 120))
            pen.setWidthF(1.0)
            painter.strokePath(path, pen)
        else:
            painter.setOpacity(self._fade_opacity)
            painter.drawPixmap(0, 0, self._pixmap)

        painter.end()

    def closeEvent(self, event):
        ShimmerLabel._active_instances.discard(self)
        ShimmerLabel._stop_shared_timer_if_empty()
        super().closeEvent(event)

    def __del__(self):
        try:
            ShimmerLabel._active_instances.discard(self)
            ShimmerLabel._stop_shared_timer_if_empty()
        except Exception:
            pass
