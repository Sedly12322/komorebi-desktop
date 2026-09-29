import os
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from wallhaven.main_window import MainWindow
from wallhaven.styles import get_stylesheet, get_theme_watcher, is_matugen_available
from wallhaven.config import config


def get_asset_path(filename: str) -> Path:
    # 1. Check PyInstaller bundle directory
    if hasattr(sys, "_MEIPASS"):
        bundle_asset = Path(sys._MEIPASS) / "assets" / filename
        if bundle_asset.exists():
            return bundle_asset
        bundle_direct = Path(sys._MEIPASS) / filename
        if bundle_direct.exists():
            return bundle_direct

    # 2. Check alongside executable
    exe_dir = Path(sys.executable).parent / "assets" / filename
    if exe_dir.exists():
        return exe_dir

    # 3. Check package directory
    pkg_asset = Path(__file__).parent.parent / "assets" / filename
    if pkg_asset.exists():
        return pkg_asset

    # 4. Check Linux system icon paths
    sys_asset = Path(f"/usr/share/icons/hicolor/256x256/apps/{filename}")
    if sys_asset.exists():
        return sys_asset
    local_asset = Path.home() / f".local/share/icons/hicolor/256x256/apps/{filename}"
    if local_asset.exists():
        return local_asset

    return pkg_asset


def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Windows taskbar grouping & Qt plugin setup
    if sys.platform == "win32":
        # Remove any lingering or inherited Linux QPA platform settings on Windows
        if os.environ.get("QT_QPA_PLATFORM") in ("wayland", "xcb", "wayland;xcb"):
            os.environ.pop("QT_QPA_PLATFORM", None)

        # PyInstaller bundled plugins location helper
        if getattr(sys, "frozen", False):
            base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            for qt_path in [
                base_dir / "PyQt6" / "Qt6" / "plugins",
                base_dir / "PyQt6" / "plugins",
                base_dir / "plugins",
            ]:
                if qt_path.exists():
                    os.environ["QT_PLUGIN_PATH"] = str(qt_path)
                    platforms_path = qt_path / "platforms"
                    if platforms_path.exists():
                        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_path)
                    break

        try:
            import ctypes
            myappid = "sedly.komorebi.desktop.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
    else:
        # Linux Wayland / High DPI friendliness
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")

    app = QApplication(sys.argv)
    app.setApplicationName("Komorebi Desktop")
    app.setApplicationDisplayName("Komorebi Desktop")
    app.setDesktopFileName("komorebi-desktop")

    # Set icon if available (prefer ICO on Windows, PNG on Linux)
    icon_name = "icon.ico" if sys.platform == "win32" else "icon.png"
    icon_path = get_asset_path(icon_name)
    if not icon_path.exists():
        icon_path = get_asset_path("icon.png")

    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Apply global stylesheet according to saved theme
    theme_id = config.get("theme", "matugen" if sys.platform != "win32" and is_matugen_available() else "dark")
    app.setStyleSheet(get_stylesheet(theme_id))

    # Initialize dynamic theme watcher for real-time Matugen color updates
    theme_watcher = get_theme_watcher()

    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
