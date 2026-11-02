"""
core/desktop/cursor_controller.py — Observation-driven human-like cursor and keyboard controller.
"""
from __future__ import annotations

import logging
import math
import random
import time
from typing import Optional, Tuple

from core.lazyimport import LazyModule, installed
from .access_manager import PermissionScope, get_access_manager

logger = logging.getLogger("JARVIS.CursorController")

_PYAUTOGUI = installed("pyautogui")
_PYPERCLIP = installed("pyperclip")

pyautogui = LazyModule("pyautogui")
pyperclip = LazyModule("pyperclip")


class CursorController:
    """Dispatches human-like mouse trajectories and safe keyboard actions with permission checks."""

    def __init__(self):
        self._access_mgr = get_access_manager()

    def move_to(
        self,
        target_x: int,
        target_y: int,
        duration: Optional[float] = None,
        human_like: bool = True,
    ) -> bool:
        """Move cursor to (target_x, target_y) using a smooth cubic Bézier trajectory."""
        if not self._access_mgr.check_permission(PermissionScope.MOUSE_MOVE):
            logger.warning("Cursor move denied: MOUSE_MOVE permission not granted.")
            return False

        if not _PYAUTOGUI:
            logger.error("PyAutoGUI not installed; cannot move cursor.")
            return False

        start_x, start_y = pyautogui.position()
        dist = math.hypot(target_x - start_x, target_y - start_y)
        if dist < 4:
            pyautogui.moveTo(target_x, target_y)
            return True

        if duration is None:
            # Dynamically calculate duration from distance: 200ms to 600ms
            duration = max(0.20, min(0.65, 0.15 + (dist / 2500.0)))

        if not human_like:
            pyautogui.moveTo(target_x, target_y, duration=duration)
            return True

        # Cubic Bézier curve generation:
        # P0 = (start_x, start_y)
        # P3 = (target_x, target_y)
        # P1, P2 = randomized control points perturbed perpendicularly
        dx = target_x - start_x
        dy = target_y - start_y
        normal_x, normal_y = -dy, dx
        norm_len = math.hypot(normal_x, normal_y) or 1.0
        normal_x /= norm_len
        normal_y /= norm_len

        deviation = (dist * 0.15) * random.uniform(-1.0, 1.0)
        p1_x = start_x + (dx * 0.3) + (normal_x * deviation)
        p1_y = start_y + (dy * 0.3) + (normal_y * deviation)

        deviation2 = (dist * 0.10) * random.uniform(-1.0, 1.0)
        p2_x = start_x + (dx * 0.7) + (normal_x * deviation2)
        p2_y = start_y + (dy * 0.7) + (normal_y * deviation2)

        steps = max(15, int(dist / 15))
        for step in range(1, steps + 1):
            t = step / float(steps)
            # Ease-in-out smoothing: t^2 * (3 - 2t)
            t_smooth = t * t * (3.0 - 2.0 * t)

            # Cubic Bézier formula
            bx = ((1 - t_smooth) ** 3) * start_x + \
                 3 * ((1 - t_smooth) ** 2) * t_smooth * p1_x + \
                 3 * (1 - t_smooth) * (t_smooth ** 2) * p2_x + \
                 (t_smooth ** 3) * target_x

            by = ((1 - t_smooth) ** 3) * start_y + \
                 3 * ((1 - t_smooth) ** 2) * t_smooth * p1_y + \
                 3 * (1 - t_smooth) * (t_smooth ** 2) * p2_y + \
                 (t_smooth ** 3) * target_y

            # Micro-jitter
            if step < steps:
                bx += random.uniform(-1.0, 1.0)
                by += random.uniform(-1.0, 1.0)

            pyautogui.moveTo(int(round(bx)), int(round(by)))
            time.sleep(duration / float(steps))

        pyautogui.moveTo(target_x, target_y)
        return True

    def click(
        self,
        target_x: Optional[int] = None,
        target_y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
        hover_delay: float = 0.06,
    ) -> bool:
        """Move (if specified) and click with hover-settling delay."""
        if not self._access_mgr.check_permission(PermissionScope.MOUSE_CLICK):
            logger.warning("Mouse click denied: MOUSE_CLICK permission not granted.")
            return False

        if not _PYAUTOGUI:
            return False

        if target_x is not None and target_y is not None:
            self.move_to(target_x, target_y)
            time.sleep(hover_delay)

        pyautogui.click(button=button, clicks=clicks, interval=0.12)
        return True

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return self.click(x, y, button="right")

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return self.click(x, y, button="left", clicks=2)

    def drag_to(
        self,
        start_x: int,
        start_y: int,
        target_x: int,
        target_y: int,
        button: str = "left",
    ) -> bool:
        """Smoothly click and drag from (start_x, start_y) to (target_x, target_y)."""
        if not self._access_mgr.check_permission(PermissionScope.MOUSE_DRAG):
            logger.warning("Mouse drag denied: MOUSE_DRAG permission not granted.")
            return False

        self.move_to(start_x, start_y)
        time.sleep(0.08)
        pyautogui.mouseDown(button=button)
        time.sleep(0.05)
        self.move_to(target_x, target_y)
        time.sleep(0.08)
        pyautogui.mouseUp(button=button)
        return True

    def scroll(self, amount: int, direction: str = "down") -> bool:
        """Scroll mouse wheel."""
        if not self._access_mgr.check_permission(PermissionScope.MOUSE_MOVE):
            return False

        clicks = -abs(amount) if direction.lower() == "down" else abs(amount)
        pyautogui.scroll(clicks)
        return True

    def type_text(
        self,
        text: str,
        clear_first: bool = False,
        use_clipboard: bool = False,
    ) -> bool:
        """Type text with realistic keystroke latency or clipboard injection for Unicode."""
        if not self._access_mgr.check_permission(PermissionScope.KEYBOARD_INPUT):
            logger.warning("Keyboard input denied: KEYBOARD_INPUT permission not granted.")
            return False

        if clear_first:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.04)
            pyautogui.press("backspace")
            time.sleep(0.04)

        # Detect whether Unicode or multi-line requires clipboard paste
        needs_clipboard = use_clipboard or any(ord(c) > 127 or c in "\n\t" for c in text) or len(text) > 40
        if needs_clipboard and _PYPERCLIP:
            old_clip = pyperclip.paste()
            try:
                pyperclip.copy(text)
                time.sleep(0.04)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.06)
            finally:
                # Restore previous clipboard content after short delay
                threading.Timer(0.3, lambda: pyperclip.copy(old_clip)).start()
        else:
            for char in text:
                pyautogui.write(char)
                time.sleep(random.uniform(0.015, 0.045))

        return True

    def hotkey(self, *keys: str) -> bool:
        """Dispatch a keyboard shortcut (e.g. 'ctrl', 'c')."""
        if not self._access_mgr.check_permission(PermissionScope.KEYBOARD_INPUT):
            return False
        pyautogui.hotkey(*keys)
        return True

    def press(self, key: str) -> bool:
        """Press a single key (e.g. 'enter', 'tab', 'esc')."""
        if not self._access_mgr.check_permission(PermissionScope.KEYBOARD_INPUT):
            return False
        pyautogui.press(key)
        return True


_cursor_controller_instance: Optional[CursorController] = None


def get_cursor_controller() -> CursorController:
    global _cursor_controller_instance
    if _cursor_controller_instance is None:
        _cursor_controller_instance = CursorController()
    return _cursor_controller_instance
