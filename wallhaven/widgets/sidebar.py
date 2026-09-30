"""Modern vertical navigation sidebar for Komorebi Desktop.

Features:
- Sleek brand header with glowing Komorebi emblem
- Grouped navigation sections ('Objevovat' and 'Knihovna')
- Animated vertical sliding indicator pill with gradient glow
- Rich navigation items with icon, title, subtitle, and dynamic badge
- Bottom utility bar: Quick theme switcher, Auto-wallpaper toggle, Settings modal
"""
from PyQt6.QtCore import (
    Qt,
    QRect,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    pyqtSignal,
    QSize,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPainterPath,
    QLinearGradient,
    QFont,
    QPen,
    QCursor,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
    QMenu,
)
from wallhaven.i18n import tr
from wallhaven.config import config
from wallhaven.styles import get_available_themes, apply_theme


class SidebarNavItem(QPushButton):
    """Rich interactive navigation item with icon, title, subtitle, and optional count badge."""

    def __init__(
        self,
        mode: str,
        icon_str: str,
        title: str,
        subtitle: str = "",
        badge_text: str = "",
        parent=None,
    ):
        super().__init__("", parent)
        self.mode = mode
        self.icon_str = icon_str
        self.title_text = title
        self.subtitle_text = subtitle
        self.badge_text = badge_text
        self.is_active = False

        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._init_ui()

    def setText(self, text: str):
        self.title_text = text
        if hasattr(self, "title_lbl"):
            self.title_lbl.setText(text)
        super().setText("")

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Icon
        self.icon_lbl = QLabel(self.icon_str)
        self.icon_lbl.setStyleSheet("font-size: 18px; background: transparent;")
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.icon_lbl)

        # Title & Subtitle column
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.title_lbl = QLabel(self.title_text)
        self.title_lbl.setStyleSheet("""
            font-size: 12.5px;
            font-weight: 700;
            color: #cbd5e1;
            background: transparent;
        """)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(self.subtitle_text)
        self.subtitle_lbl.setStyleSheet("""
            font-size: 10px;
            font-weight: 500;
            color: #64748b;
            background: transparent;
        """)
        self.subtitle_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self.subtitle_lbl)

        layout.addLayout(text_layout, 1)

        # Optional Badge
        self.badge_lbl = QLabel(self.badge_text)
        self.badge_lbl.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.08);
            color: #94a3b8;
            border-radius: 9px;
            padding: 2px 7px;
            font-size: 10px;
            font-weight: 700;
        """)
        self.badge_lbl.setVisible(bool(self.badge_text))
        self.badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.badge_lbl)

        self._update_style()

    def set_active(self, active: bool):
        self.is_active = active
        self._update_style()

    def set_badge(self, text: str):
        self.badge_text = text
        self.badge_lbl.setText(text)
        self.badge_lbl.setVisible(bool(text))

    def update_texts(self, title: str, subtitle: str):
        self.title_text = title
        self.subtitle_text = subtitle
        self.title_lbl.setText(title)
        self.subtitle_lbl.setText(subtitle)

    def _update_style(self):
        if self.is_active:
            self.title_lbl.setStyleSheet("""
                font-size: 12.5px;
                font-weight: 800;
                color: #ffffff;
                background: transparent;
            """)
            self.subtitle_lbl.setStyleSheet("""
                font-size: 10px;
                font-weight: 600;
                color: #e0e7ff;
                background: transparent;
            """)
            self.badge_lbl.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.22);
                color: #ffffff;
                border-radius: 9px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 800;
            """)
        else:
            self.title_lbl.setStyleSheet("""
                font-size: 12.5px;
                font-weight: 700;
                color: #cbd5e1;
                background: transparent;
            """)
            self.subtitle_lbl.setStyleSheet("""
                font-size: 10px;
                font-weight: 500;
                color: #64748b;
                background: transparent;
            """)
            self.badge_lbl.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.08);
                color: #94a3b8;
                border-radius: 9px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 700;
            """)

        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 10px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.04);
            }
        """)


