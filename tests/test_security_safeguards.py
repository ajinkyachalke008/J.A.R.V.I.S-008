"""
Security and failure-mode test suite for JARVIS Desktop Agent.
"""
from core.desktop.access_manager import (
    DesktopAccessManager,
    DesktopAccessState,
    DesktopSession,
    PermissionScope,
)
from actions.desktop_agent import desktop_agent


def test_unauthorized_execution_blocked():
    mgr = DesktopAccessManager()
    assert mgr.state == DesktopAccessState.DISABLED
    # Attempting to click without enabling control must fail
    res = desktop_agent({"action": "click", "x": 100, "y": 100})
    assert "status=failed" in res
    assert "Desktop access is disabled" in res


def test_session_token_expiration():
    mgr = DesktopAccessManager()
    mgr.enable_full_control(duration_s=0.1)  # 100ms session
    assert mgr.is_control_enabled
    import time
    time.sleep(0.15)
    # Session must be expired and permission check must return False
    assert not mgr.check_permission(PermissionScope.MOUSE_CLICK)
    assert mgr.state == DesktopAccessState.DISABLED


def test_high_risk_scope_isolation():
    mgr = DesktopAccessManager()
    mgr.enable_full_control()
    # Shell execution and file destruction are never in default scopes
    assert not mgr.check_permission(PermissionScope.SHELL_EXECUTION)
    assert not mgr.check_permission(PermissionScope.FILE_ACCESS)

