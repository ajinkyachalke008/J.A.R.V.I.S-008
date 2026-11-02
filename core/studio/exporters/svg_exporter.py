"""
core/studio/exporters/svg_exporter.py — Clean, standards-compliant SVG exporter for Studio projects.
"""
from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import List

from ..models import StudioProject

logger = logging.getLogger("JARVIS.Studio.SVGExporter")


class SVGExporter:
    """Exports StudioProject vector graphics into scalable, standard SVG format."""

    @classmethod
    def export(cls, project: StudioProject, output_path: Path | str) -> str:
        w = max(100.0, project.canvas.width)
        h = max(100.0, project.canvas.height)

        lines: List[str] = [
            f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}{project.canvas.units}" height="{h}{project.canvas.units}">',
            f'  <defs>',
            f'    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
            f'      <path d="M 0 1 L 10 5 L 0 9 z" fill="#00ff88"/>',
            f'    </marker>',
            f'  </defs>',
            f'  <!-- Canvas Background -->',
            f'  <rect width="100%" height="100%" fill="{project.canvas.background_color}"/>',
        ]

        # Group elements by layer
        layer_map = {l.id: l for l in project.layers}
        for l_id, layer in layer_map.items():
            if not layer.visible:
                continue

            lines.append(f'  <g id="layer_{l_id}" data-layer-name="{html.escape(layer.name)}">')
            layer_elements = [el for el in project.elements if el.layer_id == l_id or (l_id == "default" and el.layer_id not in layer_map)]

            for el in layer_elements:
                geo = el.geometry
                st = el.style
                stroke = st.get("stroke", layer.color)
                stroke_w = st.get("stroke_width", 1.5)
                fill = st.get("fill", "none")

                if el.type == "line":
                    x1 = geo.get("x1", 0)
                    y1 = geo.get("y1", 0)
                    x2 = geo.get("x2", 0)
                    y2 = geo.get("y2", 0)
                    arrow_attr = ' marker-end="url(#arrow)"' if geo.get("arrow") else ''
                    lines.append(f'    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{stroke_w}"{arrow_attr}/>')

                elif el.type in ("rect", "component"):
                    rx = geo.get("x", 0)
                    ry = geo.get("y", 0)
                    rw = geo.get("width", 10)
                    rh = geo.get("height", 10)
                    cr = geo.get("corner_radius", 0)
                    cr_attr = f' rx="{cr}" ry="{cr}"' if cr > 0 else ''
                    lines.append(f'    <rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"{cr_attr}/>')

                    # Draw inner label if specified
                    lbl = el.properties.get("label") or el.properties.get("ref")
                    if lbl:
                        cx, cy = rx + rw / 2.0, ry + rh / 2.0 + 4.0
                        lines.append(f'    <text x="{cx}" y="{cy}" font-family="Courier New, monospace" font-size="11" fill="#8ffcff" text-anchor="middle">{html.escape(str(lbl))}</text>')

                elif el.type == "circle":
                    cx = geo.get("cx", 0)
                    cy = geo.get("cy", 0)
                    r = geo.get("r", geo.get("radius", 5))
                    lines.append(f'    <circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_w}"/>')

                elif el.type == "wire":
                    x1 = geo.get("x1", 0)
                    y1 = geo.get("y1", 0)
                    x2 = geo.get("x2", 0)
                    y2 = geo.get("y2", 0)
                    lines.append(f'    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{stroke_w}"/>')

                elif el.type == "dimension":
                    x1 = geo.get("x1", 0)
                    y1 = geo.get("y1", 0)
                    x2 = geo.get("x2", 0)
                    y2 = geo.get("y2", 0)
                    txt = geo.get("text", f"{geo.get('value', 0):.1f}")
                    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    lines.append(f'    <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="1.0" stroke-dasharray="3,3"/>')
                    lines.append(f'    <text x="{mx}" y="{my - 4}" font-family="Courier New, monospace" font-size="10" fill="{stroke}" text-anchor="middle">{html.escape(str(txt))}</text>')

                elif el.type == "text":
                    tx = geo.get("x", 0)
                    ty = geo.get("y", 0)
                    txt = geo.get("text", "")
                    lines.append(f'    <text x="{tx}" y="{ty}" font-family="Courier New, monospace" font-size="12" fill="{stroke}">{html.escape(str(txt))}</text>')

                # Render pins
                for p in el.pins:
                    lines.append(f'    <circle cx="{p.x}" cy="{p.y}" r="3" fill="#ffcc00" stroke="#00060a" stroke-width="1"/>')
                    lines.append(f'    <text x="{p.x + 5}" y="{p.y + 3}" font-family="Courier New, monospace" font-size="9" fill="#ffcc00">{html.escape(p.name)}</text>')

            lines.append('  </g>')

        lines.append('</svg>')
        svg_content = "\n".join(lines) + "\n"

        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(svg_content, encoding="utf-8")
        logger.info("Exported SVG to %s (%d bytes)", out_p, len(svg_content))
        return svg_content

