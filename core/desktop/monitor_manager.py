"""
core/desktop/monitor_manager.py — Multi-monitor topology and DPI awareness manager.
"""
from __future__ import annotations

import ctypes
import logging
import platform
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("JARVIS.MonitorManager")

# DPI Awareness
if platform.system() == "Windows":
    try:
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE_V2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


@dataclass
class MonitorInfo:
    index: int
    is_primary: bool
    left: int
    top: int
    width: int
    height: int
    scale_factor: float = 1.0

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


class MonitorManager:
    """Manages monitor detection, coordinate spaces, and DPI scaling."""

    def __init__(self):
        self._monitors: List[MonitorInfo] = []
        self.refresh()

    def refresh(self) -> None:
        """Enumerate displays and recalculate virtual desktop bounds."""
        monitors = []
        try:
            import mss
            mss_cls = getattr(mss, "MSS", mss.mss)
            with mss_cls() as sct:
                # sct.monitors[0] is the virtual desktop enclosing all monitors
                # sct.monitors[1..n] are the individual monitors
                for idx, m in enumerate(sct.monitors[1:], start=1):
                    is_prim = (m["left"] == 0 and m["top"] == 0)
                    scale = self._get_monitor_dpi_scale(idx - 1)
                    monitors.append(
                        MonitorInfo(
                            index=idx,
                            is_primary=is_prim,
                            left=m["left"],
                            top=m["top"],
                            width=m["width"],
                            height=m["height"],
                            scale_factor=scale,
                        )
                    )
        except Exception as e:
            logger.warning("MSS monitor enumeration failed: %s; falling back to primary", e)
            # Fallback
            monitors.append(MonitorInfo(index=1, is_primary=True, left=0, top=0, width=1920, height=1080))

        self._monitors = monitors
        logger.info("Detected %d monitor(s): %s", len(self._monitors), [(m.index, m.width, m.height) for m in self._monitors])

    def _get_monitor_dpi_scale(self, monitor_idx: int) -> float:
        if platform.system() != "Windows":
            return 1.0
        try:
            # Standard 96 DPI is 100%
            # Try to query DPI via GetDpiForSystem or win32
            dpi = ctypes.windll.user32.GetDpiForSystem()
            return float(dpi) / 96.0
        except Exception:
            return 1.0

    @property
    def monitors(self) -> List[MonitorInfo]:
        if not self._monitors:
            self.refresh()
        return self._monitors

    @property
    def primary_monitor(self) -> MonitorInfo:
        for m in self.monitors:
            if m.is_primary:
                return m
        return self.monitors[0] if self.monitors else MonitorInfo(1, True, 0, 0, 1920, 1080)

    def get_monitor_at(self, x: int, y: int) -> MonitorInfo:
        for m in self.monitors:
            if m.contains(x, y):
                return m
        return self.primary_monitor

    def get_monitor_by_index(self, index: int) -> Optional[MonitorInfo]:
        for m in self.monitors:
            if m.index == index:
                return m
        return None

    def get_virtual_desktop_bounds(self) -> Tuple[int, int, int, int]:
        """Returns (min_left, min_top, total_width, total_height) for all monitors."""
        if not self.monitors:
            return (0, 0, 1920, 1080)
        min_left = min(m.left for m in self.monitors)
        min_top = min(m.top for m in self.monitors)
        max_right = max(m.right for m in self.monitors)
        max_bottom = max(m.bottom for m in self.monitors)
        return (min_left, min_top, max_right - min_left, max_bottom - min_top)


_monitor_mgr_instance: Optional[MonitorManager] = None


def get_monitor_manager() -> MonitorManager:
    global _monitor_mgr_instance
    if _monitor_mgr_instance is None:
        _monitor_mgr_instance = MonitorManager()
    return _monitor_mgr_instance
