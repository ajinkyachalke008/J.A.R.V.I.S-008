"""
core/studio/cad_engine.py — 2D Mechanical CAD generation and demonstrator plate.
"""
from __future__ import annotations

import math
from typing import List

from .models import CanvasMetadata, Element, Layer, StudioProject


class CADEngine:
    """Generates 2D mechanical CAD structures with geometric annotations."""

    @staticmethod
    def create_mounting_plate_demonstrator(
        width: float = 120.0,
        height: float = 80.0,
        corner_radius: float = 5.0,
        hole_diameter: float = 4.5,
        hole_offset: float = 8.0,
        center_cutout_w: float = 40.0,
        center_cutout_h: float = 30.0,
    ) -> StudioProject:
        """
        Generates the standard Precision Mechanical Mounting Plate Demonstrator:
        - Outer rectangle: 120mm x 80mm with 5mm corner fillets
        - Four M4 mounting holes: dia 4.5mm at (8mm, 8mm) inset
        - Center rectangular cutout: 40mm x 30mm with 3mm corner fillets
        - Two lateral ventilation/flank holes: dia 10mm
        - Complete horizontal, vertical, and pitch dimension callouts
        """
        proj = StudioProject(
            title="Precision Mounting Plate Demonstrator",
            domain="cad",
            canvas=CanvasMetadata(
                units="mm",
                width=width + 60.0,
                height=height + 60.0,
                grid_spacing=5.0,
                background_color="#010d14",
            ),
            layers=[
                Layer(id="outline", name="Part Outline", color="#00d4ff"),
                Layer(id="holes", name="Cutouts & Holes", color="#00ff88"),
                Layer(id="dimensions", name="Dimensions", color="#ffcc00"),
                Layer(id="centerlines", name="Centerlines", color="#007a99"),
            ],
        )

        origin_x = 30.0
        origin_y = 30.0

        # 1. Outer plate boundary (rounded rectangle)
        proj.elements.append(
            Element(
                id="outer_plate",
                type="rect",
                layer_id="outline",
                geometry={
                    "x": origin_x,
                    "y": origin_y,
                    "width": width,
                    "height": height,
                    "corner_radius": corner_radius,
                },
                style={"stroke": "#00d4ff", "stroke_width": 2.0, "fill": "none"},
                properties={"description": "Main base plate perimeter with fillets"},
            )
        )

        # 2. Four corner mounting holes (dia 4.5mm, M4 clearance)
        hole_r = hole_diameter / 2.0
        corners = [
            ("hole_top_left", origin_x + hole_offset, origin_y + hole_offset),
            ("hole_top_right", origin_x + width - hole_offset, origin_y + hole_offset),
            ("hole_bottom_left", origin_x + hole_offset, origin_y + height - hole_offset),
            ("hole_bottom_right", origin_x + width - hole_offset, origin_y + height - hole_offset),
        ]

        for h_id, hx, hy in corners:
            proj.elements.append(
                Element(
                    id=h_id,
                    type="circle",
                    layer_id="holes",
                    geometry={"cx": hx, "cy": hy, "r": hole_r},
                    style={"stroke": "#00ff88", "stroke_width": 1.5, "fill": "none"},
                    properties={"diameter": hole_diameter, "type": "mounting_hole_M4"},
                )
            )

        # 3. Center rectangular cutout (40mm x 30mm)
        cutout_x = origin_x + (width - center_cutout_w) / 2.0
        cutout_y = origin_y + (height - center_cutout_h) / 2.0
        proj.elements.append(
            Element(
                id="center_cutout",
                type="rect",
                layer_id="holes",
                geometry={
                    "x": cutout_x,
                    "y": cutout_y,
                    "width": center_cutout_w,
                    "height": center_cutout_h,
                    "corner_radius": 3.0,
                },
                style={"stroke": "#00ff88", "stroke_width": 1.5, "fill": "none"},
                properties={"description": "Wiring/clearance center cutout"},
            )
        )

        # 4. Flank ventilation/lightweighting holes (dia 10mm)
        center_y = origin_y + height / 2.0
        left_flank_x = origin_x + (hole_offset + cutout_x) / 2.0
        right_flank_x = origin_x + width - (hole_offset + cutout_x) / 2.0

        for f_id, fx in [("flank_hole_left", left_flank_x), ("flank_hole_right", right_flank_x)]:
            proj.elements.append(
                Element(
                    id=f_id,
                    type="circle",
                    layer_id="holes",
                    geometry={"cx": fx, "cy": center_y, "r": 5.0},
                    style={"stroke": "#00ff88", "stroke_width": 1.5, "fill": "none"},
                    properties={"diameter": 10.0, "type": "ventilation_hole"},
                )
            )

        # 5. Dimensions callouts
        # Width overall
        proj.elements.append(
            Element(
                id="dim_overall_width",
                type="dimension",
                layer_id="dimensions",
                geometry={
                    "x1": origin_x,
                    "y1": origin_y - 12.0,
                    "x2": origin_x + width,
                    "y2": origin_y - 12.0,
                    "value": width,
                    "text": f"{width:.1f} mm",
                    "orientation": "horizontal",
                },
                style={"stroke": "#ffcc00", "stroke_width": 1.0, "fill": "#ffcc00"},
            )
        )

        # Height overall
        proj.elements.append(
            Element(
                id="dim_overall_height",
                type="dimension",
                layer_id="dimensions",
                geometry={
                    "x1": origin_x - 12.0,
                    "y1": origin_y,
                    "x2": origin_x - 12.0,
                    "y2": origin_y + height,
                    "value": height,
                    "text": f"{height:.1f} mm",
                    "orientation": "vertical",
                },
                style={"stroke": "#ffcc00", "stroke_width": 1.0, "fill": "#ffcc00"},
            )
        )

        # Pitch X
        pitch_x = width - (2 * hole_offset)
        proj.elements.append(
            Element(
                id="dim_pitch_x",
                type="dimension",
                layer_id="dimensions",
                geometry={
                    "x1": origin_x + hole_offset,
                    "y1": origin_y + height + 12.0,
                    "x2": origin_x + width - hole_offset,
                    "y2": origin_y + height + 12.0,
                    "value": pitch_x,
                    "text": f"PITCH {pitch_x:.1f} mm",
                    "orientation": "horizontal",
                },
                style={"stroke": "#ffcc00", "stroke_width": 1.0, "fill": "#ffcc00"},
            )
        )

        # Pitch Y
        pitch_y = height - (2 * hole_offset)
        proj.elements.append(
            Element(
                id="dim_pitch_y",
                type="dimension",
                layer_id="dimensions",
                geometry={
                    "x1": origin_x + width + 12.0,
                    "y1": origin_y + hole_offset,
                    "x2": origin_x + width + 12.0,
                    "y2": origin_y + height - hole_offset,
                    "value": pitch_y,
                    "text": f"PITCH {pitch_y:.1f} mm",
                    "orientation": "vertical",
                },
                style={"stroke": "#ffcc00", "stroke_width": 1.0, "fill": "#ffcc00"},
            )
        )

        return proj
