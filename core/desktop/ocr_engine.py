"""
core/desktop/ocr_engine.py — Multi-engine OCR and on-screen text detection.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from PIL import Image

logger = logging.getLogger("JARVIS.OCREngine")


@dataclass
class OCRTextBox:
    text: str
    rect: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float = 1.0

    @property
    def center(self) -> Tuple[int, int]:
        x, y, w, h = self.rect
        return (x + w // 2, y + h // 2)

    def contains(self, px: int, py: int) -> bool:
        x, y, w, h = self.rect
        return x <= px <= x + w and y <= py <= y + h


class OCREngine:
    """Extracts on-screen text with bounding boxes using graceful fallback engines."""

    def __init__(self):
        self._easyocr_reader = None
        self._easyocr_attempted = False

    def detect_text(self, image: Image.Image, offset: Tuple[int, int] = (0, 0)) -> List[OCRTextBox]:
        """Detect text boxes in image with (x_offset, y_offset) screen coordinates."""
        # 1. Try EasyOCR if installed
        results = self._try_easyocr(image, offset)
        if results:
            return results

        # 2. Try Windows UI Automation text as native fallback
        results = self._try_uia_text(offset)
        if results:
            return results

        return []

    def _try_easyocr(self, image: Image.Image, offset: Tuple[int, int]) -> List[OCRTextBox]:
        if not self._easyocr_attempted:
            self._easyocr_attempted = True
            try:
                import easyocr
                self._easyocr_reader = easyocr.Reader(["en"], gpu=False)
                logger.info("EasyOCR initialized successfully.")
            except Exception:
                self._easyocr_reader = None

        if self._easyocr_reader is None:
            return []

        try:
            import numpy as np
            arr = np.array(image)
            raw = self._easyocr_reader.readtext(arr)
            boxes = []
            ox, oy = offset
            for bbox, text, conf in raw:
                # bbox is [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                pts = [[int(p[0]), int(p[1])] for p in bbox]
                min_x = min(p[0] for p in pts) + ox
                min_y = min(p[1] for p in pts) + oy
                max_x = max(p[0] for p in pts) + ox
                max_y = max(p[1] for p in pts) + oy
                boxes.append(
                    OCRTextBox(
                        text=text.strip(),
                        rect=(min_x, min_y, max_x - min_x, max_y - min_y),
                        confidence=float(conf),
                    )
                )
            return boxes
        except Exception as e:
            logger.debug("EasyOCR detection error: %s", e)
            return []

    def _try_uia_text(self, offset: Tuple[int, int]) -> List[OCRTextBox]:
        """Fallback to Windows UI Automation native accessible elements."""
        try:
            from .ui_automation import get_ui_automation
            engine = get_ui_automation()
            elems = engine.get_active_window_elements()
            boxes = []
            for el in elems:
                if el.name:
                    l, t, r, b = el.rect
                    boxes.append(
                        OCRTextBox(
                            text=el.name,
                            rect=(l, t, r - l, b - t),
                            confidence=0.95,
                        )
                    )
            return boxes
        except Exception:
            return []

    def find_text(self, query: str, image: Image.Image, offset: Tuple[int, int] = (0, 0)) -> Optional[OCRTextBox]:
        """Find the text box matching query string."""
        boxes = self.detect_text(image, offset)
        q = query.strip().lower()
        # Exact match
        for b in boxes:
            if b.text.lower() == q:
                return b
        # Substring
        for b in boxes:
            if q in b.text.lower():
                return b
        return None


_ocr_engine_instance: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    global _ocr_engine_instance
    if _ocr_engine_instance is None:
        _ocr_engine_instance = OCREngine()
    return _ocr_engine_instance
