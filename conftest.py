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
