"""
core/hud/dynamic_island.py — Top-level floating Dynamic Island 2.0 companion window.

Provides a persistent, floating holographic companion anchored to the display top-center
(below the laptop webcam bezel) that remains visible and interactive even when the
primary JARVIS window is minimized or hidden to the system tray.

Features:
- Pure top-level QWidget (parent=None) owned by application lifecycle.
- Zero keyboard focus theft: WindowDoesNotAcceptFocus, WA_ShowWithoutActivating,
  WS_EX_NOACTIVATE, WM_MOUSEACTIVATE -> MA_NOACTIVATE.
- Suppressed taskbar item and Alt+Tab entry via Qt.WindowType.Tool.
- Sleek translucent rounded capsule pill with radiant cyan perimeter glow.
- 5-layer miniature animated holographic arc reactor on the left (~40 DIP).
- Symmetric mirrored audio waveform visualizer on the right.
- Smooth expansion animation to full companion card.
- Metrics panel: Mic status, Output, Activity description, Circular Core Activity gauge.
- Quick actions: Open JARVIS, Mic Mute toggle, Speech Interrupt, Hide.
- Single-click to expand/collapse, double-click to restore JARVIS.
- Auto-collapse on inactivity with hover/interaction pause.
- Multi-monitor DPI-aware auto-repositioning.
"""
from __future__ import annotations

import logging
import math
import random
import sys
import time
from typing import Any, Optional, Tuple, Union

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.hud.island_core import IslandCore
from core.hud.island_position import IslandAnchor, IslandPositionEngine
from core.hud.island_state import (
    COLOR_BACKGROUND,
    COLOR_ENERGY_AMBER,
    COLOR_ENERGY_HIGHLIGHT,
    COLOR_ERROR,
    COLOR_INNER_SURFACE,
    COLOR_MINT_CYAN,
    COLOR_MUTED_TEXT,
    COLOR_NEUTRAL_TEXT,
    COLOR_PRIMARY_CYAN,
    COLOR_REACTOR_SILVER,
    COLOR_SECONDARY_TEAL,
    COLOR_SUCCESS_GREEN,
    IslandPresentationModel,
    IslandState,
)
from memory.config_manager import (
    get_dynamic_island_config,
    save_dynamic_island_config,
)

logger = logging.getLogger("JARVIS.DynamicIsland")

BASE_COLLAPSED_W = 180
BASE_COLLAPSED_H = 42
BASE_EXPANDED_W = 330
BASE_EXPANDED_H = 175

COLLAPSED_W = BASE_COLLAPSED_W
COLLAPSED_H = BASE_COLLAPSED_H
EXPANDED_W = BASE_EXPANDED_W
EXPANDED_H = BASE_EXPANDED_H


