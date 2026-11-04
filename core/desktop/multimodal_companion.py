"""
core/desktop/multimodal_companion.py — Real-time multimodal desktop companion engine.
"""
from __future__ import annotations

import io
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import gemini, outcome
from core.desktop.access_manager import DesktopAccessState, PermissionScope, get_access_manager
from core.desktop.interaction_context import get_interaction_context
from core.desktop.screen_capture import get_screen_capture
from core.desktop.screen_diff import (
    ScreenSnapshot,
    SemanticScreenDiff,
    get_screen_diff_engine,
)

logger = logging.getLogger("JARVIS.MultimodalCompanion")


class MultimodalCompanion:
    """Coordinates conversational Gemini perception with desktop screen understanding and change tracking."""

    def __init__(self):
        self._access_mgr = get_access_manager()
        self._capture = get_screen_capture()
        self._diff_engine = get_screen_diff_engine()
        self._context_mgr = get_interaction_context()

        # Continuous awareness session state
        self._awareness_thread: Optional[threading.Thread] = None
        self._awareness_stop_event = threading.Event()
        self._awareness_paused = threading.Event()
        self._awareness_lock = threading.Lock()
        self._last_observation_summary = ""
        self._last_snapshot: Optional[ScreenSnapshot] = None

    @property
    def is_watching_screen(self) -> bool:
        with self._awareness_lock:
            return (
                self._awareness_thread is not None
                and self._awareness_thread.is_alive()
                and not self._awareness_paused.is_set()
            )

    def analyze_screen(self, query: str = "Explain what is on my screen in detail") -> Dict[str, Any]:
        """Mode A — On-demand screen perception using Gemini SMART vision ladder."""
        if not self._access_mgr.check_permission(PermissionScope.SCREEN_CAPTURE):
            if self._access_mgr.state != DesktopAccessState.ERROR:
                self._access_mgr.enable_observe_only()
            else:
                return {"status": "FAILED", "error": "Screen capture permission denied (Emergency Stop active)."}

        # 1. Capture Active Window or Screen
        img, ox, oy = self._capture.capture_active_window(compress=True)
        session = self._context_mgr.get_or_create_session()

        # 2. Convert to JPEG bytes for Gemini API Part
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        img_bytes = buf.getvalue()

        # 3. Build Prompt with Context
        prompt = (
            f"You are JARVIS, an autonomous personal AI operating system.\n"
            f"Active Application: {session.app_name} | Window: \"{session.window_title}\"\n"
            f"User Instruction: {query}\n\n"
            f"Analyze the visible screen, identify the main content, layout, key UI elements, and any errors or diagrams.\n"
            f"Provide a concise, direct explanation suitable for voice output. Address the user as 'sir'."
        )

        from google.genai import types
        img_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

        try:
            resp = gemini.call([prompt, img_part], tier=gemini.SMART, timeout_ms=25000)
            analysis_text = (resp.text or "").strip() if resp else "I couldn't analyze the screen content, sir."
        except Exception as e:
            logger.error("Gemini screen analysis error: %s", e)
            analysis_text = f"Screen analysis encountered an error: {e}"

        # 4. Update Interaction Context & Baseline Snapshot
        self._last_observation_summary = analysis_text
        self._last_snapshot = self._diff_engine.capture_snapshot(include_ocr=False)

        return {
            "status": "SUCCESS",
            "app_name": session.app_name,
            "window_title": session.window_title,
            "analysis": analysis_text,
            "timestamp": time.time(),
        }

    def explain_diff_after_action(
        self,
        action_callable: Callable[[], Any],
        action_name: str = "action",
        settle_delay: float = 0.25,
    ) -> SemanticScreenDiff:
        """Mode B — Action-triggered perception: captures pre- and post-action states and explains changes."""
        pre_snap = self._diff_engine.capture_snapshot(include_ocr=True)

        # Execute the action (e.g., scroll, click)
        try:
            action_callable()
        except Exception as e:
            logger.error("Action execution failed during diff analysis: %s", e)

        time.sleep(settle_delay)
        post_snap = self._diff_engine.capture_snapshot(include_ocr=True)

        diff = self._diff_engine.compute_diff(pre_snap, post_snap)
        self._last_snapshot = post_snap
        return diff

    def what_changed(self) -> str:
        """Analyzes what changed between the last recorded snapshot and the current screen."""
        if not self._last_snapshot:
            # No prior snapshot; establish baseline and report
            self._last_snapshot = self._diff_engine.capture_snapshot(include_ocr=True)
            return "Baseline screen state captured, sir. You can now request an action and ask me what changed."

        current_snap = self._diff_engine.capture_snapshot(include_ocr=True)
        diff = self._diff_engine.compute_diff(self._last_snapshot, current_snap)
        self._last_snapshot = current_snap
        return diff.summary

    def start_continuous_awareness(self, interval_seconds: float = 6.0) -> str:
        """Mode C — Starts user-authorized continuous background screen awareness."""
        if not self._access_mgr.check_permission(PermissionScope.SCREEN_CAPTURE):
            self._access_mgr.enable_observe_only()

        with self._awareness_lock:
            if self._awareness_thread is not None and self._awareness_thread.is_alive():
                self._awareness_paused.clear()
                return outcome.done("continuous_awareness", status="active", message="Screen awareness already active.")

            self._awareness_stop_event.clear()
            self._awareness_paused.clear()

            def _worker():
                logger.info("Continuous screen awareness loop started (interval=%.1fs)...", interval_seconds)
                last_hash = ""
                while not self._awareness_stop_event.is_set():
                    if not self._awareness_paused.is_set():
                        try:
                            snap = self._diff_engine.capture_snapshot(include_ocr=False)
                            if snap.visual_hash != last_hash and last_hash:
                                logger.info("Screen awareness: visual change detected in %s ('%s')", snap.app_name, snap.window_title[:30])
                                # Update context
                                self._context_mgr.update_scroll_state("none", "none")
                            last_hash = snap.visual_hash
                        except Exception as e:
                            logger.debug("Awareness loop tick error: %s", e)
                    time.sleep(interval_seconds)
                logger.info("Continuous screen awareness loop terminated.")

            self._awareness_thread = threading.Thread(
                target=_worker,
                name="JarvisScreenAwareness",
                daemon=True,
            )
            self._awareness_thread.start()

        return outcome.done(
            "continuous_awareness",
            status="active",
            message="Screen awareness active, sir. Say 'pause screen awareness' or 'stop watching my screen' anytime.",
        )

    def pause_continuous_awareness(self) -> str:
        """Pauses the continuous awareness loop."""
        with self._awareness_lock:
            self._awareness_paused.set()
        return outcome.done("continuous_awareness", status="paused", message="Screen awareness paused, sir.")

    def stop_continuous_awareness(self) -> str:
        """Terminates continuous screen awareness."""
        with self._awareness_lock:
            self._awareness_stop_event.set()
            if self._awareness_thread is not None and self._awareness_thread.is_alive():
                self._awareness_thread.join(timeout=1.0)
                self._awareness_thread = None
        return outcome.done("continuous_awareness", status="stopped", message="Screen awareness stopped, sir.")


_multimodal_companion_instance: Optional[MultimodalCompanion] = None


def get_multimodal_companion() -> MultimodalCompanion:
    global _multimodal_companion_instance
    if _multimodal_companion_instance is None:
        _multimodal_companion_instance = MultimodalCompanion()
    return _multimodal_companion_instance

