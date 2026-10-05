"""In-app update checker and updater for Komorebi Desktop.

Features:
- Queries GitHub Releases API (and fallback to tags) for new releases
- Detects git commits ahead/behind when running from a git clone
- Asynchronous background update checking (UpdateCheckWorker)
- Asynchronous chunked download and installation worker (UpdateApplyWorker)
- Full support for Linux (updating ~/.local/share/komorebi-desktop or git pull)
- Full support for Windows (downloading & executing Setup installer)
- Modern animated UpdateDialog and floating UpdateBanner
- Detached application restart
"""
import os
import sys
import re
import json
import time
import shutil
import hashlib
import tarfile
import tempfile
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
import urllib.request
import urllib.error

from PyQt6.QtCore import (
    Qt,
    QObject,
    QThread,
    pyqtSignal,
    QPoint,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
    QUrl,
)
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QLinearGradient,
    QDesktopServices,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QFrame,
    QApplication,
    QGraphicsDropShadowEffect,
)

from wallhaven import __version__
from wallhaven.config import config
from wallhaven.i18n import tr
from wallhaven.styles import get_asset_path, get_palette

GITHUB_REPO = "Sedly12322/komorebi-desktop"
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"

# ---------------------------------------------------------------------------
# Worker lifetime registry
# ---------------------------------------------------------------------------
# Workers are never parented to widgets. This set keeps them alive until they
# have delivered their result, so closing a dialog mid-check/mid-install can
# never destroy a running thread.
_ACTIVE_WORKERS: set = set()
_SHUTDOWN_HOOKED = False


def _track_worker(worker):
    global _SHUTDOWN_HOOKED
    _ACTIVE_WORKERS.add(worker)
    app = QApplication.instance()
    if app is not None and not _SHUTDOWN_HOOKED:
        app.aboutToQuit.connect(_wait_for_running_installs)
        _SHUTDOWN_HOOKED = True


def _untrack_worker_later(worker):
    # Deferred so that all queued result slots run before the last reference drops.
    QTimer.singleShot(1000, lambda: _ACTIVE_WORKERS.discard(worker))


def _wait_for_running_installs():
    """On quit, let an in-progress install finish instead of leaving a half-updated app."""
    for w in list(_ACTIVE_WORKERS):
        if isinstance(w, QThread) and w.isRunning():
            w.wait(300_000)


def parse_semver(v: str) -> tuple[int, ...]:
    """Parse a version string (e.g., 'v1.4.2', '2.0.0', 'v1.4.2-beta') into a comparable tuple."""
    if not v:
        return (0, 0, 0)
    v_clean = v.strip().lstrip("vV")
    main_part = v_clean.split("-")[0].split("+")[0]
    nums = []
    for part in re.split(r"[._]", main_part):
        if part.isdigit():
            nums.append(int(part))
        else:
            break
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def is_newer_version(remote_v: str, local_v: str) -> bool:
    """Return True if remote_v is strictly greater than local_v."""
    return parse_semver(remote_v) > parse_semver(local_v)


@dataclass
class UpdateInfo:
    current_version: str = __version__
    latest_version: str = ""
    has_update: bool = False
    release_name: str = ""
    release_notes: str = ""
    published_at: str = ""
    html_url: str = ""
    tarball_url: str = ""
    zipball_url: str = ""
    windows_installer_url: str | None = None
    windows_installer_name: str | None = None
    windows_portable_url: str | None = None
    checksums: dict[str, str] = field(default_factory=dict)
    is_git_clone: bool = False
    git_branch: str = ""
    git_commits_ahead: int = 0
    error: str = ""


