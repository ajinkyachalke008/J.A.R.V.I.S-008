"""
core/desktop/visual_grounding.py — Coordinate translation, normalization, and element snapping.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from .monitor_manager import MonitorInfo, get_monitor_manager
from .ui_automation import UIElement, get_ui_automation

logger = logging.getLogger("JARVIS.VisualGrounding")


class VisualGroundingEngine:
    """Translates normalized and relative coordinates into precise physical screen targets."""

    def __init__(self):
        self._monitor_mgr = get_monitor_manager()
        self._ui_automation = get_ui_automation()

    def normalized_to_screen(
        self,
        norm_x: float,
        norm_y: float,
        monitor_index: int = 1,
        range_max: float = 1000.0,
    ) -> Tuple[int, int]:
        """Convert normalized coordinates (e.g. 0..1000 from Gemini Vision) to absolute screen pixels."""
        mon = self._monitor_mgr.get_monitor_by_index(monitor_index) or self._monitor_mgr.primary_monitor

        # Clamp input
        nx = max(0.0, min(float(norm_x), range_max)) / range_max
        ny = max(0.0, min(float(norm_y), range_max)) / range_max

        screen_x = int(mon.left + (nx * mon.width))
        screen_y = int(mon.top + (ny * mon.height))
        return (screen_x, screen_y)

    def screen_to_normalized(
        self,
        screen_x: int,
        screen_y: int,
        monitor_index: int = 1,
        range_max: float = 1000.0,
    ) -> Tuple[int, int]:
        """Convert absolute screen pixels to normalized coordinates (0..1000)."""
        mon = self._monitor_mgr.get_monitor_by_index(monitor_index) or self._monitor_mgr.primary_monitor
        nx = ((screen_x - mon.left) / max(1, mon.width)) * range_max
        ny = ((screen_y - mon.top) / max(1, mon.height)) * range_max
        return (int(round(max(0.0, min(range_max, nx)))), int(round(max(0.0, min(range_max, ny)))))

    def snap_to_element(
        self,
        x: int,
        y: int,
        max_distance: int = 25,
    ) -> Tuple[int, int, Optional[UIElement]]:
        """Snap (x, y) to the centroid of the nearest UI Automation element within max_distance pixels."""
        elems = self._ui_automation.get_active_window_elements()
        if not elems:
            return (x, y, None)

        # 1. Direct containment check
        containing = [el for el in elems if el.contains(x, y)]
        if containing:
            containing.sort(key=lambda el: el.width * el.height)
            best = containing[0]
            cx, cy = best.center
            logger.debug("Snapped (%d, %d) to containing element '%s' at (%d, %d)", x, y, best.name, cx, cy)
            return (cx, cy, best)

        # 2. Distance check to centroids
        best_dist = float("inf")
        best_elem = None
        for el in elems:
            cx, cy = el.center
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist < best_dist and dist <= max_distance:
                best_dist = dist
                best_elem = el

        if best_elem is not None:
            cx, cy = best_elem.center
            logger.debug("Snapped (%d, %d) to nearest element '%s' at (%d, %d) [dist=%.1fpx]", x, y, best_elem.name, cx, cy, best_dist)
            return (cx, cy, best_elem)

        return (x, y, None)


_visual_grounding_instance: Optional[VisualGroundingEngine] = None


def get_visual_grounding() -> VisualGroundingEngine:
    global _visual_grounding_instance
    if _visual_grounding_instance is None:
        _visual_grounding_instance = VisualGroundingEngine()
    return _visual_grounding_instance
