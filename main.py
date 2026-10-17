import importlib.abc
import importlib.machinery
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

GITHUB_REPO = "Sedly12322/komorebi-desktop"


def get_live_app_dir() -> Path:
    """Returns the user-writable live-update directory used by the frozen Windows runtime."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else (Path.home() / "AppData" / "Local")
        return base / "KomorebiDesktop" / "live_app"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data) if xdg_data else (Path.home() / ".local" / "share")
    return base / "komorebi-desktop" / "live_app"


def _parse_ver(v: str) -> tuple[int, ...]:
    if not v:
        return (0, 0, 0)
    clean = v.strip().lstrip("vV").split("-")[0].split("+")[0]
    nums = [int(p) for p in re.split(r"[._]", clean) if p.isdigit()]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def _read_init_version(init_file: Path) -> str:
    try:
        if init_file.is_file():
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_file.read_text(encoding="utf-8"))
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""


class _LivePackageFinder(importlib.abc.MetaPathFinder):
    """MetaPathFinder that loads `wallhaven.*` from `live_app` ahead of PyInstaller's PyiFrozenImporter."""

    def __init__(self, live_root: Path):
        self.live_root = str(live_root.resolve())

    def find_spec(self, fullname: str, path=None, target=None):
        if fullname != "wallhaven" and not fullname.startswith("wallhaven."):
            return None
        search_paths = [self.live_root] if fullname == "wallhaven" else path
        return importlib.machinery.PathFinder.find_spec(fullname, search_paths, target)


def _bootstrap_update_from_github() -> int:
    """Downloads the latest Komorebi Desktop source from GitHub into live_app (used by Universal Installer)."""
    live_dir = get_live_app_dir()
    bundled_ver = "0.0.0"
    if hasattr(sys, "_MEIPASS"):
        bundled_ver = _read_init_version(Path(sys._MEIPASS) / "wallhaven" / "__init__.py") or "0.0.0"

    try:
        # Check main branch version first (always has the very latest commits/releases)
        raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/wallhaven/__init__.py"
        req = urllib.request.Request(raw_url, headers={"User-Agent": "Komorebi-Universal-Bootstrap/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        remote_ver = m.group(1) if m else ""

        # If bundled exe already has the same or newer version and live_dir doesn't need replacing, skip download
        current_live_ver = _read_init_version(live_dir / "wallhaven" / "__init__.py")
        best_local = current_live_ver if _parse_ver(current_live_ver) > _parse_ver(bundled_ver) else bundled_ver
        if remote_ver and _parse_ver(remote_ver) <= _parse_ver(best_local):
            return 0

        zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
        with tempfile.TemporaryDirectory(prefix="komorebi-bootstrap-") as tmp:
            tmp_path = Path(tmp)
            archive_path = tmp_path / "main.zip"
            extract_dir = tmp_path / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)

            req_zip = urllib.request.Request(zip_url, headers={"User-Agent": "Komorebi-Universal-Bootstrap/1.0"})
            with urllib.request.urlopen(req_zip, timeout=30) as resp_zip, open(archive_path, "wb") as out_f:
                shutil.copyfileobj(resp_zip, out_f)

            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(extract_dir)

            roots = [p for p in extract_dir.iterdir() if p.is_dir()]
            if not roots:
                return 0
            src_root = roots[0]
            if not (src_root / "wallhaven" / "__init__.py").is_file():
                return 0

            live_dir.mkdir(parents=True, exist_ok=True)
            for item_name in ("wallhaven", "assets", "main.py", "LICENSE"):
                src_item = src_root / item_name
                if not src_item.exists():
                    continue
                dst_item = live_dir / item_name
                if dst_item.is_dir():
                    shutil.rmtree(dst_item, ignore_errors=True)
                elif dst_item.exists():
                    dst_item.unlink(missing_ok=True)
                if src_item.is_dir():
                    shutil.copytree(src_item, dst_item)
                else:
                    shutil.copy2(src_item, dst_item)
    except Exception:
        # Offline or GitHub unreachable during setup -> silently fall back to bundled version
        pass
    return 0


def _activate_live_app_if_newer() -> _LivePackageFinder | None:
    """If running as a frozen executable and a valid live_app >= bundled version exists, activate it."""
    if not getattr(sys, "frozen", False):
        return None
    live_dir = get_live_app_dir()
    live_init = live_dir / "wallhaven" / "__init__.py"
    if not live_init.is_file():
        return None

    live_ver = _read_init_version(live_init)
    bundled_ver = "0.0.0"
    if hasattr(sys, "_MEIPASS"):
        bundled_ver = _read_init_version(Path(sys._MEIPASS) / "wallhaven" / "__init__.py") or "0.0.0"

    if not live_ver or _parse_ver(live_ver) < _parse_ver(bundled_ver):
        return None

    os.environ["KOMOREBI_LIVE_APP_DIR"] = str(live_dir)
    if str(live_dir) not in sys.path:
        sys.path.insert(0, str(live_dir))
    finder = _LivePackageFinder(live_dir)
    sys.meta_path.insert(0, finder)
    return finder


if __name__ == "__main__":
    if "--bootstrap-update" in sys.argv:
        sys.exit(_bootstrap_update_from_github())

    # Ensure package root is in sys.path
    sys.path.insert(0, str(Path(__file__).parent))

    _finder = _activate_live_app_if_newer()
    try:
        from wallhaven.app import main
    except Exception:
        # Automatic self-healing fallback to bundled frozen modules if live_app was corrupted
        if _finder is not None and _finder in sys.meta_path:
            sys.meta_path.remove(_finder)
        os.environ.pop("KOMOREBI_LIVE_APP_DIR", None)
        for k in [m for m in list(sys.modules) if m == "wallhaven" or m.startswith("wallhaven.")]:
            sys.modules.pop(k, None)
        from wallhaven.app import main

    main()