class SidebarNavContainer(QWidget):
    """Container holding navigation buttons with an animated sliding indicator pill behind them."""

    item_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "wallhaven"
        self._indicator_rect = QRect(6, 6, 208, 48)
        self.buttons: dict[str, SidebarNavItem] = {}

        self._anim = QPropertyAnimation(self, b"indicatorRect")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._init_layout()

    def _init_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 4, 6, 4)
        self.main_layout.setSpacing(4)

        # 1. Section Header: Feeds / Explore
        self.section_explore_lbl = QLabel(tr("nav_explore").upper() if tr("nav_explore") else "OBJEVOVAT")
        self.section_explore_lbl.setStyleSheet("""
            color: #475569;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.2px;
            padding: 8px 10px 4px 10px;
        """)
        self.main_layout.addWidget(self.section_explore_lbl)

        # Explore feeds
        explore_items = [
            ("wallhaven", "🌌", "Wallhaven", "HD & 4K tapety", ""),
            ("moewalls", "🎬", "MoeWalls", "Živé video tapety", "LIVE"),
            ("osu!", "🎯", "osu! Art", "Soutěžní ilustrace", ""),
            ("pfps", "🎭", "Profilovky", "pfps.gg & GIFy", "NEW"),
        ]

        for mode_key, icon, title, subtitle, badge in explore_items:
            # Map "osu!" to mode "osu"
            actual_mode = "osu" if mode_key == "osu!" else mode_key
            item = SidebarNavItem(actual_mode, icon, title, subtitle, badge, self)
            item.clicked.connect(lambda checked, m=actual_mode: self.select_mode(m, user_click=True))
            self.main_layout.addWidget(item)
            self.buttons[actual_mode] = item

        self.main_layout.addSpacing(10)

        # 2. Section Header: Library
        self.section_lib_lbl = QLabel(tr("nav_library").upper() if tr("nav_library") else "KNIHOVNA")
        self.section_lib_lbl.setStyleSheet("""
            color: #475569;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.2px;
            padding: 8px 10px 4px 10px;
        """)
        self.main_layout.addWidget(self.section_lib_lbl)

        # Installed / Local
        item_inst = SidebarNavItem("installed", "💾", "Stažené", "Nainstalované tapety", "", self)
        item_inst.clicked.connect(lambda checked: self.select_mode("installed", user_click=True))
        self.main_layout.addWidget(item_inst)
        self.buttons["installed"] = item_inst

        self.main_layout.addStretch()

    @pyqtProperty(QRect)
    def indicatorRect(self) -> QRect:
        return self._indicator_rect

    @indicatorRect.setter
    def indicatorRect(self, r: QRect):
        self._indicator_rect = r
        self.update()

    def select_mode(self, mode: str, user_click: bool = False):
        if mode not in self.buttons:
            return

        prev_mode = self._current_mode
        self._current_mode = mode

        for m, btn in self.buttons.items():
            btn.set_active(m == mode)

        target_btn = self.buttons[mode]
        target_r = target_btn.geometry()

        if target_r.isValid() and target_r.width() > 0 and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._indicator_rect)
            self._anim.setEndValue(target_r)
            self._anim.start()
        else:
            self._indicator_rect = target_r
            self.update()

        if user_click and prev_mode != mode:
            self.item_selected.emit(mode)

    def snap_indicator(self):
        if self._current_mode in self.buttons:
            btn = self.buttons[self._current_mode]
            r = btn.geometry()
            if r.isValid() and r.width() > 0:
                self._indicator_rect = r
                self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.snap_indicator()

    def showEvent(self, event):
        super().showEvent(event)
        self.snap_indicator()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw glowing animated pill behind the active item
        if self._indicator_rect.isValid() and self._indicator_rect.width() > 0:
            ir = self._indicator_rect
            pill_path = QPainterPath()
            pill_path.addRoundedRect(
                float(ir.x()),
                float(ir.y()),
                float(ir.width()),
                float(ir.height()),
                10.0,
                10.0,
            )

            # Elegant linear gradient with vibrant indigo / purple
            grad = QLinearGradient(float(ir.x()), float(ir.y()), float(ir.x() + ir.width()), float(ir.y() + ir.height()))
            grad.setColorAt(0.0, QColor(79, 70, 229, 235))   # #4f46e5
            grad.setColorAt(1.0, QColor(124, 58, 237, 235))  # #7c3aed
            painter.fillPath(pill_path, grad)

            # Subtle accent border sheen
            pen = QPen(QColor(165, 180, 252, 120))
            pen.setWidthF(1.2)
            painter.strokePath(pill_path, pen)

        painter.end()


