"""
core/studio/workflow_engine.py — Flowcharts, state machines, and system architecture diagrams.
"""
from __future__ import annotations

from .models import CanvasMetadata, Element, Layer, StudioProject


class WorkflowEngine:
    """Generates process flows, decision trees, and architecture diagrams."""

    @staticmethod
    def create_agent_loop_demonstrator() -> StudioProject:
        """
        Creates an Autonomous Agent Loop flowchart:
        User Intent -> Observation -> Task Planning -> Permission Gate -> Action -> Verification -> Done
        """
        proj = StudioProject(
            title="JARVIS Autonomous Agent Workflow",
            domain="workflow",
            canvas=CanvasMetadata(units="px", width=900, height=600, grid_spacing=20, background_color="#010d14"),
            layers=[
                Layer(id="nodes", name="Process Nodes", color="#00d4ff"),
                Layer(id="connectors", name="Connectors", color="#00ff88"),
                Layer(id="labels", name="Labels", color="#ffffff"),
            ],
        )

        nodes = [
            ("n_start", "rect", 80, 250, 120, 50, "User Voice Intent", "#00d4ff"),
            ("n_observe", "rect", 240, 250, 130, 50, "Visual Observation\n(MSS + UIA)", "#00d4ff"),
            ("n_plan", "rect", 410, 250, 130, 50, "Task Decomposition\n(Planning Loop)", "#00d4ff"),
            ("n_gate", "rect", 580, 240, 120, 70, "Permission Gate\n(Desktop Access)", "#ffcc00"),
            ("n_exec", "rect", 740, 250, 120, 50, "Bézier Action\n(PyAutoGUI)", "#00ff88"),
            ("n_verify", "rect", 580, 400, 120, 50, "Pre/Post Diff\nVerification", "#00d4ff"),
        ]

        for n_id, n_type, x, y, w, h, label, color in nodes:
            proj.elements.append(
                Element(
                    id=n_id,
                    type=n_type,
                    layer_id="nodes",
                    geometry={"x": x, "y": y, "width": w, "height": h, "corner_radius": 6},
                    style={"stroke": color, "stroke_width": 2.0, "fill": "#011520"},
                    properties={"label": label},
                )
            )

        connectors = [
            ("c1", 200, 275, 240, 275),
            ("c2", 370, 275, 410, 275),
            ("c3", 540, 275, 580, 275),
            ("c4", 700, 275, 740, 275),
            ("c5", 800, 300, 640, 400),
            ("c6", 580, 425, 305, 300),
        ]

        for c_id, x1, y1, x2, y2 in connectors:
            proj.elements.append(
                Element(
                    id=c_id,
                    type="line",
                    layer_id="connectors",
                    geometry={"x1": x1, "y1": y1, "x2": x2, "y2": y2, "arrow": True},
                    style={"stroke": "#00ff88", "stroke_width": 1.5, "fill": "none"},
                )
            )

        return proj
