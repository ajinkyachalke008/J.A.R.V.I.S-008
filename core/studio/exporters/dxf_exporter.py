"""
core/studio/exporters/dxf_exporter.py — Standard ASCII DXF exporter for 2D CAD models.

Produces AutoCAD R12/2000 compliant DXF files importable directly into
AutoCAD, FreeCAD, LibreCAD, SolidWorks, CNC cam software, and laser cutters.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from ..models import StudioProject

logger = logging.getLogger("JARVIS.Studio.DXFExporter")


class DXFExporter:
    """Exports StudioProject CAD geometry into standard ASCII DXF format."""

    @classmethod
    def export(cls, project: StudioProject, output_path: Path | str) -> str:
        """Export project to a DXF file. Returns the DXF string."""
        lines: List[str] = []

        def _code(code: int, value: str | int | float):
            lines.append(f"{code:3d}")
            lines.append(str(value))

        # 1. HEADER SECTION
        _code(0, "SECTION")
        _code(2, "HEADER")
        _code(9, "$ACADVER")
        _code(1, "AC1009")  # AutoCAD R12 format (most universal compatibility)
        _code(9, "$INSUNITS")
        # 1 = inches, 4 = millimeters
        _code(70, 4 if project.canvas.units == "mm" else 1)
        _code(0, "ENDSEC")

        # 2. TABLES SECTION (Layers)
        _code(0, "SECTION")
        _code(2, "TABLES")
        _code(0, "TABLE")
        _code(2, "LAYER")
        _code(70, len(project.layers))

        for l in project.layers:
            _code(0, "LAYER")
            _code(2, l.name.upper().replace(" ", "_"))
            _code(70, 0)
            _code(62, 7)  # Standard color white/black
            _code(6, "CONTINUOUS")

        _code(0, "ENDTAB")
        _code(0, "ENDSEC")

        # 3. ENTITIES SECTION (Geometric shapes)
        _code(0, "SECTION")
        _code(2, "ENTITIES")

        for el in project.elements:
            geo = el.geometry
            layer = el.layer_id.upper().replace(" ", "_")

            if el.type == "line":
                x1 = geo.get("x1", 0.0)
                y1 = geo.get("y1", 0.0)
                x2 = geo.get("x2", 0.0)
                y2 = geo.get("y2", 0.0)
                _code(0, "LINE")
                _code(8, layer)
                _code(10, f"{x1:.4f}")
                _code(20, f"{y1:.4f}")
                _code(30, "0.0")
                _code(11, f"{x2:.4f}")
                _code(21, f"{y2:.4f}")
                _code(31, "0.0")

            elif el.type == "rect":
                rx = geo.get("x", 0.0)
                ry = geo.get("y", 0.0)
                rw = geo.get("width", 0.0)
                rh = geo.get("height", 0.0)
                cr = geo.get("corner_radius", 0.0)

                if cr > 0:
                    # Draw rectangle with rounded corners (4 lines + 4 arcs)
                    # Lines
                    # Bottom line
                    cls._write_line(_code, layer, rx + cr, ry, rx + rw - cr, ry)
                    # Right line
                    cls._write_line(_code, layer, rx + rw, ry + cr, rx + rw, ry + rh - cr)
                    # Top line
                    cls._write_line(_code, layer, rx + rw - cr, ry + rh, rx + cr, ry + rh)
                    # Left line
                    cls._write_line(_code, layer, rx, ry + rh - cr, rx, ry + cr)

                    # 4 corner arcs
                    cls._write_arc(_code, layer, rx + rw - cr, ry + cr, cr, 270, 360)
                    cls._write_arc(_code, layer, rx + rw - cr, ry + rh - cr, cr, 0, 90)
                    cls._write_arc(_code, layer, rx + cr, ry + rh - cr, cr, 90, 180)
                    cls._write_arc(_code, layer, rx + cr, ry + cr, cr, 180, 270)
                else:
                    # 4 straight boundary lines
                    cls._write_line(_code, layer, rx, ry, rx + rw, ry)
                    cls._write_line(_code, layer, rx + rw, ry, rx + rw, ry + rh)
                    cls._write_line(_code, layer, rx + rw, ry + rh, rx, ry + rh)
                    cls._write_line(_code, layer, rx, ry + rh, rx, ry)

            elif el.type == "circle":
                cx = geo.get("cx", 0.0)
                cy = geo.get("cy", 0.0)
                r = geo.get("r", geo.get("radius", 0.0))
                _code(0, "CIRCLE")
                _code(8, layer)
                _code(10, f"{cx:.4f}")
                _code(20, f"{cy:.4f}")
                _code(30, "0.0")
                _code(40, f"{r:.4f}")

            elif el.type == "arc":
                cx = geo.get("cx", 0.0)
                cy = geo.get("cy", 0.0)
                r = geo.get("r", 0.0)
                a1 = geo.get("start_angle", 0.0)
                a2 = geo.get("end_angle", 360.0)
                cls._write_arc(_code, layer, cx, cy, r, a1, a2)

            elif el.type == "dimension":
                x1 = geo.get("x1", 0.0)
                y1 = geo.get("y1", 0.0)
                x2 = geo.get("x2", 0.0)
                y2 = geo.get("y2", 0.0)
                text = geo.get("text", f"{geo.get('value', 0):.1f}")
                # Dimension line
                cls._write_line(_code, "DIMENSIONS", x1, y1, x2, y2)
                # Dimension text in the center
                mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                _code(0, "TEXT")
                _code(8, "DIMENSIONS")
                _code(10, f"{mx:.4f}")
                _code(20, f"{my + 2.0:.4f}")
                _code(30, "0.0")
                _code(40, "3.5")  # text height
                _code(1, text)

        _code(0, "ENDSEC")

        # 4. END OF FILE
        _code(0, "EOF")

        dxf_content = "\n".join(lines) + "\n"
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(dxf_content, encoding="ascii")
        logger.info("Exported DXF to %s (%d bytes)", out_p, len(dxf_content))
        return dxf_content

    @staticmethod
    def _write_line(_code, layer: str, x1: float, y1: float, x2: float, y2: float):
        _code(0, "LINE")
        _code(8, layer)
        _code(10, f"{x1:.4f}")
        _code(20, f"{y1:.4f}")
        _code(30, "0.0")
        _code(11, f"{x2:.4f}")
        _code(21, f"{y2:.4f}")
        _code(31, "0.0")

    @staticmethod
    def _write_arc(_code, layer: str, cx: float, cy: float, r: float, a1: float, a2: float):
        _code(0, "ARC")
        _code(8, layer)
        _code(10, f"{cx:.4f}")
        _code(20, f"{cy:.4f}")
        _code(30, "0.0")
        _code(40, f"{r:.4f}")
        _code(50, f"{a1:.2f}")
        _code(51, f"{a2:.2f}")

