"""
core/desktop/selection_overlay.py — Multi-monitor transparent PyQt6 overlay for Circle-to-Understand.
"""
from __future__ import annotations

import io
import logging
from typing import Callable, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget

from .monitor_manager import get_monitor_manager
from .screen_capture import get_screen_capture

logger = logging.getLogger("JARVIS.SelectionOverlay")


class SelectionOverlayWindow(QWidget):
    """Fullscreen multi-monitor overlay for freeform lasso and rectangle selection."""

    region_selected = pyqtSignal(object, bytes, str, object)  # (PIL.Image, bytes, mime_type, QRect)

    def __init__(self, on_selected: Optional[Callable[[Image.Image, bytes, str, QRect], None]] = None):
        super().__init__()
        if on_selected:
            self.region_selected.connect(on_selected)

        self._monitor_mgr = get_monitor_manager()
        self._capture_svc = get_screen_capture()

        self._frozen_pixmap: Optional[QPixmap] = None
        self._frozen_image: Optional[Image.Image] = None
        self._virtual_bounds = (0, 0, 1920, 1080)

        # Drawing state
        self._mode = "freeform"  # "freeform" or "rectangle"
        self._drawing = False
        self._points: list[QPoint] = []
        self._start_pos = QPoint()
        self._current_pos = QPoint()

        self._init_window()

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def activate_overlay(self, mode: str = "freeform") -> None:
        """Freeze desktop and display selection overlay across all monitors."""
        self._mode = mode
        self._points.clear()
        self._drawing = False

        # 1. Capture screen before opening overlay
        min_l, min_t, total_w, total_h = self._monitor_mgr.get_virtual_desktop_bounds()
        self._virtual_bounds = (min_l, min_t, total_w, total_h)

        try:
            pil_img, _, _ = self._capture_svc.capture_full_desktop(compress=False, max_size=None)
            self._frozen_image = pil_img
            # Convert to QPixmap
            raw_data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
            qim = QImage(raw_data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
            self._frozen_pixmap = QPixmap.fromImage(qim)
        except Exception as e:
            logger.error("Failed to capture freeze frame for overlay: %s", e)
            self._frozen_pixmap = None
            self._frozen_image = None

        self.setGeometry(min_l, min_t, total_w, total_h)
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw frozen desktop
        if self._frozen_pixmap:
            painter.drawPixmap(0, 0, self._frozen_pixmap)
            # Semi-transparent dark overlay to focus attention
            painter.fillRect(self.rect(), QColor(0, 10, 20, 110))
        else:
            painter.fillRect(self.rect(), QColor(0, 10, 20, 160))

        # Draw HUD instruction banner at top
        banner_w, banner_h = 440, 36
        bx = (self.width() - banner_w) // 2
        painter.setBrush(QColor(0, 15, 25, 230))
        painter.setPen(QPen(QColor(0, 212, 255), 1))
        painter.drawRoundedRect(bx, 20, banner_w, banner_h, 4, 4)
        painter.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        painter.setPen(QColor(143, 252, 255))
        painter.drawText(
            QRect(bx, 20, banner_w, banner_h),
            Qt.AlignmentFlag.AlignCenter,
            "⚡ CIRCLE OR DRAG ANY AREA TO EXPLAIN [ESC TO CANCEL]",
        )

        # Draw active selection
        if self._drawing:
            pen = QPen(QColor(0, 212, 255), 2.5, Qt.PenStyle.SolidLine)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            if self._mode == "freeform" and len(self._points) > 1:
                path = QPainterPath()
                path.moveTo(self._points[0].x(), self._points[0].y())
                for pt in self._points[1:]:
                    path.lineTo(pt.x(), pt.y())
                # Semi-transparent cyan fill
                painter.setBrush(QColor(0, 212, 255, 35))
                painter.drawPath(path)
            elif self._mode == "rectangle":
                rect = QRect(self._start_pos, self._current_pos).normalized()
                painter.setBrush(QColor(0, 212, 255, 35))
                painter.drawRect(rect)
                # Dimension tag
                painter.setFont(QFont("Courier New", 8))
                painter.setPen(QColor(0, 212, 255))
                painter.drawText(rect.right() + 8, rect.bottom() + 4, f"{rect.width()}x{rect.height()}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._start_pos = event.pos()
            self._current_pos = event.pos()
            self._points = [event.pos()]
            self.update()

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._current_pos = event.pos()
            self._points.append(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            self.hide()
            self._finalize_selection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._drawing = False
            self.hide()
            logger.info("Selection overlay cancelled by user (ESC).")

    def _finalize_selection(self) -> None:
        """Extract cropped region and emit selection signal."""
        if not self._points or not self._frozen_image:
            return

        # Calculate bounding rect of drawn points
        xs = [pt.x() for pt in self._points]
        ys = [pt.y() for pt in self._points]
        min_x, max_x = max(0, min(xs)), min(self.width(), max(xs))
        min_y, max_y = max(0, min(ys)), min(self.height(), max(ys))

        width = max_x - min_x
        height = max_y - min_y

        # Minimum threshold to ignore accidental micro-clicks
        if width < 10 or height < 10:
            logger.info("Selection too small (<10px); discarded.")
            return

        target_rect = QRect(min_x, min_y, width, height)
        try:
            cropped = self._frozen_image.crop((min_x, min_y, max_x, max_y))
            buf = io.BytesIO()
            cropped.save(buf, format="JPEG", quality=88)
            jpeg_bytes = buf.getvalue()

            logger.info("Selection cropped: %dx%d (%d bytes)", width, height, len(jpeg_bytes))
            self.region_selected.emit(cropped, jpeg_bytes, "image/jpeg", target_rect)
        except Exception as e:
            logger.error("Failed to crop selected overlay region: %s", e)


_overlay_window_instance: Optional[SelectionOverlayWindow] = None


def get_selection_overlay(on_selected: Optional[Callable] = None) -> SelectionOverlayWindow:
    global _overlay_window_instance
    if _overlay_window_instance is None:
        import sys
        from PyQt6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)
        _overlay_window_instance = SelectionOverlayWindow(on_selected)
    elif on_selected:
        _overlay_window_instance.region_selected.connect(on_selected)
    return _overlay_window_instance
