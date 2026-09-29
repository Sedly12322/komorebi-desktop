"""Modern floating glassmorphic toast notification banner for Komorebi."""
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect, QGraphicsDropShadowEffect


class KomorebiToast(QWidget):
    """Floating glassmorphic pill notification with slide and fade animations."""

    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setFixedHeight(44)
        self.setMinimumWidth(260)
        self.setMaximumWidth(520)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        # Drop shadow
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(20)
        self._shadow.setOffset(0, 6)
        self._shadow.setColor(QColor(0, 0, 0, 140))

        # Auto-dismiss timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_toast)

        self._anim_pos: QPropertyAnimation | None = None
        self._anim_opacity: QPropertyAnimation | None = None

        self._init_ui()
        self.hide()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 12, 6)
        layout.setSpacing(10)

        self.icon_lbl = QLabel("🌿")
        self.icon_lbl.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(self.icon_lbl)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setStyleSheet("""
            color: #f8fafc;
            font-size: 12.5px;
            font-weight: 600;
            background: transparent;
        """)
        self.msg_lbl.setWordWrap(False)
        layout.addWidget(self.msg_lbl, 1)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #94a3b8;
                border: none;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.3);
                color: #ffffff;
            }
        """)
        self.close_btn.clicked.connect(self.hide_toast)
        layout.addWidget(self.close_btn)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Translucent glassmorphic pill background
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(1.0, 1.0, float(rect.width() - 2), float(rect.height() - 2), 22.0, 22.0)

        # Dark glass gradient
        painter.fillPath(path, QColor(16, 20, 32, 235))

        # Glowing antialiased border
        pen = painter.pen()
        pen.setColor(QColor(99, 102, 241, 160))
        pen.setWidthF(1.5)
        painter.strokePath(path, pen)
        painter.end()

    def show_message(self, text: str, icon: str = "🌿", duration_ms: int = 4000):
        if not self.parent():
            return

        self._timer.stop()
        self.icon_lbl.setText(icon)
        self.msg_lbl.setText(text)
        self.adjustSize()

        parent_w = self.parent().width()
        parent_h = self.parent().height()

        target_w = max(280, min(self.sizeHint().width() + 40, parent_w - 60))
        self.setFixedWidth(target_w)

        # Position at bottom center, floating 24px above bottom
        target_x = (parent_w - target_w) // 2
        target_y = parent_h - self.height() - 24
        start_y = target_y + 18

        self.move(target_x, start_y)
        self.show()
        self.raise_()

        # Slide & Fade in animation
        self._anim_pos = QPropertyAnimation(self, b"pos")
        self._anim_pos.setDuration(260)
        self._anim_pos.setStartValue(QPoint(target_x, start_y))
        self._anim_pos.setEndValue(QPoint(target_x, target_y))
        self._anim_pos.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_opacity = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim_opacity.setDuration(240)
        self._anim_opacity.setStartValue(0.0)
        self._anim_opacity.setEndValue(1.0)
        self._anim_opacity.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_pos.start()
        self._anim_opacity.start()

        if duration_ms > 0:
            self._timer.start(duration_ms)

    def hide_toast(self):
        if not self.isVisible():
            return
        self._timer.stop()

        target_x = self.x()
        target_y = self.y() + 14

        self._anim_pos = QPropertyAnimation(self, b"pos")
        self._anim_pos.setDuration(220)
        self._anim_pos.setStartValue(self.pos())
        self._anim_pos.setEndValue(QPoint(target_x, target_y))
        self._anim_pos.setEasingCurve(QEasingCurve.Type.InCubic)

        self._anim_opacity = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim_opacity.setDuration(200)
        self._anim_opacity.setStartValue(self._opacity_effect.opacity())
        self._anim_opacity.setEndValue(0.0)
        self._anim_opacity.setEasingCurve(QEasingCurve.Type.InCubic)

        self._anim_opacity.finished.connect(self._on_hide_finished)
        self._anim_pos.start()
        self._anim_opacity.start()

    def _on_hide_finished(self):
        self.hide()
        self.dismissed.emit()
