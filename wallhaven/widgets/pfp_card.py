"""PfpCard widget for displaying 1:1 square avatars and animated GIFs in Komorebi Desktop."""
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QMovie, QCursor, QColor, QPainter, QPainterPath, QLinearGradient, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGraphicsDropShadowEffect,
)
from wallhaven.pfps import PfpItem, pfps_client, format_download_count
from wallhaven.config import config
from wallhaven.styles import get_palette
from wallhaven.cache import cache
from wallhaven.image_loader import loader
from wallhaven.i18n import tr
from wallhaven.widgets.shimmer import ShimmerLabel


class PfpCard(QFrame):
    clicked = pyqtSignal(PfpItem)
    download_requested = pyqtSignal(PfpItem)
    set_avatar_requested = pyqtSignal(PfpItem)
    copy_requested = pyqtSignal(PfpItem)

    CARD_WIDTH = 204
    CARD_HEIGHT = 246
    IMAGE_SIZE = 192

    SIZE_PRESETS = {
        "compact": (172, 214, 160),
        "normal": (204, 246, 192),
        "large": (252, 294, 240),
    }

    def __init__(self, item: PfpItem, parent=None, size_mode: str = ""):
        super().__init__(parent)
        self.item = item
        self.size_mode = size_mode or config.card_size
        cw, ch, isz = self.SIZE_PRESETS.get(self.size_mode, self.SIZE_PRESETS["normal"])
        self._card_w = cw
        self._card_h = ch
        self._img_sz = isz
        self._hovered = False

        self.setObjectName("pfpCard")
        self.setFixedSize(self._card_w, self._card_h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pixmap: QPixmap | None = None
        self._movie: QMovie | None = None

        # Neon / Gaming drop shadow with animated hover bloom
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(12)
        self._shadow.setOffset(0, 4)
        self._shadow.setColor(QColor(0, 0, 0, 95))
        self.setGraphicsEffect(self._shadow)

        self._anim_blur: QPropertyAnimation | None = None
        self._anim_offset: QPropertyAnimation | None = None

        self._init_ui()
        self._load_image()

    def _init_ui(self):
        pal = get_palette(config.theme)
        accent = pal.get("accent", "#6366f1")
        accent_hover = pal.get("accent_hover", "#818cf8")
        text_pri = pal.get("text_primary", "#f8fafc")
        text_mut = pal.get("text_muted", "#64748b")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Square Avatar with animated shimmer skeleton
        self.image_label = ShimmerLabel(self, corner_radius=12)
        self.image_label.setFixedSize(self._img_sz, self._img_sz)

        # In-image overlay
        overlay_layout = QVBoxLayout(self.image_label)
        overlay_layout.setContentsMargins(8, 8, 8, 8)
        overlay_layout.setSpacing(0)

        # Top row: Format badge (GIF / PNG)
        top_row = QHBoxLayout()
        top_row.addStretch()

        fmt_text = "🎞️ GIF" if self.item.is_animated else self.item.format.upper()
        self.fmt_badge = QLabel(fmt_text)
        if self.item.is_animated:
            self.fmt_badge.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(139, 92, 246, 0.92), stop:1 rgba(236, 72, 153, 0.92));
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.30);
                border-radius: 5px;
                font-weight: 800;
                font-size: 9px;
                padding: 2px 6px;
            """)
        else:
            self.fmt_badge.setStyleSheet(f"""
                background-color: rgba(15, 18, 28, 0.86);
                color: {accent_hover};
                border: 1px solid {accent};
                border-radius: 5px;
                font-weight: 800;
                font-size: 9px;
                padding: 2px 6px;
            """)
        top_row.addWidget(self.fmt_badge)
        overlay_layout.addLayout(top_row)

        overlay_layout.addStretch()

        # Center/Bottom Floating action dock on hover
        self.hover_bar = QFrame(self.image_label)
        self.hover_bar.setObjectName("cardHoverBar")
        self.hover_bar.setStyleSheet(f"""
            QFrame#cardHoverBar {{
                background-color: rgba(10, 12, 20, 0.78);
                border: 1px solid {accent};
                border-radius: 19px;
            }}
        """)
        self.hover_bar.setVisible(False)
        hover_bar_wrap = QHBoxLayout()
        hover_bar_wrap.setContentsMargins(0, 0, 0, 2)
        hover_bar_wrap.addStretch()
        hover_bar_wrap.addWidget(self.hover_bar)
        hover_bar_wrap.addStretch()

        hover_layout = QHBoxLayout(self.hover_bar)
        hover_layout.setContentsMargins(6, 3, 6, 3)
        hover_layout.setSpacing(6)
        hover_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Copy button (Ctrl+C / Discord paste)
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setToolTip(tr("pfp_copy_tip"))
        self.copy_btn.setFixedSize(30, 30)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet(self._action_btn_style("#3b82f6", "#60a5fa"))
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        hover_layout.addWidget(self.copy_btn)

        # Set as avatar button
        self.set_btn = QPushButton("👤")
        self.set_btn.setToolTip(tr("pfp_set_avatar_tip"))
        self.set_btn.setFixedSize(30, 30)
        self.set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_btn.setStyleSheet(self._action_btn_style(accent, accent_hover))
        self.set_btn.clicked.connect(self._on_set_avatar_clicked)
        hover_layout.addWidget(self.set_btn)

        # Download button
        self.dl_btn = QPushButton("⬇")
        self.dl_btn.setToolTip(tr("pfp_download_tip"))
        self.dl_btn.setFixedSize(30, 30)
        self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_btn.setStyleSheet(self._action_btn_style("#10b981", "#34d399"))
        self.dl_btn.clicked.connect(self._on_download_clicked)
        hover_layout.addWidget(self.dl_btn)

        # Detail view button
        self.view_btn = QPushButton("🔍")
        self.view_btn.setToolTip(tr("pfp_view_detail_tip"))
        self.view_btn.setFixedSize(30, 30)
        self.view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_btn.setStyleSheet(self._action_btn_style(accent_hover, "#ffffff"))
        self.view_btn.clicked.connect(lambda: self.clicked.emit(self.item))
        hover_layout.addWidget(self.view_btn)

        overlay_layout.addLayout(hover_bar_wrap)
        layout.addWidget(self.image_label)

        # 2. Bottom Meta Row (Title & Downloads count)
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(4, 0, 4, 2)
        meta_row.setSpacing(6)

        self.title_lbl = QLabel(self.item.title)
        self.title_lbl.setStyleSheet(f"font-size: 11.5px; font-weight: bold; color: {text_pri};")
        self.title_lbl.setToolTip(self.item.title)
        meta_row.addWidget(self.title_lbl, 1)

        dl_text = f"⬇ {self._format_downloads(self.item.downloads)}"
        self.dl_lbl = QLabel(dl_text)
        self.dl_lbl.setStyleSheet(f"color: {text_mut}; font-size: 10px; font-weight: 700;")
        meta_row.addWidget(self.dl_lbl)

        layout.addLayout(meta_row)

    def _action_btn_style(self, bg_hover: str, border_hover: str) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(20, 27, 45, 0.92);
                color: #ffffff;
                border: 1.5px solid rgba(255, 255, 255, 0.22);
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border-color: {border_hover};
            }}
        """

    def _load_image(self):
        target_size = (self._img_sz, self._img_sz)
        loader.load_thumbnail(
            self.item.url,
            target_size=target_size,
            radius=12,
            callback=self._set_pixmap_instant
        )

    def _set_pixmap_instant(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.image_label.set_loaded_pixmap(pixmap, animate=True)

        # If it's a GIF, check if local file is already cached so we can play preview on hover
        if self.item.is_animated:
            try:
                cached_path = cache.get_cached_path(self.item.url, is_thumb=True)
                if cached_path and cached_path.exists():
                    self._movie = QMovie(str(cached_path))
                    self._movie.setScaledSize(QSize(self._img_sz, self._img_sz))
            except Exception:
                pass

    def _format_downloads(self, count) -> str:
        return format_download_count(count)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pal = get_palette(config.theme)
            c1 = QColor(pal.get("accent", "#6366f1"))
            c2 = QColor(pal.get("accent_hover", "#ec4899"))
            rect = QRectF(1.0, 1.0, float(self.width()) - 2.0, float(self.height()) - 2.0)
            path = QPainterPath()
            path.addRoundedRect(rect, 13.0, 13.0)
            grad = QLinearGradient(0.0, 0.0, float(self.width()), float(self.height()))
            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)
            pen = QPen(grad, 2.2)
            painter.strokePath(path, pen)
            painter.end()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hovered = True
        self.hover_bar.setVisible(True)

        pal = get_palette(config.theme)
        glow_col = QColor(pal.get("accent_hover", pal.get("accent", "#8b5cf6")))
        glow_col.setAlpha(195)

        # Animate drop shadow neon bloom on hover
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(200)
        self._anim_blur.setEndValue(30.0)
        self._anim_blur.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim_offset.setDuration(200)
        self._anim_offset.setEndValue(7.0)
        self._anim_offset.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow.setColor(glow_col)
        self._anim_blur.start()
        self._anim_offset.start()
        self.update()

        # Play GIF animation if available
        if self._movie and self.item.is_animated:
            self.image_label.setMovie(self._movie)
            self._movie.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hovered = False
        self.hover_bar.setVisible(False)

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

        if self._movie and self.item.is_animated:
            self._movie.stop()
            if self._pixmap:
                self.image_label.setPixmap(self._pixmap)

    def _cleanup_loader(self):
        if self.item.url:
            loader.unregister_callback(self.item.url, self._set_pixmap_instant)
        if self._movie:
            self._movie.stop()
            self._movie = None

    def closeEvent(self, event):
        self._cleanup_loader()
        super().closeEvent(event)

    def _on_download_clicked(self):
        self.download_requested.emit(self.item)

    def _on_set_avatar_clicked(self):
        self.set_avatar_requested.emit(self.item)

    def _on_copy_clicked(self):
        pm = self._pixmap or cache.get_pixmap(self.item.url, is_thumb=True)
        if pm and not pm.isNull():
            pfps_client.copy_image_to_clipboard(pm)
        self.copy_requested.emit(self.item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            btn_clicked = False
            for btn_name in ("copy_btn", "set_btn", "dl_btn", "view_btn"):
                if hasattr(self, btn_name):
                    btn = getattr(self, btn_name)
                    btn_card_pos = btn.mapTo(self, btn.rect().topLeft())
                    btn_rect = btn.rect().translated(btn_card_pos)
                    if btn_rect.contains(pos):
                        btn_clicked = True
                        break

            if not btn_clicked:
                self.clicked.emit(self.item)
        super().mousePressEvent(event)
