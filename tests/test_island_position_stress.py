"""
tests/test_island_position_stress.py — Adversarial stress test suite for IslandPositionEngine
and Dynamic Island ConfigManager.

Evaluates:
1. Multi-monitor simulated geometries: 3-4 displays across virtual desktop space
   (negative X, negative Y, vertical 9:16 portrait, ultrawide 32:9).
2. Extreme offsets, degenerate sizes (0x0, oversize pills, extreme safe margins).
3. Fractional DPI scaling simulations (1.0x to 3.0x).
4. ConfigManager type validation, boundary clamping, and sanitization.
5. Corrupt JSON recovery & non-dict root handling.
6. Multi-threaded concurrency stress testing.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import List

import pytest
from PyQt6.QtCore import QPoint, QRect

from core.hud.island_position import IslandAnchor, IslandPositionEngine
import memory.config_manager as config_manager


# ── Mock Screen Fixtures ─────────────────────────────────────────────────────

class SimulatedScreen:
    """Mock display implementing QScreen geometry contracts."""

    def __init__(self, rect: QRect, name: str = "SimulatedScreen", dpr: float = 1.0):
        self._rect = rect
        self._name = name
        self._dpr = dpr

    def geometry(self) -> QRect:
        return self._rect

    def availableGeometry(self) -> QRect:
        return self._rect

    def devicePixelRatio(self) -> float:
        return self._dpr

    def name(self) -> str:
        return self._name


# ── 1. Multi-Monitor Simulated Geometries ────────────────────────────────────

class TestMultiMonitorGeometries:
    """Stress-test IslandPositionEngine across virtual multi-monitor setups."""

    def test_triple_monitor_extended_desktop(self, qapp):
        """
        Setup: 3-Monitor span
        Screen 0 (Left):     -1920, 0, 1920x1080 (Negative X)
        Screen 1 (Primary):  0, 0, 1920x1080
        Screen 2 (Right):     1920, 0, 1920x1080
        """
        left = SimulatedScreen(QRect(-1920, 0, 1920, 1080), name="Left")
        center = SimulatedScreen(QRect(0, 0, 1920, 1080), name="Center")
        right = SimulatedScreen(QRect(1920, 0, 1920, 1080), name="Right")

        pill_w, pill_h = 240, 50
        engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER, offset_x=0, offset_y=12, safe_margin=5)

        # Left Screen (Negative X space)
        pos_left = engine.calculate_position(pill_w, pill_h, screen=left)
        assert pos_left == QPoint(-1080, 12)

        # Primary Screen
        pos_center = engine.calculate_position(pill_w, pill_h, screen=center)
        assert pos_center == QPoint(840, 12)

        # Right Screen
        pos_right = engine.calculate_position(pill_w, pill_h, screen=right)
        assert pos_right == QPoint(2760, 12)

    def test_quad_monitor_with_negative_x_and_negative_y(self, qapp):
        """
        Setup: 4-Monitor 2x2 grid with negative X and negative Y
        Screen 0: Top-Left    -1920, -1080, 1920x1080 (Negative X & Negative Y)
        Screen 1: Top-Right       0, -1080, 1920x1080 (Negative Y)
        Screen 2: Bottom-Left -1920,     0, 1920x1080 (Negative X)
        Screen 3: Bottom-Right    0,     0, 1920x1080 (Primary origin)
        """
        screens = [
            SimulatedScreen(QRect(-1920, -1080, 1920, 1080), "Top-Left"),
            SimulatedScreen(QRect(0, -1080, 1920, 1080), "Top-Right"),
            SimulatedScreen(QRect(-1920, 0, 1920, 1080), "Bottom-Left"),
            SimulatedScreen(QRect(0, 0, 1920, 1080), "Bottom-Right"),
        ]

        pill_w, pill_h = 220, 48
        engine = IslandPositionEngine(safe_margin=6)

        anchors_to_test = [
            (IslandAnchor.TOP_CENTER, lambda sx, sy, sw, sh: (sx + (sw - pill_w) // 2, sy + 10)),
            (IslandAnchor.TOP_LEFT, lambda sx, sy, sw, sh: (sx + 6, sy + 10)),  # Clamped by safe_margin 6
            (IslandAnchor.TOP_RIGHT, lambda sx, sy, sw, sh: (sx + sw - pill_w - 6, sy + 10)),  # Clamped by margin
            (IslandAnchor.BOTTOM_CENTER, lambda sx, sy, sw, sh: (sx + (sw - pill_w) // 2, sy + sh - pill_h - 10)),
        ]

        for screen in screens:
            geom = screen.geometry()
            sx, sy, sw, sh = geom.x(), geom.y(), geom.width(), geom.height()

            for anchor, expected_fn in anchors_to_test:
                engine.anchor = anchor
                engine.set_offset(0, 10)
                pos = engine.calculate_position(pill_w, pill_h, screen=screen, clamp_to_bounds=True)

                exp_x, exp_y = expected_fn(sx, sy, sw, sh)
                assert pos.x() == exp_x, f"Failed on {screen.name()} with anchor {anchor}: x={pos.x()}, exp={exp_x}"
                assert pos.y() == exp_y, f"Failed on {screen.name()} with anchor {anchor}: y={pos.y()}, exp={exp_y}"

    def test_ultrawide_and_vertical_portrait_aspect_ratios(self, qapp):
        """
        Setup: Heterogeneous monitors with Ultrawide 32:9 and Vertical 9:16
        - Ultrawide: 5120x1440 at (0, 0)
        - Vertical 9:16: 1080x1920 at (5120, -240)
        - Left Portrait 9:16: 1080x1920 at (-1080, -240)
        """
        ultrawide = SimulatedScreen(QRect(0, 0, 5120, 1440), "32:9 Ultrawide")
        vertical_right = SimulatedScreen(QRect(5120, -240, 1080, 1920), "9:16 Portrait Right")
        vertical_left = SimulatedScreen(QRect(-1080, -240, 1080, 1920), "9:16 Portrait Left")

        engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER, offset_x=0, offset_y=15, safe_margin=8)
        pw, ph = 260, 52

        # 1. Ultrawide center positioning
        pos_uw = engine.calculate_position(pw, ph, screen=ultrawide)
        assert pos_uw == QPoint(2430, 15)

        # 2. Right Vertical Portrait
        pos_vr = engine.calculate_position(pw, ph, screen=vertical_right)
        assert pos_vr == QPoint(5530, -225)

        # 3. Left Vertical Portrait (Negative X & Negative Y)
        pos_vl = engine.calculate_position(pw, ph, screen=vertical_left)
        assert pos_vl == QPoint(-670, -225)

        # 4. Bottom-Center on Vertical Portrait
        engine.anchor = IslandAnchor.BOTTOM_CENTER
        pos_vl_bottom = engine.calculate_position(pw, ph, screen=vertical_left)
        assert pos_vl_bottom == QPoint(-670, 1613)


# ── 2. Extreme Offsets & Degenerate Boundaries ───────────────────────────────

class TestExtremeOffsetsAndBoundaries:
    """Stress-test bounding limits, clamping, and degenerate dimensions."""

    def test_massive_positive_and_negative_offsets(self, qapp):
        screen = SimulatedScreen(QRect(0, 0, 1920, 1080))
        engine = IslandPositionEngine(anchor=IslandAnchor.CUSTOM, safe_margin=10)
        pw, ph = 200, 40

        # Massive positive offset: 1,000,000 px
        engine.set_offset(1000000, 1000000)
        pos_clamped = engine.calculate_position(pw, ph, screen=screen, clamp_to_bounds=True)
        assert pos_clamped == QPoint(1710, 1030)

        pos_unclamped = engine.calculate_position(pw, ph, screen=screen, clamp_to_bounds=False)
        assert pos_unclamped == QPoint(1000000, 1000000)

        # Massive negative offset: -1,000,000 px
        engine.set_offset(-1000000, -1000000)
        pos_neg_clamped = engine.calculate_position(pw, ph, screen=screen, clamp_to_bounds=True)
        assert pos_neg_clamped == QPoint(10, 10)

        pos_neg_unclamped = engine.calculate_position(pw, ph, screen=screen, clamp_to_bounds=False)
        assert pos_neg_unclamped == QPoint(-1000000, -1000000)

    def test_degenerate_zero_dimensions(self, qapp):
        """Zero pill width and height must not divide-by-zero or crash."""
        screen = SimulatedScreen(QRect(0, 0, 1920, 1080))
        engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER, offset_x=0, offset_y=0, safe_margin=0)

        pos = engine.calculate_position(0, 0, screen=screen)
        assert pos == QPoint(960, 0)

    def test_oversized_pill_exceeding_screen_dimensions(self, qapp):
        """Pill larger than screen width or height should gracefully clamp without crash."""
        screen = SimulatedScreen(QRect(0, 0, 1000, 800))
        engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER, offset_x=0, offset_y=10, safe_margin=10)

        # Pill is 1200x900 (larger than 1000x800 display)
        pos = engine.calculate_position(1200, 900, screen=screen, clamp_to_bounds=True)
        assert pos == QPoint(0, 0)

    def test_massive_safe_margins_exceeding_screen(self, qapp):
        """Safe margin larger than screen dimension must fall back safely to sx, sy."""
        screen = SimulatedScreen(QRect(100, 100, 800, 600))
        engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER, safe_margin=500)

        pos = engine.calculate_position(200, 50, screen=screen, clamp_to_bounds=True)
        assert pos == QPoint(100, 100)

    def test_fractional_dpi_scaling_simulation(self, qapp):
        """Verify positioning math under simulated fractional DPI scaling (1.0x to 3.0x)."""
        screen = SimulatedScreen(QRect(0, 0, 2560, 1440), dpr=1.5)
        base_w, base_h = 210, 46

        scales = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
        for scale in scales:
            pw = int(base_w * scale)
            ph = int(base_h * scale)
            engine = IslandPositionEngine(anchor=IslandAnchor.TOP_CENTER, offset_x=0, offset_y=int(10 * scale), safe_margin=4)
            pos = engine.calculate_position(pw, ph, screen=screen)

            expected_x = (2560 - pw) // 2
            expected_y = int(10 * scale)
            assert pos.x() == expected_x
            assert pos.y() == expected_y


# ── 3. ConfigManager Type Validation & Resilience ────────────────────────────

class TestConfigManagerResilience:
    """Adversarial stress-testing of Dynamic Island configuration persistence."""

    @pytest.fixture(autouse=True)
    def isolated_config(self, tmp_path, monkeypatch):
        """Redirect CONFIG_FILE and CONFIG_DIR to an isolated sandbox."""
        sandbox_dir = tmp_path / "config"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        fake_config_file = sandbox_dir / "api_keys.json"

        monkeypatch.setattr(config_manager, "CONFIG_DIR", sandbox_dir)
        monkeypatch.setattr(config_manager, "CONFIG_FILE", fake_config_file)
        yield fake_config_file

    def test_type_validation_and_clamping(self):
        """Verify strict coercion of malformed, extreme, and invalid input values."""
        cfg = config_manager.get_dynamic_island_config()
        assert cfg == config_manager.DEFAULT_DYNAMIC_ISLAND_CONFIG

        bad_inputs = {
            "enabled": 0,                      # Non-bool falsy
            "anchor": "  BOTTOM-CENTER  ",     # Mixed case, hyphens, whitespace
            "offset_x": "not_an_int",          # Unparseable string
            "offset_y": 999999,                # Massive offset
            "monitor_index": -42,              # Negative monitor index
            "scale": 99.5,                     # Out-of-bounds scale
        }
        config_manager.save_dynamic_island_config(bad_inputs)
        saved = config_manager.get_dynamic_island_config()

        assert saved["enabled"] is False
        assert saved["anchor"] == "bottom-center"
        assert saved["offset_x"] == 0  # Reverted to default
        assert saved["offset_y"] == 999999
        assert saved["monitor_index"] == 0  # Clamped to >= 0
        assert saved["scale"] == 3.0  # Clamped to max 3.0

        # Test lower bounds
        config_manager.save_dynamic_island_config({"scale": -10.0})
        saved2 = config_manager.get_dynamic_island_config()
        assert saved2["scale"] == 0.5  # Clamped to min 0.5

    def test_non_dict_and_none_save_input(self):
        """Passing non-dict or None to save_dynamic_island_config should safely no-op."""
        original = config_manager.get_dynamic_island_config()
        config_manager.save_dynamic_island_config(None)  # type: ignore
        config_manager.save_dynamic_island_config("not_a_dict")  # type: ignore
        config_manager.save_dynamic_island_config([1, 2, 3])  # type: ignore
        assert config_manager.get_dynamic_island_config() == original

    def test_corrupt_json_syntax_recovery(self, isolated_config):
        """A syntactically broken api_keys.json should fall back gracefully to defaults under UTF-8 stdout."""
        isolated_config.write_text('{"dynamic_island": { incomplete', encoding="utf-8")

        cfg = config_manager.get_dynamic_island_config()
        assert cfg == config_manager.DEFAULT_DYNAMIC_ISLAND_CONFIG

    def test_non_dict_json_root_vulnerability_probe(self, isolated_config):
        """
        Adversarial challenge: what happens when api_keys.json contains a non-dict root?
        (e.g., '[1, 2, 3]', 'null', '"raw string"', '123')
        """
        # Case A: list root
        isolated_config.write_text("[1, 2, 3]", encoding="utf-8")
        has_list_root_bug = False
        try:
            cfg = config_manager.get_dynamic_island_config()
        except AttributeError:
            has_list_root_bug = True

        # Case B: null root
        isolated_config.write_text("null", encoding="utf-8")
        has_null_root_bug = False
        try:
            cfg = config_manager.get_dynamic_island_config()
        except AttributeError:
            has_null_root_bug = True

        assert not has_list_root_bug, "VULNERABILITY: load_api_keys() returned list, causing AttributeError in get_dynamic_island_config()"
        assert not has_null_root_bug, "VULNERABILITY: load_api_keys() returned None, causing AttributeError in get_dynamic_island_config()"

    def test_windows_cp1252_stdout_logging_crash(self, isolated_config):
        """
        Adversarial challenge: On standard Windows command prompts with CP1252 codepage,
        load_api_keys() line 43 executes `print(f'❌ Failed to load api_keys.json: {e}')`
        which raises UnicodeEncodeError and crashes the process.
        """
        isolated_config.write_text('{"corrupted": true', encoding="utf-8")
        old_stdout = sys.stdout
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        try:
            cfg = config_manager.get_dynamic_island_config()
            assert cfg == config_manager.DEFAULT_DYNAMIC_ISLAND_CONFIG
        finally:
            sys.stdout = old_stdout


# ── 4. High-Concurrency Stress Test ──────────────────────────────────────────

class TestConfigManagerConcurrency:
    """Stress test concurrent read/write access to Dynamic Island config."""

    @pytest.fixture(autouse=True)
    def isolated_config(self, tmp_path, monkeypatch):
        sandbox_dir = tmp_path / "config"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        fake_config_file = sandbox_dir / "api_keys.json"

        monkeypatch.setattr(config_manager, "CONFIG_DIR", sandbox_dir)
        monkeypatch.setattr(config_manager, "CONFIG_FILE", fake_config_file)
        yield fake_config_file

    def test_concurrent_read_write_stress(self):
        """
        Launch 15 worker threads performing concurrent get and save calls.
        Verify consistency and detect any file access collision errors on Windows.
        """
        num_threads = 15
        iterations_per_thread = 30
        errors: List[Exception] = []

        def worker_task(thread_id: int):
            for i in range(iterations_per_thread):
                try:
                    if i % 2 == 0:
                        config_manager.save_dynamic_island_config({
                            "offset_x": thread_id * 10 + i,
                            "scale": 1.0 + (i % 5) * 0.2,
                        })
                    else:
                        cfg = config_manager.get_dynamic_island_config()
                        assert isinstance(cfg, dict)
                        assert "enabled" in cfg
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker_task, args=(tid,)) for tid in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Encountered {len(errors)} errors during concurrent execution: {errors[:5]}"
