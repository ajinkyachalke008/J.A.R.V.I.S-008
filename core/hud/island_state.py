"""
core/hud/island_state.py — Presentation state model and audio smoothing for Dynamic Island 2.0.

Provides normalized state definitions, semantic technical color themes, asymmetric audio
smoothing filters, and status metadata for the Dynamic Island holographic companion.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Optional, Union
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger("JARVIS.IslandState")

# ── Dynamic Island 2.0 Technical Color Palette ────────────────────────────────
COLOR_BACKGROUND = "#030B11"
COLOR_INNER_SURFACE = "#07171E"
COLOR_PRIMARY_CYAN = "#00DDF2"
COLOR_SECONDARY_TEAL = "#16B8C5"
COLOR_ENERGY_AMBER = "#FFB53F"
COLOR_ENERGY_HIGHLIGHT = "#FFE08A"
COLOR_REACTOR_SILVER = "#DCE9EC"
COLOR_MINT_CYAN = "#00F5D4"
COLOR_ELECTRIC_BLUE = "#00B4D8"
COLOR_MAGENTA_VIOLET = "#D946EF"
COLOR_SLATE_GREY = "#64748B"
COLOR_SUCCESS_GREEN = "#10B981"
COLOR_NEUTRAL_TEXT = "#D8F0F2"
COLOR_MUTED_TEXT = "#72959C"
COLOR_ERROR = "#FF526C"

PALETTE: Dict[str, str] = {
    "background": COLOR_BACKGROUND,
    "inner_surface": COLOR_INNER_SURFACE,
    "primary_cyan": COLOR_PRIMARY_CYAN,
    "secondary_teal": COLOR_SECONDARY_TEAL,
    "energy_amber": COLOR_ENERGY_AMBER,
    "energy_highlight": COLOR_ENERGY_HIGHLIGHT,
    "reactor_silver": COLOR_REACTOR_SILVER,
    "mint_cyan": COLOR_MINT_CYAN,
    "electric_blue": COLOR_ELECTRIC_BLUE,
    "magenta_violet": COLOR_MAGENTA_VIOLET,
    "slate_grey": COLOR_SLATE_GREY,
    "success_green": COLOR_SUCCESS_GREEN,
    "neutral_text": COLOR_NEUTRAL_TEXT,
    "muted_text": COLOR_MUTED_TEXT,
    "error": COLOR_ERROR,
}


class IslandState(Enum):
    """Normalized operating states for the Dynamic Island companion."""
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


# State theme definitions mapping each state to semantic UI color roles
STATE_THEMES: Dict[IslandState, Dict[str, str]] = {
    IslandState.IDLE: {
        "background": COLOR_BACKGROUND,
        "surface": COLOR_INNER_SURFACE,
        "primary": COLOR_PRIMARY_CYAN,
        "secondary": COLOR_SECONDARY_TEAL,
        "accent": COLOR_ENERGY_AMBER,
        "highlight": COLOR_ENERGY_HIGHLIGHT,
        "core": COLOR_ENERGY_AMBER,
        "nucleus": COLOR_ENERGY_HIGHLIGHT,
        "cage": COLOR_REACTOR_SILVER,
        "wave": COLOR_ENERGY_AMBER,
        "text": COLOR_NEUTRAL_TEXT,
        "text_muted": COLOR_MUTED_TEXT,
        "border": COLOR_SECONDARY_TEAL,
        "glow": COLOR_PRIMARY_CYAN,
    },
    IslandState.LISTENING: {
        "background": COLOR_BACKGROUND,
        "surface": COLOR_INNER_SURFACE,
        "primary": COLOR_PRIMARY_CYAN,
        "secondary": COLOR_SECONDARY_TEAL,
        "accent": COLOR_MINT_CYAN,
        "highlight": COLOR_MINT_CYAN,
        "core": COLOR_MINT_CYAN,
        "nucleus": "#E0FFF9",
        "cage": COLOR_PRIMARY_CYAN,
        "wave": COLOR_PRIMARY_CYAN,
        "text": COLOR_NEUTRAL_TEXT,
        "text_muted": COLOR_MUTED_TEXT,
        "border": COLOR_PRIMARY_CYAN,
        "glow": COLOR_PRIMARY_CYAN,
    },
    IslandState.THINKING: {
        "background": COLOR_BACKGROUND,
        "surface": COLOR_INNER_SURFACE,
        "primary": COLOR_ENERGY_AMBER,
        "secondary": COLOR_PRIMARY_CYAN,
        "accent": COLOR_ELECTRIC_BLUE,
        "highlight": "#BAE6FD",
        "core": COLOR_ELECTRIC_BLUE,
        "nucleus": "#E0F2FE",
        "cage": COLOR_REACTOR_SILVER,
        "wave": COLOR_ELECTRIC_BLUE,
        "text": COLOR_NEUTRAL_TEXT,
        "text_muted": COLOR_MUTED_TEXT,
        "border": COLOR_ENERGY_AMBER,
        "glow": COLOR_ENERGY_AMBER,
    },
    IslandState.SPEAKING: {
        "background": COLOR_BACKGROUND,
        "surface": COLOR_INNER_SURFACE,
        "primary": COLOR_ENERGY_AMBER,
        "secondary": COLOR_ENERGY_HIGHLIGHT,
        "accent": COLOR_ENERGY_AMBER,
        "highlight": COLOR_ENERGY_HIGHLIGHT,
        "core": COLOR_ENERGY_AMBER,
        "nucleus": "#FFFBEB",
        "cage": COLOR_REACTOR_SILVER,
        "wave": COLOR_ENERGY_AMBER,
        "text": COLOR_NEUTRAL_TEXT,
        "text_muted": COLOR_MUTED_TEXT,
        "border": COLOR_ENERGY_AMBER,
        "glow": COLOR_ENERGY_HIGHLIGHT,
    },
    IslandState.ERROR: {
        "background": COLOR_BACKGROUND,
        "surface": COLOR_INNER_SURFACE,
        "primary": COLOR_ERROR,
        "secondary": COLOR_ERROR,
        "accent": COLOR_ERROR,
        "highlight": "#FECACA",
        "core": COLOR_ERROR,
        "nucleus": "#FFF1F2",
        "cage": "#991B1B",
        "wave": COLOR_ERROR,
        "text": COLOR_ERROR,
        "text_muted": COLOR_MUTED_TEXT,
        "border": COLOR_ERROR,
        "glow": COLOR_ERROR,
    },
    IslandState.OFFLINE: {
        "background": COLOR_BACKGROUND,
        "surface": COLOR_INNER_SURFACE,
        "primary": COLOR_MUTED_TEXT,
        "secondary": COLOR_MUTED_TEXT,
        "accent": COLOR_SLATE_GREY,
        "highlight": COLOR_SLATE_GREY,
        "core": COLOR_SLATE_GREY,
        "nucleus": "#CBD5E1",
        "cage": "#475569",
        "wave": COLOR_SLATE_GREY,
        "text": COLOR_MUTED_TEXT,
        "text_muted": COLOR_MUTED_TEXT,
        "border": COLOR_MUTED_TEXT,
        "glow": COLOR_MUTED_TEXT,
    },
}

# Raw state string normalization mappings
_STATE_MAPPINGS: Dict[str, IslandState] = {
    "IDLE": IslandState.IDLE,
    "READY": IslandState.IDLE,
    "ONLINE": IslandState.IDLE,
    "STANDBY": IslandState.IDLE,
    "SLEEP": IslandState.IDLE,
    "SLEEPING": IslandState.IDLE,
    "MUTED": IslandState.IDLE,
    "LISTEN": IslandState.LISTENING,
    "LISTENING": IslandState.LISTENING,
    "HEAR": IslandState.LISTENING,
    "HEARING": IslandState.LISTENING,
    "MIC": IslandState.LISTENING,
    "THINK": IslandState.THINKING,
    "THINKING": IslandState.THINKING,
    "PROCESS": IslandState.THINKING,
    "PROCESSING": IslandState.THINKING,
    "WORKING": IslandState.THINKING,
    "SPEAK": IslandState.SPEAKING,
    "SPEAKING": IslandState.SPEAKING,
    "TALK": IslandState.SPEAKING,
    "TALKING": IslandState.SPEAKING,
    "ERR": IslandState.ERROR,
    "ERROR": IslandState.ERROR,
    "FAIL": IslandState.ERROR,
    "FAILED": IslandState.ERROR,
    "CRASH": IslandState.ERROR,
    "OFFLINE": IslandState.OFFLINE,
    "DISCONNECTED": IslandState.OFFLINE,
    "OFF": IslandState.OFFLINE,
}


class IslandPresentationModel(QObject):
    """
    Presentation model for Dynamic Island.
    Maintains normalized operating state, audio smoothing filter matching HudCanvas,
    and publishes reactive signals for UI widgets.
    """

    state_changed = pyqtSignal(IslandState)
    audio_level_changed = pyqtSignal(float)
    status_text_changed = pyqtSignal(str)
    mic_status_changed = pyqtSignal(bool)
    output_status_changed = pyqtSignal(bool)
    activity_changed = pyqtSignal(str)
    core_activity_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state: IslandState = IslandState.IDLE
        self._status_text: str = IslandState.IDLE.value
        self._live_amp: float = 0.0
        self._amp_disp: float = 0.0
        self._mic_active: bool = True
        self._output_active: bool = True
        self._activity_description: str = "Online"
        self._core_activity_pct: float = 87.0

    # ── State Management ─────────────────────────────────────────────────────

    @classmethod
    def normalize_state(cls, raw: Union[str, IslandState, Any]) -> IslandState:
        """Parse and normalize an incoming state identifier into an IslandState enum."""
        if isinstance(raw, IslandState):
            return raw
        key = str(raw or "").strip().upper()
        return _STATE_MAPPINGS.get(key, IslandState.IDLE)

    def set_state(self, raw_state: Union[str, IslandState]) -> None:
        """
        Transition presentation model to a new state.
        Normalizes input, updates status label, and emits signals on value changes.
        """
        new_state = self.normalize_state(raw_state)
        # Preserve specific status text if caller passes descriptive string (e.g. SLEEPING, MUTED, PROCESSING)
        raw_str = raw_state.value if isinstance(raw_state, IslandState) else str(raw_state or "").strip().upper()
        new_text = raw_str if raw_str in ("SLEEPING", "MUTED", "PROCESSING") else new_state.value

        state_changed = (new_state != self._state)
        text_changed = (new_text != self._status_text)

        if state_changed:
            self._state = new_state
        if text_changed:
            self._status_text = new_text

        # Update activity description automatically based on state
        if new_text == "MUTED":
            self.set_mic_active(False)
            self.set_activity_description("Microphone Muted")
        elif new_text == "SLEEPING":
            self.set_activity_description("Standing By")
        elif new_state == IslandState.LISTENING:
            self.set_mic_active(True)
            self.set_activity_description("Listening to speech...")
        elif new_state == IslandState.THINKING:
            self.set_activity_description("Processing Voice...")
        elif new_state == IslandState.SPEAKING:
            self.set_activity_description("Speaking...")
        elif new_state == IslandState.ERROR:
            self.set_activity_description("System Error")
        else:
            self.set_activity_description("Online")

        if state_changed:
            self.state_changed.emit(self._state)
        if text_changed:
            self.status_text_changed.emit(self._status_text)

    def set_status_text(self, text: Any) -> None:
        """Explicitly override the visible status text."""
        if text is None:
            cleaned = ""
        elif isinstance(text, str) and not text.strip():
            cleaned = ""
        else:
            cleaned = str(text).strip().upper()
        if cleaned != self._status_text:
            self._status_text = cleaned
            self.status_text_changed.emit(self._status_text)

    def get_state(self) -> IslandState:
        """Return the current normalized IslandState."""
        return self._state

    def get_status_text(self) -> str:
        """Return the current status label string."""
        return self._status_text

    # ── Extended Status & Activity Properties ─────────────────────────────────

    def set_mic_active(self, active: bool) -> None:
        """Set whether microphone listening is currently active."""
        if self._mic_active != active:
            self._mic_active = active
            self.mic_status_changed.emit(self._mic_active)

    def is_mic_active(self) -> bool:
        return self._mic_active

    def set_output_active(self, active: bool) -> None:
        """Set whether audio output playback is currently active."""
        if self._output_active != active:
            self._output_active = active
            self.output_status_changed.emit(self._output_active)

    def is_output_active(self) -> bool:
        return self._output_active

    def set_activity_description(self, desc: str) -> None:
        """Set human-readable activity description for expanded panel."""
        clean = str(desc or "").strip()
        if self._activity_description != clean:
            self._activity_description = clean
            self.activity_changed.emit(self._activity_description)

    def get_activity_description(self) -> str:
        return self._activity_description

    def set_core_activity_pct(self, pct: float) -> None:
        """Set core activity percentage gauge value (0.0 to 100.0)."""
        clamped = max(0.0, min(100.0, float(pct)))
        if abs(self._core_activity_pct - clamped) > 0.1:
            self._core_activity_pct = clamped
            self.core_activity_changed.emit(self._core_activity_pct)

    def get_core_activity_pct(self) -> float:
        return self._core_activity_pct

    # ── Audio Smoothing Filter ───────────────────────────────────────────────

    def set_audio_level(self, level: float) -> None:
        """
        Thread-safe ingestion of incoming audio amplitude (0.0 to 1.0).
        Matches HudCanvas peak absorption: captures louder peaks without clamping decay.
        """
        try:
            lv = float(level)
        except (TypeError, ValueError):
            return
        lv = max(0.0, min(1.0, lv))
        if lv > self._live_amp:
            self._live_amp = lv

    def step_audio_filter(self) -> float:
        """
        Execute one audio filter smoothing step matching HudCanvas mathematics:
            _live_amp *= 0.86
            _amp_disp += (_live_amp - _amp_disp) * 0.45
        Clamped between 0.0 and 1.0. Emits audio_level_changed signal.
        """
        self._live_amp *= 0.86
        self._amp_disp += (self._live_amp - self._amp_disp) * 0.45
        self._amp_disp = max(0.0, min(1.0, self._amp_disp))

        # Clamp tiny residuals to clean zero
        if self._amp_disp < 0.001:
            self._amp_disp = 0.0
        if self._live_amp < 0.001:
            self._live_amp = 0.0

        self.audio_level_changed.emit(self._amp_disp)
        return self._amp_disp

    def get_display_amplitude(self) -> float:
        """Return the current smoothed audio display amplitude (0.0 to 1.0)."""
        return self._amp_disp

    def reset_audio(self) -> None:
        """Reset live and display amplitude filters to zero."""
        self._live_amp = 0.0
        self._amp_disp = 0.0
        self.audio_level_changed.emit(0.0)

    # ── Theme Colors ─────────────────────────────────────────────────────────

    def get_theme_colors(self) -> Dict[str, str]:
        """Return semantic color dictionary corresponding to current state and status text."""
        # Check specific status text for specialized theme overrides (MUTED, SLEEPING, PROCESSING)
        text = self._status_text.upper()
        if text == "MUTED":
            theme = dict(STATE_THEMES[IslandState.OFFLINE])
            theme["wave"] = COLOR_ERROR
            theme["core"] = COLOR_REACTOR_SILVER
            theme["nucleus"] = "#FFFFFF"
            theme["palette"] = dict(PALETTE)
            return theme
        if text == "SLEEPING":
            theme = dict(STATE_THEMES[IslandState.OFFLINE])
            theme["core"] = COLOR_SLATE_GREY
            theme["nucleus"] = "#94A3B8"
            theme["palette"] = dict(PALETTE)
            return theme
        if text == "PROCESSING":
            theme = dict(STATE_THEMES[IslandState.THINKING])
            theme["core"] = COLOR_MAGENTA_VIOLET
            theme["nucleus"] = "#F5D0FE"
            theme["wave"] = COLOR_MAGENTA_VIOLET
            theme["palette"] = dict(PALETTE)
            return theme

        return self.get_theme_colors_for_state(self._state)

    @classmethod
    def get_theme_colors_for_state(cls, state: IslandState) -> Dict[str, str]:
        """Return semantic color dictionary corresponding to any given IslandState."""
        theme = dict(STATE_THEMES.get(state, STATE_THEMES[IslandState.IDLE]))
        theme["palette"] = dict(PALETTE)
        return theme