def check_for_updates_sync(current_ver: str = __version__) -> UpdateInfo:
    """Synchronously queries GitHub for the latest release and update information."""
    info = UpdateInfo(current_version=current_ver)

    # 1. Check if running inside a git repository
    app_root = Path(__file__).resolve().parent.parent
    if (app_root / ".git").is_dir():
        info.is_git_clone = True
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(app_root),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                info.git_branch = res.stdout.strip()
        except Exception:
            pass

    # 2. Query GitHub Releases API
    url = f"{GITHUB_API_BASE}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"Komorebi-Desktop-Updater/{current_ver}",
        },
    )

    release_data = None
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                release_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Fallback to listing all releases (e.g. if only draft or pre-release)
            try:
                list_url = f"{GITHUB_API_BASE}/releases"
                req_list = urllib.request.Request(
                    list_url,
                    headers={
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": f"Komorebi-Desktop-Updater/{current_ver}",
                    },
                )
                with urllib.request.urlopen(req_list, timeout=8) as resp:
                    releases = json.loads(resp.read().decode("utf-8"))
                    if releases and isinstance(releases, list):
                        release_data = releases[0]
            except Exception as e_sub:
                info.error = str(e_sub)
        else:
            info.error = f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        info.error = str(e)

    if not release_data:
        # Fallback to tags if releases failed
        try:
            tags_url = f"{GITHUB_API_BASE}/tags"
            req_tags = urllib.request.Request(
                tags_url,
                headers={"User-Agent": f"Komorebi-Desktop-Updater/{current_ver}"},
            )
            with urllib.request.urlopen(req_tags, timeout=8) as resp:
                tags = json.loads(resp.read().decode("utf-8"))
                if tags and isinstance(tags, list):
                    first_tag = tags[0].get("name", "")
                    info.latest_version = first_tag
                    info.has_update = is_newer_version(first_tag, current_ver)
                    info.tarball_url = tags[0].get("tarball_url", "")
                    info.html_url = f"https://github.com/{GITHUB_REPO}/releases/tag/{first_tag}"
                    info.release_name = f"Release {first_tag}"
                    return info
        except Exception:
            pass
        return info

    tag = release_data.get("tag_name", "")
    info.latest_version = tag
    info.release_name = release_data.get("name") or f"Release {tag}"
    info.release_notes = release_data.get("body") or ""
    info.published_at = release_data.get("published_at", "")
    info.html_url = release_data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}"
    info.tarball_url = release_data.get("tarball_url") or f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.tar.gz"
    info.zipball_url = release_data.get("zipball_url") or f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.zip"

    # Assets inspection & SHA256 discovery
    checksum_assets: list[tuple[str, str]] = []
    for asset in release_data.get("assets", []):
        name = asset.get("name", "")
        dl_url = asset.get("browser_download_url", "")
        name_lower = name.lower()
        if name_lower.endswith(".exe"):
            info.windows_installer_url = dl_url
            info.windows_installer_name = name
        elif name_lower.endswith(".zip") and "portable" in name_lower:
            info.windows_portable_url = dl_url
        elif name_lower.endswith(".sha256") or name_lower in ("sha256sums.txt", "checksums.txt", "sha256sum.txt"):
            checksum_assets.append((name, dl_url))

    # 1. Parse checksums from release notes (body)
    if info.release_notes:
        for line in info.release_notes.splitlines():
            line = line.strip()
            m = re.search(r"\b([a-fA-F0-9]{64})\b\s+\*?([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)", line)
            if m:
                h, fn = m.groups()
                info.checksums[fn.strip().lower()] = h.strip().lower()
            else:
                m2 = re.search(r"([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)\s*[:=]\s*\b([a-fA-F0-9]{64})\b", line)
                if m2:
                    fn, h = m2.groups()
                    info.checksums[fn.strip().lower()] = h.strip().lower()

    # 2. Parse dedicated checksum asset files if present
    for c_name, c_url in checksum_assets:
        try:
            req_c = urllib.request.Request(c_url, headers={"User-Agent": f"Komorebi-Desktop-Updater/{current_ver}"})
            with urllib.request.urlopen(req_c, timeout=5) as c_resp:
                c_content = c_resp.read(65536).decode("utf-8", errors="ignore")
                if c_name.lower().endswith(".sha256") and not c_name.lower().startswith("sha256sums"):
                    target_file = c_name[:-7]
                    h_match = re.search(r"\b([a-fA-F0-9]{64})\b", c_content)
                    if h_match:
                        info.checksums[target_file.lower()] = h_match.group(1).lower()
                else:
                    for line in c_content.splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 2 and len(parts[0]) == 64:
                            h = parts[0]
                            fn = parts[1].lstrip("*")
                            info.checksums[fn.lower()] = h.lower()
        except Exception:
            pass

    info.has_update = is_newer_version(tag, current_ver)
    try:
        config.last_update_check = time.time()
    except Exception:
        pass
    return info


