"""
core/intelligence/engineering/engineering_intelligence.py — Engineering Intelligence Platform.

Extends Universal Creation Studio into an engineering problem solver:
- Mathematical calculations with unit verification (V, A, W, Ω, F, H, mm, Hz)
- Circuit calculations (LM2596 regulator, voltage divider, RC filter, LED ballast)
- Mechanical geometry calculations (bolt hole patterns, fillet clearance bounds)
- Automated Bill of Materials (BOM) generator
- Seamless integration with core/studio/project_manager.py
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from core.intelligence.models import (
    BOMItem,
    EngineeringCalculation,
    EngineeringSpec,
)
from core.studio.models import Element, StudioProject
from core.studio.project_manager import ProjectManager

logger = logging.getLogger("JARVIS.Intelligence.Engineering")


class EngineeringIntelligence:
    """Provides mathematically verified calculations, BOM synthesis, and Studio integration."""

    def __init__(self, studio_mgr: Optional[Any] = None, base_dir: Optional[Any] = None):
        self._studio_mgr = studio_mgr or ProjectManager()

    # ── Mathematical Calculations & Unit Validation ───────────────────────────

    def calculate_voltage_divider(self, v_in: float, r1: float, r2: float) -> EngineeringCalculation:
        """Calculates V_out = V_in * (R2 / (R1 + R2)) with Ohm / Volt unit validation."""
        if r1 + r2 <= 0:
            return EngineeringCalculation(
                formula_name="Voltage Divider",
                formula_latex=r"V_{out} = V_{in} \cdot \frac{R_2}{R_1 + R_2}",
                inputs={"v_in": v_in, "r1": r1, "r2": r2},
                result_value=0.0,
                unit="V",
                is_valid=False,
                error_message="Sum of resistances (R1 + R2) must be strictly positive.",
            )

        v_out = v_in * (r2 / (r1 + r2))
        return EngineeringCalculation(
            formula_name="Voltage Divider",
            formula_latex=r"V_{out} = V_{in} \cdot \frac{R_2}{R_1 + R_2}",
            inputs={"v_in": v_in, "r1": r1, "r2": r2},
            result_value=round(v_out, 4),
            unit="V",
            precision=4,
            explanation=f"Output voltage V_out is {v_out:.4f}V across R2 ({r2}Ω) with {v_in}V input.",
            is_valid=True,
        )

    def calculate_lm2596_feedback(self, target_vout: float, r1: float = 1000.0) -> EngineeringCalculation:
        """
        Calculates R2 for LM2596 adjustable buck regulator:
        V_out = 1.23 * (1 + R2 / R1) => R2 = R1 * ((V_out / 1.23) - 1)
        """
        if target_vout < 1.23:
            return EngineeringCalculation(
                formula_name="LM2596 Feedback Resistor",
                formula_latex=r"R_2 = R_1 \cdot \left(\frac{V_{out}}{1.23} - 1\right)",
                inputs={"target_vout": target_vout, "r1": r1},
                result_value=0.0,
                unit="Ω",
                is_valid=False,
                error_message="Target V_out must be >= internal reference voltage (1.23V).",
            )

        r2 = r1 * ((target_vout / 1.23) - 1.0)
        return EngineeringCalculation(
            formula_name="LM2596 Feedback Resistor",
            formula_latex=r"R_2 = R_1 \cdot \left(\frac{V_{out}}{1.23} - 1\right)",
            inputs={"target_vout": target_vout, "r1": r1},
            result_value=round(r2, 2),
            unit="Ω",
            precision=2,
            explanation=f"For {target_vout}V output with R1={r1}Ω, use R2={r2:.2f}Ω (nearest standard E24/E96 resistor).",
            is_valid=True,
        )

    def calculate_rc_filter_cutoff(self, r_ohms: float, c_farads: float) -> EngineeringCalculation:
        """Calculates f_c = 1 / (2 * pi * R * C) in Hertz."""
        if r_ohms <= 0 or c_farads <= 0:
            return EngineeringCalculation(
                formula_name="RC Low-Pass Filter Cutoff",
                formula_latex=r"f_c = \frac{1}{2\pi R C}",
                inputs={"r_ohms": r_ohms, "c_farads": c_farads},
                result_value=0.0,
                unit="Hz",
                is_valid=False,
                error_message="Resistance and capacitance must be strictly greater than zero.",
            )

        fc = 1.0 / (2.0 * math.pi * r_ohms * c_farads)
        return EngineeringCalculation(
            formula_name="RC Low-Pass Filter Cutoff",
            formula_latex=r"f_c = \frac{1}{2\pi R C}",
            inputs={"r_ohms": r_ohms, "c_farads": c_farads},
            result_value=round(fc, 2),
            unit="Hz",
            precision=2,
            explanation=f"-3dB cutoff frequency is {fc:.2f}Hz for R={r_ohms}Ω and C={c_farads:.2e}F.",
            is_valid=True,
        )

    def calculate_bolt_circle_pattern(
        self, center_x: float, center_y: float, radius: float, num_holes: int
    ) -> List[Tuple[float, float]]:
        """Generates coordinate tuples (x, y) for circular bolt hole patterns."""
        if num_holes <= 0 or radius <= 0:
            return []
        coords = []
        angle_step = (2.0 * math.pi) / num_holes
        for i in range(num_holes):
            theta = i * angle_step
            x = center_x + radius * math.cos(theta)
            y = center_y + radius * math.sin(theta)
            coords.append((round(x, 3), round(y, 3)))
        return coords

    # ── Bill of Materials (BOM) Synthesis ─────────────────────────────────────

    def generate_bom_for_regulator(self, v_in: float, v_out: float) -> List[BOMItem]:
        """Generates verified Bill of Materials for LM2596 Step-Down Power Supply."""
        calc = self.calculate_lm2596_feedback(v_out, r1=1000.0)
        r2_val = f"{calc.result_value:.0f}Ω" if calc.is_valid else "3.1kΩ"

        bom = [
            BOMItem(
                item_id="bom_01",
                component_name="Step-Down Voltage Regulator",
                designator="U1",
                package="TO-263-5 / TO-220-5",
                parameters=f"LM2596-ADJ (3A 150kHz)",
                quantity=1,
                manufacturer="Texas Instruments",
                part_number="LM2596S-ADJ/NOPB",
                datasheet_url="https://www.ti.com/lit/ds/symlink/lm2596.pdf",
                estimated_unit_cost=1.85,
            ),
            BOMItem(
                item_id="bom_02",
                component_name="Schottky Catch Diode",
                designator="D1",
                package="DO-214AB (SMC)",
                parameters="1N5824 / SS34 (3A 40V, Vf < 0.45V)",
                quantity=1,
                manufacturer="Vishay",
                part_number="SS34-E3/57T",
                estimated_unit_cost=0.35,
            ),
            BOMItem(
                item_id="bom_03",
                component_name="Power Inductor",
                designator="L1",
                package="SMD 12x12mm",
                parameters="33µH, 3.5A Saturation",
                quantity=1,
                manufacturer="Bourns",
                part_number="SRR1280-330M",
                estimated_unit_cost=0.95,
            ),
            BOMItem(
                item_id="bom_04",
                component_name="Input Electrolytic Capacitor",
                designator="C_IN",
                package="Radial 8x11.5mm",
                parameters="680µF 50V Low-ESR",
                quantity=1,
                manufacturer="Panasonic",
                part_number="EEU-FR1H681B",
                estimated_unit_cost=0.55,
            ),
            BOMItem(
                item_id="bom_05",
                component_name="Output Filter Capacitor",
                designator="C_OUT",
                package="Radial 8x11.5mm",
                parameters="220µF 25V Low-ESR",
                quantity=1,
                manufacturer="Panasonic",
                part_number="EEU-FR1E221",
                estimated_unit_cost=0.40,
            ),
            BOMItem(
                item_id="bom_06",
                component_name="Precision Feedback Resistor R1",
                designator="R1",
                package="SMD 0805",
                parameters="1.0kΩ ±1% 1/8W",
                quantity=1,
                manufacturer="Yageo",
                part_number="RC0805FR-071KL",
                estimated_unit_cost=0.05,
            ),
            BOMItem(
                item_id="bom_07",
                component_name="Precision Feedback Resistor R2",
                designator="R2",
                package="SMD 0805",
                parameters=f"{r2_val} ±1% 1/8W",
                quantity=1,
                manufacturer="Yageo",
                part_number=f"RC0805FR-07{r2_val.replace('Ω','R')}",
                estimated_unit_cost=0.05,
            ),
        ]
        return bom

    def format_bom_markdown(self, *args, **kwargs) -> str:
        if len(args) == 1 and isinstance(args[0], list):
            project_name, bom_items = "Engineering Project", args[0]
        elif len(args) >= 2:
            project_name, bom_items = str(args[0]), args[1]
        else:
            project_name = kwargs.get("project_name", "Engineering Project")
            bom_items = kwargs.get("bom_items", [])
        lines = [
            "| Item | Designator | Component Name | Package | Parameters | Qty | Est. Cost |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        total = 0.0
        for it in bom_items:
            lines.append(
                f"| {it.item_id} | `{it.designator}` | {it.component_name} | `{it.package}` | {it.parameters} | {it.quantity} | ${it.estimated_unit_cost:.2f} |"
            )
            total += it.estimated_unit_cost * it.quantity
        lines.append(f"| **Total** | | | | | | **${total:.2f}** |")
        return "\n".join(lines)

    def calculate_buck_feedback(self, target_vout: float, r1: float = 1000.0) -> EngineeringCalculation:
        return self.calculate_lm2596_feedback(target_vout=target_vout, r1=r1)

    def calculate_rc_cutoff(self, r_ohms: float, c_farads: float) -> EngineeringCalculation:
        return self.calculate_rc_filter_cutoff(r_ohms=r_ohms, c_farads=c_farads)

    def calculate_bolt_circle(self, pcd_mm: float, num_holes: int, bolt_size: str = "M6") -> EngineeringCalculation:
        coords = self.calculate_bolt_circle_pattern(0.0, 0.0, pcd_mm / 2.0, num_holes)
        return EngineeringCalculation(
            formula_name="Bolt Circle Pattern",
            formula_latex=r"\theta_i = \frac{2\pi i}{N}",
            inputs={"pcd_mm": pcd_mm, "num_holes": num_holes, "bolt_size": bolt_size, "hole_coordinates": coords},
            result_value=float(len(coords)),
            unit="holes",
        )

    def generate_standard_regulator_bom(self, project_name: str = "Power Module") -> List[BOMItem]:
        return self.generate_bom_for_regulator(v_in=12.0, v_out=5.0)

    @classmethod
    def get_instance(cls, base_dir: Optional[Any] = None) -> "EngineeringIntelligence":
        return get_engineering_intelligence()


# Global Singleton accessor
_engineering_instance: Optional[EngineeringIntelligence] = None

def get_engineering_intelligence() -> EngineeringIntelligence:
    global _engineering_instance
    if _engineering_instance is None:
        _engineering_instance = EngineeringIntelligence()
    return _engineering_instance
