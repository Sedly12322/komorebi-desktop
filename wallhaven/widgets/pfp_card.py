"""PfpCard widget for displaying 1:1 square avatars and animated GIFs in Komorebi."""
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QMovie, QCursor, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
    CARD_HEIGHT = 252
    IMAGE_SIZE = 192

    def __init__(self, item: PfpItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("wallpaperCard")  # Inherits nice card background & border from theme
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
        layout.addWidget(self.image_label)

        # 2. Bottom Meta & Action Bar
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(2, 0, 2, 2)
        bottom_layout.setSpacing(4)

        # Row 1: Title & Format Badge
        title_row = QHBoxLayout()
        title_row.setSpacing(4)

        self.title_lbl = QLabel(self.item.title)
        self.title_lbl.setStyleSheet("font-size: 11.5px; font-weight: bold; color: #f8fafc;")
        self.title_lbl.setToolTip(self.item.title)
        title_row.addWidget(self.title_lbl, 1)

        # Format Badge (GIF or PNG)
        fmt_text = "🎞️ GIF" if self.item.is_animated else self.item.format.upper()
        self.fmt_badge = QLabel(fmt_text)
        if self.item.is_animated:
            self.fmt_badge.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                color: #ffffff;
                border-radius: 4px;
                font-weight: 800;
                font-size: 9px;
                padding: 1px 4px;
            """)
        else:
            self.fmt_badge.setStyleSheet("""
                background-color: rgba(99, 102, 241, 0.15);
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 4px;
                font-weight: 700;
                font-size: 9px;
                padding: 1px 4px;
            """)
        title_row.addWidget(self.fmt_badge)
        bottom_layout.addLayout(title_row)

        # Row 2: Downloads & Quick Buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(4)

        # Downloads count
        dl_text = f"⬇ {self._format_downloads(self.item.downloads)}"
        self.dl_lbl = QLabel(dl_text)
        self.dl_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        action_row.addWidget(self.dl_lbl)
        action_row.addStretch()

        # Copy button (copies to clipboard for Discord/chat paste)
        self.copy_btn = QPushButton("📋")
        self.copy_btn.setToolTip("Zkopírovat do schránky (Ctrl+V)")
        self.copy_btn.setFixedSize(24, 24)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: #1e2434;
                color: #cbd5e1;
                border: 1px solid #2d3748;
                border-radius: 6px;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover {
                background: #3b82f6;
                color: #ffffff;
                border-color: #60a5fa;
            }
        """)
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        action_row.addWidget(self.copy_btn)

        # Set as avatar button
        self.set_btn = QPushButton("👤")
        self.set_btn.setToolTip("Nastavit jako profilovku systému")
        self.set_btn.setFixedSize(24, 24)
        self.set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_btn.setStyleSheet("""
            QPushButton {
                background: #1e2434;
                color: #cbd5e1;
                border: 1px solid #2d3748;
                border-radius: 6px;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover {
                background: #8b5cf6;
                color: #ffffff;
                border-color: #c4b5fd;
            }
        """)
        self.set_btn.clicked.connect(self._on_set_avatar_clicked)
        action_row.addWidget(self.set_btn)

        # Download button
        self.dl_btn = QPushButton("💾")
        self.dl_btn.setToolTip("Stáhnout do složky Avatary")
        self.dl_btn.setFixedSize(24, 24)
        self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_btn.setStyleSheet("""
            QPushButton {
                background: #1e2434;
                color: #cbd5e1;
                border: 1px solid #2d3748;
                border-radius: 6px;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover {
                background: #10b981;
                color: #ffffff;
                border-color: #34d399;
            }
        """)
        self.dl_btn.clicked.connect(self._on_download_clicked)
        action_row.addWidget(self.dl_btn)

        bottom_layout.addLayout(action_row)
        layout.addLayout(bottom_layout)

    def _format_downloads(self, dls_str: str) -> str:
        try:
            num = int(dls_str)
            if num >= 1_000_000:
                return f"{num / 1_000_000:.1f}M"
            elif num >= 1_000:
                return f"{num / 1_000:.1f}k"
            return str(num)
        except Exception:
            return dls_str

    def _load_image(self):
        """Loads avatar image from cache or network."""
        target_size = (self.IMAGE_SIZE, self.IMAGE_SIZE)
        loader.load_thumbnail(
            self.item.image_url,
            target_size=target_size,
            radius=12,
            callback=self._set_pixmap_instant,
        )

    def _set_pixmap_instant(self, pixmap: QPixmap):
        if pixmap.isNull():
            self.image_label.setText("⚠️ " + tr("card_error"))
            return
        self._pixmap = pixmap
        self.image_label.set_loaded_pixmap(pixmap, animate=True)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        self._anim_blur.setDuration(180)
        self._anim_blur.setEndValue(24.0)
        self._anim_blur.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_offset = QPropertyAnimation(self._shadow, b"yOffset")
        self._anim_offset.setDuration(180)
        self._anim_offset.setEndValue(7.0)
        self._anim_offset.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shadow.setColor(QColor(236, 72, 153, 90) if self.item.is_animated else QColor(99, 102, 241, 90))
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

    def _on_copy_clicked(self):
        if self._pixmap and not self._pixmap.isNull():
            pfps_client.copy_image_to_clipboard(self._pixmap)
            self.copy_btn.setText("✓")
            self.copy_btn.setStyleSheet("background: #059669; color: #fff; border-radius: 6px; border: none;")
        self.copy_requested.emit(self.item)

    def _on_set_avatar_clicked(self):
        self.set_avatar_requested.emit(self.item)

    def _on_download_clicked(self):
        self.download_requested.emit(self.item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)
        super().mousePressEvent(event)

    def _cleanup_loader(self):
        if hasattr(self, "item") and self.item.image_url:
            loader.unregister_callback(self.item.image_url, self._set_pixmap_instant)
        if self._movie:
            self._movie.stop()
            self._movie = None

    def closeEvent(self, event):
        self._cleanup_loader()
        super().closeEvent(event)