class MirroredWaveformWidget(QWidget):
    """
    Symmetric mirrored audio waveform visualizer.
    Draws animated vertical bars centered along the horizontal axis, responding
    dynamically to voice audio amplitude and state theme colors.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        bar_count: int = 12,
        model: Optional[IslandPresentationModel] = None,
    ) -> None:
        super().__init__(parent)
        self._bar_count = bar_count
        self._model = model
        self._amplitude: float = 0.0
        self._bars: list[float] = [0.08] * bar_count
        self._phase: float = 0.0

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 30 FPS waveform update timer
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._step)
        self._timer.start()

    def set_amplitude(self, amp: float) -> None:
        self._amplitude = max(0.0, min(1.0, float(amp)))

    def _step(self) -> None:
        self._phase = (self._phase + 0.18) % (2.0 * math.pi)
        for i in range(self._bar_count):
            # Center bars naturally have higher default dynamic range
            dist_from_center = abs(i - (self._bar_count - 1) / 2.0) / ((self._bar_count - 1) / 2.0)
            center_weight = 1.0 - 0.45 * dist_from_center

            if self._amplitude > 0.01:
                target = self._amplitude * center_weight * (0.45 + 0.55 * random.random())
                self._bars[i] += (target - self._bars[i]) * 0.48
            else:
                # Organic flowing idle ripple
                idle_wave = 0.08 + 0.05 * math.sin(self._phase + i * 0.6)
                self._bars[i] += (idle_wave - self._bars[i]) * 0.25

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        cy = h / 2.0

        bar_w = 2.4
        gap = max(1.5, (w - (self._bar_count * bar_w)) / max(1, self._bar_count - 1))
        total_w = self._bar_count * bar_w + (self._bar_count - 1) * gap
        start_x = (w - total_w) / 2.0

        # Resolve color from theme
        wave_color = QColor(COLOR_PRIMARY_CYAN)
        if self._model is not None:
            theme = self._model.get_theme_colors()
            wave_color = QColor(theme.get("wave", COLOR_PRIMARY_CYAN))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(wave_color))

        for i in range(self._bar_count):
            val = max(0.06, min(1.0, self._bars[i]))
            bar_h = max(3.0, val * (h - 4.0))
            x = start_x + i * (bar_w + gap)
            y = cy - bar_h / 2.0

            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.2, 1.2)

        p.end()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()
        super().closeEvent(event)


class CircularActivityGauge(QWidget):
    """
    Circular core activity percentage gauge widget.
    Renders an antialiased radial progress arc around a percentage readout.
    """

    def __init__(self, parent: Optional[QWidget] = None, percentage: float = 87.0) -> None:
        super().__init__(parent)
        self._percentage: float = percentage
        self.setFixedSize(56, 56)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_percentage(self, pct: float) -> None:
        self._percentage = max(0.0, min(100.0, float(pct)))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0 - 4.0
        r = 18.0

        rect = QRectF(cx - r, cy - r, r * 2.0, r * 2.0)

        # Background track
        track_pen = QPen(QColor(15, 35, 45, 180), 2.8)
        p.setPen(track_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # Active progress arc
        arc_pen = QPen(QColor(COLOR_PRIMARY_CYAN), 2.8)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)

        span_angle = int(-(self._percentage / 100.0) * 360.0 * 16)
        p.drawArc(rect, 90 * 16, span_angle)

        # Percentage Text
        p.setPen(QColor(COLOR_NEUTRAL_TEXT))
        p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        text_rect = QRectF(cx - r, cy - 8.0, r * 2.0, 16.0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{int(self._percentage)}%")

        # Subtext Label
        p.setPen(QColor(COLOR_MUTED_TEXT))
        p.setFont(QFont("Segoe UI", 6, QFont.Weight.DemiBold))
        sub_rect = QRectF(0, h - 14.0, w, 12.0)
        p.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "Core Activity")

        p.end()


class DynamicIsland(QWidget):
    """
    Floating, topmost Dynamic Island 2.0 desktop companion for J.A.R.V.I.S. — 008.
    """

    # Signals for external listeners
    expanded_changed = pyqtSignal(bool)
    mute_requested = pyqtSignal()
    interrupt_requested = pyqtSignal()
    restore_requested = pyqtSignal()
    hide_requested = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        model: Optional[IslandPresentationModel] = None,
        config: Optional[dict] = None,
    ) -> None:
        super().__init__(parent)
        self._model = model or IslandPresentationModel()
        self._cfg = config or get_dynamic_island_config()
        self._is_expanded: bool = bool(self._cfg.get("expanded", False))
        self._main_window: Optional[QWidget] = None
        self._drag_start: Optional[QPoint] = None
        self._is_hovered: bool = False
        self._glow_phase: float = 0.0
        self._amplitude: float = 0.0

        # Configure Window Characteristics
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Position Engine
        anchor_val = self._cfg.get("anchor", "top_center")
        try:
            anchor_enum = IslandAnchor(anchor_val)
        except ValueError:
            anchor_enum = IslandAnchor.TOP_CENTER

        self._pos_engine = IslandPositionEngine(
            anchor=anchor_enum,
            offset_x=int(self._cfg.get("offset_x", 0)),
            offset_y=int(self._cfg.get("offset_y", 10)),
        )
        self._pos_engine.topology_changed.connect(self.reposition)

        # Geometry Setup
        init_w = EXPANDED_W if self._is_expanded else COLLAPSED_W
        init_h = EXPANDED_H if self._is_expanded else COLLAPSED_H
        self.resize(init_w, init_h)

        # Smooth Geometry Transition Animation
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Inactivity auto-collapse timer (defaults to 5 seconds)
        collapse_ms = int(self._cfg.get("collapse_delay", 5)) * 1000
        self._auto_collapse_timer = QTimer(self)
        self._auto_collapse_timer.setInterval(max(2000, collapse_ms))
        self._auto_collapse_timer.setSingleShot(True)
        self._auto_collapse_timer.timeout.connect(self._on_auto_collapse)

        # Lightweight 30 FPS perimeter edge illumination timer
        self._glow_timer = QTimer(self)
        self._glow_timer.setInterval(33)
        self._glow_timer.timeout.connect(self._step_glow)
        self._glow_timer.start()

        # Build UI Structure
        self._init_ui()
        self.setToolTip("J.A.R.V.I.S. — 008 (Dynamic Island)")

        # Connect to Presentation Model
        self._model.state_changed.connect(self._on_state_changed)
        self._model.status_text_changed.connect(self._on_status_text_changed)
        self._model.audio_level_changed.connect(self._on_audio_changed)
        self._model.mic_status_changed.connect(self._on_mic_status_changed)
        self._model.activity_changed.connect(self._on_activity_desc_changed)
        self._model.core_activity_changed.connect(self._on_core_activity_changed)

        # Initial Positioning
        self.reposition()

        # Windows Native Style Hardening
        self._apply_native_styles()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        """Construct collapsed pill and expanded companion layouts."""
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(5, 3, 5, 3)
        self._root_layout.setSpacing(2)

        # ── Collapsed Header Row ──
        self._header_row = QWidget(self)
        self._header_layout = QHBoxLayout(self._header_row)
        self._header_layout.setContentsMargins(1, 0, 1, 0)
        self._header_layout.setSpacing(4)

        # Left: Miniature Holographic Arc Reactor (5-layer)
        self._core = IslandCore(self._header_row, model=self._model, size=30)
        self.core = self._core  # Contract alias
        self._header_layout.addWidget(self._core)

        # Center: Technical Identity & Status Typography
        self._text_container = QWidget(self._header_row)
        self._text_layout = QVBoxLayout(self._text_container)
        self._text_layout.setContentsMargins(0, 0, 0, 0)
        self._text_layout.setSpacing(0)

        # Brand row with activity dots
        self._brand_row = QWidget(self._text_container)
        self._brand_layout = QHBoxLayout(self._brand_row)
        self._brand_layout.setContentsMargins(0, 0, 0, 0)
        self._brand_layout.setSpacing(3)

        self._lbl_identity = QLabel("J.A.R.V.I.S.", self._brand_row)
        self._lbl_identity.setFont(QFont("Consolas", 7, QFont.Weight.Bold))
        self._lbl_identity.setStyleSheet(f"color: {COLOR_PRIMARY_CYAN}; letter-spacing: 0.5px;")

        self._lbl_dots = QLabel("•••", self._brand_row)
        self._lbl_dots.setFont(QFont("Segoe UI", 5, QFont.Weight.Bold))
        self._lbl_dots.setStyleSheet(f"color: {COLOR_MINT_CYAN};")

        self._brand_layout.addWidget(self._lbl_identity)
        self._brand_layout.addWidget(self._lbl_dots)
        self._brand_layout.addStretch()

        self._lbl_status = QLabel(self._model.get_status_text(), self._text_container)
        self._lbl_status.setFont(QFont("Segoe UI", 6, QFont.Weight.DemiBold))
        self._lbl_status.setStyleSheet(f"color: {COLOR_NEUTRAL_TEXT};")

        self._text_layout.addWidget(self._brand_row)
        self._text_layout.addWidget(self._lbl_status)
        self._header_layout.addWidget(self._text_container, 1)

        # Right: Symmetric Mirrored Audio Waveform
        self._eq = MirroredWaveformWidget(self._header_row, bar_count=9, model=self._model)
        self._eq.setFixedSize(26, 16)
        self._header_layout.addWidget(self._eq)

        # Rightmost expand indicator button
        self._btn_toggle = QPushButton("▼" if not self._is_expanded else "▲", self._header_row)
        self._btn_toggle.setFixedSize(14, 14)
        self._btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLOR_MUTED_TEXT}; border: none; font-size: 7px; }}"
            f"QPushButton:hover {{ color: {COLOR_PRIMARY_CYAN}; }}"
        )
        self._btn_toggle.clicked.connect(self.toggle_expanded)
        self._header_layout.addWidget(self._btn_toggle)

        self._root_layout.addWidget(self._header_row)

        # ── Expanded Quick Controls Panel ──
        self._expanded_panel = QWidget(self)
        self._expanded_vbox = QVBoxLayout(self._expanded_panel)
        self._expanded_vbox.setContentsMargins(4, 4, 4, 2)
        self._expanded_vbox.setSpacing(6)

        # 1. Expanded Waveform Banner
        self._expanded_waveform = MirroredWaveformWidget(self._expanded_panel, bar_count=22, model=self._model)
        self._expanded_waveform.setFixedHeight(22)
        self._expanded_vbox.addWidget(self._expanded_waveform)

        # 2. Status & Metrics Grid
        self._metrics_row = QWidget(self._expanded_panel)
        self._metrics_layout = QHBoxLayout(self._metrics_row)
        self._metrics_layout.setContentsMargins(2, 2, 2, 2)
        self._metrics_layout.setSpacing(8)

        # Left: Key Status Details
        self._status_col = QWidget(self._metrics_row)
        self._status_layout = QVBoxLayout(self._status_col)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        self._status_layout.setSpacing(3)

        self._lbl_mic_status = QLabel("🎙  Microphone:  Active", self._status_col)
        self._lbl_mic_status.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        self._lbl_mic_status.setStyleSheet(f"color: {COLOR_SUCCESS_GREEN};")

        self._lbl_output_status = QLabel("🔊  Output:  On", self._status_col)
        self._lbl_output_status.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        self._lbl_output_status.setStyleSheet(f"color: {COLOR_PRIMARY_CYAN};")

        self._lbl_act_desc = QLabel(f"⚙️  {self._model.get_activity_description()}", self._status_col)
        self._lbl_act_desc.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
        self._lbl_act_desc.setStyleSheet(f"color: {COLOR_NEUTRAL_TEXT};")

        self._status_layout.addWidget(self._lbl_mic_status)
        self._status_layout.addWidget(self._lbl_output_status)
        self._status_layout.addWidget(self._lbl_act_desc)
        self._metrics_layout.addWidget(self._status_col, 1)

        # Right: Circular Core Activity Gauge
        self._core_gauge = CircularActivityGauge(self._metrics_row, percentage=self._model.get_core_activity_pct())
        self._metrics_layout.addWidget(self._core_gauge)

        self._expanded_vbox.addWidget(self._metrics_row)

        # 3. Action Buttons Row (Open, Mute, Interrupt, Hide)
        self._btn_bar = QWidget(self._expanded_panel)
        self._btn_bar_layout = QHBoxLayout(self._btn_bar)
        self._btn_bar_layout.setContentsMargins(0, 2, 0, 0)
        self._btn_bar_layout.setSpacing(5)

        btn_base_style = (
            f"QPushButton {{"
            f"  background: {COLOR_INNER_SURFACE};"
            f"  color: {COLOR_NEUTRAL_TEXT};"
            f"  border: 1px solid {COLOR_SECONDARY_TEAL};"
            f"  border-radius: 4px;"
            f"  padding: 3px 6px;"
            f"  font-family: 'Segoe UI';"
            f"  font-size: 8px;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: #0D2C38;"
            f"  border-color: {COLOR_PRIMARY_CYAN};"
            f"  color: #FFFFFF;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background: #061821;"
            f"}}"
        )

        btn_danger_style = (
            f"QPushButton {{"
            f"  background: {COLOR_INNER_SURFACE};"
            f"  color: {COLOR_ERROR};"
            f"  border: 1px solid {COLOR_ERROR};"
            f"  border-radius: 4px;"
            f"  padding: 3px 6px;"
            f"  font-family: 'Segoe UI';"
            f"  font-size: 8px;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: #2D0B14;"
            f"  color: #FFFFFF;"
            f"}}"
        )

        self._btn_restore = QPushButton("⧉ Open JARVIS", self._btn_bar)
        self._btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_restore.setStyleSheet(btn_base_style)
        self._btn_restore.clicked.connect(self.restore_main_window)
        self._btn_bar_layout.addWidget(self._btn_restore)

        self._btn_mute = QPushButton("🎙 Mute", self._btn_bar)
        self._btn_mute.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_mute.setStyleSheet(btn_base_style)
        self._btn_mute.clicked.connect(self.toggle_mute)
        self._btn_bar_layout.addWidget(self._btn_mute)

        self._btn_interrupt = QPushButton("■ Interrupt", self._btn_bar)
        self._btn_interrupt.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_interrupt.setStyleSheet(btn_danger_style)
        self._btn_interrupt.clicked.connect(self.interrupt_speech)
        self._btn_bar_layout.addWidget(self._btn_interrupt)

        self._btn_hide = QPushButton("⦸ Hide", self._btn_bar)
        self._btn_hide.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_hide.setStyleSheet(btn_base_style)
        self._btn_hide.clicked.connect(self.hide_island)
        self._btn_bar_layout.addWidget(self._btn_hide)

        self._expanded_vbox.addWidget(self._btn_bar)
        self._root_layout.addWidget(self._expanded_panel)

        # Initial visibility of expanded controls
        self._expanded_panel.setVisible(self._is_expanded)

    # ── State and Control Handlers ───────────────────────────────────────────

    def is_expanded(self) -> bool:
        """Return whether the Dynamic Island is currently in expanded mode."""
        return self._is_expanded

    def toggle_expanded(self) -> None:
        """Toggle between collapsed capsule and expanded control card."""
        self.set_expanded(not self._is_expanded)

    def set_expanded(self, expanded: bool) -> None:
        """Expand or collapse the island with smooth geometry transition."""
        if self._is_expanded == expanded:
            return

        self._is_expanded = expanded
        self._btn_toggle.setText("▲" if self._is_expanded else "▼")
        self._expanded_panel.setVisible(self._is_expanded)
        self._root_layout.activate()

        target_w = EXPANDED_W if self._is_expanded else COLLAPSED_W
        target_h = EXPANDED_H if self._is_expanded else COLLAPSED_H

        # Calculate new target position keeping top anchor stable
        target_pos = self._pos_engine.calculate_position(target_w, target_h)
        target_rect = QRect(target_pos.x(), target_pos.y(), target_w, target_h)

        if not self.isVisible():
            self.setGeometry(target_rect)
        else:
            self._anim.stop()
            self._anim.setStartValue(self.geometry())
            self._anim.setEndValue(target_rect)
            self._anim.start()

        if self._is_expanded:
            self._auto_collapse_timer.start()
        else:
            self._auto_collapse_timer.stop()

        self.expanded_changed.emit(self._is_expanded)
        self.update()

    def _on_auto_collapse(self) -> None:
        """Timer callback to automatically return to collapsed state after inactivity."""
        if self._is_expanded and not self._is_hovered:
            self.set_expanded(False)

    def set_main_window(self, win: Optional[QWidget]) -> None:
        """Associate the primary MainWindow instance."""
        self._main_window = win

    def restore_main_window(self) -> None:
        """Unminimize, raise, and activate primary JARVIS application window."""
        self.restore_requested.emit()
        if self._main_window is not None:
            self._main_window.showNormal()
            self._main_window.raise_()
            self._main_window.activateWindow()
        # Collapse island back to capsule after restoring main interface
        self.set_expanded(False)

    def toggle_mute(self) -> None:
        """Toggle microphone mute status."""
        self.mute_requested.emit()
        if self._main_window is not None and hasattr(self._main_window, "_toggle_mute"):
            self._main_window._toggle_mute()
        else:
            new_active = not self._model.is_mic_active()
            self._model.set_mic_active(new_active)

    def interrupt_speech(self) -> None:
        """Trigger immediate voice synthesis cancellation."""
        self.interrupt_requested.emit()
        if self._main_window is not None and hasattr(self._main_window, "interrupt"):
            self._main_window.interrupt()
        self._model.reset_audio()
        self._model.set_state(IslandState.IDLE)

    def hide_island(self) -> None:
        """Temporarily hide Dynamic Island to system tray."""
        self.hide_requested.emit()
        self.hide()

    def on_mute_clicked(self) -> None:
        """Contract alias for toggle_mute."""
        self.toggle_mute()

    # ── Presentation Model Sync ──────────────────────────────────────────────

    def set_state(self, state: Union[str, IslandState]) -> None:
        """Ingest new JARVIS operating state."""
        self._model.set_state(state)

    def set_audio_level(self, level: float) -> None:
        """Ingest live audio amplitude [0.0, 1.0]."""
        self._amplitude = max(0.0, min(1.0, float(level)))
        self._model.set_audio_level(level)
        self._eq.set_amplitude(level)
        if hasattr(self, "_expanded_waveform"):
            self._expanded_waveform.set_amplitude(level)

    def _on_state_changed(self, state: IslandState) -> None:
        self.update()

    def _on_status_text_changed(self, text: str) -> None:
        self._lbl_status.setText(text)
        self.update()

    def _on_audio_changed(self, level: float) -> None:
        self._amplitude = max(0.0, min(1.0, float(level)))
        self._eq.set_amplitude(level)
        if hasattr(self, "_expanded_waveform"):
            self._expanded_waveform.set_amplitude(level)

    def _on_mic_status_changed(self, active: bool) -> None:
        status_str = "Active" if active else "Muted"
        color_str = COLOR_SUCCESS_GREEN if active else COLOR_ERROR
        self._lbl_mic_status.setText(f"🎙  Microphone:  {status_str}")
        self._lbl_mic_status.setStyleSheet(f"color: {color_str};")
        self._btn_mute.setText("🎙 Unmute" if not active else "🎙 Mute")

    def _on_activity_desc_changed(self, desc: str) -> None:
        self._lbl_act_desc.setText(f"⚙️  {desc}")

    def _on_core_activity_changed(self, pct: float) -> None:
        self._core_gauge.set_percentage(pct)

    # ── Positioning, DPI Scaling, and Animation Ticks ─────────────────────────

    def get_dpi_scale(self) -> float:
        """Calculate screen DPI scaling ratio relative to standard 96 DPI baseline."""
        screen = self.screen() or (QApplication.primaryScreen() if QApplication.instance() else None)
        if screen:
            dpi = screen.logicalDotsPerInch()
            return max(1.0, dpi / 96.0)
        return 1.0

    def _step_glow(self) -> None:
        """Lightweight 30 FPS timer callback driving animated perimeter edge lighting."""
        if not self.isVisible():
            return

        state = self._model.get_state()
        if state == IslandState.IDLE:
            step = 0.035
        elif state == IslandState.LISTENING:
            step = 0.05
        elif state == IslandState.THINKING:
            step = 0.12
        elif state == IslandState.SPEAKING:
            step = 0.07 + 0.08 * self._amplitude
        elif state == IslandState.ERROR:
            step = 0.04
        else:
            step = 0.09

        self._glow_phase = (self._glow_phase + step) % (2.0 * math.pi)
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, "_glow_timer") and not self._glow_timer.isActive():
            self._glow_timer.start()

    def hideEvent(self, event) -> None:
        if hasattr(self, "_glow_timer") and self._glow_timer.isActive():
            self._glow_timer.stop()
        super().hideEvent(event)

    def reposition(self) -> None:
        """Recalculate and apply screen positioning."""
        w = EXPANDED_W if self._is_expanded else COLLAPSED_W
        h = EXPANDED_H if self._is_expanded else COLLAPSED_H
        pos = self._pos_engine.calculate_position(w, h)
        self.move(pos)

    # ── Painting and Capsule Appearance ──────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw holographic translucent pill/card surface with radiant glowing border."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        radius = (self.height() / 2.0 - 1.0) if not self._is_expanded else 14.0

        theme = self._model.get_theme_colors()
        border_hex = theme.get("border", COLOR_PRIMARY_CYAN)
        glow_hex = theme.get("glow", COLOR_PRIMARY_CYAN)
        state = self._model.get_state()

        # Dynamic Edge Illumination & State Modulation
        if state == IslandState.IDLE:
            breath = 0.78 + 0.22 * math.sin(self._glow_phase * 1.6)
            base_alpha = 135.0 * breath
        elif state == IslandState.LISTENING:
            base_alpha = 195.0
        elif state == IslandState.THINKING:
            pulse = 0.82 + 0.18 * math.sin(self._glow_phase * 3.2)
            base_alpha = 185.0 * pulse
        elif state == IslandState.SPEAKING:
            base_alpha = min(255.0, 145.0 + self._amplitude * 110.0)
        elif state == IslandState.ERROR:
            alarm = 0.70 + 0.30 * math.sin(self._glow_phase * 4.5)
            base_alpha = 215.0 * alarm
        else:
            base_alpha = 140.0

        if not self._model.is_mic_active():
            base_alpha *= 0.55  # Dimmed when muted

        if self._is_hovered:
            base_alpha = min(255.0, base_alpha * 1.3 + 35.0)  # Smooth hover illumination

        # 1. Soft Edge Glow & Gentle Ambient Halo (2 outer passes)
        halo_color = QColor(glow_hex)
        p.setBrush(Qt.BrushStyle.NoBrush)

        halo_color.setAlpha(max(10, int(base_alpha * 0.18)))
        p.setPen(QPen(halo_color, 2.8))
        p.drawRoundedRect(rect.adjusted(-1.5, -1.5, 1.5, 1.5), radius + 1.5, radius + 1.5)

        halo_color.setAlpha(max(15, int(base_alpha * 0.42)))
        p.setPen(QPen(halo_color, 1.8))
        p.drawRoundedRect(rect.adjusted(-0.6, -0.6, 0.6, 0.6), radius + 0.6, radius + 0.6)

        # 2. Translucent Background Surface
        surface_color = QColor(COLOR_BACKGROUND)
        surface_color.setAlpha(228)
        p.setBrush(QBrush(surface_color))

        # 3. Thin Outer Border
        border_color = QColor(border_hex)
        border_color.setAlpha(min(255, int(base_alpha)))
        p.setPen(QPen(border_color, 1.2))
        p.drawRoundedRect(rect, radius, radius)

        # 4. Slightly Brighter Curved End Caps (specular corner accents)
        if not self._is_expanded:
            accent_color = QColor(COLOR_ENERGY_HIGHLIGHT if state == IslandState.SPEAKING else COLOR_MINT_CYAN)
            accent_color.setAlpha(min(255, int(base_alpha * 0.55)))
            p.setPen(QPen(accent_color, 1.0))
            # Left semicircular cap accent
            p.drawArc(QRectF(1.0, 1.0, (radius * 2.0), (radius * 2.0)), 90 * 16, 180 * 16)
            # Right semicircular cap accent
            p.drawArc(QRectF(rect.right() - radius * 2.0, 1.0, (radius * 2.0), (radius * 2.0)), -90 * 16, 180 * 16)

        # 5. Small Moving Light Highlights / Traveling Light Photon Sweep
        w_straight = max(0.0, rect.width() - 2.0 * radius)
        semi_len = math.pi * radius
        total_p = 2.0 * w_straight + 2.0 * semi_len

        if total_p > 0.0:
            def _get_perimeter_pos(t_norm: float) -> Tuple[float, float]:
                d = (t_norm % 1.0) * total_p
                if d < w_straight:
                    return (rect.left() + radius + d, rect.top())
                d -= w_straight
                if d < semi_len:
                    ang = -math.pi / 2.0 + (d / semi_len) * math.pi
                    return (rect.right() - radius + radius * math.cos(ang), rect.top() + radius + radius * math.sin(ang))
                d -= semi_len
                if d < w_straight:
                    return (rect.right() - radius - d, rect.bottom())
                d -= w_straight
                ang = math.pi / 2.0 + (d / semi_len) * math.pi
                return (rect.left() + radius + radius * math.cos(ang), rect.top() + radius + radius * math.sin(ang))

            # Primary traveling highlight photon
            t1 = (self._glow_phase / (2.0 * math.pi)) % 1.0
            x1, y1 = _get_perimeter_pos(t1)

            # Draw glowing photon bead
            p.setPen(Qt.PenStyle.NoPen)
            photon_halo = QColor(COLOR_ENERGY_HIGHLIGHT if state in (IslandState.SPEAKING, IslandState.THINKING) else COLOR_PRIMARY_CYAN)
            photon_halo.setAlpha(min(255, int(base_alpha * 0.5)))
            p.setBrush(QBrush(photon_halo))
            p.drawEllipse(QPointF(x1, y1), 3.2, 3.2)

            photon_core = QColor("#FFFFFF")
            photon_core.setAlpha(min(255, int(base_alpha * 0.9)))
            p.setBrush(QBrush(photon_core))
            p.drawEllipse(QPointF(x1, y1), 1.5, 1.5)

            # Secondary trailing highlight for Thinking / Speaking
            if state in (IslandState.THINKING, IslandState.SPEAKING):
                t2 = (t1 + 0.5) % 1.0
                x2, y2 = _get_perimeter_pos(t2)
                p.setBrush(QBrush(photon_halo))
                p.drawEllipse(QPointF(x2, y2), 2.5, 2.5)
                p.setBrush(QBrush(photon_core))
                p.drawEllipse(QPointF(x2, y2), 1.2, 1.2)

        # 6. Inner Edge Rim Highlight
        inner_rect = rect.adjusted(1.0, 1.0, -1.0, -1.0)
        inner_pen = QPen(QColor(COLOR_INNER_SURFACE), 0.9)
        p.setPen(inner_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(inner_rect, max(1.0, radius - 1.0), max(1.0, radius - 1.0))

        p.end()

    # ── Mouse Interaction, Double-Click & Dragging ───────────────────────────

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
        if self._auto_collapse_timer.isActive():
            self._auto_collapse_timer.stop()  # Pause auto collapse while interacting
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
        if self._is_expanded and not self._auto_collapse_timer.isActive():
            self._auto_collapse_timer.start()  # Resume auto collapse on leave
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-clicking the island restores the primary full JARVIS window."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.restore_main_window()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_start
            self.move(new_pos)
            # Update custom offsets
            self._pos_engine.anchor = IslandAnchor.CUSTOM
            self._pos_engine.offset_x = new_pos.x()
            self._pos_engine.offset_y = new_pos.y()
            if self._auto_collapse_timer.isActive():
                self._auto_collapse_timer.start()  # Reset timer on move
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)

    # ── Platform Non-Activation & Win32 Integration ──────────────────────────

    def _apply_native_styles(self) -> None:
        """Apply Windows extended styles if on Windows desktop with valid HWND."""
        if sys.platform != "win32":
            return
        pass

    def nativeEvent(self, event_type: Any, message: Any) -> Tuple[bool, int]:
        """
        Intercept Windows messages to ensure mouse interaction does not steal focus
        from other applications (WM_MOUSEACTIVATE -> MA_NOACTIVATE).
        """
        if sys.platform == "win32" and event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            try:
                import ctypes
                from ctypes import wintypes

                class MSG(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", wintypes.HWND),
                        ("message", wintypes.UINT),
                        ("wParam", wintypes.WPARAM),
                        ("lParam", wintypes.LPARAM),
                        ("time", wintypes.DWORD),
                        ("pt", wintypes.POINT),
                    ]

                msg = MSG.from_address(int(message))
                if msg.message == 0x0021:  # WM_MOUSEACTIVATE
                    MA_NOACTIVATE = 3
                    return True, MA_NOACTIVATE
            except Exception:
                pass
        return False, 0

    # ── Teardown ──────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Halt timers and clean up resources on application exit."""
        if hasattr(self, "_glow_timer") and self._glow_timer.isActive():
            self._glow_timer.stop()
        if hasattr(self, "_auto_collapse_timer") and self._auto_collapse_timer.isActive():
            self._auto_collapse_timer.stop()
        if hasattr(self, "_anim") and self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
        if hasattr(self, "_core") and hasattr(self._core, "close"):
            self._core.close()
        if hasattr(self, "_eq") and hasattr(self._eq, "close"):
            self._eq.close()
        if hasattr(self, "_expanded_waveform") and hasattr(self._expanded_waveform, "close"):
            self._expanded_waveform.close()
        super().closeEvent(event)
