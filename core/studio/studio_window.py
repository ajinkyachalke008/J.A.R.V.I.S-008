"""
core/studio/studio_window.py — Native PyQt6 interactive Creation Studio window for JARVIS MARK LVI.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .cad_engine import CADEngine
from .circuit_engine import CircuitEngine
from .exporters import DXFExporter, JSONExporter, PNGExporter, SVGExporter
from .models import Element, StudioProject
from .project_manager import get_project_manager
from .workflow_engine import WorkflowEngine

logger = logging.getLogger("JARVIS.Studio.Window")

# Palette
C_BG = "#00060a"
C_PANEL = "#010d14"
C_BORDER = "#0d3347"
C_BORDER_B = "#1a5c7a"
C_PRI = "#00d4ff"
C_PRI_DIM = "#007a99"
C_TEXT = "#8ffcff"
C_TEXT_DIM = "#3a8a9a"


class StudioCanvasView(QGraphicsView):
    """Interactive pan and zoom graphics canvas with grid snapping."""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QBrush(QColor(C_PANEL)))
        self.setStyleSheet(f"border: 1px solid {C_BORDER}; background: {C_PANEL};")

        self._panning = False
        self._pan_start = QPointF()

    def wheelEvent(self, event: QWheelEvent):
        """Zoom in / zoom out with mouse wheel."""
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.SpaceModifier
        ):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class StudioWindow(QMainWindow):
    """Main window for the Universal Creation Studio."""

    def __init__(self):
        super().__init__()
        self._proj_mgr = get_project_manager()
        self._proj_mgr.register_change_listener(self._on_project_changed)

        self.setWindowTitle("JARVIS CREATION STUDIO — [Universal CAD & Schematics]")
        self.resize(1200, 800)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {C_BG}; }}
            QWidget {{ background: {C_BG}; color: {C_TEXT}; font-family: 'Courier New', monospace; }}
            QTableWidget {{ background: {C_PANEL}; border: 1px solid {C_BORDER}; gridline-color: {C_BORDER}; }}
            QHeaderView::section {{ background: {C_PANEL}; color: {C_PRI}; border: 1px solid {C_BORDER}; }}
        """)

        self._scene = QGraphicsScene()
        self._canvas_view = StudioCanvasView(self._scene, self)

        self._init_ui()
        # Load default demonstrator
        self.load_demonstrator("cad")

    def _init_ui(self) -> None:
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. Top Toolbar
        toolbar = self._build_toolbar()
        main_layout.addWidget(toolbar)

        # 2. Central Splitter (Canvas + Property Panel)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._canvas_view)

        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)

        # 3. Status Bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.setStyleSheet(f"background: {C_PANEL}; color: {C_TEXT_DIM}; border-top: 1px solid {C_BORDER};")
        self._status_bar.showMessage("Ready. Canvas units: mm | Snap: ON")

    def _build_toolbar(self) -> QWidget:
        tb = QWidget()
        tb.setFixedHeight(48)
        tb.setStyleSheet(f"background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 4px;")
        lay = QHBoxLayout(tb)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(8)

        # Domain / Demonstrator Selector
        lay.addWidget(QLabel("DOMAIN:"))
        self._domain_combo = QComboBox()
        self._domain_combo.addItems(["Mechanical CAD", "Circuit Schematics", "Workflow Diagrams"])
        self._domain_combo.currentIndexChanged.connect(self._on_domain_changed)
        self._domain_combo.setStyleSheet(f"background: #011520; color: {C_PRI}; border: 1px solid {C_BORDER_B}; padding: 4px;")
        lay.addWidget(self._domain_combo)

        # Demo Loader Button
        demo_btn = self._make_btn("⚡ LOAD DEMO", self._load_current_demo)
        lay.addWidget(demo_btn)

        lay.addSpacing(16)

        # Export Buttons
        dxf_btn = self._make_btn("💾 EXPORT DXF", self._export_dxf)
        svg_btn = self._make_btn("📄 EXPORT SVG", self._export_svg)
        png_btn = self._make_btn("🖼️ EXPORT PNG", self._export_png)
        lay.addWidget(dxf_btn)
        lay.addWidget(svg_btn)
        lay.addWidget(png_btn)

        lay.addStretch()

        # Undo / Redo
        undo_btn = self._make_btn("↶ UNDO", self._proj_mgr.undo)
        redo_btn = self._make_btn("↷ REDO", self._proj_mgr.redo)
        lay.addWidget(undo_btn)
        lay.addWidget(redo_btn)

        return tb

    def _build_right_panel(self) -> QWidget:
        p = QWidget()
        p.setFixedWidth(280)
        p.setStyleSheet(f"background: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 4px;")
        lay = QVBoxLayout(p)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        hdr = QLabel("PROJECT ELEMENTS")
        hdr.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C_PRI}; border-bottom: 1px solid {C_BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)

        self._elements_table = QTableWidget(0, 2)
        self._elements_table.setHorizontalHeaderLabels(["ID", "Type"])
        self._elements_table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._elements_table)

        return p

    def _make_btn(self, text: str, callback) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: #011520; color: {C_PRI};
                border: 1px solid {C_BORDER_B}; border-radius: 3px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ background: #012438; border-color: {C_PRI}; color: #ffffff; }}
        """)
        btn.clicked.connect(callback)
        return btn

    def _on_domain_changed(self, index: int):
        domain_keys = ["cad", "circuit", "workflow"]
        self.load_demonstrator(domain_keys[index])

    def _load_current_demo(self):
        idx = self._domain_combo.currentIndex()
        domain_keys = ["cad", "circuit", "workflow"]
        self.load_demonstrator(domain_keys[idx])

    def load_demonstrator(self, domain: str = "cad") -> None:
        if domain == "cad":
            proj = CADEngine.create_mounting_plate_demonstrator()
        elif domain == "circuit":
            proj = CircuitEngine.create_regulator_demonstrator()
        else:
            proj = WorkflowEngine.create_agent_loop_demonstrator()

        self._proj_mgr.set_project(proj)

    def _on_project_changed(self, project: StudioProject) -> None:
        """Render project elements on QGraphicsScene."""
        self._scene.clear()
        w = project.canvas.width
        h = project.canvas.height
        self._scene.setSceneRect(0, 0, w, h)

        # Draw grid
        spacing = project.canvas.grid_spacing
        grid_pen = QPen(QColor("#031d2e"), 0.5, Qt.PenStyle.DotLine)
        for x in range(0, int(w) + 1, int(spacing)):
            self._scene.addLine(x, 0, x, h, grid_pen)
        for y in range(0, int(h) + 1, int(spacing)):
            self._scene.addLine(0, y, w, y, grid_pen)

        # Draw elements
        layer_map = {l.id: l for l in project.layers}
        self._elements_table.setRowCount(0)

        for row, el in enumerate(project.elements):
            layer = layer_map.get(el.layer_id, project.layers[0])
            if not layer.visible:
                continue

            geo = el.geometry
            st = el.style
            stroke_color = QColor(st.get("stroke", layer.color))
            stroke_w = float(st.get("stroke_width", 1.5))
            pen = QPen(stroke_color, stroke_w)

            fill_str = st.get("fill", "none")
            brush = QBrush(QColor(fill_str)) if fill_str != "none" else QBrush(Qt.BrushStyle.NoBrush)

            if el.type == "line":
                self._scene.addLine(geo.get("x1", 0), geo.get("y1", 0), geo.get("x2", 0), geo.get("y2", 0), pen)

            elif el.type in ("rect", "component"):
                rx, ry = float(geo.get("x", 0)), float(geo.get("y", 0))
                rw, rh = float(geo.get("width", 10)), float(geo.get("height", 10))
                cr = float(geo.get("corner_radius", 0))
                if cr > 0:
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(rx, ry, rw, rh), cr, cr)
                    self._scene.addPath(path, pen, brush)
                else:
                    self._scene.addRect(QRectF(rx, ry, rw, rh), pen, brush)

            elif el.type == "circle":
                cx, cy = float(geo.get("cx", 0)), float(geo.get("cy", 0))
                r = float(geo.get("r", geo.get("radius", 5)))
                self._scene.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r), pen, brush)

            elif el.type == "wire":
                self._scene.addLine(geo.get("x1", 0), geo.get("y1", 0), geo.get("x2", 0), geo.get("y2", 0), pen)

            elif el.type == "dimension":
                x1, y1 = float(geo.get("x1", 0)), float(geo.get("y1", 0))
                x2, y2 = float(geo.get("x2", 0)), float(geo.get("y2", 0))
                txt = geo.get("text", f"{geo.get('value', 0):.1f}")
                dim_pen = QPen(stroke_color, 1.0, Qt.PenStyle.DashLine)
                self._scene.addLine(x1, y1, x2, y2, dim_pen)
                text_item = self._scene.addText(str(txt), QFont("Courier New", 8))
                text_item.setDefaultTextColor(stroke_color)
                text_item.setPos((x1 + x2) / 2.0 - 15, (y1 + y2) / 2.0 - 12)

            # Update Elements table
            self._elements_table.insertRow(row)
            self._elements_table.setItem(row, 0, QTableWidgetItem(el.id))
            self._elements_table.setItem(row, 1, QTableWidgetItem(el.type))

        self._status_bar.showMessage(f"Project '{project.title}' | {len(project.elements)} elements | Canvas: {w}x{h} {project.canvas.units}")

    def _export_dxf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export DXF", "mounting_plate.dxf", "DXF Files (*.dxf)")
        if path:
            DXFExporter.export(self._proj_mgr.project, path)
            QMessageBox.information(self, "Export Successful", f"CAD project exported to:\n{path}")

    def _export_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "creation.svg", "SVG Files (*.svg)")
        if path:
            SVGExporter.export(self._proj_mgr.project, path)
            QMessageBox.information(self, "Export Successful", f"Vector graphic exported to:\n{path}")

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "creation.png", "PNG Images (*.png)")
        if path:
            PNGExporter.export(self._proj_mgr.project, path)
            QMessageBox.information(self, "Export Successful", f"High-resolution image exported to:\n{path}")


_studio_window_instance: Optional[StudioWindow] = None


def get_studio_window() -> StudioWindow:
    global _studio_window_instance
    if _studio_window_instance is None:
        import sys
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)
        _studio_window_instance = StudioWindow()
    return _studio_window_instance
