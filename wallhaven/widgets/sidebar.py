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
    QRadialGradient,
    QFont,
    QPen,
    QCursor,
    QPixmap,
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
from wallhaven import __version__
from wallhaven.i18n import tr
from wallhaven.config import config
from wallhaven.styles import get_available_themes, apply_theme, get_palette, get_asset_path


class SidebarNavItem(QPushButton):
    """Rich interactive navigation item with 34x34 neon icon tile, title, subtitle, and optional count badge."""

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

        self.setFixedHeight(52)
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
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # 34x34 Rounded Icon Tile
        self.icon_lbl = QLabel(self.icon_str)
        self.icon_lbl.setFixedSize(34, 34)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.icon_lbl)

        # Title & Subtitle column
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.title_lbl = QLabel(self.title_text)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(self.subtitle_text)
        self.subtitle_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self.subtitle_lbl)

        layout.addLayout(text_layout, 1)

        # Optional Badge
        self.badge_lbl = QLabel(self.badge_text)
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
        pal = get_palette(config.theme)
        text_pri = pal.get("text_primary", "#f8fafc")
        text_sec = pal.get("text_secondary", "#cbd5e1")
        text_mut = pal.get("text_muted", "#64748b")
        accent = pal.get("accent", "#6366f1")
        accent_hover = pal.get("accent_hover", "#818cf8")
        accent_text = pal.get("accent_text", "#ffffff")
        bg_cap = pal.get("bg_capsule", "#0b0d14")
        border_col = pal.get("border", "#232838")

        if self.is_active:
            self.icon_lbl.setStyleSheet("""
                font-size: 17px;
                background-color: rgba(255, 255, 255, 0.20);
                border: 1px solid rgba(255, 255, 255, 0.40);
                border-radius: 10px;
            """)
            self.title_lbl.setStyleSheet(f"""
                font-size: 12.5px;
                font-weight: 800;
                color: {accent_text};
                background: transparent;
            """)
            self.subtitle_lbl.setStyleSheet(f"""
                font-size: 10px;
                font-weight: 600;
                color: {accent_text};
                background: transparent;
            """)
            self.badge_lbl.setStyleSheet(f"""
                background-color: rgba(255, 255, 255, 0.25);
                color: {accent_text};
                border: 1px solid rgba(255, 255, 255, 0.42);
                border-radius: 9px;
                padding: 2px 7px;
                font-size: 9.5px;
                font-weight: 900;
            """)
        else:
            self.icon_lbl.setStyleSheet(f"""
                font-size: 16px;
                background-color: {bg_cap};
                border: 1px solid {border_col};
                border-radius: 10px;
            """)
            self.title_lbl.setStyleSheet(f"""
                font-size: 12.5px;
                font-weight: 700;
                color: {text_sec};
                background: transparent;
            """)
            self.subtitle_lbl.setStyleSheet(f"""
                font-size: 10px;
                font-weight: 500;
                color: {text_mut};
                background: transparent;
            """)
            self.badge_lbl.setStyleSheet(f"""
                background-color: {bg_cap};
                color: {accent_hover};
                border: 1px solid {accent};
                border-radius: 9px;
                padding: 2px 7px;
                font-size: 9.5px;
                font-weight: 800;
            """)

        self.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.015);
                border: 1px solid rgba(255, 255, 255, 0.04);
                border-radius: 12px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.07);
                border: 1px solid rgba(255, 255, 255, 0.14);
            }
        """)


class SidebarNavContainer(QWidget):
    """Container holding navigation buttons with an animated sliding indicator pill behind them."""

    item_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "wallhaven"
        self._indicator_rect = QRect(4, 6, 218, 52)
        self.buttons: dict[str, SidebarNavItem] = {}

        self._anim = QPropertyAnimation(self, b"indicatorRect")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._init_layout()

    def _init_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(6)

        # 1. Section Header: Feeds / Explore
        self.section_explore_lbl = QLabel(tr("nav_explore").upper() if tr("nav_explore") else "OBJEVOVAT")
        self.section_explore_lbl.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            font-weight: 900;
            letter-spacing: 1.6px;
            padding: 6px 8px 2px 8px;
            background: transparent;
        """)
        self.main_layout.addWidget(self.section_explore_lbl)

        # Explore feeds
        explore_items = [
            ("wallhaven", "🌌", tr("tab_wallhaven"), tr("sidebar_wallhaven_sub") or "HD & 4K Wallpapers", ""),
            ("moewalls", "🎬", tr("tab_moewalls"), tr("sidebar_moewalls_sub") or "Live Video Wallpapers", "LIVE"),
            ("osu!", "🎯", tr("tab_osu"), tr("sidebar_osu_sub") or "Contest Artworks", ""),
            ("pfps", "🎭", tr("tab_pfps"), tr("sidebar_pfps_sub") or "pfps.gg & GIFs", "NEW"),
        ]

        for mode_key, icon, title, subtitle, badge in explore_items:
            actual_mode = "osu" if mode_key == "osu!" else mode_key
            item = SidebarNavItem(actual_mode, icon, title, subtitle, badge, self)
            item.clicked.connect(lambda checked, m=actual_mode: self.select_mode(m, user_click=True))
            self.main_layout.addWidget(item)
            self.buttons[actual_mode] = item

        self.main_layout.addSpacing(8)

        # 2. Section Header: Library
        self.section_lib_lbl = QLabel(tr("nav_library").upper() if tr("nav_library") else "LIBRARY")
        self.section_lib_lbl.setStyleSheet("""
            color: #94a3b8;
            font-size: 10px;
            font-weight: 900;
            letter-spacing: 1.6px;
            padding: 6px 8px 2px 8px;
            background: transparent;
        """)
        self.main_layout.addWidget(self.section_lib_lbl)

        # Installed / Local
        item_inst = SidebarNavItem("installed", "💾", tr("tab_installed"), tr("sidebar_installed_sub") or "Installed Wallpapers", "", self)
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
            pal = get_palette(config.theme)
            c_start = QColor(pal.get("accent_gradient_start", pal.get("accent", "#4f46e5")))
            c_end = QColor(pal.get("accent_gradient_end", pal.get("accent_hover", "#7c3aed")))
            c_glow = QColor(pal.get("accent_hover", pal.get("accent", "#818cf8")))

            # Outer neon halo layers
            for expand, alpha in ((5.0, 32), (2.5, 68)):
                halo_path = QPainterPath()
                halo_path.addRoundedRect(
                    float(ir.x()) - expand,
                    float(ir.y()) - expand,
                    float(ir.width()) + expand * 2,
                    float(ir.height()) + expand * 2,
                    13.0,
                    13.0,
                )
                glow_col = QColor(c_glow)
                glow_col.setAlpha(alpha)
                painter.fillPath(halo_path, glow_col)

            pill_path = QPainterPath()
            pill_path.addRoundedRect(
                float(ir.x()),
                float(ir.y()),
                float(ir.width()),
                float(ir.height()),
                12.0,
                12.0,
            )

            c_start.setAlpha(248)
            c_end.setAlpha(248)

            grad = QLinearGradient(float(ir.x()), float(ir.y()), float(ir.x() + ir.width()), float(ir.y() + ir.height()))
            grad.setColorAt(0.0, c_start)
            grad.setColorAt(1.0, c_end)
            painter.fillPath(pill_path, grad)

            # Vivid neon edge highlight
            sheen_color = QColor(c_glow).lighter(130)
            sheen_color.setAlpha(210)
            pen = QPen(sheen_color)
            pen.setWidthF(1.6)
            painter.strokePath(pill_path, pen)

        painter.end()


