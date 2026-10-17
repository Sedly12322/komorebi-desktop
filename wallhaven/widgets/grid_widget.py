from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, QGraphicsOpacityEffect
from typing import Any
from wallhaven.api import WallpaperItem
from wallhaven.pfps import PfpItem
from wallhaven.config import config
from wallhaven.i18n import tr
from wallhaven.styles import get_palette
from wallhaven.widgets.wallpaper_card import WallpaperCard
from wallhaven.widgets.pfp_card import PfpCard


class WallpaperGridWidget(QWidget):
    card_clicked = pyqtSignal(WallpaperItem)
    download_requested = pyqtSignal(WallpaperItem)
    uninstall_requested = pyqtSignal(WallpaperItem)
    set_wall_requested = pyqtSignal(WallpaperItem)

    pfp_clicked = pyqtSignal(object)
    pfp_download_requested = pyqtSignal(object)
    pfp_set_avatar_requested = pyqtSignal(object)
    pfp_copy_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("wallpaperGrid")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        self.cards: list[QFrame] = []
        self.items: list[Any] = []
        self._is_pfp_mode: bool = False
        self.card_size: str = config.card_size
        self._entrance_anim: QPropertyAnimation | None = None

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(16, 16, 16, 68)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Empty State Card (shown when search returns 0 results)
        self.empty_state_frame = QFrame(self)
        self.empty_state_frame.setObjectName("emptyStateFrame")
        self.empty_state_frame.setFixedSize(420, 210)
        self.empty_state_frame.setVisible(False)
        empty_layout = QVBoxLayout(self.empty_state_frame)
        empty_layout.setContentsMargins(28, 26, 28, 26)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_icon_lbl = QLabel("🌌")
        self.empty_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_icon_lbl.setStyleSheet("font-size: 40px; background: transparent; border: none;")
        empty_layout.addWidget(self.empty_icon_lbl)

        self.empty_title_lbl = QLabel(tr("grid_empty_title"))
        self.empty_title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title_lbl.setWordWrap(True)
        empty_layout.addWidget(self.empty_title_lbl)

        self.empty_sub_lbl = QLabel(tr("grid_empty_sub"))
        self.empty_sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_sub_lbl.setWordWrap(True)
        empty_layout.addWidget(self.empty_sub_lbl)

        self._update_empty_state_style()
        self.current_cols = 4

    def _update_empty_state_style(self):
        pal = get_palette(config.theme)
        bg = pal.get("bg_card", "#12151f")
        border = pal.get("border", "#232a3b")
        accent = pal.get("accent", "#6366f1")
        text_pri = pal.get("text_primary", "#f8fafc")
        text_sec = pal.get("text_secondary", "#94a3b8")
        self.empty_state_frame.setStyleSheet(f"""
            QFrame#emptyStateFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg}, stop:1 {pal.get('bg_surface', '#161b28')});
                border: 1.5px solid {border};
                border-top: 2px solid {accent};
                border-radius: 18px;
            }}
        """)
        self.empty_title_lbl.setStyleSheet(f"color: {text_pri}; font-size: 15px; font-weight: 800; background: transparent; border: none;")
        self.empty_sub_lbl.setStyleSheet(f"color: {text_sec}; font-size: 12px; font-weight: 500; background: transparent; border: none;")

    def retranslate_ui(self):
        self.empty_title_lbl.setText(tr("grid_empty_title"))
        self.empty_sub_lbl.setText(tr("grid_empty_sub"))
        self._update_empty_state_style()

    def set_card_size(self, size_mode: str):
        if size_mode not in ("compact", "normal", "large"):
            size_mode = "normal"
        if size_mode == self.card_size:
            return
        self.card_size = size_mode
        config.card_size = size_mode
        if self.items:
            saved_items = list(self.items)
            if self._is_pfp_mode:
                self.set_pfp_items(saved_items)
            else:
                self.set_items(saved_items)

    def refresh_theme(self):
        self._update_empty_state_style()
        for card in self.cards:
            if hasattr(card, "_apply_hover_glow"):
                card._apply_hover_glow(getattr(card, "_hovered", False))
            card.update()

    def _trigger_entrance_animation(self):
        if not self.cards:
            return
        try:
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(180)
            anim.setStartValue(0.25)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            # Remove parent graphics effect once done so child card neon shadows render at full fidelity
            anim.finished.connect(lambda: self.setGraphicsEffect(None))
            self._entrance_anim = anim
            anim.start()
        except Exception:
            self.setGraphicsEffect(None)

    def set_items(self, items: list[WallpaperItem]):
        self.clear()
        self._is_pfp_mode = False
        self.items = list(items)

        if not items:
            self.empty_state_frame.setVisible(True)
            self.grid_layout.addWidget(self.empty_state_frame, 0, 0, Qt.AlignmentFlag.AlignCenter)
            return

        self.empty_state_frame.setVisible(False)
        for item in items:
            card = WallpaperCard(item, size_mode=self.card_size)
            card.clicked.connect(self.card_clicked)
            card.download_requested.connect(self.download_requested)
            card.uninstall_requested.connect(self.uninstall_requested)
            card.set_wall_requested.connect(self.set_wall_requested)
            self.cards.append(card)

        self._relayout()
        self._trigger_entrance_animation()

    def set_pfp_items(self, items: list[PfpItem]):
        self.clear()
        self._is_pfp_mode = True
        self.items = list(items)

        if not items:
            self.empty_state_frame.setVisible(True)
            self.grid_layout.addWidget(self.empty_state_frame, 0, 0, Qt.AlignmentFlag.AlignCenter)
            return

        self.empty_state_frame.setVisible(False)
        for item in items:
            card = PfpCard(item, size_mode=self.card_size)
            card.clicked.connect(self.pfp_clicked)
            card.download_requested.connect(self.pfp_download_requested)
            card.set_avatar_requested.connect(self.pfp_set_avatar_requested)
            card.copy_requested.connect(self.pfp_copy_requested)
            self.cards.append(card)

        self._relayout()
        self._trigger_entrance_animation()

    def clear(self):
        if self._entrance_anim and self._entrance_anim.state() == QPropertyAnimation.State.Running:
            self._entrance_anim.stop()
        self.setGraphicsEffect(None)
        self.grid_layout.removeWidget(self.empty_state_frame)
        self.empty_state_frame.setVisible(False)
        for card in self.cards:
            if hasattr(card, "_cleanup_loader"):
                card._cleanup_loader()
            self.grid_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
        self.items.clear()

    def _calc_columns(self) -> int:
        if self.cards:
            card_w = self.cards[0].width() + 14
        else:
            preset = WallpaperCard.SIZE_PRESETS.get(self.card_size, WallpaperCard.SIZE_PRESETS["normal"])
            card_w = preset[0] + 14
        available_w = max(200, self.width() - 32)
        cols = max(1, available_w // card_w)
        return min(cols, 10)

    def _relayout(self):
        cols = self._calc_columns()
        self.current_cols = cols

        for idx, card in enumerate(self.cards):
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self._calc_columns()
        if new_cols != self.current_cols:
            self._relayout()
