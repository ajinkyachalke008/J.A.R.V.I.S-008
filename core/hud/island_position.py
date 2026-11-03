"""
core/hud/island_position.py — Screen geometry, anchor calculation, and multi-monitor engine for Dynamic Island.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, List, Optional, Set, Union
from PyQt6.QtCore import QObject, QPoint, QRect, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QScreen

logger = logging.getLogger("JARVIS.IslandPosition")


class IslandAnchor(Enum):
    """Anchoring alignment modes for the Dynamic Island."""
    TOP_CENTER = "top_center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_CENTER = "bottom_center"
    CUSTOM = "custom"


_ANCHOR_MAPPINGS = {
    "top_center": IslandAnchor.TOP_CENTER,
    "top-center": IslandAnchor.TOP_CENTER,
    "top center": IslandAnchor.TOP_CENTER,
    "top": IslandAnchor.TOP_CENTER,
    "center": IslandAnchor.TOP_CENTER,
    "top_left": IslandAnchor.TOP_LEFT,
    "top-left": IslandAnchor.TOP_LEFT,
    "top left": IslandAnchor.TOP_LEFT,
    "left": IslandAnchor.TOP_LEFT,
    "top_right": IslandAnchor.TOP_RIGHT,
    "top-right": IslandAnchor.TOP_RIGHT,
    "top right": IslandAnchor.TOP_RIGHT,
    "right": IslandAnchor.TOP_RIGHT,
    "bottom_center": IslandAnchor.BOTTOM_CENTER,
    "bottom-center": IslandAnchor.BOTTOM_CENTER,
    "bottom center": IslandAnchor.BOTTOM_CENTER,
    "bottom": IslandAnchor.BOTTOM_CENTER,
    "custom": IslandAnchor.CUSTOM,
}


class IslandPositionEngine(QObject):
    """
    Computes precise floating window coordinates based on active monitor geometry,
    anchor presets, and user offsets. Listens for display topology changes.
    """

    topology_changed = pyqtSignal()
    position_changed = pyqtSignal(QPoint)

    def __init__(
        self,
        anchor: Union[str, IslandAnchor] = IslandAnchor.TOP_CENTER,
        offset_x: int = 0,
        offset_y: int = 10,
        monitor_index: int = 0,
        safe_margin: int = 4,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._anchor: IslandAnchor = self.normalize_anchor(anchor)
        self._offset_x: int = int(offset_x)
        self._offset_y: int = int(offset_y)
        self._monitor_index: int = max(0, int(monitor_index))
        self._safe_margin: int = max(0, int(safe_margin))
        self._fallback_geometry: QRect = QRect(0, 0, 1920, 1080)
        self._monitored_screens: Set[int] = set()

        self.attach_screen_listeners()

    # ── Configuration & Accessors ────────────────────────────────────────────

    @classmethod
    def normalize_anchor(cls, raw: Union[str, IslandAnchor, Any]) -> IslandAnchor:
        """Parse raw string or enum into a validated IslandAnchor."""
        if isinstance(raw, IslandAnchor):
            return raw
        key = str(raw or "").strip().lower()
        return _ANCHOR_MAPPINGS.get(key, IslandAnchor.TOP_CENTER)

    @property
    def anchor(self) -> IslandAnchor:
        return self._anchor

    @anchor.setter
    def anchor(self, val: Union[str, IslandAnchor]) -> None:
        norm = self.normalize_anchor(val)
        if norm != self._anchor:
            self._anchor = norm
            self.topology_changed.emit()

    def set_anchor(self, val: Union[str, IslandAnchor]) -> None:
        self.anchor = val

    @property
    def offset_x(self) -> int:
        return self._offset_x

    @offset_x.setter
    def offset_x(self, val: int) -> None:
        self._offset_x = int(val)

    @property
    def offset_y(self) -> int:
        return self._offset_y

    @offset_y.setter
    def offset_y(self, val: int) -> None:
        self._offset_y = int(val)

    def set_offset(self, x: int, y: int) -> None:
        self._offset_x = int(x)
        self._offset_y = int(y)

    @property
    def monitor_index(self) -> int:
        return self._monitor_index

    @monitor_index.setter
    def monitor_index(self, val: int) -> None:
        self._monitor_index = max(0, int(val))
        self.topology_changed.emit()

    def set_monitor_index(self, index: int) -> None:
        self.monitor_index = index

    @property
    def safe_margin(self) -> int:
        return self._safe_margin

    @safe_margin.setter
    def safe_margin(self, val: int) -> None:
        self._safe_margin = max(0, int(val))

    # ── Monitor Resolution ───────────────────────────────────────────────────

    def get_target_screen(self) -> Optional[QScreen]:
        """
        Resolve the target QScreen by monitor index.
        Falls back to primaryScreen or the first available screen.
        """
        app = QGuiApplication.instance()
        if not app:
            return None
        screens = app.screens()
        if not screens:
            return None
        if 0 <= self._monitor_index < len(screens):
            return screens[self._monitor_index]
        primary = app.primaryScreen()
        return primary if primary is not None else screens[0]

    def get_screen_geometry(self, screen: Optional[Any] = None) -> QRect:
        """Retrieve QRect geometry of the specified or target screen with fallback."""
        target = screen if screen is not None else self.get_target_screen()
        if target is not None and hasattr(target, "geometry"):
            return target.geometry()
        return self._fallback_geometry

    # ── Position Calculation ─────────────────────────────────────────────────

    def calculate_position(
        self,
        pill_width: int,
        pill_height: int,
        screen: Optional[Any] = None,
        clamp_to_bounds: bool = True,
    ) -> QPoint:
        """
        Compute top-left coordinates for the Dynamic Island pill on the target display.
        Correctly supports multi-monitor virtual coordinates (including negative offsets)
        and enforces display safe margins.
        """
        geom = self.get_screen_geometry(screen)
        sx = geom.x()
        sy = geom.y()
        sw = geom.width()
        sh = geom.height()

        pw = int(pill_width)
        ph = int(pill_height)

        if self._anchor == IslandAnchor.TOP_CENTER:
            x = sx + (sw - pw) // 2 + self._offset_x
            y = sy + self._offset_y
        elif self._anchor == IslandAnchor.TOP_LEFT:
            x = sx + self._offset_x
            y = sy + self._offset_y
        elif self._anchor == IslandAnchor.TOP_RIGHT:
            x = sx + sw - pw - self._offset_x
            y = sy + self._offset_y
        elif self._anchor == IslandAnchor.BOTTOM_CENTER:
            x = sx + (sw - pw) // 2 + self._offset_x
            y = sy + sh - ph - self._offset_y
        elif self._anchor == IslandAnchor.CUSTOM:
            x = sx + self._offset_x
            y = sy + self._offset_y
        else:
            x = sx + (sw - pw) // 2 + self._offset_x
            y = sy + self._offset_y

        if clamp_to_bounds:
            min_x = sx + self._safe_margin
            max_x = sx + sw - pw - self._safe_margin
            min_y = sy + self._safe_margin
            max_y = sy + sh - ph - self._safe_margin

            if max_x >= min_x:
                x = max(min_x, min(x, max_x))
            else:
                x = sx

            if max_y >= min_y:
                y = max(min_y, min(y, max_y))
            else:
                y = sy

        pos = QPoint(int(x), int(y))
        self.position_changed.emit(pos)
        return pos

    # ── Display Topology Change Listeners ────────────────────────────────────

    def attach_screen_listeners(self) -> None:
        """Subscribe to QGuiApplication screen lifecycle and geometry events."""
        app = QGuiApplication.instance()
        if not app:
            return

        try:
            app.screenAdded.connect(self._on_screen_added)
            app.screenRemoved.connect(self._on_screen_removed)
        except Exception as e:
            logger.debug("Failed connecting to screenAdded/Removed signals: %s", e)

        for screen in app.screens():
            self._track_screen_geometry(screen)

    def detach_screen_listeners(self) -> None:
        """Cleanly unsubscribe from QGuiApplication screen events."""
        app = QGuiApplication.instance()
        if not app:
            return
        try:
            app.screenAdded.disconnect(self._on_screen_added)
        except Exception:
            pass
        try:
            app.screenRemoved.disconnect(self._on_screen_removed)
        except Exception:
            pass
        self._monitored_screens.clear()

    def _track_screen_geometry(self, screen: QScreen) -> None:
        """Connect to geometryChanged for a screen if not already tracked."""
        if not screen or not hasattr(screen, "geometryChanged"):
            return
        screen_id = id(screen)
        if screen_id not in self._monitored_screens:
            try:
                screen.geometryChanged.connect(self._on_geometry_changed)
                self._monitored_screens.add(screen_id)
            except Exception as e:
                logger.debug("Could not track screen geometry: %s", e)

    def _on_screen_added(self, screen: QScreen) -> None:
        logger.info("Display added: %s", getattr(screen, "name", lambda: "Unknown")())
        self._track_screen_geometry(screen)
        self.update_screen_topology()

    def _on_screen_removed(self, screen: QScreen) -> None:
        logger.info("Display removed: %s", getattr(screen, "name", lambda: "Unknown")())
        screen_id = id(screen)
        self._monitored_screens.discard(screen_id)
        self.update_screen_topology()

    def _on_geometry_changed(self, geometry: QRect) -> None:
        logger.info("Display geometry changed: %s", geometry)
        self.update_screen_topology()

    def update_screen_topology(self) -> None:
        """Emit topology changed notification to recalculate layout."""
        self.topology_changed.emit()