class KomorebiSidebar(QFrame):
    """The ultra-modern Gaming/Neon Command Center left sidebar for Komorebi Desktop."""

    mode_changed = pyqtSignal(str)
    theme_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    auto_wall_toggled = pyqtSignal(bool)
    update_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("komorebiSidebar")
        self.setFixedWidth(258)

        self._init_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        pal = get_palette(config.theme)

        bg_surf = QColor(pal.get("bg_surface", "#12151f"))
        bg_cap = QColor(pal.get("bg_capsule", "#0b0d14"))
        accent = QColor(pal.get("accent", "#6366f1"))
        accent_hover = QColor(pal.get("accent_hover", "#818cf8"))

        # 1. Deep vertical cyber-glass gradient
        bg_grad = QLinearGradient(0.0, 0.0, 0.0, h)
        bg_grad.setColorAt(0.0, bg_surf.lighter(108))
        bg_grad.setColorAt(0.5, bg_surf)
        bg_grad.setColorAt(1.0, bg_cap)
        painter.fillRect(self.rect(), bg_grad)

        # 2. Top-left radial neon aura behind Hero Brand Card
        rad = QRadialGradient(w * 0.35, 42.0, 160.0)
        aura_col = QColor(accent)
        aura_col.setAlpha(46)
        rad.setColorAt(0.0, aura_col)
        aura_mid = QColor(accent_hover)
        aura_mid.setAlpha(18)
        rad.setColorAt(0.55, aura_mid)
        rad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), rad)

        # 3. Glowing vertical neon accent edge line along the right border
        edge_grad = QLinearGradient(0.0, 0.0, 0.0, h)
        c_top = QColor(accent_hover)
        c_top.setAlpha(180)
        c_mid = QColor(accent)
        c_mid.setAlpha(110)
        c_bot = QColor(accent)
        c_bot.setAlpha(40)
        edge_grad.setColorAt(0.0, c_top)
        edge_grad.setColorAt(0.5, c_mid)
        edge_grad.setColorAt(1.0, c_bot)
        pen = QPen(edge_grad, 1.8)
        painter.setPen(pen)
        painter.drawLine(int(w) - 1, 0, int(w) - 1, int(h))

        painter.end()

    def _init_ui(self):
        sidebar_layout = QVBoxLayout(self)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(10)

        # 1. Hero Brand Card at Top
        self.brand_card = QFrame()
        self.brand_card.setObjectName("sidebarBrandCard")
        brand_layout = QHBoxLayout(self.brand_card)
        brand_layout.setContentsMargins(10, 10, 10, 10)
        brand_layout.setSpacing(10)

        # Glowing emblem icon using official app emblem asset
        emblem_lbl = QLabel()
        emblem_lbl.setFixedSize(40, 40)
        emblem_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emblem_path = get_asset_path("icon_emblem.png")
        if not emblem_path.exists():
            emblem_path = get_asset_path("icon.png")
        if emblem_path.exists():
            pm = QPixmap(str(emblem_path)).scaled(
                30,
                30,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            emblem_lbl.setPixmap(pm)
        else:
            emblem_lbl.setText("🌿")

        emblem_lbl.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(99, 102, 241, 0.28), stop:1 rgba(236, 72, 153, 0.25));
            border: 1.5px solid rgba(129, 140, 248, 0.55);
            border-radius: 11px;
            padding: 3px;
        """)
        brand_layout.addWidget(emblem_lbl)

        # Brand title & version badge
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        brand_title = QLabel("KOMOREBI")
        brand_title.setStyleSheet("""
            font-size: 14.5px;
            font-weight: 900;
            color: #ffffff;
            letter-spacing: 2.2px;
            background: transparent;
        """)
        title_box.addWidget(brand_title)

        subtitle_row = QHBoxLayout()
        subtitle_row.setSpacing(5)
        brand_sub = QLabel("NEON HUB")
        brand_sub.setStyleSheet("font-size: 9.5px; color: #94a3b8; font-weight: 800; letter-spacing: 0.8px; background: transparent;")
        subtitle_row.addWidget(brand_sub)

        self.ver_badge = QLabel(f"v{__version__}")
        self.ver_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ver_badge.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.28);
            border-radius: 5px;
            padding: 1px 6px;
            font-size: 9px;
            font-weight: 900;
        """)
        self.ver_badge.setToolTip(tr("update_badge_tip"))
        self.ver_badge.mousePressEvent = lambda e: self.update_clicked.emit()
        subtitle_row.addWidget(self.ver_badge)
        subtitle_row.addStretch()
        title_box.addLayout(subtitle_row)

        brand_layout.addLayout(title_box, 1)
        sidebar_layout.addWidget(self.brand_card)

        # 2. Central Navigation Container with Sliding Pill
        self.nav_container = SidebarNavContainer(self)
        self.nav_container.item_selected.connect(self._on_item_selected)
        sidebar_layout.addWidget(self.nav_container, 1)

        # 3. Bottom Utility Deck (Frosted Glass Dock)
        self.utility_deck = QFrame()
        self.utility_deck.setObjectName("sidebarUtilityDeck")
        bottom_box = QVBoxLayout(self.utility_deck)
        bottom_box.setSpacing(5)
        bottom_box.setContentsMargins(8, 8, 8, 8)

        # Quick Theme Button
        self.theme_btn = QPushButton(f"🎨  {tr('theme_menu_title')}")
        self.theme_btn.setObjectName("sidebarUtilityBtn")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setFixedHeight(34)
        self.theme_btn.clicked.connect(self.theme_clicked.emit)
        bottom_box.addWidget(self.theme_btn)

        # Auto-wallpaper toggle
        self.auto_wall_btn = QPushButton(f"🖼️  {tr('auto_wallpaper')}")
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
        self.settings_btn = QPushButton(f"⚙️  {tr('settings_title')}")
        self.settings_btn.setObjectName("sidebarUtilityBtn")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setFixedHeight(34)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        bottom_box.addWidget(self.settings_btn)

        sidebar_layout.addWidget(self.utility_deck)

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

    def show_update_available(self, new_version: str):
        self._new_version = new_version
        if hasattr(self, "ver_badge"):
            self.ver_badge.setText(f"✨ {new_version}")
            self.ver_badge.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #06b6d4);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 5px;
                padding: 1px 6px;
                font-size: 9px;
                font-weight: 900;
            """)
            self.ver_badge.setToolTip(tr("update_badge_available_tip", version=new_version))

    def set_auto_wall_checked(self, checked: bool):
        self.auto_wall_btn.setChecked(checked)
        self._update_auto_wall_btn_style()

    def _update_auto_wall_btn_style(self):
        if self.auto_wall_btn.isChecked():
            self.auto_wall_btn.setText(f"🖼️  {tr('auto_wall_on')}")
            self.auto_wall_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(5, 150, 105, 0.28), stop:1 rgba(16, 185, 129, 0.16));
                    color: #34d399;
                    border: 1px solid rgba(52, 211, 153, 0.5);
                    border-radius: 9px;
                    text-align: left;
                    padding-left: 10px;
                    font-size: 11.5px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background-color: rgba(16, 185, 129, 0.32);
                    border-color: #34d399;
                }
            """)
        else:
            self.auto_wall_btn.setText(f"🖼️  {tr('auto_wall_off')}")
            self.auto_wall_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    border: 1px solid transparent;
                    border-radius: 9px;
                    text-align: left;
                    padding-left: 10px;
                    font-size: 11.5px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    color: #f1f5f9;
                }
            """)

    def update_theme_display(self, theme_id: str = ""):
        if not theme_id:
            theme_id = config.theme
        theme_names = {
            "matugen": "Matugen",
            "dark": "Wallhaven",
            "catppuccin": "Catppuccin",
            "tokyo_night": "Tokyo Night",
            "nord": "Nord",
            "dracula": "Dracula",
            "gruvbox": "Gruvbox",
            "rose_pine": "Rosé Pine",
            "everforest": "Everforest",
            "kanagawa": "Kanagawa",
            "synthwave": "Synthwave",
            "cyberpunk": "Cyberpunk",
            "oled": "OLED",
            "pywal": "Pywal",
        }
        short_name = theme_names.get(theme_id, theme_id.capitalize())
        theme_label = tr("theme_menu_title") or "Theme"
        self.theme_btn.setText(f"🎨  {theme_label}: {short_name}")
        for btn in self.nav_container.buttons.values():
            btn._update_style()
        self._update_auto_wall_btn_style()
        self.nav_container.update()
        self.update()

    def retranslate_ui(self):
        if hasattr(self, "nav_container"):
            if hasattr(self.nav_container, "section_explore_lbl"):
                exp_text = tr("nav_explore") or "Explore"
                self.nav_container.section_explore_lbl.setText(exp_text.upper())
            if hasattr(self.nav_container, "section_lib_lbl"):
                lib_text = tr("nav_library") or "Library"
                self.nav_container.section_lib_lbl.setText(lib_text.upper())

            if "wallhaven" in self.nav_container.buttons:
                self.nav_container.buttons["wallhaven"].update_texts(
                    tr("tab_wallhaven"),
                    tr("sidebar_wallhaven_sub") or "HD & 4K Wallpapers",
                )
            if "moewalls" in self.nav_container.buttons:
                self.nav_container.buttons["moewalls"].update_texts(
                    tr("tab_moewalls"),
                    tr("sidebar_moewalls_sub") or "Live Video Wallpapers",
                )
            if "osu" in self.nav_container.buttons:
                self.nav_container.buttons["osu"].update_texts(
                    tr("tab_osu"),
                    tr("sidebar_osu_sub") or "Contest Artworks",
                )
            if "pfps" in self.nav_container.buttons:
                self.nav_container.buttons["pfps"].update_texts(
                    tr("tab_pfps"),
                    tr("sidebar_pfps_sub") or "pfps.gg & GIFs",
                )
            if "installed" in self.nav_container.buttons:
                self.nav_container.buttons["installed"].update_texts(
                    tr("tab_installed"),
                    tr("sidebar_installed_sub") or "Installed Wallpapers",
                )

        if hasattr(self, "theme_btn"):
            self.update_theme_display()
        if hasattr(self, "auto_wall_btn"):
            self._update_auto_wall_btn_style()
        if hasattr(self, "settings_btn"):
            self.settings_btn.setText(f"⚙️  {tr('settings_title') or 'Settings'}")
        if hasattr(self, "ver_badge"):
            if getattr(self, "_new_version", None):
                self.ver_badge.setToolTip(tr("update_badge_available_tip", version=self._new_version))
            else:
                self.ver_badge.setToolTip(tr("update_badge_tip"))
