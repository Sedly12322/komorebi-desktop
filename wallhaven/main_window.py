import os
import sys
import time
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QPoint, QTimer
from PyQt6.QtGui import QIcon, QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QScrollArea,
    QFrame,
    QMessageBox,
    QFileDialog,
    QSpinBox,
    QStatusBar,
    QApplication,
    QSizePolicy,
    QLayout,
    QMenu,
)
from wallhaven.api import WallpaperItem, SearchResult, api
from wallhaven.osu import osu_manager
from wallhaven.moewalls import moewalls_manager
from wallhaven.installed import installed_manager
from wallhaven.config import config
from wallhaven.i18n import tr, i18n
from wallhaven.widgets.grid_widget import WallpaperGridWidget
from wallhaven.widgets.color_bar import ColorBar
from wallhaven.widgets.detail_dialog import DetailDialog, DownloadWorker
from wallhaven.widgets.settings_dialog import SettingsDialog
from wallhaven.widgets.pfp_detail_dialog import PfpDetailDialog
from wallhaven.widgets.animated_nav import AnimatedCapsuleBar
from wallhaven.widgets.smooth_scroll import SmoothScrollArea
from wallhaven.widgets.sidebar import KomorebiSidebar
from wallhaven.widgets.floating_pagination import FloatingPagination, CanvasWrapper
from wallhaven.widgets.ambient_background import KomorebiAmbientCanvas
from wallhaven.widgets.toast import KomorebiToast
from wallhaven.wallpaper import set_desktop_wallpaper
from wallhaven.pfps import pfps_client, PfpItem
from wallhaven.styles import get_available_themes, apply_theme, get_palette, get_asset_path
from wallhaven import __version__
from wallhaven.updater import UpdateCheckWorker, UpdateDialog, UpdateBanner, UpdateInfo


class SearchWorker(QThread):
    finished = pyqtSignal(int, SearchResult)
    failed = pyqtSignal(int, str)

    def __init__(self, search_id: int, **kwargs):
        super().__init__()
        self.search_id = search_id
        self.kwargs = kwargs

    def run(self):
        try:
            res = api.search(**self.kwargs)
            self.finished.emit(self.search_id, res)
        except Exception as e:
            self.failed.emit(self.search_id, str(e))


class OsuSearchWorker(QThread):
    finished = pyqtSignal(int, SearchResult)
    failed = pyqtSignal(int, str)

    def __init__(self, search_id: int, **kwargs):
        super().__init__()
        self.search_id = search_id
        self.kwargs = kwargs

    def run(self):
        try:
            res = osu_manager.search(**self.kwargs)
            self.finished.emit(self.search_id, res)
        except Exception as e:
            self.failed.emit(self.search_id, str(e))


class MoeSearchWorker(QThread):
    finished = pyqtSignal(int, SearchResult)
    failed = pyqtSignal(int, str)

    def __init__(self, search_id: int, **kwargs):
        super().__init__()
        self.search_id = search_id
        self.kwargs = kwargs

    def run(self):
        try:
            res = moewalls_manager.search(**self.kwargs)
            self.finished.emit(self.search_id, res)
        except Exception as e:
            self.failed.emit(self.search_id, str(e))


class InstalledSearchWorker(QThread):
    finished = pyqtSignal(int, SearchResult)
    failed = pyqtSignal(int, str)

    def __init__(self, search_id: int, **kwargs):
        super().__init__()
        self.search_id = search_id
        self.kwargs = kwargs

    def run(self):
        try:
            res = installed_manager.search(**self.kwargs)
            self.finished.emit(self.search_id, res)
        except Exception as e:
            self.failed.emit(self.search_id, str(e))


class PfpsSearchWorker(QThread):
    finished = pyqtSignal(int, list, bool, int)
    failed = pyqtSignal(int, str)

    def __init__(self, search_id: int, **kwargs):
        super().__init__()
        self.search_id = search_id
        self.kwargs = kwargs

    def run(self):
        try:
            page = self.kwargs.get("page", 1)
            items, has_next = pfps_client.fetch_pfps(**self.kwargs)
            self.finished.emit(self.search_id, items, has_next, page)
        except Exception as e:
            self.failed.emit(self.search_id, str(e))


