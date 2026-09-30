"""Floating frosted glass pagination capsule for Komorebi Desktop.

Floats centered above the wallpaper canvas with smooth glassmorphism styling,
elevation drop shadow, quick page navigation, and a floating popover jump card.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QScreen
from PyQt6.QtWidgets import (
    QWidget,
    QDialog,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QGraphicsDropShadowEffect,
    QApplication,
)
from wallhaven.i18n import tr


class PageJumpPopover(QDialog):
    """Floating popover card anchored directly above the pagination capsule.
    
    Provides an elegant quick-jump number input with keyboard support (Enter to jump,
    Esc to close, click outside to dismiss) without altering or distorting the capsule.
    """

    page_selected = pyqtSignal(int)

    def __init__(self, current_page: int, last_page: int, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_page = max(1, current_page)
        self.last_page = max(1, last_page)
        self._init_ui()

    def _init_ui(self):
        from wallhaven.config import config
        from wallhaven.styles import get_palette

        pal = get_palette(config.theme)
        bg = pal.get("bg_surface", "#12151f")
        border = pal.get("border", "#283045")
        accent = pal.get("accent", "#6366f1")
        accent_hover = pal.get("accent_hover", "#4f46e5")
        text = pal.get("text_primary", "#f8fafc")
        text_muted = pal.get("text_muted", "#94a3b8")
        bg_input = pal.get("bg_input", "#1e293b")

        # Outer layout
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        # Container card
        self.card = QFrame(self)
        self.card.setObjectName("jumpCard")
        self.card.setStyleSheet(f"""
            QFrame#jumpCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel#jumpTitle {{
                color: {text};
                font-size: 11.5px;
                font-weight: 800;
            }}
            QLabel#jumpRange {{
                color: {text_muted};
                font-size: 10px;
                font-weight: 600;
            }}
            QSpinBox#jumpSpin {{
                background-color: {bg_input};
                color: {text};
                border: 1.5px solid {border};
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 13px;
                font-weight: bold;
            }}
            QSpinBox#jumpSpin:focus {{
                border-color: {accent};
            }}
            QPushButton#jumpBtn {{
                background-color: {accent};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: bold;
                padding: 0 14px;
            }}
            QPushButton#jumpBtn:hover {{
                background-color: {accent_hover};
            }}
        """)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        # Header: Title & page range
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)
        title_lbl = QLabel(tr("page_jump_title"))
        title_lbl.setObjectName("jumpTitle")
        header_layout.addWidget(title_lbl)

        range_lbl = QLabel(f"(1 – {self.last_page:,})")
        range_lbl.setObjectName("jumpRange")
        header_layout.addWidget(range_lbl)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        # Input row: Spinbox + Go Button
        row = QHBoxLayout()
        row.setSpacing(8)

        self.spin = QSpinBox()
        self.spin.setObjectName("jumpSpin")
        self.spin.setRange(1, self.last_page)
        self.spin.setValue(self.current_page)
        self.spin.setFixedHeight(32)
        self.spin.setFixedWidth(90)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.spin)

        self.go_btn = QPushButton(tr("page_jump_go"))
        self.go_btn.setObjectName("jumpBtn")
        self.go_btn.setFixedHeight(32)
        self.go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_btn.clicked.connect(self._commit)
        row.addWidget(self.go_btn)

        card_layout.addLayout(row)
        outer_layout.addWidget(self.card)

    def _commit(self):
        val = self.spin.value()
        self.page_selected.emit(val)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._commit()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


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
        self.item_type = "wallpapers"

        # Compatibility dummies
        self.jump_spin = None
        self.jump_go_btn = None

        # Elevation drop shadow
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(20)
        self._shadow.setOffset(0, 6)
        self._shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(self._shadow)

        self._init_ui()
        self.retranslate_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        # First button (<<)
        self.first_btn = QPushButton("«")
        self.first_btn.setObjectName("paginationPillBtn")
        self.first_btn.setFixedSize(28, 28)
        self.first_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.first_btn.clicked.connect(lambda: self.page_requested.emit(1))
        layout.addWidget(self.first_btn)

        # Prev button (<)
        self.prev_btn = QPushButton("‹")
        self.prev_btn.setObjectName("paginationPillBtn")
        self.prev_btn.setFixedSize(30, 28)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(lambda: self.page_requested.emit(max(1, self.current_page - 1)))
        layout.addWidget(self.prev_btn)

        # Center info badge: Page X of Y
        self.page_info_btn = QPushButton()
        self.page_info_btn.setObjectName("paginationInfoBtn")
        self.page_info_btn.setFixedHeight(28)
        self.page_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.page_info_btn.clicked.connect(self._open_quick_jump)
        layout.addWidget(self.page_info_btn)

        # Next button (>)
        self.next_btn = QPushButton("›")
        self.next_btn.setObjectName("paginationPillBtn")
        self.next_btn.setFixedSize(30, 28)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(lambda: self.page_requested.emit(min(self.last_page, self.current_page + 1)))
        layout.addWidget(self.next_btn)

        # Last button (>>)
        self.last_btn = QPushButton("»")
        self.last_btn.setObjectName("paginationPillBtn")
        self.last_btn.setFixedSize(28, 28)
        self.last_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.last_btn.clicked.connect(lambda: self.page_requested.emit(self.last_page))
        layout.addWidget(self.last_btn)

        self._apply_capsule_style()

    def _apply_capsule_style(self):
        from wallhaven.config import config
        from wallhaven.styles import get_palette

        pal = get_palette(config.theme)
        bg = pal.get("bg_surface", "#12151f")
        border = pal.get("border", "#283045")
        accent = pal.get("accent", "#6366f1")
        text = pal.get("text_primary", "#f8fafc")

        self.setStyleSheet(f"""
            QFrame#floatingPagination {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 22px;
            }}
            QPushButton#paginationPillBtn {{
                background-color: rgba(255, 255, 255, 0.05);
                color: {text};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#paginationPillBtn:hover {{
                background-color: {accent};
                border-color: {accent};
                color: #ffffff;
            }}
            QPushButton#paginationPillBtn:disabled {{
                background-color: transparent;
                color: #475569;
                border-color: transparent;
            }}
            QPushButton#paginationInfoBtn {{
                background-color: transparent;
                color: {text};
                border: none;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 700;
                padding: 0 10px;
            }}
            QPushButton#paginationInfoBtn:hover {{
                background-color: rgba(255, 255, 255, 0.06);
                color: {accent};
            }}
        """)

    def _open_quick_jump(self):
        """Opens clean floating popover anchored directly above the center info button."""
        popover = PageJumpPopover(self.current_page, self.last_page, self)
        popover.page_selected.connect(self.page_requested.emit)
        popover.adjustSize()

        # Calculate coordinates directly above page_info_btn
        btn_global = self.page_info_btn.mapToGlobal(self.page_info_btn.rect().topLeft())
        btn_center_x = btn_global.x() + self.page_info_btn.width() // 2

        pop_w = popover.sizeHint().width()
        pop_h = popover.sizeHint().height()
        pop_x = btn_center_x - pop_w // 2
        pop_y = btn_global.y() - pop_h - 6

        # Screen boundary protection
        screen = QApplication.screenAt(btn_global) or self.screen()
        if screen:
            sg = screen.availableGeometry()
            pop_x = max(sg.left() + 8, min(pop_x, sg.right() - pop_w - 8))
            pop_y = max(sg.top() + 8, pop_y)

        popover.move(pop_x, pop_y)
        popover.show()
        popover.spin.setFocus()
        popover.spin.selectAll()

    def update_pagination(self, current_page: int, last_page: int, total_count: int = 0, item_type: str = "wallpapers"):
        self.current_page = max(1, current_page)
        self.last_page = max(1, last_page)
        self.total_count = total_count
        self.item_type = item_type
        self._apply_capsule_style()
        self._update_display()

    def retranslate_ui(self):
        self.first_btn.setToolTip(tr("page_first"))
        self.prev_btn.setToolTip(tr("page_prev"))
        self.next_btn.setToolTip(tr("page_next"))
        self.last_btn.setToolTip(tr("page_last"))
        self.page_info_btn.setToolTip(tr("page_jump_tip"))
        self._update_display()

    def _update_display(self):
        # Direction buttons state
        self.first_btn.setEnabled(self.current_page > 1)
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.last_page)
        self.last_btn.setEnabled(self.current_page < self.last_page)

        # Center label with clean localization
        page_info_str = tr("page_info", current=self.current_page, last=self.last_page)
        if self.total_count > 0:
            unit_str = tr("page_total_avatars") if self.item_type == "avatars" else tr("page_total_wallpapers")
            page_text = f"{page_info_str}  •  {self.total_count:,} {unit_str}"
        else:
            page_text = page_info_str

        self.page_info_btn.setText(page_text)
        self.adjustSize()


class CanvasWrapper(QWidget):
    """Wrapper holding a scroll area and a floating frosted pagination pill."""

    def __init__(self, scroll_area: QWidget, pagination: FloatingPagination, parent=None):
        super().__init__(parent)
        self.setObjectName("canvasWrapper")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
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
        self.pagination.adjustSize()
        pw = self.pagination.sizeHint().width()
        pw = max(pw, 280)
        ph = 44
        x = (self.width() - pw) // 2
        y = self.height() - ph - 16
        self.pagination.setGeometry(x, y, pw, ph)
        self.pagination.raise_()
