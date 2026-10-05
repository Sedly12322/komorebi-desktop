import os
import shutil
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
    QGroupBox,
    QCheckBox,
    QComboBox,
    QScrollArea,
    QWidget,
)
from wallhaven.config import config
from wallhaven.cache import CACHE_DIR
from wallhaven.styles import get_available_themes, get_stylesheet, is_matugen_available
from PyQt6.QtWidgets import QApplication
from wallhaven.wallpaper import (
    detect_wallpaper_command,
    get_available_wallpaper_setters,
    set_desktop_wallpaper,
)
from wallhaven import __version__
from wallhaven.updater import UpdateCheckWorker, UpdateDialog, UpdateInfo
from wallhaven.i18n import tr, i18n


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings_title"))
        self.setMinimumWidth(620)
        self.resize(650, 680)
        self.setModal(True)
        self._all_setters = get_available_wallpaper_setters()
        self.check_worker: UpdateCheckWorker | None = None
        self.latest_update_info: UpdateInfo | None = None

        # Store initial settings for preview rollback on cancel
        self._orig_theme = config.get("theme", "matugen" if is_matugen_available() else "dark")
        self._orig_lang = i18n.current_language
        self._orig_effects = config.background_effects

        self._init_ui()
        i18n.language_changed.connect(self.retranslate_ui)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)
        root_layout.setContentsMargins(20, 20, 20, 16)

        self.title_lbl = QLabel(tr("settings_title"))
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        root_layout.addWidget(self.title_lbl)

        # Responsive Scroll Area for settings sections
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(scroll_widget)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 4, 8, 4)

        # 1. Appearance & Language Section
        self.theme_group = QGroupBox(tr("theme_section"))
        self._apply_group_style(self.theme_group)
        theme_layout = QVBoxLayout(self.theme_group)
        theme_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.theme_label = QLabel(tr("theme_label"))
        self.theme_label.setStyleSheet("color: #cbd5e1; font-size: 12px; min-width: 125px;")
        row1.addWidget(self.theme_label)

        self.theme_combo = QComboBox()
        for tid, tname in get_available_themes():
            self.theme_combo.addItem(tname, tid)
        curr_theme = config.get("theme", "matugen" if is_matugen_available() else "dark")
        t_idx = self.theme_combo.findData(curr_theme)
        if t_idx >= 0:
            self.theme_combo.setCurrentIndex(t_idx)
        elif self.theme_combo.findData("matugen") >= 0:
            self.theme_combo.setCurrentIndex(self.theme_combo.findData("matugen"))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        row1.addWidget(self.theme_combo, 1)
        theme_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.lang_label = QLabel(tr("lang_label"))
        self.lang_label.setStyleSheet("color: #cbd5e1; font-size: 12px; min-width: 125px;")
        row2.addWidget(self.lang_label)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Čeština (Czech)", "cs")
        idx = self.lang_combo.findData(i18n.current_language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        row2.addWidget(self.lang_combo, 1)
        theme_layout.addLayout(row2)

        self.bg_effects_cb = QCheckBox(tr("bg_effects_label"))
        self.bg_effects_cb.setChecked(config.background_effects)
        self.bg_effects_cb.setStyleSheet("color: #cbd5e1; font-size: 12px; font-weight: 600; margin-top: 4px;")
        self.bg_effects_cb.toggled.connect(self._on_bg_effects_toggled)
        theme_layout.addWidget(self.bg_effects_cb)

        layout.addWidget(self.theme_group)

        # 2. API Key Section
        self.api_group = QGroupBox(tr("api_group"))
        self._apply_group_style(self.api_group)
        api_layout = QVBoxLayout(self.api_group)
        api_layout.setSpacing(10)

        self.api_desc = QLabel(tr("api_desc"))
        self.api_desc.setOpenExternalLinks(True)
        self.api_desc.setWordWrap(True)
        self.api_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        api_layout.addWidget(self.api_desc)

        api_input_row = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText(tr("api_placeholder"))
        self.api_key_input.setText(config.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_input_row.addWidget(self.api_key_input)

        self.toggle_key_btn = QPushButton("👁")
        self.toggle_key_btn.setToolTip(tr("api_toggle_tip"))
        self.toggle_key_btn.setFixedWidth(36)
        self.toggle_key_btn.clicked.connect(self._toggle_api_visibility)
        api_input_row.addWidget(self.toggle_key_btn)

        api_layout.addLayout(api_input_row)
        layout.addWidget(self.api_group)

        # 3. Download Directory Section
        self.dir_group = QGroupBox(tr("dir_group"))
        self._apply_group_style(self.dir_group)
        dir_layout = QVBoxLayout(self.dir_group)
        dir_layout.setSpacing(10)

        self.dir_desc = QLabel(tr("dir_desc"))
        self.dir_desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        dir_layout.addWidget(self.dir_desc)

        dir_input_row = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setText(config.default_download_dir)
        dir_input_row.addWidget(self.dir_input)

        self.browse_btn = QPushButton(tr("browse_button"))
        self.browse_btn.clicked.connect(self._on_browse_dir)
        dir_input_row.addWidget(self.browse_btn)

        dir_layout.addLayout(dir_input_row)
        layout.addWidget(self.dir_group)

        # 4. Wallpaper Section (Linux & Windows)
        self.wall_group = QGroupBox(tr("wall_group"))
        self._apply_group_style(self.wall_group)
        wall_layout = QVBoxLayout(self.wall_group)
        wall_layout.setSpacing(10)

        # Auto set checkbox
        self.auto_wall_cb = QCheckBox(tr("auto_wall_checkbox"))
        self.auto_wall_cb.setChecked(config.auto_set_wallpaper)
        self.auto_wall_cb.setStyleSheet("font-weight: bold; color: #f1f5f9; font-size: 12px;")
        wall_layout.addWidget(self.auto_wall_cb)

        # Method selector row
        method_row = QHBoxLayout()
        self.method_lbl = QLabel(tr("wallpaper_setter_label"))
        self.method_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        method_row.addWidget(self.method_lbl)

        self.setter_combo = QComboBox()
        self.setter_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self._populate_setter_combo()
        self.setter_combo.currentIndexChanged.connect(self._on_setter_changed)
        method_row.addWidget(self.setter_combo, stretch=1)

        # Test wallpaper setter button
        self.test_wall_btn = QPushButton(tr("test_setter_btn"))
        self.test_wall_btn.setObjectName("headerToolBtn")
        self.test_wall_btn.setToolTip(tr("test_setter_tip"))
        self.test_wall_btn.clicked.connect(self._on_test_wallpaper)
        method_row.addWidget(self.test_wall_btn)

        wall_layout.addLayout(method_row)

        # Active detection description
        detected_list = detect_wallpaper_command()
        detected_str = " ".join(detected_list) if detected_list else tr("tool_none")
        self.det_lbl = QLabel(tr("detected_tool", tool=detected_str))
        self.det_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.det_lbl.setWordWrap(True)
        wall_layout.addWidget(self.det_lbl)

        # Custom image command row
        self.custom_cmd_lbl = QLabel(tr("custom_cmd_label"))
        self.custom_cmd_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        wall_layout.addWidget(self.custom_cmd_lbl)

        self.custom_cmd_input = QLineEdit()
        self.custom_cmd_input.setPlaceholderText(tr("custom_cmd_placeholder"))
        self.custom_cmd_input.setText(config.custom_wallpaper_cmd)
        wall_layout.addWidget(self.custom_cmd_input)

        # Custom video command row
        self.custom_video_lbl = QLabel(tr("custom_video_cmd_label"))
        self.custom_video_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        wall_layout.addWidget(self.custom_video_lbl)

        self.custom_video_input = QLineEdit()
        self.custom_video_input.setPlaceholderText(tr("custom_video_placeholder"))
        self.custom_video_input.setText(config.custom_video_wallpaper_cmd)
        wall_layout.addWidget(self.custom_video_input)

        layout.addWidget(self.wall_group)

        # 5. Cache Section
        self.cache_group = QGroupBox(tr("cache_group"))
        self._apply_group_style(self.cache_group)
        cache_layout = QHBoxLayout(self.cache_group)

        self.cache_size_lbl = QLabel(self._get_cache_size_str())
        self.cache_size_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        cache_layout.addWidget(self.cache_size_lbl)

        cache_layout.addStretch()

        self.clear_cache_btn = QPushButton(tr("cache_clear_button"))
        self.clear_cache_btn.setStyleSheet("color: #f87171; border-color: #7f1d1d;")
        self.clear_cache_btn.clicked.connect(self._on_clear_cache)
        cache_layout.addWidget(self.clear_cache_btn)

        layout.addWidget(self.cache_group)

        # 6. Updates Section
        self.update_group = QGroupBox(tr("update_section"))
        self._apply_group_style(self.update_group)
        update_layout = QVBoxLayout(self.update_group)
        update_layout.setSpacing(10)

        up_row1 = QHBoxLayout()
        self.cur_ver_lbl = QLabel(f"Komorebi Desktop v{__version__}")
        self.cur_ver_lbl.setStyleSheet("color: #f1f5f9; font-weight: 700; font-size: 12.5px;")
        up_row1.addWidget(self.cur_ver_lbl)

        up_row1.addStretch()

        self.check_update_btn = QPushButton(tr("update_check_btn"))
        self.check_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_update_btn.clicked.connect(self._on_check_updates)
        up_row1.addWidget(self.check_update_btn)

        self.apply_update_btn = QPushButton(tr("update_btn_apply"))
        self.apply_update_btn.setObjectName("primaryButton")
        self.apply_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_update_btn.setVisible(False)
        self.apply_update_btn.clicked.connect(self._on_open_update_dialog)
        up_row1.addWidget(self.apply_update_btn)

        update_layout.addLayout(up_row1)

        self.update_status_lbl = QLabel("")
        self.update_status_lbl.setStyleSheet("color: #94a3b8; font-size: 11.5px;")
        self.update_status_lbl.setWordWrap(True)
        update_layout.addWidget(self.update_status_lbl)

        self.auto_check_cb = QCheckBox(tr("update_auto_check"))
        self.auto_check_cb.setChecked(config.check_updates_on_launch)
        self.auto_check_cb.setStyleSheet("color: #cbd5e1; font-size: 12px; margin-top: 2px;")
        update_layout.addWidget(self.auto_check_cb)

        layout.addWidget(self.update_group)
        layout.addStretch()

        self.scroll_area.setWidget(scroll_widget)
        root_layout.addWidget(self.scroll_area, 1)

        # Action Buttons (fixed outside scroll area)
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton(tr("btn_cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.cancel_btn)

        self.save_btn = QPushButton(tr("btn_save"))
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self.save_btn)

        root_layout.addLayout(btn_row)

    def _apply_group_style(self, group: QGroupBox):
        pass

    def _populate_setter_combo(self):
        cur_data = self.setter_combo.currentData() if hasattr(self, "setter_combo") else config.wallpaper_setter
        self.setter_combo.blockSignals(True)
        self.setter_combo.clear()
        self.setter_combo.addItem(f"⭐ {tr('setter_auto')}", "auto")

        for s in self._all_setters:
            status = tr("setter_available") if s.get("available") else tr("setter_not_installed")
            vid = tr("setter_video_badge") if s.get("supports_video") else ""
            label = f"{s['name']} [{status}{vid}]"
            self.setter_combo.addItem(label, s["id"])

        self.setter_combo.addItem(f"⚙ {tr('setter_custom')}", "custom")

        target = cur_data if cur_data is not None else config.wallpaper_setter
        idx = self.setter_combo.findData(target)
        if idx >= 0:
            self.setter_combo.setCurrentIndex(idx)
        else:
            self.setter_combo.setCurrentIndex(0)
        self.setter_combo.blockSignals(False)

    def _on_setter_changed(self):
        setter_id = self.setter_combo.currentData()
        if setter_id == "auto":
            detected_list = detect_wallpaper_command()
            detected_str = " ".join(detected_list) if detected_list else tr("tool_none")
            self.det_lbl.setText(tr("detected_tool", tool=detected_str))
        elif setter_id == "custom":
            self.det_lbl.setText(tr("setter_custom_desc"))
        else:
            setter_obj = next((s for s in self._all_setters if s["id"] == setter_id), None)
            if setter_obj:
                desc = setter_obj.get("description", "")
                cmd = setter_obj.get("default_cmd", "")
                status = tr("setter_status_available") if setter_obj.get("available") else tr("setter_status_not_installed")
                self.det_lbl.setText(tr("setter_status_info", status=status, desc=desc, cmd=cmd))

    def _on_test_wallpaper(self):
        # Look for any existing wallpaper image or video in user directory or cache
        candidates = [
            Path(config.default_download_dir),
            Path.home() / "Pictures" / "Wallpapers",
            Path.home() / "Pictures",
            CACHE_DIR,
        ]
        sample_file = None
        for d in candidates:
            if d.exists():
                for ext in [".jpg", ".png", ".jpeg", ".mp4", ".webp"]:
                    files = list(d.glob(f"*{ext}"))
                    if files:
                        sample_file = str(files[0])
                        break
            if sample_file:
                break

        if not sample_file:
            QMessageBox.information(
                self,
                tr("test_wall_title"),
                tr("test_wall_not_found"),
            )
            return

        setter_id = self.setter_combo.currentData()
        custom_cmd = self.custom_cmd_input.text().strip()
        custom_vid = self.custom_video_input.text().strip()

        ok, msg = set_desktop_wallpaper(sample_file, custom_cmd, setter_id, custom_vid)
        if ok:
            QMessageBox.information(
                self,
                tr("test_wall_title"),
                tr("test_wall_success", msg=msg, filename=os.path.basename(sample_file)),
            )
        else:
            QMessageBox.warning(
                self,
                tr("test_wall_title"),
                tr("test_wall_fail", msg=msg),
            )

    def _on_theme_changed(self):
        theme_id = self.theme_combo.currentData()
        if theme_id:
            config.set("theme", theme_id)
            app = QApplication.instance()
            if app:
                app.setStyleSheet(get_stylesheet(theme_id))
            parent = self.parent()
            if parent and hasattr(parent, "sidebar"):
                parent.sidebar.update_theme_display(theme_id)

    def _on_language_changed(self):
        new_lang = self.lang_combo.currentData()
        if new_lang:
            i18n.set_language(new_lang)

    def _on_bg_effects_toggled(self, checked: bool):
        config.background_effects = checked
        parent = self.parent()
        if parent and hasattr(parent, "content_canvas") and hasattr(parent.content_canvas, "set_effects_enabled"):
            parent.content_canvas.set_effects_enabled(checked)

    def reject(self):
        # Revert live preview changes if cancelled
        if config.get("theme") != self._orig_theme:
            config.set("theme", self._orig_theme)
            app = QApplication.instance()
            if app:
                app.setStyleSheet(get_stylesheet(self._orig_theme))
            parent = self.parent()
            if parent and hasattr(parent, "sidebar"):
                parent.sidebar.update_theme_display(self._orig_theme)
        if i18n.current_language != self._orig_lang:
            i18n.set_language(self._orig_lang)
        if config.background_effects != self._orig_effects:
            config.background_effects = self._orig_effects
            parent = self.parent()
            if parent and hasattr(parent, "content_canvas") and hasattr(parent.content_canvas, "set_effects_enabled"):
                parent.content_canvas.set_effects_enabled(self._orig_effects)
        super().reject()

    def retranslate_ui(self):
        self.setWindowTitle(tr("settings_title"))
        self.title_lbl.setText(tr("settings_title"))
        self.theme_group.setTitle(tr("theme_section"))
        self.theme_label.setText(tr("theme_label"))
        self.lang_label.setText(tr("lang_label"))
        if hasattr(self, "bg_effects_cb"):
            self.bg_effects_cb.setText(tr("bg_effects_label"))
        self.api_group.setTitle(tr("api_group"))
        self.api_desc.setText(tr("api_desc"))
        self.api_key_input.setPlaceholderText(tr("api_placeholder"))
        self.dir_group.setTitle(tr("dir_group"))
        self.dir_desc.setText(tr("dir_desc"))
        self.browse_btn.setText(tr("browse_button"))
        self.wall_group.setTitle(tr("wall_group"))
        self.auto_wall_cb.setText(tr("auto_wall_checkbox"))
        self.method_lbl.setText(tr("wallpaper_setter_label"))
        self.test_wall_btn.setText(tr("test_setter_btn"))
        self.test_wall_btn.setToolTip(tr("test_setter_tip"))

        self._populate_setter_combo()
        self._on_setter_changed()

        self.custom_cmd_lbl.setText(tr("custom_cmd_label"))
        self.custom_cmd_input.setPlaceholderText(tr("custom_cmd_placeholder"))
        self.custom_video_lbl.setText(tr("custom_video_cmd_label"))
        self.custom_video_input.setPlaceholderText(tr("custom_video_placeholder"))
        self.cache_group.setTitle(tr("cache_group"))
        self.cache_size_lbl.setText(self._get_cache_size_str())
        self.clear_cache_btn.setText(tr("cache_clear_button"))
        if hasattr(self, "update_group"):
            self.update_group.setTitle(tr("update_section"))
            self.cur_ver_lbl.setText(f"Komorebi Desktop v{__version__}")
            self.check_update_btn.setText(tr("update_check_btn"))
            self.auto_check_cb.setText(tr("update_auto_check"))
        self.cancel_btn.setText(tr("btn_cancel"))
        self.save_btn.setText(tr("btn_save"))

    def _on_check_updates(self):
        self.check_update_btn.setEnabled(False)
        self.update_status_lbl.setText(tr("update_checking"))
        self.update_status_lbl.setStyleSheet("color: #a5b4fc; font-size: 11.5px;")
        self.check_worker = UpdateCheckWorker(current_ver=__version__, parent=self)
        self.check_worker.check_finished.connect(self._on_check_finished)
        self.check_worker.check_failed.connect(self._on_check_failed)
        self.check_worker.start()

    def _on_check_finished(self, info: UpdateInfo):
        try:
            self.check_update_btn.setEnabled(True)
            self.latest_update_info = info
            if info.has_update:
                self.update_status_lbl.setText(tr("update_available_status", version=info.latest_version))
                self.update_status_lbl.setStyleSheet("color: #34d399; font-weight: 700; font-size: 11.5px;")
                self.apply_update_btn.setVisible(True)
                self.apply_update_btn.setText(f"⬇️ {tr('update_banner_apply')} ({info.latest_version})")
            else:
                self.update_status_lbl.setText(tr("update_latest_status", version=__version__))
                self.update_status_lbl.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11.5px;")
                self.apply_update_btn.setVisible(False)
        except RuntimeError:
            pass

    def _on_check_failed(self, error: str):
        try:
            self.check_update_btn.setEnabled(True)
            self.update_status_lbl.setText(tr("update_check_error", error=error))
            self.update_status_lbl.setStyleSheet("color: #f87171; font-size: 11.5px;")
        except RuntimeError:
            pass

    def _on_open_update_dialog(self):
        if not self.latest_update_info:
            info = UpdateInfo(current_version=__version__, latest_version=f"v{__version__}")
        else:
            info = self.latest_update_info
        dlg = UpdateDialog(info, self)
        dlg.exec()

    def _toggle_api_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def _on_browse_dir(self):
        cur = self.dir_input.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, tr("browse_dialog_title"), cur)
        if chosen:
            self.dir_input.setText(chosen)

    def _get_cache_size_str(self) -> str:
        try:
            if not CACHE_DIR.exists():
                return tr("cache_size", size="0")
            total = sum(f.stat().st_size for f in CACHE_DIR.glob("**/*") if f.is_file())
            mb = total / (1024 * 1024)
            return tr("cache_size", size=f"{mb:.1f}")
        except Exception:
            return tr("cache_size", size="?")

    def _on_clear_cache(self):
        try:
            if CACHE_DIR.exists():
                for item in CACHE_DIR.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            (CACHE_DIR / "thumbnails").mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / "previews").mkdir(parents=True, exist_ok=True)
            self.cache_size_lbl.setText(self._get_cache_size_str())
            QMessageBox.information(self, tr("cache_cleared_title"), tr("cache_cleared_msg"))
        except Exception as e:
            QMessageBox.critical(self, tr("download_failed_title"), tr("cache_clear_error", error=str(e)))

    def _on_save(self):
        config.api_key = self.api_key_input.text().strip()
        chosen_dir = self.dir_input.text().strip()
        if chosen_dir and os.path.isdir(chosen_dir):
            config.default_download_dir = chosen_dir
        config.auto_set_wallpaper = self.auto_wall_cb.isChecked()
        config.wallpaper_setter = self.setter_combo.currentData() or "auto"
        config.custom_wallpaper_cmd = self.custom_cmd_input.text().strip()
        config.custom_video_wallpaper_cmd = self.custom_video_input.text().strip()
        config.language = self.lang_combo.currentData()
        config.set("theme", self.theme_combo.currentData() or "dark")
        if hasattr(self, "bg_effects_cb"):
            config.background_effects = self.bg_effects_cb.isChecked()
        if hasattr(self, "auto_check_cb"):
            config.check_updates_on_launch = self.auto_check_cb.isChecked()
        config.save()
        self.accept()
