"""Ultra-Modern Multi-Theme Engine for Wallhaven Desktop.

Supports curated Linux & cross-platform themes:
- Wallhaven Dark (Default Obsidian & Indigo)
- Catppuccin Mocha (Community favorite Lavender & Deep Base)
- Tokyo Night (Cyberpunk Blue & Deep Violet)
- Nord Frost (Arctic Frost & Polar Night)
- Dracula (Gothic Vampire Purple & Slate)
- Gruvbox Dark (Warm Retro Gold & Charcoal)
- Cyberpunk 2077 (Electric Neon Cyan & Hot Pink)
- OLED Pure Black (Pure #000000 & Electric Sapphire)
- Linux System / Pywal Palette (Dynamic desktop adaptation)
"""
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from PyQt6.QtCore import QObject, QFileSystemWatcher, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_CHEVRON_NORMAL = str(_ASSETS_DIR / "chevron_down.png").replace("\\", "/")
_CHEVRON_HOVER = str(_ASSETS_DIR / "chevron_down_hover.png").replace("\\", "/")


def get_asset_path(filename: str) -> Path:
    """Finds an asset across bundled environments, local paths, and system icon directories."""
    # 1. PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        b1 = Path(sys._MEIPASS) / "assets" / filename
        if b1.exists():
            return b1
        b2 = Path(sys._MEIPASS) / filename
        if b2.exists():
            return b2

    # 2. Alongside executable
    exe_dir = Path(sys.executable).parent / "assets" / filename
    if exe_dir.exists():
        return exe_dir

    # 3. Source assets directory
    pkg_asset = _ASSETS_DIR / filename
    if pkg_asset.exists():
        return pkg_asset

    # 4. Linux system icon paths
    sys_asset = Path(f"/usr/share/icons/hicolor/256x256/apps/{filename}")
    if sys_asset.exists():
        return sys_asset
    local_asset = Path.home() / f".local/share/icons/hicolor/256x256/apps/{filename}"
    if local_asset.exists():
        return local_asset

    return pkg_asset


# Curated theme palettes
THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "dark": {
        "name": "🌌 Wallhaven Dark",
        "bg_base": "#0d1017",
        "bg_surface": "#12151f",
        "bg_subsurface": "#0f121a",
        "bg_capsule": "#0b0d14",
        "bg_input": "#151824",
        "bg_input_hover": "#1e2434",
        "bg_card_hover": "#161a27",
        "border": "#232838",
        "border_subtle": "#1c2230",
        "border_hover": "#3b4461",
        "accent": "#6366f1",
        "accent_hover": "#818cf8",
        "accent_gradient_start": "#4f46e5",
        "accent_gradient_end": "#6366f1",
        "accent_surface": "#262463",
        "accent_text": "#ffffff",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
    },
    "catppuccin": {
        "name": "🌸 Catppuccin Mocha",
        "bg_base": "#1e1e2e",
        "bg_surface": "#181825",
        "bg_subsurface": "#11111b",
        "bg_capsule": "#11111b",
        "bg_input": "#313244",
        "bg_input_hover": "#45475a",
        "bg_card_hover": "#252739",
        "border": "#45475a",
        "border_subtle": "#313244",
        "border_hover": "#585b70",
        "accent": "#cba6f7",
        "accent_hover": "#b4befe",
        "accent_gradient_start": "#995bf5",
        "accent_gradient_end": "#cba6f7",
        "accent_surface": "#3f3657",
        "accent_text": "#ffffff",
        "text_primary": "#cdd6f4",
        "text_secondary": "#a6adc8",
        "text_muted": "#6c7086",
    },
    "tokyo_night": {
        "name": "🌃 Tokyo Night",
        "bg_base": "#1a1b26",
        "bg_surface": "#16161e",
        "bg_subsurface": "#13141c",
        "bg_capsule": "#101016",
        "bg_input": "#24283b",
        "bg_input_hover": "#2f354f",
        "bg_card_hover": "#1f2335",
        "border": "#292e42",
        "border_subtle": "#1f2335",
        "border_hover": "#414868",
        "accent": "#7aa2f7",
        "accent_hover": "#89b4fa",
        "accent_gradient_start": "#5981f4",
        "accent_gradient_end": "#7aa2f7",
        "accent_surface": "#233154",
        "accent_text": "#ffffff",
        "text_primary": "#c0caf5",
        "text_secondary": "#9aa5ce",
        "text_muted": "#565f89",
    },
    "nord": {
        "name": "❄️ Nord Frost",
        "bg_base": "#242933",
        "bg_surface": "#2e3440",
        "bg_subsurface": "#272c36",
        "bg_capsule": "#1e222a",
        "bg_input": "#3b4252",
        "bg_input_hover": "#434c5e",
        "bg_card_hover": "#353c4a",
        "border": "#434c5e",
        "border_subtle": "#2e3440",
        "border_hover": "#4c566a",
        "accent": "#88c0d0",
        "accent_hover": "#8fbcbb",
        "accent_gradient_start": "#5e81ac",
        "accent_gradient_end": "#88c0d0",
        "accent_surface": "#2d4350",
        "accent_text": "#eceff4",
        "text_primary": "#eceff4",
        "text_secondary": "#d8dee9",
        "text_muted": "#7b88a1",
    },
    "dracula": {
        "name": "🧛 Dracula",
        "bg_base": "#21222c",
        "bg_surface": "#282a36",
        "bg_subsurface": "#1e1f29",
        "bg_capsule": "#181920",
        "bg_input": "#343746",
        "bg_input_hover": "#44475a",
        "bg_card_hover": "#2d303e",
        "border": "#44475a",
        "border_subtle": "#2e303e",
        "border_hover": "#6272a4",
        "accent": "#bd93f9",
        "accent_hover": "#ff79c6",
        "accent_gradient_start": "#9a6df7",
        "accent_gradient_end": "#bd93f9",
        "accent_surface": "#422e5a",
        "accent_text": "#ffffff",
        "text_primary": "#f8f8f2",
        "text_secondary": "#bfbfbf",
        "text_muted": "#6272a4",
    },
    "gruvbox": {
        "name": "📻 Gruvbox Dark",
        "bg_base": "#1d2021",
        "bg_surface": "#282828",
        "bg_subsurface": "#242424",
        "bg_capsule": "#191b1c",
        "bg_input": "#3c3836",
        "bg_input_hover": "#504945",
        "bg_card_hover": "#32302f",
        "border": "#504945",
        "border_subtle": "#32302f",
        "border_hover": "#665c54",
        "accent": "#fabd2f",
        "accent_hover": "#fe8019",
        "accent_gradient_start": "#d65d0e",
        "accent_gradient_end": "#fabd2f",
        "accent_surface": "#4e3d1f",
        "accent_text": "#1d2021",
        "text_primary": "#ebdbb2",
        "text_secondary": "#d5c4a1",
        "text_muted": "#928374",
    },
    "cyberpunk": {
        "name": "⚡ Cyberpunk Neon",
        "bg_base": "#0a0b12",
        "bg_surface": "#111320",
        "bg_subsurface": "#0d0f19",
        "bg_capsule": "#07080d",
        "bg_input": "#181b2e",
        "bg_input_hover": "#222640",
        "bg_card_hover": "#171a2b",
        "border": "#272c4a",
        "border_subtle": "#1a1d30",
        "border_hover": "#3e4775",
        "accent": "#00f0ff",
        "accent_hover": "#f72585",
        "accent_gradient_start": "#f72585",
        "accent_gradient_end": "#00f0ff",
        "accent_surface": "#1a3547",
        "accent_text": "#ffffff",
        "text_primary": "#e0fbfc",
        "text_secondary": "#90e0ef",
        "text_muted": "#52796f",
    },
    "oled": {
        "name": "🖤 OLED Pure Black",
        "bg_base": "#000000",
        "bg_surface": "#0a0a0a",
        "bg_subsurface": "#050505",
        "bg_capsule": "#000000",
        "bg_input": "#141414",
        "bg_input_hover": "#222222",
        "bg_card_hover": "#111111",
        "border": "#282828",
        "border_subtle": "#161616",
        "border_hover": "#444444",
        "accent": "#3b82f6",
        "accent_hover": "#60a5fa",
        "accent_gradient_start": "#1d4ed8",
        "accent_gradient_end": "#3b82f6",
        "accent_surface": "#13274f",
        "accent_text": "#ffffff",
        "text_primary": "#ffffff",
        "text_secondary": "#a1a1aa",
        "text_muted": "#71717a",
    },
}


