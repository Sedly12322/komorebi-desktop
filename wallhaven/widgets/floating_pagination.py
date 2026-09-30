"""Floating frosted glass pagination capsule for Komorebi Desktop.

Floats centered above the wallpaper canvas with smooth glassmorphism styling,
elevation drop shadow, quick page navigation, and direct page jumping.
"""
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QGraphicsDropShadowEffect,
    QSizePolicy,
)
from wallhaven.i18n import tr


class FloatingPagination(QFrame):
    """Frosted glass floating capsule for modern pagination."""

    page_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("floatingPagination")
        self.setFixedHeight(44)

        self.current_page = 1
        self.last_page = 1
        self.total_count = 0

        # Elevation drop shadow
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(20)
        self._shadow.setOffset(0, 6)
        self._shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(self._shadow)

        self._init_ui()
        self._update_display()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        # First button (<<)
        self.first_btn = QPushButton("«")
        self.first_btn.setObjectName("paginationPillBtn")
        self.first_btn.setFixedSize(28, 28)
        self.first_btn.setToolTip("První strana")
        self.first_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.first_btn.clicked.connect(lambda: self.page_requested.emit(1))
        layout.addWidget(self.first_btn)

        # Prev button (<)
        self.prev_btn = QPushButton("‹")
        self.prev_btn.setObjectName("paginationPillBtn")
        self.prev_btn.setFixedSize(30, 28)
        self.prev_btn.setToolTip("Předchozí strana")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(lambda: self.page_requested.emit(max(1, self.current_page - 1)))
        layout.addWidget(self.prev_btn)

        # Center info badge: Strana X z Y
        self.page_info_btn = QPushButton("Strana 1 z 1")
        self.page_info_btn.setObjectName("paginationInfoBtn")
        self.page_info_btn.setFixedHeight(28)
        self.page_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.page_info_btn.setToolTip("Klikněte pro rychlý přechod na stránku")
        self.page_info_btn.clicked.connect(self._toggle_quick_jump)
        layout.addWidget(self.page_info_btn)

        # Quick Jump SpinBox (hidden by default, revealed on click)
        self.jump_box = QFrame()
        self.jump_box.setVisible(False)
        j_layout = QHBoxLayout(self.jump_box)
        j_layout.setContentsMargins(0, 0, 0, 0)
        j_layout.setSpacing(4)

        self.jump_spin = QSpinBox()
        self.jump_spin.setObjectName("paginationSpin")
        self.jump_spin.setRange(1, 9999)
        self.jump_spin.setValue(1)
        self.jump_spin.setFixedHeight(28)
        self.jump_spin.setFixedWidth(64)
        self.jump_spin.returnPressed = lambda: self._commit_quick_jump()
        j_layout.addWidget(self.jump_spin)

        self.jump_go_btn = QPushButton("Go")
        self.jump_go_btn.setObjectName("primaryButton")
        self.jump_go_btn.setFixedSize(32, 28)
        self.jump_go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.jump_go_btn.clicked.connect(self._commit_quick_jump)
        j_layout.addWidget(self.jump_go_btn)

        layout.addWidget(self.jump_box)

        # Next button (>)
        self.next_btn = QPushButton("›")
        self.next_btn.setObjectName("paginationPillBtn")
        self.next_btn.setFixedSize(30, 28)
        self.next_btn.setToolTip("Další strana")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(lambda: self.page_requested.emit(min(self.last_page, self.current_page + 1)))
        layout.addWidget(self.next_btn)

        # Last button (>>)
        self.last_btn = QPushButton("»")
        self.last_btn.setObjectName("paginationPillBtn")
        self.last_btn.setFixedSize(28, 28)
        self.last_btn.setToolTip("Poslední strana")
        self.last_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.last_btn.clicked.connect(lambda: self.page_requested.emit(self.last_page))
        layout.addWidget(self.last_btn)

        self._apply_capsule_style()

    def _apply_capsule_style(self):
        self.setStyleSheet("""
            QFrame#floatingPagination {
                background-color: rgba(15, 18, 28, 0.92);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 22px;
            }
            QPushButton#paginationPillBtn {
                background-color: rgba(255, 255, 255, 0.06);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton#paginationPillBtn:hover {
                background-color: rgba(99, 102, 241, 0.4);
                border-color: rgba(129, 140, 248, 0.6);
                color: #ffffff;
            }
            QPushButton#paginationPillBtn:disabled {
                background-color: transparent;
                color: #475569;
                border-color: transparent;
            }
            QPushButton#paginationInfoBtn {
                background-color: transparent;
                color: #f1f5f9;
                border: none;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 700;
                padding: 0 8px;
            }
            QPushButton#paginationInfoBtn:hover {
                background-color: rgba(255, 255, 255, 0.06);
                color: #818cf8;
            }
            QSpinBox#paginationSpin {
                background-color: rgba(30, 41, 59, 0.9);
                color: #ffffff;
                border: 1px solid #4f46e5;
                border-radius: 8px;
                padding: 2px 6px;
                font-size: 12px;
                font-weight: bold;
            }
        """)

    def _toggle_quick_jump(self):
        is_editing = self.jump_box.isVisible()
        self.jump_box.setVisible(not is_editing)
        self.page_info_btn.setVisible(is_editing)
        if not is_editing:
            self.jump_spin.setValue(self.current_page)
            self.jump_spin.setFocus()
            self.jump_spin.selectAll()

    def _commit_quick_jump(self):
        target_page = self.jump_spin.value()
        self.jump_box.setVisible(False)
        self.page_info_btn.setVisible(True)
        if target_page != self.current_page:
            self.page_requested.emit(target_page)

    def update_pagination(self, current_page: int, last_page: int, total_count: int = 0):
        self.current_page = max(1, current_page)
        self.last_page = max(1, last_page)
        self.total_count = total_count
        self._update_display()

    def _update_display(self):
        # Enable / disable direction buttons
        self.first_btn.setEnabled(self.current_page > 1)
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.last_page)
        self.last_btn.setEnabled(self.current_page < self.last_page)

        # Center label
        page_text = f"Strana {self.current_page} z {self.last_page}"
        if self.total_count > 0:
            page_text += f"  •  {self.total_count:,} tapet"
        self.page_info_btn.setText(page_text)
        self.jump_spin.setRange(1, self.last_page)

        self.adjustSize()


class CanvasWrapper(QWidget):
    """Wrapper holding a scroll area and a floating frosted pagination pill."""

    def __init__(self, scroll_area: QWidget, pagination: FloatingPagination, parent=None):
        super().__init__(parent)
        self.scroll_area = scroll_area
        self.pagination = pagination

        self.scroll_area.setParent(self)
        self.pagination.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scroll_area)

        self.pagination.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_pagination()

    def reposition_pagination(self):
        pw = self.pagination.sizeHint().width()
        pw = max(pw, 320)
        ph = 44
        x = (self.width() - pw) // 2
        y = self.height() - ph - 16
        self.pagination.setGeometry(x, y, pw, ph)
        self.pagination.raise_()
