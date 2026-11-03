"""
core/desktop/action_verifier.py — Pre/post action execution verification for JARVIS MARK LVI.
"""
from __future__ import annotations

import logging
import platform
import time
from typing import Any, Callable, Optional, Tuple

import numpy as np
from PIL import Image

from core import outcome
from .screen_capture import get_screen_capture

logger = logging.getLogger("JARVIS.ActionVerifier")


class ActionVerifier:
    """Verifies that an atomic or composite desktop action produced the intended effect."""

    def __init__(self):
        self._capture = get_screen_capture()

    def get_window_snapshot(self) -> dict[str, Any]:
        """Captures active foreground window metadata."""
        if platform.system() != "Windows":
            return {"hwnd": 0, "title": ""}
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) if hwnd else ""
            rect = win32gui.GetWindowRect(hwnd) if hwnd else (0, 0, 0, 0)
            return {"hwnd": hwnd, "title": title, "rect": rect}
        except Exception:
            return {"hwnd": 0, "title": ""}

    def verify_action(
        self,
        action_name: str,
        target_desc: str,
        action_callable: Callable[[], Any],
        expected_focus_change: bool = False,
        region: Optional[Tuple[int, int, int, int]] = None,
        settle_delay: float = 0.20,
    ) -> str:
        """Executes action_callable and checks pre/post state changes."""
        pre_win = self.get_window_snapshot()
        pre_img_arr = None

        try:
            if region:
                img, _, _ = self._capture.capture_region(*region, compress=False)
                pre_img_arr = np.array(img)
        except Exception:
            pass

        # Execute
        try:
            result = action_callable()
        except Exception as e:
            logger.error("Action '%s' failed during execution: %s", action_name, e)
            return outcome.failed(action_name, str(e), target=target_desc)

        time.sleep(settle_delay)
        post_win = self.get_window_snapshot()

        # Check 1: Focus change
        focus_changed = (pre_win["hwnd"] != post_win["hwnd"])
        if expected_focus_change and focus_changed:
            return outcome.done(action_name, target=target_desc, active_window=post_win["title"])

        # Check 2: Visual delta
        pixel_diff_pct = 0.0
        if region and pre_img_arr is not None:
            try:
                post_img, _, _ = self._capture.capture_region(*region, compress=False)
                post_img_arr = np.array(post_img)
                if pre_img_arr.shape == post_img_arr.shape:
                    diff = np.abs(pre_img_arr.astype("int32") - post_img_arr.astype("int32"))
                    pixel_diff_pct = float(np.mean(diff > 10) * 100.0)
            except Exception:
                pass

        title_changed = (pre_win["title"] != post_win["title"])

        if focus_changed or title_changed or pixel_diff_pct > 0.4:
            return outcome.done(
                action_name,
                target=target_desc,
                window=post_win["title"],
                visual_diff=f"{pixel_diff_pct:.1f}%",
            )

        # Request accepted but no change detected
        return outcome.unverified(
            action_name,
            "No visible screen change or focus change detected",
            target=target_desc,
        )


_verifier_instance: Optional[ActionVerifier] = None


def get_action_verifier() -> ActionVerifier:
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = ActionVerifier()
    return _verifier_instance
