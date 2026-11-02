"""
core/studio/circuit_engine.py — Electrical schematic generation and circuit primitives.
"""
from __future__ import annotations

from .models import CanvasMetadata, Element, Layer, Pin, StudioProject


class CircuitEngine:
    """Generates electrical circuit schematics, pins, and netlists."""

    @staticmethod
    def create_regulator_demonstrator() -> StudioProject:
        """
        Creates a 5V buck power regulation schematic:
        VIN (+12V) -> Buck Regulator IC (LM2596) -> Inductor (33uH) -> Filter Cap (220uF) -> VOUT (+5V)
        """
        proj = StudioProject(
            title="5V Buck Regulator Circuit",
            domain="circuit",
            canvas=CanvasMetadata(units="px", width=800, height=500, grid_spacing=20, background_color="#010d14"),
            layers=[
                Layer(id="components", name="Components", color="#00d4ff"),
                Layer(id="wires", name="Netlist Wires", color="#00ff88"),
                Layer(id="labels", name="Text & Values", color="#ffffff"),
            ],
        )

        # 1. Input connector
        proj.elements.append(
            Element(
                id="j_in",
                type="component",
                layer_id="components",
                geometry={"x": 60, "y": 180, "width": 40, "height": 60},
                style={"stroke": "#00d4ff", "stroke_width": 2.0, "fill": "#011520"},
                properties={"ref": "J1", "value": "VIN_12V"},
                pins=[Pin(id="p_vin", name="VIN", x=100, y=190, net="VIN"), Pin(id="p_gnd_in", name="GND", x=100, y=230, net="GND")],
            )
        )

        # 2. Input Capacitor (100uF)
        proj.elements.append(
            Element(
                id="c_in",
                type="component",
                layer_id="components",
                geometry={"x": 150, "y": 180, "width": 30, "height": 50},
                style={"stroke": "#00d4ff", "stroke_width": 2.0, "fill": "none"},
                properties={"ref": "C1", "value": "100uF / 50V"},
                pins=[Pin(id="p_cin_pos", name="+", x=165, y=180, net="VIN"), Pin(id="p_cin_neg", name="-", x=165, y=230, net="GND")],
            )
        )

        # 3. LM2596 Regulator IC
        proj.elements.append(
            Element(
                id="u_reg",
                type="component",
                layer_id="components",
                geometry={"x": 260, "y": 150, "width": 120, "height": 100},
                style={"stroke": "#00d4ff", "stroke_width": 2.0, "fill": "#011a29"},
                properties={"ref": "U1", "value": "LM2596-5.0"},
                pins=[
                    Pin(id="p_u_in", name="IN", x=260, y=180, net="VIN"),
                    Pin(id="p_u_out", name="SW", x=380, y=180, net="SW_NODE"),
                    Pin(id="p_u_fb", name="FB", x=380, y=220, net="VOUT"),
                    Pin(id="p_u_gnd", name="GND", x=320, y=250, net="GND"),
                    Pin(id="p_u_onoff", name="ON/OFF", x=260, y=220, net="GND"),
                ],
            )
        )

        # 4. Schottky Catch Diode (1N5822)
        proj.elements.append(
            Element(
                id="d_catch",
                type="component",
                layer_id="components",
                geometry={"x": 420, "y": 200, "width": 30, "height": 40},
                style={"stroke": "#ff6b00", "stroke_width": 2.0, "fill": "none"},
                properties={"ref": "D1", "value": "1N5822 Schottky"},
                pins=[Pin(id="p_d_k", name="K", x=435, y=180, net="SW_NODE"), Pin(id="p_d_a", name="A", x=435, y=240, net="GND")],
            )
        )

        # 5. Inductor (33uH)
        proj.elements.append(
            Element(
                id="l_buck",
                type="component",
                layer_id="components",
                geometry={"x": 480, "y": 165, "width": 60, "height": 30},
                style={"stroke": "#00d4ff", "stroke_width": 2.0, "fill": "none"},
                properties={"ref": "L1", "value": "33uH / 3A"},
                pins=[Pin(id="p_l_1", name="1", x=480, y=180, net="SW_NODE"), Pin(id="p_l_2", name="2", x=540, y=180, net="VOUT")],
            )
        )

        # 6. Output Capacitor (220uF)
        proj.elements.append(
            Element(
                id="c_out",
                type="component",
                layer_id="components",
                geometry={"x": 580, "y": 180, "width": 30, "height": 50},
                style={"stroke": "#00d4ff", "stroke_width": 2.0, "fill": "none"},
                properties={"ref": "C2", "value": "220uF / 16V"},
                pins=[Pin(id="p_cout_pos", name="+", x=595, y=180, net="VOUT"), Pin(id="p_cout_neg", name="-", x=595, y=230, net="GND")],
            )
        )

        # 7. Output Terminal (+5V)
        proj.elements.append(
            Element(
                id="j_out",
                type="component",
                layer_id="components",
                geometry={"x": 670, "y": 180, "width": 40, "height": 60},
                style={"stroke": "#00ff88", "stroke_width": 2.0, "fill": "#011520"},
                properties={"ref": "J2", "value": "VOUT_5V"},
                pins=[Pin(id="p_vout", name="+5V", x=670, y=190, net="VOUT"), Pin(id="p_gnd_out", name="GND", x=670, y=230, net="GND")],
            )
        )

        # 8. Netlist Connecting Wires
        wires = [
            ("wire_vin", 100, 190, 260, 180, "VIN"),
            ("wire_sw", 380, 180, 480, 180, "SW_NODE"),
            ("wire_vout", 540, 180, 670, 190, "VOUT"),
            ("wire_gnd", 100, 230, 670, 230, "GND"),
        ]

        for w_id, x1, y1, x2, y2, net in wires:
            proj.elements.append(
                Element(
                    id=w_id,
                    type="wire",
                    layer_id="wires",
                    geometry={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    style={"stroke": "#00ff88", "stroke_width": 1.5, "fill": "none"},
                    properties={"net": net},
                )
            )

        return proj
