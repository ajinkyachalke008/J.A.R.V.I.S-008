"""
actions/creation_studio.py — Universal Creation Studio action for J.A.R.V.I.S. — 008.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from core import outcome
from core.studio.cad_engine import CADEngine
from core.studio.circuit_engine import CircuitEngine
from core.studio.exporters import DXFExporter, JSONExporter, PNGExporter, SVGExporter
from core.studio.models import StudioProject
from core.studio.project_manager import get_project_manager
from core.studio.studio_window import get_studio_window
from core.studio.workflow_engine import WorkflowEngine

logger = logging.getLogger("JARVIS.Action.CreationStudio")


def creation_studio(
    parameters: dict[str, Any],
    player: Optional[Any] = None,
    speak: Optional[Any] = None,
    session_memory: Optional[Any] = None,
) -> str:
    """Creates, renders, and exports 2D CAD models, circuit schematics, and diagrams."""
    action = str(parameters.get("action", "open")).strip().lower()
    domain = str(parameters.get("domain", "cad")).strip().lower()
    title = str(parameters.get("title", "")).strip()

    proj_mgr = get_project_manager()

    if action in ("open", "open_studio", "show"):
        try:
            win = get_studio_window()
            win.show()
            win.raise_()
            win.activateWindow()
            return outcome.done("creation_studio", status="opened", active_project=proj_mgr.project.title)
        except Exception as e:
            return outcome.failed("creation_studio", str(e))

    elif action in ("create", "create_demonstrator", "demo"):
        if domain in ("cad", "mounting_plate", "mechanical"):
            w = float(parameters.get("width", 120.0))
            h = float(parameters.get("height", 80.0))
            proj = CADEngine.create_mounting_plate_demonstrator(width=w, height=h)
        elif domain in ("circuit", "schematic", "regulator", "electronics"):
            proj = CircuitEngine.create_regulator_demonstrator()
        elif domain in ("workflow", "flowchart", "diagram", "agent"):
            proj = WorkflowEngine.create_agent_loop_demonstrator()
        else:
            proj = CADEngine.create_mounting_plate_demonstrator()

        if title:
            proj.title = title

        proj_mgr.set_project(proj)

        # Show window
        try:
            win = get_studio_window()
            win.show()
            win.raise_()
        except Exception:
            pass

        return outcome.done(
            "create_demonstrator",
            domain=proj.domain,
            title=proj.title,
            elements_count=len(proj.elements),
        )

    elif action.startswith("export"):
        import sys
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)
        export_format = str(parameters.get("format", "dxf" if domain == "cad" else "svg")).strip().lower()
        export_dir = Path.home() / "Desktop" / "JarvisCreations"
        export_dir.mkdir(parents=True, exist_ok=True)

        base_name = proj_mgr.project.title.lower().replace(" ", "_")
        proj = proj_mgr.project

        if "dxf" in export_format:
            out_file = export_dir / f"{base_name}.dxf"
            DXFExporter.export(proj, out_file)
        elif "svg" in export_format:
            out_file = export_dir / f"{base_name}.svg"
            SVGExporter.export(proj, out_file)
        elif "png" in export_format:
            out_file = export_dir / f"{base_name}.png"
            PNGExporter.export(proj, out_file)
        elif "json" in export_format:
            out_file = export_dir / f"{base_name}.json"
            JSONExporter.export(proj, out_file)
        else:
            out_file = export_dir / f"{base_name}.dxf"
            DXFExporter.export(proj, out_file)

        return outcome.done(
            "export_project",
            format=export_format,
            path=str(out_file),
            elements=len(proj.elements),
        )

    return outcome.failed("creation_studio", f"Unknown creation action: {action}")


TOOL = {
    "name": "creation_studio",
    "description": (
        "Universal Creation Studio for designing 2D mechanical CAD models, "
        "electrical circuit schematics, and workflow architecture diagrams, with multi-format export to DXF, SVG, PNG, and JSON."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "open | create_demonstrator | export",
            },
            "domain": {
                "type": "STRING",
                "description": "cad | circuit | workflow",
            },
            "title": {
                "type": "STRING",
                "description": "Project title.",
            },
            "width": {
                "type": "NUMBER",
                "description": "Width in mm for CAD parts.",
            },
            "height": {
                "type": "NUMBER",
                "description": "Height in mm for CAD parts.",
            },
            "format": {
                "type": "STRING",
                "description": "dxf | svg | png | json",
            },
        },
        "required": ["action"],
    },
    "handler": creation_studio,
    "tier": "core",
}
