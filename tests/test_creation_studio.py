"""
Unit tests for Creation Studio models, validation, and domain engines.
"""
from core.studio.cad_engine import CADEngine
from core.studio.circuit_engine import CircuitEngine
from core.studio.models import Element, Layer, StudioProject
from core.studio.project_manager import ProjectManager
from core.studio.validator import ProjectValidator
from core.studio.workflow_engine import WorkflowEngine


def test_cad_mounting_plate_demonstrator():
    proj = CADEngine.create_mounting_plate_demonstrator()
    assert proj.domain == "cad"
    assert proj.canvas.units == "mm"
    assert len(proj.elements) >= 9

    # Verify outer plate
    outer = [el for el in proj.elements if el.id == "outer_plate"][0]
    assert outer.type == "rect"
    assert outer.geometry["width"] == 120.0
    assert outer.geometry["height"] == 80.0
    assert outer.geometry["corner_radius"] == 5.0

    # Verify 4 mounting holes
    holes = [el for el in proj.elements if el.properties.get("type") == "mounting_hole_M4"]
    assert len(holes) == 4
    for h in holes:
        assert h.geometry["r"] == 2.25  # 4.5mm dia / 2

    # Verify center cutout
    cutout = [el for el in proj.elements if el.id == "center_cutout"][0]
    assert cutout.geometry["width"] == 40.0
    assert cutout.geometry["height"] == 30.0

    # Validate
    is_valid, errors = ProjectValidator.validate(proj)
    assert is_valid, f"CAD demonstrator validation failed: {errors}"


def test_circuit_regulator_demonstrator():
    proj = CircuitEngine.create_regulator_demonstrator()
    assert proj.domain == "circuit"
    assert len(proj.elements) >= 7

    comps = [el for el in proj.elements if el.type == "component"]
    assert len(comps) >= 5

    # Check LM2596 IC
    u1 = [el for el in comps if el.properties.get("ref") == "U1"][0]
    assert len(u1.pins) == 5

    # Validate
    is_valid, errors = ProjectValidator.validate(proj)
    assert is_valid, f"Circuit validation failed: {errors}"


def test_workflow_agent_loop_demonstrator():
    proj = WorkflowEngine.create_agent_loop_demonstrator()
    assert proj.domain == "workflow"
    assert len(proj.elements) >= 10

    is_valid, errors = ProjectValidator.validate(proj)
    assert is_valid, f"Workflow validation failed: {errors}"


def test_project_undo_redo():
    pm = ProjectManager()
    pm.new_project("Test Undo", "cad")
    assert len(pm.project.elements) == 0

    el1 = Element(id="el1", type="circle", geometry={"cx": 10, "cy": 10, "r": 5})
    pm.add_element(el1)
    assert len(pm.project.elements) == 1

    el2 = Element(id="el2", type="line", geometry={"x1": 0, "y1": 0, "x2": 10, "y2": 10})
    pm.add_element(el2)
    assert len(pm.project.elements) == 2

    pm.undo()
    assert len(pm.project.elements) == 1
    assert pm.project.elements[0].id == "el1"

    pm.redo()
    assert len(pm.project.elements) == 2


def test_validator_detects_invalid():
    proj = StudioProject()
    # Negative width
    proj.elements.append(Element(id="bad_rect", type="rect", geometry={"width": -10, "height": 20}))
    is_valid, errors = ProjectValidator.validate(proj)
    assert not is_valid
    assert any("must be positive" in e for e in errors)