class UpdateCheckWorker(QObject):
    """Checks GitHub for updates on a daemon Python thread.

    Uses a daemon ``threading.Thread`` instead of ``QThread`` so that closing a
    dialog or quitting the app while a (slow) network request is in flight can
    never trigger ``QThread: Destroyed while thread is still running`` aborts.
    The worker is intentionally never parented to a widget; its lifetime is
    managed by the module-level registry until results have been delivered.
    """

    check_finished = pyqtSignal(object)  # UpdateInfo
    check_failed = pyqtSignal(str)

    def __init__(self, current_ver: str = __version__, parent=None):
        # ``parent`` is accepted for API compatibility but deliberately ignored.
        super().__init__(None)
        self.current_ver = current_ver
        self._thread: threading.Thread | None = None
        self.check_finished.connect(self._cleanup)
        self.check_failed.connect(self._cleanup)

    def start(self):
        if self.isRunning():
            return
        _track_worker(self)
        self._thread = threading.Thread(target=self._run, name="komorebi-update-check", daemon=True)
        self._thread.start()

    def isRunning(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def wait(self, msecs: int | None = None) -> bool:
        if self._thread:
            self._thread.join(None if msecs is None else msecs / 1000.0)
        return not self.isRunning()

    def _run(self):
        try:
            info = check_for_updates_sync(self.current_ver)
            if info.error and not info.latest_version:
                self._safe_emit(self.check_failed, info.error)
            else:
                self._safe_emit(self.check_finished, info)
        except Exception as e:
            self._safe_emit(self.check_failed, str(e))

    @staticmethod
    def _safe_emit(signal, value):
        try:
            signal.emit(value)
        except RuntimeError:
            # Receiver/wrapper already deleted (e.g. app shutting down) - ignore.
            pass

    def _cleanup(self, *_):
        _untrack_worker_later(self)


class UpdateApplyWorker(QThread):
    """Background worker that downloads and installs the application update.

    NOTE: the result signal is called ``apply_finished`` on purpose - naming it
    ``finished`` would shadow QThread's built-in ``finished`` signal.
    """

    progress = pyqtSignal(int, str)  # (percent 0-100, message)
    apply_finished = pyqtSignal(bool, str)  # (success, message / installer path)

    UPDATE_ITEMS = ("wallhaven", "assets", "main.py", "requirements.txt", "LICENSE", "install.sh")

    def __init__(self, info: UpdateInfo, parent=None):
        # Never parented to a dialog: closing the dialog must not destroy a running install.
        super().__init__(None)
        self.info = info
        self.finished.connect(lambda: _untrack_worker_later(self))

    def start(self, *args):
        _track_worker(self)
        super().start(*args)

    def run(self):
        try:
            # Guard against downgrades: only ever install a strictly newer release.
            if not self.info.has_update or not is_newer_version(self.info.latest_version, self.info.current_version):
                self.apply_finished.emit(
                    False,
                    tr("updater_err_not_newer", version=self.info.latest_version or '?', current=self.info.current_version),
                )
                return
            if sys.platform == "win32":
                self._update_windows()
            else:
                self._update_linux()
        except Exception as e:
            self.apply_finished.emit(False, str(e))

    # ------------------------------------------------------------------ helpers
    def _download(self, url: str, target: Path, pct_start: int, pct_span: int):
        req = urllib.request.Request(url, headers={"User-Agent": f"Komorebi-Desktop-Updater/{__version__}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("content-length", 0) or 0)
            downloaded = 0
            with open(target, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    cur_mb = downloaded / (1024 * 1024)
                    if total_size > 0:
                        pct = pct_start + int((downloaded / total_size) * pct_span)
                        tot_mb = total_size / (1024 * 1024)
                        self.progress.emit(pct, tr("updater_prog_downloading_mb", cur=cur_mb, tot=tot_mb, pct=pct))
                    else:
                        self.progress.emit(pct_start, tr("updater_prog_downloading_cur", cur=cur_mb))

    @staticmethod
    def _remove_path(p: Path):
        if p.is_symlink() or p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)

    def _verify_sha256(self, target_path: Path, filename: str):
        """Verifies downloaded file against SHA-256 checksum if available in release metadata."""
        if not target_path.exists():
            return
        expected_hash = self.info.checksums.get(filename.lower())
        if not expected_hash:
            return  # No checksum was published for this asset

        self.progress.emit(90, tr("updater_prog_verifying_hash"))
        h = hashlib.sha256()
        with open(target_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        actual_hash = h.hexdigest().lower()
        if actual_hash != expected_hash.lower():
            try:
                target_path.unlink()
            except Exception:
                pass
            raise RuntimeError(
                tr("updater_err_sha256_mismatch", name=filename, expected=expected_hash, actual=actual_hash)
            )

    # ------------------------------------------------------------------ Windows
    def _update_windows(self):
        """Downloads the Windows installer; it is launched after the user confirms restart."""
        installer_url = self.info.windows_installer_url
        if not installer_url:
            self.apply_finished.emit(
                False,
                tr("updater_err_no_win_installer", url=self.info.html_url),
            )
            return

        out_name = self.info.windows_installer_name or "Komorebi-Desktop-Setup.exe"
        target_path = Path(tempfile.gettempdir()) / out_name

        self.progress.emit(5, tr("updater_prog_download_installer", name=out_name))
        self._download(installer_url, target_path, 5, 85)

        # Verify integrity
        self._verify_sha256(target_path, out_name)

        self.progress.emit(100, tr("updater_prog_installer_ready"))
        self.apply_finished.emit(True, str(target_path))

    # ------------------------------------------------------------------ Linux
    def _update_linux(self):
        if getattr(sys, "frozen", False):
            raise RuntimeError(tr("updater_err_frozen_linux", url=self.info.html_url))
        app_root = Path(__file__).resolve().parent.parent
        if (app_root / ".git").exists():
            self._update_git_clone(app_root)
        else:
            self._update_from_archive(app_root)

    def _run_git(self, args: list[str], repo: Path, timeout: int = 60) -> str:
        res = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            detail = (res.stderr or res.stdout).strip()
            raise RuntimeError(f"git {' '.join(args)} selhal: {detail}")
        return res.stdout.strip()

    def _run_install_script(self, repo: Path):
        install_sh = repo / "install.sh"
        if not install_sh.is_file():
            return
        self.progress.emit(70, tr("updater_prog_updating_system"))
        res = subprocess.run(["bash", str(install_sh)], cwd=str(repo), capture_output=True, text=True, timeout=900)
        if res.returncode != 0:
            tail = "\n".join((res.stderr or res.stdout).strip().splitlines()[-5:])
            raise RuntimeError(f"install.sh selhal:\n{tail}")

    def _update_git_clone(self, repo: Path):
        """Fast-forward a git checkout. Never merges, never touches local changes."""
        self.progress.emit(10, tr("updater_prog_git_status"))
        if self._run_git(["status", "--porcelain", "--untracked-files=no"], repo):
            raise RuntimeError(tr("updater_err_git_dirty"))
        branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
        if branch == "HEAD":
            raise RuntimeError(tr("updater_err_git_detached"))

        self.progress.emit(25, tr("updater_prog_git_fetch", branch=branch))
        self._run_git(["fetch", "origin", branch], repo, timeout=120)

        self.progress.emit(50, tr("updater_prog_git_apply"))
        self._run_git(["merge", "--ff-only", f"origin/{branch}"], repo)

        self._run_install_script(repo)

        self.progress.emit(100, tr("updater_prog_done"))
        self.apply_finished.emit(True, tr("updater_success_git"))

    def _update_from_archive(self, target_dir: Path):
        """Download release tarball, validate it, then swap files in with automatic rollback."""
        tag = self.info.latest_version
        archive_url = self.info.tarball_url or f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.tar.gz"

        with tempfile.TemporaryDirectory(prefix="komorebi-update-") as tmp:
            tmp_dir = Path(tmp)
            tmp_tar = tmp_dir / "update.tar.gz"
            extract_dir = tmp_dir / "extracted"
            extract_dir.mkdir()

            self.progress.emit(10, tr("updater_prog_download_archive", tag=tag))
            self._download(archive_url, tmp_tar, 10, 45)

            # Verify integrity if checksum published
            self._verify_sha256(tmp_tar, f"{tag}.tar.gz")
            self._verify_sha256(tmp_tar, "update.tar.gz")

            self.progress.emit(58, tr("updater_prog_extract"))
            with tarfile.open(tmp_tar, "r:gz") as tar:
                try:
                    tar.extractall(path=extract_dir, filter="data")
                except TypeError:  # Python < 3.12 without extraction filters
                    root = extract_dir.resolve()
                    for m in tar.getmembers():
                        dest = (extract_dir / m.name).resolve()
                        if root not in dest.parents and dest != root:
                            raise RuntimeError(tr("updater_err_unsafe_path", path=m.name))
                        if m.issym() or m.islnk():
                            raise RuntimeError(tr("updater_err_symlink_denied", path=m.name))
                    tar.extractall(path=extract_dir)

            roots = [p for p in extract_dir.iterdir() if p.is_dir()]
            if len(roots) != 1:
                raise RuntimeError(tr("updater_err_archive_structure"))
            src_root = roots[0]

            init_file = src_root / "wallhaven" / "__init__.py"
            if not init_file.is_file() or not (src_root / "main.py").is_file():
                raise RuntimeError("Archiv neobsahuje platnou aplikaci Komorebi Desktop.")
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_file.read_text(encoding="utf-8"))
            archive_ver = m.group(1) if m else ""
            if not is_newer_version(archive_ver, self.info.current_version):
                raise RuntimeError(
                    tr("updater_err_archive_not_newer", archive_ver=archive_ver or '?', current=self.info.current_version)
                )

            # Install new Python dependencies BEFORE touching any app files,
            # so a pip failure leaves the current installation fully intact.
            venv_pip = target_dir / ".venv" / "bin" / "pip"
            new_req = src_root / "requirements.txt"
            if venv_pip.is_file() and new_req.is_file():
                self.progress.emit(65, tr("updater_prog_deps"))
                res = subprocess.run(
                    [str(venv_pip), "install", "-r", str(new_req), "--quiet"],
                    capture_output=True, text=True, timeout=600,
                )
                if res.returncode != 0:
                    tail = "\n".join((res.stderr or res.stdout).strip().splitlines()[-5:])
                    raise RuntimeError(tr("updater_err_deps_failed", tail=tail))

            self.progress.emit(80, tr("updater_prog_replace_files"))
            self._swap_in(src_root, target_dir)

        self.progress.emit(92, "Aktualizuji ikony...")
        try:
            icon_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "icons/hicolor/256x256/apps"
            src_icon = target_dir / "assets" / "icon.png"
            if src_icon.exists() and icon_dir.exists():
                for name in ("komorebi.png", "komorebi-desktop.png"):
                    shutil.copy2(src_icon, icon_dir / name)
        except Exception:
            pass  # cosmetic only

        self.progress.emit(100, tr("updater_prog_done"))
        self.apply_finished.emit(True, tr("updater_success_archive"))

    def _swap_in(self, src_root: Path, target_dir: Path):
        """Replace app files atomically-per-item; restore everything on any failure."""
        backup = target_dir / ".update-backup"
        if backup.exists():
            shutil.rmtree(backup)
        backup.mkdir(parents=True)

        touched: list[str] = []
        try:
            for name in self.UPDATE_ITEMS:
                src = src_root / name
                if not src.exists():
                    continue
                dst = target_dir / name
                if dst.exists() or dst.is_symlink():
                    os.replace(dst, backup / name)  # same filesystem -> atomic rename
                touched.append(name)
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        except Exception:
            for name in reversed(touched):
                dst = target_dir / name
                try:
                    self._remove_path(dst)
                except Exception:
                    pass
                if (backup / name).exists() or (backup / name).is_symlink():
                    os.replace(backup / name, dst)
            shutil.rmtree(backup, ignore_errors=True)
            raise

        shutil.rmtree(backup, ignore_errors=True)


def restart_application():
    """Restarts Komorebi Desktop in a detached process and exits the current one."""
    app = QApplication.instance()

    if getattr(sys, "frozen", False):
        cmd = [sys.executable] + sys.argv[1:]
    elif sys.argv and sys.argv[0].endswith("__main__.py"):
        cmd = [sys.executable, "-m", "wallhaven"] + sys.argv[1:]
    else:
        # Re-run exactly the same interpreter + entry script (works for the
        # ~/.local/share install, git checkouts and ad-hoc source copies).
        cmd = [sys.executable] + sys.argv

    try:
        if sys.platform == "win32":
            subprocess.Popen(cmd, close_fds=True)
        else:
            subprocess.Popen(cmd, start_new_session=True)
    except Exception as e:
        print(f"Failed to restart application: {e}")

    if app:
        app.quit()
    sys.exit(0)


class UpdateDialog(QDialog):
    """Modern glassmorphic modal dialog to view release notes and perform updates."""

    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.info = update_info
        self.apply_worker: UpdateApplyWorker | None = None
        self._downloaded_installer_path: str | None = None

        self.setWindowTitle(tr("update_title"))
        self.setMinimumWidth(560)
        self.setMaximumWidth(680)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        pal = get_palette(config.theme)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 22, 24, 22)

        # 1. Header Card with App Emblem and Version Badges
        header = QHBoxLayout()
        header.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(48, 48)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emblem_path = get_asset_path("icon_emblem.png")
        if not emblem_path.exists():
            emblem_path = get_asset_path("icon.png")
        if emblem_path.exists():
            pm = QPixmap(str(emblem_path)).scaled(
                38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            icon_lbl.setPixmap(pm)
        else:
            icon_lbl.setText("🌿")
            icon_lbl.setStyleSheet("font-size: 26px;")

        icon_lbl.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(234, 179, 8, 0.2), stop:1 rgba(99, 102, 241, 0.25));
            border: 1px solid rgba(234, 179, 8, 0.4);
            border-radius: 12px;
        """)
        header.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel(tr("update_title"))
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 900; color: #f8fafc;")
        title_box.addWidget(title_lbl)

        # Version progression row: v1.4.2 -> v2.0.0
        ver_row = QHBoxLayout()
        ver_row.setSpacing(8)

        cur_v = self.info.current_version
        new_v = self.info.latest_version or cur_v

        cur_badge = QLabel(f"v{cur_v}")
        cur_badge.setStyleSheet("""
            background: rgba(255, 255, 255, 0.08);
            color: #94a3b8;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
        """)
        ver_row.addWidget(cur_badge)

        if self.info.has_update:
            arrow_lbl = QLabel("➔")
            arrow_lbl.setStyleSheet("color: #6366f1; font-weight: 900; font-size: 12px;")
            ver_row.addWidget(arrow_lbl)

            new_badge = QLabel(f"{new_v}")
            new_badge.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
                color: #ffffff;
                font-size: 11px;
                font-weight: 800;
                padding: 2px 10px;
                border-radius: 6px;
            """)
            ver_row.addWidget(new_badge)

            status_text = QLabel(tr("update_available_status", version=new_v))
            status_text.setStyleSheet("color: #34d399; font-size: 11.5px; font-weight: 700;")
            ver_row.addWidget(status_text)
        else:
            status_text = QLabel(tr("update_latest_status", version=cur_v))
            status_text.setStyleSheet("color: #38bdf8; font-size: 11.5px; font-weight: 700;")
            ver_row.addWidget(status_text)

        ver_row.addStretch()
        title_box.addLayout(ver_row)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background-color: rgba(255, 255, 255, 0.08); max-height: 1px;")
        layout.addWidget(div)

        # 2. Release Notes / Changelog section
        notes_title = QLabel(tr("update_changelog_title", version=new_v))
        notes_title.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #cbd5e1;")
        layout.addWidget(notes_title)

        self.notes_box = QTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setMinimumHeight(170)
        self.notes_box.setStyleSheet("""
            QTextEdit {
                background-color: #0b0e14;
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                padding: 10px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 12px;
                line-height: 1.5;
            }
        """)

        # Clean markdown / release notes presentation
        notes_text = self.info.release_notes.strip() if self.info.release_notes else tr("updater_default_notes", release=self.info.release_name)
        self.notes_box.setMarkdown(notes_text)
        layout.addWidget(self.notes_box, 1)

        # 3. Progress Bar & Live Status Area (initially hidden)
        self.progress_container = QWidget()
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 4, 0, 4)
        prog_layout.setSpacing(6)

        self.status_lbl = QLabel(tr("update_downloading", percent=0))
        self.status_lbl.setStyleSheet("color: #a5b4fc; font-size: 12px; font-weight: 600;")
        prog_layout.addWidget(self.status_lbl)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedHeight(12)
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #06b6d4);
                border-radius: 6px;
            }
        """)
        prog_layout.addWidget(self.prog_bar)
        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)

        # 4. Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # GitHub button
        self.github_btn = QPushButton(tr("update_btn_github"))
        self.github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.github_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
                color: #ffffff;
            }
        """)
        self.github_btn.clicked.connect(self._open_github)
        btn_row.addWidget(self.github_btn)

        btn_row.addStretch()

        self.close_btn = QPushButton(tr("update_btn_later") if self.info.has_update else tr("update_btn_close"))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.close_btn)

        # Primary update button
        self.apply_btn = QPushButton(tr("update_btn_apply"))
        self.apply_btn.setObjectName("primaryButton")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setStyleSheet("""
            QPushButton#primaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 7px 18px;
                font-size: 12.5px;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
            }
            QPushButton#primaryButton:disabled {
                background: #334155;
                color: #64748b;
            }
        """)
        self.apply_btn.clicked.connect(self._start_update)
        # No "reinstall/force" path: installing a non-newer release would downgrade the app.
        self.apply_btn.setVisible(self.info.has_update)
        btn_row.addWidget(self.apply_btn)

        layout.addLayout(btn_row)

    def _is_installing(self) -> bool:
        return self.apply_worker is not None and self.apply_worker.isRunning()

    def reject(self):
        # Esc / window close must not abandon a running install.
        if self._is_installing():
            return
        super().reject()

    def _open_github(self):
        url = self.info.html_url or f"https://github.com/{GITHUB_REPO}/releases"
        QDesktopServices.openUrl(QUrl(url))

    def _start_update(self):
        if self._is_installing() or not self.info.has_update:
            return
        self.apply_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.github_btn.setEnabled(False)
        self.progress_container.setVisible(True)

        self.status_lbl.setText(tr("update_downloading", percent=0))
        self.status_lbl.setStyleSheet("color: #a5b4fc; font-size: 12px; font-weight: 600;")
        self.prog_bar.setValue(0)

        self.apply_worker = UpdateApplyWorker(self.info)
        self.apply_worker.progress.connect(self._on_progress)
        self.apply_worker.apply_finished.connect(self._on_finished)
        self.apply_worker.start()

    def _on_progress(self, pct: int, msg: str):
        self.prog_bar.setValue(pct)
        self.status_lbl.setText(msg)

    def _on_finished(self, success: bool, message: str):
        self.close_btn.setEnabled(True)
        self.github_btn.setEnabled(True)

        if success:
            self.prog_bar.setValue(100)
            self.status_lbl.setText(tr("update_success"))
            self.status_lbl.setStyleSheet("color: #34d399; font-size: 12px; font-weight: 700;")

            if sys.platform == "win32" and message.lower().endswith(".exe"):
                # Windows installer ready
                self._downloaded_installer_path = message
                self.apply_btn.setText(tr("updater_btn_run_installer"))
            else:
                self.apply_btn.setText(tr("update_btn_restart"))

            self.apply_btn.setEnabled(True)
            self.apply_btn.setStyleSheet("""
                QPushButton#primaryButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 7px 18px;
                    font-size: 12.5px;
                    font-weight: 800;
                }
                QPushButton#primaryButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
                }
            """)
            self.apply_btn.clicked.disconnect()
            self.apply_btn.clicked.connect(self._execute_restart)
        else:
            self.status_lbl.setText(tr("update_failed", error=message))
            self.status_lbl.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 700;")
            self.apply_btn.setEnabled(True)
            self.apply_btn.setText(tr("update_btn_apply"))

    def _execute_restart(self):
        if sys.platform == "win32" and self._downloaded_installer_path:
            try:
                subprocess.Popen([self._downloaded_installer_path])
            except Exception as e:
                print(f"Failed to launch Windows installer: {e}")
            app = QApplication.instance()
            if app:
                app.quit()
            sys.exit(0)
        else:
            restart_application()


