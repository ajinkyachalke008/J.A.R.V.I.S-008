"""
core/desktop/interaction_context.py — Conversational memory and state tracker for desktop interactions.
"""
from __future__ import annotations

import logging
import platform
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("JARVIS.InteractionContext")

_SESSION_TTL_SECONDS = 90.0


@dataclass
class InteractionSession:
    """Snapshot of active interaction state across multi-turn conversational commands."""
    active_hwnd: int = 0
    window_title: str = ""
    app_name: str = ""
    window_rect: Tuple[int, int, int, int] = (0, 0, 0, 0)  # (left, top, right, bottom)
    container_bounds: Optional[Tuple[int, int, int, int]] = None  # (left, top, width, height)
    container_type: str = "main"
    last_direction: str = "down"
    last_magnitude: str = "normal"
    last_action: str = ""
    last_targets: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)

    def is_valid(self, max_age: float = _SESSION_TTL_SECONDS) -> bool:
        if self.active_hwnd == 0:
            return False
        return (time.time() - self.last_updated) <= max_age

    @property
    def window_center(self) -> Tuple[int, int]:
        l, t, r, b = self.window_rect
        if r > l and b > t:
            # Place slightly below center (avoid browser toolbars / title bars)
            return (l + (r - l) // 2, t + int((b - t) * 0.55))
        return (960, 540)


class InteractionContextManager:
    """Maintains desktop interaction state and handles context invalidation on window switches."""

    def __init__(self):
        self._current_session: Optional[InteractionSession] = None

    def get_active_window_info(self) -> Tuple[int, str, Tuple[int, int, int, int]]:
        """Get (hwnd, title, (left, top, right, bottom)) for current foreground window."""
        if platform.system() != "Windows":
            return (0, "", (0, 0, 1920, 1080))
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return (0, "", (0, 0, 1920, 1080))
            title = win32gui.GetWindowText(hwnd) or ""
            rect = win32gui.GetWindowRect(hwnd) or (0, 0, 1920, 1080)
            return (hwnd, title, rect)
        except Exception as e:
            logger.debug("Failed to get foreground window info: %s", e)
            return (0, "", (0, 0, 1920, 1080))

    def get_or_create_session(self, force_refresh: bool = False) -> InteractionSession:
        """Retrieves or refreshes the interaction session for the current foreground window."""
        hwnd, title, rect = self.get_active_window_info()
        now = time.time()

        if (
            not force_refresh
            and self._current_session is not None
            and self._current_session.is_valid()
            and self._current_session.active_hwnd == hwnd
        ):
            # Still valid session in same window
            self._current_session.last_updated = now
            return self._current_session

        # Window changed or expired: construct new session
        app_name = self._infer_app_name(title)
        self._current_session = InteractionSession(
            active_hwnd=hwnd,
            window_title=title,
            app_name=app_name,
            window_rect=rect,
            last_updated=now,
        )
        logger.debug(
            "Created interaction session: hwnd=%d, app='%s', title='%s'",
            hwnd,
            app_name,
            title[:40],
        )
        return self._current_session

    def update_scroll_state(
        self,
        direction: str,
        magnitude: str,
        container_type: str = "main",
        container_bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> InteractionSession:
        """Record the latest scroll operation to enable 'again' and continuous chaining."""
        session = self.get_or_create_session()
        session.last_direction = direction
        session.last_magnitude = magnitude
        session.last_action = "scroll"
        session.container_type = container_type
        if container_bounds:
            session.container_bounds = container_bounds
        session.last_updated = time.time()
        return session

    def update_detected_targets(self, targets: List[Dict[str, Any]]) -> None:
        """Cache detected interactive targets on screen."""
        session = self.get_or_create_session()
        session.last_targets = targets
        session.last_updated = time.time()

    def get_target_centroid(self, container_type: str = "main") -> Tuple[int, int]:
        """Resolves target coordinate (X, Y) to position cursor before dispatching scroll wheel."""
        session = self.get_or_create_session()

        # If a specific container bounding box is registered and matches container_type
        if session.container_bounds and session.container_type == container_type:
            cx, cy, cw, ch = session.container_bounds
            return (cx + cw // 2, cy + ch // 2)

        l, t, r, b = session.window_rect
        w = max(100, r - l)
        h = max(100, b - t)

        if container_type == "sidebar":
            # Position inside the left ~18% of the window
            return (l + int(w * 0.12), t + int(h * 0.50))
        elif container_type == "comments":
            # In YouTube and many web layouts, comments / secondary panel is on right ~30%
            return (l + int(w * 0.80), t + int(h * 0.50))
        else:
            # Main feed / center viewport (45% X, 55% Y to avoid headers and toolbars)
            return (l + int(w * 0.50), t + int(h * 0.55))

    def clear(self) -> None:
        """Reset the active session."""
        self._current_session = None

    def _infer_app_name(self, title: str) -> str:
        low = title.lower()
        if "youtube" in low:
            return "YouTube"
        elif "chrome" in low:
            return "Chrome"
        elif "edge" in low:
            return "Edge"
        elif "firefox" in low:
            return "Firefox"
        elif "visual studio code" in low or "vscode" in low:
            return "VS Code"
        elif "file explorer" in low:
            return "File Explorer"
        return "DesktopApp"


_interaction_context_instance: Optional[InteractionContextManager] = None


def get_interaction_context() -> InteractionContextManager:
    global _interaction_context_instance
    if _interaction_context_instance is None:
        _interaction_context_instance = InteractionContextManager()
    return _interaction_context_instance