def _is_light_color(hex_str: str) -> bool:
    """Check if color is light based on perceived luminance."""
    try:
        clean = hex_str.lstrip("#")
        if len(clean) == 6:
            r = int(clean[0:2], 16)
            g = int(clean[2:4], 16)
            b = int(clean[4:6], 16)
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            return lum > 0.55
    except Exception:
        pass
    return False


def is_matugen_available() -> bool:
    """Check if Matugen color outputs or executable are present on the system."""
    paths = [
        Path.home() / ".cache/quickshell/matugen.json",
        Path.home() / ".cache/sedly-rice/current_wallpaper",
        Path.home() / ".cache/matugen/vscode-colors.json",
        Path.home() / ".config/gtk-3.0/colors.css",
        Path.home() / ".config/gtk-4.0/colors.css",
        Path.home() / ".config/kdeglobals",
        Path.home() / ".local/state/serpantinum/qs_colors.json",
        Path.home() / ".local/state/serpantinum/qs_matugen_colors.json",
        Path.home() / ".config/matugen/colors.json",
        Path.home() / ".cache/matugen/colors.json",
        Path.home() / ".local/state/matugen/colors.json",
    ]
    for p in paths:
        if p.exists():
            return True

    if shutil.which("matugen") is not None or os.path.exists("/usr/bin/matugen"):
        return True

    return False