class KomorebiSidebar(QFrame):
    """The ultra-modern left navigation sidebar for Komorebi Desktop."""

    mode_changed = pyqtSignal(str)
    theme_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    auto_wall_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("komorebiSidebar")
        self.setFixedWidth(248)

        self._init_ui()

    def _init_ui(self):
        sidebar_layout = QVBoxLayout(self)
        sidebar_layout.setContentsMargins(10, 14, 10, 14)
        sidebar_layout.setSpacing(10)

        # 1. Top Brand Logo & App Emblem
        brand_container = QWidget()
        brand_layout = QHBoxLayout(brand_container)
        brand_layout.setContentsMargins(8, 6, 8, 10)
        brand_layout.setSpacing(10)

        # Glowing emblem icon
        emblem_lbl = QLabel("🌿")
        emblem_lbl.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(99, 102, 241, 0.3), stop:1 rgba(168, 85, 247, 0.3));
            border: 1px solid rgba(168, 85, 247, 0.4);
            border-radius: 10px;
            padding: 5px;
            font-size: 18px;
        """)
        brand_layout.addWidget(emblem_lbl)

        # Brand title & version badge
        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        brand_title = QLabel("KOMOREBI")
        brand_title.setStyleSheet("""
            font-size: 14px;
            font-weight: 900;
            color: #f8fafc;
            letter-spacing: 2px;
        """)
        title_box.addWidget(brand_title)

        subtitle_row = QHBoxLayout()
        subtitle_row.setSpacing(4)
        brand_sub = QLabel("Wallpapers & PFPs")
        brand_sub.setStyleSheet("font-size: 9.5px; color: #64748b; font-weight: 600;")
        subtitle_row.addWidget(brand_sub)

        ver_badge = QLabel("v2.0")
        ver_badge.setStyleSheet("""
            background: rgba(99, 102, 241, 0.2);
            color: #a5b4fc;
            border-radius: 4px;
            padding: 1px 4px;
            font-size: 8.5px;
            font-weight: 800;
        """)
        subtitle_row.addWidget(ver_badge)
        subtitle_row.addStretch()
        title_box.addLayout(subtitle_row)

        brand_layout.addLayout(title_box, 1)
        sidebar_layout.addWidget(brand_container)

        # Divider line
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); max-height: 1px;")
        sidebar_layout.addWidget(div)

        # 2. Central Navigation Container with Sliding Pill
        self.nav_container = SidebarNavContainer(self)
        self.nav_container.item_selected.connect(self._on_item_selected)
        sidebar_layout.addWidget(self.nav_container, 1)

        # Divider line
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); max-height: 1px;")
        sidebar_layout.addWidget(div2)

        # 3. Bottom Utility Section
        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(4)
        bottom_box.setContentsMargins(4, 2, 4, 2)

        # Quick Theme Button
        self.theme_btn = QPushButton("🎨  Téma")
        self.theme_btn.setObjectName("sidebarUtilityBtn")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setFixedHeight(34)
        self.theme_btn.clicked.connect(self.theme_clicked.emit)
        bottom_box.addWidget(self.theme_btn)

        # Auto-wallpaper toggle
        self.auto_wall_btn = QPushButton("🖼️  Auto-tapeta")
        self.auto_wall_btn.setObjectName("sidebarUtilityBtn")
        self.auto_wall_btn.setCheckable(True)
        self.auto_wall_btn.setChecked(config.auto_set_wallpaper)
        self.auto_wall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_wall_btn.setFixedHeight(34)
        self.auto_wall_btn.clicked.connect(lambda: self.auto_wall_toggled.emit(self.auto_wall_btn.isChecked()))
        self._update_auto_wall_btn_style()
        self.auto_wall_btn.toggled.connect(self._update_auto_wall_btn_style)
        bottom_box.addWidget(self.auto_wall_btn)

        # Settings Button
        self.settings_btn = QPushButton("⚙️  Nastavení")
        self.settings_btn.setObjectName("sidebarUtilityBtn")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setFixedHeight(34)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        bottom_box.addWidget(self.settings_btn)

        sidebar_layout.addLayout(bottom_box)

        # Retranslate labels
        self.retranslate_ui()

    def _on_item_selected(self, mode: str):
        self.mode_changed.emit(mode)

    def set_mode(self, mode: str, user_click: bool = False):
        self.nav_container.select_mode(mode, user_click=user_click)

    def current_mode(self) -> str:
        return self.nav_container._current_mode

    def set_installed_count(self, count: int):
        if "installed" in self.nav_container.buttons:
            badge = str(count) if count > 0 else ""
            self.nav_container.buttons["installed"].set_badge(badge)

    def set_auto_wall_checked(self, checked: bool):
        self.auto_wall_btn.setChecked(checked)
        self._update_auto_wall_btn_style()

    def _update_auto_wall_btn_style(self):
        if self.auto_wall_btn.isChecked():
            self.auto_wall_btn.setText("🖼️  Auto-tapeta: ZAP")
            self.auto_wall_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(16, 185, 129, 0.15);
                    color: #34d399;
                    border: 1px solid rgba(16, 185, 129, 0.35);
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 10px;
                    font-size: 11.5px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: rgba(16, 185, 129, 0.25);
                }
            """)
        else:
            self.auto_wall_btn.setText("🖼️  Auto-tapeta: VYP")
            self.auto_wall_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 10px;
                    font-size: 11.5px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.04);
                    color: #f1f5f9;
                }
            """)

    def retranslate_ui(self):
        if hasattr(self, "nav_container"):
            if "wallhaven" in self.nav_container.buttons:
                self.nav_container.buttons["wallhaven"].update_texts(
                    tr("tab_wallhaven"),
                    tr("sidebar_wallhaven_sub") or "HD & 4K tapety",
                )
            if "moewalls" in self.nav_container.buttons:
                self.nav_container.buttons["moewalls"].update_texts(
                    tr("tab_moewalls"),
                    tr("sidebar_moewalls_sub") or "Živé video tapety",
                )
            if "osu" in self.nav_container.buttons:
                self.nav_container.buttons["osu"].update_texts(
                    tr("tab_osu"),
                    tr("sidebar_osu_sub") or "Soutěžní ilustrace",
                )
            if "pfps" in self.nav_container.buttons:
                self.nav_container.buttons["pfps"].update_texts(
                    tr("tab_pfps"),
                    tr("sidebar_pfps_sub") or "pfps.gg & GIFy",
                )
            if "installed" in self.nav_container.buttons:
                self.nav_container.buttons["installed"].update_texts(
                    tr("tab_installed"),
                    tr("sidebar_installed_sub") or "Nainstalované tapety",
                )

        if hasattr(self, "theme_btn"):
            self.theme_btn.setText(f"🎨  {tr('theme_menu_title') or 'Téma'}")
        if hasattr(self, "settings_btn"):
            self.settings_btn.setText(f"⚙️  {tr('settings_title') or 'Nastavení'}")
