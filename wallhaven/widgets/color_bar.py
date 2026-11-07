from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from wallhaven.i18n import tr, i18n

WALLHAVEN_COLOR_CODES = [
    "660000", "cc0000", "ea4c88", "993399", "333399", "0066cc", "0099ff",
    "66cccc", "77cc33", "336600", "ffff00", "ff9900", "ff6600", "663300",
    "000000", "424153", "999999", "ffffff"
]


class ColorButton(QPushButton):
    def __init__(self, hex_color: str, parent=None):
        super().__init__(parent)
        self.hex_color = hex_color
        self.setToolTip(tr(f"color_{hex_color}"))
        self.setFixedSize(24, 24)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style(False)

    def update_style(self, checked: bool):
        border = "2.5px solid #ffffff" if checked else "1.5px solid #282e42"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #{self.hex_color};
                border: {border};
                border-radius: 2px;
            }}
            QPushButton:hover {{
                border: 2px solid #818cf8;
            }}
        """)


class ColorBar(QFrame):
    color_changed = pyqtSignal(str)  # Emits hex code without '#' or "" if reset

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("colorBarFrame")
        self.selected_color = ""
        self.buttons: list[ColorButton] = []
        self._init_ui()
        i18n.language_changed.connect(self.retranslate_ui)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(7)

        self.title = QLabel(tr("color_label"))
        self.title.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 11px; margin-right: 4px;")
        layout.addWidget(self.title)

        for hex_code in WALLHAVEN_COLOR_CODES:
            btn = ColorButton(hex_code)
            btn.clicked.connect(lambda checked, c=hex_code, b=btn: self._on_color_clicked(c, b))
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addSpacing(6)

        self.clear_btn = QPushButton(tr("color_clear"))
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #1a1e2b;
                color: #94a3b8;
                border: 1px solid #282e42;
                border-radius: 2px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #242a3c;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_selection)
        layout.addWidget(self.clear_btn)

        layout.addStretch()

    def retranslate_ui(self):
        self.title.setText(tr("color_label"))
        self.clear_btn.setText(tr("color_clear"))
        for btn in self.buttons:
            btn.setToolTip(tr(f"color_{btn.hex_color}"))

    def _on_color_clicked(self, hex_code: str, clicked_btn: ColorButton):
        if self.selected_color == hex_code:
            self.selected_color = ""
            clicked_btn.setChecked(False)
            clicked_btn.update_style(False)
        else:
            self.selected_color = hex_code
            for btn in self.buttons:
                is_this = (btn == clicked_btn)
                btn.setChecked(is_this)
                btn.update_style(is_this)

        self.color_changed.emit(self.selected_color)

    def clear_selection(self):
        self.selected_color = ""
        for btn in self.buttons:
            btn.setChecked(False)
            btn.update_style(False)
        self.color_changed.emit("")

    def set_color(self, hex_code: str):
        self.selected_color = hex_code.lower()
        for btn in self.buttons:
            is_this = (btn.hex_color.lower() == self.selected_color)
            btn.setChecked(is_this)
            btn.update_style(is_this)
