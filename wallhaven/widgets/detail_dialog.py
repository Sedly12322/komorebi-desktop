import os
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices, QColor
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFileDialog,
    QScrollArea,
    QWidget,
    QFrame,
    QMessageBox,
    QCheckBox,
    QStackedWidget,
)
from wallhaven.api import WallpaperItem, api
from wallhaven.config import config
from wallhaven.image_loader import loader
from wallhaven.wallpaper import set_desktop_wallpaper
from wallhaven.i18n import tr, i18n

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False


class DetailFetchWorker(QThread):
    finished = pyqtSignal(WallpaperItem)
    failed = pyqtSignal(str)

    def __init__(self, item: WallpaperItem):
        super().__init__()
        self.item = item

    def run(self):
        try:
            if getattr(self.item, "is_animated", False) or self.item.source == "MoeWalls":
                from wallhaven.moewalls import moewalls_manager
                full_item = moewalls_manager.get_wallpaper_detail(self.item)
            else:
                full_item = api.get_wallpaper_detail(self.item.id)
            self.finished.emit(full_item)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)  # downloaded, total
    finished = pyqtSignal(str)       # saved file path
    failed = pyqtSignal(str)

    def __init__(self, item_or_url: WallpaperItem | str, dest_path: str):
        super().__init__()
        self.item_or_url = item_or_url
        self.dest_path = dest_path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            url = ""
            headers = None
            if isinstance(self.item_or_url, WallpaperItem):
                if getattr(self.item_or_url, "is_animated", False):
                    from wallhaven.moewalls import moewalls_manager
                    url = moewalls_manager.get_download_url(self.item_or_url)
                    headers = {"Referer": "https://moewalls.com/"}
                else:
                    url = self.item_or_url.path
            else:
                url = str(self.item_or_url)
                if "moewalls.com" in url:
                    headers = {"Referer": "https://moewalls.com/"}

            ok = api.download_file(
                url,
                self.dest_path,
                progress_callback=lambda d, t: self.progress.emit(d, t),
                is_cancelled=lambda: self._cancelled,
                headers=headers,
            )
            if ok:
                self.finished.emit(self.dest_path)
            else:
                self.failed.emit(tr("download_cancelled"))
        except Exception as e:
            self.failed.emit(str(e))