def _parse_flat_matugen_json(data: dict) -> Optional[Dict[str, str]]:
    """Parse flat Matugen Material 3 JSON (Quickshell / Rice format)."""
    if not isinstance(data, dict):
        return None

    primary = data.get("primary")
    if not primary or not isinstance(primary, str) or not primary.startswith("#"):
        return None

    bg_base = (
        data.get("surface_container_lowest")
        or data.get("surface")
        or data.get("background")
        or "#140c0c"
    )
    bg_surface = (
        data.get("surface_container_low")
        or data.get("surface")
        or data.get("background")
        or "#1f1818"
    )
    bg_subsurface = data.get("surface") or bg_base
    bg_capsule = data.get("surface_container_lowest") or bg_base
    bg_input = (
        data.get("surface_container")
        or data.get("surface_variant")
        or "#271d1d"
    )
    bg_input_hover = (
        data.get("surface_container_high")
        or data.get("surface_bright")
        or "#322827"
    )
    bg_card_hover = data.get("surface_container_high") or bg_input_hover
    border = (
        data.get("outline_variant")
        or data.get("surface_variant")
        or "#534342"
    )
    border_subtle = (
        data.get("surface_container_highest")
        or data.get("outline_variant")
        or "#3d3231"
    )
    accent = primary
    accent_hover = data.get("surface_tint") or data.get("secondary") or accent
    accent_surface = data.get("primary_container") or "#733332"

    accent_text = data.get("on_primary")
    if not accent_text:
        accent_text = bg_base if _is_light_color(accent) else "#ffffff"

    accent_grad_start = accent
    accent_grad_end = data.get("secondary") or accent_hover

    text_primary = data.get("on_surface") or "#f0dedd"
    text_secondary = data.get("on_surface_variant") or "#d8c1c0"
    text_muted = data.get("outline") or "#a08c8b"

    return {
        "name": "🪄 Matugen (Systémové barvy)",
        "bg_base": bg_base,
        "bg_surface": bg_surface,
        "bg_subsurface": bg_subsurface,
        "bg_capsule": bg_capsule,
        "bg_input": bg_input,
        "bg_input_hover": bg_input_hover,
        "bg_card_hover": bg_card_hover,
        "border": border,
        "border_subtle": border_subtle,
        "border_hover": accent,
        "accent": accent,
        "accent_hover": accent_hover,
        "accent_gradient_start": accent_grad_start,
        "accent_gradient_end": accent_grad_end,
        "accent_surface": accent_surface,
        "accent_text": accent_text,
        "text_primary": text_primary,
        "text_secondary": text_secondary,
        "text_muted": text_muted,
    }


def _parse_standard_matugen_json(data: dict) -> Optional[Dict[str, str]]:
    """Parse standard Matugen JSON color schema."""
    try:
        colors = data.get("colors", {})
        if not colors:
            return None

        def get_c(key: str, fallback: str) -> str:
            item = colors.get(key, {})
            if isinstance(item, dict):
                return item.get("dark", {}).get("color") or item.get("default", {}).get("color") or fallback
            return fallback

        bg_base = get_c("surface_container_lowest", get_c("background", "#0c0e13"))
        bg_surface = get_c("surface_container_low", get_c("surface", "#111318"))
        bg_subsurface = get_c("surface", "#0c0e13")
        bg_card_hover = get_c("surface_container_high", "#191c20")
        bg_input = get_c("surface_container", "#1d2024")
        bg_input_hover = get_c("surface_container_high", "#282a2f")
        border = get_c("outline_variant", "#32353a")
        border_subtle = get_c("surface_container_highest", "#282a2f")

        accent = get_c("primary", "#a5c8fe")
        accent_hover = get_c("surface_tint", "#c1c1ff")
        accent_surface = get_c("primary_container", "#214876")
        accent_text_color = get_c("on_primary", "")
        if not accent_text_color:
            accent_text_color = bg_base if _is_light_color(accent) else "#ffffff"

        text_primary = get_c("on_surface", "#e1e2e9")
        text_secondary = get_c("on_surface_variant", "#c3c6cf")
        text_muted = get_c("outline", "#8d9199")

        return {
            "name": "🪄 Matugen (Systémové barvy)",
            "bg_base": bg_base,
            "bg_surface": bg_surface,
            "bg_subsurface": bg_subsurface,
            "bg_capsule": bg_base,
            "bg_input": bg_input,
            "bg_input_hover": bg_input_hover,
            "bg_card_hover": bg_card_hover,
            "border": border,
            "border_subtle": border_subtle,
            "border_hover": accent,
            "accent": accent,
            "accent_hover": accent_hover,
            "accent_gradient_start": accent,
            "accent_gradient_end": accent_hover,
            "accent_surface": accent_surface,
            "accent_text": accent_text_color,
            "text_primary": text_primary,
            "text_secondary": text_secondary,
            "text_muted": text_muted,
        }
    except Exception:
        return None


