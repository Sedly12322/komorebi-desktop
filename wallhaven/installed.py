import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Union
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QImageReader
from wallhaven.api import WallpaperItem, SearchResult
from wallhaven.config import config, CONFIG_DIR

INSTALLED_FILE = CONFIG_DIR / "installed.json"


def _format_bytes(size: int) -> str:
    if size <= 0:
        return "0 B"
    s = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if s < 1024.0:
            return f"{s:.1f} {unit}"
        s /= 1024.0
    return f"{s:.1f} PB"


class InstalledManager:
    def __init__(self):
        self._items: dict[str, dict] = {}  # keyed by absolute normalized file_path
        self._loaded = False
        self.load()

    def load(self):
        if INSTALLED_FILE.exists():
            try:
                with open(INSTALLED_FILE, "r", encoding="utf-8") as f:
                    self._items = json.load(f)
            except Exception as e:
                print(f"Error loading installed wallpapers: {e}")
                self._items = {}
        else:
            self._items = {}
        self._loaded = True

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(INSTALLED_FILE, "w", encoding="utf-8") as f:
                json.dump(self._items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving installed wallpapers: {e}")

    def is_installed(self, item_or_path: Union[WallpaperItem, str]) -> bool:
        if isinstance(item_or_path, str):
            p = os.path.abspath(item_or_path)
            if p in self._items and os.path.exists(p):
                return True
            for path, data in self._items.items():
                if data.get("id") == item_or_path and os.path.exists(path):
                    return True
            return False
        else:
            # WallpaperItem
            local_path = getattr(item_or_path, "local_path", "")
            if local_path and os.path.exists(local_path):
                return True
            if item_or_path.path and os.path.isabs(item_or_path.path) and os.path.exists(item_or_path.path):
                return True
            for path, data in self._items.items():
                if data.get("id") == str(item_or_path.id) and os.path.exists(path):
                    return True
            return False

    def get_installed_path(self, item: WallpaperItem) -> Optional[str]:
        local_path = getattr(item, "local_path", "")
        if local_path and os.path.exists(local_path):
            return local_path
        if item.path and os.path.isabs(item.path) and os.path.exists(item.path):
            return item.path
        for path, data in self._items.items():
            if data.get("id") == str(item.id) and os.path.exists(path):
                return path
        return None

    def register_download(self, file_path: str, item: WallpaperItem):
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return

        size = os.path.getsize(file_path)
        title = getattr(item, "_display_title", "")
        if not title and getattr(item, "_osu_meta", None):
            meta = item._osu_meta
            title = f"{meta.get('title', '')} - {meta.get('artist', '')}"
        if not title:
            if getattr(item, "is_animated", False):
                title = os.path.splitext(os.path.basename(file_path))[0].replace("moewalls-", "").replace("_", " ")
            else:
                title = f"{item.source or 'Wallpaper'} #{item.id}"

        source = item.source
        if not source:
            if getattr(item, "is_animated", False):
                source = "MoeWalls"
            elif getattr(item, "_osu_meta", None):
                source = "osu!"
            else:
                source = "Wallhaven"

        tags = []
        if item.tags:
            for t in item.tags:
                if isinstance(t, dict):
                    tags.append(t.get("name", ""))
                elif isinstance(t, str):
                    tags.append(t)

        self._items[file_path] = {
            "id": str(item.id),
            "title": title,
            "source": source,
            "file_path": file_path,
            "file_size": size,
            "is_animated": bool(getattr(item, "is_animated", False)),
            "resolution": item.resolution or "Unknown",
            "dimension_x": item.dimension_x or 0,
            "dimension_y": item.dimension_y or 0,
            "ratio": item.ratio or "",
            "thumb_url": item.thumb_large or item.thumb_small or "",
            "url": item.url or "",
            "tags": tags,
            "colors": item.colors or [],
            "category": item.category or "General",
            "purity": item.purity or "sfw",
            "installed_at": time.time(),
        }
        self.save()

    def _probe_video_resolution(self, video_path: str) -> tuple[int, int, str]:
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                video_path,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and "x" in res.stdout:
                w, h = res.stdout.strip().split("x")[:2]
                w, h = int(w), int(h)
                return w, h, f"{w}x{h}"
        except Exception:
            pass
        return 1920, 1080, "1920x1080"

    def scan_local_wallpapers(self):
        """
        Scans the default wallpaper download directory and syncs with installed.json.
        Prunes missing files and automatically registers uncatalogued wallpaper files.
        """
        download_dir = Path(config.default_download_dir)
        changed = False

        # 1. Prune missing files
        to_delete = []
        for path in self._items:
            if not os.path.exists(path):
                to_delete.append(path)
        if to_delete:
            for p in to_delete:
                del self._items[p]
            changed = True

        # 2. Scan download_dir
        if download_dir.is_dir():
            supported_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp4", ".webm", ".mkv"}
            try:
                for entry in os.scandir(download_dir):
                    if not entry.is_file():
                        continue
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext not in supported_exts:
                        continue

                    abs_path = os.path.abspath(entry.path)
                    if abs_path in self._items:
                        continue

                    # Determine metadata from filename
                    fname = entry.name
                    file_size = entry.stat().st_size
                    mtime = entry.stat().st_mtime
                    is_animated = ext in {".mp4", ".webm", ".mkv"}

                    source = "Local"
                    title = os.path.splitext(fname)[0]
                    item_id = title
                    tags = []
                    category = "Wallpaper"

                    if fname.startswith("osu-"):
                        source = "osu!"
                        category = "Anime"
                        tags.append("osu!")
                        parts = os.path.splitext(fname)[0].split("-")
                        if len(parts) >= 4:
                            season = parts[1].replace("_", " ")
                            artist = parts[2].replace("_", " ")
                            raw_title = parts[3].replace("_", " ")
                            title = f"{raw_title} by {artist}"
                            tags.extend([season, artist, "Seasonal"])
                    elif fname.startswith("moewalls-") or "moewalls-com" in fname:
                        source = "MoeWalls"
                        is_animated = True
                        category = "Animated"
                        clean = os.path.splitext(fname)[0].replace("moewalls-", "").replace("-moewalls-com", "").replace("_", " ").strip()
                        title = clean
                        tags.extend(["MoeWalls", "Animated", "Live Wallpaper"])
                    elif fname.startswith("wallhaven-"):
                        source = "Wallhaven"
                        item_id = os.path.splitext(fname)[0].replace("wallhaven-", "")
                        title = f"Wallhaven #{item_id}"
                        tags.append("Wallhaven")
                    elif is_animated:
                        source = "MoeWalls"
                        tags.extend(["Live Wallpaper", "Video"])

                    # Resolution
                    if is_animated:
                        dim_x, dim_y, res_str = self._probe_video_resolution(abs_path)
                    else:
                        reader = QImageReader(abs_path)
                        sz = reader.size()
                        if sz.isValid():
                            dim_x, dim_y = sz.width(), sz.height()
                            res_str = f"{dim_x}x{dim_y}"
                        else:
                            dim_x, dim_y = 1920, 1080
                            res_str = "1920x1080"

                    self._items[abs_path] = {
                        "id": item_id,
                        "title": title,
                        "source": source,
                        "file_path": abs_path,
                        "file_size": file_size,
                        "is_animated": is_animated,
                        "resolution": res_str,
                        "dimension_x": dim_x,
                        "dimension_y": dim_y,
                        "ratio": f"{dim_x / max(1, dim_y):.2f}" if dim_y > 0 else "16:9",
                        "thumb_url": "",
                        "url": "",
                        "tags": tags,
                        "colors": [],
                        "category": category,
                        "purity": "sfw",
                        "installed_at": mtime,
                    }
                    changed = True
            except Exception as e:
                print(f"Error scanning local wallpaper directory: {e}")

        if changed:
            self.save()

    def uninstall_wallpaper(self, item_or_path: Union[WallpaperItem, str]) -> tuple[bool, str]:
        """
        Uninstalls (deletes) the wallpaper from disk and removes it from the installed registry.
        """
        target_path = None
        if isinstance(item_or_path, str):
            p = os.path.abspath(item_or_path)
            if p in self._items or os.path.exists(p):
                target_path = p
            else:
                for path, data in self._items.items():
                    if data.get("id") == item_or_path:
                        target_path = path
                        break
        else:
            target_path = self.get_installed_path(item_or_path)

        if not target_path:
            return False, "Wallpaper not found in installed database."

        # Delete file
        error_msg = ""
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception as e:
                error_msg = str(e)
                return False, f"Cannot delete file: {error_msg}"

        # Clean from registry
        if target_path in self._items:
            del self._items[target_path]
            self.save()

        # Delete any generated video thumbnail from cache
        try:
            from wallhaven.cache import cache
            vid_thumb = cache.get_video_thumb_path(target_path)
            if vid_thumb.exists():
                vid_thumb.unlink()
        except Exception:
            pass

        return True, ""

    def get_stats(self, rescan: bool = True) -> dict:
        if rescan:
            self.scan_local_wallpapers()
        total_count = len(self._items)
        total_bytes = sum(item.get("file_size", 0) for item in self._items.values())
        return {
            "total_count": total_count,
            "total_bytes": total_bytes,
            "human_size": _format_bytes(total_bytes),
        }

    def search(
        self,
        query: str = "",
        provider: str = "all",
        media_type: str = "all",
        sorting: str = "latest",
        page: int = 1,
        per_page: int = 24,
    ) -> SearchResult:
        self.scan_local_wallpapers()

        q = query.strip().lower()
        prov = provider.strip().lower()
        mtype = media_type.strip().lower()

        filtered: list[dict] = []
        for data in self._items.values():
            # Check if file still exists
            if not os.path.exists(data.get("file_path", "")):
                continue

            # Provider filter
            item_source = data.get("source", "").lower()
            if prov != "all":
                if prov == "wallhaven" and "wallhaven" not in item_source:
                    continue
                elif prov == "moewalls" and "moewalls" not in item_source:
                    continue
                elif prov in ("osu", "osu!") and "osu" not in item_source:
                    continue

            # Media type filter
            is_anim = bool(data.get("is_animated", False))
            if mtype == "image" and is_anim:
                continue
            elif mtype == "video" and not is_anim:
                continue

            # Query text search
            if q:
                match = (
                    q in data.get("title", "").lower()
                    or q in data.get("id", "").lower()
                    or q in data.get("source", "").lower()
                    or q in os.path.basename(data.get("file_path", "")).lower()
                    or any(q in t.lower() for t in data.get("tags", []))
                )
                if not match:
                    continue

            filtered.append(data)

        # Sorting
        if sorting == "oldest":
            filtered.sort(key=lambda d: d.get("installed_at", 0))
        elif sorting == "name":
            filtered.sort(key=lambda d: d.get("title", "").lower())
        elif sorting == "size":
            filtered.sort(key=lambda d: d.get("file_size", 0), reverse=True)
        else:  # latest
            filtered.sort(key=lambda d: d.get("installed_at", 0), reverse=True)

        total = len(filtered)
        last_page = max(1, (total + per_page - 1) // per_page)
        if page < 1:
            page = 1
        if page > last_page:
            page = last_page

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_items = filtered[start_idx:end_idx]

        results: list[WallpaperItem] = []
        for d in page_items:
            path = d.get("file_path", "")
            ext = os.path.splitext(path)[1].lstrip(".").lower()
            thumb = d.get("thumb_url") or path

            wp = WallpaperItem(
                id=d.get("id", ""),
                url=d.get("url", ""),
                short_url=d.get("url", ""),
                views=0,
                favorites=0,
                source=d.get("source", "Installed"),
                purity=d.get("purity", "sfw"),
                category=d.get("category", "Installed"),
                dimension_x=d.get("dimension_x", 0),
                dimension_y=d.get("dimension_y", 0),
                resolution=d.get("resolution", ""),
                ratio=d.get("ratio", "16:9"),
                file_size=d.get("file_size", 0),
                file_type=f"image/{ext}" if not d.get("is_animated", False) else f"video/{ext}",
                created_at="",
                colors=d.get("colors", []),
                path=path,
                thumb_large=thumb,
                thumb_small=thumb,
                thumb_original=path,
                tags=[{"name": t} for t in d.get("tags", [])],
                is_animated=d.get("is_animated", False),
                preview_video_url=path if d.get("is_animated", False) else "",
            )
            setattr(wp, "_display_title", d.get("title", ""))
            setattr(wp, "is_installed", True)
            setattr(wp, "local_path", path)
            results.append(wp)

        return SearchResult(
            items=results,
            current_page=page,
            last_page=last_page,
            per_page=per_page,
            total=total,
        )


installed_manager = InstalledManager()
