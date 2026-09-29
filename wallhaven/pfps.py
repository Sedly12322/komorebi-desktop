"""Pfps.gg Client and Avatar Manager for Komorebi.

Provides search, browsing, downloading and system avatar integration
for Discord profile pictures, anime PFPs, aesthetic icons, and animated GIFs from pfps.gg.
"""
import os
import sys
import re
import json
import shutil
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QImage


@dataclass
class PfpItem:
    id: str
    title: str
    image_url: str
    format: str  # png, gif, jpeg, webp
    downloads: str
    category: str = "all"
    page_url: str = ""

    @property
    def is_animated(self) -> bool:
        return self.format.lower() == "gif" or self.image_url.lower().endswith(".gif")

    @property
    def filename(self) -> str:
        ext = self.format.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        safe_title = re.sub(r'[^\w\-_\.]', '_', self.title)
        return f"{safe_title}_{self.id}{ext}"


PFP_CATEGORIES = [
    ("all", "✨ Vše / Nejnovější", "All / Latest"),
    ("anime", "🌸 Anime", "Anime"),
    ("animated", "🎞️ GIF / Animované", "Animated / GIF"),
    ("aesthetic", "🌙 Aesthetic", "Aesthetic"),
    ("gaming", "🎮 Gaming", "Gaming"),
    ("cute", "🐾 Cute / Roztomilé", "Cute"),
    ("meme", "🐸 Meme & Funny", "Meme & Funny"),
    ("dark", "🖤 Dark / Gothic", "Dark / Gothic"),
    ("matching", "👥 Matching / Dvojice", "Matching Pairs"),
    ("boy", "👦 Boy", "Boy"),
    ("girl", "👧 Girl", "Girl"),
    ("cool", "⚡ Cool", "Cool"),
    ("black", "🕶️ Black", "Black"),
    ("blue", "💙 Blue", "Blue"),
]

PFP_SORTING = [
    ("latest", "Nejnovější", "Latest"),
    ("downloads", "Nejvíce stahované", "Most Downloaded"),
    ("oldest", "Nejstarší", "Oldest"),
]


