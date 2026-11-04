"""
core/desktop/universal_scroll.py — Universal scrolling engine for browsers, panels, and desktop applications.
"""
from __future__ import annotations

import logging
import platform
import threading
import time
from typing import Any, Dict, Optional, Tuple

from core import outcome
from core.lazyimport import LazyModule, installed
from .access_manager import PermissionScope, get_access_manager
from .action_verifier import get_action_verifier
from .cursor_controller import get_cursor_controller
from .emergency_stop import EmergencyStopController
from .interaction_context import get_interaction_context
from .scroll_intent import (
    ContainerTarget,
    ScrollDirection,
    ScrollIntent,
    ScrollMagnitude,
    parse_scroll_intent,
)

logger = logging.getLogger("JARVIS.UniversalScroll")

_PYAUTOGUI = installed("pyautogui")
pyautogui = LazyModule("pyautogui")

# Standard Windows wheel delta constant
WHEEL_DELTA = 120

# Delta calibration table for vertical scrolling (positive for UP, negative for DOWN)
_DELTA_MAP: Dict[ScrollMagnitude, int] = {
    ScrollMagnitude.SUBTLE: 240,    # 2 notches
    ScrollMagnitude.NORMAL: 600,    # 5 notches (~3 lines per notch)
    ScrollMagnitude.MORE: 1200,     # 10 notches
    ScrollMagnitude.PAGE: 1800,     # 15 notches (~1 viewport page)
    ScrollMagnitude.EXTREME: 9999,  # Home / End boundary
}


