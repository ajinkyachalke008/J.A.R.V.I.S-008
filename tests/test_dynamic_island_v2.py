"""
tests/test_dynamic_island_v2.py — Verification suite for Dynamic Island 2.0.

Tests:
- 5-Layer Arc Reactor (Nucleus, Energy Sphere, Inner Rings, Outer Cage, 4-Axis Stabilizers)
- Animation Quality Profiles (low, balanced, high)
- Mirrored Waveform Visualizer
- Circular Core Activity Gauge
- Smart Interactions (single-click expand, double-click restore, hide action)
- Extended Status and Theme Synchronization
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, QRect, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from core.hud.dynamic_island import (
    CircularActivityGauge,
    DynamicIsland,
    MirroredWaveformWidget,
)
from core.hud.island_core import IslandCore
from core.hud.island_state import (
    COLOR_ENERGY_AMBER,
    COLOR_MINT_CYAN,
    COLOR_PRIMARY_CYAN,
    IslandPresentationModel,
    IslandState,
)
from memory.config_manager import (
    get_dynamic_island_config,
    save_dynamic_island_config,
)


def process_events(cycles: int = 3):
    app = QApplication.instance()
    if app:
        for _ in range(cycles):
            app.processEvents()


# ── 1. Miniature Holographic Arc Reactor Tests ───────────────────────────────

def test_v2_reactor_layer_rendering(qapp):
    """Verify that all 5 layers of the Arc Reactor execute paintEvent safely without error."""
    model = IslandPresentationModel()
    core = IslandCore(parent=None, model=model, size=46)
    try:
        # Test across states (IDLE, LISTENING, THINKING, SPEAKING, ERROR)
        for st in [IslandState.IDLE, IslandState.LISTENING, IslandState.THINKING, IslandState.SPEAKING, IslandState.ERROR]:
            model.set_state(st)
            core.set_audio_level(0.75)
            core.repaint()
            process_events(2)
    finally:
        core.close()
        core.deleteLater()


def test_v2_reactor_quality_profiles(qapp):
    """Verify quality profiles (low, balanced, high) configure timer intervals."""
    core = IslandCore(parent=None, quality="low")
    try:
        assert core._quality == "low"
        assert core._timer.interval() == 42  # ~24 FPS

        core.set_quality("high")
        assert core._quality == "high"
        assert core._timer.interval() == 16  # ~60 FPS

        core.set_quality("balanced")
        assert core._quality == "balanced"
        assert core._timer.interval() == 28  # ~35 FPS
    finally:
        core.close()
        core.deleteLater()


def test_v2_reactor_audio_pulse_reactivity(qapp):
    """Verify audio amplitude lifts reactor pulse and outer connector scaling."""
    core = IslandCore(parent=None)
    try:
        core.set_audio_level(0.0)
        core._step()
        base_pulse = core._pulse

        core.set_audio_level(1.0)
        core._step()
        loud_pulse = core._pulse

        assert loud_pulse > base_pulse, "Loud audio must increase pulse expansion"
    finally:
        core.close()
        core.deleteLater()


# ── 2. Mirrored Waveform Visualizer Tests ────────────────────────────────────

def test_v2_mirrored_waveform_widget(qapp):
    """Verify symmetric mirrored waveform reacts to amplitude updates and paints safely."""
    model = IslandPresentationModel()
    wave = MirroredWaveformWidget(parent=None, bar_count=16, model=model)
    try:
        wave.resize(100, 30)
        wave.set_amplitude(0.8)
        wave._step()
        wave.repaint()
        process_events(2)
        assert wave._amplitude == 0.8
    finally:
        wave.close()
        wave.deleteLater()


# ── 3. Circular Core Activity Gauge Tests ────────────────────────────────────

def test_v2_circular_activity_gauge(qapp):
    """Verify circular gauge clamps values and updates percentage safely."""
    gauge = CircularActivityGauge(parent=None, percentage=87.0)
    try:
        assert gauge._percentage == 87.0
        gauge.set_percentage(120.0)
        assert gauge._percentage == 100.0  # Clamped to 100%
        gauge.set_percentage(-10.0)
        assert gauge._percentage == 0.0  # Clamped to 0%
        gauge.set_percentage(72.5)
        gauge.repaint()
        process_events(2)
        assert gauge._percentage == 72.5
    finally:
        gauge.close()
        gauge.deleteLater()


# ── 4. Dynamic Island 2.0 Smart Interactions ─────────────────────────────────

def test_v2_island_double_click_restores_jarvis(qapp):
    """Double-clicking the Dynamic Island restores the main application window."""
    mock_main = QWidget()
    mock_main.hide()

    island = DynamicIsland(parent=None)
    try:
        island.set_main_window(mock_main)

        # Simulate double click
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonDblClick,
            QPointF(20.0, 20.0),
            QPointF(20.0, 20.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        island.mouseDoubleClickEvent(event)
        process_events(3)

        assert mock_main.isVisible(), "Double clicking must restore main window"
    finally:
        mock_main.deleteLater()
        island.close()
        island.deleteLater()


def test_v2_island_hide_action(qapp):
    """Clicking hide on the expanded panel hides the island without closing the app."""
    island = DynamicIsland(parent=None)
    island.show()
    process_events(2)
    assert island.isVisible()

    island.hide_island()
    process_events(2)
    assert not island.isVisible()
    island.close()
    island.deleteLater()


def test_v2_hover_pauses_auto_collapse(qapp):
    """Hovering over the expanded island prevents premature auto-collapse."""
    island = DynamicIsland(parent=None)
    try:
        island.set_expanded(True)
        assert island.is_expanded()
        island._is_hovered = True

        # When hovered, auto collapse should no-op
        island._on_auto_collapse()
        process_events(2)
        assert island.is_expanded(), "Island must remain expanded while hovered"

        # On leave, auto collapse executes
        island._is_hovered = False
        island._on_auto_collapse()
        process_events(2)
        assert not island.is_expanded(), "Island should collapse once unhovered"
    finally:
        island.close()
        island.deleteLater()


# ── 5. Configuration Persistence Tests ───────────────────────────────────────

def test_v2_extended_configuration_keys():
    """Verify new 2.0 config keys persist and load correctly."""
    orig = get_dynamic_island_config()
    try:
        patch = {
            "auto_collapse": False,
            "collapse_delay": 8,
            "draggable": True,
            "animation_quality": "high",
            "show_audio_visualizer": True,
        }
        save_dynamic_island_config(patch)
        loaded = get_dynamic_island_config()
        assert loaded["auto_collapse"] is False
        assert loaded["collapse_delay"] == 8
        assert loaded["animation_quality"] == "high"
    finally:
        save_dynamic_island_config(orig)