def _detect_current_wallpaper_image() -> Optional[str]:
    """Tries to find current desktop wallpaper image path for Matugen."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
                val, _ = winreg.QueryValueEx(key, "Wallpaper")
                if val and os.path.exists(val):
                    return val
        except Exception:
            pass
        return None

    # 1. Check direct rice / desktop cache files
    cache_candidates = [
        Path.home() / ".cache/sedly-rice/current_wallpaper",
        Path.home() / ".cache/current_wallpaper",
        Path.home() / ".cache/wallpaper",
        Path.home() / ".cache/wal/wal",
    ]
    for cp in cache_candidates:
        if cp.exists():
            try:
                p = cp.read_text(encoding="utf-8").strip()
                if os.path.exists(p) and not p.lower().endswith((".mp4", ".webm", ".mkv")):
                    return p
            except Exception:
                pass

    # 2. awww query
    if shutil.which("awww"):
        try:
            res = subprocess.run(["awww", "query"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout:
                import re
                m = re.search(r"image:\s*([^\s\n\r]+)", res.stdout)
                if m and os.path.exists(m.group(1)) and not m.group(1).lower().endswith((".mp4", ".webm", ".mkv")):
                    return m.group(1)
        except Exception:
            pass

    # 3. swww query
    if shutil.which("swww"):
        try:
            res = subprocess.run(["swww", "query"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout:
                import re
                m = re.search(r"image:\s*([^\s\n\r]+)", res.stdout)
                if m and os.path.exists(m.group(1)) and not m.group(1).lower().endswith((".mp4", ".webm", ".mkv")):
                    return m.group(1)
        except Exception:
            pass

    # 4. Quickshell IPC
    if shutil.which("qs"):
        try:
            res = subprocess.run(
                ["qs", "ipc", "call", "wallpaper", "getWallpaperPath", '""'],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                p = res.stdout.strip().strip('"').strip("'")
                if os.path.exists(p) and not p.lower().endswith((".mp4", ".webm", ".mkv")):
                    return p
        except Exception:
            pass

    # 5. Hyprland hyprpaper
    if shutil.which("hyprctl"):
        try:
            res = subprocess.run(["hyprctl", "hyprpaper", "listactive"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    if "=" in line:
                        p = line.split("=", 1)[1].strip()
                        if os.path.exists(p):
                            return p
        except Exception:
            pass

    # 6. GNOME / Cinnamon gsettings
    if shutil.which("gsettings"):
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if res.returncode == 0 and res.stdout:
                p = res.stdout.strip().strip("'").strip('"').replace("file://", "")
                if os.path.exists(p):
                    return p
        except Exception:
            pass

    return None


def _get_matugen_palette() -> Optional[Dict[str, str]]:
    """Load dynamic Material You color scheme generated by Matugen / Desktop profile."""
    # 1. Check Quickshell / Serpantinum / Rice flat Matugen schema
    flat_paths = [
        Path.home() / ".cache/quickshell/matugen.json",
        Path.home() / ".local/state/serpantinum/qs_matugen_colors.json",
    ]
    for fp in flat_paths:
        if fp.exists():
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pal = _parse_flat_matugen_json(data)
                if pal:
                    return pal
            except Exception:
                pass

    # 2. Check Serpantinum Catppuccin-style state files
    serp_paths = [
        Path.home() / ".local/state/serpantinum/qs_colors.json",
    ]
    for sp in serp_paths:
        if sp.exists():
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "base" in data and "text" in data:
                    bg_base = data.get("base", "#0c0e13")
                    bg_surface = data.get("crust", "#111318")
                    bg_mantle = data.get("mantle", "#191c20")
                    bg_input = data.get("surface0", "#1d2024")
                    bg_input_hover = data.get("surface1", "#282a2f")
                    border = data.get("surface2", "#32353a")
                    border_subtle = data.get("surface1", "#282a2f")
                    text_primary = data.get("text", "#e1e2e9")
                    text_secondary = data.get("subtext0", "#c3c6cf")
                    text_muted = data.get("subtext1", "#8d9199")
                    accent = data.get("blue") or data.get("mauve") or "#a5c8fe"
                    accent_hover = data.get("mauve") or data.get("blue") or "#c1c1ff"
                    accent_surface = data.get("sapphire") or "#214876"

                    accent_text = bg_base if _is_light_color(accent) else "#ffffff"

                    return {
                        "name": "🪄 Matugen (Systémové barvy)",
                        "bg_base": bg_base,
                        "bg_surface": bg_surface,
                        "bg_subsurface": bg_surface,
                        "bg_capsule": bg_base,
                        "bg_input": bg_input,
                        "bg_input_hover": bg_input_hover,
                        "bg_card_hover": bg_mantle,
                        "border": border,
                        "border_subtle": border_subtle,
                        "border_hover": accent,
                        "accent": accent,
                        "accent_hover": accent_hover,
                        "accent_gradient_start": accent,
                        "accent_gradient_end": accent_hover,
                        "accent_surface": accent_surface,
                        "accent_text": accent_text,
                        "text_primary": text_primary,
                        "text_secondary": text_secondary,
                        "text_muted": text_muted,
                    }
            except Exception:
                pass

    # 3. Check standard Matugen config / cache files
    std_matugen_paths = [
        Path.home() / ".config/matugen/colors.json",
        Path.home() / ".cache/matugen/colors.json",
        Path.home() / ".local/state/matugen/colors.json",
    ]
    for mp in std_matugen_paths:
        if mp.exists():
            try:
                with open(mp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pal = _parse_standard_matugen_json(data)
                if pal:
                    return pal
            except Exception:
                pass

    # 4. Direct matugen invocation if binary exists and wallpaper image is found
    matugen_bin = shutil.which("matugen") or ("/usr/bin/matugen" if os.path.exists("/usr/bin/matugen") else None)
    if matugen_bin:
        wp_candidate = _detect_current_wallpaper_image()
        if wp_candidate and os.path.exists(wp_candidate):
            try:
                res = subprocess.run(
                    [matugen_bin, "image", wp_candidate, "-m", "dark", "--source-color-index", "0", "--dry-run", "-j", "hex"],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if res.returncode == 0 and res.stdout:
                    data = json.loads(res.stdout)
                    pal = _parse_standard_matugen_json(data)
                    if pal:
                        return pal
            except Exception:
                pass

    return None


def _get_gtk_palette() -> Optional[Dict[str, str]]:
    """Parse GTK 3/4 colors.css generated by Matugen or desktop theme."""
    gtk_paths = [
        Path.home() / ".config/gtk-3.0/colors.css",
        Path.home() / ".config/gtk-4.0/colors.css",
    ]
    for gp in gtk_paths:
        if gp.exists():
            try:
                import re
                content = gp.read_text(encoding="utf-8")
                colors = dict(re.findall(r"@define-color\s+([\w-]+)\s+(#[0-9a-fA-F]{6});", content))
                if "accent_color" in colors and "window_bg_color" in colors:
                    accent = colors["accent_color"]
                    bg = colors["window_bg_color"]
                    fg = colors.get("window_fg_color", "#f0dedd")
                    header_bg = colors.get("headerbar_bg_color", bg)
                    card_bg = colors.get("card_bg_color", bg)
                    accent_fg = colors.get("accent_fg_color") or (bg if _is_light_color(accent) else "#ffffff")
                    return {
                        "name": "🐧 GTK (Systémové téma)",
                        "bg_base": bg,
                        "bg_surface": header_bg,
                        "bg_subsurface": bg,
                        "bg_capsule": bg,
                        "bg_input": card_bg,
                        "bg_input_hover": card_bg,
                        "bg_card_hover": card_bg,
                        "border": colors.get("sidebar_border_color", "#333333"),
                        "border_subtle": "#282828",
                        "border_hover": accent,
                        "accent": accent,
                        "accent_hover": accent,
                        "accent_gradient_start": accent,
                        "accent_gradient_end": accent,
                        "accent_surface": colors.get("accent_bg_color", accent),
                        "accent_text": accent_fg,
                        "text_primary": fg,
                        "text_secondary": fg,
                        "text_muted": "#888888",
                    }
            except Exception:
                pass
    return None


def _get_kde_palette() -> Optional[Dict[str, str]]:
    """Parse KDE Plasma kdeglobals color scheme."""
    kde_path = Path.home() / ".config/kdeglobals"
    if not kde_path.exists():
        return None
    try:
        import configparser
        cp = configparser.ConfigParser()
        cp.read(kde_path)
        if cp.has_section("Colors:Window") and cp.has_section("Colors:Selection"):
            win = cp["Colors:Window"]
            sel = cp["Colors:Selection"]
            btn = cp["Colors:Button"] if cp.has_section("Colors:Button") else win
            bg_base = win.get("backgroundnormal", "#1e2022")
            fg_base = win.get("foregroundnormal", "#e2e2e5")
            accent = sel.get("backgroundnormal", "#3584e4")
            accent_text = sel.get("foregroundnormal", "#ffffff")
            btn_bg = btn.get("backgroundnormal", "#26282b")
            return {
                "name": "❄️ KDE Plasma (Systémové barvy)",
                "bg_base": bg_base,
                "bg_surface": btn_bg,
                "bg_subsurface": bg_base,
                "bg_capsule": bg_base,
                "bg_input": btn_bg,
                "bg_input_hover": btn.get("backgroundalternate", "#35393f"),
                "bg_card_hover": btn_bg,
                "border": win.get("decorationfocus", "#444444"),
                "border_subtle": "#333333",
                "border_hover": accent,
                "accent": accent,
                "accent_hover": sel.get("decorationhover", accent),
                "accent_gradient_start": accent,
                "accent_gradient_end": accent,
                "accent_surface": btn_bg,
                "accent_text": accent_text,
                "text_primary": fg_base,
                "text_secondary": win.get("foregroundinactive", "#8c9198"),
                "text_muted": win.get("foregroundinactive", "#666666"),
            }
    except Exception:
        pass
    return None


def _detect_linux_system_accent() -> Optional[str]:
    """Detect GNOME / GTK / Desktop accent color on Linux or Windows DWM accent."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
                val, _ = winreg.QueryValueEx(key, "AccentColor")
                r = val & 0xFF
                g = (val >> 8) & 0xFF
                b = (val >> 16) & 0xFF
                return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            pass
        return None

    try:
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "accent-color"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if res.returncode == 0 and res.stdout:
            val = res.stdout.strip().strip("'").strip('"').lower()
            accent_map = {
                "blue": "#3584e4",
                "teal": "#2190a4",
                "green": "#3a944c",
                "yellow": "#e5a50a",
                "orange": "#ed5b00",
                "red": "#e62d42",
                "pink": "#d56199",
                "purple": "#9141ac",
                "slate": "#6d7889",
            }
            return accent_map.get(val)
    except Exception:
        pass
    return None


