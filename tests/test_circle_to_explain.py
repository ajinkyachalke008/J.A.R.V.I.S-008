"""
Unit tests for Circle-to-Explain (C2U) pipeline and image command dispatch.
"""
import io
from unittest.mock import MagicMock
from PIL import Image
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication

from core.desktop.access_manager import DesktopAccessManager, DesktopAccessState, PermissionScope
from core.desktop.screen_capture import ScreenCaptureService
from core.desktop.selection_overlay import SelectionOverlayWindow, get_selection_overlay


def test_screen_capture_auto_observe_permission():
    """Verify ScreenCaptureService auto-promotes DISABLED to OBSERVE_ONLY for read-only capture."""
    mgr = DesktopAccessManager()
    assert mgr.state == DesktopAccessState.DISABLED

    svc = ScreenCaptureService()
    svc._access_mgr = mgr

    # Should not raise PermissionError; should auto-enable OBSERVE_ONLY
    svc._verify_permission()
    assert mgr.state == DesktopAccessState.OBSERVE_ONLY
    assert mgr.check_permission(PermissionScope.SCREEN_CAPTURE)


def test_selection_overlay_callback_and_emission():
    """Verify SelectionOverlayWindow emits region_selected with cropped JPEG bytes."""
    app = QApplication.instance() or QApplication([])

    received = []

    def _callback(pil_img, img_bytes, mime_type, qrect):
        received.append((pil_img, img_bytes, mime_type, qrect))

    overlay = SelectionOverlayWindow(_callback)

    # Provide a mock frozen 200x200 image
    mock_img = Image.new("RGB", (200, 200), color=(50, 100, 150))
    overlay._frozen_image = mock_img

    # Simulate drawing a circle / region from (20, 20) to (80, 80)
    overlay._points = [QPoint(20, 20), QPoint(80, 20), QPoint(80, 80), QPoint(20, 80)]
    overlay._finalize_selection()

    assert len(received) == 1
    cropped, jpeg_b, mime_t, qrect = received[0]
    assert mime_t == "image/jpeg"
    assert len(jpeg_b) > 0
    assert qrect.width() == 60
    assert qrect.height() == 60
    assert cropped.size == (60, 60)


def test_selection_overlay_set_callback_no_duplicate():
    """Verify set_callback replaces previous callback and does not accumulate duplicate signals."""
    app = QApplication.instance() or QApplication([])
    overlay = SelectionOverlayWindow()

    calls = []
    cb1 = lambda *args: calls.append("cb1")
    cb2 = lambda *args: calls.append("cb2")

    overlay.set_callback(cb1)
    overlay.set_callback(cb2)

    mock_img = Image.new("RGB", (100, 100), color=(0, 255, 0))
    overlay._frozen_image = mock_img
    overlay._points = [QPoint(10, 10), QPoint(50, 50)]
    overlay._finalize_selection()

    # Only cb2 should have been called, exactly once
    assert calls == ["cb2"]

