"""
core/integrations/antigravity_controller.py — Google Antigravity IDE Agent Chat Integration.

Provides reliable window identification, foreground focus, chat input focusing, and
safe prompt injection with clipboard preservation for the Google Antigravity IDE.
"""
from __future__ import annotations

import logging
import os
import platform
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from core import appidentity, outcome
from core.lazyimport import LazyModule, installed

logger = logging.getLogger("JARVIS.Integration.Antigravity")

_PYAUTOGUI = installed("pyautogui")
_PYPERCLIP = installed("pyperclip")

pyautogui = LazyModule("pyautogui")
pyperclip = LazyModule("pyperclip")

_OS = platform.system()


class AntigravityController:
    """
    Controller for interacting directly with Google Antigravity IDE agent chat interface.
    """

    def __init__(self) -> None:
        self._target_process_name = "antigravity ide"

    def is_running(self) -> bool:
        """Check whether Google Antigravity IDE is currently running."""
        try:
            matches = appidentity.running("antigravity", include_self=True)
            if matches:
                return True
        except Exception:
            pass

        # Direct psutil fallback
        try:
            import psutil
            for p in psutil.process_iter(["name"]):
                name = (p.info.get("name") or "").lower()
                if "antigravity" in name:
                    return True
        except Exception:
            pass

        return False

    def find_window_handle(self) -> Optional[int]:
        """Locate the primary HWND for the Antigravity IDE window on Windows."""
        if _OS != "Windows":
            return None

        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)

            hwnds: List[int] = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def _enum_win(hwnd, _lparam):
                if user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value.lower()
                        if "antigravity" in title:
                            hwnds.append(int(hwnd))
                return True

            user32.EnumWindows(WNDENUMPROC(_enum_win), 0)
            if hwnds:
                return hwnds[0]

            # Try by process match handles
            matches = appidentity.running("antigravity", include_self=True)
            for m in matches:
                proc_hwnds = appidentity._hwnds_for(m.pid)
                if proc_hwnds:
                    return proc_hwnds[0]
        except Exception as exc:
            logger.warning("Error finding Antigravity window: %s", exc)

        return None

    def focus_window(self) -> bool:
        """Bring Google Antigravity IDE window to the foreground."""
        if not self.is_running():
            return False

        # 1. Native appidentity focus_window
        if appidentity.focus_window("Antigravity"):
            time.sleep(0.15)
            return True

        # 2. Match-based focus
        matches = appidentity.running("antigravity", include_self=True)
        if matches and appidentity.focus(matches[0]):
            time.sleep(0.15)
            return True

        # 3. Direct HWND raise
        hwnd = self.find_window_handle()
        if hwnd and appidentity._raise_hwnd(hwnd):
            time.sleep(0.15)
            return True

        # 4. WScript.Shell AppActivate fallback on Windows
        if _OS == "Windows":
            try:
                script = '(New-Object -ComObject WScript.Shell).AppActivate("Antigravity")'
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                    capture_output=True, timeout=3,
                )
                if r.returncode == 0:
                    time.sleep(0.15)
                    return True
            except Exception:
                pass

        return False

    def focus_chat_input(self) -> bool:
        """
        Focus the Agent Chat input field in Google Antigravity IDE.
        In Antigravity / Cursor / VS Code, Ctrl+L focuses the Agent chat conversation input.
        """
        if not _PYAUTOGUI:
            logger.warning("pyautogui is not installed; cannot send focus shortcut")
            return False

        try:
            # Ctrl+L focuses the chat / conversation input in Antigravity IDE
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.08)
            return True
        except Exception as exc:
            logger.warning("Failed to send chat input shortcut: %s", exc)
            return False

    def deliver_prompt(
        self,
        prompt: str,
        submit: bool = False,
        focus_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Safely delivers prompt text to the Google Antigravity IDE agent chat input.

        Parameters:
        - prompt: The text/code/query to insert.
        - submit: If True, sends Enter to immediately execute/submit the prompt.
                  If False (default), inserts text and leaves it for user review.
        - focus_only: If True, only focuses the window and input without inserting text.

        Preserves user clipboard contents before and after insertion.
        """
        cleaned_prompt = str(prompt or "").strip()
        if not cleaned_prompt and not focus_only:
            return {
                "success": False,
                "error": "No prompt text provided to insert.",
                "status": "failed",
            }

        # Step 1: Verify Antigravity is running
        if not self.is_running():
            return {
                "success": False,
                "error": (
                    "Google Antigravity IDE is not running. "
                    "Please open Antigravity IDE before sending prompts."
                ),
                "status": "failed",
                "running": False,
            }

        # Step 2: Focus Antigravity window
        if not self.focus_window():
            logger.warning("Could not focus Antigravity window; attempting to continue")

        # Step 3: Focus agent chat input
        self.focus_chat_input()

        if focus_only:
            return {
                "success": True,
                "status": "done",
                "action": "focus_only",
                "message": "Antigravity IDE focused and chat input selected.",
            }

        # Step 4: Clipboard-safe delivery
        if not _PYPERCLIP or not _PYAUTOGUI:
            return {
                "success": False,
                "error": "pyperclip or pyautogui is not available for safe prompt insertion.",
                "status": "failed",
            }

        previous_clipboard: Optional[str] = None
        try:
            try:
                previous_clipboard = pyperclip.paste()
            except Exception:
                previous_clipboard = None

            # Copy target prompt to clipboard
            pyperclip.copy(cleaned_prompt)
            time.sleep(0.05)

            # Paste into the focused input field
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.08)

            # Submit if explicitly requested
            if submit:
                pyautogui.press("enter")
                time.sleep(0.05)

            return {
                "success": True,
                "status": "done",
                "action": "deliver_prompt",
                "chars": len(cleaned_prompt),
                "submitted": bool(submit),
                "message": (
                    f"Prompt ({len(cleaned_prompt)} chars) {'submitted to' if submit else 'inserted into'} "
                    f"Antigravity IDE chat."
                ),
            }
        except Exception as exc:
            logger.error("Error during prompt delivery to Antigravity: %s", exc)
            return {
                "success": False,
                "error": f"Failed to deliver prompt to Antigravity: {exc}",
                "status": "failed",
            }
        finally:
            # Restore previous clipboard content after small delay to let paste finish
            if previous_clipboard is not None:
                try:
                    time.sleep(0.15)
                    pyperclip.copy(previous_clipboard)
                except Exception:
                    pass


_controller_instance: Optional[AntigravityController] = None


def get_antigravity_controller() -> AntigravityController:
    """Return the singleton instance of AntigravityController."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = AntigravityController()
    return _controller_instance