def _get_pywal_palette() -> Optional[Dict[str, str]]:
    """Load palette generated by Pywal from ~/.cache/wal/colors.json if present."""
    wal_file = Path.home() / ".cache" / "wal" / "colors.json"
    if not wal_file.exists():
        return None
    try:
        with open(wal_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        c = data.get("colors", {})
        sp = data.get("special", {})
        bg = sp.get("background", "#121212")
        fg = sp.get("foreground", "#f0f0f0")
        accent = c.get("color4", "#6366f1")
        accent_alt = c.get("color5", "#818cf8")
        return {
            "name": "🎨 Pywal (Systémové barvy tapety)",
            "bg_base": bg,
            "bg_surface": c.get("color0", "#181818"),
            "bg_subsurface": bg,
            "bg_capsule": bg,
            "bg_input": c.get("color8", "#282828"),
            "bg_input_hover": c.get("color7", "#383838"),
            "bg_card_hover": c.get("color0", "#202020"),
            "border": c.get("color8", "#333333"),
            "border_subtle": c.get("color0", "#222222"),
            "border_hover": accent,
            "accent": accent,
            "accent_hover": accent_alt,
            "accent_gradient_start": accent,
            "accent_gradient_end": accent_alt,
            "accent_surface": c.get("color1", "#2b2244"),
            "accent_text": "#ffffff",
            "text_primary": fg,
            "text_secondary": c.get("color7", "#b0b0b0"),
            "text_muted": c.get("color8", "#777777"),
        }
    except Exception:
        return None


def get_available_themes() -> List[Tuple[str, str]]:
    """Return list of (theme_id, display_name) for theme selection."""
    from wallhaven.i18n import tr
    themes = []

    # 1. Matugen / System dynamic colors (first if available on Linux)
    if is_matugen_available() or _detect_linux_system_accent() or _get_gtk_palette() or _get_kde_palette():
        themes.append(("matugen", tr("theme_matugen")))

    # 2. Curated theme palettes
    themes.extend([(k, v["name"]) for k, v in THEME_PALETTES.items()])

    # 3. Pywal colors
    if (Path.home() / ".cache" / "wal" / "colors.json").exists():
        themes.append(("pywal", tr("theme_pywal")))

    return themes


def get_palette(theme_id: str = "dark") -> Dict[str, str]:
    """Retrieve color palette dictionary for given theme ID."""
    if theme_id in ("matugen", "auto", "system"):
        pal = _get_matugen_palette()
        if pal:
            return pal
        gtk_pal = _get_gtk_palette()
        if gtk_pal:
            return gtk_pal
        kde_pal = _get_kde_palette()
        if kde_pal:
            return kde_pal
        wal_pal = _get_pywal_palette()
        if wal_pal:
            return wal_pal
        sys_accent = _detect_linux_system_accent()
        if sys_accent:
            base = dict(THEME_PALETTES["dark"])
            base["name"] = "🐧 Systémové barvy (Accent)"
            base["accent"] = sys_accent
            base["accent_hover"] = sys_accent
            base["accent_gradient_start"] = sys_accent
            base["accent_gradient_end"] = sys_accent
            base["accent_surface"] = "#1e2a3a"
            return base
        theme_id = "dark"

    if theme_id == "pywal":
        wal_pal = _get_pywal_palette()
        if wal_pal:
            return wal_pal
        theme_id = "dark"

    return THEME_PALETTES.get(theme_id, THEME_PALETTES["dark"])


_TEMPLATE_STYLESHEET = """
QWidget {
    background-color: %(bg_base)s;
    color: %(text_primary)s;
    font-family: 'Inter', 'Segoe UI', 'Noto Sans', sans-serif;
    font-size: 13px;
}

/* Sidebar & Modern Layout */
QFrame#komorebiSidebar {
    background-color: %(bg_surface)s;
    border-right: 1px solid %(border_subtle)s;
}

QPushButton#sidebarUtilityBtn {
    background-color: transparent;
    color: %(text_secondary)s;
    border: 1px solid transparent;
    border-radius: 8px;
    text-align: left;
    padding-left: 10px;
    font-size: 11.5px;
    font-weight: 600;
}

QPushButton#sidebarUtilityBtn:hover {
    background-color: %(bg_input_hover)s;
    color: %(text_primary)s;
}

/* Spotlight Canvas Top Bar */
QFrame#spotlightBar {
    background-color: %(bg_surface)s;
    border-bottom: 1px solid %(border_subtle)s;
    padding: 10px 18px;
}

QLineEdit#spotlightInput {
    background-color: %(bg_input)s;
    color: %(text_primary)s;
    border: 1.5px solid %(border)s;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 13px;
    selection-background-color: %(accent)s;
}

QLineEdit#spotlightInput:focus {
    border: 1.5px solid %(accent)s;
    background-color: %(bg_input_hover)s;
    color: %(text_primary)s;
}

/* Header & Filter Panels */
QFrame#headerPanel {
    background-color: %(bg_surface)s;
    border-bottom: 1px solid %(border_subtle)s;
    padding: 8px 16px;
}

QFrame#filterPanel {
    background-color: %(bg_subsurface)s;
    border-bottom: 1px solid %(border_subtle)s;
    padding: 6px 14px;
}

QFrame#colorBarFrame {
    background-color: %(bg_capsule)s;
    border-bottom: 1px solid %(border_subtle)s;
    padding: 6px 16px;
}

QFrame#toolbarSeparator {
    background-color: %(border_subtle)s;
    max-width: 1px;
    margin: 3px 4px;
}

QLabel#filterLabel {
    color: %(text_secondary)s;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.5px;
}

/* Navigation Capsule Container */
QFrame#tabsContainer, QWidget#tabsContainer {
    background-color: %(bg_capsule)s;
    border: 1px solid %(border_subtle)s;
    border-radius: 9px;
    padding: 2px;
}

QPushButton#navTab {
    background: transparent;
    color: %(text_secondary)s;
    border: none;
    border-radius: 7px;
    padding: 4px 9px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#navTab:hover {
    background-color: %(bg_input_hover)s;
    color: %(text_primary)s;
}

QPushButton#navTab:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(accent_gradient_start)s, stop:1 %(accent_gradient_end)s);
    color: %(accent_text)s;
    font-weight: bold;
}

/* Search Box & Inputs */
QLineEdit {
    background-color: %(bg_input)s;
    color: %(text_primary)s;
    border: 1.5px solid %(border)s;
    border-radius: 10px;
    padding: 6px 14px;
    font-size: 13px;
    selection-background-color: %(accent)s;
}

QLineEdit:focus {
    border: 1.5px solid %(accent)s;
    background-color: %(bg_input_hover)s;
    color: %(text_primary)s;
}

/* Combo Boxes */
QComboBox {
    background-color: %(bg_input)s;
    color: %(text_primary)s;
    border: 1.5px solid %(border)s;
    border-radius: 9px;
    padding: 4px 8px;
    padding-right: 20px;
    font-size: 11.5px;
    font-weight: 500;
}

QComboBox:hover {
    border-color: %(accent)s;
    background-color: %(bg_input_hover)s;
    color: %(text_primary)s;
}

QComboBox:focus {
    border-color: %(accent_hover)s;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border: none;
}

QComboBox::down-arrow {
    image: url("__CHEVRON_NORMAL__");
    width: 10px;
    height: 10px;
}

QComboBox::down-arrow:hover {
    image: url("__CHEVRON_HOVER__");
}

QComboBox QAbstractItemView {
    background-color: %(bg_input)s;
    color: %(text_primary)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    selection-background-color: %(accent)s;
    selection-color: %(accent_text)s;
    outline: none;
    padding: 4px;
}

/* Header Tool Buttons */
QPushButton#headerToolBtn {
    background-color: %(bg_input)s;
    color: %(text_secondary)s;
    border: 1.5px solid %(border)s;
    border-radius: 8px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#headerToolBtn:hover {
    background-color: %(bg_input_hover)s;
    border-color: %(border_hover)s;
    color: %(text_primary)s;
}

QPushButton#headerToolBtn:checked {
    background-color: %(accent_surface)s;
    border: 1.5px solid %(accent)s;
    color: %(accent_hover)s;
}

QPushButton#toolButton {
    background-color: %(bg_input)s;
    color: %(text_secondary)s;
    border: 1.5px solid %(border)s;
    border-radius: 7px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#toolButton:hover {
    background-color: %(bg_input_hover)s;
    border-color: %(border_hover)s;
    color: %(text_primary)s;
}

QPushButton#toolButton:checked {
    background-color: %(accent_surface)s;
    border: 1.5px solid %(accent)s;
    color: %(accent_hover)s;
}

/* Primary Vibrant Button (Search, Action) */
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(accent_gradient_start)s, stop:1 %(accent_gradient_end)s);
    border: 1px solid %(accent_hover)s;
    color: %(accent_text)s;
    font-weight: bold;
    border-radius: 8px;
    padding: 5px 14px;
    font-size: 12px;
}

QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %(accent_hover)s, stop:1 %(accent_gradient_end)s);
    border-color: %(text_primary)s;
}

QPushButton#primaryButton:pressed {
    background-color: %(accent_surface)s;
}

/* Standard Push Buttons */
QPushButton {
    background-color: %(bg_input)s;
    color: %(text_primary)s;
    border: 1.5px solid %(border)s;
    border-radius: 8px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: %(bg_input_hover)s;
    border-color: %(accent)s;
    color: %(text_primary)s;
}

QPushButton:pressed {
    background-color: %(bg_capsule)s;
    border-color: %(accent)s;
}

/* Filter Chips */
QPushButton#filterChip {
    background-color: %(bg_input)s;
    color: %(text_secondary)s;
    border: 1.5px solid %(border)s;
    border-radius: 12px;
    padding: 3px 7px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#filterChip:hover {
    border-color: %(accent)s;
    background-color: %(bg_input_hover)s;
    color: %(text_primary)s;
}

QPushButton#filterChip:checked {
    background-color: %(accent_surface)s;
    border: 1.5px solid %(accent)s;
    color: %(accent_text)s;
    font-weight: bold;
}

QPushButton#nsfwChip {
    background-color: %(bg_input)s;
    color: %(text_secondary)s;
    border: 1.5px solid %(border)s;
    border-radius: 12px;
    padding: 3px 7px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#nsfwChip:hover {
    border-color: #f43f5e;
    background-color: %(bg_input_hover)s;
    color: #ffffff;
}

QPushButton#nsfwChip:checked {
    background-color: #881337;
    border: 1.5px solid #f43f5e;
    color: #ffe4e6;
    font-weight: bold;
}

QPushButton#sketchyChip {
    background-color: %(bg_input)s;
    color: %(text_secondary)s;
    border: 1.5px solid %(border)s;
    border-radius: 12px;
    padding: 3px 7px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#sketchyChip:hover {
    border-color: #f59e0b;
    background-color: %(bg_input_hover)s;
    color: #ffffff;
}

QPushButton#sketchyChip:checked {
    background-color: #78350f;
    border: 1.5px solid #f59e0b;
    color: #fef3c7;
    font-weight: bold;
}

QPushButton#themeChip {
    background-color: %(bg_input)s;
    border: 1.5px solid %(border)s;
    border-radius: 12px;
    padding: 3px 7px;
    font-size: 11px;
    color: %(text_secondary)s;
}

QPushButton#themeChip:hover {
    border-color: %(accent_hover)s;
    background-color: %(bg_input_hover)s;
    color: %(text_primary)s;
}

QPushButton#themeChip:checked {
    background-color: %(accent_surface)s;
    border: 1.5px solid %(accent)s;
    color: %(accent_text)s;
    font-weight: bold;
}

/* Scroll Area & Sleek Modern Scrollbar */
QWidget#ambientContentCanvas {
    background-color: transparent;
}

QWidget#canvasWrapper, QWidget#wallpaperGrid {
    background-color: transparent;
    border: none;
}

QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 0;
}

QScrollBar::handle:vertical {
    background: %(border)s;
    min-height: 28px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: %(border_hover)s;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Wallpaper Card */
QFrame#wallpaperCard {
    background-color: %(bg_surface)s;
    border: 1.5px solid %(border)s;
    border-radius: 14px;
}

QFrame#wallpaperCard:hover {
    border: 1.5px solid %(accent)s;
    background-color: %(bg_card_hover)s;
}

/* Card Badges */
QLabel#badge {
    background-color: rgba(0, 0, 0, 0.70);
    color: %(text_primary)s;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 10.5px;
    font-weight: bold;
}

QLabel#categoryBadge {
    background-color: %(accent_surface)s;
    color: %(text_primary)s;
    border: 1px solid %(accent)s;
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 10.5px;
    font-weight: bold;
}

/* Pagination Frame & Badges */
QFrame#paginationFrame {
    background-color: %(bg_subsurface)s;
    border-top: 1px solid %(border_subtle)s;
    padding: 6px 16px;
}

QLabel#pageBadge {
    background-color: %(bg_input)s;
    border: 1px solid %(border)s;
    border-radius: 7px;
    padding: 4px 10px;
    min-width: 100px;
    qproperty-alignment: AlignCenter;
    font-weight: bold;
    color: %(text_primary)s;
    font-size: 12px;
}

/* SpinBox */
QSpinBox {
    background-color: %(bg_input)s;
    color: %(text_primary)s;
    border: 1.5px solid %(border)s;
    border-radius: 8px;
    padding: 3px 6px;
    font-size: 12px;
    font-weight: 600;
}

QSpinBox:focus {
    border-color: %(accent)s;
}

/* Status Bar */
QStatusBar {
    background-color: transparent;
    color: %(text_muted)s;
    border: none;
    font-size: 12px;
    padding: 3px 12px;
}

/* Tooltips */
QToolTip {
    background-color: %(bg_surface)s;
    color: %(text_primary)s;
    border: 1.5px solid %(border)s;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
}

/* Dialog & Settings */
QDialog {
    background-color: %(bg_base)s;
    color: %(text_primary)s;
}

QFrame#previewContainer {
    background-color: %(bg_capsule)s;
    border: 1px solid %(border_subtle)s;
    border-radius: 12px;
}

QWidget#detailSidebar {
    background-color: %(bg_surface)s;
    border: 1px solid %(border_subtle)s;
    border-radius: 12px;
}

QPushButton#setWallNowBtn {
    background-color: %(accent_surface)s;
    color: %(accent_text)s;
    border: 1.5px solid %(accent)s;
    border-radius: 8px;
    font-weight: 600;
    font-size: 12px;
    padding: 6px 12px;
}

QPushButton#setWallNowBtn:hover {
    background-color: %(accent)s;
    border-color: %(accent_hover)s;
    color: %(accent_text)s;
}

QPushButton#sidebarSecondaryBtn {
    background-color: %(bg_input)s;
    color: %(text_primary)s;
    border: 1.5px solid %(border)s;
    border-radius: 8px;
    font-weight: 600;
    font-size: 12px;
    padding: 6px 12px;
}

QPushButton#sidebarSecondaryBtn:hover {
    background-color: %(bg_input_hover)s;
    border-color: %(border_hover)s;
    color: %(text_primary)s;
}

QGroupBox {
    border: 1px solid %(border)s;
    border-radius: 10px;
    margin-top: 10px;
    padding-top: 12px;
    font-weight: bold;
    color: %(text_primary)s;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: %(text_primary)s;
}
"""


def get_stylesheet(theme_id: str = "dark") -> str:
    """Generate complete CSS stylesheet for given theme ID."""
    pal = get_palette(theme_id)
    css = _TEMPLATE_STYLESHEET % pal
    return css.replace(
        "__CHEVRON_NORMAL__", _CHEVRON_NORMAL
    ).replace(
        "__CHEVRON_HOVER__", _CHEVRON_HOVER
    )


def apply_theme(theme_id: str = "dark"):
    """Apply stylesheet for theme to the active QApplication instance."""
    app = QApplication.instance()
    if app:
        qss = get_stylesheet(theme_id)
        app.setStyleSheet(qss)


DARK_STYLESHEET = get_stylesheet("dark")


class ThemeWatcher(QObject):
    """Watches external Matugen and Pywal color files and live-reloads application styles."""
    theme_reloaded = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._on_reload_timeout)

        self._watch_targets = [
            Path.home() / ".cache/quickshell/matugen.json",
            Path.home() / ".cache/quickshell",
            Path.home() / ".cache/sedly-rice/current_wallpaper",
            Path.home() / ".cache/sedly-rice",
            Path.home() / ".config/gtk-3.0/colors.css",
            Path.home() / ".config/gtk-3.0",
            Path.home() / ".config/gtk-4.0/colors.css",
            Path.home() / ".config/kdeglobals",
            Path.home() / ".cache/matugen/vscode-colors.json",
            Path.home() / ".cache/matugen",
            Path.home() / ".config/matugen/colors.json",
            Path.home() / ".cache/matugen/colors.json",
            Path.home() / ".local/state/matugen/colors.json",
            Path.home() / ".local/state/serpantinum/qs_colors.json",
            Path.home() / ".local/state/serpantinum/qs_matugen_colors.json",
            Path.home() / ".local/state/serpantinum",
            Path.home() / ".cache/wal/colors.json",
            Path.home() / ".cache/wal",
        ]
        self._setup_watchers()

        self._watcher.fileChanged.connect(self._on_change)
        self._watcher.directoryChanged.connect(self._on_change)

    def _setup_watchers(self):
        for p in self._watch_targets:
            if p.exists():
                sp = str(p)
                if sp not in self._watcher.files() and sp not in self._watcher.directories():
                    try:
                        self._watcher.addPath(sp)
                    except Exception:
                        pass

    def _on_change(self, path: str):
        # Trigger debounced reload
        self._debounce_timer.start()

    def _on_reload_timeout(self):
        self._setup_watchers()
        try:
            from wallhaven.config import config
            curr_theme = config.get("theme", "dark")
        except Exception:
            curr_theme = "matugen"

        # If current theme is Matugen, System or Pywal, refresh dynamically
        if curr_theme in ("matugen", "auto", "system", "pywal"):
            app = QApplication.instance()
            if app:
                new_qss = get_stylesheet(curr_theme)
                app.setStyleSheet(new_qss)
                self.theme_reloaded.emit(curr_theme)


_THEME_WATCHER: Optional[ThemeWatcher] = None


def get_theme_watcher() -> Optional[ThemeWatcher]:
    """Get or create singleton ThemeWatcher instance (requires QApplication)."""
    global _THEME_WATCHER
    app = QApplication.instance()
    if not app:
        return None
    if _THEME_WATCHER is None:
        _THEME_WATCHER = ThemeWatcher(app)
    return _THEME_WATCHER
