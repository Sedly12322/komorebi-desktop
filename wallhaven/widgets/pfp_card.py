"""PfpCard widget for displaying 1:1 square avatars and animated GIFs in Komorebi Desktop."""
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QMovie, QCursor, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGraphicsDropShadowEffect,
)
from wallhaven.pfps import PfpItem, pfps_client
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

    def __init__(self, item: PfpItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("wallpaperCard")
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pixmap: QPixmap | None = None
        self._movie: QMovie | None = None

        # Soft drop shadow with animated hover bloom
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(10)
        self._shadow.setOffset(0, 3)
        self._shadow.setColor(QColor(0, 0, 0, 75))
        self.setGraphicsEffect(self._shadow)

        self._anim_blur: QPropertyAnimation | None = None
        self._anim_offset: QPropertyAnimation | None = None

        self._init_ui()
        self._load_image()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Square Avatar with animated shimmer skeleton
        self.image_label = ShimmerLabel(self, corner_radius=12)
        self.image_label.setFixedSize(self.IMAGE_SIZE, self.IMAGE_SIZE)

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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(139, 92, 246, 0.9), stop:1 rgba(236, 72, 153, 0.9));
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 5px;
                font-weight: 800;
                font-size: 9px;
                padding: 2px 6px;
            """)
        else:
            self.fmt_badge.setStyleSheet("""
                background-color: rgba(15, 18, 28, 0.85);
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.35);
                border-radius: 5px;
                font-weight: 700;
                font-size: 9px;
                padding: 2px 6px;
            """)
        top_row.addWidget(self.fmt_badge)
        overlay_layout.addLayout(top_row)

        overlay_layout.addStretch()

        # Center/Bottom Floating action buttons on hover
        self.hover_bar = QWidget(self.image_label)
        self.hover_bar.setVisible(False)
        hover_layout = QHBoxLayout(self.hover_bar)
        hover_layout.setContentsMargins(0, 0, 0, 4)
        hover_layout.setSpacing(8)
        hover_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Copy button (Ctrl+C / Discord paste)
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setToolTip("Zkopírovat do schránky (Ctrl+V)")
        self.copy_btn.setFixedSize(32, 32)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet(self._action_btn_style("#3b82f6", "#60a5fa"))
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        hover_layout.addWidget(self.copy_btn)

        # Set as avatar button
        self.set_btn = QPushButton("👤")
        self.set_btn.setToolTip("Nastavit jako profilovku systému")
        self.set_btn.setFixedSize(32, 32)
        self.set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_btn.setStyleSheet(self._action_btn_style("#8b5cf6", "#c4b5fd"))
        self.set_btn.clicked.connect(self._on_set_avatar_clicked)
        hover_layout.addWidget(self.set_btn)

        # Download button
        self.dl_btn = QPushButton("⬇")
        self.dl_btn.setToolTip("Stáhnout do složky Avatary")
        self.dl_btn.setFixedSize(32, 32)
        self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_btn.setStyleSheet(self._action_btn_style("#10b981", "#34d399"))
        self.dl_btn.clicked.connect(self._on_download_clicked)
        hover_layout.addWidget(self.dl_btn)

        # Detail view button
        self.view_btn = QPushButton("🔍")
        self.view_btn.setToolTip("Zobrazit detail")
        self.view_btn.setFixedSize(32, 32)
        self.view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_btn.setStyleSheet(self._action_btn_style("#64748b", "#94a3b8"))
        self.view_btn.clicked.connect(lambda: self.clicked.emit(self.item))
        hover_layout.addWidget(self.view_btn)

        overlay_layout.addWidget(self.hover_bar)
        layout.addWidget(self.image_label)

        # 2. Bottom Meta Row (Title & Downloads count)
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(4, 0, 4, 2)
        meta_row.setSpacing(6)

        self.title_lbl = QLabel(self.item.title)
        self.title_lbl.setStyleSheet("font-size: 11.5px; font-weight: bold; color: #f8fafc;")
        self.title_lbl.setToolTip(self.item.title)
        meta_row.addWidget(self.title_lbl, 1)

        dl_text = f"⬇ {self._format_downloads(self.item.downloads)}"
        self.dl_lbl = QLabel(dl_text)
        self.dl_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700;")
        meta_row.addWidget(self.dl_lbl)

        layout.addLayout(meta_row)

    def _action_btn_style(self, bg_hover: str, border_hover: str) -> str:
        return f"""
            QPushButton {{
                background-color: rgba(15, 23, 42, 0.88);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 16px;
                font-size: 12.5px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                border-color: {border_hover};
            }}
        """

    def _load_image(self):
        target_size = (self.IMAGE_SIZE, self.IMAGE_SIZE)
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
            cached_path = loader.get_cache_path(self.item.url)
            if cached_path and cached_path.exists():
                self._movie = QMovie(str(cached_path))
                self._movie.setScaledSize(QSize(self.IMAGE_SIZE, self.IMAGE_SIZE))

    def _format_downloads(self, count) -> str:
        if isinstance(count, str):
            if count.isdigit():
                count = int(count)
            else:
                return count
        try:
            val = int(count)
            if val >= 1_000_000:
                return f"{val / 1_000_000:.1f}M"
            if val >= 1_000:
                return f"{val / 1_000:.1f}k"
            return str(val)
        except Exception:
            return str(count)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.hover_bar.setVisible(True)

        # Animate drop shadow bloom on hover
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(180)
        self._anim_blur.setEndValue(22.0)
        self._anim_blur.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim_offset.setDuration(180)
        self._anim_offset.setEndValue(6.0)
        self._anim_offset.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow.setColor(QColor(139, 92, 246, 110))
        self._anim_blur.start()
        self._anim_offset.start()

        # Play GIF animation if available
        if self._movie and self.item.is_animated:
            self.image_label.setMovie(self._movie)
            self._movie.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hover_bar.setVisible(False)

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
