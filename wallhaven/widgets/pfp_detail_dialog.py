"""High-resolution avatar and animated GIF preview modal dialog for Komorebi."""
import os
import sys
import shutil
import urllib.request
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl, QSize
from PyQt6.QtGui import QPixmap, QMovie, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QMessageBox,
    QApplication,
)
from wallhaven.pfps import PfpItem, pfps_client
from wallhaven.i18n import tr


class PfpDetailDialog(QDialog):
    def __init__(self, item: PfpItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(f"Komorebi — {item.title}")
        self.setFixedSize(480, 580)
        self.setModal(True)

        self._local_file: str | None = None
        self._pixmap: QPixmap | None = None
        self._movie: QMovie | None = None

        self._init_ui()
        self._load_full_asset()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header Row
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title_lbl = QLabel(self.item.title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        title_lbl.setWordWrap(True)
        header_row.addWidget(title_lbl, 1)

        fmt_text = "🎞️ GIF (Animovaný)" if self.item.is_animated else f"🖼️ {self.item.format.upper()}"
        fmt_badge = QLabel(fmt_text)
        fmt_badge.setStyleSheet("""
            background: #1e2434;
            color: #a5b4fc;
            border: 1px solid #3b4252;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 8px;
        """)
        header_row.addWidget(fmt_badge)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #151824;
                color: #94a3b8;
                border: 1px solid #232838;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #e11d48;
                color: #ffffff;
                border-color: #f43f5e;
            }
        """)
        close_btn.clicked.connect(self.accept)
        header_row.addWidget(close_btn)

        layout.addLayout(header_row)

        # 2. Main Avatar Preview Box
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("avatarPreviewBox")
        self.preview_frame.setFixedSize(440, 380)
        self.preview_frame.setStyleSheet("""
            QFrame#avatarPreviewBox {
                background-color: #0b0d14;
                border: 1.5px solid #1e2434;
                border-radius: 16px;
            }
        """)
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label = QLabel("⏳ Načítám avatar...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 600;")
        self.preview_label.setFixedSize(340, 340)
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(self.preview_frame)

        # 3. Meta Row
        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)

        dl_lbl = QLabel(f"⬇ {self.item.downloads} stažení")
        dl_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        meta_row.addWidget(dl_lbl)

        meta_row.addStretch()

        web_btn = QPushButton("🌐 pfps.gg")
        web_btn.setToolTip("Otevřít stránku profilovky v prohlížeči")
        web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        web_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #38bdf8;
                border: none;
                font-size: 12px;
                font-weight: bold;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #7dd3fc;
            }
        """)
        web_btn.clicked.connect(self._open_webpage)
        meta_row.addWidget(web_btn)

        layout.addLayout(meta_row)

        # 4. Action Buttons Row
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        # Set System Avatar button
        self.set_avatar_btn = QPushButton("👤 Nastavit profilovku")
        self.set_avatar_btn.setFixedHeight(38)
        self.set_avatar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_avatar_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                border-radius: 9px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #a78bfa);
            }
        """)
        self.set_avatar_btn.clicked.connect(self._on_set_system_avatar)
        action_row.addWidget(self.set_avatar_btn)

        # Copy button
        self.copy_btn = QPushButton("📋 Zkopírovat")
        self.copy_btn.setFixedHeight(38)
        self.copy_btn.setToolTip("Zkopírovat obrázek do schránky (vložení Ctrl+V do Discordu)")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: #1e2434;
                color: #f8fafc;
                font-size: 13px;
                font-weight: bold;
                border: 1.5px solid #2d3748;
                border-radius: 9px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #3b82f6;
                border-color: #60a5fa;
            }
        """)
        self.copy_btn.clicked.connect(self._on_copy_clipboard)
        action_row.addWidget(self.copy_btn)

        # Download button
        self.download_btn = QPushButton("💾 Stáhnout")
        self.download_btn.setFixedHeight(38)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background: #1e2434;
                color: #f8fafc;
                font-size: 13px;
                font-weight: bold;
                border: 1.5px solid #2d3748;
                border-radius: 9px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #10b981;
                border-color: #34d399;
            }
        """)
        self.download_btn.clicked.connect(self._on_download)
        action_row.addWidget(self.download_btn)

        layout.addLayout(action_row)

    def _load_full_asset(self):
        """Downloads/caches the full avatar and displays animated GIF or PNG."""
        cache_dir = Path.home() / ".cache" / "komorebi" / "pfps"
        cache_dir.mkdir(parents=True, exist_ok=True)
        local_path = cache_dir / self.item.filename

        if not local_path.exists():
            try:
                req = urllib.request.Request(self.item.image_url, headers={"User-Agent": pfps_client.USER_AGENT})
                with urllib.request.urlopen(req, timeout=15) as resp, open(local_path, "wb") as f:
                    f.write(resp.read())
            except Exception as e:
                self.preview_label.setText(f"Chyba stahování: {e}")
                return

        self._local_file = str(local_path)

        if self.item.is_animated:
            self._movie = QMovie(str(local_path))
            self._movie.setScaledSize(QSize(340, 340))
            self.preview_label.setText("")
            self.preview_label.setMovie(self._movie)
            self._movie.start()
        else:
            pix = QPixmap(str(local_path))
            if not pix.isNull():
                self._pixmap = pix
                scaled = pix.scaled(
                    340,
                    340,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setText("")
                self.preview_label.setPixmap(scaled)

    def _on_copy_clipboard(self):
        if self._pixmap and not self._pixmap.isNull():
            pfps_client.copy_image_to_clipboard(self._pixmap)
            self.copy_btn.setText("✓ Zkopírováno!")
        elif self._local_file and os.path.exists(self._local_file):
            pix = QPixmap(self._local_file)
            pfps_client.copy_image_to_clipboard(pix)
            self.copy_btn.setText("✓ Zkopírováno!")

    def _on_set_system_avatar(self):
        ok, msg = pfps_client.set_system_avatar(self.item, self._local_file)
        if ok:
            self.set_avatar_btn.setText("✓ Profilovka nastavena!")
            self.set_avatar_btn.setStyleSheet("background: #059669; color: #fff; font-weight: bold; border-radius: 9px;")
            QMessageBox.information(self, "Profilovka změněna", msg)
        else:
            QMessageBox.warning(self, "Chyba", msg)

    def _on_download(self):
        ok, path_or_err = pfps_client.download_pfp(self.item)
        if ok:
            self.download_btn.setText("✓ Uloženo!")
            self.download_btn.setStyleSheet("background: #059669; color: #fff; font-weight: bold; border-radius: 9px;")
            QMessageBox.information(
                self,
                "Profilovka uložena",
                f"Profilovka byla úspěšně stažena do:\n{path_or_err}",
            )
        else:
            QMessageBox.critical(self, "Chyba", f"Stahování selhalo:\n{path_or_err}")

    def _open_webpage(self):
        if self.item.page_url:
            QDesktopServices.openUrl(QUrl(self.item.page_url))

    def closeEvent(self, event):
        if self._movie:
            self._movie.stop()
            self._movie = None
        super().closeEvent(event)
