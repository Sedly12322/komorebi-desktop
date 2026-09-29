from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QColor, QPainter, QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QGraphicsDropShadowEffect,
)
from wallhaven.api import WallpaperItem
from wallhaven.image_loader import loader
from wallhaven.i18n import tr
from wallhaven.widgets.shimmer import ShimmerLabel


class WallpaperCard(QFrame):
    clicked = pyqtSignal(WallpaperItem)
    download_requested = pyqtSignal(WallpaperItem)
    uninstall_requested = pyqtSignal(WallpaperItem)
    set_wall_requested = pyqtSignal(WallpaperItem)

    CARD_WIDTH = 296
    CARD_HEIGHT = 226
    IMAGE_WIDTH = 284
    IMAGE_HEIGHT = 170

    def __init__(self, item: WallpaperItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("wallpaperCard")
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pixmap: QPixmap | None = None
        self._thumb_url = self.item.thumb_large or self.item.thumb_small or self.item.path

        # Soft drop shadow with animated hover bloom
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(10)
        self._shadow.setOffset(0, 3)
        self._shadow.setColor(QColor(0, 0, 0, 75))
        self.setGraphicsEffect(self._shadow)

        self._anim_blur: QPropertyAnimation | None = None
        self._anim_offset: QPropertyAnimation | None = None

        self._init_ui()
        self._load_thumbnail()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Image preview with animated skeleton shimmer
        self.image_label = ShimmerLabel(self, corner_radius=9)
        self.image_label.setFixedSize(self.IMAGE_WIDTH, self.IMAGE_HEIGHT)
        layout.addWidget(self.image_label)

        # 2. Bottom info row
        info_row = QHBoxLayout()
        info_row.setContentsMargins(4, 0, 4, 2)
        info_row.setSpacing(6)

        # Live wallpaper indicator
        if getattr(self.item, "is_animated", False):
            live_badge = QLabel("▶ LIVE")
            live_badge.setToolTip(tr("card_live_tooltip"))
            live_badge.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #6366f1);
                    color: #ffffff;
                    border-radius: 5px;
                    font-weight: 800;
                    font-size: 10px;
                    padding: 2px 6px;
                }
            """)
            info_row.addWidget(live_badge)

        # Resolution badge (4K Gold, 2K Cyan, Standard)
        is_4k = self.item.dimension_x >= 3840
        is_2k = not is_4k and self.item.dimension_x >= 2560

        if is_4k:
            res_text = "✨ 4K"
        elif is_2k:
            res_text = "⚡ 2K"
        else:
            res_text = self.item.resolution

        self.res_badge = QLabel(res_text)
        self.res_badge.setToolTip(f"{self.item.resolution} • {self.item.ratio}")
        if is_4k:
            self.res_badge.setStyleSheet("""
                background-color: rgba(245, 158, 11, 0.18);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 5px;
                padding: 2px 6px;
                font-size: 10.5px;
                font-weight: bold;
            """)
        elif is_2k:
            self.res_badge.setStyleSheet("""
                background-color: rgba(56, 189, 248, 0.18);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 5px;
                padding: 2px 6px;
                font-size: 10.5px;
                font-weight: bold;
            """)
        else:
            self.res_badge.setObjectName("badge")
        info_row.addWidget(self.res_badge)

        # Category badge
        is_installed = getattr(self.item, "is_installed", False)
        if is_installed:
            cat_badge = QLabel(self.item.source or "Installed")
            tooltip_text = f"{getattr(self.item, '_display_title', self.item.id)}\n{self.item.resolution} • {self.item.human_file_size}"
            if self.item.path:
                tooltip_text += f"\n{self.item.path}"
            self.setToolTip(tooltip_text)
        elif getattr(self.item, "_osu_meta", None):
            meta = self.item._osu_meta
            cat_badge = QLabel(meta.get("theme") or "osu!")
            rank = meta.get("rank", 0)
            if 0 < rank <= 15:
                cat_badge.setToolTip(f"Winner #{rank} - {meta.get('season', '')}")
            self.setToolTip(f"{meta.get('title', '')}\nArtist: {meta.get('artist', '')}\nSeason: {meta.get('season', '')}\nVotes: {meta.get('votes', 0):,}")
        else:
            cat_badge = QLabel(self.item.category.capitalize())

        cat_badge.setObjectName("categoryBadge")
        info_row.addWidget(cat_badge)

        # Purity indicator
        if self.item.purity == "sketchy":
            purity_lbl = QLabel("S")
            purity_lbl.setToolTip("Sketchy")
            purity_lbl.setStyleSheet("""
                background: #d97706;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 5px;
            """)
            info_row.addWidget(purity_lbl)
        elif self.item.purity == "nsfw":
            purity_lbl = QLabel("NSFW")
            purity_lbl.setStyleSheet("""
                background: #e11d48;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 5px;
            """)
            info_row.addWidget(purity_lbl)

        info_row.addStretch()

        # Favorites count
        if self.item.favorites > 0:
            fav_lbl = QLabel(f"★ {self.item.favorites}")
            fav_lbl.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 600;")
            info_row.addWidget(fav_lbl)

        # Action Buttons
        if is_installed:
            self.set_wall_btn = QPushButton("🖼️")
            self.set_wall_btn.setFixedSize(28, 26)
            self.set_wall_btn.setToolTip(tr("card_set_wall_tooltip"))
            self.set_wall_btn.setStyleSheet("""
                QPushButton {
                    background: #059669;
                    color: #ffffff;
                    border: 1px solid #10b981;
                    border-radius: 6px;
                    font-size: 12px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: #10b981;
                }
            """)
            self.set_wall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.set_wall_btn.clicked.connect(lambda: self.set_wall_requested.emit(self.item))
            info_row.addWidget(self.set_wall_btn)

            self.uninstall_btn = QPushButton("🗑️")
            self.uninstall_btn.setFixedSize(28, 26)
            self.uninstall_btn.setToolTip(tr("card_uninstall_tooltip"))
            self.uninstall_btn.setStyleSheet("""
                QPushButton {
                    background: #dc2626;
                    color: #ffffff;
                    border: 1px solid #ef4444;
                    border-radius: 6px;
                    font-size: 12px;
                    padding: 0;
                }
                QPushButton:hover {
                    background: #ef4444;
                }
            """)
            self.uninstall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.uninstall_btn.clicked.connect(lambda: self.uninstall_requested.emit(self.item))
            info_row.addWidget(self.uninstall_btn)
        else:
            self.dl_btn = QPushButton("⬇")
            self.dl_btn.setFixedSize(28, 26)
            self.dl_btn.setToolTip(tr("card_download_tooltip"))
            self.dl_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                    color: #ffffff;
                    border: 1px solid #818cf8;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 0;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
                    border-color: #a5b4fc;
                }
            """)
            self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.dl_btn.clicked.connect(self._on_download_clicked)
            info_row.addWidget(self.dl_btn)

        layout.addLayout(info_row)

    def _load_thumbnail(self):
        if not self._thumb_url:
            self.image_label.setText(tr("card_no_preview"))
            return

        target_size = (self.IMAGE_WIDTH, self.IMAGE_HEIGHT)
        # Ultra-fast path: checks pre-scaled memory cache and dispatches without UI thread scaling
        loader.load_thumbnail(
            self._thumb_url,
            target_size=target_size,
            radius=8,
            callback=self._set_pixmap_instant
        )

    def _set_pixmap_instant(self, pixmap: QPixmap):
        """Called directly when pre-scaled rounded pixmap is ready."""
        self._pixmap = pixmap
        self.image_label.set_loaded_pixmap(pixmap, animate=True)

    def enterEvent(self, event):
        super().enterEvent(event)
        # Animate drop shadow bloom on hover
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(180)
        self._anim_blur.setEndValue(24.0)
        self._anim_blur.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim_offset.setDuration(180)
        self._anim_offset.setEndValue(7.0)
        self._anim_offset.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow.setColor(QColor(99, 102, 241, 100))
        self._anim_blur.start()
        self._anim_offset.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(180)
        self._anim_blur.setEndValue(10.0)
        self._anim_blur.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim_offset.setDuration(180)
        self._anim_offset.setEndValue(3.0)
        self._anim_offset.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow.setColor(QColor(0, 0, 0, 75))
        self._anim_blur.start()
        self._anim_offset.start()

    def _cleanup_loader(self):
        if self._thumb_url:
            loader.unregister_callback(self._thumb_url, self._set_pixmap_instant)

    def closeEvent(self, event):
        self._cleanup_loader()
        super().closeEvent(event)

    def _on_download_clicked(self):
        self.download_requested.emit(self.item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            btn_clicked = False
            if hasattr(self, "dl_btn") and self.dl_btn.geometry().contains(pos):
                btn_clicked = True
            elif hasattr(self, "set_wall_btn") and self.set_wall_btn.geometry().contains(pos):
                btn_clicked = True
            elif hasattr(self, "uninstall_btn") and self.uninstall_btn.geometry().contains(pos):
                btn_clicked = True

            if not btn_clicked:
                self.clicked.emit(self.item)
        super().mousePressEvent(event)
