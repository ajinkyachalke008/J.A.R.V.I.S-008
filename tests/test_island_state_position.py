"""
tests/test_island_state_position.py — Unit tests for Milestone M1:
IslandPresentationModel, IslandPositionEngine, and Dynamic Island config persistence.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QGuiApplication

from core.hud.island_state import (
    COLOR_BACKGROUND,
    COLOR_ENERGY_AMBER,
    COLOR_ENERGY_HIGHLIGHT,
    COLOR_ERROR,
    COLOR_INNER_SURFACE,
    COLOR_MUTED_TEXT,
    COLOR_NEUTRAL_TEXT,
    COLOR_PRIMARY_CYAN,
    COLOR_SECONDARY_TEAL,
    IslandPresentationModel,
    IslandState,
)
from core.hud.island_position import IslandAnchor, IslandPositionEngine
from memory.config_manager import (
    DEFAULT_DYNAMIC_ISLAND_CONFIG,
    get_dynamic_island_config,
    load_api_keys,
    save_dynamic_island_config,
)


# ── Simulated Screen Helper ──────────────────────────────────────────────────

class DummyScreen:
    """Mock screen implementing geometry() and availableGeometry() for headless tests."""

    def __init__(self, rect: QRect):
        self._rect = rect

    def geometry(self) -> QRect:
        return self._rect

    def availableGeometry(self) -> QRect:
        return self._rect


# ── IslandPresentationModel Tests ────────────────────────────────────────────

def test_island_state_enum_members():
    """Verify IslandState contains all required states with correct string values."""
    assert IslandState.IDLE.value == "IDLE"
    assert IslandState.LISTENING.value == "LISTENING"
    assert IslandState.THINKING.value == "THINKING"
    assert IslandState.SPEAKING.value == "SPEAKING"
    assert IslandState.ERROR.value == "ERROR"
    assert IslandState.OFFLINE.value == "OFFLINE"


def test_island_state_normalization():
    """Verify robust state parsing and normalization across case and aliases."""
    model = IslandPresentationModel()

    assert model.normalize_state("LISTENING") == IslandState.LISTENING
    assert model.normalize_state("listening") == IslandState.LISTENING
    assert model.normalize_state("  THINKING  ") == IslandState.THINKING
    assert model.normalize_state("speaking") == IslandState.SPEAKING
    assert model.normalize_state("talk") == IslandState.SPEAKING
    assert model.normalize_state("error") == IslandState.ERROR
    assert model.normalize_state("fail") == IslandState.ERROR
    assert model.normalize_state("offline") == IslandState.OFFLINE
    assert model.normalize_state("disconnected") == IslandState.OFFLINE

    # Aliases mapping to IDLE
    assert model.normalize_state("ready") == IslandState.IDLE
    assert model.normalize_state("sleeping") == IslandState.IDLE
    assert model.normalize_state("muted") == IslandState.IDLE
    assert model.normalize_state("online") == IslandState.IDLE

    # Unknown or empty fallbacks
    assert model.normalize_state("UNKNOWN_XYZ") == IslandState.IDLE
    assert model.normalize_state("") == IslandState.IDLE
    assert model.normalize_state(None) == IslandState.IDLE


def test_state_transitions_and_signals(qapp):
    """Verify state transitions emit signals and deduplicate redundant updates."""
    model = IslandPresentationModel()

    states_recorded = []
    texts_recorded = []

    model.state_changed.connect(states_recorded.append)
    model.status_text_changed.connect(texts_recorded.append)

    # Initial state
    assert model.get_state() == IslandState.IDLE
    assert model.get_status_text() == "IDLE"

    # Transition to LISTENING
    model.set_state("LISTENING")
    assert model.get_state() == IslandState.LISTENING
    assert model.get_status_text() == "LISTENING"
    assert states_recorded == [IslandState.LISTENING]
    assert texts_recorded == ["LISTENING"]

    # Redundant transition does not re-emit
    model.set_state("LISTENING")
    assert len(states_recorded) == 1
    assert len(texts_recorded) == 1

    # Transition to THINKING
    model.set_state("THINKING")
    assert model.get_state() == IslandState.THINKING
    assert len(states_recorded) == 2
    assert states_recorded[-1] == IslandState.THINKING

    # Transition to SLEEPING preserves descriptive status label while mapping state to IDLE
    model.set_state("SLEEPING")
    assert model.get_state() == IslandState.IDLE
    assert model.get_status_text() == "SLEEPING"
    assert states_recorded[-1] == IslandState.IDLE
    assert texts_recorded[-1] == "SLEEPING"


def test_explicit_status_text_override(qapp):
    """Verify set_status_text modifies status label independently of state."""
    model = IslandPresentationModel()
    texts = []
    model.status_text_changed.connect(texts.append)

    model.set_status_text("PROCESSING QUERY")
    assert model.get_status_text() == "PROCESSING QUERY"
    assert texts == ["PROCESSING QUERY"]

    # Deduplicate redundant text
    model.set_status_text("PROCESSING QUERY")
    assert len(texts) == 1


def test_audio_smoothing_filter_math(qapp):
    """Verify audio peak ingestion and HudCanvas-matching decay smoothing math."""
    model = IslandPresentationModel()
    levels = []
    model.audio_level_changed.connect(levels.append)

    # Peak absorption
    model.set_audio_level(0.8)
    assert model._live_amp == 0.8

    # Lower peak does not override live peak before decay
    model.set_audio_level(0.4)
    assert model._live_amp == 0.8

    # Higher peak overrides
    model.set_audio_level(1.0)
    assert model._live_amp == 1.0

    # Clamping out-of-range inputs
    model.set_audio_level(2.5)
    assert model._live_amp == 1.0

    # Step 1:
    # live_amp = 1.0 * 0.86 = 0.86
    # amp_disp = 0.0 + (0.86 - 0.0) * 0.45 = 0.387
    d1 = model.step_audio_filter()
    assert abs(d1 - 0.387) < 1e-4
    assert abs(model.get_display_amplitude() - 0.387) < 1e-4
    assert len(levels) == 1
    assert abs(levels[0] - 0.387) < 1e-4

    # Step 2:
    # live_amp = 0.86 * 0.86 = 0.7396
    # amp_disp = 0.387 + (0.7396 - 0.387) * 0.45 = 0.387 + 0.15867 = 0.54567
    d2 = model.step_audio_filter()
    assert abs(d2 - 0.54567) < 1e-4

    # Progressive decay without further audio input
    for _ in range(50):
        model.step_audio_filter()
    assert model.get_display_amplitude() == 0.0

    # Reset audio
    model.set_audio_level(0.9)
    model.reset_audio()
    assert model._live_amp == 0.0
    assert model.get_display_amplitude() == 0.0


def test_theme_colors_palette():
    """Verify theme color dictionary contains exact JARVIS palette hex colors."""
    model = IslandPresentationModel()

    for st in IslandState:
        theme = model.get_theme_colors_for_state(st)
        assert "background" in theme
        assert "surface" in theme
        assert "primary" in theme
        assert "secondary" in theme
        assert "accent" in theme
        assert "text" in theme
        assert "text_muted" in theme
        assert "border" in theme
        assert "glow" in theme
        assert "palette" in theme

        # Verify palette constants
        assert theme["background"] == COLOR_BACKGROUND
        assert theme["surface"] == COLOR_INNER_SURFACE

    # IDLE / LISTENING Cyan
    idle_theme = model.get_theme_colors_for_state(IslandState.IDLE)
    assert idle_theme["primary"] == COLOR_PRIMARY_CYAN
    assert idle_theme["secondary"] == COLOR_SECONDARY_TEAL

    # SPEAKING / THINKING Amber
    speaking_theme = model.get_theme_colors_for_state(IslandState.SPEAKING)
    assert speaking_theme["primary"] == COLOR_ENERGY_AMBER
    assert speaking_theme["glow"] == COLOR_ENERGY_HIGHLIGHT

    # ERROR Coral
    error_theme = model.get_theme_colors_for_state(IslandState.ERROR)
    assert error_theme["primary"] == COLOR_ERROR
    assert error_theme["border"] == COLOR_ERROR

    # OFFLINE Muted
    offline_theme = model.get_theme_colors_for_state(IslandState.OFFLINE)
    assert offline_theme["primary"] == COLOR_MUTED_TEXT


# ── IslandPositionEngine Tests ───────────────────────────────────────────────

def test_island_anchor_normalization():
    """Verify anchor parsing and normalization."""
    assert IslandPositionEngine.normalize_anchor("top_center") == IslandAnchor.TOP_CENTER
    assert IslandPositionEngine.normalize_anchor("TOP_CENTER") == IslandAnchor.TOP_CENTER
    assert IslandPositionEngine.normalize_anchor("top-center") == IslandAnchor.TOP_CENTER
    assert IslandPositionEngine.normalize_anchor("top_left") == IslandAnchor.TOP_LEFT
    assert IslandPositionEngine.normalize_anchor("top_right") == IslandAnchor.TOP_RIGHT
    assert IslandPositionEngine.normalize_anchor("bottom_center") == IslandAnchor.BOTTOM_CENTER
    assert IslandPositionEngine.normalize_anchor("custom") == IslandAnchor.CUSTOM
    assert IslandPositionEngine.normalize_anchor("invalid") == IslandAnchor.TOP_CENTER


def test_calculate_position_top_center(qapp):
    """Verify TOP_CENTER calculation on primary 1920x1080 display."""
    screen = DummyScreen(QRect(0, 0, 1920, 1080))
    engine = IslandPositionEngine(
        anchor=IslandAnchor.TOP_CENTER,
        offset_x=0,
        offset_y=10,
        safe_margin=0,
    )

    pill_w = 210
    pill_h = 46

    pos = engine.calculate_position(pill_w, pill_h, screen=screen)
    # Expected x: 0 + (1920 - 210) // 2 + 0 = 855
    # Expected y: 0 + 10 = 10
    assert pos.x() == 855
    assert pos.y() == 10


def test_calculate_position_all_anchors(qapp):
    """Verify coordinate calculation across all supported anchor modes."""
    screen = DummyScreen(QRect(0, 0, 1920, 1080))
    pill_w = 200
    pill_h = 50

    # TOP_LEFT
    tl_engine = IslandPositionEngine(anchor=IslandAnchor.TOP_LEFT, offset_x=15, offset_y=20, safe_margin=0)
    pos_tl = tl_engine.calculate_position(pill_w, pill_h, screen=screen)
    assert pos_tl == QPoint(15, 20)

    # TOP_RIGHT
    tr_engine = IslandPositionEngine(anchor=IslandAnchor.TOP_RIGHT, offset_x=15, offset_y=20, safe_margin=0)
    pos_tr = tr_engine.calculate_position(pill_w, pill_h, screen=screen)
    # Expected x: 0 + 1920 - 200 - 15 = 1705, y: 20
    assert pos_tr == QPoint(1705, 20)

    # BOTTOM_CENTER
    bc_engine = IslandPositionEngine(anchor=IslandAnchor.BOTTOM_CENTER, offset_x=0, offset_y=15, safe_margin=0)
    pos_bc = bc_engine.calculate_position(pill_w, pill_h, screen=screen)
    # Expected x: (1920 - 200) // 2 = 860, y: 1080 - 50 - 15 = 1015
    assert pos_bc == QPoint(860, 1015)

    # CUSTOM
    custom_engine = IslandPositionEngine(anchor=IslandAnchor.CUSTOM, offset_x=340, offset_y=180, safe_margin=0)
    pos_custom = custom_engine.calculate_position(pill_w, pill_h, screen=screen)
    assert pos_custom == QPoint(340, 180)


def test_multi_monitor_negative_origin(qapp):
    """Verify multi-monitor virtual coordinates with secondary display on left."""
    # Secondary monitor placed to the left: x=-1920, y=0, width=1920, height=1080
    left_screen = DummyScreen(QRect(-1920, 0, 1920, 1080))
    engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER, offset_x=0, offset_y=10, safe_margin=0)

    pill_w = 200
    pill_h = 46

    pos = engine.calculate_position(pill_w, pill_h, screen=left_screen)
    # Expected x: -1920 + (1920 - 200) // 2 = -1920 + 860 = -1060
    # Expected y: 0 + 10 = 10
    assert pos.x() == -1060
    assert pos.y() == 10

    # Secondary monitor placed above: x=0, y=-1080
    top_screen = DummyScreen(QRect(0, -1080, 1920, 1080))
    pos_top = engine.calculate_position(pill_w, pill_h, screen=top_screen)
    assert pos_top.x() == 860
    assert pos_top.y() == -1070


def test_screen_clamping_and_safe_margins(qapp):
    """Verify position engine clamps extreme user offsets inside safe screen margins."""
    screen = DummyScreen(QRect(0, 0, 1920, 1080))
    engine = IslandPositionEngine(
        anchor=IslandAnchor.CUSTOM,
        offset_x=99999,
        offset_y=99999,
        safe_margin=10,
    )

    pill_w = 200
    pill_h = 50

    # Clamped within safe margins
    pos = engine.calculate_position(pill_w, pill_h, screen=screen, clamp_to_bounds=True)
    assert pos.x() == 1920 - 200 - 10
    assert pos.y() == 1080 - 50 - 10

    # Without clamping, allows raw virtual coordinates
    pos_unclamped = engine.calculate_position(pill_w, pill_h, screen=screen, clamp_to_bounds=False)
    assert pos_unclamped.x() == 99999
    assert pos_unclamped.y() == 99999


def test_topology_signals_and_listeners(qapp):
    """Verify topology changed signal emits when anchor or monitor changes."""
    engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER)
    signals = []
    engine.topology_changed.connect(lambda: signals.append(True))

    engine.set_anchor(IslandAnchor.BOTTOM_CENTER)
    assert len(signals) == 1

    engine.set_monitor_index(1)
    assert len(signals) == 2

    # Clean detach without exceptions
    engine.detach_screen_listeners()


# ── Configuration Persistence Tests ──────────────────────────────────────────

def test_dynamic_island_config_persistence():
    """Verify get_dynamic_island_config and save_dynamic_island_config round-trip."""
    original_cfg = get_dynamic_island_config()

    try:
        # Default config validation
        assert "enabled" in original_cfg
        assert "anchor" in original_cfg
        assert "offset_x" in original_cfg
        assert "offset_y" in original_cfg
        assert "monitor_index" in original_cfg
        assert "scale" in original_cfg

        # Save customized values
        test_patch = {
            "enabled": False,
            "anchor": "bottom_center",
            "offset_x": 42,
            "offset_y": 28,
            "monitor_index": 1,
            "scale": 1.25,
        }
        save_dynamic_island_config(test_patch)

        reloaded = get_dynamic_island_config()
        assert reloaded["enabled"] is False
        assert reloaded["anchor"] == "bottom_center"
        assert reloaded["offset_x"] == 42
        assert reloaded["offset_y"] == 28
        assert reloaded["monitor_index"] == 1
        assert reloaded["scale"] == 1.25

    finally:
        # Restore original state
        save_dynamic_island_config(original_cfg)
        restored = get_dynamic_island_config()
        assert restored["enabled"] == original_cfg["enabled"]
        assert restored["offset_x"] == original_cfg["offset_x"]
