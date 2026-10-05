import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    CONFIG_DIR = Path(appdata) / "wallhaven-desktop"
else:
    CONFIG_DIR = Path.home() / ".config" / "wallhaven-desktop"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_default_download_dir() -> Path:
    # Prefer existing Wallpapers directory
    candidates = [
        Path.home() / "Obrázky" / "Wallpapers",
        Path.home() / "Pictures" / "Wallpapers",
        Path.home() / "wallpapers",
        Path.home() / "Pictures",
        Path.home() / "Obrázky",
        Path.home() / "Downloads",
        Path.home() / "Stažené",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    # Fallback to home/Pictures/Wallpapers
    default_dir = Path.home() / "Pictures" / "Wallpapers"
    default_dir.mkdir(parents=True, exist_ok=True)
    return default_dir


def get_default_theme() -> str:
    if sys.platform != "win32":
        serp = Path.home() / ".local/state/serpantinum" / "qs_colors.json"
        if serp.exists():
            return "matugen"
    return "dark"


DEFAULT_CONFIG = {
    "api_key": "",
    "default_download_dir": str(get_default_download_dir()),
    "categories": "111",  # General, Anime, People (1=on, 0=off)
    "purity": "100",      # SFW, Sketchy, NSFW (1=on, 0=off)
    "sorting": "toplist", # date_added, relevance, random, views, favorites, toplist, hot
    "top_range": "1M",    # 1d, 3d, 1w, 1M, 3M, 6M, 1y
    "atleast": "",        # e.g. 1920x1080, 2560x1440, 3840x2160
    "ratios": "",         # e.g. 16x9, 16x10, 21x9
    "color": "",          # Hex code without #
    "per_page": 24,
    "theme": get_default_theme(),
    "auto_set_wallpaper": True,
    "wallpaper_setter": "auto",
    "custom_wallpaper_cmd": "",
    "custom_video_wallpaper_cmd": "",
    "moewalls_category": "all",
    "language": "en",
    "background_effects": True,
    "check_updates_on_launch": True,
    "last_update_check": 0.0,
}


class Config:
    def __init__(self):
        self._config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config.update(data)
                # Auto-upgrade 'system' theme to 'matugen' if Serpantinum / Matugen is active
                if self._config.get("theme") in ("system", "dark") and sys.platform != "win32":
                    if (Path.home() / ".local/state/serpantinum" / "qs_colors.json").exists():
                        self._config["theme"] = "matugen"
            except Exception as e:
                print(f"Error loading config: {e}")
        else:
            self.save()

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    @property
    def api_key(self) -> str:
        return self._config.get("api_key", "").strip()

    @api_key.setter
    def api_key(self, val: str):
        self.set("api_key", val.strip())

    @property
    def default_download_dir(self) -> str:
        path = self._config.get("default_download_dir", "")
        if not path or not os.path.isdir(path):
            path = str(get_default_download_dir())
        return path

    @default_download_dir.setter
    def default_download_dir(self, val: str):
        self.set("default_download_dir", val)

    @property
    def auto_set_wallpaper(self) -> bool:
        return bool(self._config.get("auto_set_wallpaper", True))

    @auto_set_wallpaper.setter
    def auto_set_wallpaper(self, val: bool):
        self.set("auto_set_wallpaper", bool(val))

    @property
    def wallpaper_setter(self) -> str:
        return str(self._config.get("wallpaper_setter", "auto")).strip()

    @wallpaper_setter.setter
    def wallpaper_setter(self, val: str):
        self.set("wallpaper_setter", str(val).strip())

    @property
    def custom_wallpaper_cmd(self) -> str:
        return str(self._config.get("custom_wallpaper_cmd", "")).strip()

    @custom_wallpaper_cmd.setter
    def custom_wallpaper_cmd(self, val: str):
        self.set("custom_wallpaper_cmd", str(val).strip())

    @property
    def custom_video_wallpaper_cmd(self) -> str:
        return str(self._config.get("custom_video_wallpaper_cmd", "")).strip()

    @custom_video_wallpaper_cmd.setter
    def custom_video_wallpaper_cmd(self, val: str):
        self.set("custom_video_wallpaper_cmd", str(val).strip())

    @property
    def moewalls_category(self) -> str:
        return str(self._config.get("moewalls_category", "all")).strip()

    @moewalls_category.setter
    def moewalls_category(self, val: str):
        self.set("moewalls_category", str(val).strip())

    @property
    def language(self) -> str:
        return str(self._config.get("language", "en"))

    @language.setter
    def language(self, val: str):
        self.set("language", str(val))

    @property
    def theme(self) -> str:
        return str(self._config.get("theme", get_default_theme())).strip()

    @theme.setter
    def theme(self, val: str):
        self.set("theme", str(val).strip())

    @property
    def background_effects(self) -> bool:
        return bool(self._config.get("background_effects", True))

    @background_effects.setter
    def background_effects(self, val: bool):
        self.set("background_effects", bool(val))

    @property
    def check_updates_on_launch(self) -> bool:
        return bool(self._config.get("check_updates_on_launch", True))

    @check_updates_on_launch.setter
    def check_updates_on_launch(self, val: bool):
        self.set("check_updates_on_launch", bool(val))

    @property
    def last_update_check(self) -> float:
        return float(self._config.get("last_update_check", 0.0))

    @last_update_check.setter
    def last_update_check(self, val: float):
        self.set("last_update_check", float(val))


config = Config()
