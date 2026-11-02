"""
core/desktop/access_manager.py — Centralized desktop access and permission manager for JARVIS MARK LVI.

Ensures no desktop interaction (screen reading, mouse motion, clicking, typing)
happens without explicit user authorization, verified permissions, and session timeout guards.
"""
from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional, Set

logger = logging.getLogger("JARVIS.DesktopAccess")


class DesktopAccessState(str, enum.Enum):
    DISABLED = "disabled"               # Default: No automation or screen reading allowed
    OBSERVE_ONLY = "observe_only"       # Screen capture and UI tree reading allowed; no mouse/keyboard
    CONTROL_ENABLED = "control_enabled" # Full authorized mouse and keyboard execution active
    PAUSED = "paused"                   # Temporarily paused; all inputs rejected
    ERROR = "error"                     # Safety fault or emergency stop triggered


class PermissionScope(str, enum.Enum):
    SCREEN_CAPTURE = "screen_capture"
    ACTIVE_WINDOW_READ = "active_window_read"
    UI_AUTOMATION_READ = "ui_automation_read"
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DRAG = "mouse_drag"
    KEYBOARD_INPUT = "keyboard_input"
    CLIPBOARD_ACCESS = "clipboard_access"
    FILE_ACCESS = "file_access"
    EXTERNAL_DATA_SUBMISSION = "external_data_submission"
    SHELL_EXECUTION = "shell_execution"


# Scopes granted automatically per state
_OBSERVE_SCOPES: Set[PermissionScope] = {
    PermissionScope.SCREEN_CAPTURE,
    PermissionScope.ACTIVE_WINDOW_READ,
    PermissionScope.UI_AUTOMATION_READ,
}

_CONTROL_SCOPES: Set[PermissionScope] = _OBSERVE_SCOPES | {
    PermissionScope.MOUSE_MOVE,
    PermissionScope.MOUSE_CLICK,
    PermissionScope.MOUSE_DRAG,
    PermissionScope.KEYBOARD_INPUT,
    PermissionScope.CLIPBOARD_ACCESS,
}

# High-risk scopes that are NEVER granted automatically without explicit invocation
_HIGH_RISK_SCOPES: Set[PermissionScope] = {
    PermissionScope.FILE_ACCESS,
    PermissionScope.EXTERNAL_DATA_SUBMISSION,
    PermissionScope.SHELL_EXECUTION,
}


@dataclass
class DesktopSession:
    token: str
    state: DesktopAccessState
    granted_scopes: Set[PermissionScope]
    created_at: float = field(default_factory=time.monotonic)
    last_activity_at: float = field(default_factory=time.monotonic)
    duration_seconds: float = 1800.0  # 30 minutes default
    idle_timeout_seconds: float = 600.0  # 10 minutes idle timeout

    def is_expired(self) -> bool:
        now = time.monotonic()
        if (now - self.created_at) > self.duration_seconds:
            return True
        if (now - self.last_activity_at) > self.idle_timeout_seconds:
            return True
        return False

    def touch(self) -> None:
        self.last_activity_at = time.monotonic()


