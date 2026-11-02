"""
core/desktop/emergency_stop.py — Instant Emergency Stop Controller for JARVIS MARK LVI.

Provides redundant, immediate fail-safe interrupts:
1. Global Hotkey: Ctrl + Alt + Escape (or Esc when desktop automation is running)
2. Mouse Flick Failsafe: Moving cursor rapidly to any screen corner trips PyAutoGUI / MSS guard
3. Input Release: Unconditionally releases any held modifier keys and mouse buttons
4. State Termination: Forces DesktopAccessState to ERROR / DISABLED and cancels running tasks
"""
from __future__ import annotations

import ctypes
import logging
import platform
import threading
import time
from typing import Callable, Optional

from core.lazyimport import LazyModule, installed
from .access_manager import DesktopAccessState, get_access_manager

logger = logging.getLogger("JARVIS.EmergencyStop")
_PYAUTOGUI = installed("pyautogui")
pyautogui = LazyModule("pyautogui")


class EmergencyStopController:
    """Monitors emergency abort conditions and halts all desktop automation instantly."""

    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: list[Callable[[str], None]] = []
        self._manager = get_access_manager()

        # Connect state listener so watchdog only runs when control or observe is active
        self._manager.register_state_listener(self._on_access_state_changed)

    def _on_access_state_changed(self, state: DesktopAccessState, details: dict) -> None:
        if state in (DesktopAccessState.CONTROL_ENABLED, DesktopAccessState.OBSERVE_ONLY):
            self.start_watchdog()
        else:
            self.stop_watchdog()

    def register_callback(self, cb: Callable[[str], None]) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def trigger_halt(self, reason: str = "manual_trigger") -> None:
        """Execute the immediate fail-safe halt sequence."""
        logger.warning("🚨 EMERGENCY STOP TRIGGERED: %s", reason)

        # 1. Force hardware input release
        self.release_all_inputs()

        # 2. Tell DesktopAccessManager to halt
        self._manager.emergency_halt(reason)

        # 3. Notify any registered callbacks (audio alert, UI flash)
        for cb in list(self._callbacks):
            try:
                cb(reason)
            except Exception as e:
                logger.error("Error in emergency stop callback: %s", e)

    def release_all_inputs(self) -> None:
        """Unconditionally release all held keys and mouse buttons."""
        if not _PYAUTOGUI:
            return

        try:
            # Release mouse buttons
            for btn in ("left", "middle", "right"):
                try:
                    pyautogui.mouseUp(button=btn)
                except Exception:
                    pass

            # Release modifier keys and common control keys
            modifiers = [
                "ctrl", "ctrlleft", "ctrlright",
                "alt", "altleft", "altright",
                "shift", "shiftleft", "shiftright",
                "win", "winleft", "winright",
                "esc", "space", "enter", "tab"
            ]
            for key in modifiers:
                try:
                    pyautogui.keyUp(key)
                except Exception:
                    pass
            logger.info("Released all held keyboard and mouse inputs.")
        except Exception as e:
            logger.error("Failed to release all inputs: %s", e)

    def start_watchdog(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._monitor_thread = threading.Thread(
                target=self._watchdog_loop,
                name="JarvisEmergencyStopWatchdog",
                daemon=True,
            )
            self._monitor_thread.start()
            logger.info("Emergency Stop watchdog started.")

    def stop_watchdog(self) -> None:
        with self._lock:
            self._running = False
            self._monitor_thread = None

    def _watchdog_loop(self) -> None:
        """Polls for Ctrl+Alt+Escape or corner flick while automation is active."""
        is_windows = platform.system() == "Windows"
        user32 = ctypes.windll.user32 if is_windows else None

        # Virtual key codes on Windows:
        # VK_ESCAPE = 0x1B, VK_CONTROL = 0x11, VK_MENU (Alt) = 0x12
        VK_ESCAPE = 0x1B
        VK_CONTROL = 0x11
        VK_MENU = 0x12

        while self._running:
            try:
                # 1. Hotkey check: Ctrl + Alt + Escape
                if is_windows and user32 is not None:
                    ctrl_down = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                    alt_down = bool(user32.GetAsyncKeyState(VK_MENU) & 0x8000)
                    esc_down = bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)

                    if (ctrl_down and alt_down and esc_down) or (esc_down and self._manager.is_control_enabled):
                        self.trigger_halt("global_hotkey_ctrl_alt_esc")
                        break

                # 2. Mouse corner check (PyAutoGUI failsafe corner)
                if _PYAUTOGUI and self._manager.is_control_enabled:
                    try:
                        x, y = pyautogui.position()
                        sw, sh = pyautogui.size()
                        margin = 4
                        in_corner = (
                            (x <= margin and y <= margin) or
                            (x >= sw - margin and y <= margin) or
                            (x <= margin and y >= sh - margin) or
                            (x >= sw - margin and y >= sh - margin)
                        )
                        if in_corner:
                            self.trigger_halt("mouse_corner_flick")
                            break
                    except Exception:
                        pass

                time.sleep(0.04)  # ~25Hz check rate
            except Exception as e:
                logger.error("Watchdog loop error: %s", e)
                time.sleep(0.1)


# Global singleton
_emergency_stop_instance: Optional[EmergencyStopController] = None
_es_lock = threading.Lock()


def get_emergency_stop() -> EmergencyStopController:
    global _emergency_stop_instance
    with _es_lock:
        if _emergency_stop_instance is None:
            _emergency_stop_instance = EmergencyStopController()
        return _emergency_stop_instance
