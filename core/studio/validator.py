"""
core/studio/validator.py — Geometric and semantic validation for Creation Studio projects.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from .models import StudioProject


class ProjectValidator:
    """Validates structural, geometric, and domain-specific integrity of studio projects."""

    @staticmethod
    def validate(project: StudioProject) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. Canvas checks
        if project.canvas.width <= 0 or project.canvas.height <= 0:
            errors.append(f"Invalid canvas dimensions: {project.canvas.width}x{project.canvas.height}")

        # 2. Layer checks
        layer_ids = {l.id for l in project.layers}
        if not layer_ids:
            errors.append("Project contains no layers.")

        # 3. Element checks
        for idx, el in enumerate(project.elements):
            e_prefix = f"Element #{idx} ('{el.id}', type='{el.type}')"

            if el.layer_id not in layer_ids and el.layer_id != "default":
                errors.append(f"{e_prefix}: References unknown layer_id '{el.layer_id}'")

            geo = el.geometry
            if el.type == "line":
                for k in ("x1", "y1", "x2", "y2"):
                    if k not in geo or not isinstance(geo[k], (int, float)):
                        errors.append(f"{e_prefix}: Missing or invalid coordinate '{k}'")

            elif el.type == "rect":
                w = geo.get("width", 0)
                h = geo.get("height", 0)
                if w <= 0 or h <= 0:
                    errors.append(f"{e_prefix}: Width and height must be positive, got {w}x{h}")

            elif el.type in ("circle", "fillet"):
                r = geo.get("r", geo.get("radius", 0))
                if r <= 0:
                    errors.append(f"{e_prefix}: Radius must be positive, got {r}")

            elif el.type == "dimension":
                val = geo.get("value", 0)
                if val <= 0:
                    errors.append(f"{e_prefix}: Dimension measurement must be positive")

            elif el.type == "component":
                # Check circuit component pins
                if not el.pins and project.domain == "circuit":
                    errors.append(f"{e_prefix}: Circuit component has no pins defined")

        return (len(errors) == 0, errors)
