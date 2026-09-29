"""Smooth inertial mouse-wheel scrolling for Komorebi QScrollArea."""
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QScrollArea


class SmoothScrollArea(QScrollArea):
    """QScrollArea featuring smooth animated vertical wheel interpolation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_scroll_val: int = 0
        self._scroll_anim = QPropertyAnimation(self, b"scrollValue")
        self._scroll_anim.setDuration(220)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(int)
    def scrollValue(self) -> int:
        return self.verticalScrollBar().value()

    @scrollValue.setter
    def scrollValue(self, val: int):
        self.verticalScrollBar().setValue(val)

    def wheelEvent(self, event: QWheelEvent):
        num_degrees = event.angleDelta().y() / 8
        num_steps = num_degrees / 15

        if num_steps == 0:
            super().wheelEvent(event)
            return

        sb = self.verticalScrollBar()
        min_v = sb.minimum()
        max_v = sb.maximum()

        if not self._scroll_anim.state() == QPropertyAnimation.State.Running:
            self._target_scroll_val = sb.value()

        # Step size per wheel notch (~120px)
        delta = int(-num_steps * 130)
        self._target_scroll_val = max(min_v, min(max_v, self._target_scroll_val + delta))

        self._scroll_anim.stop()
        self._scroll_anim.setStartValue(sb.value())
        self._scroll_anim.setEndValue(self._target_scroll_val)
        self._scroll_anim.start()

        event.accept()
