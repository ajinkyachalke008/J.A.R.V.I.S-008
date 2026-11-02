"""
core/desktop — Universal Desktop Perception, Automation, and Safety System for JARVIS MARK LVI.
"""
from __future__ import annotations

from .access_manager import DesktopAccessManager, DesktopAccessState, PermissionScope, get_access_manager
from .emergency_stop import EmergencyStopController, get_emergency_stop

__all__ = [
    "DesktopAccessManager",
    "DesktopAccessState",
    "PermissionScope",
    "get_access_manager",
    "EmergencyStopController",
    "get_emergency_stop",
]
