import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Callable, Optional
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QSize, Qt
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from wallhaven.cache import cache

USER_AGENT = "KomorebiDesktop/2.0 (High-Performance Wallpaper Manager)"

# Shared pooled HTTP session for high-speed parallel downloads with keep-alive
http_session = requests.Session()
retries = Retry(total=2, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32, max_retries=retries)
http_session.mount("https://", adapter)
http_session.mount("http://", adapter)
http_session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
})


def _render_rounded_thumbnail(img: QImage, target_w: int, target_h: int, radius: int = 8) -> QImage:
    """Performs bicubic scaling, center-crop, and antialiased rounded corners in background thread."""
    scaled = img.scaled(
        QSize(target_w, target_h),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - target_w) // 2)
    y = max(0, (scaled.height() - target_h) // 2)
    cropped = scaled.copy(x, y, target_w, target_h)

    result = QImage(target_w, target_h, QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(Qt.GlobalColor.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(target_w), float(target_h), float(radius), float(radius))
    painter.setClipPath(path)
    painter.drawImage(0, 0, cropped)
    painter.end()
    return result


class ImageLoadSignals(QObject):
    finished = pyqtSignal(str, QImage, int, int)  # url, qimage, target_w, target_h
    error = pyqtSignal(str, str)                  # url, error_msg


class ImageLoadTask(QRunnable):
    def __init__(self, url: str, is_thumb: bool = True, target_size: Optional[tuple[int, int]] = None, radius: int = 8):
        super().__init__()
        self.url = url
        self.is_thumb = is_thumb
        self.target_size = target_size
        self.radius = radius
        self.signals = ImageLoadSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        try:
            target_w = self.target_size[0] if self.target_size else 0
            target_h = self.target_size[1] if self.target_size else 0

            # 1. Check local file
            if os.path.exists(self.url):
                lower = self.url.lower()
                if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
                    img = QImage(self.url)
                    if not img.isNull():
                        if target_w > 0 and target_h > 0:
                            img = _render_rounded_thumbnail(img, target_w, target_h, self.radius)
                        self.signals.finished.emit(self.url, img, target_w, target_h)
                        return
                elif lower.endswith((".mp4", ".webm", ".mkv")):
                    thumb_path = cache.get_video_thumb_path(self.url)
                    if not (thumb_path.exists() and thumb_path.stat().st_size > 0):
                        try:
                            import subprocess
                            cmd = [
                                "ffmpeg",
                                "-ss", "00:00:01",
                                "-i", self.url,
                                "-vframes", "1",
                                "-q:v", "2",
                                str(thumb_path),
                                "-y",
                            ]
                            subprocess.run(cmd, capture_output=True, timeout=4)
                        except Exception:
                            pass
                    if thumb_path.exists() and thumb_path.stat().st_size > 0:
                        img = QImage(str(thumb_path))
                        if not img.isNull():
                            if target_w > 0 and target_h > 0:
                                img = _render_rounded_thumbnail(img, target_w, target_h, self.radius)
                            self.signals.finished.emit(self.url, img, target_w, target_h)
                            return

            # 2. Check disk cache
            cached_path = cache.get_cached_path(self.url, self.is_thumb)
            if cached_path:
                img = QImage(str(cached_path))
                if not img.isNull():
                    if target_w > 0 and target_h > 0:
                        img = _render_rounded_thumbnail(img, target_w, target_h, self.radius)
                    self.signals.finished.emit(self.url, img, target_w, target_h)
                    return

            # 3. Download via pooled session
            headers = {}
            if "moewalls.com" in self.url:
                headers["Referer"] = "https://moewalls.com/"

            resp = http_session.get(self.url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.content
                cache.save_data(self.url, data, self.is_thumb)
                img = QImage()
                if img.loadFromData(data):
                    if target_w > 0 and target_h > 0:
                        img = _render_rounded_thumbnail(img, target_w, target_h, self.radius)
                    self.signals.finished.emit(self.url, img, target_w, target_h)
                else:
                    self.signals.error.emit(self.url, "Failed to decode image")
            else:
                self.signals.error.emit(self.url, f"HTTP {resp.status_code}")

        except RuntimeError:
            pass
        except Exception as e:
            try:
                self.signals.error.emit(self.url, str(e))
            except Exception:
                pass


class AsyncImageLoader(QObject):
    image_loaded = pyqtSignal(str, QPixmap)
    image_failed = pyqtSignal(str, str)

    def __init__(self, max_threads: int = 12):
        super().__init__()
        self.cache = cache
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(max_threads)
        self._pending_urls: set[str] = set()
        self._callbacks: dict[str, list[Callable[[QPixmap], None]]] = {}

    def get_cache_path(self, url: str, is_thumb: bool = True):
        return self.cache.get_cached_path(url, is_thumb)

    def load_thumbnail(
        self,
        url: str,
        target_size: tuple[int, int] = (278, 172),
        radius: int = 8,
        callback: Optional[Callable[[QPixmap], None]] = None,
    ) -> bool:
        """
        Ultra-fast thumbnail loader:
        - Returns True and invokes callback immediately on instant cache hit.
        - Otherwise scales & crops in background worker, then notifies callback without blocking UI thread.
        """
        if not url:
            return False

        w, h = target_size
        cached_pm = self.cache.get_scaled_pixmap(url, w, h)
        if cached_pm and not cached_pm.isNull():
            if callback:
                callback(cached_pm)
            self.image_loaded.emit(url, cached_pm)
            return True

        # Check raw memory cache
        raw_pm = self.cache.get_pixmap(url, is_thumb=True)
        if raw_pm and not raw_pm.isNull():
            # Quick scaled cache generation
            qimg = raw_pm.toImage()
            scaled_img = _render_rounded_thumbnail(qimg, w, h, radius)
            pm = QPixmap.fromImage(scaled_img)
            self.cache.save_scaled_pixmap(url, w, h, pm)
            if callback:
                callback(pm)
            self.image_loaded.emit(url, pm)
            return True

        if callback:
            if url not in self._callbacks:
                self._callbacks[url] = []
            self._callbacks[url].append(callback)

        if url in self._pending_urls:
            return False

        self._pending_urls.add(url)
        task = ImageLoadTask(url, is_thumb=True, target_size=target_size, radius=radius)
        task.signals.finished.connect(self._on_qimage_success)
        task.signals.error.connect(self._on_error)
        self.pool.start(task)
        return False

    def load_image(self, url: str, is_thumb: bool = True, callback: Optional[Callable[[QPixmap], None]] = None) -> bool:
        """Legacy API for backwards compatibility with optional targeted callback support."""
        if not url:
            return False

        pm = self.cache.get_pixmap(url, is_thumb)
        if pm and not pm.isNull():
            if callback:
                callback(pm)
            self.image_loaded.emit(url, pm)
            return True

        if callback:
            if url not in self._callbacks:
                self._callbacks[url] = []
            self._callbacks[url].append(callback)

        if url in self._pending_urls:
            return False

        self._pending_urls.add(url)
        task = ImageLoadTask(url, is_thumb=is_thumb, target_size=None)
        task.signals.finished.connect(self._on_qimage_success)
        task.signals.error.connect(self._on_error)
        self.pool.start(task)
        return False

    def unregister_callback(self, url: str, callback: Callable[[QPixmap], None]):
        """Unregisters a callback to prevent stale updates."""
        if url in self._callbacks:
            try:
                self._callbacks[url].remove(callback)
                if not self._callbacks[url]:
                    del self._callbacks[url]
            except ValueError:
                pass

    def _on_qimage_success(self, url: str, qimage: QImage, target_w: int, target_h: int):
        self._pending_urls.discard(url)
        pixmap = QPixmap.fromImage(qimage)

        if target_w > 0 and target_h > 0:
            self.cache.save_scaled_pixmap(url, target_w, target_h, pixmap)

        # Dispatch to targeted callbacks
        callbacks = self._callbacks.pop(url, [])
        for cb in callbacks:
            try:
                cb(pixmap)
            except Exception:
                pass

        # Also emit standard signal
        try:
            self.image_loaded.emit(url, pixmap)
        except RuntimeError:
            pass

    def _on_error(self, url: str, err: str):
        self._pending_urls.discard(url)
        self._callbacks.pop(url, None)
        try:
            self.image_failed.emit(url, err)
        except RuntimeError:
            pass


# Global singleton instance with 12 parallel threads for blazing fast loading
loader = AsyncImageLoader(max_threads=12)
