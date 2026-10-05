"""Fluid animated navigation pill capsule for Komorebi Desktop."""
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from wallhaven.i18n import tr


class NavTabButton(QPushButton):
    def __init__(self, mode: str, text: str, parent=None):
        super().__init__(text, parent)
        self.mode = mode
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.setCheckable(False)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 7px;
                padding: 0 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #f8fafc;
            }
        """)


class AnimatedCapsuleBar(QWidget):
    """Modern capsule bar with a fluid sliding indicator pill."""

    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tabsContainer")
        self.setFixedHeight(36)

        self._current_mode = "wallhaven"
        self._indicator_rect = QRect(3, 3, 100, 30)
        self._target_rect = QRect(3, 3, 100, 30)

        self._anim = QPropertyAnimation(self, b"indicatorRect")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.buttons: dict[str, NavTabButton] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        tabs = [
            ("wallhaven", "🌌 Wallhaven"),
            ("moewalls", "🎬 MoeWalls"),
            ("osu", tr("tab_osu")),
            ("pfps", tr("tab_pfps")),
            ("installed", tr("tab_installed")),
        ]

        for mode, label in tabs:
            btn = NavTabButton(mode, label, self)
            btn.clicked.connect(lambda checked, m=mode: self.set_mode(m, user_click=True))
            layout.addWidget(btn)
            self.buttons[mode] = btn

        self._update_tab_texts()

    def _update_tab_texts(self):
        mapping = {
            "wallhaven": tr("tab_wallhaven"),
            "moewalls": tr("tab_moewalls"),
            "osu": tr("tab_osu"),
            "pfps": tr("tab_pfps"),
            "installed": tr("tab_installed"),
        }
        for mode, text in mapping.items():
            if mode in self.buttons:
                self.buttons[mode].setText(text)

    def retranslate_ui(self):
        self._update_tab_texts()
        self._snap_indicator_to_mode(self._current_mode)

    @pyqtProperty(QRect)
    def indicatorRect(self) -> QRect:
        return self._indicator_rect

    @indicatorRect.setter
    def indicatorRect(self, r: QRect):
        self._indicator_rect = r
        self.update()

    def set_mode(self, mode: str, user_click: bool = False):
        if mode not in self.buttons:
            return

        old_mode = self._current_mode
        self._current_mode = mode

        # Update text styles
        for m, btn in self.buttons.items():
            if m == mode:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #ffffff;
                        border: none;
                        border-radius: 7px;
                        padding: 0 12px;
                        font-size: 12px;
                        font-weight: 800;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #94a3b8;
                        border: none;
                        border-radius: 7px;
                        padding: 0 12px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        color: #f8fafc;
                    }
                """)

        target_btn = self.buttons[mode]
        target_r = target_btn.geometry()
        if target_r.isValid() and target_r.width() > 0:
            self._target_rect = target_r
            self._anim.stop()
            self._anim.setStartValue(self._indicator_rect)
            self._anim.setEndValue(target_r)
            self._anim.start()
        else:
            self._indicator_rect = target_r
            self.update()

        if user_click:
            self.mode_changed.emit(mode)

    def _snap_indicator_to_mode(self, mode: str):
        if mode in self.buttons:
            btn = self.buttons[mode]
            r = btn.geometry()
            if r.isValid() and r.width() > 0:
                self._indicator_rect = r
                self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._snap_indicator_to_mode(self._current_mode)

    def showEvent(self, event):
        super().showEvent(event)
        self._snap_indicator_to_mode(self._current_mode)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer capsule container
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, float(rect.width() - 1), float(rect.height() - 1), 10.0, 10.0)

        painter.fillPath(path, QColor(11, 13, 20))
        pen = painter.pen()
        pen.setColor(QColor(30, 36, 52))
        pen.setWidthF(1.0)
        painter.strokePath(path, pen)

        # Animated pill indicator
        if self._indicator_rect.isValid() and self._indicator_rect.width() > 0:
            pill_path = QPainterPath()
            ir = self._indicator_rect
            pill_path.addRoundedRect(float(ir.x()), float(ir.y()), float(ir.width()), float(ir.height()), 7.0, 7.0)

            # Indigo/violet gradient
            grad = QLinearGradient(float(ir.x()), 0, float(ir.x() + ir.width()), 0)
            grad.setColorAt(0.0, QColor(99, 102, 241))
            grad.setColorAt(1.0, QColor(139, 92, 246))
            painter.fillPath(pill_path, grad)

            # Pill subtle glow border
            pill_pen = painter.pen()
            pill_pen.setColor(QColor(165, 180, 252, 140))
            pill_pen.setWidthF(1.0)
            painter.strokePath(pill_path, pill_pen)

        painter.end()
