import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".flv", ".wmv"}


def is_video_file(file_path: str) -> bool:
    """Checks if a file has a video extension."""
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS


def find_quickshell_entry() -> Optional[str]:
    """Finds the active or installed quickshell shell.qml entrypoint."""
    # 1. Check running quickshell process with -p
    try:
        res = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=2)
        m = re.search(r"quickshell\s+.*?-p\s+([^\s]+)", res.stdout)
        if m:
            p = Path(m.group(1)).expanduser().resolve()
            if p.exists():
                return str(p)
    except Exception:
        pass

    # 2. Check well-known quickshell paths
    candidates = [
        Path.home() / ".local/share/serpantinum/src/quickshell/Shell.qml",
        Path.home() / ".config/quickshell/shell.qml",
        Path.home() / ".config/quickshell/Shell.qml",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def get_available_wallpaper_setters() -> list[dict]:
    """
    Returns a list of wallpaper setters with their availability and capabilities.
    Each item contains: id, name, available (bool), supports_video (bool), description, default_cmd
    """
    setters = []

    # 0. Hyprland Rice Script (set-wallpaper.sh)
    hypr_script = Path.home() / ".config/hypr/scripts/set-wallpaper.sh"
    has_hypr_script = hypr_script.exists() and os.access(hypr_script, os.X_OK)
    setters.append({
        "id": "hyprland_script",
        "name": "Hyprland Rice (set-wallpaper.sh)",
        "available": has_hypr_script,
        "supports_video": False,
        "description": "Nativní skript profilu s automatickým Matugen & Quickshell přebarvením",
        "default_cmd": f"bash {hypr_script} '{{file}}'",
    })

    # 0b. awww (Modern Wayland wallpaper daemon)
    has_awww = shutil.which("awww") is not None
    setters.append({
        "id": "awww",
        "name": "awww (Wayland)",
        "available": has_awww,
        "supports_video": False,
        "description": "Moderní Wayland wallpaper démon s animovanými přechody",
        "default_cmd": "awww img '{file}' --transition-type fade --transition-duration 1",
    })

    # 1. Quickshell (Serpantinum / Hyprland / Wayland)
    qs_entry = find_quickshell_entry()
    qs_script = Path.home() / ".config/quickshell/ii/scripts/colors/switchwall.sh"
    has_qs = (shutil.which("qs") is not None and qs_entry is not None) or (qs_script.exists() and os.access(qs_script, os.X_OK))
    setters.append({
        "id": "quickshell",
        "name": "Quickshell (Serpantinum / Hyprland)",
        "available": has_qs,
        "supports_video": True,
        "description": "Nativní podpora statických i video (.mp4) tapet přes Quickshell IPC",
        "default_cmd": f'qs ipc -p "{qs_entry}" call wallpaper setWallpaper "all" "{{file}}" "fade"' if qs_entry else 'qs ipc call wallpaper setWallpaper "all" "{file}" "fade"',
    })

    # 2. mpvpaper (Wayland video wallpaper engine)
    has_mpvpaper = shutil.which("mpvpaper") is not None
    setters.append({
        "id": "mpvpaper",
        "name": "mpvpaper (Wayland Live/Video)",
        "available": has_mpvpaper,
        "supports_video": True,
        "description": "Přehrávání animovaných video tapet pro Wayland (Hyprland/Sway)",
        "default_cmd": "pkill mpvpaper 2>/dev/null; mpvpaper -vs -o 'no-audio --loop' '*' '{file}' &",
    })

    # 3. swww (Wayland animated & static)
    has_swww = shutil.which("swww") is not None
    setters.append({
        "id": "swww",
        "name": "swww (Wayland)",
        "available": has_swww,
        "supports_video": False,  # swww supports gif/apng, but not direct mp4/webm
        "description": "Rychlý Wayland wallpaper démon s plynulými přechody",
        "default_cmd": "swww img --transition-type grow '{file}'",
    })

    # 4. hyprpaper (Hyprland)
    has_hyprpaper = shutil.which("hyprpaper") is not None and shutil.which("hyprctl") is not None
    setters.append({
        "id": "hyprpaper",
        "name": "hyprpaper (Hyprland)",
        "available": has_hyprpaper,
        "supports_video": False,
        "description": "Oficiální Hyprland wallpaper nástroj",
        "default_cmd": "hyprctl hyprpaper preload '{file}' && hyprctl hyprpaper wallpaper ',{file}'",
    })

    # 5. waypaper (GUI/CLI Wayland)
    has_waypaper = shutil.which("waypaper") is not None
    setters.append({
        "id": "waypaper",
        "name": "waypaper (Wayland)",
        "available": has_waypaper,
        "supports_video": False,
        "description": "Univerzální frontend pro Wayland tapety",
        "default_cmd": "waypaper --wallpaper '{file}'",
    })

    # 6. swaybg (Wayland / wlroots)
    has_swaybg = shutil.which("swaybg") is not None
    setters.append({
        "id": "swaybg",
        "name": "swaybg (Wayland / Sway)",
        "available": has_swaybg,
        "supports_video": False,
        "description": "Lehký wallpaper nástroj pro wlroots compository",
        "default_cmd": "pkill swaybg 2>/dev/null; swaybg -i '{file}' -m fill &",
    })

    # 7. KDE Plasma (5 / 6)
    has_plasma = (
        shutil.which("plasma-apply-wallpaperimage") is not None
        or shutil.which("kwriteconfig6") is not None
        or shutil.which("kwriteconfig5") is not None
    )
    setters.append({
        "id": "plasma",
        "name": "KDE Plasma (plasma-apply-wallpaperimage)",
        "available": has_plasma,
        "supports_video": False,
        "description": "Standardní nástroj prostředí KDE Plasma",
        "default_cmd": "plasma-apply-wallpaperimage '{file}'",
    })

    # 8. GNOME Desktop (gsettings light & dark)
    has_gnome = shutil.which("gsettings") is not None and ("GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "") or os.environ.get("GDMSESSION") == "gnome")
    setters.append({
        "id": "gnome",
        "name": "GNOME (gsettings)",
        "available": has_gnome or shutil.which("gsettings") is not None,
        "supports_video": False,
        "description": "Nastavení tapety pro světlý i tmavý režim v prostředí GNOME",
        "default_cmd": "gsettings set org.gnome.desktop.background picture-uri 'file://{file}' && gsettings set org.gnome.desktop.background picture-uri-dark 'file://{file}'",
    })

    # 9. Cinnamon
    has_cinnamon = shutil.which("gsettings") is not None and "Cinnamon" in os.environ.get("XDG_CURRENT_DESKTOP", "")
    setters.append({
        "id": "cinnamon",
        "name": "Cinnamon (gsettings)",
        "available": has_cinnamon,
        "supports_video": False,
        "description": "Prostředí Cinnamon Desktop",
        "default_cmd": "gsettings set org.cinnamon.desktop.background picture-uri 'file://{file}'",
    })

    # 10. MATE
    has_mate = shutil.which("gsettings") is not None and "MATE" in os.environ.get("XDG_CURRENT_DESKTOP", "")
    setters.append({
        "id": "mate",
        "name": "MATE (gsettings)",
        "available": has_mate,
        "supports_video": False,
        "description": "Prostředí MATE Desktop",
        "default_cmd": "gsettings set org.mate.background picture-filename '{file}'",
    })

    # 11. XFCE
    has_xfce = shutil.which("xfconf-query") is not None
    setters.append({
        "id": "xfce",
        "name": "XFCE (xfconf-query)",
        "available": has_xfce,
        "supports_video": False,
        "description": "Prostředí XFCE 4",
        "default_cmd": 'xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/workspace0/last-image -s "{file}"',
    })

    # 12. feh (X11)
    has_feh = shutil.which("feh") is not None
    setters.append({
        "id": "feh",
        "name": "feh (X11)",
        "available": has_feh,
        "supports_video": False,
        "description": "Rychlý a populární wallpaper setter pro X11 (i3, bspwm, openbox)",
        "default_cmd": "feh --bg-fill '{file}'",
    })

    # 13. nitrogen (X11)
    has_nitrogen = shutil.which("nitrogen") is not None
    setters.append({
        "id": "nitrogen",
        "name": "nitrogen (X11)",
        "available": has_nitrogen,
        "supports_video": False,
        "description": "Grafický i CLI správce tapet pro X11",
        "default_cmd": "nitrogen --set-zoom-fill '{file}' --save",
    })

    # 14. xwinwrap + mpv (X11 video)
    has_xwinwrap = shutil.which("xwinwrap") is not None and shutil.which("mpv") is not None
    setters.append({
        "id": "xwinwrap",
        "name": "xwinwrap + mpv (X11 Live/Video)",
        "available": has_xwinwrap,
        "supports_video": True,
        "description": "Přehrávání video tapet na pozadí v X11",
        "default_cmd": "pkill -f 'mpv.*--wid' 2>/dev/null; xwinwrap -ov -fs -- mpv -wid WID --loop --no-audio '{file}' &",
    })

    return setters


def detect_wallpaper_command(for_video: bool = False) -> list[str]:
    """
    Detects the best wallpaper setter command for the current environment.
    If for_video is True, prioritizes tools capable of playing video wallpapers.
    """
    if sys.platform == "win32":
        if for_video:
            if shutil.which("lively") or shutil.which("Lively"):
                return ["lively", "setwp", "--file", "{file}"]
            return []
        return ["Nativní Windows API (SystemParametersInfoW)"]

    qs_entry = find_quickshell_entry()
    qs_script = Path.home() / ".config/quickshell/ii/scripts/colors/switchwall.sh"

    if for_video:
        # 1. Quickshell natively supports video wallpapers!
        if shutil.which("qs") and qs_entry:
            return ["qs", "ipc", "-p", qs_entry, "call", "wallpaper", "setWallpaper", "all", "{file}", "fade"]

        # 2. mpvpaper on Wayland
        if shutil.which("mpvpaper"):
            return ["mpvpaper", "-vs", "-o", "no-audio --loop", "*", "{file}"]

        # 3. xwinwrap + mpv on X11
        if shutil.which("xwinwrap") and shutil.which("mpv"):
            return ["xwinwrap", "-ov", "-fs", "--", "mpv", "-wid", "WID", "--loop", "--no-audio", "{file}"]

        return []

    # Static wallpaper detection
    # 0. Hyprland Rice Script (set-wallpaper.sh)
    hypr_script = Path.home() / ".config/hypr/scripts/set-wallpaper.sh"
    if hypr_script.exists() and os.access(hypr_script, os.X_OK):
        return ["bash", str(hypr_script), "{file}"]

    # 0b. awww (Modern Wayland wallpaper daemon)
    if shutil.which("awww"):
        return ["awww", "img", "{file}", "--transition-type", "fade", "--transition-duration", "1"]

    # 1. Quickshell
    if shutil.which("qs") and qs_entry:
        return ["qs", "ipc", "-p", qs_entry, "call", "wallpaper", "setWallpaper", "all", "{file}", "fade"]
    if qs_script.exists() and os.access(qs_script, os.X_OK):
        return [str(qs_script), "--image", "{file}"]

    # 2. swww
    if shutil.which("swww"):
        return ["swww", "img", "--transition-type", "grow", "{file}"]

    # 3. waypaper
    if shutil.which("waypaper"):
        return ["waypaper", "--wallpaper", "{file}"]

    # 4. hyprpaper
    if shutil.which("hyprpaper") and shutil.which("hyprctl"):
        return ["hyprctl", "hyprpaper", "wallpaper", ",{file}"]

    # 5. swaybg
    if shutil.which("swaybg"):
        return ["swaybg", "-i", "{file}", "-m", "fill"]

    # 6. KDE Plasma
    if shutil.which("plasma-apply-wallpaperimage"):
        return ["plasma-apply-wallpaperimage", "{file}"]

    # 7. GNOME
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if shutil.which("gsettings") and ("GNOME" in desktop or "gnome" in os.environ.get("GDMSESSION", "")):
        return ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", "file://{file}"]

    # 8. Cinnamon
    if shutil.which("gsettings") and "Cinnamon" in desktop:
        return ["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", "file://{file}"]

    # 9. MATE
    if shutil.which("gsettings") and "MATE" in desktop:
        return ["gsettings", "set", "org.mate.background", "picture-filename", "{file}"]

    # 10. feh
    if shutil.which("feh"):
        return ["feh", "--bg-fill", "{file}"]

    # 11. nitrogen
    if shutil.which("nitrogen"):
        return ["nitrogen", "--set-zoom-fill", "{file}"]

    # Fallback to gsettings if available
    if shutil.which("gsettings"):
        return ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", "file://{file}"]

    return []


def trigger_matugen_refresh(abs_path: str):
    """Triggers Matugen palette regeneration and desktop color reload on Linux."""
    if sys.platform == "win32":
        return

    matugen_bin = shutil.which("matugen") or ("/usr/bin/matugen" if os.path.exists("/usr/bin/matugen") else None)

    # Save active wallpaper to user cache so rice / widgets can read it
    try:
        rice_cache = Path.home() / ".cache/sedly-rice"
        rice_cache.mkdir(parents=True, exist_ok=True)
        (rice_cache / "current_wallpaper").write_text(abs_path, encoding="utf-8")
        (Path.home() / ".cache/current_wallpaper").write_text(abs_path, encoding="utf-8")
    except Exception:
        pass

    try:
        target_img = abs_path
        if is_video_file(abs_path):
            # Extract 1 frame from video using ffmpeg
            frame_cache = Path("/tmp/wallhaven_matugen_frame.jpg")
            if shutil.which("ffmpeg"):
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", "00:00:01", "-i", abs_path, "-vframes", "1", str(frame_cache)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                if frame_cache.exists() and frame_cache.stat().st_size > 0:
                    target_img = str(frame_cache)
                else:
                    return
            else:
                return

        # 1. Matugen CLI invocation (with config if found, otherwise generic)
        user_cfg = Path.home() / ".config/matugen/config.toml"
        serp_cfg = Path.home() / ".local/share/serpantinum/src/assets/matugen/config.toml"
        cfg_to_use = user_cfg if user_cfg.exists() else (serp_cfg if serp_cfg.exists() else None)

        if matugen_bin:
            cmd = [matugen_bin]
            if cfg_to_use:
                cmd.extend(["-c", str(cfg_to_use)])
            cmd.extend(["image", target_img, "-m", "dark", "--source-color-index", "0"])
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Quickshell IPC calls
        qs_entry = find_quickshell_entry()
        if shutil.which("qs"):
            # Sedly-Rice reload
            cmd_reload = ["qs", "ipc"]
            if qs_entry:
                cmd_reload.extend(["-p", qs_entry])
            cmd_reload.extend(["call", "theme", "reload"])
            subprocess.Popen(cmd_reload, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Serpantinum reloadColors
            cmd_colors = ["qs", "ipc"]
            if qs_entry:
                cmd_colors.extend(["-p", qs_entry])
            cmd_colors.extend(["call", "theme", "reloadColors"])
            subprocess.Popen(cmd_colors, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Matugen IPC if defined
            cmd_mat = ["qs", "ipc"]
            if qs_entry:
                cmd_mat.extend(["-p", qs_entry])
            cmd_mat.extend(["call", "matugen", "generateImage", target_img])
            subprocess.Popen(cmd_mat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Trigger reload script if present
        reload_sh = Path.home() / ".local/share/serpantinum/src/scripts/wallpaper/matugen_reload.sh"
        if reload_sh.exists():
            subprocess.Popen(["bash", str(reload_sh)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 4. Reload Hyprland if active
        if shutil.which("hyprctl"):
            subprocess.Popen(["hyprctl", "reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    except Exception as e:
        print(f"[Matugen] Trigger error: {e}")


def set_desktop_wallpaper(
    file_path: str,
    custom_cmd: str = "",
    setter_id: str = "auto",
    custom_video_cmd: str = "",
) -> Tuple[bool, str]:
    """
    Sets the downloaded wallpaper on the desktop and triggers Matugen palette update.
    Supports both static images and animated video wallpapers (.mp4, .webm).
    Returns (success: bool, message: str).
    """
    success, msg = _set_desktop_wallpaper_impl(file_path, custom_cmd, setter_id, custom_video_cmd)
    if success:
        try:
            trigger_matugen_refresh(str(Path(file_path).resolve()))
        except Exception:
            pass
    return success, msg


def _set_desktop_wallpaper_impl(
    file_path: str,
    custom_cmd: str = "",
    setter_id: str = "auto",
    custom_video_cmd: str = "",
) -> Tuple[bool, str]:
    """
    Sets the downloaded wallpaper on the desktop.
    Supports both static images and animated video wallpapers (.mp4, .webm).
    Returns (success: bool, message: str).
    """
    if not os.path.exists(file_path):
        return False, f"Soubor neexistuje: {file_path}"

    abs_path = str(Path(file_path).resolve())
    is_video = is_video_file(abs_path)

    # 1. Custom video command specified and file is video
    if is_video and custom_video_cmd.strip():
        cmd_str = custom_video_cmd.replace("{file}", f'"{abs_path}"')
        return _run_shell_cmd(cmd_str, abs_path)

    # 2. General custom command specified
    if custom_cmd.strip() and (setter_id == "custom" or setter_id == "vlastni"):
        cmd_str = custom_cmd.replace("{file}", f'"{abs_path}"')
        return _run_shell_cmd(cmd_str, abs_path)

    # 3. Windows Native API (for static images)
    if sys.platform == "win32":
        if is_video:
            if shutil.which("lively"):
                return _run_shell_cmd(f'lively setwp --file "{abs_path}"', abs_path)
            return False, "Pro animované tapety ve Windows nainstalujte aplikaci Lively Wallpaper."
        try:
            import ctypes
            SPI_SETDESKWALLPAPER = 20
            SPIF_UPDATEINIFILE = 0x01
            SPIF_SENDCHANGE = 0x02
            res = ctypes.windll.user32.SystemParametersInfoW(
                SPI_SETDESKWALLPAPER,
                0,
                abs_path,
                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
            )
            if res:
                return True, "Tapeta byla úspěšně nastavena."
            return False, "Volání Windows API (SystemParametersInfoW) selhalo."
        except Exception as e:
            return False, str(e)

    # 4. Explicit setter selected
    if setter_id and setter_id not in ("auto", "automaticky", "custom", "vlastni"):
        return _apply_specific_setter(setter_id, abs_path, is_video)

    # 5. Linux Automatic Detection
    if is_video:
        cmd_template = detect_wallpaper_command(for_video=True)
        if not cmd_template:
            # Fallback warning
            return (
                False,
                "Detekována animovaná tapeta (.mp4), ale nebyl nalezen žádný přehrávač živých tapet "
                "(např. Quickshell, mpvpaper). Pro Wayland nainstalujte: 'yay -S mpvpaper'.",
            )
    else:
        cmd_template = detect_wallpaper_command(for_video=False)
        if not cmd_template:
            return False, "Nebyl nalezen žádný podporovaný nástroj pro nastavení tapety."

    # If using hyprpaper, preload first
    if len(cmd_template) > 0 and "hyprpaper" in cmd_template[0]:
        try:
            subprocess.run(
                ["hyprctl", "hyprpaper", "preload", abs_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            pass

    # If GNOME, set both light and dark
    if len(cmd_template) > 2 and cmd_template[0] == "gsettings" and "org.gnome.desktop.background" in cmd_template:
        try:
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{abs_path}"], timeout=5)
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", f"file://{abs_path}"], timeout=5)
            _send_notification("Tapeta změněna", f"Tapeta byla nastavena na: {os.path.basename(abs_path)}")
            return True, "Tapeta byla úspěšně nastavena."
        except Exception as e:
            return False, str(e)

    cmd = [arg.replace("{file}", abs_path) for arg in cmd_template]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )
        if res.returncode == 0:
            _send_notification("Tapeta změněna", f"Tapeta byla nastavena na: {os.path.basename(abs_path)}")
            return True, "Tapeta byla úspěšně nastavena."
        return False, f"Příkaz selhal: {res.stderr.strip()}"
    except Exception as e:
        return False, str(e)


def _apply_specific_setter(setter_id: str, abs_path: str, is_video: bool) -> Tuple[bool, str]:
    """Applies a user-chosen wallpaper setter."""
    if setter_id == "quickshell":
        qs_entry = find_quickshell_entry()
        if not qs_entry:
            return False, "Quickshell nebyl v systému nalezen."
        cmd = ["qs", "ipc", "-p", qs_entry, "call", "wallpaper", "setWallpaper", "all", abs_path, "fade"]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if res.returncode == 0:
                _send_notification("Tapeta změněna", f"Quickshell nastavil tapetu: {os.path.basename(abs_path)}")
                return True, "Tapeta byla úspěšně nastavena přes Quickshell."
            return False, f"Quickshell IPC selhal: {res.stderr.strip()}"
        except Exception as e:
            return False, str(e)

    elif setter_id == "mpvpaper":
        if not shutil.which("mpvpaper"):
            return False, "Nástroj 'mpvpaper' není nainstalován. Nainstalujte jej např. příkazem 'yay -S mpvpaper'."
        cmd_str = f"pkill mpvpaper 2>/dev/null; mpvpaper -vs -o 'no-audio --loop' '*' '{abs_path}' &"
        return _run_shell_cmd(cmd_str, abs_path)

    elif setter_id == "hyprpaper":
        if not shutil.which("hyprpaper") or not shutil.which("hyprctl"):
            return False, "Nástroj 'hyprpaper' nebo 'hyprctl' není nainstalován."
        subprocess.run(["hyprctl", "hyprpaper", "preload", abs_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = ["hyprctl", "hyprpaper", "wallpaper", f",{abs_path}"]
        return _run_cmd_list(cmd, abs_path)

    elif setter_id == "swww":
        if not shutil.which("swww"):
            return False, "Nástroj 'swww' není nainstalován."
        cmd = ["swww", "img", "--transition-type", "grow", abs_path]
        return _run_cmd_list(cmd, abs_path)

    elif setter_id == "swaybg":
        if not shutil.which("swaybg"):
            return False, "Nástroj 'swaybg' není nainstalován."
        cmd_str = f"pkill swaybg 2>/dev/null; swaybg -i '{abs_path}' -m fill &"
        return _run_shell_cmd(cmd_str, abs_path)

    elif setter_id == "waypaper":
        if not shutil.which("waypaper"):
            return False, "Nástroj 'waypaper' není nainstalován."
        cmd = ["waypaper", "--wallpaper", abs_path]
        return _run_cmd_list(cmd, abs_path)

    elif setter_id == "plasma":
        if shutil.which("plasma-apply-wallpaperimage"):
            cmd = ["plasma-apply-wallpaperimage", abs_path]
            return _run_cmd_list(cmd, abs_path)
        return False, "Nástroj 'plasma-apply-wallpaperimage' nebyl nalezen."

    elif setter_id == "gnome":
        if not shutil.which("gsettings"):
            return False, "Příkaz 'gsettings' není k dispozici."
        try:
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{abs_path}"], timeout=5)
            subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", f"file://{abs_path}"], timeout=5)
            _send_notification("Tapeta změněna", f"Tapeta byla nastavena na: {os.path.basename(abs_path)}")
            return True, "Tapeta byla úspěšně nastavena pro GNOME."
        except Exception as e:
            return False, str(e)

    elif setter_id == "cinnamon":
        cmd = ["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", f"file://{abs_path}"]
        return _run_cmd_list(cmd, abs_path)

    elif setter_id == "mate":
        cmd = ["gsettings", "set", "org.mate.background", "picture-filename", abs_path]
        return _run_cmd_list(cmd, abs_path)

    elif setter_id == "xfce":
        cmd_str = f'xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/workspace0/last-image -s "{abs_path}"'
        return _run_shell_cmd(cmd_str, abs_path)

    elif setter_id == "feh":
        if not shutil.which("feh"):
            return False, "Nástroj 'feh' není nainstalován."
        cmd = ["feh", "--bg-fill", abs_path]
        return _run_cmd_list(cmd, abs_path)

    elif setter_id == "nitrogen":
        if not shutil.which("nitrogen"):
            return False, "Nástroj 'nitrogen' není nainstalován."
        cmd = ["nitrogen", "--set-zoom-fill", abs_path, "--save"]
        return _run_cmd_list(cmd, abs_path)

    elif setter_id == "xwinwrap":
        if not shutil.which("xwinwrap") or not shutil.which("mpv"):
            return False, "Nástroje 'xwinwrap' nebo 'mpv' nejsou nainstalovány."
        cmd_str = f"pkill -f 'mpv.*--wid' 2>/dev/null; xwinwrap -ov -fs -- mpv -wid WID --loop --no-audio '{abs_path}' &"
        return _run_shell_cmd(cmd_str, abs_path)

    return False, f"Neznámý setter: {setter_id}"


def _run_shell_cmd(cmd_str: str, abs_path: str) -> Tuple[bool, str]:
    try:
        res = subprocess.run(
            cmd_str,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        if res.returncode == 0:
            _send_notification("Tapeta změněna", f"Tapeta byla nastavena na: {os.path.basename(abs_path)}")
            return True, "Tapeta byla úspěšně nastavena."
        return False, f"Příkaz selhal ({res.returncode}): {res.stderr.strip()}"
    except Exception as e:
        return False, str(e)


def _run_cmd_list(cmd: list[str], abs_path: str) -> Tuple[bool, str]:
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        if res.returncode == 0:
            _send_notification("Tapeta změněna", f"Tapeta byla nastavena na: {os.path.basename(abs_path)}")
            return True, "Tapeta byla úspěšně nastavena."
        return False, f"Příkaz selhal ({res.returncode}): {res.stderr.strip()}"
    except Exception as e:
        return False, str(e)


def _send_notification(title: str, msg: str):
    if sys.platform != "win32" and shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-a", "Komorebi Desktop", title, msg],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
        except Exception:
            pass
