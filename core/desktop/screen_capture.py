"""
core/desktop/screen_capture.py — High-performance desktop screen capture service.
"""
from __future__ import annotations

import io
import logging
from typing import Optional, Tuple

import mss
import mss.tools
from PIL import Image

from .access_manager import PermissionScope, get_access_manager
from .monitor_manager import get_monitor_manager

logger = logging.getLogger("JARVIS.ScreenCapture")

_IMG_MAX_W = 1920
_IMG_MAX_H = 1080
_JPEG_QUALITY = 85


class ScreenCaptureService:
    """Provides monitor-aware, region-aware desktop screenshot capture."""

    def __init__(self):
        self._monitor_mgr = get_monitor_manager()
        self._access_mgr = get_access_manager()

    def capture_full_desktop(
        self,
        compress: bool = True,
        max_size: Optional[Tuple[int, int]] = (_IMG_MAX_W, _IMG_MAX_H),
    ) -> Tuple[Image.Image, bytes, str]:
        """Capture the entire virtual desktop across all active monitors."""
        self._verify_permission()
        mss_cls = getattr(mss, "MSS", mss.mss)
        with mss_cls() as sct:
            # monitors[0] covers the entire virtual desktop
            raw = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", raw.size, raw.rgb)
            return self._process_image(img, compress, max_size)

    def capture_monitor(
        self,
        monitor_index: int = 1,
        compress: bool = True,
        max_size: Optional[Tuple[int, int]] = (_IMG_MAX_W, _IMG_MAX_H),
    ) -> Tuple[Image.Image, bytes, str]:
        """Capture a specific monitor by 1-based index."""
        self._verify_permission()
        mss_cls = getattr(mss, "MSS", mss.mss)
        with mss_cls() as sct:
            idx = monitor_index if 0 < monitor_index < len(sct.monitors) else 1
            raw = sct.grab(sct.monitors[idx])
            img = Image.frombytes("RGB", raw.size, raw.rgb)
            return self._process_image(img, compress, max_size)

    def capture_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        compress: bool = True,
        max_size: Optional[Tuple[int, int]] = None,
    ) -> Tuple[Image.Image, bytes, str]:
        """Capture an arbitrary screen bounding box in absolute virtual desktop coordinates."""
        self._verify_permission()
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid capture region dimensions: {width}x{height}")

        bbox = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
        with mss.mss() as sct:
            raw = sct.grab(bbox)
            img = Image.frombytes("RGB", raw.size, raw.rgb)
            return self._process_image(img, compress, max_size)

    def _verify_permission(self) -> None:
        if not self._access_mgr.check_permission(PermissionScope.SCREEN_CAPTURE):
            # If access manager is disabled, auto-enable observation for explicitly requested vision actions
            # or raise permission error if strict
            if not self._access_mgr.is_observe_enabled:
                raise PermissionError("Screen capture denied: Desktop access permission not granted.")

    def _process_image(
        self,
        img: Image.Image,
        compress: bool,
        max_size: Optional[Tuple[int, int]],
    ) -> Tuple[Image.Image, bytes, str]:
        if max_size and (img.width > max_size[0] or img.height > max_size[1]):
            img.thumbnail(max_size, Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        if compress:
            img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=False)
            return img, buf.getvalue(), "image/jpeg"
        else:
            img.save(buf, format="PNG")
            return img, buf.getvalue(), "image/png"


_capture_service_instance: Optional[ScreenCaptureService] = None


def get_screen_capture() -> ScreenCaptureService:
    global _capture_service_instance
    if _capture_service_instance is None:
        _capture_service_instance = ScreenCaptureService()
    return _capture_service_instance