class PfpsClient:
    """Client for fetching and managing avatars from pfps.gg."""

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

    def __init__(self):
        self._cache_dir = Path.home() / ".cache" / "komorebi" / "pfps"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_categories(self) -> List[Tuple[str, str, str]]:
        return list(PFP_CATEGORIES)

    def get_sorting_options(self) -> List[Tuple[str, str, str]]:
        return list(PFP_SORTING)

    def fetch_pfps(
        self,
        category: str = "all",
        sort: str = "latest",
        page: int = 1,
        query: str = "",
    ) -> Tuple[List[PfpItem], bool]:
        """
        Fetches profile pictures matching criteria from pfps.gg.
        Returns (items_list, has_next_page).
        """
        query_clean = query.strip()
        if query_clean:
            # Search mode
            encoded_q = urllib.parse.quote(query_clean)
            url = f"https://pfps.gg/search?q={encoded_q}&page={page}"
        elif category in ("all", "", "latest"):
            # Homepage / latest
            url = f"https://pfps.gg?sort={sort}&page={page}" if page > 1 or sort != "latest" else "https://pfps.gg"
        else:
            # Category mode
            url = f"https://pfps.gg/pfps/{category}?sort={sort}&page={page}"

        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"[PfpsClient] Fetch error for {url}: {e}")
            return [], False

        # Parse <article class="...item..."...>...</article>
        card_matches = re.findall(r'<article class=\"[^\"]*item[^\"]*\"[^>]*>.*?</article>', html, re.DOTALL)
        items: List[PfpItem] = []

        for card in card_matches:
            # Extract Image URL
            img_m = re.search(r'<img src=\"(https://cdn\.pfps\.gg/pfps/[^\"]+)\"', card)
            if not img_m:
                continue
            image_url = img_m.group(1).strip()

            # Extract Title
            title_m = re.search(r'<span class=\"line-clamp-1[^\"]*\">(.*?)</span>', card)
            title = title_m.group(1).strip() if title_m else "Avatar"

            # Extract ID / Slug
            id_m = re.search(r'href=\"/pfp/([^\"]+)\"', card)
            pfp_id = id_m.group(1).strip() if id_m else os.path.basename(image_url).split(".")[0]

            # Extract Format (png, gif, jpeg)
            fmt_m = re.search(r'<span class=\"uppercase[^\"]*\">(.*?)</span>', card)
            fmt = fmt_m.group(1).strip().lower() if fmt_m else os.path.splitext(image_url)[1].lstrip(".") or "png"

            # Extract Download Count
            dl_m = re.search(r'fa-download[^\"]*\"><\/i>\s*([\d,]+)', card)
            downloads = dl_m.group(1).replace(",", "").strip() if dl_m else "0"

            page_url = f"https://pfps.gg/pfp/{pfp_id}"

            items.append(
                PfpItem(
                    id=pfp_id,
                    title=title,
                    image_url=image_url,
                    format=fmt,
                    downloads=downloads,
                    category=category,
                    page_url=page_url,
                )
            )

        # Determine if there's a next page
        has_next = "next-page" in html or len(card_matches) >= 30

        return items, has_next

    def get_default_avatar_dir(self) -> Path:
        """Determines default local folder for avatars."""
        candidates = [
            Path.home() / "Obrázky" / "Avatary",
            Path.home() / "Pictures" / "Avatars",
            Path.home() / "Pictures",
            Path.home() / "Obrázky",
        ]
        for c in candidates:
            if c.is_dir():
                return c
        target = Path.home() / "Pictures" / "Avatars"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def download_pfp(self, item: PfpItem, target_dir: Optional[str] = None) -> Tuple[bool, str]:
        """Downloads PFP file to target directory. Returns (success, saved_path_or_error)."""
        try:
            dest_dir = Path(target_dir) if target_dir else self.get_default_avatar_dir()
            dest_dir.mkdir(parents=True, exist_ok=True)

            target_path = dest_dir / item.filename

            req = urllib.request.Request(item.image_url, headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp, open(target_path, "wb") as f:
                f.write(resp.read())

            return True, str(target_path)
        except Exception as e:
            return False, str(e)

    def set_system_avatar(self, item: PfpItem, existing_file: Optional[str] = None) -> Tuple[bool, str]:
        """Sets the selected avatar as Linux desktop user profile picture."""
        try:
            # Ensure local file exists
            if existing_file and os.path.exists(existing_file):
                src_file = Path(existing_file)
            else:
                cache_file = self._cache_dir / item.filename
                if not cache_file.exists():
                    req = urllib.request.Request(item.image_url, headers={"User-Agent": self.USER_AGENT})
                    with urllib.request.urlopen(req, timeout=20) as resp, open(cache_file, "wb") as f:
                        f.write(resp.read())
                src_file = cache_file

            # 1. Linux Standard ~/.face and ~/.face.icon
            home_dir = Path.home()
            face_path = home_dir / ".face"
            face_icon_path = home_dir / ".face.icon"

            shutil.copyfile(src_file, face_path)
            shutil.copyfile(src_file, face_icon_path)

            # 2. Serpantinum Desktop avatar integration
            serp_cfg_file = home_dir / ".config" / "serpantinum" / "settings.json"
            if serp_cfg_file.exists():
                try:
                    with open(serp_cfg_file, "r", encoding="utf-8") as f:
                        serp_data = json.load(f)
                    if "general" not in serp_data:
                        serp_data["general"] = {}
                    serp_data["general"]["avatarPath"] = str(face_path)
                    with open(serp_cfg_file, "w", encoding="utf-8") as f:
                        json.dump(serp_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"[PfpsClient] Warning updating Serpantinum config: {e}")

            # 3. Desktop notification
            if sys.platform != "win32" and shutil.which("notify-send"):
                try:
                    import subprocess
                    subprocess.run(
                        [
                            "notify-send",
                            "-a", "Komorebi",
                            "-i", str(face_path),
                            "Profilovka změněna",
                            f"Systémový avatar byl úspěšně nastaven na: {item.title}",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=3,
                    )
                except Exception:
                    pass

            return True, f"Profilovka '{item.title}' byla úspěšně nastavena pro systém a plochu!"
        except Exception as e:
            return False, f"Chyba při nastavování profilovky: {e}"

    @staticmethod
    def copy_image_to_clipboard(pixmap: QPixmap) -> bool:
        """Copies QPixmap into system clipboard for easy Ctrl+V paste."""
        try:
            clipboard = QApplication.clipboard()
            if clipboard and not pixmap.isNull():
                clipboard.setPixmap(pixmap)
                return True
        except Exception as e:
            print(f"[PfpsClient] Clipboard error: {e}")
        return False


pfps_client = PfpsClient()
