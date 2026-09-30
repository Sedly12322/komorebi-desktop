from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, QGraphicsOpacityEffect
from typing import Any, List
from wallhaven.api import WallpaperItem
from wallhaven.pfps import PfpItem
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
        self.cards: list[QFrame] = []
        self.items: list[Any] = []

        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(16, 16, 16, 68)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.current_cols = 4

    def _trigger_entrance_animation(self):
        pass

    def set_items(self, items: list[WallpaperItem]):
        self.clear()
        self.items = items

        for item in items:
            card = WallpaperCard(item)
            card.clicked.connect(self.card_clicked)
            card.download_requested.connect(self.download_requested)
            card.uninstall_requested.connect(self.uninstall_requested)
            card.set_wall_requested.connect(self.set_wall_requested)
            self.cards.append(card)

        self._relayout()
        self._trigger_entrance_animation()

    def set_pfp_items(self, items: list[PfpItem]):
        self.clear()
        self.items = items

        for item in items:
            card = PfpCard(item)
            card.clicked.connect(self.pfp_clicked)
            card.download_requested.connect(self.pfp_download_requested)
            card.set_avatar_requested.connect(self.pfp_set_avatar_requested)
            card.copy_requested.connect(self.pfp_copy_requested)
            self.cards.append(card)

        self._relayout()
        self._trigger_entrance_animation()

    def clear(self):
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
            card_w = WallpaperCard.CARD_WIDTH + 14
        available_w = max(200, self.width() - 32)
        cols = max(1, available_w // card_w)
        return min(cols, 8)

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
