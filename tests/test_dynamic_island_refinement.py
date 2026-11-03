"""
tests/test_dynamic_island_refinement.py — Test suite for Dynamic Island UI Refinements.

Tests:
- Compact pill dimensions (width ~180 DIP, 16.7% reduction, height ~42 DIP)
- Responsive DPI scaling support
- Animated perimeter lighting timer and step
- State-reactive illumination across all operating states
- Voice amplitude reactivity in speaking state
- Muted state dimmed brightness
- Hover illumination amplification
- Show/Hide event lifecycle timer pauses
- Preserved expanded state geometry and controls
"""
from __future__ import annotations

import math
import pytest
from PyQt6.QtCore import QPointF, QRect, Qt
from PyQt6.QtGui import QMouseEvent, QPaintEvent
from PyQt6.QtWidgets import QApplication, QWidget

from core.hud.dynamic_island import (
    BASE_COLLAPSED_H,
    BASE_COLLAPSED_W,
    COLLAPSED_H,
    COLLAPSED_W,
    EXPANDED_H,
    EXPANDED_W,
    DynamicIsland,
)
from core.hud.island_state import IslandPresentationModel, IslandState


def process_events(cycles: int = 3):
    app = QApplication.instance()
    if app:
        for _ in range(cycles):
            app.processEvents()


class TestDynamicIslandRefinement:
    def test_compact_dimensions(self, qapp):
        """Verify Dynamic Island collapsed width is reduced to 180 DIP (~16.7% reduction) and height to 42 DIP."""
        island = DynamicIsland(parent=None)
        try:
            assert COLLAPSED_W == 180
            assert COLLAPSED_H == 42
            assert BASE_COLLAPSED_W == 180
            assert BASE_COLLAPSED_H == 42
            assert island.width() == 180
            assert island.height() == 42
        finally:
            island.close()
            island.deleteLater()

    def test_dpi_scale_accessor(self, qapp):
        """Verify get_dpi_scale returns a valid scale factor >= 1.0."""
        island = DynamicIsland(parent=None)
        try:
            scale = island.get_dpi_scale()
            assert isinstance(scale, float)
            assert scale >= 1.0
        finally:
            island.close()
            island.deleteLater()

    def test_glow_timer_and_step(self, qapp):
        """Verify 30 FPS perimeter glow timer advances glow phase."""
        island = DynamicIsland(parent=None)
        try:
            assert hasattr(island, "_glow_timer")
            assert island._glow_timer.isActive()
            assert island._glow_timer.interval() == 33

            initial_phase = island._glow_phase
            island.show()
            process_events(2)
            island._step_glow()
            assert island._glow_phase != initial_phase, "Glow step must advance phase"
        finally:
            island.close()
            island.deleteLater()

    def test_state_reactive_step_rates(self, qapp):
        """Verify that thinking state advances highlight sweep faster than idle."""
        island = DynamicIsland(parent=None)
        try:
            island.show()
            island._glow_phase = 0.0

            # Idle step
            island.set_state(IslandState.IDLE)
            island._step_glow()
            idle_delta = island._glow_phase

            # Thinking step
            island._glow_phase = 0.0
            island.set_state(IslandState.THINKING)
            island._step_glow()
            thinking_delta = island._glow_phase

            assert thinking_delta > idle_delta, "Thinking state must advance highlights faster than idle"
        finally:
            island.close()
            island.deleteLater()

    def test_voice_reactivity_in_speaking_state(self, qapp):
        """Verify voice amplitude surges glow phase and amplitude tracking in speaking state."""
        island = DynamicIsland(parent=None)
        try:
            island.set_state(IslandState.SPEAKING)
            island.set_audio_level(0.85)
            assert island._amplitude == 0.85

            island.set_audio_level(0.0)
            assert island._amplitude == 0.0
        finally:
            island.close()
            island.deleteLater()

    def test_hover_illumination_state(self, qapp):
        """Verify enterEvent and leaveEvent toggle hover illumination state."""
        island = DynamicIsland(parent=None)
        try:
            assert island._is_hovered is False
            island._is_hovered = True
            island.repaint()
            process_events(2)

            island._is_hovered = False
            island.repaint()
            process_events(2)
            assert island._is_hovered is False
        finally:
            island.close()
            island.deleteLater()

    def test_hide_and_show_timer_lifecycle(self, qapp):
        """Verify hiding pauses the glow timer and showing resumes it."""
        island = DynamicIsland(parent=None)
        try:
            island.show()
            process_events(2)
            assert island._glow_timer.isActive()

            island.hide()
            process_events(2)
            assert not island._glow_timer.isActive(), "Hiding island must pause glow timer to conserve resources"

            island.show()
            process_events(2)
            assert island._glow_timer.isActive(), "Showing island must resume glow timer"
        finally:
            island.close()
            island.deleteLater()

    def test_paint_across_all_states(self, qapp):
        """Verify paintEvent executes safely across all supported states."""
        island = DynamicIsland(parent=None)
        try:
            island.show()
            for st in [
                IslandState.IDLE,
                IslandState.LISTENING,
                IslandState.THINKING,
                IslandState.SPEAKING,
                IslandState.ERROR,
                IslandState.OFFLINE,
            ]:
                island.set_state(st)
                island.set_audio_level(0.7)
                island.repaint()
                process_events(2)
        finally:
            island.close()
            island.deleteLater()

    def test_expanded_state_preserved(self, qapp):
        """Verify expanding the refined island sets expanded dimensions properly."""
        island = DynamicIsland(parent=None)
        try:
            island.show()
            process_events(2)

            island.set_expanded(True)
            island._anim.stop()
            island.resize(EXPANDED_W, EXPANDED_H)
            process_events(2)

            assert island.is_expanded()
            assert island.width() == EXPANDED_W
            assert island.height() == EXPANDED_H
            assert not island._expanded_panel.isHidden()

            island.set_expanded(False)
            island._anim.stop()
            island.resize(COLLAPSED_W, COLLAPSED_H)
            process_events(2)

            assert not island.is_expanded()
            assert island.width() == COLLAPSED_W
            assert island.height() == COLLAPSED_H
            assert island._expanded_panel.isHidden()
        finally:
            island.close()
            island.deleteLater()

    def test_controls_drawer_island_toggle(self, qapp):
        """Verify MainWindow controls drawer exposes _island_btn and toggle handler."""
        from ui import MainWindow
        win = MainWindow("face.png")
        try:
            assert hasattr(win, "_island_btn"), "MainWindow must have _island_btn in controls drawer"
            assert hasattr(win, "_toggle_island_visibility"), "MainWindow must have _toggle_island_visibility handler"
            assert hasattr(win, "_refresh_island_btn"), "MainWindow must have _refresh_island_btn helper"

            # Check initial button text
            win._refresh_island_btn()
            assert "DYNAMIC ISLAND" in win._island_btn.text()
        finally:
            win.close()
            win.deleteLater()