class UniversalScrollEngine:
    """Executes context-aware, container-centered, and continuous scrolling across any active surface."""

    def __init__(self):
        self._access_mgr = get_access_manager()
        self._cursor = get_cursor_controller()
        self._context_mgr = get_interaction_context()
        self._verifier = get_action_verifier()

        self._continuous_thread: Optional[threading.Thread] = None
        self._continuous_stop_event = threading.Event()
        self._continuous_lock = threading.Lock()

        # Connect failsafe so emergency stop halts continuous scrolling immediately
        from .access_manager import DesktopAccessState
        def _on_state_change(state, details):
            if state != DesktopAccessState.CONTROL_ENABLED:
                self.stop_continuous_scroll()
        self._access_mgr.register_state_listener(_on_state_change)

    @property
    def is_continuously_scrolling(self) -> bool:
        with self._continuous_lock:
            return self._continuous_thread is not None and self._continuous_thread.is_alive()

    def stop_continuous_scroll(self) -> str:
        """Immediately abort any active continuous scroll loop."""
        with self._continuous_lock:
            if self._continuous_thread is not None and self._continuous_thread.is_alive():
                self._continuous_stop_event.set()
                self._continuous_thread.join(timeout=0.6)
                self._continuous_thread = None
                logger.info("Continuous scroll stopped.")
                return outcome.done("stop_scroll", status="halted")
        return outcome.done("stop_scroll", status="idle")

    def execute_intent(self, intent: ScrollIntent, verify: bool = True) -> str:
        """Executes a parsed ScrollIntent with container targeting, repetition, and verification."""
        # 1. Check for Stop Intent
        if intent.is_stop:
            return self.stop_continuous_scroll()

        # Stop any previous continuous scroll before initiating a new scroll
        if self.is_continuously_scrolling:
            self.stop_continuous_scroll()

        # 2. Check Permissions
        if not self._access_mgr.is_control_enabled:
            return outcome.failed(
                "scroll",
                "Desktop access is disabled. Please enable 'FULL DESKTOP ACCESS' in the JARVIS HUD first.",
            )

        # 3. Handle Repeated Command ("scroll down again", "more", "keep going")
        session = self._context_mgr.get_or_create_session()
        direction = intent.direction
        magnitude = intent.magnitude
        container_type = intent.container.value

        if intent.is_repeat and session.last_action == "scroll":
            direction = ScrollDirection(session.last_direction) if session.last_direction in [d.value for d in ScrollDirection] else direction
            # If user said "more" or "further", upgrade magnitude
            if magnitude == ScrollMagnitude.NORMAL and session.last_magnitude == ScrollMagnitude.NORMAL:
                magnitude = ScrollMagnitude.MORE
            container_type = session.container_type

        # 4. Handle Continuous Mode
        if intent.is_continuous:
            return self._start_continuous_scroll(direction, magnitude, container_type)

        # 5. Position Cursor over Target Container Centroid
        target_x, target_y = self._context_mgr.get_target_centroid(container_type)
        self._ensure_cursor_positioned(target_x, target_y)

        # 6. Execute Scrolling via Priority Ladder
        delta_base = _DELTA_MAP.get(magnitude, 600)
        action_name = f"scroll_{direction.value}"

        def _do_scroll():
            return self._dispatch_scroll_event(direction, delta_base)

        if not verify:
            ok = _do_scroll()
            self._context_mgr.update_scroll_state(direction.value, magnitude.value, container_type)
            return outcome.done(action_name, direction=direction.value, magnitude=magnitude.value)

        # Execute verified scroll
        active_rect = session.container_bounds or (
            session.window_rect[0],
            session.window_rect[1],
            max(200, session.window_rect[2] - session.window_rect[0]),
            max(200, session.window_rect[3] - session.window_rect[1]),
        )

        res = self._verifier.verify_action(
            action_name=action_name,
            target_desc=f"{session.app_name} ({container_type})",
            action_callable=_do_scroll,
            region=active_rect,
            settle_delay=0.15,
        )

        self._context_mgr.update_scroll_state(direction.value, magnitude.value, container_type)
        return res

    def scroll(
        self,
        command_or_direction: str = "down",
        amount: Optional[str] = None,
        container: str = "main",
        verify: bool = True,
    ) -> str:
        """Convenience dispatcher taking natural language or explicit arguments."""
        if any(w in command_or_direction.lower() for w in ("scroll", "move", "go", "again", "stop", "page", "top", "bottom")):
            intent = parse_scroll_intent(command_or_direction)
            if amount:
                try:
                    intent = ScrollIntent(
                        direction=intent.direction,
                        magnitude=ScrollMagnitude(amount.lower()),
                        is_repeat=intent.is_repeat,
                        is_continuous=intent.is_continuous,
                        is_stop=intent.is_stop,
                        container=ContainerTarget(container.lower()) if container in [c.value for c in ContainerTarget] else intent.container,
                        raw_command=command_or_direction,
                    )
                except Exception:
                    pass
            return self.execute_intent(intent, verify=verify)

        # Explicit arguments
        try:
            dir_enum = ScrollDirection(command_or_direction.lower())
        except ValueError:
            dir_enum = ScrollDirection.DOWN

        try:
            mag_enum = ScrollMagnitude((amount or "normal").lower())
        except ValueError:
            mag_enum = ScrollMagnitude.NORMAL

        try:
            cont_enum = ContainerTarget(container.lower())
        except ValueError:
            cont_enum = ContainerTarget.MAIN

        intent = ScrollIntent(
            direction=dir_enum,
            magnitude=mag_enum,
            container=cont_enum,
            raw_command=f"scroll {command_or_direction} {amount or 'normal'}",
        )
        return self.execute_intent(intent, verify=verify)

    def _ensure_cursor_positioned(self, target_x: int, target_y: int) -> None:
        """Moves cursor to the container centroid if not already within 80px."""
        if not _PYAUTOGUI:
            return
        curr_x, curr_y = pyautogui.position()
        dist = ((curr_x - target_x) ** 2 + (curr_y - target_y) ** 2) ** 0.5
        if dist > 80:
            self._cursor.move_to(target_x, target_y, duration=0.18, human_like=True)
            time.sleep(0.04)

    def _dispatch_scroll_event(self, direction: ScrollDirection, delta: int) -> bool:
        """Dispatches physical or virtual scroll events with proper Windows delta calibration."""
        if not _PYAUTOGUI:
            return False

        # 1. Extreme Boundaries: Top / Bottom
        if direction == ScrollDirection.TO_BOTTOM:
            pyautogui.hotkey("ctrl", "end")
            time.sleep(0.08)
            pyautogui.press("end")
            return True

        if direction == ScrollDirection.TO_TOP:
            pyautogui.hotkey("ctrl", "home")
            time.sleep(0.08)
            pyautogui.press("home")
            return True

        # 2. Page Navigation
        if direction == ScrollDirection.PAGE_DOWN:
            pyautogui.press("pagedown")
            return True

        if direction == ScrollDirection.PAGE_UP:
            pyautogui.press("pageup")
            return True

        # 3. Horizontal Scrolling
        if direction == ScrollDirection.LEFT:
            pyautogui.hscroll(-delta)
            return True

        if direction == ScrollDirection.RIGHT:
            pyautogui.hscroll(delta)
            return True

        # 4. Calibrated Vertical Scrolling
        # Positive delta = UP, Negative delta = DOWN
        wheel_clicks = -delta if direction == ScrollDirection.DOWN else delta

        if platform.system() == "Windows":
            try:
                import ctypes
                # 0x0800 = MOUSEEVENTF_WHEEL
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, wheel_clicks, 0)
                return True
            except Exception as e:
                logger.debug("Win32 mouse_event failed, falling back to pyautogui.scroll: %s", e)

        pyautogui.scroll(wheel_clicks)
        return True

    def _start_continuous_scroll(
        self,
        direction: ScrollDirection,
        magnitude: ScrollMagnitude,
        container_type: str,
    ) -> str:
        """Spawns background worker for continuous scrolling."""
        target_x, target_y = self._context_mgr.get_target_centroid(container_type)
        self._ensure_cursor_positioned(target_x, target_y)

        with self._continuous_lock:
            self._continuous_stop_event.clear()
            step_delta = 160 if magnitude == ScrollMagnitude.SUBTLE else (320 if magnitude == ScrollMagnitude.MORE else 240)
            interval = 0.08

            def _worker():
                logger.info("Continuous scroll worker running [%s]...", direction.value)
                while not self._continuous_stop_event.is_set():
                    self._dispatch_scroll_event(direction, step_delta)
                    time.sleep(interval)
                logger.info("Continuous scroll worker terminated.")

            self._continuous_thread = threading.Thread(target=_worker, daemon=True, name="ContinuousScroll")
            self._continuous_thread.start()

        self._context_mgr.update_scroll_state(direction.value, "continuous", container_type)
        return outcome.done(
            "continuous_scroll",
            direction=direction.value,
            container=container_type,
            status="scrolling",
            instruction="Say 'stop' or 'halt' to pause scrolling.",
        )


_universal_scroll_instance: Optional[UniversalScrollEngine] = None


def get_universal_scroll() -> UniversalScrollEngine:
    global _universal_scroll_instance
    if _universal_scroll_instance is None:
        _universal_scroll_instance = UniversalScrollEngine()
    return _universal_scroll_instance
