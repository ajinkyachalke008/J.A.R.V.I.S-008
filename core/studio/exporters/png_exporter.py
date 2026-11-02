"""
core/studio/exporters/png_exporter.py — High-resolution anti-aliased raster renderer.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen

from ..models import StudioProject

logger = logging.getLogger("JARVIS.Studio.PNGExporter")


class PNGExporter:
    """Renders StudioProject models into crisp raster PNG images via QPainter."""

    @classmethod
    def export(cls, project: StudioProject, output_path: Path | str, scale: float = 2.0) -> bool:
        w = int(max(100.0, project.canvas.width) * scale)
        h = int(max(100.0, project.canvas.height) * scale)

        image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        # Background
        bg_color = QColor(project.canvas.background_color)
        image.fill(bg_color)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)

        layer_map = {l.id: l for l in project.layers}

        for l_id, layer in layer_map.items():
            if not layer.visible:
                continue

            for el in project.elements:
                if el.layer_id != l_id and not (l_id == "default" and el.layer_id not in layer_map):
                    continue

                geo = el.geometry
                st = el.style
                stroke_color = QColor(st.get("stroke", layer.color))
                stroke_w = float(st.get("stroke_width", 1.5))
                pen = QPen(stroke_color, stroke_w)

                if st.get("stroke_style") == "dashed":
                    pen.setStyle(Qt.PenStyle.DashLine)

                painter.setPen(pen)

                fill_str = st.get("fill", "none")
                if fill_str and fill_str != "none":
                    painter.setBrush(QBrush(QColor(fill_str)))
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)

                if el.type == "line":
                    painter.drawLine(
                        QPointF(geo.get("x1", 0), geo.get("y1", 0)),
                        QPointF(geo.get("x2", 0), geo.get("y2", 0)),
                    )

                elif el.type in ("rect", "component"):
                    rx = float(geo.get("x", 0))
                    ry = float(geo.get("y", 0))
                    rw = float(geo.get("width", 10))
                    rh = float(geo.get("height", 10))
                    cr = float(geo.get("corner_radius", 0))
                    if cr > 0:
                        painter.drawRoundedRect(QRectF(rx, ry, rw, rh), cr, cr)
                    else:
                        painter.drawRect(QRectF(rx, ry, rw, rh))

                    lbl = el.properties.get("label") or el.properties.get("ref")
                    if lbl:
                        painter.setFont(QFont("Courier New", 9))
                        painter.setPen(QPen(QColor("#8ffcff")))
                        painter.drawText(QRectF(rx, ry, rw, rh), Qt.AlignmentFlag.AlignCenter, str(lbl))

                elif el.type == "circle":
                    cx = float(geo.get("cx", 0))
                    cy = float(geo.get("cy", 0))
                    r = float(geo.get("r", geo.get("radius", 5)))
                    painter.drawEllipse(QPointF(cx, cy), r, r)

                elif el.type == "wire":
                    painter.drawLine(
                        QPointF(geo.get("x1", 0), geo.get("y1", 0)),
                        QPointF(geo.get("x2", 0), geo.get("y2", 0)),
                    )

                elif el.type == "dimension":
                    x1 = float(geo.get("x1", 0))
                    y1 = float(geo.get("y1", 0))
                    x2 = float(geo.get("x2", 0))
                    y2 = float(geo.get("y2", 0))
                    txt = geo.get("text", f"{geo.get('value', 0):.1f}")
                    pen.setStyle(Qt.PenStyle.DashLine)
                    painter.setPen(pen)
                    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
                    painter.setFont(QFont("Courier New", 8))
                    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    painter.drawText(QPointF(mx - 15, my - 4), str(txt))

        painter.end()

        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        ok = image.save(str(out_p), "PNG")
        logger.info("Exported PNG to %s (success=%s)", out_p, ok)
        return ok