class DesktopAccessManager:
    """Thread-safe permission and session manager for desktop automation."""

    def __init__(self):
        self._lock = threading.RLock()
        self._state = DesktopAccessState.DISABLED
        self._session: Optional[DesktopSession] = None
        self._state_callbacks: list[Callable[[DesktopAccessState, dict], None]] = []
        self._active_task_canceller: Optional[Callable[[], None]] = None

    @property
    def state(self) -> DesktopAccessState:
        with self._lock:
            if self._session and self._session.is_expired():
                self._revoke_internal("session_expired")
            return self._state

    @property
    def is_control_enabled(self) -> bool:
        return self.state == DesktopAccessState.CONTROL_ENABLED

    @property
    def is_observe_enabled(self) -> bool:
        return self.state in (DesktopAccessState.OBSERVE_ONLY, DesktopAccessState.CONTROL_ENABLED)

    def enable_observe_only(self, duration_s: float = 1800.0) -> bool:
        """Enable desktop observation without input control."""
        with self._lock:
            token = str(uuid.uuid4())
            self._session = DesktopSession(
                token=token,
                state=DesktopAccessState.OBSERVE_ONLY,
                granted_scopes=set(_OBSERVE_SCOPES),
                duration_seconds=duration_s,
            )
            self._state = DesktopAccessState.OBSERVE_ONLY
            logger.info("Desktop Access: OBSERVE_ONLY enabled (session %s)", token[:8])
            self._notify_state_change({"reason": "enabled_observe", "token": token})
            return True

    def enable_full_control(self, duration_s: float = 1800.0) -> bool:
        """Enable full desktop observation and mouse/keyboard automation."""
        with self._lock:
            token = str(uuid.uuid4())
            self._session = DesktopSession(
                token=token,
                state=DesktopAccessState.CONTROL_ENABLED,
                granted_scopes=set(_CONTROL_SCOPES),
                duration_seconds=duration_s,
            )
            self._state = DesktopAccessState.CONTROL_ENABLED
            logger.info("Desktop Access: FULL CONTROL enabled (session %s)", token[:8])
            self._notify_state_change({"reason": "enabled_full_control", "token": token})
            return True

    def pause(self) -> None:
        """Pause the current session, holding input authorization."""
        with self._lock:
            if self._state in (DesktopAccessState.CONTROL_ENABLED, DesktopAccessState.OBSERVE_ONLY):
                self._state = DesktopAccessState.PAUSED
                logger.info("Desktop Access: PAUSED")
                self._notify_state_change({"reason": "paused"})

    def resume(self) -> bool:
        """Resume a paused session if valid."""
        with self._lock:
            if self._state == DesktopAccessState.PAUSED and self._session and not self._session.is_expired():
                self._state = self._session.state
                self._session.touch()
                logger.info("Desktop Access: RESUMED to %s", self._state.value)
                self._notify_state_change({"reason": "resumed"})
                return True
            return False

    def revoke(self, reason: str = "user_revoked") -> None:
        """Immediately terminate desktop access and clear session."""
        with self._lock:
            self._revoke_internal(reason)

    def _revoke_internal(self, reason: str) -> None:
        if self._active_task_canceller:
            try:
                self._active_task_canceller()
            except Exception as e:
                logger.error("Error cancelling active desktop task: %s", e)
        self._state = DesktopAccessState.DISABLED
        self._session = None
        logger.info("Desktop Access: REVOKED (reason: %s)", reason)
        self._notify_state_change({"reason": reason})

    def emergency_halt(self, source: str = "emergency_stop") -> None:
        """Emergency fail-safe trigger."""
        with self._lock:
            if self._active_task_canceller:
                try:
                    self._active_task_canceller()
                except Exception as e:
                    logger.error("Error in task cancel during halt: %s", e)
            self._state = DesktopAccessState.ERROR
            self._session = None
            logger.warning("Desktop Access: EMERGENCY HALT TRIGGERED by %s", source)
            self._notify_state_change({"reason": "emergency_halt", "source": source})

    def check_permission(self, scope: PermissionScope | str) -> bool:
        """Verify whether an action has the required scope granted."""
        if isinstance(scope, str):
            try:
                scope = PermissionScope(scope.lower())
            except ValueError:
                return False

        with self._lock:
            if self.state in (DesktopAccessState.DISABLED, DesktopAccessState.PAUSED, DesktopAccessState.ERROR):
                return False
            if not self._session or self._session.is_expired():
                self._revoke_internal("session_expired")
                return False

            if scope in self._session.granted_scopes:
                self._session.touch()
                return True
            return False

    def grant_extra_scope(self, scope: PermissionScope) -> bool:
        """Grant an explicit additional scope (e.g., file access or shell execution)."""
        with self._lock:
            if self._session and not self._session.is_expired():
                self._session.granted_scopes.add(scope)
                logger.info("Desktop Access: Extra scope granted: %s", scope.value)
                return True
            return False

    def register_state_listener(self, callback: Callable[[DesktopAccessState, dict], None]) -> None:
        """Register a callback for UI updates when desktop state changes."""
        with self._lock:
            if callback not in self._state_callbacks:
                self._state_callbacks.append(callback)

    def unregister_state_listener(self, callback: Callable[[DesktopAccessState, dict], None]) -> None:
        with self._lock:
            if callback in self._state_callbacks:
                self._state_callbacks.remove(callback)

    def set_task_canceller(self, canceller: Optional[Callable[[], None]]) -> None:
        with self._lock:
            self._active_task_canceller = canceller

    def _notify_state_change(self, details: dict) -> None:
        for cb in list(self._state_callbacks):
            try:
                cb(self._state, details)
            except Exception as e:
                logger.error("DesktopAccess listener error: %s", e)

    def get_status_dict(self) -> dict:
        with self._lock:
            return {
                "state": self.state.value,
                "is_control_enabled": self.is_control_enabled,
                "is_observe_enabled": self.is_observe_enabled,
                "session_active": self._session is not None and not self._session.is_expired(),
                "granted_scopes": [s.value for s in self._session.granted_scopes] if self._session else [],
                "remaining_seconds": max(0.0, self._session.duration_seconds - (time.monotonic() - self._session.created_at)) if self._session else 0.0,
            }


# Global Singleton instance
_access_manager_instance: Optional[DesktopAccessManager] = None
_instance_lock = threading.Lock()


def get_access_manager() -> DesktopAccessManager:
    global _access_manager_instance
    with _instance_lock:
        if _access_manager_instance is None:
            _access_manager_instance = DesktopAccessManager()
        return _access_manager_instance