class DetailDialog(QDialog):
    tag_clicked = pyqtSignal(str)
    download_completed = pyqtSignal(str)
    uninstalled = pyqtSignal(WallpaperItem)

    def __init__(self, item: WallpaperItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.download_worker: DownloadWorker | None = None
        self.fetch_worker: DetailFetchWorker | None = None
        self.saved_path: str = ""
        self.player: QMediaPlayer | None = None
        self.audio_output: QAudioOutput | None = None

        if getattr(self.item, "_osu_meta", None):
            self.setWindowTitle(f"osu! {self.item._osu_meta.get('season', '')} - #{self.item.id} ({self.item.resolution})")
        elif getattr(self.item, "is_animated", False):
            title = getattr(self.item, "_display_title", self.item.id)
            self.setWindowTitle(f"🎬 {title} ({self.item.resolution}) - Live Wallpaper")
        else:
            self.setWindowTitle(tr("detail_title", id=item.id, res=item.resolution))

        self.resize(1100, 720)
        self.setMinimumSize(850, 550)

        self._init_ui()
        self._check_installed_state()
        self._load_preview()
        self._fetch_full_details()
        i18n.language_changed.connect(self.retranslate_ui)

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Left: Large Preview Container with StackedWidget (Index 0: Image, Index 1: Video)
        preview_container = QFrame()
        preview_container.setObjectName("previewContainer")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_stack = QStackedWidget()
        preview_layout.addWidget(self.preview_stack)

        # Page 0: Static image label
        self.preview_label = QLabel(tr("detail_loading_preview"))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #64748b; font-size: 14px; font-weight: 500;")
        self.preview_stack.addWidget(self.preview_label)

        # Page 1: Video player if multimedia available
        if HAS_MULTIMEDIA and getattr(self.item, "is_animated", False):
            video_box = QWidget()
            v_layout = QVBoxLayout(video_box)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.setSpacing(6)

            self.video_widget = QVideoWidget()
            self.video_widget.setStyleSheet("background-color: #000000; border-radius: 10px;")
            v_layout.addWidget(self.video_widget, stretch=1)

            # Video Controls Bar
            controls = QHBoxLayout()
            controls.setContentsMargins(8, 0, 8, 8)
            controls.setSpacing(8)

            self.play_pause_btn = QPushButton(tr("media_pause"))
            self.play_pause_btn.setFixedHeight(28)
            self.play_pause_btn.setStyleSheet("""
                QPushButton {
                    background: #191f2d;
                    color: #e2e8f0;
                    border: 1px solid #283144;
                    border-radius: 6px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #252e42;
                    border-color: #3b82f6;
                    color: #ffffff;
                }
            """)
            self.play_pause_btn.clicked.connect(self._toggle_playback)
            controls.addWidget(self.play_pause_btn)

            self.mute_btn = QPushButton(tr("audio_muted"))
            self.mute_btn.setFixedHeight(28)
            self.mute_btn.setStyleSheet("""
                QPushButton {
                    background: #191f2d;
                    color: #e2e8f0;
                    border: 1px solid #283144;
                    border-radius: 6px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #252e42;
                    border-color: #3b82f6;
                    color: #ffffff;
                }
            """)
            self.mute_btn.clicked.connect(self._toggle_mute)
            controls.addWidget(self.mute_btn)

            controls.addStretch()

            self.live_tag = QLabel(tr("live_preview_loop"))
            self.live_tag.setStyleSheet("color: #06b6d4; font-size: 11px; font-weight: bold;")
            controls.addWidget(self.live_tag)

            v_layout.addLayout(controls)
            self.preview_stack.addWidget(video_box)

            # Initialize QMediaPlayer
            self.player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video_widget)
            self.audio_output.setMuted(True)
            self.player.setLoops(QMediaPlayer.Loops.Infinite)

        main_layout.addWidget(preview_container, stretch=3)

        # Right: Info & Actions Sidebar inside a ScrollArea
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sidebar_scroll.setFixedWidth(340)
        sidebar_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        sidebar = QWidget()
        sidebar.setObjectName("detailSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(12)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)

        # 1. Title / Header Row
        id_row = QHBoxLayout()
        if getattr(self.item, "_osu_meta", None):
            meta = self.item._osu_meta
            title = meta.get("title", f"#{self.item.id}")
            artist = meta.get("artist", "")
            id_lbl = QLabel(f"<span style='font-size: 15px; font-weight: bold; color: #ffffff;'>{title}</span><br><span style='color: #818cf8; font-size: 11px;'>🎵 {artist}</span>")
            id_lbl.setWordWrap(True)
        elif getattr(self.item, "is_animated", False):
            title = getattr(self.item, "_display_title", self.item.id)
            id_lbl = QLabel(f"<span style='font-size: 15px; font-weight: bold; color: #ffffff;'>{title}</span><br><span style='color: #06b6d4; font-size: 11px;'>🎬 MoeWalls Live Video</span>")
            id_lbl.setWordWrap(True)
        else:
            id_lbl = QLabel(f"<span style='font-size: 16px; font-weight: bold; color: #ffffff;'>Wallhaven #{self.item.id}</span>")
        id_row.addWidget(id_lbl, stretch=1)

        self.open_web_btn = QPushButton(tr("detail_open_web"))
        self.open_web_btn.setStyleSheet("""
            QPushButton {
                background: #191f2d;
                color: #94a3b8;
                border: 1px solid #283144;
                border-radius: 6px;
                font-size: 11px;
                padding: 4px 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #252e42;
                color: #ffffff;
                border-color: #3b82f6;
            }
        """)
        self.open_web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_web_btn.clicked.connect(self._open_in_browser)
        id_row.addWidget(self.open_web_btn)
        sidebar_layout.addLayout(id_row)

        # 2. Download & Action Section
        self.dl_frame = QFrame()
        self.dl_frame.setObjectName("downloadPanel")
        self.dl_frame.setStyleSheet("""
            QFrame#downloadPanel {
                background: #141824;
                border: 1px solid #232a3b;
                border-radius: 10px;
            }
        """)
        dl_layout = QVBoxLayout(self.dl_frame)
        dl_layout.setContentsMargins(12, 12, 12, 12)
        dl_layout.setSpacing(8)

        self.dl_btn = QPushButton(tr("download_button"))
        self.dl_btn.setFixedHeight(40)
        self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #818cf8, stop:1 #6366f1);
            }
            QPushButton:pressed {
                background: #4338ca;
            }
            QPushButton:disabled {
                background: #232a3b;
                color: #64748b;
            }
        """)
        self.dl_btn.clicked.connect(self._on_download_clicked)
        dl_layout.addWidget(self.dl_btn)

        self.set_wall_cb = QCheckBox(tr("set_wall_checkbox"))
        self.set_wall_cb.setChecked(config.auto_set_wallpaper)
        self.set_wall_cb.setStyleSheet("""
            QCheckBox {
                color: #cbd5e1;
                font-size: 12px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #3b4252;
                background: #161922;
            }
            QCheckBox::indicator:checked {
                background: #6366f1;
                border-color: #818cf8;
            }
        """)
        dl_layout.addWidget(self.set_wall_cb)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setRange(0, 100)
        dl_layout.addWidget(self.progress_bar)

        self.dl_status_lbl = QLabel("")
        self.dl_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dl_status_lbl.setStyleSheet("font-size: 12px; color: #94a3b8;")
        self.dl_status_lbl.setWordWrap(True)
        self.dl_status_lbl.setVisible(False)
        dl_layout.addWidget(self.dl_status_lbl)

        # The two post-download action buttons
        self.set_wall_now_btn = QPushButton(tr("set_wall_now_button"))
        self.set_wall_now_btn.setObjectName("setWallNowBtn")
        self.set_wall_now_btn.setFixedHeight(36)
        self.set_wall_now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_wall_now_btn.setVisible(False)
        self.set_wall_now_btn.clicked.connect(self._on_set_wall_now)
        dl_layout.addWidget(self.set_wall_now_btn)

        self.open_folder_btn = QPushButton(tr("open_folder_button"))
        self.open_folder_btn.setObjectName("sidebarSecondaryBtn")
        self.open_folder_btn.setFixedHeight(36)
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        dl_layout.addWidget(self.open_folder_btn)

        self.uninstall_btn = QPushButton(tr("uninstall_button_full"))
        self.uninstall_btn.setFixedHeight(36)
        self.uninstall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.uninstall_btn.setVisible(False)
        self.uninstall_btn.setStyleSheet("""
            QPushButton {
                background-color: #450a0a;
                color: #fca5a5;
                border: 1px solid #dc2626;
                border-radius: 8px;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #7f1d1d;
                border-color: #ef4444;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #450a0a;
            }
        """)
        self.uninstall_btn.clicked.connect(self._on_uninstall_clicked)
        dl_layout.addWidget(self.uninstall_btn)

        sidebar_layout.addWidget(self.dl_frame)

        # 3. Metadata Frame
        self.meta_frame = QFrame()
        self.meta_frame.setObjectName("metaFrame")
        self.meta_frame.setStyleSheet("""
            QFrame#metaFrame {
                background: #141824;
                border-radius: 10px;
                border: 1px solid #232a3b;
            }
        """)
        meta_layout = QVBoxLayout(self.meta_frame)
        meta_layout.setContentsMargins(12, 10, 12, 10)
        meta_layout.setSpacing(6)

        self.meta_labels = {}

        def add_meta_row(key: str, label_text: str, val: str):
            r = QHBoxLayout()
            l = QLabel(label_text)
            l.setStyleSheet("color: #8590a6; font-size: 12px;")
            v = QLabel(f"<b>{val}</b>")
            v.setStyleSheet("color: #f1f5f9; font-size: 12px;")
            r.addWidget(l)
            r.addStretch()
            r.addWidget(v)
            meta_layout.addLayout(r)
            self.meta_labels[key] = l

        add_meta_row("resolution", tr("meta_resolution"), self.item.resolution)
        add_meta_row("ratio", tr("meta_ratio"), self.item.ratio)
        if getattr(self.item, "is_animated", False):
            add_meta_row("format", tr("meta_format"), "MP4 (Video 60fps)")
            add_meta_row("category", tr("meta_category"), self.item.category.capitalize())
            add_meta_row("source", "Zdroj / Provider", "MoeWalls Live")
        else:
            add_meta_row("file_size", tr("meta_file_size"), self.item.human_file_size)
            add_meta_row("format", tr("meta_format"), self.item.file_type or "image/jpeg")
            add_meta_row("category", tr("meta_category"), self.item.category.capitalize())
            add_meta_row("purity", tr("meta_purity"), self.item.purity.upper())
            if self.item.views > 0:
                add_meta_row("views", tr("meta_views"), f"{self.item.views:,}")
            if self.item.favorites > 0:
                add_meta_row("favorites", tr("meta_favorites"), f"★ {self.item.favorites:,}")

        sidebar_layout.addWidget(self.meta_frame)

        # 4. Color Palette (Wallhaven)
        if self.item.colors:
            self.colors_title_lbl = QLabel(tr("meta_palette"))
            self.colors_title_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
            sidebar_layout.addWidget(self.colors_title_lbl)

            colors_layout = QHBoxLayout()
            colors_layout.setSpacing(6)
            for c in self.item.colors:
                color_chip = QLabel()
                color_chip.setFixedSize(24, 18)
                color_chip.setStyleSheet(f"background-color: {c}; border-radius: 4px; border: 1px solid #2f384d;")
                color_chip.setToolTip(c)
                colors_layout.addWidget(color_chip)
            colors_layout.addStretch()
            sidebar_layout.addLayout(colors_layout)

        # 5. Tags Section
        self.tags_title_lbl = QLabel(tr("tags_title"))
        self.tags_title_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        sidebar_layout.addWidget(self.tags_title_lbl)

        self.tags_frame = QFrame()
        self.tags_frame.setObjectName("tagsFrame")
        self.tags_frame.setStyleSheet("""
            QFrame#tagsFrame {
                background: #141824;
                border-radius: 10px;
                border: 1px solid #232a3b;
            }
        """)
        self.tags_layout = QVBoxLayout(self.tags_frame)
        self.tags_layout.setContentsMargins(8, 8, 8, 8)
        self.tags_layout.setSpacing(4)
        self.tags_status_lbl = QLabel(tr("tags_loading"))
        self.tags_status_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        self.tags_layout.addWidget(self.tags_status_lbl)

        sidebar_layout.addWidget(self.tags_frame)
        sidebar_layout.addStretch()

        sidebar_scroll.setWidget(sidebar)
        main_layout.addWidget(sidebar_scroll)

    def _toggle_playback(self):
        if not self.player:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_pause_btn.setText(tr("media_play"))
        else:
            self.player.play()
            self.play_pause_btn.setText(tr("media_pause"))

    def _toggle_mute(self):
        if not self.audio_output:
            return
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        if not is_muted:
            self.mute_btn.setText(tr("audio_muted"))
        else:
            self.mute_btn.setText(tr("audio_unmuted"))

    def retranslate_ui(self):
        if getattr(self.item, "_osu_meta", None):
            self.setWindowTitle(f"osu! {self.item._osu_meta.get('season', '')} - #{self.item.id} ({self.item.resolution})")
        elif getattr(self.item, "is_animated", False):
            title = getattr(self.item, "_display_title", self.item.id)
            self.setWindowTitle(f"🎬 {title} ({self.item.resolution}) - Live Wallpaper")
        else:
            self.setWindowTitle(tr("detail_title", id=self.item.id, res=self.item.resolution))
        self.open_web_btn.setText(tr("detail_open_web"))
        if not self.saved_path:
            self.dl_btn.setText(tr("download_button"))
        else:
            self.dl_btn.setText("✓ " + tr("download_button").replace("⬇ ", ""))
        self.set_wall_cb.setText(tr("set_wall_checkbox"))
        self.set_wall_now_btn.setText(tr("set_wall_now_button"))
        self.open_folder_btn.setText(tr("open_folder_button"))
        self.uninstall_btn.setText(tr("uninstall_button_full"))
        self.tags_title_lbl.setText(tr("tags_title"))

        if hasattr(self, "live_tag") and self.live_tag:
            self.live_tag.setText(tr("live_preview_loop"))
        if hasattr(self, "play_pause_btn") and self.play_pause_btn:
            if hasattr(self, "player") and self.player and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.play_pause_btn.setText(tr("media_pause"))
            else:
                self.play_pause_btn.setText(tr("media_play"))
        if hasattr(self, "mute_btn") and self.mute_btn:
            if hasattr(self, "audio_output") and self.audio_output and not self.audio_output.isMuted():
                self.mute_btn.setText(tr("audio_unmuted"))
            else:
                self.mute_btn.setText(tr("audio_muted"))

        if hasattr(self, "colors_title_lbl") and self.colors_title_lbl:
            self.colors_title_lbl.setText(tr("meta_palette"))

        meta_keys = {
            "resolution": "meta_resolution",
            "ratio": "meta_ratio",
            "file_size": "meta_file_size",
            "format": "meta_format",
            "category": "meta_category",
            "purity": "meta_purity",
            "views": "meta_views",
            "favorites": "meta_favorites",
        }
        for k, tr_key in meta_keys.items():
            if k in self.meta_labels:
                self.meta_labels[k].setText(tr(tr_key))

    def _load_preview(self):
        url = self.item.thumb_large or self.item.thumb_original or self.item.thumb_small
        if not url:
            return

        self._preview_url = url
        loaded = loader.load_image(url, is_thumb=True, callback=self._on_preview_loaded)
        if loaded:
            pm = loader.cache.get_pixmap(url, is_thumb=True)
            if pm:
                self._update_preview(pm)

    def _cleanup_signal(self):
        url = getattr(self, "_preview_url", None)
        if url:
            loader.unregister_callback(url, self._on_preview_loaded)

    def _on_preview_loaded(self, pixmap: QPixmap):
        self._update_preview(pixmap)

    def closeEvent(self, event):
        self._cleanup_signal()
        if self.player:
            self.player.stop()
        super().closeEvent(event)

    def reject(self):
        self._cleanup_signal()
        if self.player:
            self.player.stop()
        super().reject()

    def _update_preview(self, pixmap: QPixmap):
        lbl_size = self.preview_label.size()
        w = max(400, lbl_size.width())
        h = max(300, lbl_size.height())
        scaled = pixmap.scaled(
            QSize(w, h),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        target_url = self.item.thumb_large or self.item.thumb_original or self.item.thumb_small
        pm = loader.cache.get_pixmap(target_url, is_thumb=True)
        if pm and not pm.isNull():
            self._update_preview(pm)

    def _fetch_full_details(self):
        if getattr(self.item, "_osu_meta", None):
            self._on_details_fetched(self.item)
            return
        self.fetch_worker = DetailFetchWorker(self.item)
        self.fetch_worker.finished.connect(self._on_details_fetched)
        self.fetch_worker.failed.connect(lambda err: self.tags_status_lbl.setText(tr("tags_unavailable")))
        self.fetch_worker.start()

    def _on_details_fetched(self, full_item: WallpaperItem):
        self.item = full_item

        # If animated wallpaper and has preview video URL, switch to video view!
        if HAS_MULTIMEDIA and getattr(full_item, "is_animated", False) and full_item.preview_video_url and self.player:
            try:
                self.player.setSource(QUrl(full_item.preview_video_url))
                self.player.play()
                self.preview_stack.setCurrentIndex(1)
            except Exception as e:
                print(f"Error starting video preview: {e}")

        while self.tags_layout.count():
            child = self.tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if full_item.tags:
            for tag in full_item.tags:
                tag_name = tag.get("name", "")
                tag_btn = QPushButton(f"#{tag_name}")
                tag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                tag_btn.setStyleSheet("""
                    QPushButton {
                        background: #191f2d;
                        color: #a5b4fc;
                        border: 1px solid #283347;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-size: 11px;
                        text-align: left;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background: #312e81;
                        color: #ffffff;
                        border-color: #6366f1;
                    }
                """)
                tag_btn.clicked.connect(lambda checked, t=tag_name: self._on_tag_clicked(t))
                self.tags_layout.addWidget(tag_btn)
        else:
            no_tags = QLabel(tr("tags_none"))
            no_tags.setStyleSheet("color: #64748b; font-size: 11px;")
            self.tags_layout.addWidget(no_tags)

        self.tags_layout.addStretch()

    def _on_tag_clicked(self, tag_name: str):
        self.tag_clicked.emit(tag_name)
        self.accept()

    def _open_in_browser(self):
        if self.item.url:
            QDesktopServices.openUrl(QUrl(self.item.url))

    def _on_download_clicked(self):
        is_animated = getattr(self.item, "is_animated", False)
        ext = ".mp4" if is_animated else (os.path.splitext(self.item.path)[1] or ".jpg")

        if getattr(self.item, "_osu_meta", None):
            meta = self.item._osu_meta
            artist = "".join(c for c in meta.get("artist", "artist") if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            title = "".join(c for c in meta.get("title", self.item.id) if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            season = "".join(c for c in meta.get("season", "osu") if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            suggested_name = f"osu-{season}-{artist}-{title}{ext}"
        elif is_animated:
            clean_title = "".join(c for c in getattr(self.item, "_display_title", self.item.id) if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            suggested_name = f"moewalls-{clean_title}{ext}"
        else:
            suggested_name = f"wallhaven-{self.item.id}{ext}"

        default_dir = Path(config.default_download_dir)
        default_dir.mkdir(parents=True, exist_ok=True)
        initial_path = str(default_dir / suggested_name)

        filter_str = "Video (*.mp4 *.webm);;All Files (*)" if is_animated else tr("images_filter", ext=ext)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("save_dialog_title"),
            initial_path,
            filter_str,
        )

        if not save_path:
            return

        self.dl_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.dl_status_lbl.setVisible(True)
        self.dl_status_lbl.setText(tr("download_progress_start"))

        self.download_worker = DownloadWorker(self.item, save_path)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.failed.connect(self._on_download_failed)
        self.download_worker.start()

    def _on_download_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            mb_cur = downloaded / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.dl_status_lbl.setText(f"{mb_cur:.1f} MB / {mb_tot:.1f} MB ({pct}%)")
        else:
            self.progress_bar.setRange(0, 0)

    def _on_download_finished(self, saved_path: str):
        self.saved_path = saved_path
        self.progress_bar.setVisible(False)
        self.dl_btn.setEnabled(True)
        self.dl_btn.setText("✓ " + tr("download_button").replace("⬇ ", ""))
        self.dl_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #10b981;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)

        # Automatically set desktop wallpaper if requested
        if self.set_wall_cb.isChecked():
            ok, msg = set_desktop_wallpaper(
                saved_path,
                config.custom_wallpaper_cmd,
                config.wallpaper_setter,
                config.custom_video_wallpaper_cmd,
            )
            if ok:
                self.dl_status_lbl.setText(tr("download_status_set"))
                self.dl_status_lbl.setStyleSheet("color: #34d399; font-size: 12px; font-weight: bold;")
            else:
                self.dl_status_lbl.setText(tr("download_status_failed_wall", error=msg))
                self.dl_status_lbl.setStyleSheet("color: #fbbf24; font-size: 12px;")
        else:
            self.dl_status_lbl.setText(tr("download_status_saved", filename=os.path.basename(saved_path)))
            self.dl_status_lbl.setStyleSheet("color: #34d399; font-size: 12px;")

        self.dl_status_lbl.setVisible(True)
        self.set_wall_now_btn.setVisible(True)
        self.open_folder_btn.setVisible(True)
        self.uninstall_btn.setVisible(True)

        try:
            from wallhaven.installed import installed_manager
            installed_manager.register_download(saved_path, self.item)
        except Exception as e:
            print(f"Error registering installed download: {e}")

        self.download_completed.emit(saved_path)

    def _check_installed_state(self):
        try:
            from wallhaven.installed import installed_manager
            installed_path = installed_manager.get_installed_path(self.item)
            if not installed_path and getattr(self.item, "is_installed", False):
                installed_path = self.item.path
            if installed_path and os.path.exists(installed_path):
                self.saved_path = installed_path
                self.set_wall_now_btn.setVisible(True)
                self.open_folder_btn.setVisible(True)
                self.uninstall_btn.setVisible(True)
                self.set_wall_cb.setVisible(False)
                self.dl_btn.setText("✓ " + tr("download_status_installed"))
                self.dl_btn.setEnabled(False)
                self.dl_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #059669;
                        color: #ffffff;
                        font-weight: bold;
                        font-size: 13px;
                        border: 1px solid #10b981;
                        border-radius: 8px;
                    }
                """)
                self.dl_status_lbl.setText(tr("download_status_saved", filename=os.path.basename(installed_path)))
                self.dl_status_lbl.setStyleSheet("color: #34d399; font-size: 12px;")
                self.dl_status_lbl.setVisible(True)
                if HAS_MULTIMEDIA and getattr(self.item, "is_animated", False) and self.player:
                    try:
                        self.player.setSource(QUrl.fromLocalFile(installed_path))
                        self.player.play()
                        self.preview_stack.setCurrentIndex(1)
                    except Exception as e:
                        print(f"Error starting local video preview: {e}")
        except Exception as e:
            print(f"Error checking installed state: {e}")

    def _on_uninstall_clicked(self):
        title = getattr(self.item, "_display_title", "") or f"Wallpaper #{self.item.id}"
        target_path = self.saved_path or self.item.path
        filename = os.path.basename(target_path) if target_path else self.item.id

        res = QMessageBox.question(
            self,
            tr("confirm_uninstall_title"),
            tr("confirm_uninstall_msg", title=title, filename=filename),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            try:
                from wallhaven.installed import installed_manager
                ok, err = installed_manager.uninstall_wallpaper(target_path or self.item)
                if ok:
                    QMessageBox.information(
                        self,
                        tr("uninstall_success_title"),
                        tr("uninstall_success_msg", title=title),
                    )
                    self.uninstalled.emit(self.item)
                    self.accept()
                else:
                    QMessageBox.critical(
                        self,
                        tr("uninstall_error_title"),
                        tr("uninstall_error_msg", error=err),
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    tr("uninstall_error_title"),
                    tr("uninstall_error_msg", error=str(e)),
                )

    def _on_set_wall_now(self):
        if self.saved_path and os.path.exists(self.saved_path):
            ok, msg = set_desktop_wallpaper(
                self.saved_path,
                config.custom_wallpaper_cmd,
                config.wallpaper_setter,
                config.custom_video_wallpaper_cmd,
            )
            if ok:
                self.dl_status_lbl.setText(tr("download_status_set"))
                self.dl_status_lbl.setStyleSheet("color: #34d399; font-size: 12px; font-weight: bold;")
                QMessageBox.information(self, tr("set_wall_success_title"), tr("set_wall_success_msg"))
            else:
                QMessageBox.warning(self, tr("set_wall_error_title"), tr("set_wall_error_msg", error=msg))

    def _on_download_failed(self, error: str):
        self.progress_bar.setVisible(False)
        self.dl_btn.setEnabled(True)
        self.dl_status_lbl.setText(tr("download_failed_msg", error=error))
        self.dl_status_lbl.setStyleSheet("color: #f87171; font-size: 12px;")
        QMessageBox.critical(self, tr("download_failed_title"), tr("download_failed_msg", error=error))

    def _on_open_folder(self):
        if self.saved_path and os.path.exists(self.saved_path):
            folder = os.path.dirname(self.saved_path)
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
