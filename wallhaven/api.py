import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
import requests
from wallhaven.config import config

API_BASE_URL = "https://wallhaven.cc/api/v1"
USER_AGENT = "KomorebiDesktop/2.0 (High-Performance Wallpaper Manager)"


@dataclass
class WallpaperItem:
    id: str
    url: str
    short_url: str
    views: int
    favorites: int
    source: str
    purity: str
    category: str
    dimension_x: int
    dimension_y: int
    resolution: str
    ratio: str
    file_size: int
    file_type: str
    created_at: str
    colors: list[str]
    path: str
    thumb_large: str
    thumb_small: str
    thumb_original: str
    tags: list[dict] = field(default_factory=list)
    uploader: Optional[dict] = None
    is_animated: bool = False
    preview_video_url: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "WallpaperItem":
        thumbs = d.get("thumbs", {})
        return cls(
            id=str(d.get("id", "")),
            url=d.get("url", ""),
            short_url=d.get("short_url", ""),
            views=int(d.get("views", 0)),
            favorites=int(d.get("favorites", 0)),
            source=d.get("source", ""),
            purity=d.get("purity", "sfw"),
            category=d.get("category", "general"),
            dimension_x=int(d.get("dimension_x", 0)),
            dimension_y=int(d.get("dimension_y", 0)),
            resolution=d.get("resolution", ""),
            ratio=d.get("ratio", ""),
            file_size=int(d.get("file_size", 0)),
            file_type=d.get("file_type", ""),
            created_at=d.get("created_at", ""),
            colors=d.get("colors", []),
            path=d.get("path", ""),
            thumb_large=thumbs.get("large", ""),
            thumb_small=thumbs.get("small", ""),
            thumb_original=thumbs.get("original", ""),
            tags=d.get("tags", []),
            uploader=d.get("uploader"),
        )

    @property
    def human_file_size(self) -> str:
        if not self.file_size or self.file_size <= 0:
            return "N/A"
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"



@dataclass
class SearchResult:
    items: list[WallpaperItem]
    current_page: int
    last_page: int
    per_page: int
    total: int


class WallhavenAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })

    def _get_headers(self) -> dict:
        headers = {}
        api_key = config.api_key
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    def search(
        self,
        query: str = "",
        categories: str = "111",
        purity: str = "100",
        sorting: str = "toplist",
        order: str = "desc",
        top_range: str = "1M",
        atleast: str = "",
        resolutions: str = "",
        ratios: str = "",
        colors: str = "",
        page: int = 1,
        seed: str = "",
    ) -> SearchResult:
        params = {
            "page": page,
            "categories": categories,
            "purity": purity,
            "sorting": sorting,
            "order": order,
        }

        if query.strip():
            params["q"] = query.strip()
        if sorting == "toplist" and top_range:
            params["topRange"] = top_range
        if sorting == "random" and seed:
            params["seed"] = seed
        if atleast:
            params["atleast"] = atleast
        if resolutions:
            params["resolutions"] = resolutions
        if ratios:
            params["ratios"] = ratios
        if colors:
            params["colors"] = colors

        api_key = config.api_key
        if api_key:
            params["apikey"] = api_key

        url = f"{API_BASE_URL}/search"
        resp = self.session.get(url, params=params, headers=self._get_headers(), timeout=15)
        resp.raise_for_status()

        json_data = resp.json()
        data = json_data.get("data", [])
        meta = json_data.get("meta", {})

        items = [WallpaperItem.from_dict(item) for item in data]
        return SearchResult(
            items=items,
            current_page=int(meta.get("current_page", page)),
            last_page=int(meta.get("last_page", 1)),
            per_page=int(meta.get("per_page", 24)),
            total=int(meta.get("total", len(items))),
        )

    def get_wallpaper_detail(self, wallpaper_id: str) -> WallpaperItem:
        url = f"{API_BASE_URL}/w/{wallpaper_id}"
        params = {}
        api_key = config.api_key
        if api_key:
            params["apikey"] = api_key

        resp = self.session.get(url, params=params, headers=self._get_headers(), timeout=15)
        resp.raise_for_status()
        json_data = resp.json()
        return WallpaperItem.from_dict(json_data.get("data", {}))

    def download_file(
        self,
        url: str,
        dest_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
        headers: Optional[dict] = None,
    ) -> bool:
        tmp_path = dest_path + ".download"
        try:
            req_headers = self._get_headers()
            if headers:
                req_headers.update(headers)
            with self.session.get(url, headers=req_headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB chunks

                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if is_cancelled and is_cancelled():
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                            return False
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total_size)

            if os.path.exists(tmp_path):
                # Atomic rename
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                os.replace(tmp_path, dest_path)
                return True
            return False
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise e


api = WallhavenAPI()