class UpdateBanner(QFrame):
    """Modern floating glassmorphic banner shown at the top of the window when an update is available."""

    update_clicked = pyqtSignal(object)  # UpdateInfo
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.setFixedHeight(48)
        self.info: UpdateInfo | None = None

        self._init_ui()
        self.hide()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 14, 6)
        layout.setSpacing(12)

        icon_lbl = QLabel("✨")
        icon_lbl.setStyleSheet("font-size: 17px; background: transparent;")
        layout.addWidget(icon_lbl)

        self.text_lbl = QLabel("")
        self.text_lbl.setStyleSheet("""
            color: #f8fafc;
            font-size: 12.5px;
            font-weight: 700;
            background: transparent;
        """)
        layout.addWidget(self.text_lbl, 1)

        self.action_btn = QPushButton(tr("update_banner_apply"))
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 5px 14px;
                font-size: 11.5px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #6d28d9);
            }
        """)
        self.action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("updateBannerCloseBtn")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton#updateBannerCloseBtn {
                background-color: rgba(255, 255, 255, 0.1);
                color: #e2e8f0;
                border: none;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
                margin: 0px;
            }
            QPushButton#updateBannerCloseBtn:hover {
                background-color: rgba(239, 68, 68, 0.4);
                color: #ffffff;
            }
        """)
        self.close_btn.clicked.connect(self.hide_banner)
        layout.addWidget(self.close_btn)

        # Style frame
        self.setStyleSheet("""
            QFrame#updateBanner {
                background-color: rgba(15, 23, 42, 0.95);
                border: 1px solid rgba(99, 102, 241, 0.4);
                border-radius: 10px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.setGraphicsEffect(shadow)

    def show_update(self, info: UpdateInfo):
        self.info = info
        clean_text = tr("update_banner_text", version=info.latest_version).lstrip("✨").strip()
        self.text_lbl.setText(clean_text)
        self.action_btn.setText(tr("update_banner_apply"))
        self.show()

    def hide_banner(self):
        self.hide()
        self.dismissed.emit()

    def _on_action_clicked(self):
        if self.info:
            self.update_clicked.emit(self.info)
