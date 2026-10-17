import os
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices, QColor
from PyQt6.QtWidgets import (
    QApplication,
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
from wallhaven.styles import get_palette

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
    color_clicked = pyqtSignal(str)
    download_completed = pyqtSignal(str)
    uninstalled = pyqtSignal(WallpaperItem)
    _lingering_workers: set = set()

    def __init__(self, item: WallpaperItem, parent=None, items_list: list[WallpaperItem] | None = None):
        super().__init__(parent)
        self.item = item
        self.items_list: list[WallpaperItem] = [
            it for it in (items_list or []) if isinstance(it, WallpaperItem)
        ]
        self._current_index: int = -1
        for idx, it in enumerate(self.items_list):
            if it.id == item.id:
                self._current_index = idx
                break

        self.download_worker: DownloadWorker | None = None
        self.fetch_worker: DetailFetchWorker | None = None
        self.saved_path: str = ""
        self._current_pixmap: QPixmap | None = None
        self.player: QMediaPlayer | None = None
        self.audio_output: QAudioOutput | None = None

        self._update_window_title()
        self.resize(1120, 740)
        self.setMinimumSize(860, 560)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._init_ui()
        self._check_installed_state()
        self._load_preview()
        self._fetch_full_details()
        i18n.language_changed.connect(self.retranslate_ui)

    def _update_window_title(self):
        if getattr(self.item, "_osu_meta", None):
            self.setWindowTitle(f"osu! {self.item._osu_meta.get('season', '')} - #{self.item.id} ({self.item.resolution})")
        elif getattr(self.item, "is_animated", False):
            title = getattr(self.item, "_display_title", self.item.id)
            self.setWindowTitle(f"🎬 {title} ({self.item.resolution}) - Live Wallpaper")
        else:
            self.setWindowTitle(tr("detail_title", id=self.item.id, res=self.item.resolution))

    def _get_header_html(self) -> str:
        pal = get_palette(config.theme)
        accent = pal.get("accent_hover", "#818cf8")
        if getattr(self.item, "_osu_meta", None):
            meta = self.item._osu_meta
            title = meta.get("title", f"#{self.item.id}")
            artist = meta.get("artist", "")
            return f"<span style='font-size: 15px; font-weight: bold; color: #ffffff;'>{title}</span><br><span style='color: {accent}; font-size: 11px;'>🎵 {artist}</span>"
        elif getattr(self.item, "is_animated", False):
            title = getattr(self.item, "_display_title", self.item.id)
            return f"<span style='font-size: 15px; font-weight: bold; color: #ffffff;'>{title}</span><br><span style='color: #06b6d4; font-size: 11px;'>🎬 MoeWalls Live Video</span>"
        else:
            return f"<span style='font-size: 16px; font-weight: bold; color: #ffffff;'>Wallhaven #{self.item.id}</span>"

    def _init_ui(self):
        pal = get_palette(config.theme)
        bg_card = pal.get("bg_card", "#141824")
        bg_surface = pal.get("bg_surface", "#191f2d")
        border = pal.get("border", "#232a3b")
        accent = pal.get("accent", "#6366f1")
        accent_hover = pal.get("accent_hover", "#818cf8")
        text_pri = pal.get("text_primary", "#f8fafc")
        text_sec = pal.get("text_secondary", "#94a3b8")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Left: Large Preview Container with StackedWidget (Index 0: Image, Index 1: Video)
        preview_container = QFrame()
        preview_container.setObjectName("previewContainer")
        preview_container.setStyleSheet(f"""
            QFrame#previewContainer {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {pal.get('bg_base', '#090b10')}, stop:1 {bg_card});
                border: 1.5px solid {border};
                border-radius: 14px;
            }}
        """)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(6)

        # Top navigation bar inside preview container (Prev / Counter / Next)
        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(6, 2, 6, 2)
        nav_bar.setSpacing(8)

        nav_btn_style = f"""
            QPushButton {{
                background: {bg_surface};
                color: {text_pri};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 800;
            }}
            QPushButton:hover:enabled {{
                background: {accent};
                border-color: {accent_hover};
                color: #ffffff;
            }}
            QPushButton:disabled {{
                color: #475569;
                background: rgba(15, 20, 30, 0.4);
            }}
        """

        self.prev_item_btn = QPushButton("◀")
        self.prev_item_btn.setFixedHeight(28)
        self.prev_item_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_item_btn.setToolTip(tr("detail_prev_tip"))
        self.prev_item_btn.setStyleSheet(nav_btn_style)
        self.prev_item_btn.clicked.connect(lambda: self._navigate_relative(-1))
        nav_bar.addWidget(self.prev_item_btn)

        self.nav_counter_lbl = QLabel("")
        self.nav_counter_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nav_counter_lbl.setStyleSheet(f"color: {text_sec}; font-size: 11.5px; font-weight: 700; background: transparent;")
        nav_bar.addWidget(self.nav_counter_lbl, stretch=1)

        self.next_item_btn = QPushButton("▶")
        self.next_item_btn.setFixedHeight(28)
        self.next_item_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_item_btn.setToolTip(tr("detail_next_tip"))
        self.next_item_btn.setStyleSheet(nav_btn_style)
        self.next_item_btn.clicked.connect(lambda: self._navigate_relative(1))
        nav_bar.addWidget(self.next_item_btn)

        preview_layout.addLayout(nav_bar)
        self._update_nav_buttons()

        self.preview_stack = QStackedWidget()
        preview_layout.addWidget(self.preview_stack, stretch=1)

        # Page 0: Static image label
        self.preview_label = QLabel(tr("detail_loading_preview"))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(f"color: {text_sec}; font-size: 14px; font-weight: 500; background: transparent;")
        self.preview_stack.addWidget(self.preview_label)

        # Page 1: Video player if multimedia available
        if HAS_MULTIMEDIA:
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
            self.play_pause_btn.setStyleSheet(nav_btn_style)
            self.play_pause_btn.clicked.connect(self._toggle_playback)
            controls.addWidget(self.play_pause_btn)

            self.mute_btn = QPushButton(tr("audio_muted"))
            self.mute_btn.setFixedHeight(28)
            self.mute_btn.setStyleSheet(nav_btn_style)
            self.mute_btn.clicked.connect(self._toggle_mute)
            controls.addWidget(self.mute_btn)

            controls.addStretch()

            self.live_tag = QLabel(tr("live_preview_loop"))
            self.live_tag.setStyleSheet(f"color: {accent_hover}; font-size: 11px; font-weight: bold;")
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
        sidebar_scroll.setFixedWidth(346)
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
        sidebar_layout.setContentsMargins(10, 8, 10, 10)

        # 1. Title / Header Row
        id_row = QHBoxLayout()
        self.id_lbl = QLabel(self._get_header_html())
        self.id_lbl.setWordWrap(True)
        id_row.addWidget(self.id_lbl, stretch=1)

        self.open_web_btn = QPushButton(tr("detail_open_web"))
        self.open_web_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg_surface};
                color: {text_sec};
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 11px;
                padding: 4px 8px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {accent};
                color: #ffffff;
                border-color: {accent_hover};
            }}
        """)
        self.open_web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_web_btn.clicked.connect(self._open_in_browser)
        id_row.addWidget(self.open_web_btn)
        sidebar_layout.addLayout(id_row)

        # 2. Download & Action Section
        self.dl_frame = QFrame()
        self.dl_frame.setObjectName("downloadPanel")
        self.dl_frame.setStyleSheet(f"""
            QFrame#downloadPanel {{
                background: {bg_card};
                border: 1.5px solid {border};
                border-top: 2px solid {accent};
                border-radius: 12px;
            }}
        """)
        dl_layout = QVBoxLayout(self.dl_frame)
        dl_layout.setContentsMargins(12, 12, 12, 12)
        dl_layout.setSpacing(8)

        self.dl_btn = QPushButton(tr("download_button"))
        self.dl_btn.setFixedHeight(40)
        self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_default_dl_btn_style()
        self.dl_btn.clicked.connect(self._on_download_clicked)
        dl_layout.addWidget(self.dl_btn)

        # Copy Image to Clipboard button (for static wallpapers)
        self.copy_img_btn = QPushButton(tr("detail_copy_btn"))
        self.copy_img_btn.setFixedHeight(34)
        self.copy_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_img_btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg_surface};
                color: {text_pri};
                border: 1px solid {border};
                border-radius: 8px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {accent};
                border-color: {accent_hover};
                color: #ffffff;
            }}
        """)
        self.copy_img_btn.clicked.connect(self._on_copy_image_clicked)
        self.copy_img_btn.setVisible(not getattr(self.item, "is_animated", False))
        dl_layout.addWidget(self.copy_img_btn)

        self.set_wall_cb = QCheckBox(tr("set_wall_checkbox"))
        self.set_wall_cb.setChecked(config.auto_set_wallpaper)
        self.set_wall_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {text_sec};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid {border};
                background: {bg_surface};
            }}
            QCheckBox::indicator:checked {{
                background: {accent};
                border-color: {accent_hover};
            }}
        """)
        dl_layout.addWidget(self.set_wall_cb)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setRange(0, 100)
        dl_layout.addWidget(self.progress_bar)

        self.dl_status_lbl = QLabel("")
        self.dl_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dl_status_lbl.setStyleSheet(f"font-size: 12px; color: {text_sec};")
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
        self.meta_frame.setStyleSheet(f"""
            QFrame#metaFrame {{
                background: {bg_card};
                border-radius: 12px;
                border: 1px solid {border};
            }}
        """)
        self.meta_layout = QVBoxLayout(self.meta_frame)
        self.meta_layout.setContentsMargins(12, 10, 12, 10)
        self.meta_layout.setSpacing(6)

        self.meta_labels = {}
        self._populate_metadata()
        sidebar_layout.addWidget(self.meta_frame)

        # 4. Color Palette (Wallhaven — Clickable Color Search Chips)
        self.colors_section = QWidget()
        self.colors_section_layout = QVBoxLayout(self.colors_section)
        self.colors_section_layout.setContentsMargins(0, 0, 0, 0)
        self.colors_section_layout.setSpacing(6)

        self.colors_title_lbl = QLabel(tr("meta_palette"))
        self.colors_title_lbl.setStyleSheet(f"color: {text_sec}; font-size: 11px; font-weight: bold;")
        self.colors_section_layout.addWidget(self.colors_title_lbl)

        self.colors_row_widget = QWidget()
        self.colors_layout = QHBoxLayout(self.colors_row_widget)
        self.colors_layout.setContentsMargins(0, 0, 0, 0)
        self.colors_layout.setSpacing(6)
        self.colors_section_layout.addWidget(self.colors_row_widget)

        sidebar_layout.addWidget(self.colors_section)
        self._populate_colors()

        # 5. Tags Section
        self.tags_title_lbl = QLabel(tr("tags_title"))
        self.tags_title_lbl.setStyleSheet(f"color: {text_sec}; font-size: 11px; font-weight: bold;")
        sidebar_layout.addWidget(self.tags_title_lbl)

        self.tags_frame = QFrame()
        self.tags_frame.setObjectName("tagsFrame")
        self.tags_frame.setStyleSheet(f"""
            QFrame#tagsFrame {{
                background: {bg_card};
                border-radius: 12px;
                border: 1px solid {border};
            }}
        """)
        self.tags_layout = QVBoxLayout(self.tags_frame)
        self.tags_layout.setContentsMargins(8, 8, 8, 8)
        self.tags_layout.setSpacing(4)
        self.tags_status_lbl = QLabel(tr("tags_loading"))
        self.tags_status_lbl.setStyleSheet(f"color: {text_sec}; font-size: 11px;")
        self.tags_layout.addWidget(self.tags_status_lbl)

        sidebar_layout.addWidget(self.tags_frame)
        sidebar_layout.addStretch()

        sidebar_scroll.setWidget(sidebar)
        main_layout.addWidget(sidebar_scroll)

    def _apply_default_dl_btn_style(self):
        pal = get_palette(config.theme)
        accent = pal.get("accent", "#6366f1")
        accent_hover = pal.get("accent_hover", "#818cf8")
        border = pal.get("border", "#232a3b")
        self.dl_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent_hover});
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent_hover}, stop:1 {accent});
            }}
            QPushButton:disabled {{
                background: {border};
                color: #64748b;
            }}
        """)

    def _populate_metadata(self):
        while self.meta_layout.count():
            child = self.meta_layout.takeAt(0)
            if child.layout():
                while child.layout().count():
                    sub = child.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
            elif child.widget():
                child.widget().deleteLater()
        self.meta_labels.clear()

        pal = get_palette(config.theme)
        text_pri = pal.get("text_primary", "#f1f5f9")
        text_sec = pal.get("text_secondary", "#8590a6")

        def add_meta_row(key: str, label_text: str, val: str):
            r = QHBoxLayout()
            l = QLabel(label_text)
            l.setStyleSheet(f"color: {text_sec}; font-size: 12px;")
            v = QLabel(f"<b>{val}</b>")
            v.setStyleSheet(f"color: {text_pri}; font-size: 12px;")
            r.addWidget(l)
            r.addStretch()
            r.addWidget(v)
            self.meta_layout.addLayout(r)
            self.meta_labels[key] = l

        add_meta_row("resolution", tr("meta_resolution"), self.item.resolution)
        add_meta_row("ratio", tr("meta_ratio"), self.item.ratio)
        if getattr(self.item, "is_animated", False):
            add_meta_row("format", tr("meta_format"), "MP4 (Video 60fps)")
            add_meta_row("category", tr("meta_category"), self.item.category.capitalize())
            add_meta_row("source", tr("meta_source"), "MoeWalls Live")
        else:
            add_meta_row("file_size", tr("meta_file_size"), self.item.human_file_size)
            add_meta_row("format", tr("meta_format"), self.item.file_type or "image/jpeg")
            add_meta_row("category", tr("meta_category"), self.item.category.capitalize())
            add_meta_row("purity", tr("meta_purity"), self.item.purity.upper())
            if self.item.views > 0:
                add_meta_row("views", tr("meta_views"), f"{self.item.views:,}")
            if self.item.favorites > 0:
                add_meta_row("favorites", tr("meta_favorites"), f"★ {self.item.favorites:,}")

    def _populate_colors(self):
        while self.colors_layout.count():
            child = self.colors_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.item.colors:
            self.colors_section.setVisible(False)
            return

        self.colors_section.setVisible(True)
        pal = get_palette(config.theme)
        accent_hover = pal.get("accent_hover", "#818cf8")
        for c in self.item.colors:
            color_chip = QPushButton("")
            color_chip.setFixedSize(32, 22)
            color_chip.setCursor(Qt.CursorShape.PointingHandCursor)
            color_chip.setToolTip(tr("detail_color_search_tip", color=c))
            color_chip.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c};
                    border-radius: 6px;
                    border: 1.5px solid rgba(255, 255, 255, 0.22);
                }}
                QPushButton:hover {{
                    border: 2px solid {accent_hover};
                }}
            """)
            color_chip.clicked.connect(lambda checked, hex_col=c: self._on_color_chip_clicked(hex_col))
            self.colors_layout.addWidget(color_chip)
        self.colors_layout.addStretch()

    def _on_color_chip_clicked(self, hex_color: str):
        clean_hex = hex_color.lstrip("#")
        self.color_clicked.emit(clean_hex)
        self.accept()

    def _on_copy_image_clicked(self):
        pm = None
        if self.saved_path and os.path.exists(self.saved_path) and not getattr(self.item, "is_animated", False):
            loaded_pm = QPixmap(self.saved_path)
            if not loaded_pm.isNull():
                pm = loaded_pm
        if pm is None and self._current_pixmap and not self._current_pixmap.isNull():
            pm = self._current_pixmap
        if pm is not None and not pm.isNull():
            QApplication.clipboard().setPixmap(pm)
            self.copy_img_btn.setText(tr("detail_copied_btn"))

    def _update_nav_buttons(self):
        has_list = len(self.items_list) > 1 and self._current_index >= 0
        self.prev_item_btn.setVisible(has_list)
        self.next_item_btn.setVisible(has_list)
        self.nav_counter_lbl.setVisible(has_list)
        if has_list:
            self.prev_item_btn.setEnabled(self._current_index > 0)
            self.next_item_btn.setEnabled(self._current_index < len(self.items_list) - 1)
            self.nav_counter_lbl.setText(f"{self._current_index + 1} / {len(self.items_list)}")

    def _navigate_relative(self, delta: int):
        if not self.items_list or self._current_index < 0:
            return
        new_idx = self._current_index + delta
        if new_idx < 0 or new_idx >= len(self.items_list):
            return

        # Clean up current preview loader & fetch worker
        old_url = getattr(self, "_preview_url", None)
        if old_url:
            loader.unregister_callback(old_url, self._on_preview_loaded)
        if self.fetch_worker and self.fetch_worker.isRunning():
            try:
                self.fetch_worker.finished.disconnect()
                self.fetch_worker.failed.disconnect()
            except Exception:
                pass
            DetailDialog._lingering_workers.add(self.fetch_worker)
            self.fetch_worker.finished.connect(lambda w=self.fetch_worker: DetailDialog._lingering_workers.discard(w))
            self.fetch_worker = None
        if self.player:
            self.player.stop()

        self._current_index = new_idx
        self.item = self.items_list[new_idx]
        self.saved_path = ""
        self._current_pixmap = None

        # Reset UI for new item
        self._update_window_title()
        self._update_nav_buttons()
        self.id_lbl.setText(self._get_header_html())
        self.preview_stack.setCurrentIndex(0)
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(tr("detail_loading_preview"))

        self.dl_btn.setEnabled(True)
        self.dl_btn.setText(tr("download_button"))
        self._apply_default_dl_btn_style()
        self.copy_img_btn.setVisible(not getattr(self.item, "is_animated", False))
        self.copy_img_btn.setText(tr("detail_copy_btn"))
        self.set_wall_cb.setVisible(True)
        self.progress_bar.setVisible(False)
        self.dl_status_lbl.setVisible(False)
        self.set_wall_now_btn.setVisible(False)
        self.open_folder_btn.setVisible(False)
        self.uninstall_btn.setVisible(False)

        self._populate_metadata()
        self._populate_colors()

        while self.tags_layout.count():
            child = self.tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.tags_status_lbl = QLabel(tr("tags_loading"))
        self.tags_status_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        self.tags_layout.addWidget(self.tags_status_lbl)

        self._check_installed_state()
        self._load_preview()
        self._fetch_full_details()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self._navigate_relative(-1)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Right:
            self._navigate_relative(1)
            event.accept()
            return
        super().keyPressEvent(event)

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
        self._update_window_title()
        self.open_web_btn.setText(tr("detail_open_web"))
        self.prev_item_btn.setToolTip(tr("detail_prev_tip"))
        self.next_item_btn.setToolTip(tr("detail_next_tip"))
        if hasattr(self, "copy_img_btn"):
            self.copy_img_btn.setText(tr("detail_copy_btn"))
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
            "source": "meta_source",
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
        try:
            i18n.language_changed.disconnect(self.retranslate_ui)
        except Exception:
            pass
        for w_attr in ("download_worker", "fetch_worker"):
            worker = getattr(self, w_attr, None)
            if worker is not None:
                if hasattr(worker, "cancel"):
                    worker.cancel()
                try:
                    worker.finished.disconnect()
                except Exception:
                    pass
                try:
                    worker.failed.disconnect()
                except Exception:
                    pass
                if hasattr(worker, "progress"):
                    try:
                        worker.progress.disconnect()
                    except Exception:
                        pass
                if worker.isRunning():
                    DetailDialog._lingering_workers.add(worker)
                    worker.finished.connect(lambda w=worker: DetailDialog._lingering_workers.discard(w))
                setattr(self, w_attr, None)

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
        self._current_pixmap = pixmap
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
        self._populate_metadata()
        self._populate_colors()

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

        pal = get_palette(config.theme)
        bg_surface = pal.get("bg_surface", "#191f2d")
        border = pal.get("border", "#283347")
        accent = pal.get("accent", "#6366f1")
        accent_hover = pal.get("accent_hover", "#a5b4fc")

        if full_item.tags:
            for tag in full_item.tags:
                tag_name = tag.get("name", "")
                tag_btn = QPushButton(f"#{tag_name}")
                tag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                tag_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {bg_surface};
                        color: {accent_hover};
                        border: 1px solid {border};
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-size: 11px;
                        text-align: left;
                        font-weight: 600;
                    }}
                    QPushButton:hover {{
                        background: {accent};
                        color: #ffffff;
                        border-color: {accent_hover};
                    }}
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
