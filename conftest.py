"""
Pytest configuration and global fixtures for J.A.R.V.I.S. — 008.
Ensures Qt OpenGL context sharing and QtWebEngine hooks are initialized before any QApplication is spawned.
"""
import sys
import os

from PyQt6.QtCore import Qt, QCoreApplication
try:
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except Exception:
    pass

try:
    import PyQt6.QtWebEngineWidgets
    import PyQt6.QtWebEngineCore
except ImportError:
    pass

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([sys.argv[0] if sys.argv else "jarvis", "--no-sandbox"])
    return app


@pytest.fixture(autouse=True)
def isolate_desktop_access_and_watchdog(monkeypatch):
    """Prevents developer's physical mouse corner position from tripping watchdog during automated test runs."""
    try:
        from core.desktop.access_manager import get_access_manager
        from core.desktop.emergency_stop import get_emergency_stop

        es = get_emergency_stop()
        es.stop_watchdog()
        mgr = get_access_manager()
        mgr.revoke("conftest_reset")

        monkeypatch.setattr(es, "start_watchdog", lambda: None)
        try:
            import pyautogui
            monkeypatch.setattr(pyautogui, "position", lambda: (960, 540))
        except Exception:
            pass

        yield

        es.stop_watchdog()
        mgr.revoke("conftest_teardown")
    except Exception:
        yield
