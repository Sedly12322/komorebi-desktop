"""PfpCard widget for displaying 1:1 square avatars and animated GIFs in Komorebi."""
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QMovie, QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from wallhaven.pfps import PfpItem, pfps_client
from wallhaven.image_loader import loader
from wallhaven.i18n import tr


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

        self._init_ui()
        self._load_image()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Square Avatar Container
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(self.IMAGE_SIZE, self.IMAGE_SIZE)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #10121a;
                border: 1px solid #1c2130;
                border-radius: 12px;
                color: #475569;
                font-size: 12px;
                font-weight: 500;
            }
        """)
        self.image_label.setText("⏳ " + tr("card_loading"))
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
        self.image_label.setStyleSheet("QLabel { background-color: transparent; border: none; }")
        self.image_label.setPixmap(pixmap)
        self.image_label.setText("")

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
