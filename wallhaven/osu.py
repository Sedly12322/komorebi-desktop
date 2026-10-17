import json
import os
import random
import sys
from pathlib import Path
from wallhaven.api import WallpaperItem, SearchResult


def _get_data_file() -> Path:
    live_dir = os.environ.get("KOMOREBI_LIVE_APP_DIR")
    if live_dir:
        lp = Path(live_dir) / "wallhaven" / "data" / "osu_seasonal.json"
        if lp.exists():
            return lp
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "wallhaven" / "data" / "osu_seasonal.json"
        if p.exists():
            return p
    return Path(__file__).parent / "data" / "osu_seasonal.json"


DATA_FILE = _get_data_file()


class OsuSeasonalManager:
    def __init__(self):
        self._raw_items: list[dict] = []
        self._wallpaper_items: list[WallpaperItem] = []
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        data_file = _get_data_file()
        if not data_file.exists():
            return
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                self._raw_items = json.load(f)

            self._wallpaper_items = []
            for it in self._raw_items:
                w = it.get("width", 1920)
                h = it.get("height", 1080)
                season = it.get("season", "Seasonal")
                theme = it.get("theme", "osu!")
                artist = it.get("artist", "Unknown Artist")
                votes = it.get("votes", 0)
                rank = it.get("rank", 0)
                title = it.get("title", f"osu! {season}")
                preview = it.get("preview_url", "")
                thumb = it.get("thumbnail_url") or preview

                tags = [
                    {"name": "osu!"},
                    {"name": season},
                    {"name": theme},
                    {"name": artist},
                ]
                if 0 < rank <= 15:
                    tags.insert(1, {"name": f"🏆 Winner #{rank}"})

                wp = WallpaperItem(
                    id=it["id"],
                    url=it.get("contest_url", "https://osu.ppy.sh/community/contests"),
                    short_url=it.get("contest_url", "https://osu.ppy.sh/community/contests"),
                    views=votes,
                    favorites=votes,
                    source=f"osu! {season} Fanart Contest",
                    purity="sfw",
                    category="anime",
                    dimension_x=w,
                    dimension_y=h,
                    resolution=f"{w}x{h}",
                    ratio="16:9",
                    file_size=0,
                    file_type="image/png" if preview.lower().endswith(".png") else "image/jpeg",
                    created_at=str(it.get("year", 2024)),
                    colors=[],
                    path=preview,
                    thumb_large=thumb,
                    thumb_small=thumb,
                    thumb_original=preview,
                    tags=tags,
                    uploader={"username": artist},
                )
                wp._osu_meta = it
                self._wallpaper_items.append(wp)
            self._loaded = True
        except Exception as e:
            print(f"Failed to load osu seasonal wallpapers: {e}")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def total_count(self) -> int:
        self.load()
        return len(self._wallpaper_items)

    def get_seasons(self) -> list[str]:
        self.load()
        seasons = []
        seen = set()
        for it in self._raw_items:
            s = it.get("season")
            if s and s not in seen:
                seen.add(s)
                seasons.append(s)
        return seasons

    def get_themes(self) -> list[str]:
        self.load()
        themes = []
        seen = set()
        for it in self._raw_items:
            t = it.get("theme")
            if t and t not in seen:
                seen.add(t)
                themes.append(t)
        return themes

    def search(
        self,
        query: str = "",
        season: str = "",
        theme: str = "",
        sorting: str = "votes",
        page: int = 1,
        per_page: int = 24,
    ) -> SearchResult:
        self.load()
        results = list(self._wallpaper_items)

        # Filter by season
        if season and season != "all":
            results = [wp for wp in results if getattr(wp, "_osu_meta", {}).get("season") == season]

        # Filter by theme
        if theme and theme != "all":
            results = [wp for wp in results if getattr(wp, "_osu_meta", {}).get("theme") == theme]

        # Filter by query (title, artist, season)
        if query:
            q = query.lower().strip()
            results = [
                wp for wp in results
                if q in getattr(wp, "_osu_meta", {}).get("title", "").lower()
                or q in getattr(wp, "_osu_meta", {}).get("artist", "").lower()
                or q in getattr(wp, "_osu_meta", {}).get("season", "").lower()
            ]

        # Sorting
        if sorting == "votes":
            results.sort(key=lambda wp: getattr(wp, "_osu_meta", {}).get("votes", 0), reverse=True)
        elif sorting == "newest":
            results.sort(
                key=lambda wp: (
                    getattr(wp, "_osu_meta", {}).get("contest_id", 0),
                    -getattr(wp, "_osu_meta", {}).get("rank", 999),
                ),
                reverse=True,
            )
        elif sorting == "random":
            rng = random.Random(page * 42)
            rng.shuffle(results)

        total = len(results)
        last_page = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, last_page))

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_items = results[start_idx:end_idx]

        return SearchResult(
            items=page_items,
            current_page=page,
            last_page=last_page,
            per_page=per_page,
            total=total,
        )


osu_manager = OsuSeasonalManager()
