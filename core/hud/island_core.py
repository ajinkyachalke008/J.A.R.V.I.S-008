"""
core/hud/island_core.py — Miniature Holographic Arc Reactor (Dynamic Island 2.0).

Recreates the 5-layer animated arc reactor companion using pure PyQt6 QPainter:
- Layer 1: Central Energy Nucleus (warm white core with breathing & audio-reactive radial glow).
- Layer 2: Golden Energy Sphere (geodesic wireframe lattice with rotating nodes & connecting chords).
- Layer 3: Inner Mechanical Containment Rings (counter-rotating concentric segmented rings with radial ticks).
- Layer 4: Outer Metallic Containment Cage (silver-white/cyan technical frame with structural brackets).
- Layer 5: Four Radial Mechanical Connectors (4-axis stabilizers at 12, 3, 6, 9 o'clock with audio expansion).
- Performance quality profiles: LOW (24 FPS), BALANCED (30 FPS), HIGH (60 FPS).
"""
from __future__ import annotations

import math
import time
from typing import Optional, Union

from PyQt6.QtCore import QPointF, QRectF, QTimer, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from core.hud.island_state import (
    COLOR_ENERGY_AMBER,
    COLOR_ENERGY_HIGHLIGHT,
    COLOR_ERROR,
    COLOR_PRIMARY_CYAN,
    COLOR_REACTOR_SILVER,
    COLOR_SECONDARY_TEAL,
    IslandPresentationModel,
    IslandState,
)


