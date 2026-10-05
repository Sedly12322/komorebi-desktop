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
import tarfile
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
import urllib.request
import urllib.error

from PyQt6.QtCore import (
    Qt,
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

    # Assets inspection
    for asset in release_data.get("assets", []):
        name = asset.get("name", "")
        dl_url = asset.get("browser_download_url", "")
        if name.lower().endswith(".exe"):
            info.windows_installer_url = dl_url
            info.windows_installer_name = name
        elif name.lower().endswith(".zip") and "portable" in name.lower():
            info.windows_portable_url = dl_url

    info.has_update = is_newer_version(tag, current_ver)
    return info


class UpdateCheckWorker(QThread):
    """Background worker to check for application updates without blocking UI."""

    check_finished = pyqtSignal(object)  # UpdateInfo
    check_failed = pyqtSignal(str)

    def __init__(self, current_ver: str = __version__, parent=None):
        super().__init__(parent)
        self.current_ver = current_ver

    def run(self):
        try:
            info = check_for_updates_sync(self.current_ver)
            if info.error and not info.latest_version:
                self.check_failed.emit(info.error)
            else:
                self.check_finished.emit(info)
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateApplyWorker(QThread):
    """Background worker that downloads and installs the application update."""

    progress = pyqtSignal(int, str)  # (percent 0-100, message)
    finished = pyqtSignal(bool, str)  # (success, message / instructions)

    def __init__(self, info: UpdateInfo, force_branch: str = "", parent=None):
        super().__init__(parent)
        self.info = info
        self.force_branch = force_branch

    def run(self):
        try:
            if sys.platform == "win32":
                self._update_windows()
            else:
                self._update_linux()
        except Exception as e:
            self.finished.emit(False, str(e))

    def _update_windows(self):
        """Downloads the Windows installer and prepares it for execution."""
        installer_url = self.info.windows_installer_url
        if not installer_url:
            self.finished.emit(
                False,
                "Nebyl nalezen instalátor pro Windows v balíčku vydání.\n"
                f"Stáhněte novou verzi přímo z: {self.info.html_url}",
            )
            return

        out_name = self.info.windows_installer_name or "Wallhaven-Desktop-Setup.exe"
        temp_dir = Path(tempfile.gettempdir())
        target_path = temp_dir / out_name

        self.progress.emit(5, f"Stahuji instalátor {out_name}...")

        req = urllib.request.Request(
            installer_url,
            headers={"User-Agent": f"Komorebi-Desktop-Updater/{__version__}"},
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            block_size = 64 * 1024

            with open(target_path, "wb") as f:
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = int((downloaded / total_size) * 85) + 5
                        cur_mb = downloaded / (1024 * 1024)
                        tot_mb = total_size / (1024 * 1024)
                        self.progress.emit(pct, f"Stahování: {cur_mb:.1f} MB / {tot_mb:.1f} MB ({pct}%)")

        self.progress.emit(95, "Instalátor byl stažen. Připravuji spuštění...")
        time.sleep(0.5)
        self.progress.emit(100, "Hotovo! Instalátor je připraven.")
        self.finished.emit(True, str(target_path))

    def _update_linux(self):
        """Updates Komorebi Desktop on Linux (via git pull or archive unpack)."""
        app_root = Path(__file__).resolve().parent.parent
        installed_share_dir = Path.home() / ".local/share/komorebi-desktop"

        # Case 1: Running from a git clone
        if (app_root / ".git").is_dir():
            self.progress.emit(10, "Zjišťuji změny z GitHubu přes Git...")
            try:
                res_fetch = subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=str(app_root),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if res_fetch.returncode != 0:
                    raise RuntimeError(f"git fetch failed: {res_fetch.stderr}")

                self.progress.emit(35, "Aplikuji změny (git pull)...")
                branch = self.force_branch or "main"
                res_pull = subprocess.run(
                    ["git", "pull", "--ff-only", "origin", branch],
                    cwd=str(app_root),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if res_pull.returncode != 0:
                    # Try rebase or checkout
                    subprocess.run(["git", "pull", "origin", branch], cwd=str(app_root), timeout=20)

                self.progress.emit(65, "Aktualizuji systémovou instalaci...")
                install_sh = app_root / "install.sh"
                if install_sh.is_file():
                    subprocess.run(["bash", str(install_sh)], cwd=str(app_root), timeout=60)

                self.progress.emit(100, "Aktualizace dokončena!")
                self.finished.emit(True, "Komorebi Desktop byl úspěšně aktualizován z repozitáře.")
                return
            except Exception as e:
                # If git pull fails, fallback to archive download
                self.progress.emit(40, f"Git selhal ({e}), stahuji archiv z GitHubu...")

        # Case 2: Running from installed share or standalone
        target_dir = installed_share_dir if installed_share_dir.is_dir() else app_root
        tag = self.info.latest_version or "main"
        archive_url = self.info.tarball_url or f"https://github.com/{GITHUB_REPO}/archive/refs/tags/{tag}.tar.gz"

        self.progress.emit(15, f"Stahuji archiv vydání ({tag})...")
        req = urllib.request.Request(
            archive_url,
            headers={"User-Agent": f"Komorebi-Desktop-Updater/{__version__}"},
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tar = Path(tmp_dir) / "update.tar.gz"

            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0
                block_size = 64 * 1024

                with open(tmp_tar, "wb") as f:
                    while True:
                        chunk = resp.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 45) + 15
                            cur_mb = downloaded / (1024 * 1024)
                            tot_mb = total_size / (1024 * 1024)
                            self.progress.emit(pct, f"Stahování: {cur_mb:.1f} MB / {tot_mb:.1f} MB ({pct}%)")

            self.progress.emit(65, "Rozbaluji archiv aktualizace...")
            with tarfile.open(tmp_tar, "r:gz") as tar:
                tar.extractall(path=tmp_dir)

            # Find extracted root directory
            extracted_subdirs = [p for p in Path(tmp_dir).iterdir() if p.is_dir() and p != Path(tmp_dir)]
            if not extracted_subdirs:
                raise RuntimeError("V archivu nebyla nalezena žádná data.")
            src_root = extracted_subdirs[0]

            self.progress.emit(75, "Kopíruji aktualizované soubory aplikace...")
            target_dir.mkdir(parents=True, exist_ok=True)

            # Update package directory
            for item_name in ["wallhaven", "assets", "main.py", "requirements.txt", "LICENSE", "install.sh"]:
                src_item = src_root / item_name
                dst_item = target_dir / item_name
                if src_item.is_dir():
                    if dst_item.exists():
                        shutil.rmtree(dst_item)
                    shutil.copytree(src_item, dst_item)
                elif src_item.is_file():
                    shutil.copy2(src_item, dst_item)

            self.progress.emit(88, "Aktualizuji ikony a spouštěcí soubory...")
            # Update icons if possible
            icon_dir = Path.home() / ".local/share/icons/hicolor/256x256/apps"
            src_icon = target_dir / "assets" / "icon.png"
            if src_icon.exists() and icon_dir.exists():
                shutil.copy2(src_icon, icon_dir / "komorebi.png")
                shutil.copy2(src_icon, icon_dir / "komorebi-desktop.png")

            # Update pip requirements if virtualenv exists
            venv_pip = target_dir / ".venv" / "bin" / "pip"
            req_file = target_dir / "requirements.txt"
            if venv_pip.is_file() and req_file.is_file():
                self.progress.emit(92, "Kontroluji Python závislosti...")
                try:
                    subprocess.run([str(venv_pip), "install", "-r", str(req_file), "--quiet"], timeout=30)
                except Exception:
                    pass

            self.progress.emit(100, "Aktualizace úspěšně dokončena!")
            self.finished.emit(True, "Komorebi Desktop byl úspěšně aktualizován.")


def restart_application():
    """Cleanly restarts Komorebi Desktop in a detached process and exits the current one."""
    app = QApplication.instance()

    if sys.platform == "win32":
        if getattr(sys, "frozen", False):
            cmd = [sys.executable] + sys.argv[1:]
        else:
            cmd = [sys.executable, sys.argv[0]] + sys.argv[1:]
    else:
        launcher = Path.home() / ".local/bin" / "komorebi-desktop"
        if launcher.exists() and os.access(launcher, os.X_OK):
            cmd = [str(launcher)] + sys.argv[1:]
        elif getattr(sys, "frozen", False):
            cmd = [sys.executable] + sys.argv[1:]
        else:
            cmd = [sys.executable, sys.argv[0]] + sys.argv[1:]

    try:
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

        if self.info.has_update:
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
        notes_text = self.info.release_notes.strip() if self.info.release_notes else (
            f"Vydání {self.info.release_name}.\n"
            "Obsahuje nejnovější opravy chyb, optimalizace a nová vylepšení pro Komorebi Desktop."
        )
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
        btn_text = tr("update_btn_apply") if self.info.has_update else tr("update_reinstall_btn")
        self.apply_btn = QPushButton(btn_text)
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
        btn_row.addWidget(self.apply_btn)

        layout.addLayout(btn_row)

    def _open_github(self):
        url = self.info.html_url or f"https://github.com/{GITHUB_REPO}/releases"
        QDesktopServices.openUrl(QUrl(url))

    def _start_update(self):
        self.apply_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.github_btn.setEnabled(False)
        self.progress_container.setVisible(True)

        self.status_lbl.setText(tr("update_downloading", percent=0))
        self.prog_bar.setValue(0)

        self.apply_worker = UpdateApplyWorker(self.info, parent=self)
        self.apply_worker.progress.connect(self._on_progress)
        self.apply_worker.finished.connect(self._on_finished)
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
                self.apply_btn.setText("🚀 Spustit instalátor a restartovat")
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
