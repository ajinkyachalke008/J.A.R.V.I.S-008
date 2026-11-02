"""
Unit tests for MonitorManager, VisualGroundingEngine, and OCRTextBox.
"""
from core.desktop.monitor_manager import MonitorInfo, get_monitor_manager
from core.desktop.ocr_engine import OCRTextBox
from core.desktop.visual_grounding import get_visual_grounding


def test_monitor_manager_basics():
    mgr = get_monitor_manager()
    assert len(mgr.monitors) >= 1
    prim = mgr.primary_monitor
    assert prim is not None
    assert prim.width > 0 and prim.height > 0

    bounds = mgr.get_virtual_desktop_bounds()
    assert len(bounds) == 4
    assert bounds[2] >= prim.width
    assert bounds[3] >= prim.height


def test_visual_grounding_normalization():
    vg = get_visual_grounding()
    mon = get_monitor_manager().primary_monitor

    # Center of screen: normalized (500, 500)
    sx, sy = vg.normalized_to_screen(500, 500)
    expected_x = mon.left + int(0.5 * mon.width)
    expected_y = mon.top + int(0.5 * mon.height)
    assert abs(sx - expected_x) <= 2
    assert abs(sy - expected_y) <= 2

    # Roundtrip: screen to normalized
    nx, ny = vg.screen_to_normalized(sx, sy)
    assert abs(nx - 500) <= 2
    assert abs(ny - 500) <= 2


def test_ocr_textbox():
    box = OCRTextBox(text="Submit", rect=(100, 200, 80, 30))
    assert box.center == (140, 215)
    assert box.contains(120, 210)
    assert not box.contains(50, 50)