class IslandCore(QWidget):
    """
    Miniature Holographic Arc Reactor (~36-54 DIP circular footprint).
    Acts as the living visual heartbeat of the Dynamic Island companion.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        model: Optional[IslandPresentationModel] = None,
        size: int = 42,
        quality: str = "balanced",
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._state: IslandState = IslandState.IDLE
        self._status_text: str = "IDLE"
        self._audio_level: float = 0.0  # Normalized smoothed amplitude [0.0, 1.0]
        self._phase: float = 0.0  # Primary rotation phase (radians)
        self._pulse: float = 1.0  # Breathing / audio expansion factor
        self._quality: str = quality.lower()
        self._last_step_t: float = time.time()

        # Appearance & Geometry
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Animation Timer Configuration
        self._timer = QTimer(self)
        self._anim_timer = self._timer  # Alias for contract compatibility
        self._apply_quality_interval()
        self._timer.timeout.connect(self._step)
        self._timer.start()

        # Connect to presentation model if provided
        if self._model is not None:
            self._model.state_changed.connect(self._on_model_state_changed)
            self._model.status_text_changed.connect(self._on_model_status_changed)
            self._model.audio_level_changed.connect(self._on_model_audio_changed)
            self._state = self._model.get_state()
            self._status_text = self._model.get_status_text()
            self._audio_level = self._model.get_display_amplitude()

    # ── Quality and Performance ───────────────────────────────────────────────

    def set_quality(self, quality: str) -> None:
        """Set animation rendering quality: 'low', 'balanced', or 'high'."""
        q = quality.lower()
        if q in ("low", "balanced", "high") and q != self._quality:
            self._quality = q
            self._apply_quality_interval()

    def _apply_quality_interval(self) -> None:
        """Adjust timer FPS based on quality profile."""
        if self._quality == "low":
            self._timer.setInterval(42)  # ~24 FPS
        elif self._quality == "high":
            self._timer.setInterval(16)  # ~60 FPS
        else:  # balanced
            self._timer.setInterval(28)  # ~35 FPS (conforms to 10-33ms tests)

    # ── State and Audio Ingestion ─────────────────────────────────────────────

    def set_state(self, state: Union[IslandState, str]) -> None:
        """Update core operating state directly or via normalized string."""
        if isinstance(state, IslandState):
            new_state = state
            new_text = state.value
        elif self._model is not None:
            new_state = self._model.normalize_state(state)
            new_text = str(state or "").strip().upper()
        else:
            key = str(state or "").strip().upper()
            try:
                new_state = IslandState(key)
            except ValueError:
                new_state = IslandState.IDLE
            new_text = key

        self._state = new_state
        self._status_text = new_text
        self.update()

    def set_audio_level(self, level: float) -> None:
        """Update live audio amplitude [0.0, 1.0]."""
        try:
            lv = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            return
        self._audio_level = lv
        self.update()

    def _on_model_state_changed(self, state: IslandState) -> None:
        self.set_state(state)

    def _on_model_status_changed(self, text: str) -> None:
        self._status_text = text.upper()
        self.update()

    def _on_model_audio_changed(self, level: float) -> None:
        self.set_audio_level(level)

    # ── Animation Step ────────────────────────────────────────────────────────

    def _step(self) -> None:
        """Advance angular phase and calculate pulse expansion."""
        now = time.time()
        dt = min(0.06, max(0.001, now - self._last_step_t))
        self._last_step_t = now

        # Rotation velocity determined by current operating state
        if self._state == IslandState.THINKING or self._status_text == "PROCESSING":
            speed = 3.8
        elif self._state == IslandState.SPEAKING:
            speed = 2.4 + self._audio_level * 3.2
        elif self._state == IslandState.LISTENING:
            speed = 1.8 + self._audio_level * 1.8
        elif self._state == IslandState.ERROR:
            speed = 1.2
        elif self._status_text == "SLEEPING" or self._state == IslandState.OFFLINE:
            speed = 0.25
        elif self._status_text == "MUTED":
            speed = 0.4
        else:  # IDLE
            speed = 0.85

        self._phase = (self._phase + speed * dt) % (2.0 * math.pi)

        # Pulse expansion: gentle organic breath + voice reactive lift
        if self._status_text == "SLEEPING":
            base_breath = 0.015 * math.sin(self._phase * 0.8)
            audio_lift = 0.0
        else:
            base_breath = 0.035 * math.sin(self._phase * 1.6)
            audio_lift = self._audio_level * 0.22

        self._pulse = 1.0 + base_breath + audio_lift
        self.update()

    # ── 5-Layer Arc Reactor Painter ───────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the 5-layer miniature holographic arc reactor."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        base_radius = min(cx, cy) - 3.0

        if base_radius <= 2.0:
            p.end()
            return

        # Overall dynamic radius scaled by breath & speech pulse
        r = base_radius * self._pulse

        # Resolve Theme Colors
        theme = (
            self._model.get_theme_colors()
            if self._model is not None
            else IslandPresentationModel.get_theme_colors_for_state(self._state)
        )
        c_core = QColor(theme.get("core", COLOR_ENERGY_AMBER))
        c_nucleus = QColor(theme.get("nucleus", COLOR_ENERGY_HIGHLIGHT))
        c_cage = QColor(theme.get("cage", COLOR_REACTOR_SILVER))
        c_wave = QColor(theme.get("wave", COLOR_PRIMARY_CYAN))

        # ── LAYER 1: Central Energy Nucleus (Breathing Glow) ─────────────────
        r_nucleus = max(3.0, r * 0.25 * (1.0 + self._audio_level * 0.45))
        nuc_grad = QRadialGradient(cx, cy, r_nucleus * 2.2)
        nuc_c0 = QColor(c_nucleus)
        nuc_c0.setAlpha(255)
        nuc_c1 = QColor(c_core)
        nuc_c1.setAlpha(int(min(255, 160 + 95 * self._audio_level)))
        nuc_c2 = QColor(c_core)
        nuc_c2.setAlpha(0)

        nuc_grad.setColorAt(0.0, nuc_c0)
        nuc_grad.setColorAt(0.35, nuc_c1)
        nuc_grad.setColorAt(1.0, nuc_c2)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(nuc_grad))
        p.drawEllipse(QRectF(cx - r_nucleus * 2.2, cy - r_nucleus * 2.2, r_nucleus * 4.4, r_nucleus * 4.4))

        # ── LAYER 2: Golden Energy Sphere (Geometric Core) ───────────────────
        r_sphere = r * 0.46
        num_nodes = 8 if self._quality != "low" else 6
        sphere_nodes: list[QPointF] = []
        angle_step = 2.0 * math.pi / num_nodes
        sphere_rot = self._phase * 1.05

        for i in range(num_nodes):
            ang = sphere_rot + i * angle_step
            nx = cx + r_sphere * math.cos(ang)
            ny = cy + r_sphere * math.sin(ang)
            sphere_nodes.append(QPointF(nx, ny))

        # Connecting lattice chords
        chord_pen = QPen(c_core, 1.0)
        chord_c = QColor(c_core)
        chord_c.setAlpha(int(min(255, 90 + 120 * self._audio_level)))
        chord_pen.setColor(chord_c)
        p.setPen(chord_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        for i in range(num_nodes):
            next_idx = (i + 2) % num_nodes
            p.drawLine(sphere_nodes[i], sphere_nodes[next_idx])

        # Luminous vertex dots
        dot_pen = QPen(c_nucleus, 1.5)
        p.setPen(dot_pen)
        for pt in sphere_nodes:
            p.drawPoint(pt)

        # ── LAYER 3: Inner Mechanical Containment Rings (Counter-Rotation) ───
        r_inner1 = r * 0.64
        r_inner2 = r * 0.75
        inner_rot_deg = -math.degrees(self._phase * 1.3)

        # Concentric ring A (Segmented Luminous Arcs)
        ring_pen = QPen(c_core, 1.3)
        p.setPen(ring_pen)
        rect_in1 = QRectF(cx - r_inner1, cy - r_inner1, r_inner1 * 2.0, r_inner1 * 2.0)
        span_in1 = int(75 * 16)
        for offset_deg in (0, 120, 240):
            p.drawArc(rect_in1, int((inner_rot_deg + offset_deg) * 16), span_in1)

        # Concentric ring B (Radial Technical Ticks)
        if self._quality != "low":
            tick_pen = QPen(c_core, 1.0)
            c_tick = QColor(c_core)
            c_tick.setAlpha(150)
            tick_pen.setColor(c_tick)
            p.setPen(tick_pen)
            tick_count = 18
            for k in range(tick_count):
                a = math.radians(k * (360.0 / tick_count) + inner_rot_deg)
                cos_a, sin_a = math.cos(a), math.sin(a)
                p.drawLine(
                    QPointF(cx + cos_a * (r_inner2 - 2.0), cy + sin_a * (r_inner2 - 2.0)),
                    QPointF(cx + cos_a * (r_inner2 + 2.0), cy + sin_a * (r_inner2 + 2.0)),
                )

        # ── LAYER 4: Outer Metallic Containment Cage (Mechanical Frame) ──────
        r_cage = r * 0.88
        outer_rot_deg = math.degrees(self._phase * 0.6)
        cage_pen = QPen(c_cage, 1.4)
        p.setPen(cage_pen)
        rect_cage = QRectF(cx - r_cage, cy - r_cage, r_cage * 2.0, r_cage * 2.0)

        # 4 Mechanical frame segments with small structural gaps
        span_cage = int(68 * 16)
        for cage_deg in (10, 100, 190, 280):
            p.drawArc(rect_cage, int((outer_rot_deg + cage_deg) * 16), span_cage)

        # Outer guide rail
        rail_pen = QPen(c_cage, 0.9)
        c_rail = QColor(c_cage)
        c_rail.setAlpha(110)
        rail_pen.setColor(c_rail)
        p.setPen(rail_pen)
        p.drawEllipse(rect_cage)

        # ── LAYER 5: Four Radial Mechanical Connectors (4-Axis Stabilizers) ──
        # 4 Stabilizers anchored at cardinal directions (12, 3, 6, 9 o'clock)
        # Speech amplitude creates a subtle outward pneumatic expansion pulse
        conn_pulse = 1.0 + self._audio_level * 0.16
        r_conn_in = r * 0.82
        r_conn_out = r * 1.04 * conn_pulse
        w_conn = max(2.5, r * 0.18)

        conn_pen = QPen(c_cage, 1.3)
        p.setPen(conn_pen)
        conn_brush = QBrush(QColor(10, 24, 32, 210))
        p.setBrush(conn_brush)

        # Angles: 0 (Right/3 o'clock), 90 (Bottom/6 o'clock), 180 (Left/9 o'clock), 270 (Top/12 o'clock)
        for base_ang in (0.0, 90.0, 180.0, 270.0):
            rad_ang = math.radians(base_ang)
            cos_b, sin_b = math.cos(rad_ang), math.sin(rad_ang)
            perp_x, perp_y = -sin_b, cos_b  # Perpendicular unit vector

            # Base contact points
            b1 = QPointF(cx + cos_b * r_conn_in + perp_x * (w_conn * 0.6), cy + sin_b * r_conn_in + perp_y * (w_conn * 0.6))
            b2 = QPointF(cx + cos_b * r_conn_in - perp_x * (w_conn * 0.6), cy + sin_b * r_conn_in - perp_y * (w_conn * 0.6))
            # Outer clamp tips
            t1 = QPointF(cx + cos_b * r_conn_out + perp_x * (w_conn * 0.5), cy + sin_b * r_conn_out + perp_y * (w_conn * 0.5))
            t2 = QPointF(cx + cos_b * r_conn_out - perp_x * (w_conn * 0.5), cy + sin_b * r_conn_out - perp_y * (w_conn * 0.5))

            # Draw clamp polygon
            p.drawPolygon([b1, t1, t2, b2])

            # Stabilizer center groove
            groove_pen = QPen(c_core, 1.0)
            p.setPen(groove_pen)
            p.drawLine(
                QPointF(cx + cos_b * (r_conn_in + 1.0), cy + sin_b * (r_conn_in + 1.0)),
                QPointF(cx + cos_b * (r_conn_out - 1.0), cy + sin_b * (r_conn_out - 1.0)),
            )

            # Luminous contact node at base
            pin_pen = QPen(c_nucleus, 1.5)
            p.setPen(pin_pen)
            p.drawPoint(QPointF(cx + cos_b * r_conn_in, cy + sin_b * r_conn_in))

        # Ambient Perimeter Halo
        halo_r = r * 1.08
        halo_grad = QRadialGradient(cx, cy, halo_r)
        halo_c = QColor(c_core)
        halo_c.setAlpha(int(min(255, 30 + 100 * self._audio_level)))
        halo_grad.setColorAt(0.7, halo_c)
        halo_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(halo_grad))
        p.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2.0, halo_r * 2.0))

        p.end()

    # ── Teardown ──────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Safely halt animation timer on window close."""
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()
        super().closeEvent(event)
