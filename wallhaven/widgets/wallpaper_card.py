from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF, QPointF, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPainterPath, QLinearGradient, QPen, QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QSizePolicy,
    QGraphicsDropShadowEffect,
)
from wallhaven.api import WallpaperItem
from wallhaven.config import config
from wallhaven.styles import get_palette
from wallhaven.installed import installed_manager
from wallhaven.image_loader import loader
from wallhaven.i18n import tr
from wallhaven.widgets.shimmer import ShimmerLabel
from wallhaven.animated_preview import AnimPlayer, HAS_AV


class WallpaperCard(QFrame):
    clicked = pyqtSignal(WallpaperItem)
    download_requested = pyqtSignal(WallpaperItem)
    uninstall_requested = pyqtSignal(WallpaperItem)
    set_wall_requested = pyqtSignal(WallpaperItem)

    CARD_WIDTH = 296
    CARD_HEIGHT = 218
    IMAGE_WIDTH = 284
    IMAGE_HEIGHT = 172

    SIZE_PRESETS = {
        "compact": (236, 176, 224, 130),
        "normal": (296, 218, 284, 172),
        "large": (368, 266, 356, 220),
    }

    def __init__(self, item: WallpaperItem, parent=None, size_mode: str = ""):
        super().__init__(parent)
        self.item = item
        self.size_mode = size_mode or config.card_size
        cw, ch, iw, ih = self.SIZE_PRESETS.get(self.size_mode, self.SIZE_PRESETS["normal"])
        self._card_w = cw
        self._card_h = ch
        self._img_w = iw
        self._img_h = ih
        self._hovered = False

        self.setObjectName("wallpaperCard")
        self.setFixedSize(self._card_w, self._card_h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pixmap: QPixmap | None = None
        self._thumb_url = self.item.thumb_large or self.item.thumb_small or self.item.path

        # Neon / Gaming drop shadow with animated hover bloom
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(12)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 95))
        self.setGraphicsEffect(self._shadow)

        self._anim_blur: QPropertyAnimation | None = None
        self._anim_offset: QPropertyAnimation | None = None

        # Animated (live wallpaper) hover preview
        self._anim_player: AnimPlayer | None = None
        self._anim_playing = False
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(280)
        self._hover_timer.timeout.connect(self._start_live_preview)

        self._init_ui()
        self._load_thumbnail()

    def _init_ui(self):
        pal = get_palette(config.theme)
        accent = pal.get("accent", "#6366f1")
        accent_hover = pal.get("accent_hover", "#818cf8")
        text_pri = pal.get("text_primary", "#f8fafc")

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(6)

        # 1. Image preview with animated skeleton shimmer
        self.image_label = ShimmerLabel(self, corner_radius=2)
        self.image_label.setFixedSize(self._img_w, self._img_h)

        # In-image overlay layout
        overlay_layout = QVBoxLayout(self.image_label)
        overlay_layout.setContentsMargins(8, 8, 8, 8)
        overlay_layout.setSpacing(0)

        # Top row inside image: Format/Live/Installed badge (left) & Resolution badge (right)
        top_badge_row = QHBoxLayout()
        top_badge_row.setContentsMargins(0, 0, 0, 0)
        top_badge_row.setSpacing(5)

        if getattr(self.item, "is_animated", False):
            self.live_badge = QLabel("[ ▶ LIVE ]")
            self.live_badge.setToolTip(tr("card_live_tooltip"))
            self.live_badge.setStyleSheet("""
                QLabel {
                    background: rgba(4, 12, 8, 0.88);
                    color: #33ff77;
                    border: 1px solid #33ff77;
                    border-radius: 2px;
                    font-weight: 800;
                    font-size: 9.5px;
                    padding: 2px 7px;
                }
            """)
            top_badge_row.addWidget(self.live_badge)

        is_installed_mode = getattr(self.item, "is_installed", False)
        is_already_downloaded = not is_installed_mode and installed_manager.is_installed(self.item.id)
        if is_already_downloaded:
            self.inst_badge = QLabel(tr("card_installed_badge"))
            self.inst_badge.setStyleSheet("""
                QLabel {
                    background: rgba(4, 12, 8, 0.88);
                    color: #7dffa8;
                    border: 1px solid #2f7a4b;
                    border-radius: 2px;
                    font-weight: 800;
                    font-size: 9px;
                    padding: 2px 6px;
                }
            """)
            top_badge_row.addWidget(self.inst_badge)

        top_badge_row.addStretch()

        # Resolution badge (4K Gold, 2K Cyan, Standard Glass)
        is_4k = self.item.dimension_x >= 3840
        is_2k = not is_4k and self.item.dimension_x >= 2560

        if is_4k:
            res_text = "[4K]"
        elif is_2k:
            res_text = "[2K]"
        else:
            res_text = f"[{self.item.resolution}]"

        self.res_badge = QLabel(res_text)
        self.res_badge.setToolTip(f"{self.item.resolution} • {self.item.ratio}")
        if is_4k:
            self.res_badge.setStyleSheet("""
                background-color: rgba(15, 15, 22, 0.88);
                color: #fbbf24;
                border: 1px solid rgba(251, 191, 36, 0.65);
                border-radius: 2px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 800;
            """)
        elif is_2k:
            self.res_badge.setStyleSheet("""
                background-color: rgba(15, 15, 22, 0.88);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.65);
                border-radius: 2px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 800;
            """)
        else:
            self.res_badge.setStyleSheet(f"""
                background-color: rgba(12, 15, 24, 0.85);
                color: {text_pri};
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 2px;
                padding: 2px 6px;
                font-size: 9.5px;
                font-weight: 700;
            """)
        top_badge_row.addWidget(self.res_badge)
        overlay_layout.addLayout(top_badge_row)

        overlay_layout.addStretch()

        # Center/Bottom Floating Action Dock (revealed on hover)
        self.hover_bar = QFrame(self.image_label)
        self.hover_bar.setObjectName("cardHoverBar")
        self.hover_bar.setStyleSheet(f"""
            QFrame#cardHoverBar {{
                background-color: rgba(10, 12, 20, 0.78);
                border: 1px solid {accent};
                border-radius: 2px;
            }}
        """)
        self.hover_bar.setVisible(False)
        hover_bar_wrap = QHBoxLayout()
        hover_bar_wrap.setContentsMargins(0, 0, 0, 2)
        hover_bar_wrap.addStretch()
        hover_bar_wrap.addWidget(self.hover_bar)
        hover_bar_wrap.addStretch()

        hover_layout = QHBoxLayout(self.hover_bar)
        hover_layout.setContentsMargins(8, 4, 8, 4)
        hover_layout.setSpacing(8)
        hover_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if is_installed_mode:
            # Set wallpaper button
            self.set_wall_btn = QPushButton("🖼️")
            self.set_wall_btn.setFixedSize(32, 32)
            self.set_wall_btn.setToolTip(tr("card_set_wall_tooltip"))
            self.set_wall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.set_wall_btn.setStyleSheet(self._action_btn_style("#10b981", "#34d399"))
            self.set_wall_btn.clicked.connect(lambda: self.set_wall_requested.emit(self.item))
            hover_layout.addWidget(self.set_wall_btn)

            # Delete / Uninstall button
            self.uninstall_btn = QPushButton("🗑️")
            self.uninstall_btn.setFixedSize(32, 32)
            self.uninstall_btn.setToolTip(tr("card_uninstall_tooltip"))
            self.uninstall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.uninstall_btn.setStyleSheet(self._action_btn_style("#ef4444", "#f87171"))
            self.uninstall_btn.clicked.connect(lambda: self.uninstall_requested.emit(self.item))
            hover_layout.addWidget(self.uninstall_btn)
        else:
            # Quick download button
            self.dl_btn = QPushButton("⬇")
            self.dl_btn.setFixedSize(32, 32)
            self.dl_btn.setToolTip(tr("card_download_tooltip"))
            self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.dl_btn.setStyleSheet(self._action_btn_style(accent, accent_hover))
            self.dl_btn.clicked.connect(self._on_download_clicked)
            hover_layout.addWidget(self.dl_btn)

            # Quick set wallpaper button
            self.set_wall_btn = QPushButton("🖼️")
            self.set_wall_btn.setFixedSize(32, 32)
            self.set_wall_btn.setToolTip(tr("card_set_wall_tooltip"))
            self.set_wall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.set_wall_btn.setStyleSheet(self._action_btn_style("#0ea5e9", "#38bdf8"))
            self.set_wall_btn.clicked.connect(lambda: self.set_wall_requested.emit(self.item))
            hover_layout.addWidget(self.set_wall_btn)

        # Quick view details button
        self.view_btn = QPushButton("🔍")
        self.view_btn.setFixedSize(32, 32)
        self.view_btn.setToolTip(tr("card_view_tooltip"))
        self.view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_btn.setStyleSheet(self._action_btn_style(accent_hover, "#ffffff"))
        self.view_btn.clicked.connect(lambda: self.clicked.emit(self.item))
        hover_layout.addWidget(self.view_btn)

        overlay_layout.addLayout(hover_bar_wrap)
        card_layout.addWidget(self.image_label)

        # 2. Bottom info row (Metadata, Category, Purity, Favorites)
        info_row = QHBoxLayout()
        info_row.setContentsMargins(4, 0, 4, 2)
        info_row.setSpacing(6)

        # Category badge
        if is_installed_mode:
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
                border-radius: 2px;
                font-weight: bold;
                font-size: 9.5px;
                padding: 1px 5px;
            """)
            info_row.addWidget(purity_lbl)
        elif self.item.purity == "nsfw":
            purity_lbl = QLabel("NSFW")
            purity_lbl.setStyleSheet("""
                background: #e11d48;
                color: white;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9.5px;
                padding: 1px 5px;
            """)
            info_row.addWidget(purity_lbl)

        info_row.addStretch()

        # Mini color palette dots (up to 3 colors from item.colors)
        colors = getattr(self.item, "colors", None) or []
        if colors:
            dots_wrap = QHBoxLayout()
            dots_wrap.setContentsMargins(0, 0, 2, 0)
            dots_wrap.setSpacing(3)
            for hex_c in colors[:3]:
                c_str = hex_c if str(hex_c).startswith("#") else f"#{hex_c}"
                dot = QLabel()
                dot.setFixedSize(8, 8)
                dot.setStyleSheet(f"""
                    background-color: {c_str};
                    border: 1px solid rgba(255, 255, 255, 0.35);
                    border-radius: 2px;
                """)
                dots_wrap.addWidget(dot)
            info_row.addLayout(dots_wrap)

        # Favorites or Views count
        if self.item.favorites > 0:
            fav_lbl = QLabel(f"★ {self.item.favorites:,}")
            fav_lbl.setStyleSheet("color: #fbbf24; font-size: 11px; font-weight: 800; background: transparent;")
            info_row.addWidget(fav_lbl)
        elif getattr(self.item, "views", 0) > 0:
            v_lbl = QLabel(f"👁 {self.item.views:,}")
            v_lbl.setStyleSheet("color: #38bdf8; font-size: 10.5px; font-weight: 700; background: transparent;")
            info_row.addWidget(v_lbl)

        card_layout.addLayout(info_row)

    def _action_btn_style(self, bg_hover: str, border_hover: str) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(20, 27, 45, 0.92);
                color: #ffffff;
                border: 1.5px solid rgba(255, 255, 255, 0.22);
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border-color: {border_hover};
            }}
        """

    def _load_thumbnail(self):
        if not self._thumb_url:
            self.image_label.setText(tr("card_no_preview"))
            return

        target_size = (self._img_w, self._img_h)
        loader.load_thumbnail(
            self._thumb_url,
            target_size=target_size,
            radius=2,
            callback=self._set_pixmap_instant
        )

    def _set_pixmap_instant(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.image_label.set_loaded_pixmap(pixmap, animate=True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pal = get_palette(config.theme)
        accent = QColor(pal.get("accent", "#33ff77"))
        border = QColor(pal.get("border", "#1f4d2e"))

        rect = QRectF(0.5, 0.5, float(self.width()) - 1.0, float(self.height()) - 1.0)
        if self._hovered:
            painter.setPen(QPen(accent, 1.0))
            painter.drawRect(rect)
            # Terminal-style corner brackets
            L = 12.0
            painter.setPen(QPen(accent, 2.0))
            x0, y0, x1, y1 = rect.left(), rect.top(), rect.right(), rect.bottom()
            for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                painter.drawLine(QPointF(cx, cy), QPointF(cx + dx * L, cy))
                painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + dy * L))
        else:
            painter.setPen(QPen(border, 1.0))
            painter.drawRect(rect)
        painter.end()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hovered = True
        self.hover_bar.setVisible(True)
        if getattr(self.item, "is_animated", False) and HAS_AV:
            self._hover_timer.start()

        pal = get_palette(config.theme)
        glow_col = QColor(pal.get("accent_hover", pal.get("accent", "#6366f1")))
        glow_col.setAlpha(195)

        # Animate drop shadow neon bloom on hover
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(200)
        self._anim_blur.setEndValue(32.0)
        self._anim_blur.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim_offset.setDuration(200)
        self._anim_offset.setEndValue(8.0)
        self._anim_offset.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow.setColor(glow_col)
        self._anim_blur.start()
        self._anim_offset.start()
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hovered = False
        self.hover_bar.setVisible(False)
        self._stop_live_preview()

        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(180)
        self._anim_blur.setEndValue(12.0)
        self._anim_blur.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim_offset.setDuration(180)
        self._anim_offset.setEndValue(4.0)
        self._anim_offset.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow.setColor(QColor(0, 0, 0, 95))
        self._anim_blur.start()
        self._anim_offset.start()
        self.update()

    def _start_live_preview(self):
        if not self._hovered or self._anim_playing:
            return
        if self._anim_player is None:
            self._anim_player = AnimPlayer((self._img_w, self._img_h), cover=True, parent=self)
            self._anim_player.frame.connect(self._on_live_frame)
            self._anim_player.error.connect(lambda _e: self._stop_live_preview())
        self._anim_playing = True
        self._anim_player.start(item=self.item)

    def _on_live_frame(self, img):
        if not self._anim_playing:
            return
        self.image_label.set_loaded_pixmap(QPixmap.fromImage(img), animate=False)

    def _stop_live_preview(self):
        self._hover_timer.stop()
        if self._anim_player is not None:
            self._anim_player.stop()
        if self._anim_playing:
            self._anim_playing = False
            if self._pixmap is not None:
                self.image_label.set_loaded_pixmap(self._pixmap, animate=False)

    def _cleanup_loader(self):
        self._stop_live_preview()
        if self._thumb_url:
            loader.unregister_callback(self._thumb_url, self._set_pixmap_instant)

    def closeEvent(self, event):
        self._cleanup_loader()
        super().closeEvent(event)

    def _on_download_clicked(self):
        self.download_requested.emit(self.item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only trigger card click if not clicking directly on action buttons
            pos = event.pos()
            btn_clicked = False
            for btn_name in ("dl_btn", "set_wall_btn", "uninstall_btn", "view_btn"):
                if hasattr(self, btn_name):
                    btn = getattr(self, btn_name)
                    # Map position to card coords
                    btn_card_pos = btn.mapTo(self, btn.rect().topLeft())
                    btn_rect = btn.rect().translated(btn_card_pos)
                    if btn_rect.contains(pos):
                        btn_clicked = True
                        break

            if not btn_clicked:
                self.clicked.emit(self.item)
        super().mousePressEvent(event)
