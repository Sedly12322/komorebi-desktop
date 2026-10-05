import hashlib
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Optional
from PyQt6.QtGui import QPixmap

if sys.platform == "win32":
    localapp = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    CACHE_DIR = Path(localapp) / "komorebi-desktop"
    OLD_CACHE_DIR = Path(localapp) / "wallhaven-desktop"
else:
    CACHE_DIR = Path.home() / ".cache" / "komorebi-desktop"
    OLD_CACHE_DIR = Path.home() / ".cache" / "wallhaven-desktop"

# Transparent migration from legacy cache directory if new one doesn't exist yet
if not CACHE_DIR.exists() and OLD_CACHE_DIR.exists():
    try:
        import shutil
        shutil.move(str(OLD_CACHE_DIR), str(CACHE_DIR))
    except Exception:
        pass

THUMB_CACHE_DIR = CACHE_DIR / "thumbnails"
FULL_CACHE_DIR = CACHE_DIR / "previews"

MAX_CACHE_BYTES = 750 * 1024 * 1024  # 750 MB disk cache


class ImageCache:
    def __init__(self):
        THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        FULL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # High-performance LRU memory caches
        self._pixmap_mem_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._scaled_mem_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._max_mem_entries = 250
        self._max_scaled_entries = 350

    def _url_to_path(self, url: str, is_thumb: bool = True) -> Path:
        hash_str = hashlib.sha256(url.encode("utf-8")).hexdigest()
        ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
        target_dir = THUMB_CACHE_DIR if is_thumb else FULL_CACHE_DIR
        return target_dir / f"{hash_str}{ext}"

    def get_cached_path(self, url: str, is_thumb: bool = True) -> Optional[Path]:
        path = self._url_to_path(url, is_thumb)
        if path.exists() and path.stat().st_size > 0:
            return path
        return None

    def get_scaled_pixmap(self, url: str, w: int, h: int) -> Optional[QPixmap]:
        key = f"{url}_{w}_{h}"
        if key in self._scaled_mem_cache:
            self._scaled_mem_cache.move_to_end(key)
            return self._scaled_mem_cache[key]
        return None

    def save_scaled_pixmap(self, url: str, w: int, h: int, pm: QPixmap):
        if pm and not pm.isNull():
            key = f"{url}_{w}_{h}"
            if key in self._scaled_mem_cache:
                self._scaled_mem_cache.move_to_end(key)
            self._scaled_mem_cache[key] = pm
            if len(self._scaled_mem_cache) > self._max_scaled_entries:
                self._scaled_mem_cache.popitem(last=False)

    def get_pixmap(self, url: str, is_thumb: bool = True) -> Optional[QPixmap]:
        if url in self._pixmap_mem_cache:
            self._pixmap_mem_cache.move_to_end(url)
            return self._pixmap_mem_cache[url]

        path = self.get_cached_path(url, is_thumb)
        if path:
            pm = QPixmap(str(path))
            if not pm.isNull():
                self._pixmap_mem_cache[url] = pm
                if len(self._pixmap_mem_cache) > self._max_mem_entries:
                    self._pixmap_mem_cache.popitem(last=False)
                return pm
        return None

    def save_data(self, url: str, data: bytes, is_thumb: bool = True) -> Path:
        path = self._url_to_path(url, is_thumb)
        try:
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                f.write(data)
            temp_path.replace(path)
            # Store in mem cache
            pm = QPixmap()
            if pm.loadFromData(data):
                self._pixmap_mem_cache[url] = pm
                if len(self._pixmap_mem_cache) > self._max_mem_entries:
                    self._pixmap_mem_cache.popitem(last=False)
        except Exception as e:
            print(f"Error saving cached image {url}: {e}")
        return path

    def clean_old_cache_if_needed(self):
        try:
            total_size = sum(f.stat().st_size for f in CACHE_DIR.glob("**/*") if f.is_file())
            if total_size > MAX_CACHE_BYTES:
                files = sorted(
                    [f for f in CACHE_DIR.glob("**/*") if f.is_file()],
                    key=lambda f: f.stat().st_mtime
                )
                for f in files:
                    if total_size <= MAX_CACHE_BYTES * 0.7:
                        break
                    try:
                        total_size -= f.stat().st_size
                        f.unlink()
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error cleaning cache: {e}")

    def get_video_thumb_path(self, video_path: str) -> Path:
        hash_str = hashlib.sha256(str(video_path).encode("utf-8")).hexdigest()
        return THUMB_CACHE_DIR / f"vid_{hash_str}.jpg"


cache = ImageCache()
