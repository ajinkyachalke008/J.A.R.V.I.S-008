"""
Unit tests for EmergencyStopController.
"""
from core.desktop.access_manager import DesktopAccessState, get_access_manager
from core.desktop.emergency_stop import get_emergency_stop


def test_emergency_halt_sequence():
    mgr = get_access_manager()
    mgr.enable_full_control()
    assert mgr.is_control_enabled

    es = get_emergency_stop()
    halt_reasons = []
    es.register_callback(lambda r: halt_reasons.append(r))

    es.trigger_halt("test_emergency_halt")

    assert mgr.state == DesktopAccessState.ERROR
    assert not mgr.is_control_enabled
    assert len(halt_reasons) == 1
    assert halt_reasons[0] == "test_emergency_halt"

