"""
core/hud/orb_bridge.py — Bidirectional IPC bridge between Python (PyQt6) and the Three.js Holographic Orb.
"""
from __future__ import annotations

import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

logger = logging.getLogger("JARVIS.OrbBridge")


class OrbBridge(QObject):
    """Exposes high-speed, thread-safe state & audio amplitude events to the Three.js WebGL canvas."""

    stateChanged = pyqtSignal(str)
    audioLevelChanged = pyqtSignal(float)
    themeChanged = pyqtSignal(str, str)
    gestureToggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._current_state = "IDLE"
        self._current_audio_level = 0.0
        self._primary_color = "#FFAA30"
        self._accent_color = "#FFCC66"
        self._gestures_enabled = False

    # ── Python-facing methods ────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Forward state transition (e.g. IDLE, LISTENING, THINKING, SPEAKING, MUTED) to Three.js."""
        st = str(state or "IDLE").strip()
        if st != self._current_state:
            self._current_state = st
            self.stateChanged.emit(st)

    def set_audio_level(self, level: float) -> None:
        """Forward smoothed 0.0–1.0 speech amplitude to Three.js."""
        try:
            lv = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            return
        if abs(lv - self._current_audio_level) < 0.005 and lv < 0.002:
            return
        self._current_audio_level = lv
        self.audioLevelChanged.emit(lv)

    def set_theme(self, primary: str, accent: str) -> None:
        """Update color scheme dynamically."""
        self._primary_color = primary
        self._accent_color = accent
        self.themeChanged.emit(primary, accent)

    def toggle_gestures(self, enabled: bool) -> None:
        """Enable or disable webcam hand-gesture tracking."""
        self._gestures_enabled = bool(enabled)
        self.gestureToggled.emit(self._gestures_enabled)

    # ── JavaScript-facing slots ──────────────────────────────────────────────

    @pyqtSlot(str)
    def logFromJs(self, message: str) -> None:
        """Receive debug / diagnostic logs from Three.js runtime."""
        logger.debug("[Orb.js] %s", message)

    @pyqtSlot(float, float)
    def reportGestureOrbit(self, d_theta: float, d_phi: float) -> None:
        """Handle gesture orbit deltas from client."""
        logger.debug("[Orb.Gesture] orbit delta: dTheta=%.3f, dPhi=%.3f", d_theta, d_phi)

    @pyqtSlot(float)
    def reportGestureZoom(self, factor: float) -> None:
        """Handle gesture zoom factor from client."""
        logger.debug("[Orb.Gesture] zoom factor: %.3f", factor)

    # ── Properties ───────────────────────────────────────────────────────────

    @pyqtProperty(str)
    def state(self) -> str:
        return self._current_state

    @pyqtProperty(float)
    def audioLevel(self) -> float:
        return self._current_audio_level

