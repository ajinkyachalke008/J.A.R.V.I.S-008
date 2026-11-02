"""
Unit tests for DesktopAccessManager.
"""
import time
import pytest
from core.desktop.access_manager import (
    DesktopAccessManager,
    DesktopAccessState,
    PermissionScope,
)


def test_initial_state_disabled():
    mgr = DesktopAccessManager()
    assert mgr.state == DesktopAccessState.DISABLED
    assert not mgr.is_control_enabled
    assert not mgr.is_observe_enabled
    assert not mgr.check_permission(PermissionScope.SCREEN_CAPTURE)
    assert not mgr.check_permission(PermissionScope.MOUSE_CLICK)


def test_enable_observe_only():
    mgr = DesktopAccessManager()
    mgr.enable_observe_only()
    assert mgr.state == DesktopAccessState.OBSERVE_ONLY
    assert mgr.is_observe_enabled
    assert not mgr.is_control_enabled
    # Observe scopes should pass
    assert mgr.check_permission(PermissionScope.SCREEN_CAPTURE)
    assert mgr.check_permission(PermissionScope.UI_AUTOMATION_READ)
    # Control scopes should fail
    assert not mgr.check_permission(PermissionScope.MOUSE_CLICK)
    assert not mgr.check_permission(PermissionScope.KEYBOARD_INPUT)


def test_enable_full_control():
    mgr = DesktopAccessManager()
    mgr.enable_full_control()
    assert mgr.state == DesktopAccessState.CONTROL_ENABLED
    assert mgr.is_control_enabled
    assert mgr.is_observe_enabled
    assert mgr.check_permission(PermissionScope.SCREEN_CAPTURE)
    assert mgr.check_permission(PermissionScope.MOUSE_MOVE)
    assert mgr.check_permission(PermissionScope.MOUSE_CLICK)
    assert mgr.check_permission(PermissionScope.KEYBOARD_INPUT)
    # High-risk scope not granted by default
    assert not mgr.check_permission(PermissionScope.SHELL_EXECUTION)


def test_pause_and_resume():
    mgr = DesktopAccessManager()
    mgr.enable_full_control()
    mgr.pause()
    assert mgr.state == DesktopAccessState.PAUSED
    assert not mgr.is_control_enabled
    assert not mgr.check_permission(PermissionScope.MOUSE_CLICK)

    ok = mgr.resume()
    assert ok
    assert mgr.state == DesktopAccessState.CONTROL_ENABLED
    assert mgr.is_control_enabled


def test_revoke():
    mgr = DesktopAccessManager()
    mgr.enable_full_control()
    mgr.revoke("user_stop")
    assert mgr.state == DesktopAccessState.DISABLED
    assert not mgr.is_control_enabled
    assert not mgr.check_permission(PermissionScope.SCREEN_CAPTURE)


def test_state_change_listener():
    mgr = DesktopAccessManager()
    events = []

    def _listener(state, details):
        events.append((state, details.get("reason")))

    mgr.register_state_listener(_listener)
    mgr.enable_observe_only()
    mgr.enable_full_control()
    mgr.revoke("test")

    assert len(events) == 3
    assert events[0][0] == DesktopAccessState.OBSERVE_ONLY
    assert events[1][0] == DesktopAccessState.CONTROL_ENABLED
    assert events[2][0] == DesktopAccessState.DISABLED

