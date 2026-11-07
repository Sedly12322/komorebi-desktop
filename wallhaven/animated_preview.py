"""Codec-independent animated wallpaper preview playback.

MoeWalls serves its previews as AV1 ``.webm`` files, which the FFmpeg build bundled with
Qt Multimedia cannot decode (playback hangs in "Buffering" with zero frames).  This module
decodes the frames with PyAV (bundles dav1d, wheels for Linux and Windows) in a background
thread and hands them to the UI as ``QImage`` frames, so cards and the detail dialog can
play any preview/local video without relying on Qt's media backend.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage

from wallhaven.cache import CACHE_DIR

try:  # PyAV is optional: without it we gracefully fall back to static thumbnails
    import av  # type: ignore

    HAS_AV = True
except Exception:  # pragma: no cover - depends on environment
    av = None  # type: ignore
    HAS_AV = False

ANIM_CACHE_DIR = CACHE_DIR / "anim"
_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) Komorebi-Desktop"
_MAX_CACHE_BYTES = 400 * 1024 * 1024


def _prune_cache():
    """Keeps the animation cache bounded (oldest files removed first)."""
    try:
        files = [f for f in ANIM_CACHE_DIR.glob("*") if f.is_file()]
        total = sum(f.stat().st_size for f in files)
        if total <= _MAX_CACHE_BYTES:
            return
        for f in sorted(files, key=lambda p: p.stat().st_mtime):
            total -= f.stat().st_size
            f.unlink(missing_ok=True)
            if total <= _MAX_CACHE_BYTES * 0.8:
                break
    except Exception:
        pass


def ensure_local_video(source: str, is_cancelled=lambda: False) -> str:
    """Returns a local file path for ``source`` (downloading + caching http(s) URLs)."""
    if not source.startswith(("http://", "https://")):
        return source

    import requests

    ANIM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(source.split("?")[0])[1] or ".webm"
    target = ANIM_CACHE_DIR / (hashlib.sha1(source.encode("utf-8")).hexdigest() + ext)
    if target.exists() and target.stat().st_size > 0:
        os.utime(target, None)
        return str(target)

    tmp = target.with_suffix(target.suffix + ".part")
    headers = {"User-Agent": _USER_AGENT, "Referer": "https://moewalls.com/"}
    with requests.get(source, headers=headers, stream=True, timeout=20) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=128 * 1024):
                if is_cancelled():
                    f.close()
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError("cancelled")
                f.write(chunk)
    os.replace(tmp, target)
    _prune_cache()
    return str(target)


def resolve_animated_source(item) -> str:
    """Finds the best playable source for an animated item (local file > preview URL)."""
    for attr in ("local_path", "saved_path"):
        p = getattr(item, attr, "") or ""
        if p and os.path.exists(p):
            return p
    path = getattr(item, "path", "") or ""
    if path and os.path.exists(path):
        return path
    url = getattr(item, "preview_video_url", "") or ""
    if url:
        return url
    from wallhaven.moewalls import moewalls_manager

    detail = moewalls_manager.get_wallpaper_detail(item)
    return getattr(detail, "preview_video_url", "") or ""


class _DecodeThread(QThread):
    frame_ready = pyqtSignal(QImage)
    failed = pyqtSignal(str)

    def __init__(self, source, bounds: tuple[int, int], cover: bool, item=None):
        super().__init__()
        self._source = source
        self._item = item
        self._bw, self._bh = bounds
        self._cover = cover
        self._stop = threading.Event()
        self._running = threading.Event()
        self._running.set()

    def stop(self):
        self._stop.set()
        self._running.set()

    def set_paused(self, paused: bool):
        if paused:
            self._running.clear()
        else:
            self._running.set()

    def run(self):
        try:
            source = self._source
            if not source and self._item is not None:
                source = resolve_animated_source(self._item)
            if not source:
                self.failed.emit("no preview source")
                return
            path = ensure_local_video(source, self._stop.is_set)
            if self._stop.is_set():
                return
            self._play_loop(path)
        except Exception as e:  # network / codec errors must never crash the UI
            if not self._stop.is_set():
                self.failed.emit(str(e))

    def _target_size(self, vw: int, vh: int) -> tuple[int, int]:
        if self._cover:
            s = max(self._bw / vw, self._bh / vh)
        else:
            s = min(self._bw / vw, self._bh / vh, 1.0)
        return max(2, int(vw * s) // 2 * 2), max(2, int(vh * s) // 2 * 2)

    def _play_loop(self, path: str):
        while not self._stop.is_set():
            container = av.open(path)
            try:
                stream = container.streams.video[0]
                stream.thread_type = "AUTO"
                rate = float(stream.average_rate or 30.0)
                frame_time = 1.0 / max(1.0, min(rate, 60.0))
                tw, th = self._target_size(stream.codec_context.width, stream.codec_context.height)
                next_t = time.monotonic()
                shown = 0
                for frame in container.decode(stream):
                    if self._stop.is_set():
                        return
                    self._running.wait()
                    if self._stop.is_set():
                        return
                    rgb = frame.reformat(width=tw, height=th, format="rgb24")
                    plane = rgb.planes[0]
                    img = QImage(
                        bytes(plane), tw, th, plane.line_size, QImage.Format.Format_RGB888
                    ).copy()
                    if self._cover and (tw > self._bw or th > self._bh):
                        x = max(0, (tw - self._bw) // 2)
                        y = max(0, (th - self._bh) // 2)
                        img = img.copy(x, y, min(self._bw, tw), min(self._bh, th))
                    self.frame_ready.emit(img)
                    shown += 1
                    next_t += frame_time
                    delay = next_t - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    else:
                        next_t = time.monotonic()
                if shown == 0:
                    self.failed.emit("no decodable frames")
                    return
            finally:
                container.close()


class AnimPlayer(QObject):
    """Tiny media-player-like facade: ``play(source)`` -> ``frame`` signals, loops forever."""

    frame = pyqtSignal(QImage)
    error = pyqtSignal(str)

    _lingering: set = set()

    def __init__(self, bounds: tuple[int, int] = (1280, 720), cover: bool = False, parent=None):
        super().__init__(parent)
        self._bounds = bounds
        self._cover = cover
        self._thread: Optional[_DecodeThread] = None
        self._paused = False

    @staticmethod
    def available() -> bool:
        return HAS_AV

    def is_active(self) -> bool:
        return self._thread is not None

    def is_playing(self) -> bool:
        return self._thread is not None and not self._paused

    def start(self, source: str = "", item=None):
        """Starts looping playback of ``source`` (path/URL) or of the best source for ``item``."""
        self.stop()
        if not HAS_AV:
            self.error.emit("PyAV is not installed")
            return
        self._paused = False
        t = _DecodeThread(source, self._bounds, self._cover, item)
        t.frame_ready.connect(self.frame)
        t.failed.connect(self.error)
        self._thread = t
        AnimPlayer._lingering.add(t)  # keep a reference until the thread really finishes
        t.finished.connect(lambda th=t: AnimPlayer._lingering.discard(th))
        self.destroyed.connect(t.stop)  # owner (e.g. a grid card) deleted -> end decoding
        t.start()

    def pause(self):
        if self._thread:
            self._paused = True
            self._thread.set_paused(True)

    def resume(self):
        if self._thread:
            self._paused = False
            self._thread.set_paused(False)

    def stop(self):
        t, self._thread = self._thread, None
        self._paused = False
        if t is None:
            return
        t.stop()
        for sig in (t.frame_ready, t.failed):
            try:
                sig.disconnect()
            except Exception:
                pass
