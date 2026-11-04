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

from .access_manager import DesktopAccessState, PermissionScope, get_access_manager
from .monitor_manager import get_monitor_manager

logger = logging.getLogger("JARVIS.ScreenCapture")

_IMG_MAX_W = 1280
_IMG_MAX_H = 720
_JPEG_QUALITY = 75


def _ensure_desktop_attached() -> None:
    """Ensure the calling thread is attached to the active interactive desktop (winsta0/default)."""
    try:
        import win32service
        cur_winsta = win32service.GetProcessWindowStation()
        if cur_winsta:
            name = win32service.GetUserObjectInformation(cur_winsta, 2)
            if "winsta0" in str(name).lower():
                return
        hwinsta = win32service.OpenWindowStation("winsta0", False, 0x037F)
        hwinsta.SetProcessWindowStation()
        hdesk = win32service.OpenDesktop("default", 0, False, 0x01FF)
        hdesk.SetThreadDesktop()
    except Exception:
        pass


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
        """Capture the entire virtual desktop across all active monitors with graceful fallbacks."""
        self._verify_permission()

        # 1. Primary: MSS (target monitor 1 or 0)
        try:
            mss_cls = getattr(mss, "MSS", mss.mss)
            with mss_cls() as sct:
                target = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(target)
                img = Image.frombytes("RGB", raw.size, raw.rgb)
                return self._process_image(img, compress, max_size)
        except Exception as e:
            logger.debug("MSS desktop capture failed (%s); falling back to PIL ImageGrab", e)

        # 2. Secondary fallback: PIL ImageGrab
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True).convert("RGB")
            return self._process_image(img, compress, max_size)
        except Exception as e:
            logger.debug("PIL ImageGrab failed (%s); trying PyAutoGUI", e)

        # 3. Tertiary fallback: PyAutoGUI screenshot
        try:
            import pyautogui
            img = pyautogui.screenshot().convert("RGB")
            return self._process_image(img, compress, max_size)
        except Exception as e:
            logger.error("All desktop screenshot backends failed: %s", e)
            raise RuntimeError(f"All desktop screenshot backends failed: {e}")

    def capture_monitor(
        self,
        monitor_index: int = 1,
        compress: bool = True,
        max_size: Optional[Tuple[int, int]] = (_IMG_MAX_W, _IMG_MAX_H),
    ) -> Tuple[Image.Image, bytes, str]:
        """Capture a specific monitor by 1-based index."""
        self._verify_permission()
        try:
            mss_cls = getattr(mss, "MSS", mss.mss)
            with mss_cls() as sct:
                idx = monitor_index if 0 < monitor_index < len(sct.monitors) else 1
                raw = sct.grab(sct.monitors[idx])
                img = Image.frombytes("RGB", raw.size, raw.rgb)
                return self._process_image(img, compress, max_size)
        except Exception as e:
            logger.debug("MSS capture_monitor failed (%s); falling back to full desktop grab", e)
            return self.capture_full_desktop(compress=compress, max_size=max_size)

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

        # 1. Primary: MSS regional grab
        try:
            bbox = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
            mss_cls = getattr(mss, "MSS", mss.mss)
            with mss_cls() as sct:
                raw = sct.grab(bbox)
                img = Image.frombytes("RGB", raw.size, raw.rgb)
                return self._process_image(img, compress, max_size)
        except Exception as e:
            logger.debug("MSS regional grab failed (%s); trying PIL crop fallback", e)

        # 2. Secondary fallback: PIL ImageGrab regional crop
        try:
            from PIL import ImageGrab
            bbox_tuple = (int(left), int(top), int(left + width), int(top + height))
            img = ImageGrab.grab(bbox=bbox_tuple, all_screens=True).convert("RGB")
            return self._process_image(img, compress, max_size)
        except Exception as e:
            logger.error("Regional capture failed: %s", e)
            raise RuntimeError(f"Regional capture failed: {e}")

    def capture_active_window(
        self,
        compress: bool = True,
        max_size: Optional[Tuple[int, int]] = (_IMG_MAX_W, _IMG_MAX_H),
    ) -> Tuple[Image.Image, int, int]:
        """Capture active foreground window with (offset_x, offset_y) coordinates."""
        self._verify_permission()
        offset_x, offset_y = 0, 0
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                l, t, r, b = win32gui.GetWindowRect(hwnd)
                w, h = r - l, b - t
                if w > 50 and h > 50:
                    img, _, _ = self.capture_region(l, t, w, h, compress=compress, max_size=max_size)
                    return img, l, t
        except Exception:
            pass

        img, _, _ = self.capture_full_desktop(compress=compress, max_size=max_size)
        return img, offset_x, offset_y

    def _verify_permission(self) -> None:
        _ensure_desktop_attached()
        if not self._access_mgr.check_permission(PermissionScope.SCREEN_CAPTURE):
            # Screen capture is read-only observation. Automatically enable OBSERVE_ONLY mode
            # for requested visual perception unless an emergency stop error is active.
            if self._access_mgr.state != DesktopAccessState.ERROR:
                self._access_mgr.enable_observe_only()
            else:
                raise PermissionError("Screen capture denied: Desktop is in ERROR / Emergency Stop state.")

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


# Backward-compatible alias
ScreenCaptureEngine = ScreenCaptureService