class StatusToastProxy:
    """Seamlessly redirects status updates into KomorebiToast notifications instead of a legacy gray status bar."""

    def __init__(self, main_win):
        self.main_win = main_win

    def showMessage(self, text: str, timeout: int = 0):
        if not text:
            return
        text_clean = text.strip()
        # Suppress startup "Ready" or repetitive low-level byte progress
        if text_clean in ("Ready", "Připraveno", "Ready.", "Připraveno."):
            return
        if "Downloading" in text_clean or "Stahování" in text_clean or "MB /" in text_clean:
            return
        if "Searching wallpapers" in text_clean or "Vyhledávání tapet" in text_clean:
            return

        icon = "🌿"
        if "✓" in text_clean or "Success" in text_clean or "Úspěch" in text_clean:
            icon = "✓"
        elif "error" in text_clean.lower() or "fail" in text_clean.lower() or "chyba" in text_clean.lower() or "✗" in text_clean:
            icon = "⚠️"
        elif "tapet" in text_clean.lower() or "wallpaper" in text_clean.lower():
            icon = "🖼️"
        elif "avatar" in text_clean.lower() or "profilov" in text_clean.lower():
            icon = "👤"
        elif "kopírov" in text_clean.lower() or "copied" in text_clean.lower():
            icon = "📋"

        duration = timeout if timeout > 0 else 3500
        if hasattr(self.main_win, "toast") and self.main_win.toast:
            self.main_win.toast.show_message(text_clean, icon=icon, duration_ms=duration)

    def clearMessage(self):
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        # Set window icon
        icon_name = "icon.ico" if sys.platform == "win32" else "icon.png"
        icon_path = get_asset_path(icon_name)
        if not icon_path.exists():
            icon_path = get_asset_path("icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.current_mode = "wallhaven"
        self.osu_theme = "all"
        self.current_search_id = 0

        self.current_page = 1
        self.last_page = 1
        self.total_count = 0
        self.current_color = ""
        self.active_search_worker: SearchWorker | OsuSearchWorker | None = None
        self.quick_download_worker: DownloadWorker | None = None
        self.update_check_worker: UpdateCheckWorker | None = None
        self.latest_update_info: UpdateInfo | None = None

        app = QApplication.instance()
        if app and not app.styleSheet():
            apply_theme(config.theme)

        self._init_ui()
        i18n.language_changed.connect(self.retranslate_ui)
        self.perform_search(page=1)

        # Check for updates in background on launch if enabled
        if config.check_updates_on_launch:
            QTimer.singleShot(2500, self._check_updates_quietly)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Modern Left Sidebar Navigation
        self.sidebar = KomorebiSidebar(self)
        self.sidebar.mode_changed.connect(self._set_mode)
        self.sidebar.theme_clicked.connect(self._show_quick_theme_menu)
        self.sidebar.auto_wall_toggled.connect(self._on_auto_wall_toggled)
        self.sidebar.settings_clicked.connect(self._open_settings)
        self.sidebar.update_clicked.connect(self._open_update_dialog)
        root_layout.addWidget(self.sidebar)

        # Compatibility references
        self.nav_capsule = self.sidebar.nav_container
        self.tab_wallhaven = self.sidebar.nav_container.buttons.get("wallhaven")
        self.tab_moewalls = self.sidebar.nav_container.buttons.get("moewalls")
        self.tab_osu = self.sidebar.nav_container.buttons.get("osu")
        self.tab_pfps = self.sidebar.nav_container.buttons.get("pfps")
        self.tab_installed = self.sidebar.nav_container.buttons.get("installed")
        self.auto_wall_btn = self.sidebar.auto_wall_btn
        self.theme_picker_btn = self.sidebar.theme_btn
        self.settings_btn = self.sidebar.settings_btn

        # 2. Main Content Canvas with dynamic Komorebi ambient background
        self.content_canvas = KomorebiAmbientCanvas(self)
        self.canvas_vlayout = QVBoxLayout(self.content_canvas)
        self.canvas_vlayout.setContentsMargins(0, 0, 0, 0)
        self.canvas_vlayout.setSpacing(0)
        root_layout.addWidget(self.content_canvas, 1)

        # 2A. Floating update notification banner (when new release is detected)
        self.banner_container = QWidget()
        b_layout = QVBoxLayout(self.banner_container)
        b_layout.setContentsMargins(18, 10, 18, 0)
        b_layout.setSpacing(0)
        self.update_banner = UpdateBanner(self)
        self.update_banner.update_clicked.connect(self._open_update_dialog)
        self.update_banner.dismissed.connect(lambda: self.banner_container.setVisible(False))
        b_layout.addWidget(self.update_banner)
        self.banner_container.setVisible(False)
        self.canvas_vlayout.addWidget(self.banner_container)

        # 2B. Spotlight Search Bar (at the top of canvas)
        self.spotlight_bar = QFrame()
        self.spotlight_bar.setObjectName("spotlightBar")
        s_layout = QHBoxLayout(self.spotlight_bar)
        s_layout.setContentsMargins(18, 10, 18, 10)
        s_layout.setSpacing(10)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 15px; color: #64748b; background: transparent;")
        s_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("spotlightInput")
        self.search_input.setFixedHeight(38)
        self.search_input.returnPressed.connect(self._on_search_triggered)
        self.search_input.setClearButtonEnabled(True)
        s_layout.addWidget(self.search_input, stretch=1)

        # Shortcuts to focus search (Ctrl+K or /)
        self.shortcut_search_k = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut_search_k.activated.connect(self._focus_search)
        self.shortcut_search_slash = QShortcut(QKeySequence("/"), self)
        self.shortcut_search_slash.activated.connect(self._focus_search)

        self.shortcut_badge = QLabel("Ctrl+K")
        self.shortcut_badge.setStyleSheet("""
            background: rgba(255, 255, 255, 0.06);
            color: #94a3b8;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 700;
            font-family: monospace;
        """)
        s_layout.addWidget(self.shortcut_badge)

        self.search_btn = QPushButton()
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.setFixedHeight(38)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self._on_search_triggered)
        s_layout.addWidget(self.search_btn)

        self.canvas_vlayout.addWidget(self.spotlight_bar)

        # 2A. Wallhaven Filter Bar
        self.wallhaven_filter_bar = QFrame()
        self.wallhaven_filter_bar.setObjectName("filterPanel")
        f_layout = QHBoxLayout(self.wallhaven_filter_bar)
        f_layout.setContentsMargins(14, 5, 14, 5)
        f_layout.setSpacing(5)

        # Category Chips
        self.cat_lbl = QLabel()
        self.cat_general = QPushButton()
        self.cat_general.setObjectName("filterChip")
        self.cat_general.setCheckable(True)
        self.cat_general.setChecked(True)
        self.cat_general.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cat_general.clicked.connect(self._on_filter_changed)
        f_layout.addWidget(self.cat_general)

        self.cat_anime = QPushButton()
        self.cat_anime.setObjectName("filterChip")
        self.cat_anime.setCheckable(True)
        self.cat_anime.setChecked(True)
        self.cat_anime.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cat_anime.clicked.connect(self._on_filter_changed)
        f_layout.addWidget(self.cat_anime)

        self.cat_people = QPushButton()
        self.cat_people.setObjectName("filterChip")
        self.cat_people.setCheckable(True)
        self.cat_people.setChecked(True)
        self.cat_people.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cat_people.clicked.connect(self._on_filter_changed)
        f_layout.addWidget(self.cat_people)

        # Subtle Separator 1
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("background-color: #1e2434; max-width: 1px; margin: 3px 4px;")
        f_layout.addWidget(sep1)

        # Purity Chips
        self.pur_lbl = QLabel()
        self.pur_sfw = QPushButton("SFW")
        self.pur_sfw.setObjectName("filterChip")
        self.pur_sfw.setCheckable(True)
        self.pur_sfw.setChecked(True)
        self.pur_sfw.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pur_sfw.clicked.connect(self._on_filter_changed)
        f_layout.addWidget(self.pur_sfw)

        self.pur_sketchy = QPushButton("Sketchy")
        self.pur_sketchy.setObjectName("sketchyChip")
        self.pur_sketchy.setCheckable(True)
        self.pur_sketchy.setChecked(False)
        self.pur_sketchy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pur_sketchy.clicked.connect(self._on_filter_changed)
        f_layout.addWidget(self.pur_sketchy)

        self.pur_nsfw = QPushButton("NSFW")
        self.pur_nsfw.setObjectName("nsfwChip")
        self.pur_nsfw.setCheckable(True)
        self.pur_nsfw.setChecked(False)
        self.pur_nsfw.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pur_nsfw.clicked.connect(self._on_nsfw_clicked)
        f_layout.addWidget(self.pur_nsfw)

        # Subtle Separator 2
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("background-color: #1e2434; max-width: 1px; margin: 3px 4px;")
        f_layout.addWidget(sep2)

        # Sorting & Filters
        self.sort_lbl = QLabel()
        self.sort_combo = QComboBox()
        self.sort_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.sort_combo.setMinimumWidth(100)
        self.sort_combo.currentIndexChanged.connect(self._on_sorting_changed)
        f_layout.addWidget(self.sort_combo)

        # Top Range combo
        self.range_combo = QComboBox()
        self.range_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.range_combo.setMinimumWidth(85)
        self.range_combo.currentIndexChanged.connect(self._on_filter_changed)
        f_layout.addWidget(self.range_combo)

        # Aspect Ratio combo
        self.ratio_combo = QComboBox()
        self.ratio_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.ratio_combo.setMinimumWidth(105)
        self.ratio_combo.currentIndexChanged.connect(self._on_filter_changed)
        f_layout.addWidget(self.ratio_combo)

        # Min Resolution combo
        self.res_combo = QComboBox()
        self.res_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.res_combo.setMinimumWidth(110)
        self.res_combo.currentIndexChanged.connect(self._on_filter_changed)
        f_layout.addWidget(self.res_combo)

        # Toggle Color Bar button (Wallhaven only)
        self.color_toggle_btn = QPushButton()
        self.color_toggle_btn.setObjectName("toolButton")
        self.color_toggle_btn.setCheckable(True)
        self.color_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_toggle_btn.clicked.connect(self._toggle_color_bar)
        f_layout.addWidget(self.color_toggle_btn)

        # Quick Reset Filters button
        self.reset_filter_btn = QPushButton("↺")
        self.reset_filter_btn.setToolTip(tr("reset_filters_tip"))
        self.reset_filter_btn.setFixedSize(30, 30)
        self.reset_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #151824;
                color: #94a3b8;
                border: 1.5px solid #232838;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #1f2434;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        self.reset_filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_filter_btn.clicked.connect(self._reset_wallhaven_filters)
        f_layout.addWidget(self.reset_filter_btn)

        f_layout.addStretch()
        self.canvas_vlayout.addWidget(self.wallhaven_filter_bar)

        # 2B. osu! Seasonal Filter Bar
        self.osu_filter_bar = QFrame()
        self.osu_filter_bar.setObjectName("filterPanel")
        self.osu_filter_bar.setVisible(False)
        osu_layout = QHBoxLayout(self.osu_filter_bar)
        osu_layout.setContentsMargins(16, 6, 16, 6)
        osu_layout.setSpacing(10)

        # Season selector
        self.osu_season_lbl = QLabel()
        self.osu_season_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        osu_layout.addWidget(self.osu_season_lbl)

        self.osu_season_combo = QComboBox()
        self.osu_season_combo.currentIndexChanged.connect(self._on_osu_filter_changed)
        osu_layout.addWidget(self.osu_season_combo)

        osu_layout.addSpacing(8)

        # Theme chips
        self.osu_theme_lbl = QLabel()
        self.osu_theme_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        osu_layout.addWidget(self.osu_theme_lbl)

        self.theme_chips: dict[str, QPushButton] = {}
        themes = [
            ("all", "theme_all"),
            ("Spring", "theme_spring"),
            ("Summer", "theme_summer"),
            ("Autumn", "theme_autumn"),
            ("Winter", "theme_winter"),
            ("Halloween", "theme_halloween"),
        ]
        for key, tr_key in themes:
            btn = QPushButton()
            btn.setObjectName("themeChip")
            btn.setCheckable(True)
            if key == "all":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=key: self._on_osu_theme_clicked(k))
            osu_layout.addWidget(btn)
            self.theme_chips[key] = btn

        osu_layout.addSpacing(8)

        # Sorting combo
        self.osu_sort_lbl = QLabel()
        self.osu_sort_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        osu_layout.addWidget(self.osu_sort_lbl)

        self.osu_sort_combo = QComboBox()
        self.osu_sort_combo.currentIndexChanged.connect(self._on_osu_filter_changed)
        osu_layout.addWidget(self.osu_sort_combo)

        osu_layout.addStretch()
        self.canvas_vlayout.addWidget(self.osu_filter_bar)

        # 2C. MoeWalls (Live Wallpapers) Filter Bar
        self.moe_filter_bar = QFrame()
        self.moe_filter_bar.setObjectName("filterPanel")
        self.moe_filter_bar.setVisible(False)
        moe_layout = QHBoxLayout(self.moe_filter_bar)
        moe_layout.setContentsMargins(16, 6, 16, 6)
        moe_layout.setSpacing(10)

        self.moe_cat_lbl = QLabel(tr("moe_category_label"))
        self.moe_cat_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        moe_layout.addWidget(self.moe_cat_lbl)

        self.moe_cat_combo = QComboBox()
        self.moe_cat_combo.setMinimumWidth(160)
        for cat_id, cat_name in moewalls_manager.get_categories():
            self.moe_cat_combo.addItem(cat_name, cat_id)
        self.moe_cat_combo.currentIndexChanged.connect(lambda: self.perform_search(page=1))
        moe_layout.addWidget(self.moe_cat_combo)

        moe_layout.addSpacing(8)

        self.moe_res_lbl = QLabel(tr("moe_res_label"))
        self.moe_res_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        moe_layout.addWidget(self.moe_res_lbl)

        self.moe_res_combo = QComboBox()
        self.moe_res_combo.setMinimumWidth(170)
        self.moe_res_combo.currentIndexChanged.connect(lambda: self.perform_search(page=1))
        moe_layout.addWidget(self.moe_res_combo)

        moe_badge = QLabel("🎬 20 000+ Video Wallpapers (MP4)")
        moe_badge.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; margin-left: 8px;")
        moe_layout.addWidget(moe_badge)

        moe_layout.addStretch()
        self.canvas_vlayout.addWidget(self.moe_filter_bar)

        # 2D. Installed Wallpapers Filter Bar
        self.installed_filter_bar = QFrame()
        self.installed_filter_bar.setObjectName("filterPanel")
        self.installed_filter_bar.setVisible(False)
        inst_layout = QHBoxLayout(self.installed_filter_bar)
        inst_layout.setContentsMargins(16, 6, 16, 6)
        inst_layout.setSpacing(10)

        # Provider combo
        self.inst_prov_lbl = QLabel(tr("installed_provider_label"))
        self.inst_prov_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        inst_layout.addWidget(self.inst_prov_lbl)

        self.inst_prov_combo = QComboBox()
        self.inst_prov_combo.currentIndexChanged.connect(lambda: self.perform_search(page=1))
        inst_layout.addWidget(self.inst_prov_combo)

        inst_layout.addSpacing(8)

        # Type combo
        self.inst_type_lbl = QLabel(tr("installed_type_label"))
        self.inst_type_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        inst_layout.addWidget(self.inst_type_lbl)

        self.inst_type_combo = QComboBox()
        self.inst_type_combo.currentIndexChanged.connect(lambda: self.perform_search(page=1))
        inst_layout.addWidget(self.inst_type_combo)

        inst_layout.addSpacing(8)

        # Sorting combo
        self.inst_sort_lbl = QLabel(tr("sorting_label"))
        self.inst_sort_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        inst_layout.addWidget(self.inst_sort_lbl)

        self.inst_sort_combo = QComboBox()
        self.inst_sort_combo.currentIndexChanged.connect(lambda: self.perform_search(page=1))
        inst_layout.addWidget(self.inst_sort_combo)

        inst_layout.addSpacing(12)

        # Open folder button
        self.inst_open_folder_btn = QPushButton(tr("installed_open_folder"))
        self.inst_open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inst_open_folder_btn.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        self.inst_open_folder_btn.clicked.connect(self._open_installed_folder)
        inst_layout.addWidget(self.inst_open_folder_btn)

        # Stats label
        self.inst_stats_lbl = QLabel("")
        self.inst_stats_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; margin-left: 8px;")
        inst_layout.addWidget(self.inst_stats_lbl)

        inst_layout.addStretch()
        self.canvas_vlayout.addWidget(self.installed_filter_bar)

        # 2E. PFPs (Profile Pictures & Avatars) Filter Bar
        self.pfps_filter_bar = QFrame()
        self.pfps_filter_bar.setObjectName("filterPanel")
        self.pfps_filter_bar.setVisible(False)
        pfps_layout = QHBoxLayout(self.pfps_filter_bar)
        pfps_layout.setContentsMargins(16, 6, 16, 6)
        pfps_layout.setSpacing(10)

        self.pfps_cat_lbl = QLabel(tr("pfps_category_label"))
        self.pfps_cat_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        pfps_layout.addWidget(self.pfps_cat_lbl)

        self.pfps_cat_combo = QComboBox()
        self.pfps_cat_combo.setMinimumWidth(160)
        self.pfps_cat_combo.currentIndexChanged.connect(lambda: self.perform_search(page=1))
        pfps_layout.addWidget(self.pfps_cat_combo)

        pfps_layout.addSpacing(8)

        self.pfps_sort_lbl = QLabel(tr("pfps_sort_label"))
        self.pfps_sort_lbl.setStyleSheet("color: #7e8a9f; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        pfps_layout.addWidget(self.pfps_sort_lbl)

        self.pfps_sort_combo = QComboBox()
        self.pfps_sort_combo.setMinimumWidth(150)
        self.pfps_sort_combo.currentIndexChanged.connect(lambda: self.perform_search(page=1))
        pfps_layout.addWidget(self.pfps_sort_combo)

        pfps_badge = QLabel("🎭 pfps.gg Avatars & GIFs")
        pfps_badge.setStyleSheet("color: #ec4899; font-size: 11px; font-weight: bold; margin-left: 8px;")
        pfps_layout.addWidget(pfps_badge)

        pfps_layout.addStretch()
        self.canvas_vlayout.addWidget(self.pfps_filter_bar)

        # 3. Color Bar (Collapsible, Wallhaven only)
        self.color_bar = ColorBar()
        self.color_bar.setVisible(False)
        self.color_bar.color_changed.connect(self._on_color_changed)
        self.canvas_vlayout.addWidget(self.color_bar)

        # 4. Scrollable Wallpaper Grid Area with Floating Frosted Pagination
        self.scroll_area = SmoothScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_widget = WallpaperGridWidget()
        self.grid_widget.card_clicked.connect(self._on_card_clicked)
        self.grid_widget.download_requested.connect(self._on_quick_download)
        self.grid_widget.uninstall_requested.connect(self._on_uninstall_requested)
        self.grid_widget.set_wall_requested.connect(self._on_quick_set_wallpaper)
        self.grid_widget.pfp_clicked.connect(self._on_pfp_clicked)
        self.grid_widget.pfp_download_requested.connect(self._on_pfp_download)
        self.grid_widget.pfp_set_avatar_requested.connect(self._on_pfp_set_avatar)
        self.grid_widget.pfp_copy_requested.connect(self._on_pfp_copy)
        self.scroll_area.setWidget(self.grid_widget)

        # Floating frosted glass pagination
        self.pagination = FloatingPagination()
        self.pagination.page_requested.connect(self.perform_search)

        # Compatibility aliases
        self.first_btn = self.pagination.first_btn
        self.prev_btn = self.pagination.prev_btn
        self.next_btn = self.pagination.next_btn
        self.last_btn = self.pagination.last_btn
        self.page_info_lbl = self.pagination.page_info_btn
        self.goto_lbl = QLabel()
        self.total_count_lbl = QLabel()
        self.pagination_frame = self.pagination

        self.canvas_wrapper = CanvasWrapper(self.scroll_area, self.pagination)
        self.canvas_vlayout.addWidget(self.canvas_wrapper, stretch=1)

        # Modern floating toast notification banner
        self.toast = KomorebiToast(self)

        # Status notifications via modern glassmorphic toasts instead of legacy gray status bar
        self.setStatusBar(None)
        self.status_bar = StatusToastProxy(self)

        self.retranslate_ui()

    def _retranslate_combos(self):
        def _populate(combo: QComboBox, items: list[tuple[str, str]]):
            cur = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for text, val in items:
                combo.addItem(text, val)
            if cur is not None:
                idx = combo.findData(cur)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            combo.adjustSize()
            combo.blockSignals(False)

        _populate(self.sort_combo, [
            (tr("sort_toplist"), "toplist"),
            (tr("sort_hot"), "hot"),
            (tr("sort_latest"), "date_added"),
            (tr("sort_views"), "views"),
            (tr("sort_favorites"), "favorites"),
            (tr("sort_random"), "random"),
            (tr("sort_relevance"), "relevance"),
        ])

        _populate(self.range_combo, [
            (tr("range_1M"), "1M"),
            (tr("range_1d"), "1d"),
            (tr("range_3d"), "3d"),
            (tr("range_1w"), "1w"),
            (tr("range_3M"), "3M"),
            (tr("range_6M"), "6M"),
            (tr("range_1y"), "1y"),
        ])

        _populate(self.ratio_combo, [
            (tr("ratio_any"), ""),
            (tr("ratio_16x9"), "16x9"),
            (tr("ratio_16x10"), "16x10"),
            (tr("ratio_21x9"), "21x9"),
            (tr("ratio_32x9"), "32x9"),
            (tr("ratio_9x16"), "9x16"),
        ])

        _populate(self.res_combo, [
            (tr("res_any"), ""),
            (tr("res_1080p"), "1920x1080"),
            (tr("res_1440p"), "2560x1440"),
            (tr("res_4k"), "3840x2160"),
            (tr("res_8k"), "7680x4320"),
        ])

    def _retranslate_osu_combos(self):
        # 1. Seasons
        cur_season = self.osu_season_combo.currentData()
        self.osu_season_combo.blockSignals(True)
        self.osu_season_combo.clear()
        self.osu_season_combo.addItem(tr("season_all", count=osu_manager.total_count), "all")
        for s in osu_manager.get_seasons():
            self.osu_season_combo.addItem(s, s)
        if cur_season is not None:
            idx = self.osu_season_combo.findData(cur_season)
            if idx >= 0:
                self.osu_season_combo.setCurrentIndex(idx)
        self.osu_season_combo.blockSignals(False)

        # 2. Sorting
        cur_sort = self.osu_sort_combo.currentData()
        self.osu_sort_combo.blockSignals(True)
        self.osu_sort_combo.clear()
        self.osu_sort_combo.addItem(tr("sort_osu_votes"), "votes")
        self.osu_sort_combo.addItem(tr("sort_osu_newest"), "newest")
        self.osu_sort_combo.addItem(tr("sort_osu_random"), "random")
        if cur_sort is not None:
            idx = self.osu_sort_combo.findData(cur_sort)
            if idx >= 0:
                self.osu_sort_combo.setCurrentIndex(idx)
        self.osu_sort_combo.blockSignals(False)

        # 3. Theme Chips
        theme_keys = {
            "all": "theme_all",
            "Spring": "theme_spring",
            "Summer": "theme_summer",
            "Autumn": "theme_autumn",
            "Winter": "theme_winter",
            "Halloween": "theme_halloween",
        }
        for key, tr_key in theme_keys.items():
            if key in self.theme_chips:
                self.theme_chips[key].setText(tr(tr_key))

    def _retranslate_installed_combos(self):
        def _populate(combo: QComboBox, items: list[tuple[str, str]]):
            cur = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for text, val in items:
                combo.addItem(text, val)
            if cur is not None:
                idx = combo.findData(cur)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        _populate(self.inst_prov_combo, [
            (tr("installed_provider_all"), "all"),
            (tr("installed_provider_wallhaven"), "wallhaven"),
            (tr("installed_provider_moewalls"), "moewalls"),
            (tr("installed_provider_osu"), "osu"),
        ])

        _populate(self.inst_type_combo, [
            (tr("installed_type_all"), "all"),
            (tr("installed_type_image"), "image"),
            (tr("installed_type_video"), "video"),
        ])

        _populate(self.inst_sort_combo, [
            (tr("installed_sort_newest"), "latest"),
            (tr("installed_sort_oldest"), "oldest"),
            (tr("installed_sort_name"), "name"),
            (tr("installed_sort_size"), "size"),
        ])

    def _retranslate_moe_combos(self):
        cur_res = self.moe_res_combo.currentData()
        self.moe_res_combo.blockSignals(True)
        self.moe_res_combo.clear()
        for res_id, tr_key in moewalls_manager.get_resolutions():
            self.moe_res_combo.addItem(tr(tr_key), res_id)
        if cur_res is not None:
            idx = self.moe_res_combo.findData(cur_res)
            if idx >= 0:
                self.moe_res_combo.setCurrentIndex(idx)
        self.moe_res_combo.blockSignals(False)

    def _retranslate_pfps_combos(self):
        cur_cat = self.pfps_cat_combo.currentData()
        self.pfps_cat_combo.blockSignals(True)
        self.pfps_cat_combo.clear()
        for cat_id, cat_cs, cat_en in pfps_client.get_categories():
            text = cat_cs if i18n.current_language == "cs" else cat_en
            self.pfps_cat_combo.addItem(text, cat_id)
        if cur_cat is not None:
            idx = self.pfps_cat_combo.findData(cur_cat)
            if idx >= 0:
                self.pfps_cat_combo.setCurrentIndex(idx)
        self.pfps_cat_combo.blockSignals(False)

        cur_sort = self.pfps_sort_combo.currentData()
        self.pfps_sort_combo.blockSignals(True)
        self.pfps_sort_combo.clear()
        for sort_id, sort_cs, sort_en in pfps_client.get_sorting_options():
            text = sort_cs if i18n.current_language == "cs" else sort_en
            self.pfps_sort_combo.addItem(text, sort_id)
        if cur_sort is not None:
            idx = self.pfps_sort_combo.findData(cur_sort)
            if idx >= 0:
                self.pfps_sort_combo.setCurrentIndex(idx)
        self.pfps_sort_combo.blockSignals(False)

    def retranslate_ui(self):
        self.setWindowTitle(tr("app_title"))
        if hasattr(self, "sidebar"):
            self.sidebar.retranslate_ui()

        if self.current_mode == "osu":
            self.search_input.setPlaceholderText(tr("osu_search_placeholder"))
        elif self.current_mode == "moewalls":
            self.search_input.setPlaceholderText(tr("moe_search_placeholder"))
        elif self.current_mode == "pfps":
            self.search_input.setPlaceholderText(tr("pfps_search_placeholder"))
        elif self.current_mode == "installed":
            self.search_input.setPlaceholderText(tr("installed_search_placeholder"))
        else:
            self.search_input.setPlaceholderText(tr("search_placeholder"))

        self.search_btn.setText(tr("search_button"))
        self.color_toggle_btn.setText(tr("colors_button"))
        self.auto_wall_btn.setText(tr("auto_wallpaper"))
        self.auto_wall_btn.setToolTip(tr("auto_wallpaper_tip"))
        self.settings_btn.setText(tr("settings_button"))

        # Wallhaven filter labels
        self.cat_lbl.setText(tr("categories_label"))
        self.cat_general.setText(tr("cat_general"))
        self.cat_anime.setText(tr("cat_anime"))
        self.cat_people.setText(tr("cat_people"))
        self.pur_lbl.setText(tr("purity_label"))
        self.sort_lbl.setText(tr("sorting_label"))
        self._retranslate_combos()

        # MoeWalls filter labels
        self.moe_cat_lbl.setText(tr("moe_category_label"))
        self.moe_res_lbl.setText(tr("moe_res_label"))
        self._retranslate_moe_combos()

        # osu! filter labels
        self.osu_season_lbl.setText(tr("season_label"))
        self.osu_theme_lbl.setText(tr("theme_label"))
        self.osu_sort_lbl.setText(tr("sorting_label"))
        self._retranslate_osu_combos()

        # Installed filter labels
        self.inst_prov_lbl.setText(tr("installed_provider_label"))
        self.inst_type_lbl.setText(tr("installed_type_label"))
        self.inst_sort_lbl.setText(tr("sorting_label"))
        self.inst_open_folder_btn.setText(tr("installed_open_folder"))
        self._retranslate_installed_combos()

        # PFPs filter labels
        self.pfps_cat_lbl.setText(tr("pfps_category_label"))
        self.pfps_sort_lbl.setText(tr("pfps_sort_label"))
        self._retranslate_pfps_combos()

        if hasattr(self, "reset_filter_btn"):
            self.reset_filter_btn.setToolTip(tr("reset_filters_tip"))

        if hasattr(self, "sidebar"):
            self.sidebar.retranslate_ui()
        elif hasattr(self, "nav_capsule"):
            self.nav_capsule.retranslate_ui()

        # Pagination
        if hasattr(self, "pagination"):
            item_type = "avatars" if self.current_mode == "pfps" else "wallpapers"
            self.pagination.update_pagination(self.current_page, self.last_page, self.total_count, item_type=item_type)
            self.pagination.retranslate_ui()
            if hasattr(self, "canvas_wrapper"):
                self.canvas_wrapper.reposition_pagination()

        if self.current_mode == "osu":
            self.total_count_lbl.setText(tr("osu_total_found", total=f"{self.total_count:,}"))
        elif self.current_mode == "moewalls":
            self.total_count_lbl.setText(tr("moe_total_found", total=f"{self.total_count:,}"))
        elif self.current_mode == "installed":
            stats = installed_manager.get_stats()
            self.total_count_lbl.setText(tr("installed_total_found", total=f"{self.total_count:,}", size=stats["human_size"]))
            self.inst_stats_lbl.setText(f"💾 {stats['human_size']}")
        elif self.current_mode == "pfps":
            self.total_count_lbl.setText(tr("pfps_showing_count", count=self.total_count, page=self.current_page))
        else:
            self.total_count_lbl.setText(tr("total_found", total=f"{self.total_count:,}"))

        if hasattr(self, "update_banner") and self.update_banner.isVisible() and self.latest_update_info:
            self.update_banner.show_update(self.latest_update_info)

    def _set_mode(self, mode: str):
        if hasattr(self, "sidebar"):
            self.sidebar.set_mode(mode)
        elif hasattr(self, "nav_capsule"):
            self.nav_capsule.set_mode(mode)

        if mode == self.current_mode:
            return

        self.current_mode = mode

        is_wall = (mode == "wallhaven")
        is_moe = (mode == "moewalls")
        is_osu = (mode == "osu")
        is_pfps = (mode == "pfps")
        is_inst = (mode == "installed")

        self.wallhaven_filter_bar.setVisible(is_wall)
        self.moe_filter_bar.setVisible(is_moe)
        self.osu_filter_bar.setVisible(is_osu)
        self.pfps_filter_bar.setVisible(is_pfps)
        self.installed_filter_bar.setVisible(is_inst)
        self.color_toggle_btn.setVisible(is_wall)
        self.auto_wall_btn.setVisible(not is_pfps)
        if not is_wall:
            self.color_bar.setVisible(False)
        else:
            self.color_bar.setVisible(self.color_toggle_btn.isChecked())

        self.search_input.clear()
        if is_wall:
            self.search_input.setPlaceholderText(tr("search_placeholder"))
        elif is_moe:
            self.search_input.setPlaceholderText(tr("moe_search_placeholder"))
        elif is_osu:
            self.search_input.setPlaceholderText(tr("osu_search_placeholder"))
        elif is_pfps:
            self.search_input.setPlaceholderText(tr("pfps_search_placeholder"))
        else:
            self.search_input.setPlaceholderText(tr("installed_search_placeholder"))

        self.perform_search(page=1)

    def _on_osu_theme_clicked(self, selected_key: str):
        self.osu_theme = selected_key
        for key, btn in self.theme_chips.items():
            btn.blockSignals(True)
            btn.setChecked(key == selected_key)
            btn.blockSignals(False)
        self.perform_search(page=1)

    def _on_osu_filter_changed(self):
        self.perform_search(page=1)

    def _toggle_color_bar(self):
        is_visible = self.color_toggle_btn.isChecked()
        self.color_bar.setVisible(is_visible)

    def _on_color_changed(self, hex_code: str):
        self.current_color = hex_code
        self.perform_search(page=1)

    def _on_sorting_changed(self):
        sort_val = self.sort_combo.currentData()
        # Only show top_range when sort is toplist
        self.range_combo.setVisible(sort_val == "toplist")
        self.perform_search(page=1)

    def _on_filter_changed(self):
        self.perform_search(page=1)

    def _reset_wallhaven_filters(self):
        self.cat_general.setChecked(True)
        self.cat_anime.setChecked(True)
        self.cat_people.setChecked(True)
        self.pur_sfw.setChecked(True)
        self.pur_sketchy.setChecked(False)
        self.pur_nsfw.setChecked(False)
        idx_sort = self.sort_combo.findData("toplist")
        if idx_sort >= 0:
            self.sort_combo.setCurrentIndex(idx_sort)
        idx_range = self.range_combo.findData("1M")
        if idx_range >= 0:
            self.range_combo.setCurrentIndex(idx_range)
        idx_ratio = self.ratio_combo.findData("")
        if idx_ratio >= 0:
            self.ratio_combo.setCurrentIndex(idx_ratio)
        idx_res = self.res_combo.findData("")
        if idx_res >= 0:
            self.res_combo.setCurrentIndex(idx_res)
        self.color_bar.clear_selection()
        self.current_color = ""
        self.search_input.clear()
        self.perform_search(page=1)

    def _on_nsfw_clicked(self):
        if self.pur_nsfw.isChecked() and not config.api_key:
            res = QMessageBox.question(
                self,
                tr("nsfw_req_title"),
                tr("nsfw_req_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if res == QMessageBox.StandardButton.Yes:
                self._open_settings()
            if not config.api_key:
                self.pur_nsfw.setChecked(False)
                return
        self.perform_search(page=1)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.auto_wall_btn.setChecked(config.auto_set_wallpaper)
            if hasattr(self, "sidebar"):
                self.sidebar.update_theme_display(config.theme)
            if hasattr(self, "pagination"):
                self.pagination._apply_capsule_style()
            if hasattr(self, "content_canvas") and hasattr(self.content_canvas, "set_effects_enabled"):
                self.content_canvas.set_effects_enabled(config.background_effects)
            # If API key changed, refresh
            self.perform_search(page=self.current_page)

    def _check_updates_quietly(self):
        """Asynchronously checks GitHub for updates after app startup (throttled to once every 4h)."""
        if not config.get("auto_check_updates", True):
            return
        last_check = config.last_update_check
        if time.time() - last_check < 4 * 3600:
            return
        self.update_check_worker = UpdateCheckWorker(current_ver=__version__, parent=self)
        self.update_check_worker.check_finished.connect(self._on_quiet_update_check_finished)
        self.update_check_worker.start()

    def _on_quiet_update_check_finished(self, info: UpdateInfo):
        self.latest_update_info = info
        if info.has_update:
            if hasattr(self, "banner_container"):
                self.banner_container.setVisible(True)
            if hasattr(self, "update_banner"):
                self.update_banner.show_update(info)
            if hasattr(self, "sidebar"):
                self.sidebar.show_update_available(info.latest_version)

    def _open_update_dialog(self, info: UpdateInfo | None = None):
        """Opens the full-featured update dialog."""
        if not isinstance(info, UpdateInfo):
            info = self.latest_update_info
        if not info:
            info = UpdateInfo(current_version=__version__, latest_version=f"v{__version__}")
        dlg = UpdateDialog(info, self)
        dlg.exec()

    def _on_auto_wall_toggled(self):
        config.auto_set_wallpaper = self.auto_wall_btn.isChecked()
        status = tr("status_auto_wall_on") if config.auto_set_wallpaper else tr("status_auto_wall_off")
        self.status_bar.showMessage(tr("status_auto_wall_msg", status=status), 4000)

    def _on_search_triggered(self):
        self.perform_search(page=1)

    def _get_categories_str(self) -> str:
        g = "1" if self.cat_general.isChecked() else "0"
        a = "1" if self.cat_anime.isChecked() else "0"
        p = "1" if self.cat_people.isChecked() else "0"
        # If none checked, default to all
        if g == "0" and a == "0" and p == "0":
            return "111"
        return f"{g}{a}{p}"

    def _get_purity_str(self) -> str:
        s = "1" if self.pur_sfw.isChecked() else "0"
        k = "1" if self.pur_sketchy.isChecked() else "0"
        n = "1" if (self.pur_nsfw.isChecked() and config.api_key) else "0"
        if s == "0" and k == "0" and n == "0":
            return "100"
        return f"{s}{k}{n}"

    def perform_search(self, page: int = 1):
        if page < 1:
            page = 1

        self.current_search_id += 1
        search_id = self.current_search_id

        self.status_bar.showMessage(tr("status_searching", page=page))
        self.search_btn.setEnabled(False)

        query = self.search_input.text().strip()

        if self.current_mode == "installed":
            prov = self.inst_prov_combo.currentData() or "all"
            mtype = self.inst_type_combo.currentData() or "all"
            sorting = self.inst_sort_combo.currentData() or "latest"
            self.active_search_worker = InstalledSearchWorker(
                search_id=search_id,
                query=query,
                provider=prov,
                media_type=mtype,
                sorting=sorting,
                page=page,
                per_page=24,
            )
        elif self.current_mode == "moewalls":
            cat = self.moe_cat_combo.currentData() or "all"
            res = self.moe_res_combo.currentData() or "all"
            self.active_search_worker = MoeSearchWorker(
                search_id=search_id,
                query=query,
                category=cat,
                resolution=res,
                page=page,
            )
        elif self.current_mode == "osu":
            season = self.osu_season_combo.currentData() or "all"
            theme = self.osu_theme
            sorting = self.osu_sort_combo.currentData() or "votes"
            self.active_search_worker = OsuSearchWorker(
                search_id=search_id,
                query=query,
                season=season,
                theme=theme,
                sorting=sorting,
                page=page,
                per_page=24,
            )
        elif self.current_mode == "pfps":
            cat = self.pfps_cat_combo.currentData() or "anime"
            sorting = self.pfps_sort_combo.currentData() or "top"
            self.active_search_worker = PfpsSearchWorker(
                search_id=search_id,
                query=query,
                category=cat,
                sort=sorting,
                page=page,
            )
            self.active_search_worker.finished.connect(self._on_pfp_search_success)
            self.active_search_worker.failed.connect(self._on_search_failed)
            self.active_search_worker.start()
            return
        else:
            cats = self._get_categories_str()
            purity = self._get_purity_str()
            sorting = self.sort_combo.currentData()
            top_range = self.range_combo.currentData() if sorting == "toplist" else ""
            ratios = self.ratio_combo.currentData()
            atleast = self.res_combo.currentData()
            colors = self.current_color

            self.active_search_worker = SearchWorker(
                search_id=search_id,
                query=query,
                categories=cats,
                purity=purity,
                sorting=sorting,
                top_range=top_range,
                ratios=ratios,
                atleast=atleast,
                colors=colors,
                page=page,
            )

        self.active_search_worker.finished.connect(self._on_search_success)
        self.active_search_worker.failed.connect(self._on_search_failed)
        self.active_search_worker.start()

    def _on_search_success(self, search_id: int, result: SearchResult):
        if search_id != self.current_search_id:
            return

        self.search_btn.setEnabled(True)
        self.current_page = result.current_page
        self.last_page = max(1, result.last_page)
        self.total_count = result.total

        self.grid_widget.set_items(result.items)
        # Scroll back to top
        self.scroll_area.verticalScrollBar().setValue(0)

        # Update floating pagination & sidebar counts
        if hasattr(self, "pagination"):
            self.pagination.update_pagination(self.current_page, self.last_page, self.total_count)
            if hasattr(self, "canvas_wrapper"):
                self.canvas_wrapper.reposition_pagination()

        if self.current_mode == "installed" and hasattr(self, "sidebar"):
            self.sidebar.set_installed_count(result.total)

        if self.current_mode == "osu":
            self.total_count_lbl.setText(tr("osu_total_found", total=f"{result.total:,}"))
        elif self.current_mode == "moewalls":
            self.total_count_lbl.setText(tr("moe_total_found", total=f"{result.total:,}"))
        elif self.current_mode == "installed":
            stats = installed_manager.get_stats()
            self.total_count_lbl.setText(tr("installed_total_found", total=f"{result.total:,}", size=stats["human_size"]))
            self.inst_stats_lbl.setText(f"💾 {stats['human_size']}")
        else:
            self.total_count_lbl.setText(tr("total_found", total=f"{result.total:,}"))

        self.status_bar.showMessage(tr("status_loaded", count=len(result.items), total=f"{result.total:,}"))

    def _on_search_failed(self, search_id: int, error: str):
        if search_id != self.current_search_id:
            return

        self.search_btn.setEnabled(True)
        self.status_bar.showMessage(tr("status_search_error", error=error))
        QMessageBox.warning(self, tr("search_failed_title"), tr("search_failed_msg", error=error))

    def _on_pfp_search_success(self, search_id: int, items: list[PfpItem], has_next: bool, page: int):
        if search_id != self.current_search_id:
            return

        self.search_btn.setEnabled(True)
        self.current_page = page
        self.last_page = page + 1 if has_next else page
        self.total_count = len(items)

        self.grid_widget.set_pfp_items(items)
        self.scroll_area.verticalScrollBar().setValue(0)

        # Update floating pagination
        if hasattr(self, "pagination"):
            self.pagination.update_pagination(self.current_page, self.last_page, 0, item_type="avatars")
            self.pagination.next_btn.setEnabled(has_next)
            self.pagination.last_btn.setEnabled(False)
            if hasattr(self, "canvas_wrapper"):
                self.canvas_wrapper.reposition_pagination()

        self.total_count_lbl.setText(tr("pfps_showing_count", count=len(items), page=self.current_page))
        self.status_bar.showMessage(tr("pfps_loaded_status", count=len(items), page=self.current_page))

    def _on_card_clicked(self, item: WallpaperItem):
        if isinstance(item, PfpItem):
            self._on_pfp_clicked(item)
            return
        dlg = DetailDialog(item, self)
        dlg.tag_clicked.connect(self._search_by_tag)
        dlg.download_completed.connect(lambda p: self._on_download_completed(p, item))
        dlg.uninstalled.connect(lambda it: self.perform_search(page=self.current_page))
        dlg.exec()

    def _search_by_tag(self, tag_name: str):
        clean_tag = tag_name.lstrip("#")
        self.search_input.setText(clean_tag)
        self.perform_search(page=1)

    def _on_quick_download(self, item: WallpaperItem):
        # User requested quick download from card button
        # Respect user requirement: "Při každém stažení se zeptat dialogem na umístění"
        is_animated = getattr(item, "is_animated", False)
        ext = ".mp4" if is_animated else (os.path.splitext(item.path)[1] or ".jpg")

        if getattr(item, "_osu_meta", None):
            meta = item._osu_meta
            artist = "".join(c for c in meta.get("artist", "artist") if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            title = "".join(c for c in meta.get("title", item.id) if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            season = "".join(c for c in meta.get("season", "osu") if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            suggested_name = f"osu-{season}-{artist}-{title}{ext}"
        elif is_animated:
            clean_title = "".join(c for c in getattr(item, "_display_title", item.id) if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
            suggested_name = f"moewalls-{clean_title}{ext}"
        else:
            suggested_name = f"wallhaven-{item.id}{ext}"

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

        self.status_bar.showMessage(tr("status_downloading", id=item.id, filename=os.path.basename(save_path)))

        self.quick_download_worker = DownloadWorker(item, save_path)
        self.quick_download_worker.progress.connect(
            lambda cur, tot: self.status_bar.showMessage(
                tr("status_download_progress", id=item.id, cur=cur // (1024 * 1024), tot=tot // (1024 * 1024))
            )
        )
        self.quick_download_worker.finished.connect(
            lambda path, it=item: self._on_download_completed(path, it)
        )
        self.quick_download_worker.failed.connect(
            lambda err: QMessageBox.critical(self, tr("download_failed_title"), tr("download_failed_msg", error=err))
        )
        self.quick_download_worker.start()

    def _on_download_completed(self, path: str, item: WallpaperItem | None = None):
        filename = os.path.basename(path)
        if item:
            try:
                installed_manager.register_download(path, item)
            except Exception as e:
                print(f"Error registering downloaded wallpaper: {e}")

        if config.auto_set_wallpaper:
            ok, msg = set_desktop_wallpaper(
                path,
                config.custom_wallpaper_cmd,
                config.wallpaper_setter,
                config.custom_video_wallpaper_cmd,
            )
            if ok:
                self.status_bar.showMessage(tr("status_download_done_wall", filename=filename), 8000)
                if hasattr(self, "toast"):
                    self.toast.show_message(tr("toast_wall_set", filename=filename), icon="🖼️")
            else:
                self.status_bar.showMessage(tr("status_download_fail_wall", filename=filename, error=msg), 8000)
                if hasattr(self, "toast"):
                    self.toast.show_message(tr("toast_wall_saved", filename=filename), icon="💾")
        else:
            self.status_bar.showMessage(tr("status_download_done", filename=filename), 8000)
            if hasattr(self, "toast"):
                self.toast.show_message(tr("toast_wall_saved", filename=filename), icon="💾")

    def _open_installed_folder(self):
        folder = config.default_download_dir
        if os.path.isdir(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _on_uninstall_requested(self, item: WallpaperItem):
        title = getattr(item, "_display_title", "") or f"Wallpaper #{item.id}"
        target_path = getattr(item, "local_path", "") or item.path
        filename = os.path.basename(target_path) if target_path else item.id

        res = QMessageBox.question(
            self,
            tr("confirm_uninstall_title"),
            tr("confirm_uninstall_msg", title=title, filename=filename),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            ok, err = installed_manager.uninstall_wallpaper(item)
            if ok:
                self.status_bar.showMessage(tr("status_uninstalled", title=title), 6000)
                if hasattr(self, "toast"):
                    self.toast.show_message(tr("toast_wall_uninstalled", title=title), icon="🗑️")
                self.perform_search(page=self.current_page)
            else:
                QMessageBox.critical(self, tr("uninstall_error_title"), tr("uninstall_error_msg", error=err))

    def _on_quick_set_wallpaper(self, item: WallpaperItem):
        target_path = getattr(item, "local_path", "") or item.path
        if not target_path or not os.path.exists(target_path):
            QMessageBox.warning(self, tr("set_wall_error_title"), "File not found on disk.")
            return

        ok, msg = set_desktop_wallpaper(
            target_path,
            config.custom_wallpaper_cmd,
            config.wallpaper_setter,
            config.custom_video_wallpaper_cmd,
        )
        filename = os.path.basename(target_path)
        if ok:
            self.status_bar.showMessage(tr("status_download_done_wall", filename=filename), 8000)
            if hasattr(self, "toast"):
                self.toast.show_message(tr("toast_wall_set", filename=filename), icon="🖼️")
        else:
            self.status_bar.showMessage(tr("status_download_fail_wall", filename=filename, error=msg), 8000)

    def _on_pfp_clicked(self, item: PfpItem):
        if not isinstance(item, PfpItem):
            self._on_card_clicked(item)
            return
        dlg = PfpDetailDialog(item, self)
        dlg.exec()

    def _on_pfp_download(self, item: PfpItem):
        self.status_bar.showMessage(tr("pfp_downloading_status", title=item.title))
        ok, res = pfps_client.download_pfp(item)
        if ok:
            self.status_bar.showMessage(tr("pfp_saved_status", path=res), 8000)
            if hasattr(self, "toast"):
                self.toast.show_message(tr("toast_pfp_saved", filename=os.path.basename(res)), icon="💾")
        else:
            QMessageBox.critical(
                self,
                tr("pfp_download_error_title"),
                tr("pfp_download_error_msg", error=res),
            )

    def _on_pfp_set_avatar(self, item: PfpItem):
        self.status_bar.showMessage(tr("pfp_setting_avatar_status", title=item.title))
        ok, msg = pfps_client.set_system_avatar(item)
        if ok:
            self.status_bar.showMessage(f"✓ {msg}", 8000)
            if hasattr(self, "toast"):
                self.toast.show_message(tr("toast_pfp_avatar_set"), icon="👤")
            QMessageBox.information(
                self,
                tr("pfp_avatar_changed_title"),
                msg,
            )
        else:
            QMessageBox.warning(
                self,
                tr("pfp_avatar_error_title"),
                msg,
            )

    def _on_pfp_copy(self, item: PfpItem):
        self.status_bar.showMessage(tr("pfp_copied_status", title=item.title), 6000)
        if hasattr(self, "toast"):
            self.toast.show_message(tr("toast_pfp_copied", title=item.title), icon="📋")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            pw = self.width()
            tw = self.toast.width()
            th = self.toast.height()
            self.toast.move((pw - tw) // 2, self.height() - th - 24)

    def _focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _show_quick_theme_menu(self):
        menu = QMenu(self)
        pal = get_palette(config.theme)
        bg = pal.get("bg_surface", "#12151f")
        fg = pal.get("text_primary", "#f8fafc")
        border = pal.get("border", "#283045")
        accent = pal.get("accent", "#6366f1")
        accent_text = pal.get("accent_text", "#ffffff")

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 7px 22px;
                border-radius: 6px;
                font-size: 12.5px;
                font-weight: 500;
            }}
            QMenu::item:selected {{
                background: {accent};
                color: {accent_text};
            }}
        """)
        themes = get_available_themes()
        cur_theme = config.theme
        for theme_id, display_name in themes:
            action = menu.addAction(display_name)
            action.setCheckable(True)
            action.setChecked(theme_id == cur_theme)
            action.triggered.connect(lambda chk, tid=theme_id, dname=display_name: self._on_quick_theme_selected(tid, dname))

        menu.adjustSize()
        menu_sz = menu.sizeHint()

        # Pop out to the right of the sidebar, aligned with the theme button
        btn = self.sidebar.theme_btn if hasattr(self, "sidebar") else self.theme_picker_btn
        btn_top_right = btn.mapToGlobal(QPoint(btn.width() + 8, 0))
        target_x = btn_top_right.x()
        target_y = btn_top_right.y() + btn.height() - menu_sz.height()
        target_y = max(16, target_y)
        menu.exec(QPoint(target_x, target_y))

    def _on_quick_theme_selected(self, theme_id: str, display_name: str = ""):
        config.theme = theme_id
        config.save()
        apply_theme(theme_id)
        if hasattr(self, "sidebar"):
            self.sidebar.update_theme_display(theme_id)
        if hasattr(self, "pagination"):
            self.pagination._apply_capsule_style()
        if hasattr(self, "content_canvas") and hasattr(self.content_canvas, "update"):
            self.content_canvas.update()
        if hasattr(self, "toast"):
            name = display_name or theme_id.capitalize()
            self.toast.show_message(tr("toast_theme_changed", name=name), icon="🎨", duration_ms=2500)
